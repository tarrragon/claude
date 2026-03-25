#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檔案所有權隔離檢查 Hook

功能：派發前檢查同 Wave 中兄弟 Ticket 的 `where.files` 衝突。

觸發：PreToolUse (Agent) — 當派發代理人執行 Ticket 時

輸出：
- 無衝突：靜默（DEFAULT_OUTPUT）
- 有衝突：警告訊息到 additionalContext
- 異常：錯誤日誌到 stderr + 日誌檔（雙通道）

行為：永遠返回 exit 0（不阻塊派發），但提供可操作的警告供 PM 決策
"""

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from hook_utils.hook_base import get_project_root
from hook_utils.hook_logging import setup_hook_logging
from hook_utils.hook_io import read_json_from_stdin
from hook_utils.hook_ticket import parse_ticket_frontmatter, find_ticket_file


# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "file-ownership-guard-hook"

# 預設輸出格式（靜默通過）
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse"
    }
}

# Ticket ID 正則表達式（符合規範格式）
TICKET_ID_PATTERN = r"(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)"

# 訊息常數
MSG_WARNING_HEADER = "============================================================"
MSG_WARNING_TITLE = "[檔案所有權衝突警告]"
MSG_CONFLICT_ANALYSIS_TITLE = "衝突分析"
MSG_ACTION_TITLE = "建議行動"
MSG_DECISION_TITLE = "決策建議"

# 衝突類型
CONFLICT_TYPE_BROTHER = "brother"
CONFLICT_TYPE_UNRELATED = "unrelated"
CONFLICT_TYPE_PARENT = "parent"
CONFLICT_TYPE_NONE = "none"

# 活躍狀態
ACTIVE_STATUSES = {"pending", "in_progress"}


# ============================================================================
# 資料結構
# ============================================================================

@dataclass
class ConflictInfo:
    """單個衝突的詳細資訊"""
    target_ticket_id: str
    conflicting_ticket_id: str
    conflicting_files: list[str]
    is_parent_child: bool
    conflict_type: str = CONFLICT_TYPE_NONE
    common_parent_id: Optional[str] = None
    target_parent_id: Optional[str] = None
    other_parent_id: Optional[str] = None


@dataclass
class TicketInfo:
    """Ticket 的基本資訊"""
    ticket_id: str
    version: str
    wave: int
    status: str
    parent_id: Optional[str] = None
    where_files: list[str] = field(default_factory=list)


# ============================================================================
# 核心邏輯函式
# ============================================================================


def normalize_path(path: str) -> str:
    """標準化路徑格式，用於跨來源比對

    規則：
    1. 統一使用正斜線 "/"
    2. 簡化多重斜線 "//"
    3. 移除前綴 "./"
    4. 移除尾斜線 "/"
    5. 消除 ".." 序列（stack pop 策略，防止目錄遍歷）
    6. 轉為小寫

    Args:
        path: 原始路徑字串

    Returns:
        str: 標準化後的路徑
    """
    if not path:
        return ""

    # 轉換反斜線為正斜線（Windows 相容）
    path = path.replace("\\", "/")

    # 簡化多重斜線（必須在移除前綴前進行）
    while "//" in path:
        path = path.replace("//", "/")

    # 移除前綴 "./"
    while path.startswith("./"):
        path = path[2:]

    # 防止目錄遍歷：使用 stack pop 策略消除 ".." 序列
    # 若遇到 ".." 則 pop 前面的路徑部分，實現正確的路徑遍歷消除
    parts = path.split("/")
    stack = []
    for part in parts:
        if part == "..":
            # 消除前面的路徑部分（如有）
            if stack:
                stack.pop()
        elif part and part != ".":
            # 保留非空且非 "." 的部分
            stack.append(part)
    path = "/".join(stack)

    # 移除尾斜線
    path = path.rstrip("/")

    # 轉為小寫
    path = path.lower()

    return path


def _parse_ticket_files(
    frontmatter: dict | None,
    logger: logging.Logger
) -> list[str]:
    """從 Ticket frontmatter 提取並規範化 where.files

    用於消除重複的 YAML where.files 解析邏輯。

    Args:
        frontmatter: 已解析的 Ticket frontmatter，或 None
        logger: 日誌物件

    Returns:
        list[str]: 規範化後的檔案清單（空時返回 []）
    """
    if not frontmatter:
        return []

    where_dict = frontmatter.get("where", {})
    if isinstance(where_dict, dict):
        where_files = where_dict.get("files", [])
    else:
        where_files = where_dict

    # 確保列表格式
    where_files = _ensure_file_list(where_files)

    # 規範化路徑
    normalized = [normalize_path(f) for f in where_files if f]
    return [f for f in normalized if f]  # 過濾空字串


def _classify_conflict_type(
    target_id: str,
    target_parent_id: str | None,
    other_id: str,
    other_parent_id: str | None
) -> tuple[str, bool, str | None]:
    """分類衝突類型（父子、兄弟、無關）

    用於判斷兩個 Ticket 的關係類型，支援：
    - 父子關係（one is parent of other）
    - 兄弟關係（common parent）
    - 無關關係（independent）

    Args:
        target_id: 目標 Ticket ID
        target_parent_id: 目標 Ticket 的父 ID（或 None）
        other_id: 其他 Ticket ID
        other_parent_id: 其他 Ticket 的父 ID（或 None）

    Returns:
        tuple: (conflict_type, is_parent_child, common_parent_id)
    """
    # 父子關係判斷
    if other_parent_id == target_id:
        return CONFLICT_TYPE_PARENT, True, None
    if target_parent_id and target_parent_id == other_id:
        return CONFLICT_TYPE_PARENT, True, None

    # 兄弟關係判斷
    if target_parent_id and other_parent_id and target_parent_id == other_parent_id:
        return CONFLICT_TYPE_BROTHER, False, target_parent_id

    # 無關
    return CONFLICT_TYPE_UNRELATED, False, None


def _ensure_file_list(where_value: object) -> list[str]:
    """確保 where.files 為列表格式

    YAML 解析器將列表項目累積為換行符分隔的字符串，
    此函式轉換回列表格式。

    Args:
        where_value: from YAML 解析結果（可能是字符串或列表）

    Returns:
        list[str]: 檔案路徑列表
    """
    if isinstance(where_value, list):
        return where_value

    if isinstance(where_value, str):
        # 換行符分隔的字符串 → 列表
        if not where_value:
            return []
        return [line.strip() for line in where_value.split('\n') if line.strip()]

    return []


def extract_ticket_id(input_data: dict) -> Optional[str]:
    """從派發指令中提取 Ticket ID

    支援多種格式：
    - toolInput.target_id: "0.1.2-W2-003"
    - toolInput.ticket_id: "0.1.2-W2-003"

    Args:
        input_data: PreToolUse Hook 的 stdin JSON

    Returns:
        str | None: 提取到的 Ticket ID，或 None
    """
    if not input_data:
        return None

    tool_input = input_data.get("toolInput", {})
    if not isinstance(tool_input, dict):
        return None

    # 嘗試多個可能的欄位名稱
    ticket_id = (
        tool_input.get("target_id")
        or tool_input.get("ticket_id")
        or tool_input.get("id")
    )

    if not ticket_id:
        return None

    # 驗證格式
    if re.match(TICKET_ID_PATTERN, str(ticket_id)):
        return str(ticket_id)

    return None


def is_valid_trigger(input_data: dict) -> bool:
    """判斷 Hook 觸發條件是否符合

    觸發條件：
    - hookEventName == "PreToolUse"
    - toolName == "Agent"

    Args:
        input_data: Hook stdin JSON

    Returns:
        bool: 是否符合觸發條件
    """
    if not input_data:
        return False

    hook_event = input_data.get("hookEventName")
    tool_name = input_data.get("toolName")

    return hook_event == "PreToolUse" and tool_name == "Agent"


def _extract_version_wave(ticket_id: str) -> tuple[str, int] | tuple[None, None]:
    """從 Ticket ID 提取版本和 Wave

    Args:
        ticket_id: Ticket ID 字串（如 "0.1.2-W2-003"）

    Returns:
        tuple: (version, wave) 或 (None, None)
    """
    match = re.match(TICKET_ID_PATTERN, ticket_id)
    if not match:
        return None, None

    version = match.group(1)
    wave = int(match.group(2))
    return version, wave


def _should_include_ticket(
    ticket_id: str,
    target_ticket_id: str,
    target_version: str,
    target_wave: int,
    logger: logging.Logger
) -> bool:
    """判斷 Ticket 是否符合篩選條件

    Args:
        ticket_id: 待檢查 Ticket ID
        target_ticket_id: 派發目標 Ticket ID
        target_version: 目標版本
        target_wave: 目標 Wave
        logger: 日誌物件

    Returns:
        bool: 是否符合篩選條件
    """
    if ticket_id == target_ticket_id:
        return False

    version, wave = _extract_version_wave(ticket_id)
    if version != target_version or wave != target_wave:
        return False

    return True


def _build_ticket_info(
    ticket_id: str,
    frontmatter: dict,
    logger: logging.Logger
) -> TicketInfo | None:
    """從 Frontmatter 建立 TicketInfo

    Args:
        ticket_id: Ticket ID
        frontmatter: 已解析的 frontmatter
        logger: 日誌物件

    Returns:
        TicketInfo | None: TicketInfo 或 None（若驗證失敗）
    """
    status = frontmatter.get("status")
    if status not in ACTIVE_STATUSES:
        return None

    normalized_files = _parse_ticket_files(frontmatter, logger)
    if not normalized_files:
        logger.debug("Ticket %s 無有效 where.files，跳過", ticket_id)
        return None

    version, wave = _extract_version_wave(ticket_id)
    parent_id = frontmatter.get("parent_id")

    return TicketInfo(
        ticket_id=ticket_id,
        version=version,
        wave=wave,
        status=status,
        parent_id=parent_id,
        where_files=normalized_files
    )


def _process_ticket_file(
    ticket_file: Path,
    target_ticket_id: str,
    target_version: str,
    target_wave: int,
    logger: logging.Logger
) -> TicketInfo | None:
    """處理單個 Ticket 檔案

    Args:
        ticket_file: Ticket 檔案路徑
        target_ticket_id: 派發目標 Ticket ID
        target_version: 目標版本
        target_wave: 目標 Wave
        logger: 日誌物件

    Returns:
        TicketInfo | None: 符合條件的 Ticket，或 None
    """
    filename = ticket_file.name
    if not re.match(TICKET_ID_PATTERN, filename.replace(".md", "")):
        return None

    ticket_id = filename.replace(".md", "")

    if not _should_include_ticket(
        ticket_id, target_ticket_id, target_version, target_wave, logger
    ):
        return None

    try:
        frontmatter = parse_ticket_frontmatter(ticket_file, logger)
        if not frontmatter:
            return None

        return _build_ticket_info(ticket_id, frontmatter, logger)

    except Exception as e:
        logger.error("解析 Ticket %s 失敗: %s", ticket_id, e)
        return None


def get_active_tickets(
    target_ticket_id: str,
    project_root: Path,
    logger: logging.Logger
) -> list[TicketInfo]:
    """掃描同 Wave 的活躍 Ticket

    篩選條件：
    - 版本相同
    - Wave 相同
    - 狀態為 pending 或 in_progress
    - 非目標 Ticket 本身
    - where.files 非空

    Args:
        target_ticket_id: 派發目標的 Ticket ID
        project_root: 專案根目錄
        logger: 日誌物件

    Returns:
        list[TicketInfo]: 符合條件的 Ticket 清單
    """
    target_version, target_wave = _extract_version_wave(target_ticket_id)
    if target_version is None:
        logger.warning("無法從 %s 提取版本和 Wave", target_ticket_id)
        return []

    # 掃描 Ticket 目錄
    tickets_dir = project_root / "docs" / "work-logs" / f"v{target_version}" / "tickets"
    if not tickets_dir.exists():
        logger.debug("Ticket 目錄不存在: %s", tickets_dir)
        return []

    active_tickets = []

    try:
        for ticket_file in tickets_dir.glob("*.md"):
            ticket_info = _process_ticket_file(
                ticket_file,
                target_ticket_id,
                target_version,
                target_wave,
                logger
            )
            if ticket_info:
                active_tickets.append(ticket_info)

    except Exception as e:
        logger.error("掃描 Ticket 目錄失敗: %s", e)
        return []

    return active_tickets


def detect_path_conflicts(where_files: list[str], other_files: list[str]) -> list[str]:
    """偵測兩組檔案清單之間的衝突

    衝突規則：
    - 完全相同
    - A 的前綴包含 B（目錄前綴）
    - B 的前綴包含 A（目錄前綴）

    Args:
        where_files: 第一組檔案清單（已規範化）
        other_files: 第二組檔案清單（已規範化）

    Returns:
        list[str]: 衝突的檔案（來自 where_files 的部分）
    """
    if not where_files or not other_files:
        return []

    conflicts = []

    for file_a in where_files:
        for file_b in other_files:
            # 完全相同
            if file_a == file_b:
                conflicts.append(file_a)
                break

            # 前綴匹配（A 是 B 的父目錄）
            if file_b.startswith(file_a + "/"):
                conflicts.append(file_a)
                break

            # 前綴匹配（B 是 A 的父目錄）
            if file_a.startswith(file_b + "/"):
                conflicts.append(file_a)
                break

    return conflicts


def _read_target_ticket(
    target_ticket_id: str,
    project_root: Path,
    logger: logging.Logger
) -> tuple[list[str], str | None] | tuple[None, None]:
    """讀取並提取目標 Ticket 的 where.files 和 parent_id

    Args:
        target_ticket_id: 派發目標的 Ticket ID
        project_root: 專案根目錄
        logger: 日誌物件

    Returns:
        tuple: (where_files, parent_id) 或 (None, None) 如果讀取失敗
    """
    try:
        target_file = find_ticket_file(target_ticket_id, project_root, logger)
        if not target_file:
            logger.warning("無法找到 Ticket 檔案: %s", target_ticket_id)
            return None, None

        target_frontmatter = parse_ticket_frontmatter(target_file, logger)
        if not target_frontmatter:
            return None, None

        target_where_files = _parse_ticket_files(target_frontmatter, logger)
        if not target_where_files:
            logger.debug("目標 Ticket %s 無 where.files", target_ticket_id)
            return None, None

        target_parent_id = target_frontmatter.get("parent_id")
        return target_where_files, target_parent_id

    except Exception as e:
        logger.error("讀取目標 Ticket %s 失敗: %s", target_ticket_id, e)
        return None, None


def _build_conflicts(
    target_ticket_id: str,
    target_where_files: list[str],
    target_parent_id: str | None,
    active_tickets: list[TicketInfo]
) -> list[ConflictInfo]:
    """建立衝突資訊清單

    Args:
        target_ticket_id: 派發目標 Ticket ID
        target_where_files: 目標 Ticket 的 where.files
        target_parent_id: 目標 Ticket 的 parent_id
        active_tickets: 同 Wave 活躍 Ticket 清單

    Returns:
        list[ConflictInfo]: 衝突清單
    """
    conflicts = []

    for ticket in active_tickets:
        conflicting_files = detect_path_conflicts(target_where_files, ticket.where_files)
        if not conflicting_files:
            continue

        conflict_type, is_parent_child, common_parent_id = _classify_conflict_type(
            target_ticket_id,
            target_parent_id,
            ticket.ticket_id,
            ticket.parent_id
        )

        conflicts.append(ConflictInfo(
            target_ticket_id=target_ticket_id,
            conflicting_ticket_id=ticket.ticket_id,
            conflicting_files=conflicting_files,
            is_parent_child=is_parent_child,
            conflict_type=conflict_type,
            common_parent_id=common_parent_id,
            target_parent_id=target_parent_id,
            other_parent_id=ticket.parent_id
        ))

    return conflicts


def find_file_ownership_conflicts(
    target_ticket_id: str,
    project_root: Path,
    logger: logging.Logger
) -> list[ConflictInfo]:
    """偵測目標 Ticket 與同 Wave 其他活躍 Ticket 的檔案所有權衝突

    Args:
        target_ticket_id: 派發目標的 Ticket ID
        project_root: 專案根目錄
        logger: 日誌物件

    Returns:
        list[ConflictInfo]: 衝突清單
    """
    # 讀取目標 Ticket
    target_where_files, target_parent_id = _read_target_ticket(
        target_ticket_id, project_root, logger
    )
    if target_where_files is None:
        return []

    # 掃描活躍 Ticket
    active_tickets = get_active_tickets(target_ticket_id, project_root, logger)
    if not active_tickets:
        logger.debug("無同 Wave 其他活躍 Ticket，無衝突")
        return []

    # 建立衝突清單
    conflicts = _build_conflicts(
        target_ticket_id,
        target_where_files,
        target_parent_id,
        active_tickets
    )

    # 篩選：如果有兄弟衝突，則過濾掉父子衝突
    # Hook 目的是檢查兄弟 Ticket 衝突，父子重疊不是主要關注
    if any(c.conflict_type == CONFLICT_TYPE_BROTHER for c in conflicts):
        conflicts = [c for c in conflicts if c.conflict_type != CONFLICT_TYPE_PARENT]

    return conflicts


def _format_conflict_details(conflicts: list[ConflictInfo]) -> list[str]:
    """格式化衝突詳細清單

    Args:
        conflicts: 衝突清單

    Returns:
        list[str]: 衝突詳細行清單
    """
    lines = []

    for idx, conflict in enumerate(conflicts, 1):
        lines.append(f"衝突 {idx}：同 Wave {conflict.conflict_type.lower()} Ticket")
        lines.append(f"  - 派發目標：{conflict.target_ticket_id}")
        lines.append(f"  - 衝突對象：{conflict.conflicting_ticket_id}")

        files_count = len(conflict.conflicting_files)
        lines.append(f"  - 衝突檔案（{files_count} 個）：")
        for file in conflict.conflicting_files:
            lines.append(f"    - {file}")

        if conflict.conflict_type == CONFLICT_TYPE_BROTHER:
            lines.append(f"  - 衝突類型：兄弟 Ticket（同父：{conflict.common_parent_id}）")
        elif conflict.conflict_type == CONFLICT_TYPE_UNRELATED:
            lines.append("  - 衝突類型：無關 Ticket（不同父）")
        else:
            lines.append("  - 衝突類型：父子 Ticket")

        lines.append("")

    return lines


def _format_action_items(conflicts: list[ConflictInfo]) -> list[str]:
    """格式化建議行動清單

    Args:
        conflicts: 衝突清單

    Returns:
        list[str]: 行動項目行清單
    """
    lines = [f"{MSG_ACTION_TITLE}：", "", "[檢查清單] 確認並解決衝突：", ""]

    for idx, conflict in enumerate(conflicts, 1):
        if conflict.conflict_type == CONFLICT_TYPE_BROTHER:
            lines.append(f"{idx}. 衝突 {idx} — 兄弟 Ticket （{conflict.conflicting_ticket_id}）：")
        elif conflict.conflict_type == CONFLICT_TYPE_UNRELATED:
            lines.append(f"{idx}. 衝突 {idx} — 無關 Ticket （{conflict.conflicting_ticket_id}）：")
        else:
            lines.append(f"{idx}. 衝突 {idx} — 父子 Ticket （允許重疊，已篩選）：")

        lines.append("")
        lines.append("   選項 A（推薦）：調整 where.files，移除與衝突對象重疊的檔案")
        lines.append("   選項 B（次選）：建立 blockedBy 依賴或調整派發順序")
        lines.append("   選項 C：合併任務（若兩個修改有邏輯聯繫）")
        lines.append("")

    return lines


def format_conflict_warning(
    target_ticket_id: str,
    conflicts: list[ConflictInfo]
) -> str:
    """格式化衝突警告訊息

    輸出結構：
    - 標題和分隔符
    - 衝突摘要
    - 衝突詳細清單
    - 建議行動
    - 決策指引

    Args:
        target_ticket_id: 派發目標 Ticket ID
        conflicts: 衝突清單

    Returns:
        str: 格式化後的警告訊息
    """
    if not conflicts:
        return ""

    lines = [
        MSG_WARNING_HEADER,
        MSG_WARNING_TITLE,
        MSG_WARNING_HEADER,
        "",
        f"Ticket {target_ticket_id} 派發前偵測到以下檔案所有權衝突：",
        "",
        f"{MSG_CONFLICT_ANALYSIS_TITLE}（{len(conflicts)} 個衝突）：",
        ""
    ]

    # 添加衝突詳情
    lines.extend(_format_conflict_details(conflicts))

    # 添加行動項目
    lines.extend(_format_action_items(conflicts))

    # 決策指引
    lines.append(f"{MSG_DECISION_TITLE}：")
    lines.append("  - 優先檢查 Ticket 內容，判斷修改是否真的有依賴")
    lines.append("  - 若修改獨立 → 調整 where.files 避免衝突")
    lines.append("  - 若修改有依賴 → 建立 blockedBy 或序列派發")
    lines.append("  - 如確認無誤，忽略此警告並繼續派發")
    lines.append("")
    lines.append(MSG_WARNING_HEADER)

    message = "\n".join(lines)

    # 長度控制（超過 2000 字元則截斷）
    max_length = 2000
    if len(message) > max_length:
        message = message[:max_length - 20] + "\n[訊息已截斷...]"

    return message


# ============================================================================
# Hook 生命週期
# ============================================================================


def _validate_input(
    input_data: dict,
    logger: logging.Logger
) -> str | None:
    """驗證輸入並提取目標 Ticket ID

    Args:
        input_data: Hook stdin JSON
        logger: 日誌物件

    Returns:
        str | None: 提取到的 Ticket ID，或 None
    """
    if not is_valid_trigger(input_data):
        logger.debug("非目標觸發（非 Agent 工具或 PreToolUse 事件）")
        return None

    target_ticket_id = extract_ticket_id(input_data)
    if not target_ticket_id:
        logger.debug("無法從派發指令中提取 Ticket ID")
        return None

    return target_ticket_id


def _generate_output(
    target_ticket_id: str,
    actionable_conflicts: list[ConflictInfo],
    logger: logging.Logger
) -> dict:
    """根據衝突結果產生 Hook 輸出

    Args:
        target_ticket_id: 派發目標 Ticket ID
        actionable_conflicts: 可操作衝突清單
        logger: 日誌物件

    Returns:
        dict: Hook 輸出 JSON
    """
    if actionable_conflicts:
        warning_msg = format_conflict_warning(
            target_ticket_id, actionable_conflicts
        )
        logger.warning(warning_msg)

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": warning_msg
            }
        }
    else:
        logger.debug("無衝突，靜默通過")
        return DEFAULT_OUTPUT


def main() -> int:
    """Hook 主函式

    流程：
    1. 初始化日誌
    2. 讀取和驗證輸入
    3. 執行衝突檢查
    4. 產生輸出
    5. 異常處理

    Returns:
        int: 退出碼（永遠 0，不阻塊派發）
    """
    logger = setup_hook_logging(HOOK_NAME)

    try:
        input_data = read_json_from_stdin(logger)

        target_ticket_id = _validate_input(input_data, logger)
        if not target_ticket_id:
            print(json.dumps(DEFAULT_OUTPUT))
            return 0

        logger.info("檢查 Ticket %s 的檔案所有權衝突", target_ticket_id)

        project_root = get_project_root()
        conflicts = find_file_ownership_conflicts(
            target_ticket_id, project_root, logger
        )

        # 篩選可操作的衝突（排除父子重疊）
        actionable_conflicts = [
            c for c in conflicts if not c.is_parent_child
        ]

        output = _generate_output(target_ticket_id, actionable_conflicts, logger)
        print(json.dumps(output, ensure_ascii=False))
        return 0

    except Exception as e:
        logger.critical("Hook 執行失敗: %s", e, exc_info=True)
        sys.stderr.write(f"[Hook Error] {HOOK_NAME}: {e}\n")
        print(json.dumps(DEFAULT_OUTPUT))
        return 0


if __name__ == "__main__":
    sys.exit(main())
