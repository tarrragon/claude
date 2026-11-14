"""pre-test-hook：以 run-with-timeout 包裝 worktree merge 時 deny。

merge 自行取得名額，外層計時器會把閘門內部排隊算進逾時；包裝沒有防護價值，
排得久就被外層中止。正向對照：包裝的 merge 被擋；反向對照：不包裝的 merge、
包裝的其他 heavy 命令放行。
"""

import importlib.util
import sys
from pathlib import Path

import pytest

hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))
sys.path.insert(0, str(hook_dir.parent))

spec = importlib.util.spec_from_file_location("pre_test_hook_wrapped_merge", hook_dir / "pre-test-hook.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

from lib.test_command_parse import find_wrapped_self_slotted  # noqa: E402

WRAPPER = "python3 .claude/scripts/run-with-timeout.py 2400 -- "

WRAPPED_MERGE = [
    WRAPPER + "worktree merge 3.1.0-W1-001 --pre-acceptance x",
    WRAPPER + "/Users/u/.local/bin/worktree merge --branch batch/L1",
    WRAPPER + "uv --directory .claude/skills/worktree run worktree merge 3.1.0-W1-001",
    "cd /tmp && " + WRAPPER + "worktree merge 3.1.0-W1-001 > merge.log 2>&1",
]

PASS_THROUGH = [
    "worktree merge 3.1.0-W1-001 --pre-acceptance x",
    "worktree merge --branch batch/L1 > merge.log 2>&1",
    WRAPPER + "uv run pytest .claude/hooks/tests",
    WRAPPER + "worktree status",
]


@pytest.mark.parametrize("command", WRAPPED_MERGE)
def test_wrapped_worktree_merge_is_denied_with_unwrapped_rewrite(command):
    reason = hook.build_block_reason("Bash", {"command": command})
    assert reason is not None
    assert "run-with-timeout 包裝的 worktree merge" in reason
    assert "run-with-timeout.py 2400" not in reason.split("\n", 1)[1], "改寫不得保留包裝"
    assert "worktree merge" in reason.split("\n", 1)[1]


@pytest.mark.parametrize("command", PASS_THROUGH)
def test_unwrapped_merge_and_wrapped_other_heavy_pass(command):
    assert hook.build_block_reason("Bash", {"command": command}) is None


def test_same_merge_flips_between_wrapped_and_unwrapped():
    """E2 正反對照：同一 merge 包裝 deny、去掉包裝放行。"""
    bare = "worktree merge 3.1.0-W1-001"
    assert hook.build_block_reason("Bash", {"command": bare}) is None
    assert hook.build_block_reason("Bash", {"command": WRAPPER + bare}) is not None


def test_rewrite_keeps_redirects_outside():
    found = find_wrapped_self_slotted(WRAPPER + "worktree merge 3.1.0-W1-001 > merge.log 2>&1")
    assert found == [(("worktree", "merge", "3.1.0-W1-001"), "> merge.log 2>&1")]


def test_unparseable_command_returns_none():
    assert find_wrapped_self_slotted("echo 'unterminated") is None
