"""
標準化訊息定義模組

統一管理應用程式中的所有錯誤、警告和資訊訊息，遵循 DRY 原則。

消除訊息硬編碼，提供一致的訊息格式和內容。
"""
from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY
# 防止直接執行此模組
if __name__ == "__main__":
    import sys
    print(SEPARATOR_PRIMARY)
    print("[ERROR] 此檔案不支援直接執行")
    print(SEPARATOR_PRIMARY)
    print()
    print("正確使用方式：")
    print("  ticket track summary")
    print("  ticket track claim 0.31.0-W4-001")
    print()
    print("如尚未安裝，請執行：")
    print("  cd .claude/skills/ticket && uv tool install .")
    print()
    print("詳見 SKILL.md")
    print(SEPARATOR_PRIMARY)
    sys.exit(1)




class ErrorMessages:
    """錯誤訊息常數。"""

    TICKET_NOT_FOUND = "[Error] 找不到 Ticket {ticket_id}"
    NO_HANDOFF_FILE = "[Error] Ticket {ticket_id} 無待恢復的交接檔案"
    VERSION_NOT_DETECTED = "[Error] 無法偵測版本，請使用 --version 指定"
    INVALID_TICKET_ID = "[Error] Ticket ID 格式無效"
    INVALID_TICKET_ID_FORMAT = "[Error] 無效的 Ticket ID 格式: {ticket_id}"
    FILE_NOT_FOUND = "[Error] 檔案不存在: {path}"
    FILE_CREATION_FAILED = "[Error] 無法建立檔案: {error}"
    INVALID_OPERATION = "[Error] 未知操作: {operation}"
    MISSING_TICKET_ID = "[Error] 未提供 Ticket ID"
    NO_VALID_TICKETS = "[Error] 未提供有效的 Ticket ID"
    MISSING_FIELD_NAME = "[Error] 未指定欄位名稱"
    FIELD_NOT_FOUND = "[Error] {ticket_id} 無 '{field_name}' 欄位"
    MISSING_WAVE_PARAMETER = "[Error] 建立根任務必須指定 --wave"
    INVALID_SECTION = "[Error] 無效的 section: {section}"
    INVALID_PHASE_VALUE = "[Error] 無效的 Phase 值: {phase}"
    ACCEPTANCE_CRITERIA_PARSE_FAILED = "[Error] 無法解析 Acceptance Criteria 表格"
    ACCEPTANCE_CRITERIA_NOT_FOUND = "[Error] {ticket_id} 無 Acceptance Criteria 區段"
    BODY_CONTENT_NOT_FOUND = "[Error] {ticket_id} 無 body 內容"
    SECTION_NOT_FOUND = "[Error] {ticket_id} 無 '{section}' 區段"
    ACCEPTANCE_CRITERIA_INDEX_OUT_OF_RANGE = "[Error] index 超出範圍 (1-{max_index})，收到: {index}"
    ACCEPTANCE_CRITERIA_INDEX_NOT_INTEGER = "[Error] index 必須是整數，收到: {value}"
    ACCEPTANCE_CRITERIA_INDEX_NOT_POSITIVE = "[Error] index 必須是正整數，收到: {value}"
    INCOMPLETE_ACCEPTANCE_CRITERIA = "[Error] {ticket_id} 有未完成的驗收條件"
    STATUS_ERROR = "[Error] {status_msg}"
    TICKET_NOT_FOUND_IN_BATCH = "[Error] {ticket_id} 找不到"
    CHECK_ACCEPTANCE_ALL_WITH_INDEX = "[Error] --all 和 index 參數互斥，只能選擇其中之一"
    CHECK_ACCEPTANCE_MISSING_INDEX = (
        "[Error] 必須提供 index 或使用 --all 參數\n"
        "\n"
        "用法：\n"
        "  ticket track check-acceptance <id> --all          # 勾選全部驗收條件\n"
        "  ticket track check-acceptance <id> 1 2 3          # 勾選第 1、2、3 項\n"
        "  ticket track check-acceptance <id> 1 --uncheck    # 取消勾選第 1 項\n"
        "\n"
        "提示：先用 ticket track query <id> 查看驗收條件清單和編號"
    )


