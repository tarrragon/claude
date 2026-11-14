#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

r"""
Ticket File Access Guard Hook - PreToolUse Hook

功能: 阻止直接 Edit frontmatter／Write ticket 檔案，引導使用 /ticket 指令
- 放行 Read ticket 檔案，並以 additionalContext 提示查詢建議用 ticket track full
  （讀檔不改資料；Edit body 前必須先 Read，阻擋 Read 會使 body 編輯實際做不到）
- 阻止 Edit frontmatter 欄位 -> 引導使用 /ticket track set-* 或 claim/complete
- 阻止 Write 建立/覆寫 ticket -> 引導使用 /ticket create
- 允許 ticket-tracker.py / ticket-creator.py 內部呼叫
- 允許 Edit 執行日誌區段 (## Problem Analysis, ## Solution 等 body 部分)

觸發時機: 執行 Read/Edit/Write 工具時

目標路徑:
  ^\.claude/tickets/.*\.md$
  ^docs/work-logs/.*/tickets/.*\.md$

行為:
  - Read ticket 檔案: 允許並附查詢建議（additionalContext），返回 exit code 0
  - Edit frontmatter: 阻止，返回 exit code 2
  - Edit body 區段: 允許，返回 exit code 0
  - 判定方式: 讀目標檔，old_string 任一出現位置落在 frontmatter（首兩條 --- 之間）
    即視為 frontmatter 編輯；讀檔失敗、無 frontmatter、找不到 old_string 時
    退回 is_body_section_edit 的字面判定
  - Write ticket 檔案: 阻止，返回 exit code 2（強制使用 /ticket create）
  - 內部呼叫: 允許，返回 exit code 0

設計理由:
  - ticket SKILL 使用 Python 直接 I/O 寫檔，不觸發 Claude Hook
  - 主線程直接使用 Write 工具會觸發 Hook，應被阻止
  - 這確保所有 Ticket 都透過 /ticket create 建立，編號正確
"""

import json
import os
import sys
import re
from pathlib import Path

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "hooks"))

from lib import (
    setup_hook_logging, run_hook_safely, get_project_root, save_check_log,
    read_json_from_stdin, emit_hook_output
)

from lib.checkout_identity import strip_root_prefix, strip_same_repo_checkout_prefix

from datetime import datetime
from typing import Dict, Any, Optional, Tuple

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0
EXIT_ALLOW = 0
EXIT_BLOCK = 2

# Ticket 檔案路徑模式
TICKET_PATH_PATTERNS = [
    r"^\.claude/tickets/.*\.md$",
    r"^docs/work-logs/.*/tickets/.*\.md$",
]

# 現行 body 章節：與 ticket_system/constants.py 的 CANONICAL_BODY_SECTIONS
# 逐項對應（本 hook 以 PEP 723 單檔執行，不 import ticket_system；一致性由
# 測試比對該常數守住）。
CANONICAL_BODY_SECTION_HEADINGS = [
    "## Task Summary",
    "## Problem Analysis",
    "## 重現實驗結果",
    "## Solution",
    "## Test Results",
    "## Context Bundle",
    "## NeedsContext",
    "## Exit Status",
    "## Spawn Requests",
    "## Completion Info",
]

# 舊版模板與中文別名的章節標題，存量票仍可能使用
LEGACY_BODY_SECTION_HEADINGS = [
    "## Execution Log",
    "## Notes",
    "## Phase",
    "## 問題分析",
    "## 解決方案",
    "## 測試結果",
    "## 執行日誌",
    "## 備註",
    "## 階段",
]

# 允許 Edit 的 body 區段標題（不含 frontmatter）
ALLOWED_BODY_SECTIONS = CANONICAL_BODY_SECTION_HEADINGS + LEGACY_BODY_SECTION_HEADINGS

# Read ticket 檔案時給模型的查詢建議（放行，不阻擋）
READ_QUERY_HINT = (
    "已放行讀取 ticket 檔案。查詢建議用 CLI："
    "ticket track full {id}（完整內容）、ticket track query {id}（摘要）、"
    "ticket track log {id}（執行日誌）。frontmatter 欄位以 ticket track set-* 修改。"
)

# Frontmatter 欄位模式
FRONTMATTER_FIELD_PATTERN = r"^(id|title|type|status|version|priority|parent_id|children|blockedBy|who|what|when|where|why|how|assigned|started_at|completed_at|created|updated):"


# ============================================================================
# 路徑和內容檢查
# ============================================================================

