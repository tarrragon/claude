"""doc validate 驗證端接線：完整性各型、FlowStep 必填、validate-filenames 範圍、status 值域單一定義。

每項皆含「會紅的輸入」與「正向對照（欄位齊全）」，避免接線退化為空操作時仍全綠。
"""

import argparse
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system.commands import create as create_mod
from doc_system.commands import update as update_mod
from doc_system.commands.validate import execute, execute_filenames
from doc_system.core import tracking_schema
from doc_system.core.file_locator import FileLocator

DOC_SYSTEM = Path(tracking_schema.__file__).resolve().parent.parent


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(fn, tmp_path: Path, **kwargs) -> int:
    with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
        with pytest.raises(SystemExit) as exc:
            fn(argparse.Namespace(**kwargs))
    return exc.value.code


def _validate(tmp_path: Path, doc_id: str) -> int:
    return _run(execute, tmp_path, doc_id=doc_id)


# (doc_id, 路徑, 完整 frontmatter 欄位, 被移除後應報錯的欄位)
_CASES = {
    "PROP": ("PROP-001", "docs/proposals/PROP-001-x.md", ["id: PROP-001", "title: t", "status: draft"], "status"),
    "SPEC": ("SPEC-001", "docs/spec/core/SPEC-001-x.md", ["id: SPEC-001", "title: t", "status: draft"], "title"),
    "UC": ("UC-01", "docs/usecases/UC-01-x.md", ["id: UC-01", "title: t", "status: draft"], "status"),
    "DomainBundle": (
        "DOMAIN-MAP-core", "docs/spec/core/domain-map.md",
        ["id: DOMAIN-MAP-core", "domain: core"], "domain",
    ),
}


def _doc(root: Path, kind: str, drop: str | None) -> str:
    doc_id, rel, fields, _ = _CASES[kind]
    kept = [f for f in fields if drop is None or not f.startswith(f"{drop}:")]
    _write(root, rel, "---\n" + "\n".join(kept) + "\n---\n# body\n")
    return doc_id


class TestCompletenessWiring:
    @pytest.mark.parametrize("kind", list(_CASES))
    def test_missing_field_fails(self, tmp_path, capsys, kind):
        doc_id = _doc(tmp_path, kind, _CASES[kind][3])
        assert _validate(tmp_path, doc_id) == 1
        assert f"缺少必填欄位: {_CASES[kind][3]}" in capsys.readouterr().out

    @pytest.mark.parametrize("kind", list(_CASES))
    def test_complete_fields_pass(self, tmp_path, kind):
        assert _validate(tmp_path, _doc(tmp_path, kind, None)) == 0

    def test_null_value_counts_as_present(self, tmp_path):
        _write(tmp_path, "docs/usecases/UC-01-x.md", "---\nid: UC-01\ntitle: t\nstatus: null\n---\n")
        assert _validate(tmp_path, "UC-01") == 0


_STEP = (
    '  - id: "s1"\n    name: "n"\n    next: []\n    branch_from: null\n    return_to: null\n'
    "    emits: []\n    consumes: []\n    traverses: []\n"
)


def _uc_with_flow(root: Path, step: str) -> None:
    _write(
        root, "docs/usecases/UC-01-x.md",
        "---\nid: UC-01\ntitle: t\nstatus: draft\n---\n# UC\n\n```yaml\nflow:\n" + step + "```\n",
    )


class TestFlowStepRequiredFields:
    @pytest.mark.parametrize("field", sorted(tracking_schema.FLOWSTEP_REQUIRED_FIELDS - {"id"}))
    def test_missing_field_fails_with_location(self, tmp_path, capsys, field):
        step = "".join(line for line in _STEP.splitlines(True) if not line.startswith(f"    {field}:"))
        _uc_with_flow(tmp_path, step)
        assert _validate(tmp_path, "UC-01") == 1
        out = capsys.readouterr().out
        assert "flow[s1]" in out and f"缺少必填欄位: {field}" in out

    def test_complete_step_passes(self, tmp_path):
        _uc_with_flow(tmp_path, _STEP)
        assert _validate(tmp_path, "UC-01") == 0