class WarningMessages:
    """警告訊息常數。"""

    TICKET_ALREADY_CLAIMED = "[Warning] {ticket_id} 已被接手"
    TICKET_ALREADY_COMPLETED = "[Warning] {ticket_id} 已完成"
    CANNOT_LOAD_TICKET = "[Warning] 無法載入 Ticket: {ticket_id}"
    TICKET_NOT_YET_CLAIMED = "[Warning] {ticket_id} 尚未被接手，無法釋放"
    TICKET_ALREADY_BLOCKED = "[Warning] {ticket_id} 已被阻塞，無法釋放"
    NO_BODY_CONTENT = "[Warning] Ticket {ticket_id} 沒有 body 內容"
    HANDOFF_UPDATE_FAILED = "[Warning] 無法更新 handoff 檔案（可能已不存在）"
    HANDOFF_ARCHIVE_FAILED = "[Warning] 無法歸檔 handoff 檔案到 archive/（檔案已不存在或權限問題）"
    NO_EXECUTION_LOG = "[Warning] Ticket {ticket_id} 找不到 Execution Log 區塊"
    NO_TICKETS = "[Warning] 無符合條件的 Tickets"
    BLOCKED_EXECUTION = "[BLOCKED] 找不到 Ticket: {ticket_id}"
    TICKET_CHAIN_ROOT_NOT_FOUND = "[Warning] Ticket {ticket_id} 無 chain.root 資訊"
    BACKUP_FAILED = "[WARNING] 備份失敗: {error}"
    BACKUP_SKIPPED = "[WARNING] 備份失敗，繼續遷移..."
    INVALID_MIGRATION_ITEM = "[WARNING] 跳過無效的遷移項目"
    MIGRATION_ITEM_INCOMPLETE = "[WARNING] 遷移項目缺少 'from' 或 'to'，已跳過"
    PARENT_UPDATE_FAILED = (
        "[Warning] 無法更新 Parent {parent_id} 的 children（子 Ticket {child_id} 已建立）\n"
        "   手動修復: 編輯父 Ticket 的 frontmatter，在 children 欄位加入 {child_id}\n"
        "   指令: ticket track add-child {parent_id} {child_id}"
    )
    BLOCKED_DEPENDENCIES = "[WARNING] 此 Ticket 有阻塞依賴:"
    CLAIMABLE_STATUS_WARNING = "[Warning] {error_msg}"
    SEQ_IGNORED_WITH_PARENT = "[提示] --seq {seq} 在子任務模式下被忽略，自動使用序號 {child_seq}"
    EXECUTION_LOG_NOT_FILLED = "[WARNING] 以下執行日誌區段尚未填寫:"
    EXECUTION_LOG_SUGGESTION = "建議使用以下命令填寫:"
    COMPLETED_NO_DIRECTION = "[Warning] {ticket_id} 已完成但無交接方向，請確認 handoff 設定"


class InfoMessages:
    """資訊訊息常數。"""

    TICKET_CLAIMED = "[OK] 已接手 {ticket_id}"
    TICKET_COMPLETED = "[OK] 已完成 {ticket_id}"
    TICKET_RELEASED = "[OK] 已釋放 {ticket_id}"
    HANDOFF_FILE_CREATED = "[OK] 已建立交接檔案: {path}"
    HANDOFF_NEXT_STEP = "[下一步] 請執行 /clear 清除對話，開始新的工作階段"
    HANDOFF_RESUMED = "Handoff 已接手，resumed_at 已更新"
    BATCH_CLAIM_RESULTS = "結果: {success}/{total} 成功"
    BATCH_COMPLETE_RESULTS = "結果: {success}/{total} 成功"
    TICKET_CREATED = "[OK] 已建立 Ticket: {ticket_id}"
    CHILD_RELATION_CREATED = "[OK] 已建立父子關係"
    PHASE_UPDATED = "[OK] {ticket_id} 的 phase 已更新"
    FIELD_UPDATED = "[OK] {ticket_id} 的 {field_name} 已更新"
    ACCEPTANCE_CRITERIA_UPDATED = "[OK] {ticket_id} index {index} 已{status_text}"
    LOG_APPENDED = "[OK] {ticket_id} 已追加日誌到 '{section}'"
    TICKET_MIGRATED = "[OK] 已遷移 Ticket: {source_id} → {target_id}"
    FILE_BACKED_UP = "[OK] 已備份: {path}"
    FILE_DELETED = "[OK] 已刪除舊檔案: {path}"


