"""
Unit tests for session-start-merged-worktree-audit-hook.

Source: 0.18.0-W11-033 (PC-149 follow-up, 第二批 RED)
TDD Phase: 2 (RED) — Hook 檔案尚未建立，採 module-level skip 設計

Hook 職責（兩個 section 合併在同一 SessionStart hook）：
1. Merged worktree audit：列出 ahead=0 的 user worktree（排除主 repo 與 cc runtime worktree）
2. Metadata orphan audit：列出已 complete 但 ticket md 仍 modified 的孤兒

輸出格式：標準 SessionStart hook JSON
- 兩 section 皆空 → {"suppressOutput": True}
- 任一非空 → {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}
"""

import importlib.util
import json
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


HOOK_PATH = Path(__file__).resolve().parents[2] / "skills" / "worktree" / "hooks" / "session-start-merged-worktree-audit-hook.py"

# RED 階段守則：hook 檔案尚未建立時整 module skip
# Agent 實作後測試自動啟用（pass/fail 視實作是否符合 acceptance）
if not HOOK_PATH.exists():
    pytest.skip(
        f"RED phase (W11-033): hook not yet created at {HOOK_PATH.name}. "
        "Implementation pending — see ticket 0.18.0-W11-033 Solution.",
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def hook_module():
    sys.path.insert(0, str(HOOK_PATH.parent))
    spec = importlib.util.spec_from_file_location(
        "session_start_merged_worktree_audit_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------- helpers ----------

def _make_porcelain(*worktrees):
    """組裝 git worktree list --porcelain 輸出。"""
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
    status_porcelain: str = "",
):
    """建立 subprocess.run side_effect，依命令類型分派。

    Args:
        worktree_porcelain: git worktree list --porcelain 輸出
        unmerged_per_branch: {branch: [commit lines]}
        status_porcelain: git status --porcelain 輸出（含 M ticket md 等）
    """
    unmerged_per_branch = unmerged_per_branch or {}

    def side_effect(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""

        if len(cmd) >= 3 and cmd[0] == "git" and cmd[1] == "worktree" and cmd[2] == "list":
            result.stdout = worktree_porcelain
            return result

        if len(cmd) >= 3 and cmd[0] == "git" and cmd[1] == "log":
            spec = cmd[2]
            if ".." in spec:
                branch = spec.split("..", 1)[1]
                commits = unmerged_per_branch.get(branch, [])
                result.stdout = "\n".join(commits)
            return result

        if cmd[0] == "git" and "status" in cmd:
            result.stdout = status_porcelain
            return result

        return result

    return side_effect


def _write_ticket(root: Path, ticket_id: str, *, status: str = "completed"):
    """在 tmp 專案根建立 ticket md（最小 frontmatter）。"""
    # 對應 docs/work-logs/v*/v*/v*/tickets/<id>.md
    version_parts = ticket_id.split("-")[0].split(".")  # 0.18.0 → ["0", "18", "0"]
    if len(version_parts) >= 3:
        major, minor, patch = version_parts[0], version_parts[1], version_parts[2]
        ticket_dir = root / "docs" / "work-logs" / f"v{major}" / f"v{major}.{minor}" / f"v{major}.{minor}.{patch}" / "tickets"
    else:
        ticket_dir = root / "docs" / "work-logs" / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    md = ticket_dir / f"{ticket_id}.md"
    md.write_text(textwrap.dedent(f"""\
        ---
        id: {ticket_id}
        title: stub
        type: IMP
        status: {status}
        version: {ticket_id.split('-')[0]}
        ---

        # body
        """))
    return md


def _run_main_with_mocks(hook_module, *, side_effect, project_root, monkeypatch):
    """通用 main() 執行包裝，含 stdin / env / subprocess mock。"""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project_root))
    with patch.object(hook_module, "read_json_from_stdin", return_value={}), \
         patch("subprocess.run", side_effect=side_effect):
        return hook_module.main()


def _extract_message(captured_out: str) -> str | None:
    """從 hook stdout JSON 取出 additionalContext，suppressOutput 則回 None。"""
    payload = json.loads(captured_out)
    if payload.get("suppressOutput"):
        return None
    return payload.get("hookSpecificOutput", {}).get("additionalContext")


# ============================================================
# A 組 — 基礎行為（空 / 無相關狀態）
# ============================================================

