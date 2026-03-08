"""
Ticket audit 子命令實作

負責執行驗收檢查並輸出報告。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    import sys
    from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY
    print(SEPARATOR_PRIMARY)
    print("[ERROR] 此檔案不支援直接執行")
    print(SEPARATOR_PRIMARY)
    print()
    print("正確使用方式：")
    print("  ticket track audit <ticket-id>")
    print()
    print("如尚未安裝，請執行：")
    print("  cd .claude/skills/ticket && uv tool install .")
    print()
    print("詳見 SKILL.md")
    print(SEPARATOR_PRIMARY)
    sys.exit(1)


import argparse
from typing import Optional

from ticket_system.lib.acceptance_auditor import run_audit
from ticket_system.lib.messages import format_error, format_info
from ticket_system.lib.ui_constants import SEPARATOR_CHAR, SEPARATOR_WIDTH, SEPARATOR_PRIMARY
from ticket_system.lib.command_tracking_messages import (
    TrackAuditMessages,
    format_msg,
)


def _format_audit_report(report) -> str:
    """
    格式化驗收報告為易讀的輸出格式

    Returns:
        格式化後的報告字串
    """
    lines = []

    # 建立分隔線
    separator = SEPARATOR_CHAR * SEPARATOR_WIDTH

    # 標題
    lines.append(separator)
    lines.append(TrackAuditMessages.AUDIT_REPORT_TITLE)
    lines.append(separator)
    lines.append("")

    # 基本資訊
    lines.append(f"{TrackAuditMessages.AUDIT_TICKET_PREFIX} {report.ticket_id} - {report.title}")
    lines.append(f"{TrackAuditMessages.AUDIT_TIME_PREFIX} {report.timestamp}")
    lines.append(f"{TrackAuditMessages.AUDIT_AUDITOR_PREFIX} {TrackAuditMessages.AUDIT_AUDITOR_NAME}")
    lines.append("")

    # 檢查結果表格
    lines.append(f"{TrackAuditMessages.AUDIT_RESULTS_TITLE}")
    lines.append("")
    lines.append(TrackAuditMessages.AUDIT_TABLE_HEADER_STEP)
    lines.append(TrackAuditMessages.AUDIT_TABLE_SEPARATOR)

    for step in report.steps:
        status = step.get_status_label()

        # 準備說明文字
        if step.skipped:
            description = TrackAuditMessages.AUDIT_DESCRIPTION_SKIPPED
        elif step.passed and not step.warnings:
            description = TrackAuditMessages.AUDIT_DESCRIPTION_PASSED
        elif step.passed and step.warnings:
            description = format_msg(TrackAuditMessages.AUDIT_DESCRIPTION_PASSED_WITH_WARNINGS, count=len(step.warnings))
        else:
            description = format_msg(TrackAuditMessages.AUDIT_DESCRIPTION_FAILED, issue=step.issues[0] if step.issues else '失敗')

        lines.append(f"| {step.name} | {status} | {description} |")

    lines.append("")

    # 結論
    lines.append(f"{TrackAuditMessages.AUDIT_CONCLUSION_TITLE}")
    lines.append(f"{TrackAuditMessages.AUDIT_RESULT_PREFIX} {report.get_result_label()}")

    if not report.overall_passed:
        # 列出失敗項
        failed = report.get_failed_steps()
        if failed:
            lines.append("")
            lines.append(f"{TrackAuditMessages.AUDIT_FAILED_TITLE}")
            for step in failed:
                for issue in step.issues:
                    lines.append(format_msg(TrackAuditMessages.AUDIT_FAILED_ITEM_FORMAT, step=step.name, issue=issue))

    # 列出警告項
    warnings = report.get_warning_steps()
    if warnings:
        lines.append("")
        lines.append(f"{TrackAuditMessages.AUDIT_WARNINGS_TITLE}")
        for step in warnings:
            for warning in step.warnings:
                lines.append(format_msg(TrackAuditMessages.AUDIT_WARNING_ITEM_FORMAT, step=step.name, warning=warning))

    lines.append("")
    lines.append(separator)

    return "\n".join(lines)


def execute_audit(args: argparse.Namespace, version: str) -> int:
    """
    執行 audit 命令

    Args:
        args: 命令行參數
        version: 版本號

    Returns:
        0: 驗收通過
        1: 驗收失敗或發生錯誤
    """
    ticket_id = args.ticket_id

    try:
        # 執行驗收檢查
        report = run_audit(ticket_id, version)

        # 輸出報告
        print(_format_audit_report(report))

        # 根據結果返回狀態碼
        if report.overall_passed:
            return 0
        else:
            return 1

    except ValueError as e:
        print(format_error(f"{TrackAuditMessages.AUDIT_CHECK_FAILED_PREFIX}{str(e)}"))
        return 1
    except Exception as e:
        print(format_error(f"{TrackAuditMessages.AUDIT_PROCESS_ERROR_PREFIX}{str(e)}"))
        return 1


__all__ = [
    "execute_audit",
]