def normalize_path(file_path: str) -> str:
    """正規化檔案路徑為相對於專案根目錄的路徑

    絕對路徑會被轉換為相對於專案根目錄的路徑，使 TICKET_PATH_PATTERNS
    （以 ^docs/ 或 ^\\.claude/ 錨定）能正確比對。harness 系統指令要求 subagent
    一律使用絕對路徑，若不轉換則所有絕對路徑形式的 Read/Edit/Write 都會被
    is_ticket_file() 誤判為非 ticket 檔案而完全繞過本守衛（絕對路徑未轉換破口）。
    既有相對路徑（含 ./ 前綴）行為不變。
    """
    normalized = file_path.replace("\\", "/")

    project_root = str(get_project_root())
    # 根前綴剝除含磁碟機代號大小寫與目錄邊界；不在專案根之下時，同 repo 的
    # 相鄰 checkout（worktree）以該 checkout 根剝除，使其票檔同樣受本守衛管轄
    relative = strip_root_prefix(normalized, project_root)
    if relative is None:
        relative = strip_same_repo_checkout_prefix(file_path, project_root)
    if relative is not None:
        normalized = relative

    if normalized.startswith("./"):
        normalized = normalized[2:]

    return normalized


def is_ticket_file(file_path: str) -> bool:
    """檢查是否為 ticket 檔案"""
    normalized_path = normalize_path(file_path)

    for pattern in TICKET_PATH_PATTERNS:
        if re.match(pattern, normalized_path):
            return True

    return False


def is_internal_call() -> bool:
    """檢查是否為內部呼叫（透過環境變數）"""
    return os.getenv("TICKET_TRACKER_INTERNAL") == "1"


# 共用 lib.is_handoff_recovery_mode() 只檢查 pending 目錄有無任何 handoff，
# 命中即對所有 ticket 全域放行，範圍過廣（未恢復 handoff 為常態非例外，見
# Problem Analysis）。本檔改用 lib.get_handoff_recovery_ticket_ids（與兩支
# 派發守衛共用同一解析實作），將放行範圍收窄至該 handoff 實際指向的 ticket。

def extract_ticket_id_from_path(file_path: str) -> str:
    """從 ticket 檔案路徑萃取 ticket ID（檔名去除副檔名）"""
    return Path(file_path).stem


def is_body_section_edit(old_string: str, logger) -> bool:
    """
    檢查 Edit 操作是否為 body 區段編輯

    允許編輯的情況：
    - 編輯的內容是 body 區段標題後的內容
    - 不是 frontmatter 欄位
    """
    if not old_string:
        return False

    # 檢查是否在 frontmatter 區域（以 --- 開頭的區塊）
    stripped = old_string.strip()

    # 如果編輯的是 frontmatter 欄位
    if re.match(FRONTMATTER_FIELD_PATTERN, stripped):
        logger.debug(f"偵測到 frontmatter 欄位編輯: {stripped[:50]}")
        return False

    # 如果編輯的內容包含 body 區段標題，允許
    for section in ALLOWED_BODY_SECTIONS:
        if section in old_string:
            logger.debug(f"偵測到 body 區段編輯: {section}")
            return True

    # 如果是非 frontmatter 的一般內容，也允許（但記錄警告）
    # 這裡採用寬鬆策略：只阻止明確的 frontmatter 欄位編輯
    if ":" in stripped and stripped.split(":")[0].isalpha():
        # 可能是 frontmatter 欄位
        field_name = stripped.split(":")[0].strip()
        if field_name in ["id", "title", "type", "status", "version", "priority",
                          "parent_id", "children", "blockedBy", "who", "what",
                          "when", "where", "why", "how", "assigned", "started_at",
                          "completed_at", "created", "updated"]:
            return False

    # 其他情況視為 body 內容，允許編輯
    return True


def frontmatter_end_offset(content: str) -> Optional[int]:
    """回傳 frontmatter 區段結束位置（含收尾 --- 行）；無 frontmatter 時回傳 None。

    frontmatter 定義為檔案開頭 `---` 行到下一個 `---` 行之間（含兩條分隔線）。
    """
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None
    offset = len(lines[0])
    for line in lines[1:]:
        offset += len(line)
        if line.rstrip("\r\n") == "---":
            return offset
    return None


