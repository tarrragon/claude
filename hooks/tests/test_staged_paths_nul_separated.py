"""提交守衛的路徑清單讀取改 -z 的 E2 測試（tmp git repo 真實 fixture）。

fixture 檔名含 CJK 與雙引號：即使 run_git_command 已帶 core.quotepath=false，
git 仍會為含雙引號、反斜線、tab 的路徑加引號並跳脫，只有 -z 能取得原始路徑。
另含純 CJK 與 ASCII 的對照，確認既有行為不退化。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stage_guard = _load("nul_stage_guard", "commit-stage-guard-gate-hook.py")
ref_guard = _load("nul_ref_guard", "git-ref-transaction-content-guard.py")
bare_guard = _load("nul_bare_guard", "bare-commit-guard-hook.py")
test_gate = _load("nul_test_gate", "hooks-test-gate-hook.py")

TRICKY = 'docs/文件"甲.md'
TRICKY_OLD = 'docs/舊"名.md'
TRICKY_NEW = 'docs/新"名.md'


def _git(repo, *args):
    result = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _write(root, "README.md", "base\n")
    _git(root, "add", "README.md")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _commit_rename(repo):
    """建立 TRICKY_OLD 後改名為 TRICKY_NEW，回傳 (改名前 sha, 改名後 sha)。"""
    _write(repo, TRICKY_OLD, "內容一\n內容二\n內容三\n")
    _git(repo, "add", "--", TRICKY_OLD)
    _git(repo, "commit", "-q", "-m", "add")
    pre = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", TRICKY_OLD, TRICKY_NEW)
    return pre


class TestCommitStageGuard:
    def test_staged_list_raw_path(self, repo):
        _write(repo, TRICKY, "內容\n")
        _git(repo, "add", "--", TRICKY)
        assert stage_guard._get_staged_file_list(repo) == [TRICKY]

    def test_staged_list_cjk_and_ascii(self, repo):
        _write(repo, "說明.md", "x\n")
        _write(repo, "a.md", "x\n")
        _git(repo, "add", "說明.md", "a.md")
        assert sorted(stage_guard._get_staged_file_list(repo)) == ["a.md", "說明.md"]

    def test_staged_list_empty(self, repo):
        assert stage_guard._get_staged_file_list(repo) == []

    def test_rename_map_three_segments(self, repo):
        _commit_rename(repo)
        assert stage_guard._get_staged_rename_map(repo) == {TRICKY_NEW: TRICKY_OLD}

    def test_rename_map_ascii(self, repo):
        _git(repo, "mv", "README.md", "README2.md")
        assert stage_guard._get_staged_rename_map(repo) == {"README2.md": "README.md"}

    def test_rename_map_ignores_modify_and_add(self, repo):
        _write(repo, "README.md", "base\nmore\n")
        _write(repo, "b.md", "b\n")
        _git(repo, "add", "README.md", "b.md")
        assert stage_guard._get_staged_rename_map(repo) == {}

    def test_rename_map_parses_status_and_paths_from_nul_stream(self, monkeypatch):
        stream = "R100\0old a.md\0new a.md\0M\0m.md\0A\0n.md\0R063\0x\0y\0"
        monkeypatch.setattr(
            stage_guard, "run_git_command", lambda *a, **k: (True, stream)
        )
        assert stage_guard._get_staged_rename_map(Path("/x")) == {
            "new a.md": "old a.md",
            "y": "x",
        }


class TestGitRefTransactionGuard:
    def _dangling(self, repo, rel, text):
        base = _git(repo, "rev-parse", "HEAD")
        _write(repo, rel, text)
        _git(repo, "add", "--", rel)
        tree = _git(repo, "write-tree")
        sha = _git(repo, "commit-tree", tree, "-p", base, "-m", "c")
        _git(repo, "reset", "-q", "--hard", base)
        return base, sha

    def test_changed_files_raw_path(self, repo):
        base, sha = self._dangling(repo, '.claude/references/文件"y.md', "x\n")
        assert ref_guard._changed_files(base, sha, repo) == [
            '.claude/references/文件"y.md'
        ]

    def test_changed_files_ascii(self, repo):
        base, sha = self._dangling(repo, "docs/a.md", "x\n")
        assert ref_guard._changed_files(base, sha, repo) == ["docs/a.md"]

    def test_added_text_obtainable(self, repo):
        rel = '.claude/references/文件"y.md'
        base, sha = self._dangling(repo, rel, "新增行\n")
        assert "新增行" in ref_guard._added_text(base, sha, rel, repo)

    def test_guard_denies_violation_in_tricky_path(self, repo):
        rel = '.claude/references/文件"y.md'
        base, sha = self._dangling(repo, rel, "引用 W9-501 的分析結論。\n")
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "git-ref-transaction-content-guard.py"),
             "prepared"],
            input=f"{base} {sha} refs/heads/main\n",
            cwd=str(repo),
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
        )
        assert result.returncode == 87  # guard EXIT_BLOCK 專用碼
        assert "reference-stability-rule8-guard" in result.stderr

    def test_rename_map_three_segments(self, repo):
        pre = _commit_rename(repo)
        _git(repo, "commit", "-q", "-m", "mv")
        post = _git(repo, "rev-parse", "HEAD")
        assert ref_guard._rename_map(pre, post, repo) == {TRICKY_NEW: TRICKY_OLD}

    def test_rename_map_parses_nul_stream(self, monkeypatch):
        stream = "R100\0a\0b\0M\0m\0"
        monkeypatch.setattr(ref_guard, "run_git_command", lambda *a, **k: (True, stream))
        assert ref_guard._rename_map("p", "n", Path("/x")) == {"b": "a"}


class TestBareCommitGuard:
    def test_staged_raw_path(self, repo):
        _write(repo, TRICKY, "x\n")
        _git(repo, "add", "--", TRICKY)
        assert bare_guard._get_staged_files(repo) == [TRICKY]

    def test_staged_subset_of_declared_files(self, repo):
        _write(repo, TRICKY, "x\n")
        _git(repo, "add", "--", TRICKY)
        staged = bare_guard._get_staged_files(repo)
        dispatches = [
            {"ticket_id": "T-1", "files": [TRICKY, "other.py"]},
            {"ticket_id": "T-2", "files": ["z.py"]},
        ]
        assert bare_guard._staged_scope_is_safe_for_bare_commit(staged, dispatches)

    def test_unstaged_tracked_raw_path(self, repo):
        _write(repo, TRICKY, "x\n")
        _git(repo, "add", "--", TRICKY)
        _git(repo, "commit", "-q", "-m", "add")
        _write(repo, TRICKY, "y\n")
        assert bare_guard._get_unstaged_tracked_files(repo) == [TRICKY]

    def test_ascii(self, repo):
        _write(repo, "a.py", "x\n")
        _git(repo, "add", "a.py")
        assert bare_guard._get_staged_files(repo) == ["a.py"]


class TestHooksTestGate:
    def test_rename_takes_new_path_from_nul_stream(self, monkeypatch):
        stream = (
            "R100\0.claude/hooks/old-hook.py\0.claude/hooks/new-hook.py\0"
            "D\0.claude/hooks/gone-hook.py\0M\0.claude/hooks/kept-hook.py\0"
            "M\0.claude/hooks/tests/test_x.py\0"
        )
        monkeypatch.setattr(test_gate, "run_git_command", lambda *a, **k: (True, stream))
        result = test_gate._touched_hook_filenames("git commit -m x", "/repo", MagicMock())
        assert result == {"new-hook.py", "kept-hook.py"}

    def test_real_repo_cjk_hook_filename(self, repo):
        _write(repo, ".claude/hooks/中文-hook.py", "x = 1\n")
        _git(repo, "add", "--", ".claude/hooks/中文-hook.py")
        result = test_gate._touched_hook_filenames("git commit -m x", str(repo), MagicMock())
        assert result == {"中文-hook.py"}

    def test_real_repo_rename(self, repo):
        _write(repo, ".claude/hooks/old-hook.py", "a = 1\nb = 2\nc = 3\n")
        _git(repo, "add", "--", ".claude/hooks/old-hook.py")
        _git(repo, "commit", "-q", "-m", "add")
        _git(repo, "mv", ".claude/hooks/old-hook.py", ".claude/hooks/new-hook.py")
        result = test_gate._touched_hook_filenames("git commit -m x", str(repo), MagicMock())
        assert result == {"new-hook.py"}
