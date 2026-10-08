"""doc validate 通過時的輸出呈現（0.5.0-W1-108）。

E1：同一個 UC，通過時須列出已執行且通過的檢查，且不出現 /spec 路由。
E2：flow 順序錯誤的 UC 仍以 exit 1 結束（輸出改動不得吞掉失敗）。
SPEC 非 data-contract：先列已通過檢查，仍保留 /spec validate 路由提示。
"""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system.commands.validate import execute
from doc_system.core.file_locator import FileLocator


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _step(step_id: str, next_ids: list[str]) -> str:
    nxt = "[" + ", ".join(f'"{n}"' for n in next_ids) + "]"
    return (
        f'  - id: "{step_id}"\n    name: "n{step_id}"\n    next: {nxt}\n'
        "    branch_from: null\n    return_to: null\n    emits: []\n    consumes: []\n"
        "    traverses: []\n"
    )


def _uc(root: Path, steps: list[str]) -> None:
    _write(
        root, "docs/usecases/UC-01-sample.md",
        "---\nid: UC-01\ntitle: sample\n---\n# UC\n\n```yaml\nflow:\n" + "".join(steps) + "```\n",
    )


def _run(tmp_path: Path, doc_id: str, capsys) -> tuple[int, str]:
    with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
        with pytest.raises(SystemExit) as exc:
            execute(argparse.Namespace(doc_id=doc_id))
    return exc.value.code, capsys.readouterr().out


class TestUcPassOutput:
    def test_e1_uc_lists_passed_checks_without_spec_route(self, tmp_path, capsys):
        _uc(tmp_path, [_step("s1", ["s2"]), _step("s2", [])])
        code, out = _run(tmp_path, "UC-01", capsys)
        assert code == 0
        assert "/spec" not in out
        assert "已執行" in out and "domain 引用" in out
        assert "branch_from" in out and "next" in out
        assert "不適用" in out and "data-contract" in out

    def test_e1_passed_checks_come_before_not_applicable(self, tmp_path, capsys):
        _uc(tmp_path, [_step("s1", [])])
        _, out = _run(tmp_path, "UC-01", capsys)
        assert out.index("已執行") < out.index("不適用")

    def test_e2_bad_flow_order_still_exits_1(self, tmp_path, capsys):
        _uc(tmp_path, [_step("s1", ["s3"]), _step("s2", ["s3"]), _step("s3", [])])
        code, out = _run(tmp_path, "UC-01", capsys)
        assert code == 1
        assert "已執行" not in out


class TestSpecNonDataContractOutput:
    def _spec(self, root: Path) -> None:
        _write(root, "docs/spec/ui/SPEC-001-x.md", "---\nid: SPEC-001\ntitle: x\n---\n# S\n")

    def test_lists_passed_checks_then_keeps_route_hint(self, tmp_path, capsys):
        self._spec(tmp_path)
        code, out = _run(tmp_path, "SPEC-001", capsys)
        assert code == 0
        assert "已執行" in out and "domain 引用" in out
        assert "/spec validate" in out
        assert out.index("已執行") < out.index("/spec validate")
        assert "flow" not in out.split("已執行")[1].split("不適用")[0]


def _bundle(root: Path) -> None:
    _write(
        root, "docs/spec/ui/domain-map.md",
        "---\nid: DOMAIN-MAP-ui\ntitle: ui\ndomain: ui\n---\n# ui\n",
    )


def _passed_section(out: str) -> str:
    """「已執行」到「略過」／「不適用」之間，即列為通過的檢查。"""
    body = out.split("已執行", 1)[1]
    for marker in ("略過", "不適用"):
        body = body.split(marker, 1)[0]
    return body


class TestOutputMatchesWhatRan:
    def test_e2_no_bundle_domain_check_not_listed_as_passed(self, tmp_path, capsys):
        _uc(tmp_path, [_step("s1", [])])
        code, out = _run(tmp_path, "UC-01", capsys)
        assert code == 0
        assert "domain 引用" not in _passed_section(out)
        assert "略過" in out and "DomainBundle" in out

    def test_e1_with_bundle_domain_check_listed_as_passed(self, tmp_path, capsys):
        _bundle(tmp_path)
        _uc(tmp_path, [_step("s1", [])])
        _, out = _run(tmp_path, "UC-01", capsys)
        assert "domain 引用" in _passed_section(out)

    def test_e2_spec_no_bundle_domain_check_skipped(self, tmp_path, capsys):
        _write(tmp_path, "docs/spec/ui/SPEC-001-x.md", "---\nid: SPEC-001\ntitle: x\n---\n# S\n")
        _, out = _run(tmp_path, "SPEC-001", capsys)
        assert "domain 引用" not in _passed_section(out)
        assert "/spec validate" in out

    def test_e2_uc_without_flow_block_flow_checks_not_listed_as_passed(self, tmp_path, capsys):
        _write(tmp_path, "docs/usecases/UC-01-sample.md", "---\nid: UC-01\ntitle: s\n---\n# UC\n")
        code, out = _run(tmp_path, "UC-01", capsys)
        assert code == 0
        passed = _passed_section(out)
        assert "branch_from" not in passed and "next" not in passed
        assert "略過" in out and "flow" in out

    def test_e2_prop_shows_no_spec_hint_and_no_uc_flow_text(self, tmp_path, capsys):
        _write(tmp_path, "docs/proposals/PROP-001-x.md", "---\nid: PROP-001\ntitle: x\n---\n# P\n")
        code, out = _run(tmp_path, "PROP-001", capsys)
        assert code == 0
        assert "/spec" not in out
        assert "UC flow" not in out
        assert "branch_from" not in out
