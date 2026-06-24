"""
Handoff 共用判斷函式模組

封裝 resume.py 和 handoff_gc.py 共用的 stale handoff 判斷邏輯。
消除跨模組私有函式引用，遵循模組封裝原則。
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ticket_system.lib.constants import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    TASK_CHAIN_DIRECTION_TYPES,
    NON_CHAIN_DIRECTION_TYPES,
    TERMINAL_STATUSES,
    HANDOFF_DIR,
    HANDOFF_PENDING_SUBDIR,
)
from ticket_system.lib.paths import get_project_root


# W17-181.1: 真 SSOT delegate 至 hook_utils.hook_ticket
# lib 不再持有 ticket 路徑解析責任，直接 delegate 至 find_ticket_file（單一來源）。
# 子進程環境（如 stop hook subprocess）下 cwd / fallback 路徑解析失誤的根因消除。
# Why: ARCH-020 跨進程同構邏輯反模式；先前 load_and_validate_ticket 走 paths.get_tickets_dir
# 在子進程環境下若 CLAUDE_PROJECT_DIR 未傳遞會 fallback 至 cwd 而錯誤。
def _ensure_hook_utils_path() -> None:
    """將 .claude/ 加入 sys.path 以可 import lib.hook_ticket。
    從 lib 檔案位置（…/.claude/skills/ticket/ticket_system/lib/handoff_utils.py）
    向上 4 層至 .claude/。
    """
    claude_dir = Path(__file__).resolve().parents[4]
    claude_dir_str = str(claude_dir)
    if claude_dir_str not in sys.path:
        sys.path.insert(0, claude_dir_str)


_ensure_hook_utils_path()

try:
    from lib.hook_ticket import (
        find_ticket_file as _find_ticket_file,
        parse_ticket_frontmatter as _parse_ticket_frontmatter,
    )
except Exception:  # pragma: no cover - 防禦性 fallback；正常環境下永遠應載入成功
    _find_ticket_file = None  # type: ignore
    _parse_ticket_frontmatter = None  # type: ignore

# 所有已知的 direction 值（從 constants 衍生，確保單一來源）
_KNOWN_DIRECTION_VALUES = {"auto"} | set(TASK_CHAIN_DIRECTION_TYPES) | set(NON_CHAIN_DIRECTION_TYPES)

# Handoff JSON 必填欄位
_HANDOFF_REQUIRED_FIELDS = ("ticket_id", "direction", "timestamp")


@dataclass
class ParsedHandoff:
    """
    解析後的 handoff 記錄

    包含完整的檔案和資料資訊，支援呼叫端自訂的error處理。
    """
    file_path: Path
    ticket_id: str
    direction: str
    from_status: str
    format: str  # "json" 或 "markdown"
    data: dict  # 完整的 JSON 資料（markdown 時含預設欄位）
    parse_error: Optional[str] = None  # JSON 讀取錯誤（IOError, JSONDecodeError）
    schema_error: Optional[str] = None  # 必填欄位缺失


def _load_ticket_status(
    ticket_id: str,
    project_root: Optional[Path] = None,
) -> Optional[str]:
    """W17-181.1：透過 hook_utils.find_ticket_file + parse_ticket_frontmatter
    取得 ticket status（單一 SSOT 路徑解析來源）。

    Args:
        ticket_id: Ticket ID
        project_root: 專案根目錄；None 時 fallback 至 get_project_root()

    Returns:
        Optional[str]: ticket status 字串；若無法定位或解析失敗回 None
    """
    if _find_ticket_file is None or _parse_ticket_frontmatter is None:
        return None

    root = project_root if project_root is not None else get_project_root()
    ticket_path = _find_ticket_file(ticket_id, root)
    if ticket_path is None:
        return None

    frontmatter = _parse_ticket_frontmatter(ticket_path)
    if not frontmatter:
        return None

    status = frontmatter.get("status")
    return status if isinstance(status, str) else None


def is_ticket_completed(
    ticket_id: str,
    project_root: Optional[Path] = None,
) -> bool:
    """
    檢查 Ticket 是否已 completed。

    W17-181.1：改用 hook_utils.find_ticket_file + parse_ticket_frontmatter（單一 SSOT），
    並接受顯式 project_root，消除子進程環境下 cwd 推導錯誤的根因（ARCH-020 同構修復）。

    若無法載入（不存在或格式錯誤），返回 False（保守策略：不確定時顯示）。

    Args:
        ticket_id: Ticket ID，格式如 "0.31.1-W5-004"
        project_root: 專案根目錄；None 時 fallback 至 get_project_root()（CLI 場景）

    Returns:
        bool: True 表示已完成，False 表示未完成或無法判斷
    """
    try:
        status = _load_ticket_status(ticket_id, project_root)
        return status == STATUS_COMPLETED
    except Exception:
        return False  # 保守策略：無法判斷時顯示


def is_ticket_terminal(
    ticket_id: str,
    project_root: Optional[Path] = None,
) -> bool:
    """
    檢查 Ticket 是否處於 terminal 狀態（completed 或 closed）。

    W17-181.2：將 stop hook 自定義的 terminal 判定上移至 lib，消除
    跨進程同構邏輯（ARCH-020）。stop hook 的 GC / handoff 過濾路徑使用，
    避免 closed 的 ticket 對應 handoff JSON 被誤報為「待恢復」阻止退出。

    Args:
        ticket_id: Ticket ID
        project_root: 專案根目錄；None 時 fallback 至 get_project_root()

    Returns:
        bool: True 表示處於 terminal 狀態，False 表示否或無法判斷
    """
    try:
        status = _load_ticket_status(ticket_id, project_root)
        return status in TERMINAL_STATUSES
    except Exception:
        return False  # 保守策略：無法判斷時顯示


def is_task_chain_direction(direction: str) -> bool:
    """
    判斷 handoff 的 direction 是否為任務鏈類型。

    任務鏈 direction（to-sibling、to-parent、to-child）中，
    來源 ticket completed 是預期狀態（先 complete 再 handoff 到下一任務），
    不應被過濾為 stale。

    格式：direction 格式可為 "to-sibling:target_id" 或 "to-sibling" 等，
    使用 split(":") 提取第一段來判斷。

    Args:
        direction: Handoff direction 字符串，可能為 "to-sibling", "to-sibling:xxx", etc.

    Returns:
        bool: True 表示為任務鏈類型，False 表示為其他類型（context-refresh 等）
    """
    if not direction:
        return False

    # 提取 direction type（split ":" 取首段）
    direction_type = direction.split(":")[0]

    return direction_type in TASK_CHAIN_DIRECTION_TYPES


def is_ticket_in_progress_or_completed(
    ticket_id: str,
    project_root: Optional[Path] = None,
) -> bool:
    """
    檢查 Ticket 是否已 in_progress 或 completed。

    W17-181.1：改用 hook_utils.find_ticket_file + parse_ticket_frontmatter（單一 SSOT），
    並接受顯式 project_root，消除子進程環境下 cwd 推導錯誤的根因（ARCH-020 同構修復）。

    用於判斷任務鏈 handoff 的目標 ticket 是否已啟動。
    若目標已啟動，表示此 handoff 已被接手，應過濾為 stale。

    若無法載入（不存在或格式錯誤），返回 False（保守策略：不確定時顯示）。

    Args:
        ticket_id: Ticket ID，格式如 "0.31.1-W5-004"
        project_root: 專案根目錄；None 時 fallback 至 get_project_root()（CLI 場景）

    Returns:
        bool: True 表示已啟動（in_progress 或 completed），False 表示未啟動或無法判斷
    """
    try:
        status = _load_ticket_status(ticket_id, project_root)
        return status in (STATUS_IN_PROGRESS, STATUS_COMPLETED)
    except Exception:
        return False  # 保守策略：無法判斷時顯示


def extract_direction_target_id(direction: str) -> Optional[str]:
    """
    從 direction 字串提取 target_id。

    格式：direction 可為 "type:target_id"（含目標）或 "type"（無目標）。
    - "to-sibling:0.1.0-W9-002" → "0.1.0-W9-002"
    - "to-parent" → None
    - "context-refresh" → None

    Args:
        direction: Handoff direction 字符串

    Returns:
        Optional[str]: target_id 若存在且非空，否則 None
    """
    parts = direction.split(":", 1)
    if len(parts) > 1 and parts[1]:
        return parts[1]
    return None


def is_valid_direction(direction: str) -> bool:
    """
    驗證 handoff 的 direction 是否為已知類型。

    已知 direction 值（不含後綴）：to-sibling、to-parent、to-child、context-refresh、next-wave、auto
    支援的格式：
    - "to-sibling"、"to-sibling:target_id"
    - "to-parent"、"to-parent:target_id"
    - "to-child"、"to-child:target_id"
    - "context-refresh"
    - "next-wave"
    - "auto"

    Args:
        direction: Handoff direction 字符串

    Returns:
        bool: True 表示為已知 direction，False 表示未知
    """
    if not direction:
        return False

    # 提取 direction type（split ":" 取首段，以支援 "to-sibling:target_id" 格式）
    direction_type = direction.split(":")[0]

    return direction_type in _KNOWN_DIRECTION_VALUES


def resolve_target(record: dict) -> Optional[str]:
    """
    統一解析 handoff record 的 target ticket id（W17-164 / L2-A）。

    讀取優先序：
    1. 顯式 target_ticket_id 欄位（非空字串）
    2. fallback: 從 direction 後綴提取（既有行為）

    Why：handoff 設計初衷是讓下 session 找到「該做的 ticket」（target），
    但既有 schema 以 from_ticket（source）+ direction（相對方向）間接表達。
    新增 target_ticket_id 欄位讓指向絕對化；本 helper 統一讀取邏輯，
    使所有讀取端（GC / SessionStart / Stop / resume hint）共用單一解析來源。

    Consequence：跳過此 helper 而各自實作會重蹈 ARCH-020（跨進程同構邏輯）覆轍，
    造成欄位優先序漂移。

    Args:
        record: handoff JSON dict，預期含 direction 與 / 或 target_ticket_id 欄位

    Returns:
        Optional[str]: 解析得到的 target ticket id；若兩個來源都無法解析則 None
    """
    explicit_target = record.get("target_ticket_id")
    if explicit_target:
        return explicit_target

    direction = record.get("direction", "") or ""
    return extract_direction_target_id(direction)


def is_handoff_stale(
    record: dict,
    project_root: Optional[Path] = None,
) -> tuple[bool, str]:
    """判斷 handoff record 是否為 stale。

    收斂三套消費者（reminder-hook / stop-hook / handoff_gc）對 stale 的判斷規則於單一函式，
    避免規則漂移（W17-095 根因）。

    W17-181.1：新增 project_root 參數，傳遞給 is_ticket_completed /
    is_ticket_in_progress_or_completed 與內部 status 探測，確保子進程環境下
    路徑解析正確（ARCH-020 同構修復）。

    判斷規則（依序檢查）：
    1. 任務鏈方向（to-sibling/to-parent/to-child）且目標 ticket 已 in_progress/completed
       → stale，reason 為「任務鏈目標 {target_id} 已 {status}」
    2. 非任務鏈方向且來源 ticket 已 completed
       → stale，reason 為「來源 ticket {ticket_id} 已 completed」
    3. 非任務鏈方向且 from_status == "completed"
       → stale，reason 為「from_status 標記 completed」
    4. 上述皆不滿足
       → 非 stale，reason 為空字串

    Args:
        record: 從 handoff/pending/*.json 載入的 dict，預期含
            from_ticket / ticket_id / direction / from_status 等欄位。
            ticket_id 與 from_ticket 二擇一，優先使用 from_ticket（向後相容 ticket_id）。
        project_root: 專案根目錄；None 時 fallback 至 get_project_root()（CLI 場景）

    Returns:
        tuple[bool, str]: (is_stale, reason)
            is_stale=True 時 reason 為人類可讀說明；is_stale=False 時 reason 為空字串。
    """
    direction = record.get("direction", "") or ""
    from_ticket = record.get("from_ticket") or record.get("ticket_id") or ""
    from_status = record.get("from_status", "") or ""

    # 情境 1：任務鏈目標已啟動
    if is_task_chain_direction(direction):
        target_id = extract_direction_target_id(direction)
        if target_id and is_ticket_in_progress_or_completed(target_id, project_root):
            # 取得 target 實際狀態以填入 reason（in_progress / completed）
            status = _load_ticket_status(target_id, project_root) or "in_progress"
            return True, f"任務鏈目標 {target_id} 已 {status}"
        # 任務鏈但目標未啟動：不 stale
        return False, ""

    # 情境 2：非任務鏈且來源 ticket 已 completed
    if from_ticket and is_ticket_completed(from_ticket, project_root):
        return True, f"來源 ticket {from_ticket} 已 completed"

    # 情境 3：非任務鏈且 from_status 已標記 completed
    if from_status == STATUS_COMPLETED:
        return True, "from_status 標記 completed"

    # 情境 4：未完成
    return False, ""


def scan_pending_handoffs() -> List[ParsedHandoff]:
    """
    掃描 pending/ 目錄，解析所有 handoff 檔案。

    實現共用的掃描邏輯，被 list_pending_handoffs() 和 _collect_stale_handoffs() 使用。
    同時掃描 .json 和 .md 檔案，進行基本解析（JSON 讀取、必填欄位驗證）。

    每個記錄包含：
    - 成功解析的檔案：parse_error=None, schema_error=None
    - JSON 讀取失敗：parse_error=<錯誤資訊>, schema_error=None
    - 必填欄位缺失：schema_error=<缺失欄位清單>

    呼叫端可根據 parse_error/schema_error 決定是否統計計數或直接跳過。

    Returns:
        List[ParsedHandoff]: 解析結果清單（包含成功和失敗記錄）
    """
    root = get_project_root()
    pending_dir = root / HANDOFF_DIR / HANDOFF_PENDING_SUBDIR

    if not pending_dir.exists():
        return []

    records = []

    # 同時掃描 .json 和 .md 檔案
    for handoff_file in sorted(pending_dir.glob("*.json")) + sorted(pending_dir.glob("*.md")):
        if handoff_file.suffix == ".json":
            # JSON 格式
            try:
                with open(handoff_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                # 記錄讀取錯誤，不中斷迴圈
                records.append(ParsedHandoff(
                    file_path=handoff_file,
                    ticket_id="",
                    direction="",
                    from_status="",
                    format="json",
                    data={},
                    parse_error=str(e),
                ))
                continue

            # 驗證必填欄位
            missing_fields = [f for f in _HANDOFF_REQUIRED_FIELDS if not data.get(f)]
            if missing_fields:
                records.append(ParsedHandoff(
                    file_path=handoff_file,
                    ticket_id=data.get("ticket_id", ""),
                    direction=data.get("direction", ""),
                    from_status=data.get("from_status", ""),
                    format="json",
                    data=data,
                    schema_error=f"缺少必填欄位：{', '.join(missing_fields)}",
                ))
                continue

            # 成功解析
            records.append(ParsedHandoff(
                file_path=handoff_file,
                ticket_id=data.get("ticket_id", ""),
                direction=data.get("direction", ""),
                from_status=data.get("from_status", ""),
                format="json",
                data=data,
            ))

        elif handoff_file.suffix == ".md":
            # Markdown 格式（提取檔名作為 ticket_id）
            ticket_id = handoff_file.stem
            records.append(ParsedHandoff(
                file_path=handoff_file,
                ticket_id=ticket_id,
                direction="",
                from_status="",
                format="markdown",
                data={
                    "ticket_id": ticket_id,
                    "format": "markdown",
                    "path": str(handoff_file.relative_to(root))
                },
            ))

    return records
