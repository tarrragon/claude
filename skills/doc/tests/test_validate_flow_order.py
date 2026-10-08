"""doc validate 對 UC flow 區塊主線 next 與清單順序一致性的檢查，及 path_patterns 錯誤位置。

E2：主線 next 與清單順序不一致的 fixture 須 exit 1 並列出檔案與步驟位置。
E1：順序一致、分支步 next 任意、末步 next 為空的 fixture 須 exit 0。
另含：根層載體 docs/domain-map.md 的 path_patterns 錯誤須印實際載體路徑。
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


def _step(step_id: str, next_ids: list[str], branch_from: str | None = None) -> str:
    branch = "null" if branch_from is None else f'"{branch_from}"'
    nxt = "[" + ", ".join(f'"{n}"' for n in next_ids) + "]"
    return (
        f'  - id: "{step_id}"\n    name: "n{step_id}"\n    next: {nxt}\n'
        f"    branch_from: {branch}\n    return_to: null\n    emits: []\n    consumes: []\n"
        "    traverses: []\n"
    )


def _uc(root: Path, steps: list[str]) -> None:
    _write(
        root, "docs/usecases/UC-01-sample.md",
        "---\nid: UC-01\ntitle: sample\n---\n# UC\n\n```yaml\nflow:\n" + "".join(steps) + "```\n",
    )


def _run(tmp_path: Path, doc_id: str) -> int:
    with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
        with pytest.raises(SystemExit) as exc:
            execute(argparse.Namespace(doc_id=doc_id))
    return exc.value.code


class TestMainlineNextOrder:
    def test_mismatched_mainline_next_fails_with_location(self, tmp_path, capsys):
        _uc(tmp_path, [_step("s1", ["s3"]), _step("s2", ["s3"]), _step("s3", [])])
        assert _run(tmp_path, "UC-01") == 1
        out = capsys.readouterr().out
        assert "UC-01-sample.md" in out and "flow[s1].next" in out and "s2" in out and "s3" in out

    def test_last_mainline_step_with_next_fails(self, tmp_path, capsys):
        _uc(tmp_path, [_step("s1", ["s2"]), _step("s2", ["s1"])])
        assert _run(tmp_path, "UC-01") == 1
        assert "flow[s2].next" in capsys.readouterr().out

    def test_consistent_mainline_passes(self, tmp_path):
        _uc(tmp_path, [_step("s1", ["s2"]), _step("s2", [])])
        assert _run(tmp_path, "UC-01") == 0

    def test_branch_next_is_unconstrained(self, tmp_path):
        steps = [_step("s1", ["s2"]), _step("b1", ["s1"], branch_from="s1"), _step("s2", [])]
        _uc(tmp_path, steps)
        assert _run(tmp_path, "UC-01") == 0

    def test_mainline_skipping_over_branch_passes(self, tmp_path):
        steps = [_step("s1", ["s2"]), _step("b1", ["s2"], branch_from="s1"), _step("s2", [])]
        _uc(tmp_path, steps)
        assert _run(tmp_path, "UC-01") == 0


class TestPathPatternLocation:
    def test_root_level_bundle_error_prints_actual_path(self, tmp_path, capsys):
        _write(
            tmp_path, "docs/domain-map.md",
            "---\nid: DOMAIN-MAP-root\ndomain: root\npath_patterns: [missing/]\n---\n# map\n",
        )
        assert _run(tmp_path, "DOMAIN-MAP-root") == 1
        out = capsys.readouterr().out
        assert str(tmp_path / "docs" / "domain-map.md") in out
        assert "docs/spec/root" not in out

    def test_spec_level_bundle_error_prints_actual_path(self, tmp_path, capsys):
        _write(
            tmp_path, "docs/spec/alpha/domain-map.md",
            "---\nid: DOMAIN-MAP-alpha\ndomain: alpha\npath_patterns: [missing/]\n---\n# map\n",
        )
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1
        assert str(tmp_path / "docs" / "spec" / "alpha" / "domain-map.md") in capsys.readouterr().out
