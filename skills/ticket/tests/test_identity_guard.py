"""
identity_guard.check_identity 單元測試（W1-048）。

對應規格表五情境（docs/work-logs/v1/.../1.0.0-W1-048.md 判定邏輯表）：
1. 未提供 --as          → 放行（None），且 stderr 含警告（向後相容零破壞）
2. --as = PM 身份        → 放行（None），無 deny
3. --as = who.current   → 放行（None）
4. --as != who.current  → deny（exit 1）
5. who.current 空值      → deny（exit 1）

設計約束驗證：deny 不寫入任何狀態（本測試以 check_identity 不觸碰
save_ticket 為前提；check_identity 僅讀取 load_ticket）。
"""

import argparse
import json

import pytest

from ticket_system.lib import identity_guard
from ticket_system.lib.identity_guard import (
    check_identity,
    PM_AGENT_NAME,
    IDENTITY_DENY_EXIT,
    RESULT_WARN,
    RESULT_EXEMPT,
    RESULT_PASS,
    RESULT_DENY,
)


@pytest.fixture(autouse=True)
def _isolate_identity_log(tmp_path, monkeypatch):
    """Autouse：將 telemetry 落盤導向 tmp，避免污染真實 .claude/hook-logs。

    W1-057 + W1-082：check_identity 全部判定路徑（warn/exempt/pass/deny）均
    append usage.log；本檔測試位於 tests/ 樹（無 ticket_system/tests/conftest.py
    的 hook-logs autouse），故此處自設 HOOK_LOGS_DIR 隔離。
    回傳 log 檔路徑供 telemetry 測試斷言。
    """
    logs_dir = tmp_path / "hook-logs"
    monkeypatch.setenv("HOOK_LOGS_DIR", str(logs_dir))
    return logs_dir / "identity-guard" / "usage.log"


def _patch_who(monkeypatch, who_current):
    """patch load_ticket 回傳含指定 who.current 的 ticket dict。"""
    def fake_load(version, ticket_id):
        if who_current is _SENTINEL_NO_TICKET:
            return None
        return {"id": ticket_id, "who": {"current": who_current}}
    monkeypatch.setattr(identity_guard, "load_ticket", fake_load)


_SENTINEL_NO_TICKET = object()


def test_no_as_flag_passes_with_warning(monkeypatch, capsys):
    """情境 1：未提供 --as → 放行 + stderr 警告（向後相容零破壞）。"""
    _patch_who(monkeypatch, "thyme-python-developer")
    result = check_identity("1.0.0", "1.0.0-W1-048", None)
    assert result is None
    captured = capsys.readouterr()
    assert "建議帶 --as" in captured.err
    assert captured.err  # 警告走 stderr


def test_no_as_flag_empty_string_treated_as_unprovided(monkeypatch, capsys):
    """空字串等同未提供（argparse default None；防禦性測試）。"""
    _patch_who(monkeypatch, "thyme-python-developer")
    assert check_identity("1.0.0", "1.0.0-W1-048", "") is None


def test_pm_identity_exempt(monkeypatch, capsys):
    """情境 2：--as = PM 身份 → 一律放行（bookkeeping 豁免），不查 who.current。"""
    _patch_who(monkeypatch, "thyme-python-developer")  # 即使不符也放行
    result = check_identity("1.0.0", "1.0.0-W1-048", PM_AGENT_NAME)
    assert result is None
    captured = capsys.readouterr()
    assert "deny" not in captured.err


def test_non_string_as_value_treated_as_unprovided(monkeypatch, capsys):
    """非 str 值（如 Mock args auto-attr / getattr default）視為未提供 → 放行 + 警告。

    回歸防護：既有 Mock-based 測試傳 args.as_agent 為 Mock 物件（truthy 但非
    str），不得誤觸發 deny。argparse --as 恆為 str/None，此為防禦性。
    """
    from unittest.mock import Mock
    _patch_who(monkeypatch, "thyme-python-developer")
    result = check_identity("1.0.0", "1.0.0-W1-048", Mock())
    assert result is None
    captured = capsys.readouterr()
    assert "deny" not in captured.err


def test_matching_identity_passes(monkeypatch):
    """情境 3：--as = who.current → 放行。"""
    _patch_who(monkeypatch, "thyme-python-developer")
    result = check_identity("1.0.0", "1.0.0-W1-048", "thyme-python-developer")
    assert result is None


def test_mismatch_identity_denied(monkeypatch, capsys):
    """情境 4：--as != who.current → deny（exit 1）+ stderr 訊息引導回報 PM。"""
    _patch_who(monkeypatch, "thyme-python-developer")
    result = check_identity("1.0.0", "1.0.0-W1-048", "claude")
    assert result == IDENTITY_DENY_EXIT
    captured = capsys.readouterr()
    assert "deny" in captured.err
    assert "回報 PM" in captured.err
    assert "claude" in captured.err
    assert "thyme-python-developer" in captured.err


