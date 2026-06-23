"""
Test: branch-verify-hook 跨專案豁免 + deny 訊息（Ticket: 0.18.0-W17-149）

驗證項目：
1. find_target_repo: 從檔案路徑往上找最近的 .git 目錄
2. is_exempt_path_on_protected_branch（same repo）：本專案豁免清單仍生效
3. is_exempt_path_on_protected_branch（cross repo）：退化為通用清單
   - README.md / CHANGELOG.md / .gitignore / .gitattributes 放行
   - .claude/、docs/ 等本專案約定不放行
4. build_cross_repo_deny_message: 含目標 repo 路徑、目標 branch、cd + git checkout 指令

Source: ANA 0.18.0-W17-147 → IMP 0.18.0-W17-149
"""

import sys
import importlib.util
import tempfile
import subprocess
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))

_spec = importlib.util.spec_from_file_location(
    "branch_verify_hook",
    HOOKS_DIR / "branch-verify-hook.py",
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

find_target_repo = _module.find_target_repo
is_exempt_path_on_protected_branch = _module.is_exempt_path_on_protected_branch
build_cross_repo_deny_message = _module.build_cross_repo_deny_message
GENERIC_EXEMPT_EXACT = _module.GENERIC_EXEMPT_EXACT


# ---------- find_target_repo ----------

def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def test_find_target_repo_returns_repo_root_for_nested_file():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        _init_git_repo(repo)
        sub = repo / "sub" / "deep"
        sub.mkdir(parents=True)
        target_file = sub / "file.md"
        target_file.write_text("hi")
        assert find_target_repo(str(target_file)) == str(repo.resolve()) or \
            Path(find_target_repo(str(target_file))).resolve() == repo.resolve()


def test_find_target_repo_returns_none_for_empty_path():
    # W17-150: 改用 git_utils.find_target_repo 後，相對路徑會被 Path.resolve() 解析為絕對路徑，
    # 故不再保證相對路徑回傳 None。實際 hook 呼叫端仍以 file_path.startswith("/") 守門，
    # 行為對 hook 場景一致。本測試僅保留空字串案例。
    assert find_target_repo("") is None


def test_find_target_repo_returns_none_when_no_git_ancestor():
    with tempfile.TemporaryDirectory() as tmp:
        # 不 init git
        f = Path(tmp) / "file.md"
        f.write_text("x")
        # 上層可能恰好有 .git（如 /Users/.../.git），所以結果可能非 None；
        # 但應不等於 tmp 自身
        result = find_target_repo(str(f))
        # 至少確認不是 tmp（無 .git）
        assert result != str(Path(tmp).resolve()) or result is None


# ---------- is_exempt_path_on_protected_branch: same repo ----------

def test_same_repo_claude_dir_exempt(tmp_path):
    repo = tmp_path / "host"
    repo.mkdir()
    _init_git_repo(repo)
    file_path = str(repo / ".claude" / "rules" / "x.md")
    # same repo: target_repo == host
    assert is_exempt_path_on_protected_branch(
        file_path, cwd=str(repo), target_repo=str(repo)
    )


def test_same_repo_docs_dir_exempt(tmp_path):
    repo = tmp_path / "host"
    repo.mkdir()
    _init_git_repo(repo)
    file_path = str(repo / "docs" / "ticket.md")
    assert is_exempt_path_on_protected_branch(
        file_path, cwd=str(repo), target_repo=str(repo)
    )


def test_same_repo_random_file_not_exempt(tmp_path):
    repo = tmp_path / "host"
    repo.mkdir()
    _init_git_repo(repo)
    file_path = str(repo / "src" / "main.py")
    assert not is_exempt_path_on_protected_branch(
        file_path, cwd=str(repo), target_repo=str(repo)
    )


# ---------- is_exempt_path_on_protected_branch: cross repo ----------

def test_cross_repo_readme_exempt(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    _init_git_repo(host)
    target = tmp_path / "external"
    target.mkdir()
    _init_git_repo(target)
    file_path = str(target / "README.md")
    assert is_exempt_path_on_protected_branch(
        file_path, cwd=str(host), target_repo=str(target)
    )


def test_cross_repo_changelog_exempt(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    _init_git_repo(host)
    target = tmp_path / "external"
    target.mkdir()
    _init_git_repo(target)
    for name in ["CHANGELOG.md", ".gitignore", ".gitattributes"]:
        f = target / name
        assert is_exempt_path_on_protected_branch(
            str(f), cwd=str(host), target_repo=str(target)
        ), f"{name} 應在跨專案通用豁免清單"


def test_cross_repo_claude_dir_NOT_exempt(tmp_path):
    """關鍵迴歸測試：跨專案的 .claude/ 不再用本專案約定豁免。"""
    host = tmp_path / "host"
    host.mkdir()
    _init_git_repo(host)
    target = tmp_path / "external"
    target.mkdir()
    _init_git_repo(target)
    file_path = str(target / ".claude" / "skills" / "x.md")
    assert not is_exempt_path_on_protected_branch(
        file_path, cwd=str(host), target_repo=str(target)
    )


def test_cross_repo_docs_dir_NOT_exempt(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    _init_git_repo(host)
    target = tmp_path / "external"
    target.mkdir()
    _init_git_repo(target)
    file_path = str(target / "docs" / "spec.md")
    assert not is_exempt_path_on_protected_branch(
        file_path, cwd=str(host), target_repo=str(target)
    )


def test_cross_repo_arbitrary_file_NOT_exempt(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    _init_git_repo(host)
    target = tmp_path / "external"
    target.mkdir()
    _init_git_repo(target)
    file_path = str(target / "content" / "post.md")
    assert not is_exempt_path_on_protected_branch(
        file_path, cwd=str(host), target_repo=str(target)
    )


# ---------- build_cross_repo_deny_message ----------

def test_deny_message_contains_target_repo_path():
    msg = build_cross_repo_deny_message(
        file_path="/Users/x/project/blog/content/skills/x.md",
        target_repo="/Users/x/project/blog",
        target_branch="main",
    )
    assert "/Users/x/project/blog" in msg


def test_deny_message_contains_target_branch():
    msg = build_cross_repo_deny_message(
        file_path="/repo/file.md",
        target_repo="/repo",
        target_branch="main",
    )
    assert "main" in msg


def test_deny_message_contains_cd_and_checkout_command():
    msg = build_cross_repo_deny_message(
        file_path="/repo/file.md",
        target_repo="/repo",
        target_branch="main",
    )
    assert "cd /repo" in msg
    assert "git checkout -b" in msg


def test_deny_message_uses_custom_suggested_branch():
    msg = build_cross_repo_deny_message(
        file_path="/repo/file.md",
        target_repo="/repo",
        target_branch="main",
        suggested_branch="feat/blog-update",
    )
    assert "feat/blog-update" in msg


# ---------- GENERIC_EXEMPT_EXACT 完整性 ----------

def test_generic_exempt_list_minimal_set():
    """跨專案豁免清單應僅含通用文件，不含本專案約定。"""
    assert "README.md" in GENERIC_EXEMPT_EXACT
    assert "CHANGELOG.md" in GENERIC_EXEMPT_EXACT
    assert ".gitignore" in GENERIC_EXEMPT_EXACT
    assert ".gitattributes" in GENERIC_EXEMPT_EXACT
    # 反向斷言：不可含本專案約定前綴
    assert ".claude/" not in GENERIC_EXEMPT_EXACT
    assert "docs/" not in GENERIC_EXEMPT_EXACT
    assert "CLAUDE.md" not in GENERIC_EXEMPT_EXACT
