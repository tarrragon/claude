"""
Unit tests for worktree-merge-reminder-hook.

Source: 0.18.0-W11-033 (PC-149 follow-up)
TDD Phase: 2 (RED) — A 組為 regression、B 組為新增 PostToolUse cleanup acceptance

A 組（既有功能，應 pass）：
- is_ticket_complete_command 命令偵測
- subagent 環境跳過
- 未合併 commit 警告

B 組（新增 PostToolUse cleanup，RED 階段應 fail）：
- ahead=0 worktree → cleanup reminder（核心 acceptance）
- ahead=0 worktree dirty → cleanup reminder + dirty 提示
- 混合 worktree（已合併 + 未合併）→ 雙重提示
- 全部已清（無 worktree）→ 不警告
- 已合併且 clean → 推送 cleanup reminder（不應觸發 dirty 字眼）
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


HOOK_PATH = Path(__file__).resolve().parents[2] / "skills" / "worktree" / "hooks" / "worktree-merge-reminder-hook.py"


@pytest.fixture(scope="module")
def hook_module():
    sys.path.insert(0, str(HOOK_PATH.parent))
    spec = importlib.util.spec_from_file_location(
        "worktree_merge_reminder_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------- helpers ----------

def _make_porcelain(*worktrees):
    """組裝 git worktree list --porcelain 輸出。

    Args:
        *worktrees: (path, branch) tuples; branch=None 表示 detached
    """
    lines = []
    for path, branch in worktrees:
        lines.append(f"worktree {path}")
        lines.append("HEAD abc123def456")
        if branch:
            lines.append(f"branch refs/heads/{branch}")
        else:
            lines.append("detached")
        lines.append("")
    return "\n".join(lines)


def _mk_subprocess_side_effect(
    *,
    worktree_porcelain: str = "",
    unmerged_per_branch: dict | None = None,
    dirty_per_path: dict | None = None,
):
    """建立 subprocess.run side_effect，依命令類型分派回傳。

    Args:
        worktree_porcelain: git worktree list --porcelain 輸出
        unmerged_per_branch: {branch: [commit lines]}，缺則回 ahead=0
        dirty_per_path: {worktree_path: status_porcelain}，缺則回 clean
    """
    unmerged_per_branch = unmerged_per_branch or {}
    dirty_per_path = dirty_per_path or {}

    def side_effect(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""

        # ["git", "worktree", "list", "--porcelain"]
        if len(cmd) >= 3 and cmd[0] == "git" and cmd[1] == "worktree" and cmd[2] == "list":
            result.stdout = worktree_porcelain
            return result

        # ["git", "log", "main..<branch>", "--oneline"]
        if len(cmd) >= 3 and cmd[0] == "git" and cmd[1] == "log":
            spec = cmd[2]
            if ".." in spec:
                branch = spec.split("..", 1)[1]
                commits = unmerged_per_branch.get(branch, [])
                result.stdout = "\n".join(commits)
            return result

        # ["git", "-C", <path>, "status", "--porcelain"] 或變體
        if cmd[0] == "git" and "status" in cmd:
            path = None
            if "-C" in cmd:
                idx = cmd.index("-C")
                path = cmd[idx + 1]
            result.stdout = dirty_per_path.get(path, "")
            return result

        return result

    return side_effect


def _run_main(hook_module, input_data, side_effect):
    """通用 main() 執行包裝。"""
    with patch.object(hook_module, "read_json_from_stdin", return_value=input_data), \
         patch.object(hook_module, "is_subagent_environment", return_value=False), \
         patch("subprocess.run", side_effect=side_effect):
        return hook_module.main()


def _extract_message(captured_out: str) -> str:
    """從 hook stdout JSON 取出 additionalContext 文字。"""
    payload = json.loads(captured_out)
    return payload["hookSpecificOutput"]["additionalContext"]


# ============================================================
# A 組 Regression — 既有命令偵測（純函式）
# ============================================================

def test_is_ticket_complete_command_positive(hook_module):
    """偵測 ticket track complete 命令"""
    assert hook_module.is_ticket_complete_command(
        {"tool_input": {"command": "ticket track complete 0.18.0-W1-001"}}
    ) is True


def test_is_ticket_complete_command_negative_git(hook_module):
    """git status 不觸發"""
    assert hook_module.is_ticket_complete_command(
        {"tool_input": {"command": "git status"}}
    ) is False


def test_is_ticket_complete_command_negative_claim(hook_module):
    """ticket track claim 不觸發"""
    assert hook_module.is_ticket_complete_command(
        {"tool_input": {"command": "ticket track claim 0.18.0-W1-001"}}
    ) is False


def test_is_ticket_complete_command_negative_release(hook_module):
    """ticket track release 不觸發"""
    assert hook_module.is_ticket_complete_command(
        {"tool_input": {"command": "ticket track release 0.18.0-W1-001"}}
    ) is False


# ============================================================
# A 組 Regression — main 流程基本守則
# ============================================================

def test_main_skip_when_not_complete_command(hook_module, capsys):
    """非 ticket complete 命令 → 不觸發任何輸出"""
    side_effect = _mk_subprocess_side_effect()
    rc = _run_main(hook_module, {"tool_input": {"command": "ls -la"}}, side_effect)
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() == ""


def test_main_skip_when_subagent(hook_module, capsys):
    """subagent 環境 → 不觸發"""
    input_data = {"tool_input": {"command": "ticket track complete X"}}
    side_effect = _mk_subprocess_side_effect()
    with patch.object(hook_module, "read_json_from_stdin", return_value=input_data), \
         patch.object(hook_module, "is_subagent_environment", return_value=True), \
         patch("subprocess.run", side_effect=side_effect):
        rc = hook_module.main()
    assert rc == 0
    assert capsys.readouterr().out.strip() == ""


def test_main_unmerged_worktree_warns(hook_module, capsys):
    """既有功能：未合併 commit → 推送 unmerged 警告（regression）"""
    input_data = {"tool_input": {"command": "ticket track complete 0.18.0-W1-001"}}
    porcelain = _make_porcelain(("/tmp/wt-A", "feat/W1-001"))
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={"feat/W1-001": ["abc111 first commit", "def222 second commit"]},
    )
    rc = _run_main(hook_module, input_data, side_effect)
    out = capsys.readouterr().out
    assert rc == 0
    assert out, "expected hook output for unmerged worktree"
    message = _extract_message(out)
    # 訊息應提及待合併 commit
    assert "未合併" in message or "待合併" in message or "unmerged" in message.lower()
    # 應提供 git merge 建議或顯示分支
    assert "feat/W1-001" in message


def test_main_no_worktree_no_message(hook_module, capsys):
    """無 worktree → 不警告"""
    input_data = {"tool_input": {"command": "ticket track complete 0.18.0-W1-001"}}
    side_effect = _mk_subprocess_side_effect(worktree_porcelain="")
    rc = _run_main(hook_module, input_data, side_effect)
    assert rc == 0
    assert capsys.readouterr().out.strip() == ""


# ============================================================
# B 組 RED — PostToolUse cleanup reminder（新增 acceptance）
# ============================================================

def test_main_merged_worktree_post_complete_reminder(hook_module, capsys):
    """RED: ahead=0 worktree → 推送 cleanup reminder（核心 acceptance 1）"""
    input_data = {"tool_input": {"command": "ticket track complete 0.18.0-W1-001"}}
    porcelain = _make_porcelain(("/tmp/wt-merged", "feat/W1-001"))
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={},  # ahead=0
        dirty_per_path={"/tmp/wt-merged": ""},  # clean
    )
    rc = _run_main(hook_module, input_data, side_effect)
    out = capsys.readouterr().out
    assert rc == 0
    assert out, "expected hook to emit cleanup reminder for merged worktree (PC-149)"
    message = _extract_message(out)
    # 必須包含 cleanup 命令建議
    assert "git worktree remove" in message, \
        f"expected 'git worktree remove' suggestion in message:\n{message}"
    # 必須指出哪個 worktree 需要清理
    assert "/tmp/wt-merged" in message or "feat/W1-001" in message
    # 不應誤判為 dirty
    assert "dirty" not in message.lower()


def test_main_merged_worktree_dirty_warns_dirty_first(hook_module, capsys):
    """RED: ahead=0 worktree 但 dirty → cleanup reminder 並提示先處理變更"""
    input_data = {"tool_input": {"command": "ticket track complete 0.18.0-W1-001"}}
    porcelain = _make_porcelain(("/tmp/wt-dirty", "feat/W1-001"))
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={},  # ahead=0
        dirty_per_path={"/tmp/wt-dirty": "?? node_modules/\n M package-lock.json\n"},
    )
    rc = _run_main(hook_module, input_data, side_effect)
    out = capsys.readouterr().out
    assert rc == 0
    assert out, "expected reminder for merged-dirty worktree"
    message = _extract_message(out)
    assert "git worktree remove" in message
    # dirty 必須有顯性提示（dirty 字眼 / 未提交 / 未追蹤之一）
    assert any(kw in message for kw in ("dirty", "未提交", "未追蹤", "未清理")), \
        f"expected dirty hint in message:\n{message}"


def test_main_merged_worktree_path_missing_skipped(hook_module, capsys):
    """RED: worktree 路徑已不存在 → 跳過該項，不報錯"""
    input_data = {"tool_input": {"command": "ticket track complete 0.18.0-W1-001"}}
    # /tmp/wt-ghost 不存在於檔案系統
    porcelain = _make_porcelain(
        ("/tmp/wt-ghost-does-not-exist-xyz", "feat/W1-001"),
        ("/tmp/wt-real", "feat/W1-002"),
    )
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={},  # 兩個都 ahead=0
        dirty_per_path={"/tmp/wt-real": ""},
    )
    rc = _run_main(hook_module, input_data, side_effect)
    out = capsys.readouterr().out
    assert rc == 0
    # 至少 /tmp/wt-real 應出現在 cleanup 建議
    if out:
        message = _extract_message(out)
        assert "/tmp/wt-real" in message or "feat/W1-002" in message


def test_main_mixed_merged_and_unmerged_worktrees(hook_module, capsys):
    """RED: 混合 1 未合併 + 1 已合併 → 兩種訊息都出現"""
    input_data = {"tool_input": {"command": "ticket track complete 0.18.0-W1-001"}}
    porcelain = _make_porcelain(
        ("/tmp/wt-unmerged", "feat/W1-001"),
        ("/tmp/wt-merged", "feat/W1-002"),
    )
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={"feat/W1-001": ["abc111 unmerged commit"]},
        dirty_per_path={"/tmp/wt-merged": ""},
    )
    rc = _run_main(hook_module, input_data, side_effect)
    out = capsys.readouterr().out
    assert rc == 0
    assert out, "expected combined output for mixed worktree states"
    message = _extract_message(out)
    # 未合併分支應出現
    assert "feat/W1-001" in message or "/tmp/wt-unmerged" in message
    # 已合併且 cleanup 建議應出現
    assert "git worktree remove" in message
    assert "feat/W1-002" in message or "/tmp/wt-merged" in message


def test_main_merged_clean_excludes_main_branch(hook_module, capsys):
    """RED: 主 repo（branch=main）即使 ahead=0 也不列入 cleanup 候選"""
    input_data = {"tool_input": {"command": "ticket track complete 0.18.0-W1-001"}}
    porcelain = _make_porcelain(
        ("/tmp/main-repo", "main"),
        ("/tmp/wt-merged", "feat/W1-001"),
    )
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={},
        dirty_per_path={"/tmp/wt-merged": ""},
    )
    rc = _run_main(hook_module, input_data, side_effect)
    out = capsys.readouterr().out
    assert rc == 0
    if out:
        message = _extract_message(out)
        # main 不應出現在 cleanup 訊息
        assert "/tmp/main-repo" not in message
        # 但 feat/W1-001 應出現
        assert "git worktree remove" in message
        assert "feat/W1-001" in message or "/tmp/wt-merged" in message
