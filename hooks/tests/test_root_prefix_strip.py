"""
Test: 根前綴剝除共用函式與兩個呼叫點（lib/path_permission、ticket-file-access-guard）

驗證項目：
1. strip_root_prefix：分隔符、磁碟機代號大小寫、目錄邊界
2. path_permission：代號大小寫不一的 Windows 路徑，.claude/、docs/ 放行；
   lib/、test/ 仍拒絕（正向對照）；同字首兄弟目錄不被剝成 `-wt/...`
3. ticket-file-access-guard：代號大小寫不一時仍判為票；同 repo 相鄰 worktree
   的票檔判為票；不同 repo 的同字首目錄不判為票（對照）
"""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))

from lib import path_permission as pp  # noqa: E402
from lib.checkout_identity import (  # noqa: E402
    strip_root_prefix,
    strip_same_repo_checkout_prefix,
)

_LOG = logging.getLogger("test_root_prefix_strip")


def _load_ticket_guard():
    path = CLAUDE_DIR / "skills" / "ticket" / "hooks" / "ticket-file-access-guard-hook.py"
    spec = importlib.util.spec_from_file_location("ticket_file_access_guard_rps", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_ticket_guard()

WIN_ROOT = "C:\\Users\\u\\proj"
TICKET_REL = "docs/work-logs/v3/v3.3/v3.3.0/tickets/a.md"


# ---------------------------------------------------------------------------
# 1. strip_root_prefix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, root, expected",
    [
        ("/a/proj/docs/x.md", "/a/proj", "docs/x.md"),
        ("/a/proj/docs/x.md", "/a/proj/", "docs/x.md"),
        ("/a/proj", "/a/proj", ""),
        ("/a/proj2/docs/x.md", "/a/proj", None),       # 目錄邊界
        ("/a/proj-wt/docs/x.md", "/a/proj", None),     # 目錄邊界（worktree 版面）
        ("/A/proj/docs/x.md", "/a/proj", None),        # POSIX 逐字比對
        ("c:\\Users\\u\\proj\\docs\\x.md", WIN_ROOT, "docs/x.md"),  # 代號折疊
        ("C:/Users/u/proj/docs/x.md", WIN_ROOT, "docs/x.md"),
        ("C:/Users/u/proj2/docs/x.md", WIN_ROOT, None),
        ("docs/x.md", "/a/proj", None),
        ("/a/proj/docs/x.md", "", None),
        ("/a/proj/docs/x.md", None, None),
    ],
)
def test_strip_root_prefix(path, root, expected):
    assert strip_root_prefix(path, root) == expected


# ---------------------------------------------------------------------------
# 2. path_permission
# ---------------------------------------------------------------------------


@pytest.fixture
def win_project_dir(monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", WIN_ROOT)


@pytest.mark.parametrize(
    "file_path",
    [
        "c:\\Users\\u\\proj\\docs\\a.md",
        "c:/Users/u/proj/.claude/rules/x.md",
    ],
)
def test_path_permission_drive_case_allows_exempt_dirs(win_project_dir, file_path):
    assert pp.check_file_permission(file_path, _LOG)[0] is True


@pytest.mark.parametrize(
    "file_path",
    [
        "c:\\Users\\u\\proj\\lib\\a.py",
        "c:/Users/u/proj/test/a_test.py",
    ],
)
def test_path_permission_drive_case_still_blocks_product_code(win_project_dir, file_path):
    # E2 正向對照：折疊代號後產品碼路徑仍拒絕
    assert pp.normalize_path(file_path).split("/")[0] in ("lib", "test")
    assert pp.check_file_permission(file_path, _LOG)[0] is False


def test_path_permission_sibling_prefix_not_stripped(monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/a/proj")
    assert pp.normalize_path("/a/proj-wt/docs/a.md") == "/a/proj-wt/docs/a.md"
    assert pp.normalize_path("/a/proj/docs/a.md") == "docs/a.md"


# ---------------------------------------------------------------------------
# 3. ticket-file-access-guard
# ---------------------------------------------------------------------------


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo_with_sibling_worktree(tmp_path):
    """tmp/llm-dev（主 checkout）、tmp/llm-dev-x（同 repo worktree）、
    tmp/llm-dev-y（不同 repo，同字首）。"""
    main = tmp_path / "llm-dev"
    main.mkdir()
    _git("init", "-q", cwd=main)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
         "--allow-empty", "-m", "init", cwd=main)
    _git("worktree", "add", "-q", str(tmp_path / "llm-dev-x"), cwd=main)
    other = tmp_path / "llm-dev-y"
    other.mkdir()
    _git("init", "-q", cwd=other)
    return tmp_path


def test_ticket_guard_drive_case_is_ticket(monkeypatch):
    monkeypatch.setattr(guard, "get_project_root", lambda: Path(WIN_ROOT))
    path = "c:\\Users\\u\\proj\\" + TICKET_REL.replace("/", "\\")
    assert guard.is_ticket_file(path) is True


def test_ticket_guard_sibling_worktree_is_ticket(monkeypatch, repo_with_sibling_worktree):
    base = repo_with_sibling_worktree
    monkeypatch.setattr(guard, "get_project_root", lambda: base / "llm-dev")
    assert guard.is_ticket_file(str(base / "llm-dev-x" / TICKET_REL)) is True


def test_ticket_guard_other_repo_same_prefix_not_ticket(monkeypatch, repo_with_sibling_worktree):
    # 對照：不同 repo 的同字首目錄不得被當成本專案的票
    base = repo_with_sibling_worktree
    monkeypatch.setattr(guard, "get_project_root", lambda: base / "llm-dev")
    assert guard.is_ticket_file(str(base / "llm-dev-y" / TICKET_REL)) is False


def test_ticket_guard_main_checkout_ticket_unchanged(monkeypatch, repo_with_sibling_worktree):
    base = repo_with_sibling_worktree
    monkeypatch.setattr(guard, "get_project_root", lambda: base / "llm-dev")
    assert guard.is_ticket_file(str(base / "llm-dev" / TICKET_REL)) is True
    assert guard.is_ticket_file(str(base / "llm-dev" / "docs" / "a.md")) is False


def test_strip_same_repo_checkout_prefix_outside_repo_is_none(tmp_path):
    assert strip_same_repo_checkout_prefix(str(tmp_path / "x" / "a.md"), str(tmp_path)) is None


def test_strip_same_repo_checkout_prefix_broken_gitlink_is_none(repo_with_sibling_worktree):
    # 相鄰 checkout 的 .git gitlink 損毀（common dir 無法解析）→ 不視為同 repo
    base = repo_with_sibling_worktree
    (base / "llm-dev-x" / ".git").write_text("not a gitlink\n", encoding="utf-8")
    path = str(base / "llm-dev-x" / TICKET_REL)
    assert strip_same_repo_checkout_prefix(path, str(base / "llm-dev")) is None


def test_strip_same_repo_checkout_prefix_invalid_path_is_none(tmp_path):
    assert strip_same_repo_checkout_prefix("/a/\0bad/x.md", str(tmp_path)) is None
