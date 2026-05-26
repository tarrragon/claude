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
# W17-163 L1-A: 改用 is_handoff_stale 統一 stale 判定（消除 ARCH-020 同構）
# 歷史背景：handoff_gc 原獨立重寫 stale 判定邏輯，與 handoff_utils 漂移；
# W10-047.4 漏判（direction=to-source + from_status="in_progress" 走非任務鏈分支
# 但 from_status != "completed" 即不標 stale）即此漂移之直接成因。
# 本次改 delegate 到 is_handoff_stale，三套消費者共用單一判定函式。
from ticket_system.lib.handoff_utils import (
    is_handoff_stale,
    is_ticket_completed,
    scan_pending_handoffs,
)


def _collect_stale_handoffs(force: bool = False) -> List[Tuple[Path, str, str]]:
    """
    掃描 pending/ 目錄，收集所有 stale handoff 檔案。

    Stale 判斷 delegate 至 handoff_utils.is_handoff_stale（W17-163 L1-A，
    消除 ARCH-020 跨進程重複邏輯）。判定規則詳見該函式 docstring。

    Markdown 格式 handoff 因無 direction 資訊，沿用原行為：
    來源 ticket 已 completed 即視為 stale。

    Args:
        force: True 時跳過 task-chain 保護（is_handoff_stale），改用
               is_ticket_completed(source_ticket) 統一判定；False 時保持
               現有行為（向後相容）。W3-018.2 新增。

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

            if force:
                # W3-018.2: --force 模式跳過 task-chain 保護，
                # 來源 ticket 已 completed 即視為 stale
                if is_ticket_completed(ticket_id):
                    reason = (
                        f"來源 ticket {ticket_id} 已完成 "
                        f"(--force 模式跳過 task-chain 保護)"
                    )
                    stale.append((record.file_path, ticket_id, reason))
            else:
                # W17-163 L1-A: delegate 至 is_handoff_stale（單一 stale 判定來源）
                is_stale, reason = is_handoff_stale(record.data)
                if is_stale:
                    stale.append((record.file_path, ticket_id, reason))

        elif record.format == "markdown":
            # Markdown 格式無 direction 資訊，沿用原行為：
            # 來源 ticket 已 completed → stale（不受 force 影響）
            ticket_id = record.ticket_id
            if ticket_id and is_ticket_completed(ticket_id):
                reason = f"來源 ticket {ticket_id} 已完成（Markdown 格式）"
                stale.append((record.file_path, ticket_id, reason))

    return stale


def execute_gc(dry_run: bool = True, force: bool = False) -> int:
    """
    執行 handoff GC 清理。

    Args:
        dry_run: True 時僅預覽，False 時實際移動至 archive/
        force: True 時跳過 task-chain 保護（W3-018.2）

    Returns:
        int: 退出碼（0 成功）
    """
    stale = _collect_stale_handoffs(force=force)

    if not stale:
        print("[GC] 無 stale handoff，pending 目錄已清潔。")
        return 0

    root = get_project_root()
    archive_dir = root / HANDOFF_DIR / HANDOFF_ARCHIVE_SUBDIR

    mode = "[DRY-RUN]" if dry_run else "[執行]"
    force_tag = " [--force]" if force else ""
    print(f"{mode}{force_tag} 發現 {len(stale)} 個 stale handoff：")
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
