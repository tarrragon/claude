"""Group B：5 層 fail-open 資料來源測試。

對應 Phase 2 §3 Group B（B{N}.1/.2/.3/.4/.5）與 AC3。

四維場景（針對每個資料來源 N）：
- B{N}.1 正常：合法內容 → 對應欄位正確
- B{N}.2 異常：I/O 類例外 → SAFE_CALL 走 fallback + errors/pending 記錄
- B{N}.3 邊界：空回傳 → 預設值
- B{N}.4 中斷：多來源同時失敗（串聯 test）
- B{N}.5 邊界：.claude/state/ 或 .claude/handoffs/ 目錄不存在
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List

import pytest

from ticket_system.lib.checkpoint_state import (
    IO_ERRORS,
    PendingCheck,
    SAFE_CALL,
    _read_dispatch_active,
    _read_git_status,
    _read_git_worktrees,
    _read_handoff_pending,
    _query_in_progress_tickets,
)


# ===========================================================================
# SAFE_CALL 本體行為
# ===========================================================================


def test_SAFE_CALL_success_returns_result_and_marks_ok():
    errors: dict = {}
    pending: List[PendingCheck] = []
    result = SAFE_CALL(lambda: 42, errors, pending, "src", fallback=0)
    assert result == 42
    assert errors == {"src": "ok"}
    assert pending == []


def test_SAFE_CALL_catches_filenotfounderror_and_returns_fallback():
    errors: dict = {}
    pending: List[PendingCheck] = []

    def raiser():
        raise FileNotFoundError("missing")

    result = SAFE_CALL(raiser, errors, pending, "src", fallback=None)
    assert result is None
    assert "FileNotFoundError" in errors["src"]
    assert len(pending) == 1
    assert pending[0].check_id == "data_source_src"
    assert pending[0].auto_detectable is False
    assert pending[0].blocker is False


def test_SAFE_CALL_does_not_catch_attributeerror():
    """AttributeError 屬程式 bug，不該被 SAFE_CALL 捕獲（Phase 3a §1.3 捕獲判準）。"""
    errors: dict = {}
    pending: List[PendingCheck] = []

    def raiser():
        raise AttributeError("bug")

    with pytest.raises(AttributeError):
        SAFE_CALL(raiser, errors, pending, "src", fallback=None)


def test_IO_ERRORS_whitelist_includes_expected_types():
    assert subprocess.CalledProcessError in IO_ERRORS
    assert subprocess.TimeoutExpired in IO_ERRORS
    assert FileNotFoundError in IO_ERRORS
    assert PermissionError in IO_ERRORS
    assert json.JSONDecodeError in IO_ERRORS
    assert OSError in IO_ERRORS


# ===========================================================================
# B1: git-status
# ===========================================================================


def test_B1_1_git_status_normal_returns_uncommitted_count(tmp_git_repo: Path):
    # 建立 2 個未提交檔案
    (tmp_git_repo / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp_git_repo / "b.txt").write_text("b\n", encoding="utf-8")
    assert _read_git_status(tmp_git_repo) == 2


def test_B1_2_git_status_non_git_dir_raises_called_process_error(tmp_path: Path):
    # 非 git 目錄 → git 返回非零
    with pytest.raises((subprocess.CalledProcessError, FileNotFoundError)):
        _read_git_status(tmp_path)


def test_B1_3_git_status_empty_clean_tree_returns_zero(tmp_git_repo: Path):
    assert _read_git_status(tmp_git_repo) == 0


def test_B1_2_via_SAFE_CALL_falls_back_to_none(tmp_path: Path):
    errors: dict = {}
    pending: List[PendingCheck] = []
    result = SAFE_CALL(
        lambda: _read_git_status(tmp_path),
        errors, pending, "git-status", fallback=None,
    )
    assert result is None
    assert "git-status" in errors
    assert errors["git-status"] != "ok"


# ===========================================================================
# B2: dispatch-active
# ===========================================================================


def test_B2_1_dispatch_active_normal_counts_only_non_completed(
    tmp_path: Path, mock_dispatch_active
):
    mock_dispatch_active(active_count=2, completed_count=3, project_root=tmp_path)
    active, raw = _read_dispatch_active(tmp_path)
    assert active == 2
    assert "dispatches" in raw


def test_B2_2_dispatch_active_missing_file_raises_filenotfounderror(tmp_path: Path):
    # 檔案不存在但父目錄存在
    (tmp_path / ".claude" / "state").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        _read_dispatch_active(tmp_path)


def test_B2_3_dispatch_active_empty_dispatches_returns_zero(
    tmp_path: Path, mock_dispatch_active
):
    mock_dispatch_active(active_count=0, completed_count=0, project_root=tmp_path)
    active, raw = _read_dispatch_active(tmp_path)
    assert active == 0


def test_B2_2_dispatch_active_malformed_json_raises(
    tmp_path: Path,
):
    state_dir = tmp_path / ".claude" / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "dispatch-active.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _read_dispatch_active(tmp_path)


def test_B2_5_dispatch_active_state_dir_missing_raises_filenotfounderror(
    tmp_path: Path,
):
    """.claude/state/ 整個目錄不存在（Phase 2 §B.5）。"""
    # 連 .claude/state/ 都沒有
    with pytest.raises(FileNotFoundError):
        _read_dispatch_active(tmp_path)


# ===========================================================================
# B3: handoff-pending
# ===========================================================================


def test_B3_1_handoff_pending_normal_returns_ticket_id(
    tmp_path: Path, mock_handoff_pending
):
    mock_handoff_pending(ticket_id="W10-017.8", project_root=tmp_path)
    assert _read_handoff_pending(tmp_path) == "W10-017.8"


def test_B3_3_handoff_pending_empty_dir_returns_none(tmp_path: Path):
    pending_dir = tmp_path / ".claude" / "handoffs" / "pending"
    pending_dir.mkdir(parents=True)
    assert _read_handoff_pending(tmp_path) is None


def test_B3_5_handoff_pending_dir_missing_raises_filenotfounderror(tmp_path: Path):
    """.claude/handoffs/ 整個目錄不存在（Phase 2 §B.5）。"""
    with pytest.raises(FileNotFoundError):
        _read_handoff_pending(tmp_path)


def test_B3_1_handoff_pending_picks_latest_mtime(
    tmp_path: Path, mock_handoff_pending
):
    import os
    import time as time_mod

    p1 = mock_handoff_pending(
        ticket_id="OLD", project_root=tmp_path, filename="a.json"
    )
    # 明確設定 p1 較舊
    old = time_mod.time() - 1000
    os.utime(p1, (old, old))
    mock_handoff_pending(
        ticket_id="NEW", project_root=tmp_path, filename="b.json"
    )
    assert _read_handoff_pending(tmp_path) == "NEW"


# ===========================================================================
# B4: ticket-query
# ===========================================================================


def test_B4_1_ticket_query_normal_returns_ids(mock_ticket_query, tmp_path: Path):
    mock_ticket_query(ids=["T1", "T2", "T3"])
    result = _query_in_progress_tickets(tmp_path)
    assert result == ["T1", "T2", "T3"]


def test_B4_2_ticket_query_subprocess_error_raises(mock_ticket_query, tmp_path: Path):
    mock_ticket_query(
        raises=subprocess.CalledProcessError(returncode=1, cmd="ticket", stderr="fail")
    )
    with pytest.raises(subprocess.CalledProcessError):
        _query_in_progress_tickets(tmp_path)


def test_B4_3_ticket_query_empty_returns_empty_list(mock_ticket_query, tmp_path: Path):
    mock_ticket_query(ids=[])
    assert _query_in_progress_tickets(tmp_path) == []


def test_B4_2_ticket_query_via_SAFE_CALL_falls_back(mock_ticket_query, tmp_path: Path):
    mock_ticket_query(raises=FileNotFoundError("ticket CLI missing"))
    errors: dict = {}
    pending: List[PendingCheck] = []
    result = SAFE_CALL(
        lambda: _query_in_progress_tickets(tmp_path),
        errors, pending, "ticket-query", fallback=[],
    )
    assert result == []
    assert "ticket-query" in errors
    assert errors["ticket-query"] != "ok"
    assert len(pending) == 1


# ===========================================================================
# B5: git-worktree
# ===========================================================================


def test_B5_1_git_worktree_normal_excludes_main(tmp_git_repo: Path, tmp_path: Path):
    # 主 worktree 本身應被排除
    result = _read_git_worktrees(tmp_git_repo)
    assert result == []


def test_B5_1_git_worktree_lists_linked(tmp_git_repo: Path, tmp_path: Path):
    # 建立一個 linked worktree
    wt_dir = tmp_path / "wt1"
    subprocess.run(
        ["git", "worktree", "add", str(wt_dir), "-b", "branch1"],
        cwd=tmp_git_repo, check=True, capture_output=True,
    )
    result = _read_git_worktrees(tmp_git_repo)
    assert len(result) == 1
    assert "wt1" in result[0]


def test_B5_2_git_worktree_non_git_raises(tmp_path: Path):
    with pytest.raises((subprocess.CalledProcessError, FileNotFoundError)):
        _read_git_worktrees(tmp_path)


def test_B5_2_git_worktree_via_SAFE_CALL_falls_back(tmp_path: Path):
    errors: dict = {}
    pending: List[PendingCheck] = []
    result = SAFE_CALL(
        lambda: _read_git_worktrees(tmp_path),
        errors, pending, "git-worktree", fallback=[],
    )
    assert result == []
    assert "git-worktree" in errors
    assert errors["git-worktree"] != "ok"


# ===========================================================================
# B4 交錯：多資料來源同時失敗仍 fail-open
# ===========================================================================


def test_B_interleaved_multiple_sources_fail_all_fallback(tmp_path: Path):
    """多來源同時失敗 → 所有 SAFE_CALL 各自走 fallback，errors 累積。"""
    errors: dict = {}
    pending: List[PendingCheck] = []

    r1 = SAFE_CALL(
        lambda: _read_git_status(tmp_path),
        errors, pending, "git-status", fallback=None,
    )
    r2 = SAFE_CALL(
        lambda: _read_dispatch_active(tmp_path),
        errors, pending, "dispatch-active", fallback=(0, {}),
    )
    r3 = SAFE_CALL(
        lambda: _read_handoff_pending(tmp_path),
        errors, pending, "handoff-pending", fallback=None,
    )

    assert r1 is None
    assert r2 == (0, {})
    assert r3 is None
    # 三個來源皆有錯誤記錄
    for key in ("git-status", "dispatch-active", "handoff-pending"):
        assert key in errors
        assert errors[key] != "ok"
    assert len(pending) == 3
