"""
身份申報守衛（identity guard）— --as 旗標與 ticket who.current 對照。

背景（PC-V1-002 防護鏈 CLI 層）：W1-045 WRAP 二輪翻案認定威脅模型為「誠實但
誤解的 agent」——generic agent 收到 Ticket ID 即走自律收尾流程，越權勾選 PM
保留的 acceptance 並 complete（W1-044 探針實證）。規則層（W1-046/047）已用文字
固化防線，本模組在世界平面（CLI exit code）強制：寫入命令可選用 --as <agent-name>
申報身份，與 frontmatter who.current 精確比對，不符即 deny（exit 1），不寫入任何
ticket 狀態（純前置檢查）。

過渡策略（warn-only）：未提供 --as 維持現行為，僅 stderr 警告一行（向後相容）。
轉強制（無 --as 即阻擋）的 trigger 由獨立監測 ticket 評估，不在本模組範圍。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ticket_system.lib.parser import load_ticket

# PM bookkeeping 豁免身份：代收尾、stale cleanup 等合法跨 ticket 操作一律放行。
PM_AGENT_NAME = "rosemary-project-manager"

# Deny 結果（exit 1）— 為業務拒絕（identity mismatch），非執行錯誤。
IDENTITY_DENY_EXIT = 1

# --- Telemetry（W1-057 warn/deny + W1-082 pass/exempt 全路徑落盤觀測管線）--------
#
# 過渡期（warn-only）需稽核 --as 使用率與 deny/warn 分佈，作為 W1-049 轉強制裁決
# 的資料依據；僅寫 stderr 無法事後統計，故每條判定路徑各 append 一行結構化記錄。
# W1-082 補齊放行路徑（pass/exempt）：只記 warn/deny 會使「使用率指標」分母缺失
# 不可計算，且完美遵循（全 --as 正確）時 log 零增長，10+ 樣本 trigger 永不成立。
# 基底目錄沿用 force-usage 的 HOOK_LOGS_DIR env 慣例（測試隔離），
# 子目錄 identity-guard 區隔此管線。
_HOOK_LOGS_DIR_ENV = "HOOK_LOGS_DIR"
_DEFAULT_HOOK_LOGS_DIR = ".claude/hook-logs"
_IDENTITY_LOG_SUBDIR = "identity-guard"
_IDENTITY_LOG_FILENAME = "usage.log"

# 結果列舉（四路徑與 check_identity 判定邏輯一一對應）：
#   warn   = 未提供 --as 放行（情境 1）
#   exempt = PM 身份豁免放行（情境 2）
#   pass   = --as 與 who.current 相符放行（情境 3）
#   deny   = 身份不符攔截（情境 4）
RESULT_WARN = "warn"
RESULT_EXEMPT = "exempt"
RESULT_PASS = "pass"
RESULT_DENY = "deny"


def _resolve_identity_log_path() -> Path:
    """解析 identity-guard usage.log 路徑；HOOK_LOGS_DIR 優先（測試隔離用）。"""
    base = Path(os.environ.get(_HOOK_LOGS_DIR_ENV, _DEFAULT_HOOK_LOGS_DIR))
    return base / _IDENTITY_LOG_SUBDIR / _IDENTITY_LOG_FILENAME


def _write_telemetry(
    *,
    command: str,
    ticket_id: str,
    as_value: Optional[str],
    result: str,
    caller_type: str,
) -> None:
    """Append 一行結構化記錄；失敗不阻斷主流程，但寫 stderr（observability 規則 4）。

    欄位：timestamp / command / ticket_id / has_as（--as 有無）/ result / caller_type。
    result 為四值列舉（warn / exempt / pass / deny），覆蓋 check_identity 全部
    判定路徑，使「--as 使用率」分子分母皆可從 log 計算。
    caller_type 為三值列舉（pm / agent / unknown），標註呼叫者角色類型。
    不記錄 as_value 原文，僅記其有無，避免將 agent 名稱寫入長期觀測檔。
    """
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "ticket_id": ticket_id,
        "has_as": bool(isinstance(as_value, str) and as_value.strip()),
        "result": result,
        "caller_type": caller_type,
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"

    try:
        log_path = _resolve_identity_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # POSIX O_APPEND 對 ≤ PIPE_BUF (4096 bytes) 為原子，單行 JSON 遠低於此閾值
        with open(log_path, mode="a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
    except OSError as exc:
        # 落盤失敗不阻斷 CLI 主流程（telemetry 為旁路觀測），但雙通道可見：
        # 此處寫 stderr，確保用戶端不靜默吞掉（quality-baseline 規則 4 擴充）。
        sys.stderr.write(
            f"[identity-guard] telemetry 落盤失敗（不影響本次操作）：{exc}\n"
        )


def _resolve_who_current(version: str, ticket_id: str) -> Optional[str]:
    """讀取 ticket frontmatter 的 who.current；無法解析時回傳 None（視為空值）。"""
    ticket = load_ticket(version, ticket_id)
    if not ticket:
        return None
    who = ticket.get("who")
    if not isinstance(who, dict):
        return None
    current = who.get("current")
    if not isinstance(current, str) or not current.strip():
        return None
    return current.strip()


def check_identity(
    version: str,
    ticket_id: str,
    as_value: Optional[str],
    command: str = "(unknown)",
) -> Optional[int]:
    """
    對照申報身份與 ticket who.current，回傳 deny exit code 或 None（放行）。

    判定邏輯（依序，對應 W1-048 規格表；括號為 telemetry result 列舉）：
    1. 未提供 --as            → 僅 stderr 警告，放行（warn，回傳 None）
    2. --as = PM_AGENT_NAME   → 一律放行（exempt；PM bookkeeping 豁免，回傳 None）
    3. --as = who.current     → 放行（pass，回傳 None）
    4. --as != who.current    → deny（含 who.current 空值，回傳 IDENTITY_DENY_EXIT）

    本函式不寫入任何 ticket 狀態（純前置檢查）。所有提示走 stderr，
    避免污染 stdout 消費者。四條路徑均 append telemetry（W1-082：全路徑落盤，
    否則使用率分母缺失不可計算）。

    Args:
        version: 版本號
        ticket_id: Ticket ID
        as_value: --as 旗標值（未提供時為 None）
        command: 觸發守衛的 CLI 命令名稱（telemetry 用；呼叫端未傳時為 "(unknown)"）

    Returns:
        None 表示放行；整數表示 deny 的 exit code（呼叫端應直接 return 此值）。
    """
    # 情境 1：未提供 --as → warn-only（向後相容）
    # 僅 str 且非空才視為「已提供」；None 或非 str（如 Mock args 的 auto-attr、
    # getattr default）皆視為未提供，避免守衛誤觸發於既有 Mock-based 測試與
    # 未升級的呼叫端（argparse --as 恆為 str 或 None，此檢查為防禦性）。
    if not isinstance(as_value, str) or not as_value.strip():
        sys.stderr.write(
            "[identity-guard] 建議帶 --as <agent-name> 申報執行身份"
            "（過渡期不阻擋，向後相容；PC-V1-002 前提一）\n"
        )
        _write_telemetry(
            command=command,
            ticket_id=ticket_id,
            as_value=as_value,
            result=RESULT_WARN,
            caller_type="unknown",
        )
        return None

    # 情境 2：PM 身份豁免
    if as_value == PM_AGENT_NAME:
        _write_telemetry(
            command=command,
            ticket_id=ticket_id,
            as_value=as_value,
            result=RESULT_EXEMPT,
            caller_type="pm",
        )
        return None

    who_current = _resolve_who_current(version, ticket_id)

    # 情境 3：相符放行
    if who_current is not None and as_value == who_current:
        _write_telemetry(
            command=command,
            ticket_id=ticket_id,
            as_value=as_value,
            result=RESULT_PASS,
            caller_type="agent",
        )
        return None

    # 情境 4：不符 deny（含 who.current 空值）
    who_display = who_current if who_current is not None else "(未指派)"
    sys.stderr.write(
        f"[identity-guard] deny：身份 {as_value} 與指派執行者 {who_display} 不符，"
        f"請回報 PM（PC-V1-002 前提一）\n"
    )
    _write_telemetry(
        command=command,
        ticket_id=ticket_id,
        as_value=as_value,
        result=RESULT_DENY,
        caller_type="agent",
    )
    return IDENTITY_DENY_EXIT