def test_main_no_worktree_no_orphan_suppress_output(hook_module, capsys, tmp_path, monkeypatch):
    """無 worktree 且無 orphan → suppressOutput=True"""
    side_effect = _mk_subprocess_side_effect()
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload.get("suppressOutput") is True


def test_main_only_main_repo_no_message(hook_module, capsys, tmp_path, monkeypatch):
    """只有主 repo（branch=main）→ 不警告"""
    porcelain = _make_porcelain(("/tmp/main-repo", "main"))
    side_effect = _mk_subprocess_side_effect(worktree_porcelain=porcelain)
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload.get("suppressOutput") is True


def test_main_unmerged_worktree_not_in_audit(hook_module, capsys, tmp_path, monkeypatch):
    """有未合併 commit 的 worktree → 不在本 hook 範圍（不警告）"""
    porcelain = _make_porcelain(("/tmp/wt-unmerged", "feat/W1-001"))
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={"feat/W1-001": ["abc111 commit"]},
    )
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    # 未合併 worktree 不應觸發本 audit
    assert payload.get("suppressOutput") is True


# ============================================================
# B 組 RED — Merged worktree audit
# ============================================================

def test_main_single_merged_user_worktree_listed(hook_module, capsys, tmp_path, monkeypatch):
    """RED: 1 個 ahead=0 user worktree → 列出於 audit section"""
    porcelain = _make_porcelain(("/tmp/wt-user-merged", "feat/W1-001"))
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={},  # ahead=0
    )
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    out = capsys.readouterr().out
    assert rc == 0
    message = _extract_message(out)
    assert message is not None, "expected audit message for ahead=0 user worktree"
    # 訊息應指出 worktree 路徑或分支
    assert "/tmp/wt-user-merged" in message or "feat/W1-001" in message
    # 應提供 cleanup 提示
    assert "git worktree remove" in message or "cleanup" in message.lower() or "清理" in message


def test_main_multiple_merged_worktrees_all_listed(hook_module, capsys, tmp_path, monkeypatch):
    """RED: 多個 ahead=0 user worktree → 全部列出（或顯示總數）"""
    porcelain = _make_porcelain(
        ("/tmp/wt-a", "feat/W1-001"),
        ("/tmp/wt-b", "feat/W1-002"),
        ("/tmp/wt-c", "feat/W1-003"),
    )
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={},
    )
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    out = capsys.readouterr().out
    assert rc == 0
    message = _extract_message(out)
    assert message is not None
    # 至少有 3 / 數量 字眼或三個分支至少一個出現（限上限顯示時仍應提及總數）
    has_count = any(token in message for token in ("3", "三"))
    has_any_branch = any(
        f"feat/W1-00{i}" in message or f"/tmp/wt-{c}" in message
        for i, c in [(1, "a"), (2, "b"), (3, "c")]
    )
    assert has_count or has_any_branch, f"expected count or branch list in message:\n{message}"


def test_main_cc_runtime_worktree_excluded(hook_module, capsys, tmp_path, monkeypatch):
    """RED: cc runtime worktree（.claude/worktrees/agent-*）→ 排除"""
    cc_runtime_path = str(tmp_path / ".claude" / "worktrees" / "agent-abc12345")
    porcelain = _make_porcelain(
        (cc_runtime_path, "agent/temp-001"),
    )
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={},
    )
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    # cc runtime worktree 由 worktree-zombie-cleanup-hook 處理；本 audit 應排除
    if not payload.get("suppressOutput"):
        message = payload["hookSpecificOutput"]["additionalContext"]
        assert "agent-abc12345" not in message
        assert cc_runtime_path not in message


def test_main_mixed_user_and_cc_runtime_only_user_listed(hook_module, capsys, tmp_path, monkeypatch):
    """RED: 混合 user + cc runtime worktree → 只列 user"""
    cc_runtime_path = str(tmp_path / ".claude" / "worktrees" / "agent-deadbeef")
    porcelain = _make_porcelain(
        (cc_runtime_path, "agent/temp-001"),
        ("/tmp/wt-user", "feat/W1-001"),
    )
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={},
    )
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    out = capsys.readouterr().out
    assert rc == 0
    message = _extract_message(out)
    assert message is not None
    # user worktree 應出現
    assert "/tmp/wt-user" in message or "feat/W1-001" in message
    # cc runtime 不應出現
    assert "agent-deadbeef" not in message
    assert cc_runtime_path not in message


