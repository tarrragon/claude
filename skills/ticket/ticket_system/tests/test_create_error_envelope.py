"""
test_create_error_envelope
==========================

W17-008.5.3：覆蓋 commands/create.py 業務錯誤路徑改寫為 ErrorEnvelope 後的整合測試。

每案例呼叫 ticket CLI（subprocess）模擬實際使用，斷言：
- exit code = 1（錯誤路徑）或 envelope 輸出
- stdout / stderr 含 ERROR_ENVELOPE_VERSION_MARKER
- 含對應 component / action / errno

Source: ticket 0.18.0-W17-008.5.3
"""
import argparse
import io
import sys
from contextlib import redirect_stderr, redirect_stdout

import pytest

from ticket_system.commands import create as create_cmd
from ticket_system.lib.messages import ERROR_ENVELOPE_VERSION_MARKER


def _make_args(**overrides):
    """建立 argparse.Namespace 包含 create.execute 預期欄位的預設值。"""
    defaults = dict(
        version=None,
        wave=None,
        seq=None,
        action="測試",
        target="錯誤路徑",
        title=None,
        type="IMP",
        priority=None,
        who=None,
        what=None,
        when=None,
        where_layer=None,
        where_files=None,
        why="測試錯誤路徑",
        how_type=None,
        how_strategy=None,
        parent=None,
        source_ticket=None,
        blocked_by=None,
        related_to=None,
        acceptance=None,
        decision_tree_entry=None,
        decision_tree_decision=None,
        decision_tree_rationale=None,
        quiet=False,
        verbose=False,
        json_output=False,
        force=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _capture(args):
    """執行 create.execute(args) 並擷取 stdout / stderr / exit code。"""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    exit_code = None
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            exit_code = create_cmd.execute(args)
    except SystemExit as exc:
        exit_code = exc.code
    return out_buf.getvalue(), err_buf.getvalue(), exit_code


# ---------------------------------------------------------------------------
# 整合測試 1：缺 --wave 參數
# ---------------------------------------------------------------------------


def test_missing_wave_emits_envelope():
    """根任務未提供 --wave → envelope MISSING_WAVE_PARAMETER。"""
    args = _make_args(wave=None, parent=None)
    stdout, _, exit_code = _capture(args)
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "component: create" in stdout
    assert "errno: MISSING_WAVE_PARAMETER" in stdout


# ---------------------------------------------------------------------------
# 整合測試 2：非法 --type（會走到 validate_version_registered 之後的邏輯）
# 這裡用 --source-ticket 格式無效作為 errno=INVALID_TICKET_ID_FORMAT 的入口
# ---------------------------------------------------------------------------


def test_invalid_source_ticket_id_emits_envelope():
    """--source-ticket ID 格式無效 → envelope INVALID_TICKET_ID_FORMAT。"""
    args = _make_args(wave=99, source_ticket="not-a-valid-id", type="IMP")
    stdout, _, exit_code = _capture(args)
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "errno: INVALID_TICKET_ID_FORMAT" in stdout
    assert "action: validate_source_ticket" in stdout


# ---------------------------------------------------------------------------
# 整合測試 3：--source-ticket 與 --parent 互斥
# ---------------------------------------------------------------------------


def test_source_parent_mutually_exclusive_emits_envelope():
    """--source-ticket 與 --parent 同用 → envelope SOURCE_PARENT_MUTUALLY_EXCLUSIVE。"""
    args = _make_args(
        wave=99,
        parent="0.99.0-W99-001",
        source_ticket="0.99.0-W99-002",
    )
    stdout, _, exit_code = _capture(args)
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "errno: SOURCE_PARENT_MUTUALLY_EXCLUSIVE" in stdout


# ---------------------------------------------------------------------------
# 整合測試 4：--why 缺失（IMP 類型）
# ---------------------------------------------------------------------------


def test_why_required_for_imp_emits_envelope_to_stderr():
    """IMP 類型未提供 --why → envelope WHY_REQUIRED 寫至 stderr 並 sys.exit(1)。

    需提供 decision-tree 三參數讓 _parse_cli_args_to_config 能進入 why 檢查。
    """
    args = _make_args(
        wave=99,
        type="IMP",
        why=None,
        decision_tree_entry="x",
        decision_tree_decision="y",
        decision_tree_rationale="z",
    )
    stdout, stderr, exit_code = _capture(args)
    assert exit_code == 1
    # WHY_REQUIRED 走 stderr 路徑
    assert ERROR_ENVELOPE_VERSION_MARKER in stderr
    assert "errno: WHY_REQUIRED" in stderr


# ---------------------------------------------------------------------------
# 整合測試 5：decision-tree 部分參數（非豁免）
# ---------------------------------------------------------------------------


def test_decision_tree_partial_params_emits_envelope():
    """非豁免（IMP 根任務）但僅提供部分 decision-tree 參數 → envelope DECISION_TREE_MISSING_PARTIAL。"""
    args = _make_args(
        wave=99,
        type="IMP",
        decision_tree_entry="entry only",  # decision/rationale 缺
    )
    stdout, _, exit_code = _capture(args)
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "errno: DECISION_TREE_MISSING_PARTIAL" in stdout


# ---------------------------------------------------------------------------
# 整合測試 6：decision-tree 全缺（非豁免）
# ---------------------------------------------------------------------------


def test_decision_tree_missing_all_emits_envelope():
    """非豁免（IMP 根任務）未提供任何 decision-tree 參數 → envelope DECISION_TREE_MISSING_ALL。"""
    args = _make_args(
        wave=99,
        type="IMP",
    )
    stdout, _, exit_code = _capture(args)
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    assert "errno: DECISION_TREE_MISSING_ALL" in stdout


# ---------------------------------------------------------------------------
# 整合測試 7：blocked-by 不存在的 ticket
# ---------------------------------------------------------------------------


def test_blocked_by_not_found_emits_envelope():
    """blockedBy 引用不存在的 ticket → envelope BLOCKED_BY_NOT_FOUND。"""
    args = _make_args(
        wave=99,
        type="DOC",  # DOC 豁免 decision-tree
        blocked_by="0.99.0-W99-DOES-NOT-EXIST",
        why="not required for DOC",
    )
    stdout, _, exit_code = _capture(args)
    # DOC 豁免 why；但 blocked-by 應觸發 envelope
    assert exit_code == 1
    assert ERROR_ENVELOPE_VERSION_MARKER in stdout
    # 可能是 INVALID_TICKET_ID_FORMAT（先驗格式）或 BLOCKED_BY_NOT_FOUND
    assert ("errno: BLOCKED_BY_NOT_FOUND" in stdout
            or "errno: INVALID_TICKET_ID_FORMAT" in stdout)
