"""doc validate 對 depends_on_bundles 成環與 UC flow branch_from 結構錯誤的檢查。

E2：bundle 依賴成環、branch_from 成環、自指、懸空各一個該紅 fixture，須 exit 1 並列出檔案與路徑／id。
E1：各自的合法對照（無環依賴、合法分支鏈）須 exit 0。
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


def _bundle(root: Path, name: str, depends_on: list[str]) -> None:
    deps = "[" + ", ".join(f"DOMAIN-MAP-{d}" for d in depends_on) + "]"
    _write(
        root, f"docs/spec/{name}/domain-map.md",
        f"---\nid: DOMAIN-MAP-{name}\ndomain: {name}\ndepends_on_bundles: {deps}\n---\n# map\n",
    )


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


class TestBundleDependencyCycle:
    def test_two_bundle_cycle_fails_with_path(self, tmp_path, capsys):
        _bundle(tmp_path, "alpha", ["beta"])
        _bundle(tmp_path, "beta", ["alpha"])
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1
        out = capsys.readouterr().out
        assert "DOMAIN-MAP-alpha" in out and "DOMAIN-MAP-beta" in out and "->" in out

    def test_self_dependency_fails(self, tmp_path, capsys):
        _bundle(tmp_path, "alpha", ["alpha"])
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1
        assert "DOMAIN-MAP-alpha -> DOMAIN-MAP-alpha" in capsys.readouterr().out

    def test_three_bundle_cycle_fails_for_member_not_on_entry(self, tmp_path):
        _bundle(tmp_path, "alpha", ["beta"])
        _bundle(tmp_path, "beta", ["gamma"])
        _bundle(tmp_path, "gamma", ["beta"])
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 1

    def test_acyclic_chain_passes(self, tmp_path):
        _bundle(tmp_path, "alpha", ["beta", "gamma"])
        _bundle(tmp_path, "beta", ["gamma"])
        _bundle(tmp_path, "gamma", [])
        assert _run(tmp_path, "DOMAIN-MAP-alpha") == 0


class TestBranchFromStructure:
    def test_dangling_branch_from_fails_with_ids(self, tmp_path, capsys):
        _uc(tmp_path, [_step("s1", []), _step("b1", [], branch_from="ghost")])
        assert _run(tmp_path, "UC-01") == 1
        out = capsys.readouterr().out
        assert "UC-01-sample.md" in out and "flow[b1].branch_from" in out and "ghost" in out

    def test_self_branch_from_fails(self, tmp_path, capsys):
        _uc(tmp_path, [_step("s1", []), _step("b1", [], branch_from="b1")])
        assert _run(tmp_path, "UC-01") == 1
        out = capsys.readouterr().out
        assert "UC-01-sample.md" in out and "flow[b1].branch_from" in out and "自指" in out

    def test_branch_from_cycle_fails_with_path(self, tmp_path, capsys):
        _uc(
            tmp_path,
            [_step("s1", []), _step("b1", [], branch_from="b2"), _step("b2", [], branch_from="b1")],
        )
        assert _run(tmp_path, "UC-01") == 1
        out = capsys.readouterr().out
        assert "UC-01-sample.md" in out and "b1 -> b2 -> b1" in out

    def test_valid_branch_chain_passes(self, tmp_path):
        steps = [
            _step("s1", ["s2"]),
            _step("b1", ["s2"], branch_from="s1"),
            _step("b2", ["s2"], branch_from="b1"),
            _step("s2", []),
        ]
        _uc(tmp_path, steps)
        assert _run(tmp_path, "UC-01") == 0
