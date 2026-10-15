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
    for entry in worktrees:
        path, branch = entry[0], entry[1]
        locked = len(entry) > 2 and entry[2] == "locked"
        lines.append(f"worktree {path}")
        lines.append("HEAD abc123def456")
        if branch:
            lines.append(f"branch refs/heads/{branch}")
        else:
            lines.append("detached")
        if locked:
            lines.append("locked")
        lines.append("")
    return "\n".join(lines)


def _mk_subprocess_side_effect(
    *,
    worktree_porcelain: str = "",
    unmerged_per_branch: dict | None = None,
    dirty_per_path: dict | None = None,
    zero_commit_branches: tuple = (),
    rev_parse_fails: bool = False,
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
        # 0.2.1-W3-286：collections 改用 lib.git_utils.run_git_command，該函式
        # 於命令前多插入 "--no-optional-locks" flag（`git --no-optional-locks
        # worktree list ...`），原本按固定 index（cmd[1]/cmd[2]）比對的
        # dispatch 會因偏移而失配；改用「token 是否存在於 cmd」判斷，並用
        # kwargs["cwd"]（git_utils 以 cwd kwarg 而非 `-C` flag 指定路徑）
        # 取代原本掃 `-C` 位置的路徑取得方式。
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""

        if "worktree" in cmd and "list" in cmd:
            result.stdout = worktree_porcelain
            return result

        if "rev-parse" in cmd:
            if rev_parse_fails:
                result.returncode = 128
                return result
            result.stdout = f"tip-{cmd[-1]}\n"
            return result

        if "rev-list" in cmd:
            # main 的 first-parent 歷史；零提交分支的 tip 落在其上
            tips = [f"tip-{b}" for b in zero_commit_branches]
            result.stdout = "\n".join(["maintip"] + tips)
            return result

        if "log" in cmd:
            spec = next((tok for tok in cmd if ".." in tok), None)
            if spec:
                branch = spec.split("..", 1)[1]
                commits = unmerged_per_branch.get(branch, [])
                result.stdout = "\n".join(commits)
            return result

        if "status" in cmd:
            path = kwargs.get("cwd")
            if path is None and "-C" in cmd:
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


# ============================================================
# 0.5.0-W1-270.8：完成命令辨識（finish 別名）
# ============================================================

def test_finish_triggers_unmerged_warning(hook_module, capsys):
    """E2：finish 觸發原本對 complete 的處理（未合併警告含分支與 commit 數）"""
    input_data = {"tool_input": {"command": "ticket track finish 0.18.0-W1-001"}}
    porcelain = _make_porcelain(("/tmp/wt-A", "feat/W1-001"))
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={"feat/W1-001": ["abc111 first commit"]},
    )
    rc = _run_main(hook_module, input_data, side_effect)
    lines = _extract_message(capsys.readouterr().out).splitlines()
    assert rc == 0
    assert "  分支: feat/W1-001" in lines
    assert "  待合併 commit: 1 個" in lines


def test_batch_complete_recognized(hook_module):
    assert hook_module.is_ticket_complete_command(
        {"tool_input": {"command": "ticket track batch-complete A B"}}
    ) is True


def test_quoted_literal_not_recognized(hook_module):
    assert hook_module.is_ticket_complete_command(
        {"tool_input": {"command": "echo 'ticket track complete X'"}}
    ) is False


def _classify(hook_module, porcelain, **kwargs):
    side_effect = _mk_subprocess_side_effect(worktree_porcelain=porcelain, **kwargs)
    logger = MagicMock()
    with patch("subprocess.run", side_effect=side_effect):
        worktrees = hook_module.parse_worktree_list(logger)
        return hook_module.classify_worktrees(worktrees, logger)


def _branches(entries):
    return [e[1] for e in entries]


def test_classify_locked_worktree_not_in_merged(hook_module):
    """正向對照：locked（進行中派發）舊實作列入 merged，新實作歸 in_progress"""
    porcelain = _make_porcelain(("/tmp/wt-run", "agent-run", "locked"))
    unmerged, merged, in_progress = _classify(hook_module, porcelain)
    assert "agent-run" not in _branches(merged)
    assert _branches(in_progress) == ["agent-run"]


def test_classify_zero_commit_worktree_not_in_merged(hook_module):
    """正向對照：零提交（tip 在 main first-parent 上）未 locked 也歸 in_progress"""
    porcelain = _make_porcelain(("/tmp/wt-zero", "agent-zero"))
    unmerged, merged, in_progress = _classify(
        hook_module, porcelain, zero_commit_branches=("agent-zero",)
    )
    assert "agent-zero" not in _branches(merged)
    assert _branches(in_progress) == ["agent-zero"]


def test_classify_finished_merged_worktree_still_in_merged(hook_module):
    """liveness：未 locked、tip 不在 first-parent（merge commit 親代）→ 仍列 merged"""
    porcelain = _make_porcelain(("/tmp/wt-done", "agent-done"))
    unmerged, merged, in_progress = _classify(hook_module, porcelain)
    assert _branches(merged) == ["agent-done"]
    assert in_progress == []


def test_classify_unknown_tip_fail_open_not_in_merged(hook_module):
    """失敗語意：rev-parse 失敗 → 不列入建議清理（歸 in_progress）"""
    porcelain = _make_porcelain(("/tmp/wt-x", "agent-x"))
    unmerged, merged, in_progress = _classify(
        hook_module, porcelain, rev_parse_fails=True
    )
    assert merged == []
    assert _branches(in_progress) == ["agent-x"]


def test_classify_locked_read_failure_not_in_merged(hook_module):
    """失敗語意：locked 狀態讀取失敗 → 全部歸 in_progress"""
    logger = MagicMock()
    failed = MagicMock(returncode=1, stdout="", stderr="")
    with patch("subprocess.run", return_value=failed):
        unmerged, merged, in_progress = hook_module.classify_worktrees(
            [("/tmp/wt-y", "agent-y")], logger
        )
    assert merged == []
    assert _branches(in_progress) == ["agent-y"]


def test_main_locked_worktree_not_suggested_for_removal(hook_module, capsys):
    """main 層：locked worktree 不帶 git worktree remove 建議"""
    input_data = {"tool_input": {"command": "ticket track complete X"}}
    porcelain = _make_porcelain(("/tmp/wt-run", "agent-run", "locked"))
    rc = _run_main(
        hook_module, input_data,
        _mk_subprocess_side_effect(worktree_porcelain=porcelain),
    )
    message = _extract_message(capsys.readouterr().out)
    assert rc == 0
    assert "git worktree remove" not in message
    assert "不建議清理" in message


def test_unparseable_command_fail_open(hook_module):
    """未閉合引號 → 不觸發（提示類不阻擋）"""
    assert hook_module.is_ticket_complete_command(
        {"tool_input": {"command": "echo 'ticket track finish X"}}
    ) is False