def test_empty_who_current_denied(monkeypatch, capsys):
    """情境 5：who.current 空值 + 提供 --as → deny（exit 1）。"""
    _patch_who(monkeypatch, "")
    result = check_identity("1.0.0", "1.0.0-W1-048", "claude")
    assert result == IDENTITY_DENY_EXIT
    captured = capsys.readouterr()
    assert "deny" in captured.err
    assert "(未指派)" in captured.err


def test_missing_who_key_denied(monkeypatch, capsys):
    """who 欄位缺失（None）+ 提供非 PM --as → deny（空值視同未指派）。"""
    def fake_load(version, ticket_id):
        return {"id": ticket_id}  # 無 who 欄位
    monkeypatch.setattr(identity_guard, "load_ticket", fake_load)
    result = check_identity("1.0.0", "1.0.0-W1-048", "claude")
    assert result == IDENTITY_DENY_EXIT


def test_ticket_not_found_denied_with_as(monkeypatch, capsys):
    """ticket 不存在 + 提供非 PM --as → who.current 視為空值 → deny。"""
    _patch_who(monkeypatch, _SENTINEL_NO_TICKET)
    result = check_identity("1.0.0", "1.0.0-W1-999", "claude")
    assert result == IDENTITY_DENY_EXIT


def test_ticket_not_found_pm_still_exempt(monkeypatch):
    """ticket 不存在但 --as = PM → 仍放行（豁免先於 who.current 解析）。"""
    _patch_who(monkeypatch, _SENTINEL_NO_TICKET)
    assert check_identity("1.0.0", "1.0.0-W1-999", PM_AGENT_NAME) is None


# ============================================================
# Telemetry 落盤（W1-057 warn/deny + W1-082 pass/exempt 全路徑）
# ============================================================


