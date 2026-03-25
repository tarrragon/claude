"""
Ticket audit-version 子命令實作

負責掃描並驗證 Ticket 版本歸屬一致性。
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
    print("  ticket track audit-version")
    print("  ticket track audit-version --fix")
    print("  ticket track audit-version --version 0.1.0")
    print()
    print("如尚未安裝，請執行：")
    print("  cd .claude/skills/ticket && uv tool install .")
    print()
    print("詳見 SKILL.md")
    print(SEPARATOR_PRIMARY)
    sys.exit(1)


import argparse
import sys
from pathlib import Path
from typing import List

from ticket_system.lib.audit_version import (
    scan_all_tickets,
    detect_mismatches,
    detect_duplicates,
    VersionMismatch,
    DuplicateTicket,
)
from ticket_system.lib.messages import format_error, format_info
from ticket_system.lib.ui_constants import SEPARATOR_CHAR, SEPARATOR_WIDTH
from ticket_system.lib.command_tracking_messages import (
    AuditVersionMessages,
)


# ============================================================================
# 格式化工具函式
# ============================================================================

def _format_separator() -> str:
    """建立分隔線"""
    return SEPARATOR_CHAR * SEPARATOR_WIDTH


def _format_version_audit_report(
    mismatches: List[VersionMismatch],
    duplicates: List[DuplicateTicket],
    total_tickets: int,
) -> str:
    """
    格式化版本審計報告

    Args:
        mismatches: 發現的版本不一致清單
        duplicates: 發現的重複 Ticket 清單
        total_tickets: 掃描的總 Ticket 數

    Returns:
        格式化後的報告字串
    """
    lines = []
    separator = _format_separator()

    # 標題
    lines.append(separator)
    lines.append(AuditVersionMessages.AUDIT_REPORT_TITLE)
    lines.append(separator)
    lines.append("")

    # 統計摘要
    issue_count = len(mismatches) + len(duplicates)
    if issue_count == 0:
        lines.append(AuditVersionMessages.AUDIT_PASSED.format(total=total_tickets))
        lines.append("")
    else:
        lines.append(AuditVersionMessages.AUDIT_FOUND_ISSUES.format(
            issues=issue_count,
            mismatches=len(mismatches),
            duplicates=len(duplicates),
        ))
        lines.append("")

    # 版本不一致部分
    if mismatches:
        lines.append(AuditVersionMessages.SECTION_MISMATCHES)
        lines.append("")

        for mismatch in mismatches:
            ticket_info = mismatch.ticket_info
            lines.append(AuditVersionMessages.MISMATCH_ITEM.format(
                ticket_id=ticket_info.ticket_id,
            ))

            # 根據不一致類型顯示詳細資訊
            if mismatch.mismatch_type == "id_vs_directory":
                lines.append(AuditVersionMessages.MISMATCH_ID_VERSION.format(
                    version=ticket_info.id_version,
                ))
                lines.append(AuditVersionMessages.MISMATCH_DIR_VERSION.format(
                    version=ticket_info.directory_version,
                ))
                lines.append(AuditVersionMessages.FIX_SUGGESTION_MOVE.format(
                    old_version=ticket_info.id_version,
                    new_version=ticket_info.directory_version,
                ))
            elif mismatch.mismatch_type == "frontmatter_vs_directory":
                lines.append(AuditVersionMessages.MISMATCH_FRONTMATTER_VERSION.format(
                    version=ticket_info.frontmatter_version,
                ))
                lines.append(AuditVersionMessages.MISMATCH_DIR_VERSION.format(
                    version=ticket_info.directory_version,
                ))
                lines.append(AuditVersionMessages.FIX_SUGGESTION_FRONTMATTER.format(
                    version=ticket_info.directory_version,
                ))
            elif mismatch.mismatch_type == "id_vs_frontmatter":
                lines.append(AuditVersionMessages.MISMATCH_ID_VERSION.format(
                    version=ticket_info.id_version,
                ))
                lines.append(AuditVersionMessages.MISMATCH_FRONTMATTER_VERSION.format(
                    version=ticket_info.frontmatter_version,
                ))
                lines.append(AuditVersionMessages.FIX_SUGGESTION_FRONTMATTER.format(
                    version=ticket_info.directory_version,
                ))

            lines.append(f"  檔案: {ticket_info.file_path}")
            lines.append("")

    # 重複 Ticket 部分
    if duplicates:
        lines.append(AuditVersionMessages.SECTION_DUPLICATES)
        lines.append("")

        for dup in duplicates:
            lines.append(AuditVersionMessages.DUPLICATE_ITEM.format(
                ticket_id=dup.ticket_id,
            ))

            for location in dup.locations:
                status = "✓ 正確" if location.directory_version == dup.recommended_version else "✗ 錯誤"
                lines.append(f"  {status}: {location.file_path}")

            lines.append(AuditVersionMessages.DUPLICATE_SUGGESTION.format(
                recommended_version=dup.recommended_version,
            ))
            lines.append("")

    # 結論
    lines.append(separator)
    if issue_count == 0:
        lines.append(AuditVersionMessages.CONCLUSION_PASS)
    else:
        lines.append(AuditVersionMessages.CONCLUSION_FAIL.format(
            issues=issue_count,
        ))
    lines.append(separator)

    return "\n".join(lines)


# ============================================================================
# 修復操作
# ============================================================================

def _fix_mismatches(mismatches: List[VersionMismatch]) -> int:
    """
    修復版本不一致

    Args:
        mismatches: 版本不一致清單

    Returns:
        0: 成功, 1: 有失敗
    """
    success_count = 0
    fail_count = 0

    for mismatch in mismatches:
        ticket_info = mismatch.ticket_info
        file_path = Path(ticket_info.file_path)

        if mismatch.mismatch_type == "frontmatter_vs_directory":
            # 修正 frontmatter 中的 version 欄位
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 簡單的 YAML 替換（假設 version: 在單獨一行）
                old_line = f"version: {ticket_info.frontmatter_version}"
                new_line = f"version: {mismatch.expected_version}"
                new_content = content.replace(old_line, new_line)

                if new_content == content:
                    print(f"[SKIP] {ticket_info.ticket_id}: 找不到 frontmatter 版本行")
                    fail_count += 1
                    continue

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                print(f"[FIXED] {ticket_info.ticket_id}: 更新 frontmatter version 為 {mismatch.expected_version}")
                success_count += 1

            except Exception as e:
                print(format_error(f"修復 {ticket_info.ticket_id} 失敗: {str(e)}"))
                fail_count += 1

        elif mismatch.mismatch_type == "id_vs_directory":
            # Ticket ID 和目錄版本不一致
            # 需要透過 git mv 搬移檔案（不在此實作，只提示）
            print(f"[INFO] {ticket_info.ticket_id}: 需要搬移檔案（手動操作）")
            print(f"       從 v{ticket_info.id_version} 搬移到 v{mismatch.expected_version}")

    return 0 if fail_count == 0 else 1


def _fix_duplicates(duplicates: List[DuplicateTicket]) -> int:
    """
    修復重複 Ticket

    Args:
        duplicates: 重複 Ticket 清單

    Returns:
        0: 成功, 1: 有失敗
    """
    success_count = 0
    fail_count = 0

    for dup in duplicates:
        # 找到不在建議版本的重複檔案並刪除
        for location in dup.locations:
            if location.directory_version != dup.recommended_version:
                file_path = Path(location.file_path)
                try:
                    if file_path.exists():
                        file_path.unlink()
                        print(f"[DELETED] {file_path}")
                        success_count += 1
                    else:
                        print(f"[SKIP] {file_path}: 檔案不存在")
                except Exception as e:
                    print(format_error(f"刪除 {file_path} 失敗: {str(e)}"))
                    fail_count += 1

    return 0 if fail_count == 0 else 1


# ============================================================================
# 主命令處理函式
# ============================================================================

def execute_audit_version(args: argparse.Namespace, version: str) -> int:
    """
    執行 audit-version 命令

    Args:
        args: 命令行參數
        version: 版本號（未使用，保持簽名一致）

    Returns:
        0: 檢查通過或修復成功
        1: 檢查失敗或修復有失敗
    """
    try:
        is_dry_run = not args.fix
        target_version = getattr(args, 'audit_version', None)

        # 掃描所有 Ticket
        print(AuditVersionMessages.SCANNING_TICKETS)
        all_tickets = scan_all_tickets()

        # 過濾特定版本（如指定了 --version）
        if target_version:
            tickets = [t for t in all_tickets if t.directory_version == target_version]
            print(AuditVersionMessages.FILTERED_VERSION.format(
                total=len(all_tickets),
                version=target_version,
                filtered=len(tickets),
            ))
        else:
            tickets = all_tickets

        # 偵測不一致和重複
        mismatches = detect_mismatches(tickets)
        duplicates = detect_duplicates(tickets)

        # 輸出報告
        report = _format_version_audit_report(mismatches, duplicates, len(tickets))
        print(report)

        # 如果有問題且指定了 --fix，進行修復
        if (mismatches or duplicates) and args.fix:
            print("")
            print(AuditVersionMessages.FIXING_ISSUES)
            print("")

            # 修復不一致
            if mismatches:
                result = _fix_mismatches(mismatches)
                if result != 0:
                    return 1

            # 修復重複
            if duplicates:
                result = _fix_duplicates(duplicates)
                if result != 0:
                    return 1

            print("")
            print(AuditVersionMessages.FIX_COMPLETED)

        # 檢查結果
        if mismatches or duplicates:
            return 1
        else:
            return 0

    except Exception as e:
        print(format_error(f"審計失敗: {str(e)}"))
        return 1


__all__ = [
    "execute_audit_version",
]
