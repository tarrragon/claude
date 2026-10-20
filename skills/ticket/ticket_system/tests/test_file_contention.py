"""同檔票樹競爭計數測試（0.5.0-W1-338.1）。

fixture 為真實臨時 git repo，不 mock git；E1 對照：同一份 fixture 結構下，
「同票樹多次修改」與「不同票樹修改」輸出必須不同。
"""

from __future__ import annotations

import json
import subprocess
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.commands import track_conflicts
from ticket_system.lib import file_contention

from conftest import _ticket


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
         *args],
        check=True, capture_output=True,
    )


def _commit_edit(repo: Path, rel: str, subject: str, n: int) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"v{n}\n")
    _git(repo, "add", rel)
    _git(repo, "commit", "-m", subject)


def _repo(tmp_path: Path, subjects: list, rel: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    for i, subject in enumerate(subjects):
        _commit_edit(repo, rel, subject, i)
    return repo


def _run_conflicts(repo: Path, rel: str, capsys, fmt: str = "table"):
    tickets = [_ticket("A", "pending", [rel]), _ticket("B", "pending", [rel])]
    args = Namespace(version="9.9.9", all=False, format=fmt)
    with patch.object(track_conflicts, "_gather_tickets", return_value=tickets), \
         patch.object(track_conflicts, "get_project_root", return_value=repo), \
         patch.object(track_conflicts, "current_project_root", return_value=str(repo)), \
         patch.object(track_conflicts, "load_registry", return_value={"sessions": {}}):
        track_conflicts.execute_conflicts(args)
    return capsys.readouterr()


SAME_TREE = [
    "feat(0.5.0-W1-100): a",
    "feat(0.5.0-W1-100.1): b",
    "feat(0.5.0-W1-100.2): c",
]
DIFF_TREES = [
    "feat(0.5.0-W1-100): a",
    "feat(0.5.0-W1-200): b",
    "feat(0.5.0-W1-300): c",
]


class TestE1Contrast:
    def test_same_tree_vs_different_trees_outputs_differ(self, tmp_path, capsys):
        rel = "src/mod.py"
        same = _run_conflicts(_repo(tmp_path / "s", SAME_TREE, rel), rel, capsys)
        diff = _run_conflicts(_repo(tmp_path / "d", DIFF_TREES, rel), rel, capsys)
        assert same.out != diff.out
        assert "[競爭]" not in same.out  # 1 棵票樹不列
        assert same.out.count("[競爭]") < diff.out.count("[競爭]")
        assert "3 棵票樹" in diff.out and "建議拆分" in diff.out


class TestJsonKeepsAll:
    def test_json_contention_includes_single_tree_file(self, tmp_path, capsys):
        rel = "src/mod.py"
        out = _run_conflicts(_repo(tmp_path, SAME_TREE, rel), rel, capsys, "json").out
        records = json.loads(out)["contention"]
        assert [r["tree_count"] for r in records] == [1]


class TestAggregate:
    def test_aggregate_file_gets_note_not_split_advice(self, tmp_path, capsys):
        rel = ".claude/settings.json"
        out = _run_conflicts(_repo(tmp_path, DIFF_TREES, rel), rel, capsys).out
        assert "3 棵票樹" in out
        assert file_contention.AGGREGATE_NOTE in out
        assert "建議拆分" not in out

    def test_non_aggregate_gets_split_advice(self, tmp_path, capsys):
        rel = "src/mod.py"
        out = _run_conflicts(_repo(tmp_path, DIFF_TREES, rel), rel, capsys).out
        assert "建議拆分" in out
        assert file_contention.AGGREGATE_NOTE not in out

    @pytest.mark.parametrize("path", [
        "x/pm-registry.json", "CHANGELOG.md", "docs/work-logs/v0.5.0/v0.5.0-main.md",
        "docs/spec/index.md",
    ])
    def test_aggregate_classification(self, path):
        assert file_contention.is_aggregate_file(path)

    @pytest.mark.parametrize("path", [
        "src/mod.py", "docs/work-logs/v0.5.0/tickets/0.5.0-W1-001.md",
    ])
    def test_non_aggregate_classification(self, path):
        assert not file_contention.is_aggregate_file(path)


class TestMetaCommitsExcluded:
    def test_chore_commits_not_counted(self, tmp_path, capsys):
        rel = "src/mod.py"
        subjects = ["feat(0.5.0-W1-100): a", "chore(0.5.0-W1-200): m",
                    "chore(0.5.0-W1-300): m"]
        out = _run_conflicts(_repo(tmp_path, subjects, rel), rel, capsys, "json").out
        assert json.loads(out)["contention"][0]["tree_count"] == 1


class TestGitFailureDegrades:
    def test_non_git_dir_keeps_conflict_output_and_warns(self, tmp_path, capsys):
        plain = tmp_path / "plain"
        plain.mkdir()
        captured = _run_conflicts(plain, "src/mod.py", capsys)
        assert "A <-> B" in captured.out
        assert "[競爭]" not in captured.out
        assert "略過同檔票樹競爭訊號" in captured.err
