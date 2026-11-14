"""不同步但可入版控的四項：sync 排除不變，gitignore 必要清單不再要求。

plans、analyses、migration-backups（根層錨定）與 .version-release.yaml 只需要
「不跨專案同步」；防外洩由 should_exclude 完成，與 .gitignore 無關。它們若列入
gitignore 必要清單，consumer 的計畫、分析與發版設定就無法入版控。

正向對照：其餘 local-only 項（logs、state、settings.local.json 等）仍被要求。

Ticket：3.3.0-W1-144.1
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

CLAUDE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(CLAUDE_DIR))

from lib.sync_exclude_manifest import (  # noqa: E402
    GITIGNORE_EXPECTED,
    LOCAL_ONLY_ROOT_DIRS,
    PER_PROJECT_PATTERNS,
    PER_PROJECT_ROOT_DIRS,
    required_gitignore_entry,
    should_exclude,
)

HOOKS_DIR = CLAUDE_DIR / "hooks"

TRACKED_ROOT_DIRS = {"plans", "analyses", "migration-backups"}
TRACKED_NAME = ".version-release.yaml"
TRACKED_ITEMS = TRACKED_ROOT_DIRS | {TRACKED_NAME}

# 正向對照：仍須進 .gitignore 的 local-only 項
STILL_REQUIRED = {"logs", "state", "worktrees", "settings.local.json", "hook-logs"}


def _load(name: str):
    path = HOOKS_DIR / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_")[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_items_classified_as_per_project():
    assert TRACKED_ROOT_DIRS <= PER_PROJECT_ROOT_DIRS
    assert TRACKED_NAME in PER_PROJECT_PATTERNS
    assert not (TRACKED_ROOT_DIRS & LOCAL_ONLY_ROOT_DIRS)


@pytest.mark.parametrize("rel", [
    "plans/p.md",
    "analyses/a.md",
    "migration-backups/20261112/t.md",
    "plans",
    ".version-release.yaml",
])
def test_sync_exclusion_unchanged(rel):
    assert should_exclude(Path(rel))


@pytest.mark.parametrize("rel", [
    "skills/foo/plans/x.md",
    "skills/foo/analyses/x.md",
    "references/migration-backups-guide.md",
])
def test_root_anchored_not_nested(rel):
    assert not should_exclude(Path(rel))


def test_not_in_gitignore_expected():
    assert not (TRACKED_ITEMS & GITIGNORE_EXPECTED)


def test_local_only_still_expected_positive_control():
    assert STILL_REQUIRED <= GITIGNORE_EXPECTED


def test_gitignore_check_no_longer_requires_items():
    hook = _load("session-start-gitignore-check-hook.py")
    for item in TRACKED_ITEMS:
        assert f".claude/{item}" not in hook.REQUIRED_GITIGNORE_ENTRIES
    for item in STILL_REQUIRED:
        assert required_gitignore_entry(item) in hook.REQUIRED_GITIGNORE_ENTRIES


def test_gitignore_check_missing_list(tmp_path):
    """.gitignore 含其餘必要項、不含四項時，缺失清單為空；拿掉 logs 則只報 logs。"""
    hook = _load("session-start-gitignore-check-hook.py")
    complete = set(hook.REQUIRED_GITIGNORE_ENTRIES)
    assert hook.check_missing_entries(complete, MagicMock()) == []

    without_logs = complete - {".claude/logs"}
    assert hook.check_missing_entries(without_logs, MagicMock()) == [".claude/logs"]


def test_sync_exclusion_check_drift(tmp_path):
    """sync-exclusion-check 的 .gitignore 交叉驗證同樣不要求四項。"""
    hook = _load("session-start-sync-exclusion-check-hook.py")
    gi = tmp_path / ".gitignore"
    lines = [required_gitignore_entry(n) for n in sorted(GITIGNORE_EXPECTED)]
    gi.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert hook.find_gitignore_drift(gi) == []

    gi.write_text("\n".join(l for l in lines if l != ".claude/state") + "\n", encoding="utf-8")
    assert hook.find_gitignore_drift(gi) == ["state"]