class SummaryMessages:
    """摘要訊息常數。"""

    SUMMARY_HEADER = "[Summary] {version} ({completed}/{total} 完成)"
    NO_TICKETS_MESSAGE = "   沒有 Tickets"
    BATCH_CLAIM_HEADER = "[Batch Claim] 處理 {count} 個 Ticket"
    BATCH_COMPLETE_HEADER = "[Batch Complete] 處理 {count} 個 Ticket"
    LIST_HEADER = "[List] {version} ({completed}/{total} 完成)"


class StatusMessages:
    """狀態訊息常數。"""

    STATUS_BLOCKED = "被阻塞"
    STATUS_CHANGE_BLOCKED = "狀態: 被阻塞"


class SectionHeaders:
    """區段標題常數。"""

    BASIC_INFO = "[基本資訊]"
    TASK_DESCRIPTION = "[任務描述]"
    TASK_CHAIN_INFO = "[任務鏈資訊]"
    FULL_CONTENT = "[完整內容]"
    TICKET_SYSTEM_INFO = "[Ticket 系統資訊]"
    PENDING_RESUME_LIST = "[待恢復任務清單]"
    COMPLETION = "[完成]"
    CREATION_CHECKLIST = "[建立檢查清單]"
    TDD_SEQUENCE_SUGGESTION = "[TDD 順序建議]"
    PARALLEL_ANALYSIS = "[並行分析]（子任務）"
    SUGGESTED_NEXT_STEP = "[建議下一步]"


class LifecycleMessages:
    """Ticket 生命週期相關訊息。"""

    TASK_CHAIN_COMPLETED = "任務鏈全部完成!"
    SUGGESTED_NEXT_STEP_LABEL = "建議下一步:"
    NO_SUGGESTED_NEXT = "無建議的下一步 Ticket"
    NO_SUGGESTED_REASON = "   可能原因：同 Wave 無待處理 Ticket，或需要開始新 Wave"
    PRE_START_CHECKLIST = "開始前請確認:"
    CHECKLIST_DESIGN_DOCS = "   [ ] 已閱讀相關設計文件（功能規格、測試案例等）"
    CHECKLIST_ACCEPTANCE = "   [ ] 已理解驗收條件"
    CHECKLIST_DEV_ENV = "   [ ] 開發環境已準備就緒"
    CHECKLIST_ERROR_PATTERNS = "   [ ] 已查詢是否有相關的 error-patterns"
    CHECKLIST_EXECUTION_LOG = "   [ ] 完成時記得更新執行日誌（ticket track append-log）"
    CONFIRM_DEPENDENCIES = "   請確認這些依賴已完成後再開始"


class AgentProgressMessages:
    """代理人進度相關訊息。"""

    AGENT_PROGRESS = "代理人進度: {agent_name}"
    NO_TICKETS = "無 Tickets"
    TICKETS_COUNT = "Tickets 總數: {count}"
    IN_PROGRESS = "進行中 ({count}):"
    PENDING = "待處理 ({count}):"
    COMPLETED = "已完成 ({count}):"
    BLOCKED = "被阻塞 ({count}):"


class MigrationMessages:
    """遷移命令相關訊息。"""

    DRY_RUN_HEADER = "[DRY-RUN] 將遷移 Ticket: {source_id} → {target_id}"
    BACKUP_LOCATION = "[INFO] 備份檔案位置: {path}"
    LOAD_MIGRATIONS = "[INFO] 載入 {count} 個遷移任務"
    MIGRATION_SUMMARY = "遷移摘要:"
    SUCCESS_COUNT = "  成功: {count}"
    FAIL_COUNT = "  失敗: {count}"
    SKIP_COUNT = "  跳過: {count}"