def old_string_overlaps_frontmatter(
    file_path: str, old_string: str, logger
) -> Optional[bool]:
    """依 old_string 在檔案中的實際位置判定是否觸及 frontmatter。

    回傳 True＝任一出現位置與 frontmatter 重疊；False＝全部出現位置都在
    frontmatter 之後；None＝無法判定（讀檔失敗、無 frontmatter、找不到
    old_string），由呼叫端退回字面判定。
    """
    if not old_string:
        return None
    path = Path(file_path)
    if not path.is_absolute():
        path = get_project_root() / normalize_path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"位置判定讀檔失敗，退回字面判定: {file_path}: {e}")
        return None

    fm_end = frontmatter_end_offset(content)
    if fm_end is None:
        logger.info(f"位置判定找不到 frontmatter，退回字面判定: {file_path}")
        return None

    start = content.find(old_string)
    if start < 0:
        logger.info(f"位置判定找不到 old_string，退回字面判定: {file_path}")
        return None
    while start >= 0:
        if start < fm_end:
            return True
        start = content.find(old_string, start + 1)
    return False


def is_new_file_write(file_path: str) -> bool:
    """檢查是否為新檔案寫入"""
    project_dir = get_project_root()
    full_path = project_dir / file_path
    return not full_path.exists()


# ============================================================================
# 權限檢查
# ============================================================================

def check_read_permission(file_path: str, logger) -> Tuple[bool, str]:
    """檢查 Read 操作權限。

    ticket 檔案一律放行：讀檔不改資料，cat／grep／ticket track full 皆可讀到
    同樣內容；且 Edit body 區段前必須先 Read，阻擋 Read 會使設計上放行的
    body 編輯實際做不到。查詢建議由 main 以 additionalContext 附上。
    """
    if is_internal_call():
        return True, "內部呼叫允許"

    if not is_ticket_file(file_path):
        return True, "非 ticket 檔案，允許讀取"

    logger.info(f"放行讀取 ticket 檔案（附查詢建議）: {file_path}")
    return True, "ticket 檔案允許讀取（查詢建議用 ticket track full）"


def check_edit_permission(file_path: str, old_string: str, logger) -> Tuple[bool, str]:
    """檢查 Edit 操作權限"""
    if is_internal_call():
        return True, "內部呼叫允許"

    if not is_ticket_file(file_path):
        return True, "非 ticket 檔案，允許編輯"

    # 先依 old_string 在檔案中的位置判定；無法判定時退回字面判定
    overlaps = old_string_overlaps_frontmatter(file_path, old_string, logger)
    if overlaps is False:
        logger.info(f"允許編輯 ticket body 區段（位置判定）: {file_path}")
        return True, "body 區段編輯允許"
    if overlaps is None and is_body_section_edit(old_string, logger):
        logger.info(f"允許編輯 ticket body 區段（字面判定）: {file_path}")
        return True, "body 區段編輯允許"

    # 阻止 frontmatter 欄位編輯
    reason = (
        "禁止直接編輯 ticket frontmatter 欄位。\n"
        "常用指令（完整清單見 `ticket track --help`）：\n"
        "  - /ticket track claim {id}       - 認領 ticket\n"
        "  - /ticket track complete {id}    - 完成 ticket\n"
        "  - /ticket track set-title {id} {value} - 更新 title（清單顯示用短標籤）\n"
        "  - /ticket track set-what {id} {value}  - 更新 what（完整任務敘述）\n"
        "  - /ticket track set-who {id} {value}   - 更新 who 欄位\n"
        "  - /ticket track set-priority {id} {value} - 更新優先級\n"
        "  - /ticket track append-log {id} --section {section} {content} - 追加執行日誌\n"
        "  - /ticket track set-where {id} ... - 更新 where（含 where.files 的 ::read／::write 後綴）\n"
        "  - ticket migrate - 變更 version／wave（隨 ID 一起遷移）\n"
        "\n"
        "判定依 old_string 在檔案中的位置：只要觸及 frontmatter（首兩條 --- 之間）即阻擋，\n"
        "body 章節內的編輯不受影響。\n"
        "若 `ticket track --help` 也找不到對應該欄位的命令，代表該欄位缺少合法\n"
        "更新途徑（PC-BAL-047）——請建 ticket 回報，不要繞道直接改檔。"
    )
    logger.warning(f"阻止編輯 ticket frontmatter: {file_path}")
    return False, reason


