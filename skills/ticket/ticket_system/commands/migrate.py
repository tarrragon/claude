"""
Ticket 遷移命令模組

負責 Ticket ID 遷移功能，支援單一 Ticket 遷移和批量遷移。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()



import argparse
import json
import re
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from ticket_system.constants import MAX_TICKET_DEPTH
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY
from ticket_system.lib.constants import WORK_LOGS_DIR, TICKETS_DIR
from ticket_system.lib.ticket_loader import (
    get_ticket_path,
    get_tickets_dir,
    load_ticket,
    save_ticket,
    resolve_version,
)
from ticket_system.lib.paths import get_ticket_state_root
from ticket_system.lib.parser import parse_frontmatter
from ticket_system.lib.ticket_validator import validate_ticket_id
from ticket_system.lib.id_parser import (
    extract_id_components,
    extract_core_ticket_id,
    parse_sequence,
    format_sequence,
    calculate_chain_info,
)
from ticket_system.lib.messages import (
    ErrorMessages,
    MigrationMessages,
    WarningMessages,
    InfoMessages,
    format_error,
    format_warning,
    format_info,
)
from ticket_system.lib.command_tracking_messages import (
    MigrateMessages,
)
from ticket_system.lib.ticket_ops import (
    load_and_validate_ticket,
)
from ticket_system.lib.git_utils import (
    EXIT_AUTO_COMMIT_FAILED,
    commit_ticket_mds_reporting,
)
from ticket_system.lib.topic_assignments import (
    assignments_file_path,
    inherit_assignment,
)

# 被遷移票記錄「曾用 ID」的欄位名（由舊到新的有序清單）。與 migrated_from 語意不同：
# migrated_from 是撞號改號前的原目標；本欄位是票自己走過的 ID，長度即遷移（前移）次數。
PREVIOUS_IDS_FIELD = "previous_ids"


@dataclass
class _MigrationRecord:
    """一次成功遷移寫入工作區的檔案集合，供呼叫端併成單一提交。"""

    old_id: str
    new_id: str
    target_path: Path
    source_path: Path
    referrers: List[Path] = field(default_factory=list)
    topic_line: Optional[str] = None
    # 有子孫的票連帶遷移時，根票 record 帶其餘成員的 record（與根票併成同一提交）
    subtree: List["_MigrationRecord"] = field(default_factory=list)


def _update_ticket_id_references(ticket: Dict[str, Any], old_id: str, new_id: str) -> None:
    """
    更新 Ticket 中所有對舊 ID 的引用

    Args:
        ticket: Ticket 資料
        old_id: 舊 Ticket ID
        new_id: 新 Ticket ID
    """
    # 更新 blockedBy 引用（list of string）
    if "blockedBy" in ticket and ticket["blockedBy"]:
        ticket["blockedBy"] = [new_id if ref == old_id else ref for ref in ticket["blockedBy"]]

    # 更新 relatedTo 引用（list of string）
    if "relatedTo" in ticket and ticket["relatedTo"]:
        ticket["relatedTo"] = [new_id if ref == old_id else ref for ref in ticket["relatedTo"]]

    # 更新 spawned_tickets 引用（list of string）
    if "spawned_tickets" in ticket and ticket["spawned_tickets"]:
        ticket["spawned_tickets"] = [
            new_id if ref == old_id else ref for ref in ticket["spawned_tickets"]
        ]

    # 更新 children 中的 ID（同時支援 string 與 dict 兩種形式，與 _update_cross_references 一致）
    if "children" in ticket and ticket["children"]:
        new_children = []
        for child in ticket["children"]:
            if isinstance(child, str):
                new_children.append(new_id if child == old_id else child)
            elif isinstance(child, dict):
                if child.get("id") == old_id:
                    child["id"] = new_id
                new_children.append(child)
            else:
                new_children.append(child)
        ticket["children"] = new_children

    # 更新 source_ticket（scalar string）
    if "source_ticket" in ticket and ticket["source_ticket"] == old_id:
        ticket["source_ticket"] = new_id

    # 更新 parent_id（scalar string）
    if "parent_id" in ticket and ticket["parent_id"] == old_id:
        ticket["parent_id"] = new_id


def _replace_scalar_or_list_ref(value: Any, old_id: str, new_id: str):
    """替換字串或字串清單欄位中的舊 ID，回傳 (新值, 是否變更)。"""
    if value == old_id:
        return new_id, True
    if isinstance(value, list) and old_id in value:
        return [new_id if ref == old_id else ref for ref in value], True
    return value, False


def _rewrite_extra_structural_refs(ticket: Dict[str, Any], old_id: str, new_id: str) -> bool:
    """改寫 discovered_during、closed_by 與 chain.root／chain.parent 中的舊 ID。"""
    updated = False
    for key in ("discovered_during", "closed_by"):
        if key in ticket:
            ticket[key], changed = _replace_scalar_or_list_ref(ticket[key], old_id, new_id)
            updated = updated or changed
    chain = ticket.get("chain")
    if isinstance(chain, dict):
        for key in ("root", "parent"):
            if chain.get(key) == old_id:
                chain[key] = new_id
                updated = True
    return updated


def _update_cross_references(old_id: str, new_id: str) -> int:
    """更新交叉引用並回傳更新的檔案數（相容舊介面，實作見 collecting 版）。"""
    return len(_update_cross_references_collecting(old_id, new_id))


def _update_cross_references_collecting(old_id: str, new_id: str) -> List[Path]:
    """
    搜尋所有 Ticket 文件並更新對舊 ID 的交叉引用

    掃描所有版本目錄下的 tickets 資料夾，查找並更新以下欄位中
    對舊 ID 的引用：
    - blockedBy: 阻塞依賴列表
    - relatedTo: 相關 Ticket 列表
    - children: 子 Ticket 列表（支援字串和 dict 形式）
    - source_ticket: 來源 Ticket
    - parent_id: 父 Ticket ID
    - spawned_tickets: 衍生 Ticket 列表
    - discovered_during、closed_by: 發現來源與關閉來源
    - chain.root、chain.parent: 子孫的任務鏈位置

    Args:
        old_id: 舊 Ticket ID
        new_id: 新 Ticket ID

    Returns:
        List[Path]: 實際更新（已寫入）的檔案路徑
    """
    updated_paths: List[Path] = []
    # 根目錄改用 get_ticket_state_root()（非 get_project_root()，2026-09-02）：
    # 掃描對象是所有版本的 ticket 檔案（ticket 狀態），linked worktree 內
    # 執行時必須統一解析主倉庫，理由見 get_ticket_state_root docstring。
    work_logs_root = get_ticket_state_root() / "docs" / "work-logs"

    # 掃描所有版本目錄下的 tickets 資料夾
    # 支援 flat (v{ver}/tickets) 與三層 (v{major}/v{major.minor}/v{ver}/tickets)
    flat_dirs = list(work_logs_root.glob("v*/tickets"))
    hierarchical_dirs = list(work_logs_root.glob("v*/v*/v*/tickets"))
    for tickets_dir in sorted(set(flat_dirs + hierarchical_dirs)):
        for ticket_file in sorted(tickets_dir.glob("*.md")):
            # 跳過剛遷移的 Ticket 本身（來源：0.18.0-W10-037 Bug 2）
            # 原本使用 startswith 會誤跳過子 Ticket（檔名以 new_id 開頭），
            # 導致它們的 blockedBy / parent_id / relatedTo 等引用不被更新。
            # 改用 extract_core_ticket_id 取得核心 ID 做精確比較，
            # 僅跳過「確實等於 new_id 的那個檔案」，子任務與帶後綴檔案都會被掃描。
            core_id = extract_core_ticket_id(ticket_file.stem)
            if core_id == new_id:
                continue

            # 載入 Ticket
            ticket = _load_ticket_from_path(ticket_file)
            if not ticket:
                continue

            # 檢查是否包含舊 ID 的引用
            updated = False

            # 更新 blockedBy
            if "blockedBy" in ticket and ticket.get("blockedBy"):
                if isinstance(ticket["blockedBy"], list):
                    for i, ref in enumerate(ticket["blockedBy"]):
                        if ref == old_id:
                            ticket["blockedBy"][i] = new_id
                            updated = True

            # 更新 relatedTo
            if "relatedTo" in ticket and ticket.get("relatedTo"):
                if isinstance(ticket["relatedTo"], list):
                    for i, ref in enumerate(ticket["relatedTo"]):
                        if ref == old_id:
                            ticket["relatedTo"][i] = new_id
                            updated = True

            # 更新 children（支援字串和 dict 形式）
            if "children" in ticket and ticket.get("children"):
                if isinstance(ticket["children"], list):
                    for i, child in enumerate(ticket["children"]):
                        if isinstance(child, str) and child == old_id:
                            ticket["children"][i] = new_id
                            updated = True
                        elif isinstance(child, dict) and child.get("id") == old_id:
                            child["id"] = new_id
                            updated = True

            # 更新 source_ticket
            if "source_ticket" in ticket and ticket.get("source_ticket") == old_id:
                ticket["source_ticket"] = new_id
                updated = True

            # 更新 parent_id
            if "parent_id" in ticket and ticket.get("parent_id") == old_id:
                ticket["parent_id"] = new_id
                updated = True

            # 更新 spawned_tickets
            if "spawned_tickets" in ticket and ticket.get("spawned_tickets"):
                if isinstance(ticket["spawned_tickets"], list):
                    for i, ref in enumerate(ticket["spawned_tickets"]):
                        if ref == old_id:
                            ticket["spawned_tickets"][i] = new_id
                            updated = True

            if _rewrite_extra_structural_refs(ticket, old_id, new_id):
                updated = True

            # 儲存修改
            if updated:
                try:
                    save_ticket(ticket, ticket_file)
                    updated_paths.append(ticket_file)
                except (IOError, OSError) as e:
                    print(format_warning(
                        WarningMessages.FILE_UPDATE_FAILED,
                        path=str(ticket_file),
                        error=str(e)
                    ))

    return updated_paths


def _load_ticket_from_path(ticket_path: Path) -> Optional[Dict[str, Any]]:
    """
    從檔案路徑載入 Ticket

    Args:
        ticket_path: Ticket 檔案路徑

    Returns:
        Dict: Ticket 資料，或 None 如果載入失敗
    """
    if not ticket_path.exists():
        return None

    try:
        with open(ticket_path, "r", encoding="utf-8") as f:
            content = f.read()
        # parse_frontmatter 返回 (frontmatter_dict, body_text)
        # W4-025：保留 body 至 ticket["_body"]，否則 save_ticket 寫回時
        # body 預設空字串 → 截斷被引用 ticket 的整個 Execution Log（資料損壞）
        ticket, body = parse_frontmatter(content)
        if ticket:
            ticket["_body"] = body
        return ticket if ticket else None
    except Exception:
        # 捕獲所有異常，包括 YAMLParseError 和其他解析錯誤
        # 無法載入的檔案將被跳過，不影響整個遷移流程
        return None


def _backup_ticket(version: str, ticket_id: str) -> Optional[Path]:
    """
    備份 Ticket 檔案

    Args:
        version: 版本號
        ticket_id: Ticket ID

    Returns:
        Path: 備份檔案路徑，或 None 如果備份失敗
    """
    # 根目錄改用 get_ticket_state_root()（非 get_project_root()，2026-09-02）：
    # 備份目錄是 ticket 狀態的附屬產物，理由同上（見 get_ticket_state_root
    # docstring）。
    root = get_ticket_state_root()
    backup_dir = root / ".claude" / "migration-backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    original_path = get_ticket_path(version, ticket_id)
    if not original_path.exists():
        return None

    backup_path = backup_dir / original_path.name
    try:
        shutil.copy2(original_path, backup_path)
        return backup_path
    except (IOError, OSError) as e:
        print(format_warning(WarningMessages.BACKUP_FAILED, error=str(e)))
        return None


def _check_target_collision(target_id: str, version: str) -> Optional[Dict[str, Any]]:
    """
    檢查目標 ID 是否與既有 Ticket 撞檔（W14-048 collision detection）。

    Args:
        target_id: 目標 Ticket ID
        version: fallback 版本號（若 target_id 無法解析版本時使用）

    Returns:
        Dict 包含 path/title/status；若無 collision 則回傳 None。
    """
    target_components = extract_id_components(target_id)
    target_version = target_components["version"] if target_components else version
    target_path = get_ticket_path(target_version, target_id)

    if not target_path.exists():
        return None

    existing = _load_ticket_from_path(target_path)
    return {
        "path": target_path,
        "title": (existing or {}).get("title", "N/A"),
        "status": (existing or {}).get("status", "N/A"),
    }


def _increment_sequence_str(sequence_str: str) -> str:
    """
    將序號字串（可含點號）最末一段遞增 1，保留原有補零寬度。

    Args:
        sequence_str: 序號字串（如 "011" 或 "011.1"）

    Returns:
        str: 遞增後的序號字串（如 "012" 或 "011.2"）
    """
    parts = sequence_str.split(".")
    last = parts[-1]
    width = len(last)
    parts[-1] = str(int(last) + 1).zfill(width)
    return ".".join(parts)


def _resolve_available_target_id(target_id: str, version: str) -> str:
    """
    碰撞時尋找下一個可用序號（發版前移撞號改號機制）。

    在目標版本同一 Wave 下，自目標序號起遞增，直到找到無碰撞的 ID 為止。
    僅在 target_id 可解析元件時生效；無法解析時原樣返回（呼叫端仍會照舊
    走碰撞拒絕路徑，避免對非標準格式 ID 產生未預期行為）。

    Args:
        target_id: 原本碰撞的目標 Ticket ID
        version: fallback 版本號（若 target_id 無法解析版本時使用）

    Returns:
        str: 下一個可用的目標 Ticket ID
    """
    components = extract_id_components(target_id)
    if not components:
        return target_id

    target_version = components["version"]
    wave = components["wave"]
    sequence_str = components["sequence"]

    while True:
        sequence_str = _increment_sequence_str(sequence_str)
        candidate_id = f"{target_version}-W{wave}-{sequence_str}"
        if not _check_target_collision(candidate_id, version):
            return candidate_id


def _validate_target_version(target_id: str, version: str) -> Optional[str]:
    """
    驗證目標 Ticket ID 的版本是否已在 todolist.yaml 中註冊（W9-002）。

    僅阻擋完全未註冊的版本；planned/active/completed 皆放行，因為
    跨版本遷移（含遷入尚未 active 的未來版本）是正當場景。

    Args:
        target_id: 目標 Ticket ID
        version: fallback 版本號（若 target_id 無法解析版本時使用）

    Returns:
        Optional[str]: 未註冊時回傳錯誤訊息；已註冊（或無法判定）回傳 None
    """
    from ticket_system.lib.version import is_version_registered

    target_components = extract_id_components(target_id)
    target_version = target_components["version"] if target_components else version

    if is_version_registered(target_version):
        return None

    return ErrorMessages.VERSION_NOT_REGISTERED.format(version=target_version)


def _children_without(children: Any, *ids: str) -> list:
    """回傳移除指定 ID 的 children（字串與 dict 形式皆處理）。"""
    return [
        c for c in (children or [])
        if (c.get("id") if isinstance(c, dict) else c) not in ids
    ]


def _load_parent_for_sync(parent_id: str):
    """載入父票，回傳 (path, ticket)；缺檔或讀取失敗回傳 (path, None)。"""
    components = extract_id_components(parent_id)
    version = components["version"] if components else None
    path = get_ticket_path(version, parent_id) if version else None
    if path is None or not path.exists():
        return path, None
    return path, _load_ticket_from_path(path)


def _save_parent_children(path: Path, parent: Dict[str, Any], children: list) -> bool:
    """寫回父票 children；寫入失敗輸出 warning 並回傳 False。"""
    parent["children"] = children
    try:
        save_ticket(parent, path)
        return True
    except (IOError, OSError) as e:
        print(format_warning(WarningMessages.FILE_UPDATE_FAILED, path=str(path), error=str(e)))
        return False


def _sync_parent_children(
    old_id: str,
    new_id: str,
    old_parent_id: Optional[str],
    new_parent_id: Optional[str],
) -> List[Path]:
    """父票改變時：舊父 children 移除該票，新父 children 加入新 ID（不重複）。

    必須在 _update_cross_references_collecting 之後呼叫（舊父的 children 此時已被
    原地改為 new_id，這裡一併移除）。父票缺檔只輸出 warning，不中斷遷移。

    Returns:
        實際寫入的父票檔案路徑。
    """
    written: List[Path] = []
    if old_parent_id:
        path, parent = _load_parent_for_sync(old_parent_id)
        if parent is not None:
            kept = _children_without(parent.get("children"), old_id, new_id)
            if _save_parent_children(path, parent, kept):
                written.append(path)
    if new_parent_id:
        path, parent = _load_parent_for_sync(new_parent_id)
        if parent is None:
            print(format_warning(
                "[WARNING] [migrate] 新父票 {parent_id} 不存在，未能加入其 children（遷移照常完成）",
                parent_id=new_parent_id,
            ))
        else:
            children = parent.get("children") or []
            if len(_children_without(children, new_id)) < len(children):
                return written  # 已列：保留原項、原形式、原順序，不寫檔
            if _save_parent_children(path, parent, [*children, new_id]):
                written.append(path)
    return written


# ---------------------------------------------------------------------------
# 有子孫的票：連帶遷移整個子樹（preflight 任一項失敗整體拒絕、零寫入）
# ---------------------------------------------------------------------------

_SUBTREE_PREFLIGHT_FAILED = "[ERROR] 子樹遷移 preflight 失敗（零寫入），共 {count} 項："
_SUBTREE_DRY_RUN_HEADER = "預覽子樹遷移：{source_id} → {target_id}，共 {count} 張票"
_SUBTREE_MIDWAY_FAILED = "[ERROR] 子樹遷移中途失敗：{error}；以下檔案已寫入工作區："
_TERMINAL_STATUSES = ("completed", "closed")
_STRUCTURAL_REF_FIELDS = (
    "blockedBy", "relatedTo", "spawned_tickets", "children", "source_ticket",
    "parent_id", "discovered_during", "closed_by",
)


def _map_ref(value: Any, mapping: Dict[str, str]):
    """單趟映射字串或清單（含 children 的 dict 形式）引用，回傳 (新值, 是否變更)。"""
    if isinstance(value, str):
        new = mapping.get(value, value)
        return new, new != value
    if not isinstance(value, list):
        return value, False
    out, changed = [], False
    for item in value:
        if isinstance(item, dict) and item.get("id") in mapping:
            item, changed = {**item, "id": mapping[item["id"]]}, True
        elif isinstance(item, str) and item in mapping:
            item, changed = mapping[item], True
        out.append(item)
    return out, changed


def _remap_ticket_refs(ticket: Dict[str, Any], mapping: Dict[str, str]) -> bool:
    """以 old->new 映射一次改寫票內所有結構引用（不逐對替換，重疊映射不會二次改寫）。"""
    changed = False
    for key in _STRUCTURAL_REF_FIELDS:
        if key in ticket:
            ticket[key], hit = _map_ref(ticket[key], mapping)
            changed = changed or hit
    chain = ticket.get("chain")
    if isinstance(chain, dict):
        for key in ("root", "parent"):
            chain[key], hit = _map_ref(chain.get(key), mapping)
            changed = changed or hit
    return changed


def _iter_all_ticket_files() -> List[Path]:
    """所有版本目錄（扁平與三層）下的票檔，路徑排序。"""
    work_logs_root = get_ticket_state_root() / "docs" / "work-logs"
    dirs = set(work_logs_root.glob("v*/tickets")) | set(work_logs_root.glob("v*/v*/v*/tickets"))
    return [f for d in sorted(dirs) for f in sorted(d.glob("*.md"))]


def _collect_subtree(source_id: str) -> List[tuple]:
    """收集 source 的待搬子孫：ID 前綴 `source.` 且 status 非終態者，回傳 [(id, path, ticket)]（依 ID 排序）。

    completed／closed 的子孫留在原版本、ID 不變（歷史紀錄穩定），不屬成員；其祖先鏈上
    有被留下者的子孫也一併留下（搬走會失去父票）。留下者的 parent 參照由子樹外引用改寫
    更新。parent_id 指向 source 但 ID 不在前綴下的票無法由前綴映射新 ID，同樣不屬成員。
    """
    prefix = source_id + "."
    found = {}
    for path in _iter_all_ticket_files():
        ticket = _load_ticket_from_path(path)
        tid = (ticket or {}).get("id") or extract_core_ticket_id(path.stem)
        if ticket and tid.startswith(prefix):
            found[tid] = (path, ticket)
    kept: List[str] = []
    moved = []
    for tid in sorted(found):  # 祖先 ID 必排在後代之前
        path, ticket = found[tid]
        under_kept = any(tid.startswith(k + ".") for k in kept)
        if under_kept or ticket.get("status") in _TERMINAL_STATUSES:
            kept.append(tid)
        else:
            moved.append((tid, path, ticket))
    return moved


def _subtree_preflight(mapping: Dict[str, str], version: str,
                       force_overwrite: bool) -> List[str]:
    """子樹遷移的全部前置檢查，回傳失敗項訊息清單（空表示通過）。"""
    failures: List[str] = []
    old_ids = set(mapping)
    version_error = _validate_target_version(mapping[next(iter(mapping))], version)
    if version_error:
        failures.append(version_error)
    for old_id, new_id in mapping.items():
        if not validate_ticket_id(new_id):
            failures.append(f"{new_id}：Ticket ID 格式無效（來源 {old_id}）")
            continue
        info = calculate_chain_info(new_id)
        new_depth = (info or {}).get("depth", 0) + 1
        if new_depth > MAX_TICKET_DEPTH:
            failures.append(
                f"{new_id}：遷移後深度 {new_depth} 超過 MAX_TICKET_DEPTH={MAX_TICKET_DEPTH}"
                f"（來源 {old_id}）")
        collision = _check_target_collision(new_id, version) if new_id not in old_ids else None
        if collision and not force_overwrite:
            failures.append(f"{new_id}：目標已存在（{collision['path']}，來源 {old_id}）")
    return failures


def _prepare_member(ticket: Dict[str, Any], old_id: str, new_id: str,
                    mapping: Dict[str, str]) -> None:
    """依映射改寫成員票：先改引用（舊值），再設新 ID／previous_ids／wave／chain／parent_id。"""
    _remap_ticket_refs(ticket, mapping)
    ticket["id"] = new_id
    ticket[PREVIOUS_IDS_FIELD] = [*(ticket.get(PREVIOUS_IDS_FIELD) or []), old_id]
    components = extract_id_components(new_id)
    if components:
        ticket["version"] = components["version"]
        ticket["wave"] = components["wave"]
    chain_info = calculate_chain_info(new_id)
    if chain_info:
        ticket["chain"] = chain_info
        ticket["parent_id"] = chain_info.get("parent")


def _member_path(new_id: str, fallback_version: str) -> Path:
    components = extract_id_components(new_id)
    return get_ticket_path(components["version"] if components else fallback_version, new_id)


def _rewrite_external_refs(mapping: Dict[str, str], skip_paths: set) -> List[Path]:
    """單趟改寫子樹以外票檔的引用；子樹成員已改寫，跳過以免重疊映射二次改寫。"""
    written: List[Path] = []
    for path in _iter_all_ticket_files():
        if path in skip_paths:
            continue
        ticket = _load_ticket_from_path(path)
        if not ticket or not _remap_ticket_refs(ticket, mapping):
            continue
        try:
            save_ticket(ticket, path)
            written.append(path)
        except (IOError, OSError) as e:
            print(format_warning(WarningMessages.FILE_UPDATE_FAILED, path=str(path), error=str(e)))
    return written


def _migrate_subtree(
    version: str,
    source_id: str,
    target_id: str,
    root: Dict[str, Any],
    descendants: List[tuple],
    dry_run: bool,
    backup: bool,
    force_overwrite: bool,
) -> tuple:
    """連帶遷移 source 與其整個子樹，回傳 (exit code, 根票 record | None)。"""
    source_path = get_ticket_path(
        (extract_id_components(source_id) or {}).get("version", version), source_id)
    members = [(source_id, source_path, root), *descendants]
    mapping = {tid: target_id + tid[len(source_id):] for tid, _p, _t in members}
    failures = _subtree_preflight(mapping, version, force_overwrite)
    if failures:
        print(format_error(_SUBTREE_PREFLIGHT_FAILED, count=len(failures)))
        for failure in failures:
            print(f"  - {failure}")
        return 1, None
    if dry_run:
        print(format_info(_SUBTREE_DRY_RUN_HEADER, source_id=source_id,
                          target_id=target_id, count=len(members)))
        for old_id, new_id in mapping.items():
            print(f"  {old_id} → {new_id}")
        return 0, None

    old_parent_id = root.get("parent_id")
    new_paths = {tid: _member_path(mapping[tid], version) for tid, _p, _t in members}
    if backup:
        for tid, _p, _t in members:
            _backup_ticket((extract_id_components(tid) or {}).get("version", version), tid)
    written: List[Path] = []
    try:
        for tid, _path, ticket in members:
            _prepare_member(ticket, tid, mapping[tid], mapping)
            new_paths[tid].parent.mkdir(parents=True, exist_ok=True)
            save_ticket(ticket, new_paths[tid])
            written.append(new_paths[tid])
    except (IOError, OSError) as e:
        print(format_error(_SUBTREE_MIDWAY_FAILED, error=str(e)))
        for path in written:
            print(f"  {path}")
        return 1, None

    produced = set(new_paths.values())
    for _tid, old_path, _t in members:
        if old_path not in produced and old_path.exists():
            old_path.unlink()
    referrers = _rewrite_external_refs(mapping, produced | {p for _i, p, _t in members})
    new_parent_id = root.get("parent_id")
    if old_parent_id != new_parent_id:
        target_parent = None if new_parent_id in mapping else new_parent_id
        for path in _sync_parent_children(source_id, target_id, old_parent_id, target_parent):
            if path not in referrers:
                referrers.append(path)
    records = [
        _MigrationRecord(old_id=tid, new_id=mapping[tid], target_path=new_paths[tid],
                         source_path=old_path, topic_line=inherit_assignment(tid, mapping[tid]))
        for tid, old_path, _t in members
    ]
    records[0].referrers = referrers
    records[0].subtree = records[1:]
    print(format_info(InfoMessages.TICKET_MIGRATED, source_id=source_id, target_id=target_id)
          + f"（含子孫共 {len(records)} 張）")
    return 0, records[0]


def _flatten_records(records: List[_MigrationRecord]) -> List[_MigrationRecord]:
    """展開根票 record 帶的子樹成員，供併成單一提交。"""
    return [item for record in records for item in (record, *record.subtree)]


def _migrate_ticket_files(
    version: str,
    source_id: str,
    target_id: str,
    dry_run: bool = False,
    backup: bool = True,
    force_overwrite: bool = False,
) -> tuple:
    """
    遷移單一 Ticket 的檔案（寫入工作區，不提交）

    Args:
        version: 版本號
        source_id: 來源 Ticket ID
        target_id: 目標 Ticket ID
        dry_run: 預覽模式
        backup: 是否備份
        force_overwrite: 明示授權覆寫目標 ID 既有 Ticket（W14-048）

    Returns:
        (exit code, _MigrationRecord | None)：exit code 0 成功, 1 失敗, 2 來源 Ticket
        不存在；僅實際寫入成功時帶 record（預覽與失敗為 None）。
    """
    # 驗證 ID 格式
    if not validate_ticket_id(source_id) or not validate_ticket_id(target_id):
        print(MigrateMessages.INVALID_TICKET_ID_FORMAT)
        return 1, None

    # W9-002: 目標版本合法性守衛（未註冊阻擋；dry-run 同樣須過守衛）
    version_error = _validate_target_version(target_id, version)
    if version_error:
        print(format_error(version_error))
        return 1, None

    # 從 source_id 提取版本號，支援跨版本遷移
    source_components = extract_id_components(source_id)
    source_version = source_components["version"] if source_components else version

    # W14-048: 在 load_and_validate_ticket 之前先檢查實體檔案存在
    # （load_ticket 有 process-scoped cache，可能在檔案已刪除後仍命中快取，
    #  導致冪等性 re-run 場景誤判 source 仍存在）
    source_path_check = get_ticket_path(source_version, source_id)
    if not source_path_check.exists():
        return 2, None

    # 載入來源 Ticket
    ticket, error = load_and_validate_ticket(source_version, source_id)
    if error:
        return 2, None

    # 有子孫的票：連帶遷移整個子樹（同 ID 改名不涉及子孫，沿用單票路徑）
    if source_id != target_id:
        descendants = _collect_subtree(source_id)
        if descendants:
            root = _load_ticket_from_path(source_path_check) or ticket
            return _migrate_subtree(version, source_id, target_id, root, descendants,
                                    dry_run, backup, force_overwrite)

    # W14-048: collision detection（target 已存在）
    # 例外：source == target（同 ID rename，等同 in-place 更新）不視為 collision
    collision = None
    if source_id != target_id:
        collision = _check_target_collision(target_id, version)

    # 預覽模式
    if dry_run:
        print(format_info(MigrateMessages.DRY_RUN_HEADER, source_id=source_id, target_id=target_id))
        print(f"{MigrateMessages.DRY_RUN_TITLE_PREFIX} {ticket.get('title', 'N/A')}")
        print(f"{MigrateMessages.DRY_RUN_STATUS_PREFIX} {ticket.get('status', 'N/A')}")
        if collision:
            if force_overwrite:
                print(format_warning(
                    MigrateMessages.WARN_MIGRATE_TARGET_EXISTS,
                    target_path=str(collision["path"]),
                    existing_title=collision["title"],
                    existing_status=collision["status"],
                ))
                return 0, None
            # 發版前移撞號改號機制：dry-run 對碰撞判 FAIL 並印改號預覽，
            # 不再視為可放行的預覽（避免 finish --dry-run 對碰撞誤判 [OK]）。
            resolved_id = _resolve_available_target_id(target_id, version)
            print(format_error(
                MigrateMessages.DRY_RUN_COLLISION_FAIL,
                target_id=target_id,
                target_path=str(collision["path"]),
                existing_title=collision["title"],
                existing_status=collision["status"],
                resolved_id=resolved_id,
            ))
            return 1, None
        return 0, None

    # 實際執行階段：碰撞時預設改取下一可用序號（migrated_from 記錄原目標）；
    # --force-overwrite 旗標語意不變，仍記錄 audit log 後覆寫既有 Ticket。
    if collision:
        if not force_overwrite:
            original_target_id = target_id
            target_id = _resolve_available_target_id(target_id, version)
            ticket["migrated_from"] = original_target_id
            print(format_info(
                MigrateMessages.INFO_MIGRATE_RENUMBERED,
                original_target_id=original_target_id,
                resolved_id=target_id,
            ))
        else:
            # force_overwrite=True：記錄 audit log 後繼續執行
            print(format_info(
                MigrateMessages.INFO_FORCE_OVERWRITE,
                target_id=target_id,
                timestamp=datetime.now().isoformat(),
                existing_title=collision["title"],
            ))

    # 執行備份
    backup_path = None
    if backup:
        backup_path = _backup_ticket(source_version, source_id)
        if backup_path:
            print(format_info(InfoMessages.FILE_BACKED_UP, path=str(backup_path)))
        else:
            print(format_warning(WarningMessages.BACKUP_SKIPPED))

    # 更新 Ticket 資料
    old_id = ticket.get("id")
    original_parent_id = ticket.get("parent_id")
    ticket["id"] = target_id
    if old_id and old_id != target_id:
        ticket[PREVIOUS_IDS_FIELD] = [*(ticket.get(PREVIOUS_IDS_FIELD) or []), old_id]

    # 更新 wave
    components = extract_id_components(target_id)
    if components:
        ticket["version"] = components["version"]
        ticket["wave"] = components["wave"]

        # 更新 chain 資訊
        chain_info = calculate_chain_info(target_id)
        if chain_info:
            ticket["chain"] = chain_info

        # 更新 parent_id；新 ID 為根票時清為 null（chain_info 為空時不動）
        if chain_info:
            ticket["parent_id"] = chain_info.get("parent")

    # 遷移前的父票（供遷移後同步舊父/新父 children）
    old_parent_id = original_parent_id
    new_parent_id = ticket.get("parent_id")

    # 更新所有引用
    _update_ticket_id_references(ticket, old_id, target_id)

    # 取得原始檔案路徑
    source_path = get_ticket_path(source_version, source_id)

    # 提取目標版本（從目標 ID 中）以支援跨版本遷移
    target_components = extract_id_components(target_id)
    target_version = target_components["version"] if target_components else version
    target_path = get_ticket_path(target_version, target_id)

    # 確保目錄存在
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # 儲存到新位置
        save_ticket(ticket, target_path)
        print(format_info(InfoMessages.TICKET_MIGRATED, source_id=source_id, target_id=target_id))

        # 刪除舊檔案
        if source_path != target_path and source_path.exists():
            source_path.unlink()
            print(format_info(InfoMessages.FILE_DELETED, path=str(source_path)))

        # 更新其他 Ticket 中的交叉引用
        referrers = _update_cross_references_collecting(old_id, target_id)
        if referrers:
            print(format_info(MigrateMessages.CROSS_REFERENCES_UPDATED, count=len(referrers)))

        # 父票改變時同步舊父/新父 children（異動檔併入同一提交）
        if old_id != target_id and old_parent_id != new_parent_id:
            for path in _sync_parent_children(old_id, target_id, old_parent_id, new_parent_id):
                if path not in referrers:
                    referrers.append(path)

        # topic-assignments 追加新 ID 行（舊行保留，append-only）；同 ID 改名無需處理
        topic_line = inherit_assignment(old_id, target_id) if old_id != target_id else None

        return 0, _MigrationRecord(
            old_id=old_id,
            new_id=target_id,
            target_path=target_path,
            source_path=source_path,
            referrers=referrers,
            topic_line=topic_line,
        )

    except (IOError, OSError) as e:
        print(format_error(ErrorMessages.FILE_CREATION_FAILED, error=str(e)))
        if backup_path:
            print(format_info(MigrationMessages.BACKUP_LOCATION, path=str(backup_path)))
        return 1, None


def _commit_migrations(records: List[_MigrationRecord]) -> bool:
    """把成功遷移的全部檔案以單一隔離提交入庫。

    路徑含新檔、舊檔（刪除）與各引用者；主路徑取仍存在的新檔（git 錨點）。
    topic-assignments 以 append_lines 只提交本次追加行。

    Returns:
        True 表提交最終失敗（呼叫端應回 EXIT_AUTO_COMMIT_FAILED）。
    """
    records = _flatten_records(records)
    if not records:
        return False
    targets = [r.target_path for r in records if r.target_path.exists()]
    paths = [str(p) for p in targets]
    for record in records:
        paths.append(str(record.source_path))
        paths.extend(str(p) for p in record.referrers)
    topic_lines = "".join(r.topic_line for r in records if r.topic_line)
    first = records[0]
    single = len(records) == 1
    failed = commit_ticket_mds_reporting(
        "migrate",
        paths,
        ticket_id=first.new_id,
        section=f"from {first.old_id}" if single else f"{len(records)} tickets",
        operation="migrate",
        append_lines={str(assignments_file_path()): topic_lines} if topic_lines else None,
    )
    if failed and topic_lines:
        import sys

        sys.stderr.write(
            f"[WARNING] [migrate] 尚未入庫的追加行（{assignments_file_path()}），"
            "補救時一併 git add 該檔：\n" + topic_lines
        )
    return failed


def _migrate_single_ticket(
    version: str,
    source_id: str,
    target_id: str,
    dry_run: bool = False,
    backup: bool = True,
    force_overwrite: bool = False,
) -> int:
    """遷移單一 Ticket 並以單一 commit 入庫。

    Returns:
        int: exit code (0 成功, 1 失敗, 2 來源 Ticket 不存在,
        EXIT_AUTO_COMMIT_FAILED 檔案已寫入但提交最終失敗)
    """
    rc, record = _migrate_ticket_files(
        version, source_id, target_id, dry_run, backup, force_overwrite
    )
    if rc == 0 and record and _commit_migrations([record]):
        return EXIT_AUTO_COMMIT_FAILED
    return rc


def _load_migration_config(config_file: str) -> Optional[List[Dict[str, str]]]:
    """
    載入遷移配置檔案

    Args:
        config_file: 配置檔案路徑

    Returns:
        List[Dict]: 遷移清單，或 None 如果載入失敗
    """
    config_path = Path(config_file)

    if not config_path.exists():
        print(f"{MigrateMessages.CONFIG_FILE_NOT_FOUND} {config_file}")
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            if config_file.endswith(".yaml") or config_file.endswith(".yml"):
                data = yaml.safe_load(f)
            elif config_file.endswith(".json"):
                data = json.load(f)
            else:
                print(MigrateMessages.CONFIG_FORMAT_NOT_SUPPORTED)
                return None

        if not isinstance(data, dict) or "migrations" not in data:
            print(MigrateMessages.CONFIG_FORMAT_INVALID)
            return None

        migrations = data["migrations"]
        if not isinstance(migrations, list):
            print(MigrateMessages.MIGRATIONS_FIELD_NOT_LIST)
            return None

        return migrations

    except (IOError, OSError, yaml.YAMLError, json.JSONDecodeError) as e:
        print(f"{MigrateMessages.CONFIG_LOAD_FAILED} {e}")
        return None


def _batch_migrate(
    version: str,
    config_file: str,
    dry_run: bool = False,
    backup: bool = True,
    force_overwrite: bool = False,
) -> int:
    """
    批量遷移 Tickets

    Args:
        version: 版本號
        config_file: 配置檔案路徑
        dry_run: 預覽模式
        backup: 是否備份
        force_overwrite: 明示授權覆寫目標 ID 既有 Ticket（W14-048）

    Returns:
        int: exit code (0 全部成功, 1 部分失敗, 2 全部失敗)
    """
    migrations = _load_migration_config(config_file)
    if not migrations:
        return 1

    print(format_info(MigrationMessages.LOAD_MIGRATIONS, count=len(migrations)))

    # 發版前移撞號改號機制：碰撞不再 fail-fast，改由個別 _migrate_single_ticket
    # 自動改號（force_overwrite=True 時仍記錄 audit log 覆寫，語意不變）。
    # 批量預掃描因此不再需要——各筆遷移各自對當下檔案系統狀態判斷碰撞並
    # 改號，天然支援批次內連環碰撞（前一筆改號後的新目標仍會被下一筆的
    # 碰撞檢查看見）。

    success_count = 0
    fail_count = 0
    skip_count = 0
    records: List[_MigrationRecord] = []

    for migration in migrations:
        if not isinstance(migration, dict):
            print(format_warning(WarningMessages.INVALID_MIGRATION_ITEM))
            skip_count += 1
            continue

        source_id = migration.get("from")
        target_id = migration.get("to")

        if not source_id or not target_id:
            print(format_warning(WarningMessages.MIGRATION_ITEM_INCOMPLETE))
            skip_count += 1
            continue

        print()
        result, record = _migrate_ticket_files(
            version, source_id, target_id, dry_run, backup, force_overwrite
        )

        if result == 0:
            success_count += 1
            if record:
                records.append(record)
        elif result == 2:
            skip_count += 1
        else:
            fail_count += 1

    # 輸出摘要
    print()
    print(SEPARATOR_PRIMARY)
    print(format_info(MigrateMessages.MIGRATION_SUMMARY))
    print(format_info(MigrationMessages.SUCCESS_COUNT, count=success_count))
    print(format_info(MigrationMessages.FAIL_COUNT, count=fail_count))
    print(format_info(MigrationMessages.SKIP_COUNT, count=skip_count))
    print(SEPARATOR_PRIMARY)

    # 整批只把成功項以單一 commit 提交；提交失敗的 75 優先於其餘結果
    if _commit_migrations(records):
        return EXIT_AUTO_COMMIT_FAILED
    if fail_count > 0:
        return 1 if success_count > 0 else 2
    return 0


def execute(args: argparse.Namespace) -> int:
    """執行 migrate 命令"""
    # 使用共用 API 解析版本（自動標準化移除 v 前綴）
    version = resolve_version(getattr(args, "version", None))
    if not version:
        print(format_error(ErrorMessages.VERSION_NOT_DETECTED))
        return 1

    # 檢查是否為批量遷移
    if getattr(args, "config", None):
        dry_run = getattr(args, "dry_run", False)
        backup = not getattr(args, "no_backup", False)
        force_overwrite = getattr(args, "force_overwrite", False)
        return _batch_migrate(version, args.config, dry_run, backup, force_overwrite)

    # 單一 Ticket 遷移
    source_id = getattr(args, "source_id", None)
    target_id = getattr(args, "target_id", None)

    if not source_id or not target_id:
        print(format_error(ErrorMessages.MISSING_PARAMETERS))
        return 1

    dry_run = getattr(args, "dry_run", False)
    backup = not getattr(args, "no_backup", False)
    force_overwrite = getattr(args, "force_overwrite", False)

    return _migrate_single_ticket(
        version, source_id, target_id, dry_run, backup, force_overwrite
    )


def register(subparsers: argparse._SubParsersAction) -> None:
    """註冊 migrate 子命令"""
    parser = subparsers.add_parser(
        "migrate",
        help=MigrateMessages.HELP_MIGRATE
    )

    # 位置參數（用於單一遷移）
    parser.add_argument(
        "source_id",
        nargs="?",
        help=MigrateMessages.ARG_SOURCE_ID
    )
    parser.add_argument(
        "target_id",
        nargs="?",
        help=MigrateMessages.ARG_TARGET_ID
    )

    # 選項
    parser.add_argument(
        "--config",
        metavar="FILE",
        help=MigrateMessages.ARG_CONFIG
    )
    parser.add_argument(
        "--version",
        help=MigrateMessages.ARG_VERSION
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=MigrateMessages.ARG_DRY_RUN
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        default=True,
        help=MigrateMessages.ARG_BACKUP
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help=MigrateMessages.ARG_NO_BACKUP
    )
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        default=False,
        help=MigrateMessages.ARG_FORCE_OVERWRITE
    )

    parser.set_defaults(func=execute)