class GenerateMessages:
    """Generate 命令相關訊息。"""

    GENERATION_SUMMARY = "[Summary] 從 {plan_file} 生成 {count} 個 Tickets"
    TICKETS_PREVIEW = "預覽 Tickets ({mode} 模式):"
    TICKET_PREVIEW_LINE = "   {ticket_id}: {title}"
    TICKET_DETAILS = "      Wave: W{wave}, TDD: {phases}"
    TICKETS_SAVED = "[OK] 已保存 {saved}/{total} 個 Tickets"
    PLAN_PARSING_FAILED = "[Error] Plan 解析失敗: {error}"
    NO_TASKS_IN_PLAN = "[Error] Plan 中無任務項目"
    DRY_RUN_MODE = "[DRY-RUN] 預演模式，不實際建立檔案"


class ModuleMessages:
    """模組相關訊息。"""

    NOT_DIRECTLY_EXECUTABLE = "[ERROR] 此檔案不支援直接執行"
    HINT_NOT_EXECUTABLE = "[提示] 此模組不支援直接執行"
    CORRECT_USAGE = "正確使用方式："
    INSTALL_INSTRUCTION = "如尚未安裝，請執行："
    INSTALL_COMMAND = "  cd .claude/skills/ticket && uv tool install ."
    SEE_DOCS = "詳見 SKILL.md"


def format_error(template: str, **kwargs) -> str:
    """
    格式化錯誤訊息。

    使用 Python 內建的 str.format() 方法，將 {} 佔位符替換為實際參數。
    所有錯誤訊息應該使用 ErrorMessages 類別中的常數作為 template。

    Args:
        template: 訊息模板字串，包含 {} 佔位符用於參數替換
        **kwargs: 格式化參數（鍵必須與 template 中的佔位符相符）

    Returns:
        str: 格式化後的錯誤訊息（含 [Error] 前綴）

    Raises:
        KeyError: 若 kwargs 缺少 template 所需的參數

    Examples:
        >>> format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id="0.31.0-W4-001")
        '[Error] 找不到 Ticket 0.31.0-W4-001'
        >>> format_error(ErrorMessages.INVALID_TICKET_ID)
        '[Error] Ticket ID 格式無效'
    """
    return template.format(**kwargs)


def format_warning(template: str, **kwargs) -> str:
    """
    格式化警告訊息。

    使用 Python 內建的 str.format() 方法，將 {} 佔位符替換為實際參數。
    所有警告訊息應該使用 WarningMessages 類別中的常數作為 template。

    Args:
        template: 訊息模板字串，包含 {} 佔位符用於參數替換
        **kwargs: 格式化參數（鍵必須與 template 中的佔位符相符）

    Returns:
        str: 格式化後的警告訊息（含 [Warning] 前綴）

    Raises:
        KeyError: 若 kwargs 缺少 template 所需的參數

    Examples:
        >>> format_warning(WarningMessages.TICKET_ALREADY_CLAIMED, ticket_id="0.31.0-W4-001")
        '[Warning] 0.31.0-W4-001 已被接手'
        >>> format_warning(WarningMessages.NO_TICKETS)
        '[Warning] 無符合條件的 Tickets'
    """
    return template.format(**kwargs)


def format_info(template: str, **kwargs) -> str:
    """
    格式化資訊訊息。

    Args:
        template: 訊息模板（包含 {} 佔位符）
        **kwargs: 格式化參數

    Returns:
        str: 格式化後的訊息

    Examples:
        >>> format_info(InfoMessages.TICKET_CLAIMED, ticket_id="0.31.0-W4-001")
        '[OK] 已接手 0.31.0-W4-001'
    """
    return template.format(**kwargs)


def print_not_executable_and_exit():
    """統一的 __main__ guard 訊息輸出。"""
    import sys
    print(SEPARATOR_PRIMARY)
    print(ModuleMessages.NOT_DIRECTLY_EXECUTABLE)
    print(SEPARATOR_PRIMARY)
    print()
    print(ModuleMessages.CORRECT_USAGE)
    print("  ticket track summary")
    print("  ticket track claim 0.31.0-W4-001")
    print()
    print(ModuleMessages.INSTALL_INSTRUCTION)
    print(ModuleMessages.INSTALL_COMMAND)
    print()
    print(ModuleMessages.SEE_DOCS)
    print(SEPARATOR_PRIMARY)
    sys.exit(1)
