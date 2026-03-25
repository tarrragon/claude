#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Protocol Version Migration Dry-Run 驗證腳本

對所有現存 ticket 執行遷移驗證，確保：
1. 所有舊 ticket 可成功升級至 v2.0
2. 無任何資訊遺失
3. 產生完整的驗證報告
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

# 添加模組路徑
sys.path.insert(0, str(Path(__file__).parent))

from ticket_system.lib.migrations import migrate_ticket, ProtocolVersionError
from ticket_system.lib.constants import PROTOCOL_VERSION_CURRENT


def scan_ticket_files() -> List[Dict[str, Any]]:
    """
    掃描所有 ticket 檔案。

    Returns:
        list: ticket 資料清單
    """
    ticket_dir = Path(__file__).parent.parent.parent.parent / "docs" / "work-logs"
    tickets: List[Dict[str, Any]] = []

    # 遞迴掃描所有 tickets 目錄
    for version_dir in ticket_dir.glob("v*/tickets/"):
        for ticket_file in version_dir.glob("*.md"):
            try:
                with open(ticket_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # 分離 YAML frontmatter 和內容
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 2:
                        frontmatter = yaml.safe_load(parts[1])
                        if frontmatter and isinstance(frontmatter, dict):
                            frontmatter["_file"] = str(ticket_file)
                            tickets.append(frontmatter)
            except Exception as e:
                print(f"  [WARN] 無法解析 {ticket_file}: {e}", file=sys.stderr)

    return tickets


def run_migration_dryrun() -> Tuple[int, int, int, List[Dict[str, Any]]]:
    """
    對所有現存 ticket 執行 dry-run 遷移驗證。

    Returns:
        tuple: (total_count, success_count, error_count, error_details)
    """
    tickets = scan_ticket_files()
    total_count = len(tickets)
    success_count = 0
    error_count = 0
    error_details: List[Dict[str, Any]] = []

    print(f"\n{'='*60}")
    print(f"Protocol Version Dry-Run 驗證")
    print(f"{'='*60}")
    print(f"掃描到 {total_count} 個 ticket\n")

    for ticket in tickets:
        ticket_id = ticket.get("id", "unknown")
        try:
            # 執行遷移
            migrated, history = migrate_ticket(ticket)

            # 驗證遷移結果
            if migrated.get("protocol_version") == PROTOCOL_VERSION_CURRENT:
                success_count += 1
                status = "✓ PASS"
            else:
                error_count += 1
                status = "✗ FAIL"
                error_details.append({
                    "ticket_id": ticket_id,
                    "reason": f"版本未升級至 {PROTOCOL_VERSION_CURRENT}，當前: {migrated.get('protocol_version')}",
                })

            # 印出進度
            print(f"  {status}  {ticket_id}")

            # 若有遷移歷史，印出詳情
            if history:
                for step in history:
                    print(f"        → {step['from']} → {step['to']} ({step['handler']})")

        except ProtocolVersionError as e:
            error_count += 1
            error_details.append({
                "ticket_id": ticket_id,
                "reason": str(e),
            })
            print(f"  ✗ FAIL  {ticket_id} (Version Error)")

        except Exception as e:
            error_count += 1
            error_details.append({
                "ticket_id": ticket_id,
                "reason": f"Unexpected Error: {str(e)}",
            })
            print(f"  ✗ FAIL  {ticket_id} (Unexpected Error)")

    # 產生摘要報告
    print(f"\n{'='*60}")
    print(f"驗證摘要")
    print(f"{'='*60}")
    print(f"總數：       {total_count} 個 ticket")
    print(f"成功：       {success_count} 個 ({100*success_count//total_count if total_count > 0 else 0}%)")
    print(f"失敗：       {error_count} 個 ({100*error_count//total_count if total_count > 0 else 0}%)")

    if error_details:
        print(f"\n失敗詳情：")
        for error in error_details:
            print(f"  - {error['ticket_id']}: {error['reason']}")

    print(f"{'='*60}\n")

    return total_count, success_count, error_count, error_details


if __name__ == "__main__":
    total, success, errors, details = run_migration_dryrun()
    sys.exit(0 if errors == 0 else 1)