# ============================================================
# C 組 RED — Metadata orphan audit
# ============================================================

def test_main_orphan_completed_ticket_listed(hook_module, capsys, tmp_path, monkeypatch):
    """RED: ticket md 標為 completed 但 git status 顯示 M → 列為 orphan"""
    ticket_id = "0.18.0-W6-022"
    _write_ticket(tmp_path, ticket_id, status="completed")
    # 模擬 git status 顯示該 ticket md 為 modified
    status_porcelain = f" M docs/work-logs/v0/v0.18/v0.18.0/tickets/{ticket_id}.md\n"
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain="",
        status_porcelain=status_porcelain,
    )
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    out = capsys.readouterr().out
    assert rc == 0
    message = _extract_message(out)
    assert message is not None, "expected orphan message"
    assert ticket_id in message, f"expected ticket id {ticket_id} in message:\n{message}"
    # 應提示「未 commit metadata」/「孤兒」/「orphan」之一
    assert any(kw in message for kw in ("orphan", "孤兒", "未 commit", "未提交")), \
        f"expected orphan hint in message:\n{message}"


def test_main_in_progress_ticket_modified_not_orphan(hook_module, capsys, tmp_path, monkeypatch):
    """RED: in_progress 的 ticket md modified → 不算 orphan（agent 還在寫）"""
    ticket_id = "0.18.0-W1-001"
    _write_ticket(tmp_path, ticket_id, status="in_progress")
    status_porcelain = f" M docs/work-logs/v0/v0.18/v0.18.0/tickets/{ticket_id}.md\n"
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain="",
        status_porcelain=status_porcelain,
    )
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    # in_progress ticket md 變更是預期狀態，不應出現在 orphan 列表
    if not payload.get("suppressOutput"):
        message = payload["hookSpecificOutput"]["additionalContext"]
        assert ticket_id not in message, \
            f"in_progress ticket should NOT be listed as orphan; message:\n{message}"


# ============================================================
# D 組 RED — 綜合：worktree + orphan 同時出現
# ============================================================

def test_main_combined_worktree_and_orphan_both_sections(hook_module, capsys, tmp_path, monkeypatch):
    """RED: ahead=0 worktree + orphan ticket 同時存在 → 兩個 section 都出現"""
    ticket_id = "0.18.0-W6-022"
    _write_ticket(tmp_path, ticket_id, status="completed")
    porcelain = _make_porcelain(("/tmp/wt-user", "feat/W1-001"))
    status_porcelain = f" M docs/work-logs/v0/v0.18/v0.18.0/tickets/{ticket_id}.md\n"
    side_effect = _mk_subprocess_side_effect(
        worktree_porcelain=porcelain,
        unmerged_per_branch={},
        status_porcelain=status_porcelain,
    )
    rc = _run_main_with_mocks(
        hook_module,
        side_effect=side_effect,
        project_root=tmp_path,
        monkeypatch=monkeypatch,
    )
    out = capsys.readouterr().out
    assert rc == 0
    message = _extract_message(out)
    assert message is not None
    # worktree section 內容
    assert "/tmp/wt-user" in message or "feat/W1-001" in message
    # orphan section 內容
    assert ticket_id in message


# ============================================================
# E 組 RED — 失敗模式（不阻塞 SessionStart）
# ============================================================

def test_main_git_failure_silent_no_exception(hook_module, capsys, tmp_path, monkeypatch):
    """RED: git 命令失敗 → silent fail（不阻塞 session）"""
    def failing_side_effect(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 128
        result.stdout = ""
        result.stderr = "fatal: not a git repository"
        return result

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    with patch.object(hook_module, "read_json_from_stdin", return_value={}), \
         patch("subprocess.run", side_effect=failing_side_effect):
        rc = hook_module.main()
    assert rc == 0, "git failure must not raise; SessionStart hook never blocks"
    # 輸出應為 suppressOutput 或合理訊息（不應拋例外）
    out = capsys.readouterr().out
    payload = json.loads(out)
    # 接受 suppressOutput 或空 sections
    assert payload.get("suppressOutput") is True or "hookSpecificOutput" in payload
