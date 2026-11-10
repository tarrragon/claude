"""
Test: 主線程允許編輯 .claude/VERSION 與 .claude/project-integration/（3.0.1-W1-004）

來源：roadmap §5 第 3 步由主線程更新 VERSION；framework-update-adaptation
Step 5 由主線程寫 project-integration/ 下的 last-adapted.md。
"""

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(HOOKS_DIR.parent))


class _SilentLogger:
    def debug(self, *args, **kwargs):
        pass

    info = warning = error = debug


def _allowed(path):
    from lib.path_permission import check_file_permission

    return check_file_permission(path, _SilentLogger())[0]


def test_version_file_allowed():
    assert _allowed(".claude/VERSION")


def test_other_root_non_md_still_blocked():
    assert not _allowed(".claude/foo.txt")
    assert not _allowed(".claude/VERSION.bak")


def test_project_integration_allowed():
    assert _allowed(
        ".claude/project-integration/framework-update-adaptation/last-adapted.md"
    )


def test_project_integration_listed_in_deny_message():
    from lib.path_permission import get_allowed_claude_subdirectory_lines

    lines = get_allowed_claude_subdirectory_lines()
    assert any(".claude/project-integration/" in line for line in lines)