def _read_records(log_path):
    """讀取 usage.log，回傳逐行 parse 的 JSON record 列表。"""
    text = log_path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_warn_path_writes_telemetry(monkeypatch, _isolate_identity_log):
    """warn 路徑（未提供 --as）落盤一行結構化記錄，含 timestamp 與 result=warn。"""
    log_path = _isolate_identity_log
    _patch_who(monkeypatch, "thyme-python-developer")

    check_identity("1.0.0", "1.0.0-W1-057", None, command="complete")

    assert log_path.exists()
    records = _read_records(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["result"] == RESULT_WARN
    assert rec["command"] == "complete"
    assert rec["ticket_id"] == "1.0.0-W1-057"
    assert rec["has_as"] is False
    assert rec["timestamp"]  # 非空


def test_deny_path_writes_telemetry(monkeypatch, _isolate_identity_log):
    """deny 路徑（身份不符）落盤同格式記錄，result=deny 且 has_as=True。"""
    log_path = _isolate_identity_log
    _patch_who(monkeypatch, "thyme-python-developer")

    result = check_identity("1.0.0", "1.0.0-W1-057", "claude", command="complete")

    assert result == IDENTITY_DENY_EXIT
    records = _read_records(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["result"] == RESULT_DENY
    assert rec["has_as"] is True
    assert rec["ticket_id"] == "1.0.0-W1-057"
    assert rec["timestamp"]


def test_pass_path_writes_telemetry(monkeypatch, _isolate_identity_log):
    """pass 路徑（--as 與 who.current 相符）落盤 result=pass（W1-082：分母補齊）。

    回歸防護：W1-057 原設計只記 warn/deny，完美遵循時 log 零增長，
    使用率指標分母缺失不可計算（W1-049.2 量測缺口）。
    """
    log_path = _isolate_identity_log
    _patch_who(monkeypatch, "thyme-python-developer")

    check_identity("1.0.0", "1.0.0-W1-082", "thyme-python-developer", command="complete")

    assert log_path.exists()
    records = _read_records(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["result"] == RESULT_PASS
    assert rec["command"] == "complete"
    assert rec["ticket_id"] == "1.0.0-W1-082"
    assert rec["has_as"] is True
    assert rec["timestamp"]  # 非空


def test_exempt_path_writes_telemetry(monkeypatch, _isolate_identity_log):
    """exempt 路徑（--as = PM 豁免）落盤 result=exempt（W1-082）。"""
    log_path = _isolate_identity_log
    _patch_who(monkeypatch, "thyme-python-developer")  # 即使不符也豁免放行

    result = check_identity(
        "1.0.0", "1.0.0-W1-082", PM_AGENT_NAME, command="set-acceptance"
    )

    assert result is None
    records = _read_records(log_path)
    assert len(records) == 1
    rec = records[0]
    assert rec["result"] == RESULT_EXEMPT
    assert rec["command"] == "set-acceptance"
    assert rec["has_as"] is True
    # 隱私設計維持：僅記 has_as 布林，不落 as_value 原文（agent 名稱）
    assert PM_AGENT_NAME not in log_path.read_text(encoding="utf-8")


def test_telemetry_appends_multiple_records(monkeypatch, _isolate_identity_log):
    """四路徑連續觸發各 append 一行累積（append-only 語義 + 全路徑覆蓋）。"""
    log_path = _isolate_identity_log
    _patch_who(monkeypatch, "thyme-python-developer")

    check_identity("1.0.0", "1.0.0-W1-057", None, command="complete")
    check_identity("1.0.0", "1.0.0-W1-057", "claude", command="set-acceptance")
    check_identity("1.0.0", "1.0.0-W1-057", PM_AGENT_NAME, command="close")
    check_identity("1.0.0", "1.0.0-W1-057", "thyme-python-developer", command="complete")

    records = _read_records(log_path)
    assert len(records) == 4
    assert [r["result"] for r in records] == [
        RESULT_WARN,
        RESULT_DENY,
        RESULT_EXEMPT,
        RESULT_PASS,
    ]


def test_telemetry_failure_does_not_block_main_flow(monkeypatch, capsys):
    """落盤失敗（OSError）不阻斷 CLI 主流程，但 stderr 可見（雙通道）。"""
    _patch_who(monkeypatch, "thyme-python-developer")

    def _raise_oserror(*args, **kwargs):
        raise OSError("simulated disk full")

    # patch open，模擬寫入失敗；deny 判定仍應正常返回
    monkeypatch.setattr("builtins.open", _raise_oserror)

    result = check_identity("1.0.0", "1.0.0-W1-057", "claude", command="complete")

    # 主流程仍正常返回 deny exit code（telemetry 失敗不影響判定）
    assert result == IDENTITY_DENY_EXIT
    captured = capsys.readouterr()
    assert "telemetry 落盤失敗" in captured.err


def test_default_command_is_unknown(monkeypatch, _isolate_identity_log):
    """呼叫端未傳 command 時，記錄 command=(unknown)（向後相容預設）。"""
    log_path = _isolate_identity_log
    _patch_who(monkeypatch, "thyme-python-developer")

    check_identity("1.0.0", "1.0.0-W1-057", None)

    records = _read_records(log_path)
    assert records[0]["command"] == "(unknown)"


# ============================================================
# 呼叫端 command 歸因（W1-083：三個寫入命令各傳真實名稱）
# ============================================================
#
# 回歸防護：W1-082 實機 smoke 發現 usage.log 全部紀錄 command 恆為 (unknown)
# （W1-057 設計含 command 欄位但呼叫端未傳），per-command 使用率歸因不可自動
# 計算。本節以 deny 早退路徑驗證各呼叫端傳入值——deny 在 check_identity 內
# 直接 return，不執行命令本體，無需鋪設完整 ticket 環境且零狀態副作用。


def _make_args(ticket_id: str, as_agent: str) -> argparse.Namespace:
    """組最小 args；deny 早退只會讀 ticket_id 與 as_agent 兩欄位。"""
    return argparse.Namespace(ticket_id=ticket_id, as_agent=as_agent)


def _caller_complete(args, version):
    from ticket_system.commands.track import _execute_complete
    return _execute_complete(args, version)


def _caller_check_acceptance(args, version):
    from ticket_system.commands.track_acceptance import execute_check_acceptance
    return execute_check_acceptance(args, version)


def _caller_set_acceptance(args, version):
    from ticket_system.commands.track_set_acceptance import execute_set_acceptance
    return execute_set_acceptance(args, version)


@pytest.mark.parametrize(
    ("caller", "expected_command"),
    [
        (_caller_complete, "complete"),
        (_caller_check_acceptance, "check-acceptance"),
        (_caller_set_acceptance, "set-acceptance"),
    ],
    ids=["complete", "check-acceptance", "set-acceptance"],
)
def test_caller_passes_real_command_name(
    monkeypatch, _isolate_identity_log, caller, expected_command
):
    """三個寫入命令呼叫 check_identity 時皆傳入真實 command 名稱（非 (unknown)）。"""
    log_path = _isolate_identity_log
    _patch_who(monkeypatch, "thyme-python-developer")

    # 身份不符 → deny 早退：呼叫端在 check_identity 後直接 return，無命令本體副作用
    result = caller(_make_args("1.0.0-W1-083", "claude"), "1.0.0")

    assert result == IDENTITY_DENY_EXIT
    records = _read_records(log_path)
    assert len(records) == 1
    assert records[0]["command"] == expected_command
    assert records[0]["command"] != "(unknown)"
