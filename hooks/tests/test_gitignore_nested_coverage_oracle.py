"""gitignore-check 的涵蓋判定與 git 錨定語意一致（以 git check-ignore 為 oracle）。

git 對中間含斜線的條目只比對該目錄：`.claude/hook-logs` 只忽略根層，
`.claude/hooks/hook-logs/` 照樣 untracked。檢查判定「已涵蓋」時，manifest 每個
名稱層級的 local-only 名稱在巢狀位置也必須真的被 git 忽略；根層錨定的
logs、state、worktrees 只要求根層。

Ticket：3.3.0-W1-107
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

CLAUDE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(CLAUDE_DIR))

from lib.sync_exclude_manifest import (  # noqa: E402
    LOCAL_ONLY_PATTERNS,
    LOCAL_ONLY_ROOT_DIRS,
    NESTED_LOCAL_ONLY_DIR_NAMES,
    required_gitignore_entry,
)

HOOK_PATH = CLAUDE_DIR / "hooks" / "session-start-gitignore-check-hook.py"


def _load_hook():
    spec = importlib.util.spec_from_file_location("gitignore_check_oracle", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _repo(tmp_path: Path, lines) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / ".gitignore").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return repo


def _ignored(repo: Path, rel: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "--no-index", "-q", rel],
    ).returncode == 0


def _nested_probe(name: str) -> str:
    base = f".claude/skills/demo/{name}"
    return f"{base}/x" if name in NESTED_LOCAL_ONLY_DIR_NAMES else base


@pytest.fixture(scope="module")
def hook():
    return _load_hook()


def test_judged_covered_implies_git_ignores_nested(tmp_path, hook):
    """以 hook 建議的條目組成 .gitignore：檢查判定無缺項，且每個名稱的巢狀樣本皆被忽略。"""
    lines = sorted(hook.REQUIRED_GITIGNORE_ENTRIES)
    assert hook.check_missing_entries(set(lines), MagicMock()) == []
    repo = _repo(tmp_path, lines)
    not_ignored = [n for n in sorted(LOCAL_ONLY_PATTERNS) if not _ignored(repo, _nested_probe(n))]
    assert not_ignored == []
    # 根層同樣被忽略（** 可為零層）
    root_not_ignored = [
        n for n in sorted(LOCAL_ONLY_PATTERNS)
        if not _ignored(repo, f".claude/{n}/x" if n in NESTED_LOCAL_ONLY_DIR_NAMES else f".claude/{n}")
    ]
    assert root_not_ignored == []


def test_root_form_hook_logs_reported_and_not_ignored(tmp_path, hook):
    """對照：hook-logs 只寫根層形式時，git 不忽略巢狀 hook-logs，檢查也回報缺項。"""
    lines = [e for e in hook.REQUIRED_GITIGNORE_ENTRIES if e != required_gitignore_entry("hook-logs")]
    lines.append(".claude/hook-logs")
    repo = _repo(tmp_path, lines)
    assert not _ignored(repo, ".claude/hooks/hook-logs/x.log")
    missing = hook.check_missing_entries(set(lines), MagicMock())
    assert missing == [".claude/**/hook-logs"]


@pytest.mark.parametrize("line", ["hook-logs/", "**/hook-logs", ".claude/**/hook-logs/"])
def test_nested_dir_forms_accepted(tmp_path, hook, line):
    """目錄名稱的裸名尾斜線、**/ 形式與 git 一致：判定涵蓋且巢狀確實被忽略。"""
    lines = [e for e in hook.REQUIRED_GITIGNORE_ENTRIES if e != required_gitignore_entry("hook-logs")]
    lines.append(line)
    repo = _repo(tmp_path, lines)
    assert _ignored(repo, ".claude/hooks/hook-logs/x.log")
    assert hook.check_missing_entries(set(lines), MagicMock()) == []


@pytest.mark.parametrize("wildcard", ["*.lock", ".claude/**/*.lock"])
def test_lock_wildcard_covers_nested_lock_names(tmp_path, hook, wildcard):
    """.lock 名稱由副檔名萬用字元涵蓋時，判定涵蓋且巢狀確實被忽略。"""
    lock_entries = {
        required_gitignore_entry(n) for n in LOCAL_ONLY_PATTERNS if n.endswith(".lock")
    }
    lines = sorted(hook.REQUIRED_GITIGNORE_ENTRIES - lock_entries) + [wildcard]
    repo = _repo(tmp_path, lines)
    for name in sorted(n for n in LOCAL_ONLY_PATTERNS if n.endswith(".lock")):
        assert _ignored(repo, _nested_probe(name))
    assert hook.check_missing_entries(set(lines), MagicMock()) == []


@pytest.mark.parametrize("name", sorted(LOCAL_ONLY_ROOT_DIRS))
def test_root_dirs_only_require_root(tmp_path, hook, name):
    """根層錨定的名稱只要求根層：根層形式判定涵蓋，巢狀同名目錄不被忽略也不回報。"""
    entry = required_gitignore_entry(name)
    assert entry == f".claude/{name}"
    lines = sorted(hook.REQUIRED_GITIGNORE_ENTRIES)
    repo = _repo(tmp_path, lines)
    assert _ignored(repo, f".claude/{name}/x")
    assert not _ignored(repo, f".claude/skills/demo/{name}/x")
    assert hook.check_missing_entries(set(lines), MagicMock()) == []
