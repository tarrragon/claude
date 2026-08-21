"""create 的 when-blockedBy 一致性警告測試。

覆蓋 acceptance：
1. when 含 ticket ID 且 blockedBy 空 → 輸出 WARNING，且不阻擋建票
2. when 不含 ticket ID → 無 WARNING
3. when 含 ticket ID 且 blockedBy 非空 → 無 WARNING
4. WARNING 訊息含命中的 ID、後果說明與補填指令範例
5. 測試涵蓋上述三種輸入
"""
from __future__ import annotations

import argparse
import io
from contextlib import redirect_stderr, redirect_stdout

from ticket_system.commands import create as create_cmd
from ticket_system.lib.field_validators import check_when_blocked_by_consistency


def _make_args(**overrides):
    """建立 argparse.Namespace，欄位對齊 create.execute 預期簽名。"""
    defaults = dict(
        version="1.0.1",
        wave=1,
        seq=None,
        action="實作",
        target="when-blockedBy 一致性測試",
        title=None,
        type="IMP",
        priority=None,
        who="待派發",
        what=None,
        when="立即",
        where_layer=None,
        where_files="ticket_system/commands/create.py",
        why="測試 when-blockedBy 一致性警告",
        how_type=None,
        how_strategy="驗證一致性檢查行為",
        parent=None,
        source_ticket=None,
        blocked_by=None,
        related_to=None,
        acceptance=["測試通過"],
        decision_tree_entry="Ticket",
        decision_tree_decision="直接派發",
        decision_tree_rationale="測試情境",
        quiet=False,
        verbose=False,
        json_output=False,
        force=False,
        allow_duplicate=False,
        topic=None,
        new_topic=None,
        no_topic=False,
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
# 單元層級：直接驗證 check_when_blocked_by_consistency 的三種輸入邊界
# ---------------------------------------------------------------------------


def test_when_with_id_and_empty_blocked_by_emits_warning(capsys):
    """when 含 ticket ID 且 blockedBy 空 → 輸出 WARNING。"""
    check_when_blocked_by_consistency(when="W3-731 完成後", blocked_by=None)
    out = capsys.readouterr().out
    assert "[WARNING]" in out
    assert "W3-731" in out


def test_when_without_id_emits_no_warning(capsys):
    """when 不含 ticket ID → 無 WARNING。"""
    check_when_blocked_by_consistency(when="立即可執行", blocked_by=None)
    out = capsys.readouterr().out
    assert out == ""


def test_when_with_id_and_nonempty_blocked_by_emits_no_warning(capsys):
    """when 含 ticket ID 且 blockedBy 非空 → 無 WARNING。"""
    check_when_blocked_by_consistency(
        when="W3-731 完成後", blocked_by=["1.0.1-W3-731"]
    )
    out = capsys.readouterr().out
    assert out == ""


def test_warning_message_contains_id_consequence_and_command_example(capsys):
    """WARNING 訊息含命中的 ID、後果說明（ready 判定恆為真）與補填指令範例。"""
    check_when_blocked_by_consistency(when="W3-731 完成後", blocked_by=None)
    out = capsys.readouterr().out
    assert "W3-731" in out
    assert "ready" in out
    assert "set-blocked-by" in out


def test_warning_command_example_space_separated_for_multiple_ids(capsys):
    """when 命中 2 個以上不同 ID 時，建議指令以空格分隔（可直接執行）。

    set-blocked-by 的 value 是單一 positional，要求空格分隔多個 ID
    （`ticket track set-blocked-by --help`）；敘述位置（「when 欄位提及 ...」）
    維持頓號連接不受影響，僅指令範例位置改空格。
    """
    check_when_blocked_by_consistency(
        when="W3-731 與 W3-732 完成後", blocked_by=None
    )
    out = capsys.readouterr().out
    assert "W3-731、W3-732" in out  # 敘述位置：頓號連接
    assert "set-blocked-by <ticket-id> W3-731 W3-732" in out  # 指令位置：空格連接


# ---------------------------------------------------------------------------
# 整合層級：確認掛載於 create.execute 且不阻擋建票（exit_code == 0）
# ---------------------------------------------------------------------------


def test_create_with_when_id_and_empty_blocked_by_warns_but_succeeds(
    seeded_repo_root,
):
    """整合層級驗證：WARNING 已掛載於 create.execute 路徑，且不阻擋建票（exit 0）。

    blockedBy 非空的整合案例需引用真實存在的 ticket，交由上方單元測試
    （test_when_with_id_and_nonempty_blocked_by_emits_no_warning）覆蓋，
    避免整合層另建 fixture ticket 增加不必要複雜度。
    """
    args = _make_args(when="W3-731 完成後", blocked_by=None)
    stdout, _, exit_code = _capture(args)
    assert exit_code == 0
    assert "[WARNING]" in stdout
    assert "W3-731" in stdout