class TestFilenamesCarrierScope:
    def test_file_outside_carrier_is_not_scanned(self, tmp_path):
        _write(tmp_path, "docs/spec/core/SPEC-001-x.md", "---\nid: SPEC-001\n---\n")
        _write(tmp_path, "docs/spec/core/notes/scratch.md", "# 非 carrier\n")
        _write(tmp_path, "docs/spec/README.md", "# 非 carrier\n")
        assert _run(execute_filenames, tmp_path) == 0

    def test_bad_name_inside_carrier_still_fails(self, tmp_path, capsys):
        _write(tmp_path, "docs/spec/core/SPEC-001-x.md", "---\nid: SPEC-001\n---\n")
        _write(tmp_path, "docs/spec/core/scratch.md", "# carrier 內壞檔名\n")
        assert _run(execute_filenames, tmp_path) == 1
        assert "scratch.md" in capsys.readouterr().out


class TestCarrierScopeFailureFallsBackToCheckAll:
    """範圍判定拿不到目錄資訊時退回全部檢查（改動前行為），不得靜默跳過或拋例外。"""

    @staticmethod
    def _spec_entry(**overrides):
        entry = {k: v for k, v in tracking_schema.GRAPH_NODE_TYPES["SPEC"].items() if k != "carrier_path_patterns"}
        entry.update(overrides)
        return entry

    @pytest.mark.parametrize("overrides", [{}, {"carrier_path_patterns": []}])
    def test_no_carrier_patterns_checks_every_file(self, tmp_path, capsys, monkeypatch, overrides):
        monkeypatch.setitem(tracking_schema.GRAPH_NODE_TYPES, "SPEC", self._spec_entry(**overrides))
        _write(tmp_path, "docs/spec/core/notes/scratch.md", "# 壞檔名\n")
        assert _run(execute_filenames, tmp_path) == 1
        assert "scratch.md" in capsys.readouterr().out

    def test_pattern_without_slash_checks_every_file(self, tmp_path, capsys, monkeypatch):
        entry = self._spec_entry(carrier_path_patterns=[{"pattern": r"^SPEC\.md$", "specificity": [1, 0]}])
        monkeypatch.setitem(tracking_schema.GRAPH_NODE_TYPES, "SPEC", entry)
        _write(tmp_path, "docs/spec/core/scratch.md", "# 壞檔名\n")
        assert _run(execute_filenames, tmp_path) == 1
        assert "scratch.md" in capsys.readouterr().out


class TestCreatedDocsPassValidate:
    """正向對照：doc create 產出的新檔須通過 doc validate（exit 0）。"""

    @staticmethod
    def _create(tmp_path: Path, **kwargs) -> None:
        from doc_system.commands.create import execute as create_execute

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            create_execute(argparse.Namespace(**kwargs))

    def test_proposal(self, tmp_path):
        self._create(tmp_path, type="proposal", id="PROP-001", title="提案", domain=None)
        assert _validate(tmp_path, "PROP-001") == 0

    def test_spec(self, tmp_path):
        self._create(tmp_path, type="spec", id="SPEC-001", title="規格", domain="auth")
        assert _validate(tmp_path, "SPEC-001") == 0

    # 建出來即紅（既有的 flow 主線 next 檢查對範本佔位步驟判紅，非本票接線造成），已回報 PM，不放寬判定。
    @pytest.mark.xfail(strict=True, reason="範本佔位 flow 步驟 next 指向自己，主線 next 檢查 exit 1")
    def test_usecase(self, tmp_path):
        self._create(tmp_path, type="usecase", id="UC-01", title="用例", domain=None)
        assert _validate(tmp_path, "UC-01") == 0

    # 範本開頭的 HTML 註解使 frontmatter 不在檔首，parse 不到 -> 找不到文件 exit 2；已回報 PM，不放寬判定。
    @pytest.mark.xfail(strict=True, reason="範本原樣複製：開頭註解使 frontmatter 解析失敗，exit 2")
    def test_domain_bundle_from_template(self, tmp_path):
        """DomainBundle 無 create 子命令，依範本指示複製後填入 id／domain。"""
        from doc_system.commands.create import _get_templates_dir

        text = (_get_templates_dir() / "domain-map-template.md").read_text(encoding="utf-8")
        text = text.replace("DOMAIN-MAP-{domain}", "DOMAIN-MAP-auth").replace("{domain 名稱}", "auth")
        _write(tmp_path, "docs/spec/auth/domain-map.md", text)
        assert _validate(tmp_path, "DOMAIN-MAP-auth") == 0