def check_write_permission(file_path: str, logger) -> Tuple[bool, str]:
    """檢查 Write 操作權限"""
    if is_internal_call():
        return True, "內部呼叫允許"

    if not is_ticket_file(file_path):
        return True, "非 ticket 檔案，允許寫入"

    # 完全阻止直接建立/覆寫 ticket
    # ticket 使用 Python 直接 I/O，不受此 Hook 影響
    # 這裡阻止的是主線程直接使用 Write 工具建立 ticket
    reason = (
        "禁止直接建立或覆寫 ticket 檔案。\n"
        "請使用以下指令建立新 Ticket：\n"
        "  ticket create --version X --wave Y --action \"動詞\" --target \"目標\"\n"
        "或使用 SKILL：\n"
        "  /ticket create ...\n"
        "\n"
        "這將確保編號正確且符合規範。\n"
        "\n"
        "若要修改既有 ticket 的內容，改用以下兩條途徑之一：\n"
        "  - 以 Edit 修改 body 章節內的文字（old_string 不觸及 frontmatter 即放行）\n"
        "  - ticket track append-log {id} --section <章節> --replace <內容>（整段覆寫指定章節）"
    )
    logger.warning(f"阻止直接 Write ticket 檔案: {file_path}")
    return False, reason


# ============================================================================
# Hook 輸出生成
# ============================================================================

def _emit_permission_output(
    is_allowed: bool, reason: str, additional_context: Optional[str] = None
) -> None:
    """輸出 Hook 決策 JSON（additional_context 給模型看的提示）

    放行時不帶 permissionDecision：allow 會略過平台的權限提示（例如工作目錄外
    的 Read），等於代用戶核可；本 hook 只負責擋 ticket 檔案的違規寫入，放行時
    交回平台權限流程。有提示才輸出 additionalContext，沒有提示則不輸出。
    """
    if is_allowed:
        if additional_context:
            emit_hook_output("PreToolUse", additional_context=additional_context)
        return
    emit_hook_output(
        "PreToolUse",
        additional_context=additional_context,
        permission_decision="deny",
        permission_decision_reason=reason,
    )


def read_hint_for(tool_name: str, file_path: str) -> Optional[str]:
    """Read ticket 檔案（非內部呼叫）時回傳查詢建議，其餘回傳 None。"""
    if tool_name != "Read" or is_internal_call() or not is_ticket_file(file_path):
        return None
    ticket_id = extract_ticket_id_from_path(file_path)
    return READ_QUERY_HINT.replace("{id}", ticket_id or "<id>")




# ============================================================================
# 主入口點
# ============================================================================

def main() -> int:
    """主入口點"""
    logger = setup_hook_logging("ticket-file-access-guard")
    try:
        logger.info("Ticket File Access Guard Hook 啟動")

        # 讀取 JSON 輸入
        input_data = read_json_from_stdin(logger)
        if not input_data:
            # fail-open：不輸出 decision，交回平台權限流程（不代為核可）
            logger.warning("輸入為空或解析失敗，不輸出決策（交回平台權限流程）")
            return EXIT_ALLOW

        logger.debug(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False)[:200]}...")

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input") or {}

        # 只檢查 Read, Edit, Write 工具
        if tool_name not in ["Read", "Edit", "Write"]:
            logger.debug(f"跳過: 工具類型 {tool_name} 不在檢查範圍內")
            _emit_permission_output(True, f"工具 {tool_name} 不在檢查範圍")
            return EXIT_ALLOW

        file_path = tool_input.get("file_path", "")
        logger.info(f"檢查工具: {tool_name}, 檔案: {file_path}")

        # 根據工具類型檢查權限
        if tool_name == "Read":
            is_allowed, reason = check_read_permission(file_path, logger)
        elif tool_name == "Edit":
            old_string = tool_input.get("old_string", "")
            is_allowed, reason = check_edit_permission(file_path, old_string, logger)
        elif tool_name == "Write":
            is_allowed, reason = check_write_permission(file_path, logger)
        else:
            is_allowed, reason = True, "未知工具類型，預設允許"

        _emit_permission_output(
            is_allowed, reason, additional_context=read_hint_for(tool_name, file_path)
        )

        log_entry = f"""[{datetime.now().isoformat()}]
  Tool: {tool_name}
  FilePath: {file_path}
  Permission: {"ALLOWED" if is_allowed else "BLOCKED"}
  Reason: {reason}

"""
        save_check_log("ticket-file-access-guard", log_entry, logger)

        exit_code = EXIT_ALLOW if is_allowed else EXIT_BLOCK
        logger.info(f"Hook 檢查完成，exit code: {exit_code}")
        return exit_code

    except Exception as e:
        # fail-open：不輸出 decision，交回平台權限流程；stderr + 日誌雙通道（規則 4）
        logger.error(f"Hook 執行錯誤: {type(e).__name__}: {e}", exc_info=True)
        sys.stderr.write(
            f"[ticket-file-access-guard] Hook 執行錯誤，未判定即放行（交回平台權限流程）: "
            f"{type(e).__name__}: {e}\n"
        )
        return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "ticket-file-access-guard"))
