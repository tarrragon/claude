"""
Protocol Version Checker - Library Function

功能：在 ticket 被載入時自動偵測和處理版本遷移
- 檢測 ticket 的 protocol_version 欄位
- 若缺失或格式異常，觸發自動遷移至最新版本
- 記錄遷移過程（雙通道：stderr + 日誌檔）

觸發時機：ticket 載入時（由 ticket_loader.py 或相關模組呼叫）

設計原則：
1. 無條件向前遷移：舊版本 ticket 自動升級至最新版本（無用戶干預）
2. 無資訊遺失：遷移過程 100% 保留原有欄位
3. 可審計：遷移歷史記錄完整，支援事後追蹤

錯誤處理：
- 格式異常（如 "v2.0"）：輸出 WARNING，不阻止操作
- 無遷移路徑：輸出 ERROR，可能阻止操作（取決於呼叫端決定）
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


def log_exception(message: str, error: Exception | None = None) -> None:
    """
    將異常資訊同時輸出到 stderr 和日誌檔（雙通道）。

    Args:
        message: 主要訊息
        error: 可選的異常物件（會附加其詳細資訊）
    """
    full_message = f"[protocol-version-check] {message}"
    if error:
        full_message += f"\nDetails: {str(error)}"

    # 輸出到 stderr（用戶可見）
    print(full_message, file=sys.stderr)

    # 輸出到日誌檔（審計記錄）
    log_file = Path(".claude/hook-logs/protocol-version-check.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(full_message + "\n")
    except Exception as write_err:
        print(f"Failed to write log: {write_err}", file=sys.stderr)


def check_protocol_version(ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    檢查並自動遷移 ticket 的 protocol_version。

    此函式在 ticket 載入時被呼叫，執行以下操作：
    1. 檢測 protocol_version 欄位
    2. 驗證版本格式
    3. 必要時自動遷移至最新版本
    4. 記錄遷移過程

    Args:
        ticket_data: dict，ticket frontmatter 資料

    Returns:
        dict: 遷移後的 ticket 資料（若無需遷移則原樣返回）

    設計決策：
    - 若 protocol_version 缺失，視為 v1.0（舊 ticket）並自動升級
    - 若版本格式異常，輸出 WARNING 但繼續處理（不中斷流程）
    - 若遷移成功，輸出 INFO 級別訊息記錄
    """
    try:
        # 導入遷移模組
        from ticket_system.lib.migrations import (
            migrate_ticket,
            ProtocolVersionError,
        )

        # 檢查是否需要遷移
        current_version = ticket_data.get("protocol_version")

        if current_version is None:
            # 缺失 protocol_version，視為舊 ticket，自動遷移
            log_exception(
                f"Ticket {ticket_data.get('id', 'unknown')} 缺失 protocol_version，"
                "自動遷移至 v2.0"
            )
            ticket_data, migration_history = migrate_ticket(ticket_data)
            if migration_history:
                log_exception(f"遷移成功：{migration_history}")
        else:
            # protocol_version 存在，嘗試遷移（若非最新版本）
            try:
                ticket_data, migration_history = migrate_ticket(ticket_data)
                if migration_history:
                    log_exception(
                        f"Ticket {ticket_data.get('id', 'unknown')} 已遷移：{migration_history}"
                    )
            except ProtocolVersionError as e:
                log_exception(
                    f"Ticket {ticket_data.get('id', 'unknown')} 版本異常",
                    error=e
                )
                # 版本異常時繼續返回原資料（不中斷操作）

    except ImportError as e:
        log_exception("無法載入 migrations 模組", error=e)
    except Exception as e:
        log_exception("遷移過程中發生異常", error=e)

    return ticket_data