class TestStatusSingleDefinition:
    def test_update_references_schema_definition(self):
        assert update_mod.statuses_for_doc_id is tracking_schema.statuses_for_doc_id

    def test_create_initial_status_valid_for_every_type(self):
        assert create_mod.DOC_STATUSES_BY_TYPE is tracking_schema.DOC_STATUSES_BY_TYPE
        for statuses in tracking_schema.DOC_STATUSES_BY_TYPE.values():
            assert tracking_schema.DOC_INITIAL_STATUS in statuses

    def test_domains_split_by_type(self):
        by_type = tracking_schema.DOC_STATUSES_BY_TYPE
        assert by_type["PROP"] == ("draft", "discussing", "confirmed", "implemented", "withdrawn")
        for kind in ("SPEC", "UC", "EVT"):
            assert by_type[kind] == ("draft", "review", "approved", "deprecated")

    def test_status_tuple_literal_defined_once(self):
        literal = re.compile(r'"draft",\s*"discussing"')
        hits = [p.name for p in DOC_SYSTEM.rglob("*.py") if literal.search(p.read_text(encoding="utf-8"))]
        assert hits == ["tracking_schema.py"]


_EVT_PATH = "docs/events/EVT-AUTH-001-x.md"


def _evt(root: Path, status_line: str | None) -> None:
    lines = [
        "id: EVT-AUTH-001", "name: n", "canonical_name: c", "category: domain_event",
        "producers: [a]", "consumers: [b]",
    ]
    if status_line is not None:
        lines.append(status_line)
    _write(root, _EVT_PATH, "---\n" + "\n".join(lines) + "\n---\n# e\n")


def _typed_doc(root: Path, kind: str, status_line: str | None) -> str:
    doc_id, rel, fields, _ = _CASES[kind]
    kept = [f for f in fields if not f.startswith("status:")]
    if status_line is not None:
        kept.append(status_line)
    _write(root, rel, "---\n" + "\n".join(kept) + "\n---\n# body\n")
    return doc_id


class TestStatusDomainValidation:
    @pytest.mark.parametrize("kind,value", [
        ("PROP", "draft"), ("PROP", "discussing"), ("PROP", "confirmed"),
        ("PROP", "implemented"), ("PROP", "withdrawn"),
        ("SPEC", "draft"), ("SPEC", "review"), ("SPEC", "approved"), ("SPEC", "deprecated"),
        ("UC", "approved"), ("UC", "review"),
    ])
    def test_own_domain_value_passes(self, tmp_path, kind, value):
        assert _validate(tmp_path, _typed_doc(tmp_path, kind, f"status: {value}")) == 0

    @pytest.mark.parametrize("kind,value", [
        ("PROP", "approved"), ("PROP", "review"), ("PROP", "deprecated"),
        ("SPEC", "discussing"), ("SPEC", "confirmed"), ("SPEC", "implemented"),
        ("UC", "confirmed"), ("UC", "withdrawn"),
        ("SPEC", "aproved"), ("PROP", "confimed"),
        ("SPEC", '""'), ("UC", "' '"), ("UC", "Approved"), ("PROP", "123"),
    ])
    def test_out_of_domain_value_fails(self, tmp_path, capsys, kind, value):
        assert _validate(tmp_path, _typed_doc(tmp_path, kind, f"status: {value}")) == 1
        assert "status 值不合法" in capsys.readouterr().out

    @pytest.mark.parametrize("kind", ["PROP", "SPEC", "UC"])
    def test_absent_status_is_completeness_failure_not_domain_failure(self, tmp_path, capsys, kind):
        assert _validate(tmp_path, _typed_doc(tmp_path, kind, None)) == 1
        out = capsys.readouterr().out
        assert "缺少必填欄位: status" in out and "status 值不合法" not in out

    @pytest.mark.parametrize("kind", ["PROP", "SPEC", "UC"])
    def test_null_status_stays_present_and_passes(self, tmp_path, kind):
        assert _validate(tmp_path, _typed_doc(tmp_path, kind, "status:")) == 0

    @pytest.mark.parametrize("value", ["draft", "review", "approved", "deprecated"])
    def test_evt_own_domain_passes(self, tmp_path, value):
        _evt(tmp_path, f"status: {value}")
        assert _validate(tmp_path, "EVT-AUTH-001") == 0

    @pytest.mark.parametrize("value", ["discussing", "confirmed", "typo", '""'])
    def test_evt_out_of_domain_fails(self, tmp_path, capsys, value):
        _evt(tmp_path, f"status: {value}")
        assert _validate(tmp_path, "EVT-AUTH-001") == 1
        assert "status 值不合法" in capsys.readouterr().out

    def test_evt_absent_or_null_status_passes(self, tmp_path):
        _evt(tmp_path, None)
        assert _validate(tmp_path, "EVT-AUTH-001") == 0
        _evt(tmp_path, "status:")
        assert _validate(tmp_path, "EVT-AUTH-001") == 0
