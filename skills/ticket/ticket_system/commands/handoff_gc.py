"""
Handoff GC（垃圾清理）命令模組

掃描 pending/ 目錄，識別並清理 stale handoff 檔案。
Stale handoff：來源 ticket 已 completed 且非任務鏈交接，或任務鏈目標已啟動。

支援 --dry-run（預覽）和 --execute（執行移動至 archive/）。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()


from pathlib import Path
from typing import List, Tuple

from ticket_system.lib.constants import (
    HANDOFF_DIR,
    HANDOFF_ARCHIVE_SUBDIR,
)
from ticket_system.lib.paths import get_project_root

# 共用的掃描和判斷函式
from ticket_system.lib.handoff_utils import (
    extract_direction_target_id,
    is_ticket_completed,
    is_task_chain_direction,
    is_ticket_in_progress_or_completed,
    scan_pending_handoffs,
)


def _collect_stale_handoffs() -> List[Tuple[Path, str, str]]:
    """
    掃描 pending/ 目錄，收集所有 stale handoff 檔案。

    Stale 判斷規則（與 list_pending_handoffs() 一致）：
    1. 來源 ticket 已 completed
    2. 且：
       - JSON 檔：檢查 direction 和 from_status 欄位
       - Markdown 檔：直接認定為 stale（因無法提取 direction 資訊）
       - 非任務鏈（context-refresh 等）：from_status != "completed"
       - 任務鏈（to-sibling/to-parent/to-child）：目標已 in_progress/completed

    使用共用的 scan_pending_handoffs() 函式進行掃描，避免重複邏輯。

    Returns:
        List of (file_path, ticket_id, reason) tuples
    """
    records = scan_pending_handoffs()
    stale = []

    for record in records:
        # 跳過解析/格式錯誤的檔案（不算 stale，保留作除錯用）
        if record.parse_error or record.schema_error:
            continue

        if record.format == "json":
            ticket_id = record.ticket_id
            if not ticket_id:
                continue

            if not is_ticket_completed(ticket_id):
                continue  # 來源 ticket 未完成，保留

            direction = record.direction
            from_status = record.from_status

            if is_task_chain_direction(direction):
                # 任務鏈：只有目標已啟動才算 stale
                target_id = extract_direction_target_id(direction)
                if target_id and is_ticket_in_progress_or_completed(target_id):
                    reason = f"任務鏈目標 {target_id} 已啟動"
                    stale.append((record.file_path, ticket_id, reason))
                # 無 target_id 或目標未啟動：不算 stale
            else:
                # 非任務鏈（context-refresh 等）：from_status != "completed" 才 stale
                if from_status != "completed":
                    reason = f"來源 ticket {ticket_id} 已完成（direction: {direction}）"
                    stale.append((record.file_path, ticket_id, reason))

        elif record.format == "markdown":
            # Markdown 格式的 handoff 檔案
            ticket_id = record.ticket_id

            # Markdown 格式無 direction 資訊，保持原行為
            if ticket_id and is_ticket_completed(ticket_id):
                reason = f"來源 ticket {ticket_id} 已完成（Markdown 格式）"
                stale.append((record.file_path, ticket_id, reason))

    return stale


def execute_gc(dry_run: bool = True) -> int:
    """
    執行 handoff GC 清理。

    Args:
        dry_run: True 時僅預覽，False 時實際移動至 archive/

    Returns:
        int: 退出碼（0 成功）
    """
    stale = _collect_stale_handoffs()

    if not stale:
        print("[GC] 無 stale handoff，pending 目錄已清潔。")
        return 0

    root = get_project_root()
    archive_dir = root / HANDOFF_DIR / HANDOFF_ARCHIVE_SUBDIR

    mode = "[DRY-RUN]" if dry_run else "[執行]"
    print(f"{mode} 發現 {len(stale)} 個 stale handoff：")
    print()

    for file_path, ticket_id, reason in stale:
        print(f"  - {file_path.name}")
        print(f"    原因：{reason}")
        if not dry_run:
            archive_dir.mkdir(parents=True, exist_ok=True)
            dest = archive_dir / file_path.name
            file_path.rename(dest)
            print(f"    已移動至：{dest.relative_to(root)}")
    print()

    if dry_run:
        print(f"[DRY-RUN] 使用 --execute 實際執行清理")
    else:
        print(f"[GC] 已清理 {len(stale)} 個 stale handoff（移至 {HANDOFF_ARCHIVE_SUBDIR}/）")

    return 0
