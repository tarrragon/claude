"""
commands/ 批次 A 硬編碼字串集中化模組

統一管理 handoff.py、lifecycle.py、resume.py、create.py、fields.py 中的硬編碼訊息。

此模組補充 messages.py，專門處理命令層級的具體訊息和提示文字。
"""

# 防止直接執行此模組
if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()

from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY


class HandoffMessages:
    """handoff.py 相關訊息"""

    # 格式和用法說明
    ID_FORMAT_EXPECTED = "預期格式: v{version}-W{wave}-{seq} 或 {version}-W{wave}-{seq}"
    ID_FORMAT_EXAMPLE = "範例: 0.31.0-W4-002 或 0.31.0-W4-002.1"

    # 版本偵測錯誤的詳細說明
    VERSION_ERROR_REASONS = "可能原因:"
    VERSION_ERROR_REASON_1 = "1. docs/work-logs 目錄中沒有版本目錄"
    VERSION_ERROR_REASON_2 = "2. 專案結構不完整"
    VERSION_ERROR_SOLUTION = "解決方案:"
    VERSION_ERROR_SOLUTION_1 = "使用 --version 參數指定版本"
    VERSION_ERROR_SOLUTION_EXAMPLE = "  /ticket handoff <id> --version v0.31.0"

    # Ticket 不存在錯誤的詳細說明
    TICKET_NOT_FOUND_REASONS = "可能原因:"
    TICKET_NOT_FOUND_REASON_1 = "1. 版本偵測錯誤（當前偵測版本: v{version}）"
    TICKET_NOT_FOUND_REASON_2 = "2. Ticket ID 格式錯誤"
    TICKET_NOT_FOUND_REASON_3 = "3. Ticket 尚未建立"
    TICKET_NOT_FOUND_SUGGESTIONS = "建議操作:"
    TICKET_NOT_FOUND_SUGGESTION_1 = "- 確認 Ticket ID 格式正確: v{version}-W{wave}-{seq}"
    TICKET_NOT_FOUND_SUGGESTION_2 = "- 手動指定版本: /ticket handoff {ticket_id} --version v{version}"
    TICKET_NOT_FOUND_SUGGESTION_3 = "- 使用 /ticket create 建立 Ticket"
    TICKET_NOT_FOUND_EXIT_CODE = "Exit code: 2 (執行中止)"

    # 多個任務選擇的訊息
    MULTIPLE_TASKS_FOUND = "發現多個進行中的任務："
    SELECT_TASK_PROMPT = "請選擇任務編號 (1-{count}，或 0 取消): "
    INVALID_SELECTION = "無效的選擇，請輸入 1 到 {count} 的數字"
    CANCELLED_OPERATION = "已取消操作"
    NO_IN_PROGRESS_TASKS = "目前沒有進行中的任務"
    NO_COMPLETED_TASKS = "目前沒有已完成的任務可供交接"
    MULTIPLE_COMPLETED_TASKS = "發現多個最近完成的任務，請指定要交接的 Ticket ID"
    SPECIFY_HANDOFF_USAGE = "  用法: /ticket handoff <ticket_id>"

    # 多個任務時無法選擇的錯誤
    MULTIPLE_TASKS_NO_INTERACTIVE = "發現多個進行中的任務，但無法在非互動環境下選擇"
    PLEASE_SPECIFY_TICKET_ID = "請明確指定 Ticket ID："
    SPECIFY_TICKET_USAGE = "  /ticket handoff --status <ticket_id>"
    IN_PROGRESS_TASKS = "進行中的任務："

    # Handoff 狀態顯示
    STATUS_HEADER_TICKET_ID = "Ticket ID: {ticket_id}"
    STATUS_HEADER_TITLE = "Title: {title}"
    STATUS_HEADER_STATUS = "Status: {status}"
    STATUS_HEADER_DEPTH = "Depth: {depth}"
    STATUS_CHAIN_INFO = "Chain Information:"
    STATUS_CHAIN_ROOT = "  Root: {root}"
    STATUS_CHAIN_PARENT = "  Parent: {parent}"
    STATUS_CHILDREN_COUNT = "Child Tickets ({count}):"
    STATUS_CHILD_ITEM = "  - {child_id}: {status}"
    STATUS_CHILD_NOT_FOUND = "  - {child_id}: (not found)"
    STATUS_OPTIONS = "Handoff Options:"
    STATUS_USE_TO_PARENT = "  Use: /ticket handoff {ticket_id} --to-parent"
    STATUS_USE_TO_CHILD = "  Use: /ticket handoff {ticket_id} --to-child {child_id}"
    STATUS_USE_TO_SIBLING = "  Use: /ticket handoff {ticket_id} --to-sibling {sibling_id}"
    STATUS_WAIT_DEPENDENCIES = "  Wait for dependencies to be satisfied"
    STATUS_NO_PENDING_TASKS = "  No pending tasks in chain - ready for completion"

    # 建議和命令提示
    RECOMMENDATION_PREFIX = "建議: {suggestion}"
    RECOMMENDATION_TITLE = "標題: {title}"
    RECOMMENDATION_REASON = "原因: {reason}"
    RECOMMENDATION_ENTER_CHILD = "進入子任務 {child_id}"
    RECOMMENDATION_SWITCH_SIBLING = "切換到兄弟任務 {sibling_id}"
    RECOMMENDATION_RETURN_PARENT = "返回父任務 {parent_id}"
    RECOMMENDATION_WAIT = "等待阻塞依賴完成"
    RECOMMENDATION_BLOCKED_BY = "阻塞來源: {blocked_by}"
    RECOMMENDATION_COMPLETED = "任務鏈 {root_id} 已完成"
    RECOMMENDATION_EXECUTE = "執行: {command}"
    RECOMMENDATION_EXECUTE_COMMENT_CHECK = "  # 查看阻塞任務狀態"
    RECOMMENDATION_EXECUTE_COMMENT_COMPLETE = "  # 標記完成"
    RECOMMENDATION_EXECUTE_WITH_COMMENT = "執行: {command}  {comment}"

    # Handoff 用法說明
    USAGE_HEADER = "用法:"
    USAGE_HANDOFF = "  /ticket handoff <id>"
    USAGE_TO_PARENT = "  /ticket handoff <id> --to-parent"
    USAGE_TO_CHILD = "  /ticket handoff <id> --to-child <child-id>"
    USAGE_TO_SIBLING = "  /ticket handoff <id> --to-sibling <sibling-id>"
    USAGE_STATUS = "  /ticket handoff --status"
    EXAMPLES_HEADER = "範例:"
    EXAMPLE_BASIC = "  /ticket handoff 0.31.0-W4-002"
    EXAMPLE_STATUS = "  /ticket handoff 0.31.0-W4-002 --status"
    EXAMPLE_STATUS_AUTO = "  /ticket handoff --status"

    # Command 線參數説明
    HELP_HEADER = "交接任務用法："
    HELP_TEXT = "任務交接 (Ticket 存在性強制檢查)"
    ARG_TICKET_ID_HELP = "Ticket ID (格式: {version}-W{wave}-{seq}，與 --status 配合時可省略)"
    ARG_TO_PARENT_HELP = "返回父任務"
    ARG_TO_CHILD_HELP = "切換到指定子任務"
    ARG_TO_SIBLING_HELP = "切換到兄弟任務"
    ARG_STATUS_HELP = "查看 handoff 狀態資訊"
    ARG_VERSION_HELP = "指定版本 (如不指定則自動偵測)"


class LifecycleMessages:
    """lifecycle.py 相關訊息"""

    # 自動 Handoff 完成提示
    AUTO_HANDOFF_SEPARATOR = SEPARATOR_PRIMARY
    AUTO_HANDOFF_HEADER = "[自動 Handoff 已完成]"
    AUTO_HANDOFF_NEXT_TASK = "下一步任務: {next_ticket_id}"
    AUTO_HANDOFF_NEXT_TASK_TITLE = "           [{next_title}]"
    AUTO_HANDOFF_CLEAR_PROMPT = ">>> 請執行 /clear 開始新對話 <<<"
    AUTO_HANDOFF_AUTO_LOAD = "新對話將自動載入任務 context"

    # Phase 前置條件警告
    PHASE_PREREQUISITE_WARNING_SEPARATOR = SEPARATOR_PRIMARY
    PHASE_PREREQUISITE_WARNING_HEADER = "[WARNING] Phase 前置條件未滿足"
    PHASE_PREREQUISITE_CURRENT = "Ticket {ticket_id} 屬於 {current_phase_label}"
    PHASE_PREREQUISITE_MISSING_HEADER = "缺失的前置 Phase："
    PHASE_PREREQUISITE_MISSING_ITEM = "  - {missing_label}"
    PHASE_PREREQUISITE_CORRESPONDING = "對應的 Ticket："
    PHASE_PREREQUISITE_CORRESPONDING_ID = "  - {ticket_id}"
    PHASE_PREREQUISITE_CORRESPONDING_TITLE = "    [{title}]"
    PHASE_PREREQUISITE_CORRESPONDING_STATUS = "    狀態：{status}"
    PHASE_PREREQUISITE_SUGGESTION = "建議先完成缺失的前置 Phase 再認領此 Ticket"

    # 認領檢查清單相關訊息
    CHECKLIST_DESIGN_DOCS = "   [ ] 已閱讀相關設計文件（功能規格、測試案例等）"
    CHECKLIST_ACCEPTANCE = "   [ ] 已理解驗收條件"
    CHECKLIST_DEV_ENV = "   [ ] 開發環境已準備就緒"
    CHECKLIST_ERROR_PATTERNS = "   [ ] 已查詢是否有相關的 error-patterns"
    CHECKLIST_SCOPE_VERIFICATION = "   [ ] 已獨立驗證 Ticket 描述的數量/範圍（描述是草稿，可能有遺漏）"
    CHECKLIST_EXECUTION_LOG = "   [ ] 完成時記得更新執行日誌（ticket track append-log）"
    CONFIRM_DEPENDENCIES = "   請確認這些依賴已完成後再開始"

    # Claim 操作的訊息
    CLAIM_CHECKING_PREREQUISITES = "檢查前置條件..."
    CLAIM_PHASE_PREREQUISITE_MISSING = "Phase 前置條件未滿足"
    CLAIM_PROCEED_ANYWAY = "是否仍要繼續認領? (y/n): "
    CLAIM_INVALID_INPUT = "無效的輸入，請輸入 y 或 n"
    CLAIM_CANCELLED = "已取消認領"

    # Complete 操作的訊息
    COMPLETE_CHECKING_ACCEPTANCE = "檢查驗收條件..."
    COMPLETE_UNFILLED_SECTIONS = "[WARNING] 以下執行日誌區段尚未填寫:"
    COMPLETE_SUGGESTION_HEADER = "建議使用以下命令填寫:"
    COMPLETE_PROCEED_ANYWAY = "是否確認已完成所有工作並提交驗收? (y/n): "
    COMPLETE_CANCELLED = "已取消完成"
    COMPLETE_INVALID_INPUT = "無效的輸入，請輸入 y 或 n"

    # Release 操作的訊息
    RELEASE_PROMPT = "是否確認釋放此 Ticket? (y/n): "
    RELEASE_CANCELLED = "已取消釋放"
    RELEASE_INVALID_INPUT = "無效的輸入，請輸入 y 或 n"


class ResumeMessages:
    """resume.py 相關訊息"""

    # 沒有待恢復任務
    NO_PENDING_RESUMPTIONS = "沒有待恢復的任務"

    # 恢復說明
    RESUME_INSTRUCTIONS = "使用以下命令恢復："
    RESUME_USAGE = "用法:"
    RESUME_EXAMPLES = "範例:"
    AVAILABLE_RESUMPTIONS = "可用的待恢復任務："

    # 恢復命令範例
    RESUME_EXAMPLE_CMD = "   /ticket resume <ticket_id>"
    RESUME_LIST_CMD = "   /ticket resume --list"
    RESUME_EXAMPLE_ID = "   /ticket resume 0.31.0-W4-001"

    # 幫助命令提示
    RESUME_HELP = "查看說明:"
    RESUME_HELP_CMD = "   uv run ticket resume --help"

    # Command 線參數說明
    HELP_HEADER = "恢復任務用法："
    HELP_TEXT = "從 handoff 恢復任務"
    ARG_TICKET_ID_HELP = "Ticket ID (格式: {version}-W{wave}-{seq}，與 --list 配合時可省略)"
    ARG_LIST_HELP = "列出所有待恢復的任務"
    ARG_VERSION_HELP = "指定版本 (如不指定則自動偵測)"

    # Resume 後 Checkpoint（標準化接手流程引導）
    CHECKPOINT_HEADER = "接手後的標準化步驟："
    CHECKPOINT_SCOPE_VERIFY = "   1. [ ] 獨立驗證 Ticket 描述的數量/範圍是否正確（PC-007）"
    CHECKPOINT_CLAIM_LABEL = "   2. 認領 Ticket："
    CHECKPOINT_CLAIM_CMD = "         ticket track claim {ticket_id}"
    CHECKPOINT_CHAIN_LABEL = "   3. （可選）查看任務鏈進度："
    CHECKPOINT_CHAIN_CMD = "         ticket track chain {ticket_id}"


class CreateMessages:
    """create.py 相關訊息"""

    # Create 完成後的檢查清單
    POST_CREATE_CHECKLIST = "建立後請確認:"
    PRE_START_CHECKLIST = "開始前請確認:"
    SA_REVIEW_NEEDED = "   [ ] 是否需要 SA 前置審查？（新功能/架構變更）"
    SPLIT_NEEDED = "   [ ] 是否需要拆分子任務？（認知負擔 > 10）"
    ACCEPTANCE_4V_CHECK = "   [ ] 驗收條件是否符合 4V 原則？"
    ACCEPTANCE_4V_DESC = "       （可驗證、可量化、可追溯、可記錄）"
    DEFAULT_ACCEPTANCE_WARNING = (
        "[WARNING] 使用預設驗收條件模板。請修改為具體、可量化的驗收標準。\n"
        "           使用 /ticket fields update <ticket-id> acceptance <criteria> 修改"
    )
    BLOCKED_BY_CHECK = "   [ ] 是否有需要設定的 blockedBy？"
    DECISION_TREE_CHECK = "   [ ] 是否已填寫 decision_tree_path 欄位？"
    DECISION_TREE_DESC = "       （派發驗證必需）"

    # Parallel 分析結果
    TASK_TYPE_LABEL = "任務類型: {task_type}"
    SUGGESTED_ORDER = "建議順序:"
    RATIONALE_LABEL = "理由: {rationale}"
    PARALLEL_GROUPS = "並行群組:"
    GROUP_LABEL = "   群組 {group_num}: {group_members}"
    CONFLICT_PAIRS = "衝突對:"
    CONFLICT_LABEL = "   {file_path}: {ticket_ids}"
    PARALLEL_RESULT = "分析結果: {result}"
    CANNOT_PARALLEL = "無法並行"
    CAN_PARALLEL = "可並行"

    # Create 用法和範例
    USAGE_HEADER = "用法:"
    USAGE_CREATE_ROOT = "  /ticket create --wave <wave>"
    USAGE_CREATE_CHILD = "  /ticket create --parent <parent-id>"
    USAGE_HELP = "  /ticket create --help"
    EXAMPLES_HEADER = "範例:"
    EXAMPLE_ROOT = "  /ticket create --wave 9"
    EXAMPLE_CHILD = "  /ticket create --parent 0.31.0-W9-001"

    # Command 線參數說明
    HELP_TEXT = "建立新 Ticket"
    ARG_WAVE_HELP = "建立根任務時指定 Wave 號 (必需)"
    ARG_PARENT_HELP = "建立子任務時指定父任務 ID"
    ARG_VERSION_HELP = "指定版本 (如不指定則自動偵測)"
    ARG_DRY_RUN_HELP = "預演模式，不實際建立檔案"
    ARG_NO_EDITOR_HELP = "不打開編輯器，使用預設內容"

    # Create 錯誤訊息
    INTERACTIVE_EDITOR_REQUIRED = "[Error] Create 命令需要互動式編輯器"
    NON_INTERACTIVE_USAGE = "在非互動環境中，請使用 --no-editor 選項"

    # Wave 計算相關訊息
    RECOMMENDED_WAVE = "建議使用 Wave: {wave_num}"
    WAVE_CALCULATION_REASON = "原因: {reason}"

    # decision_tree_path 驗證錯誤訊息（v0.1.1 新增）
    DECISION_TREE_MISSING_ALL = (
        "[ERROR] 缺少 decision_tree_path 必填欄位\n"
        "       請提供以下三個參數：\n"
        "         --decision-tree-entry    <進入決策樹的層級>\n"
        "         --decision-tree-decision <做出的決策>\n"
        "         --decision-tree-rationale <決策理由>\n"
        "\n"
        "       常見 entry 值：\n"
        "         - \"第三層:命令處理\" — PM 接收開發命令\n"
        "         - \"第三層半:執行中額外發現\" — 執行中發現需追蹤\n"
        "         - \"第五層:TDD\" — Phase 完成後建立後續 Ticket\n"
        "         - \"第六層:事件回應\" — 錯誤修復\n"
        "\n"
        "       範例：\n"
        "         /ticket create --wave 2 --action \"實作\" --target \"XXX\" \\\n"
        "           --decision-tree-entry \"第五層:TDD\" \\\n"
        "           --decision-tree-decision \"create-refactor-ticket\" \\\n"
        "           --decision-tree-rationale \"quality-baseline-rule-5\"\n"
        "\n"
        "       豁免條件（可省略）：子任務（--parent）或 DOC 類型（--type DOC）"
    )

    DECISION_TREE_MISSING_PARTIAL = (
        "[ERROR] decision_tree_path 欄位不完整\n"
        "       缺少：{missing_fields}\n"
        "       三個子欄位必須同時提供或同時省略\n"
        "\n"
        "       完整範例（三個參數都需要）：\n"
        "         /ticket create --wave 2 --action \"實作\" --target \"XXX\" \\\n"
        "           --decision-tree-entry \"進入點描述\" \\\n"
        "           --decision-tree-decision \"決策內容\" \\\n"
        "           --decision-tree-rationale \"決策原因\""
    )

    DECISION_TREE_EMPTY_VALUE = (
        "[ERROR] decision_tree_path 欄位值不能為空字串\n"
        "       欄位：{field_name}"
    )

    # 含糊驗收條件警告（W2-001.2 變更 1）
    VAGUE_ACCEPTANCE_WARNING = (
        "[WARNING] 驗收條件含有模糊詞彙，建議補充量化指標\n"
        "          模糊詞彙：{vague_words}\n"
        "          範例：「完成」→「新增 5 個測試案例」，「通過」→「100% 測試通過」"
    )

    # 認知負擔評估警告（W2-001.2 變更 4）
    COGNITIVE_LOAD_FILE_THRESHOLD_WARNING = (
        "[WARNING] 修改檔案數 > {threshold}，認知負擔可能超閾值，"
        "建議考慮拆分子任務"
    )
    COGNITIVE_LOAD_FILES_UNDEFINED_WARNING = (
        "[WARNING] 尚未填寫影響檔案清單（where_files），無法評估認知負擔。"
        "請使用 /ticket fields update <ticket-id> where <files> 補充"
    )

    # SRP 多目標偵測警告（W3-002）
    SRP_MULTI_TARGET_WARNING = (
        "[WARNING] what 欄位含連接詞「{conjunctions}」，疑似包含多個獨立目標\n"
        "          Atomic Ticket 原則：一個 Ticket = 一個 Action + 一個 Target\n"
        "          建議：考慮拆分為多個 Ticket，或確認目標確實是單一職責"
    )

    # SRP 跨模組驗收偵測警告（W3-002）
    SRP_CROSS_MODULE_WARNING = (
        "[WARNING] 驗收條件涉及多個模組（{modules}），疑似包含多個職責\n"
        "          Atomic Ticket 原則：所有驗收條件應指向同一目標\n"
        "          建議：確認是否需要拆分為多個獨立 Ticket"
    )

    # blockedBy 驗證錯誤訊息（Bug 1 修正）
    BLOCKED_BY_NOT_FOUND = "[ERROR] blockedBy 中的 {bid} 不存在，請確認 ID 是否正確"

    # 重複偵測警告訊息（W3-003）
    DUPLICATE_TICKETS_WARNING_HEADER = (
        "[WARNING] 發現 {count} 個可能重複的 Ticket，"
        "請確認是否需要建立新 Ticket："
    )
    DUPLICATE_TICKETS_WARNING_ITEM = "   - {ticket_id}: {title}"
    DUPLICATE_TICKETS_WARNING_ITEM_WITH_STATUS = "   - {ticket_id}: {title} [{status_label}]"
    DUPLICATE_TICKETS_WARNING_SUGGESTION = (
        "   建議：執行 /ticket track list 查看所有現有 Ticket 後再決定"
    )
    DUPLICATE_STATUS_LABEL_IN_PROGRESS = "進行中"
    DUPLICATE_STATUS_LABEL_COMPLETED = "已完成"

    # 問題 4 新增常數（0.1.2-W4-001.1）
    EXEMPTED_PARTIAL_PARAMS_ERROR = (
        "[ERROR] 豁免條件下三個參數必須全部提供或全部省略"
    )

    TICKET_LOCATION = "   Location: {ticket_path}"

    PARENT_UPDATED = "   Parent: {parent_id} (已更新 children)"


class FieldsMessages:
    """fields.py 相關訊息"""

    # 更新欄位的用法
    USAGE_HEADER = "用法:"
    USAGE_UPDATE = "  /ticket fields update <ticket-id> <field-name> <value>"
    USAGE_GET = "  /ticket fields get <ticket-id> <field-name>"
    USAGE_LIST = "  /ticket fields list <ticket-id>"
    USAGE_HELP = "  /ticket fields --help"

    # 更新欄位的範例
    EXAMPLES_HEADER = "範例:"
    EXAMPLE_UPDATE_TITLE = "  /ticket fields update 0.31.0-W4-001 title '新標題'"
    EXAMPLE_UPDATE_STATUS = "  /ticket fields update 0.31.0-W4-001 status in_progress"
    EXAMPLE_GET_TITLE = "  /ticket fields get 0.31.0-W4-001 title"
    EXAMPLE_LIST = "  /ticket fields list 0.31.0-W4-001"

    # Command 線參數說明
    HELP_TEXT = "管理 Ticket 欄位"
    ARG_OPERATION_HELP = "操作類型 (update, get, list)"
    ARG_TICKET_ID_HELP = "Ticket ID (格式: {version}-W{wave}-{seq})"
    ARG_FIELD_NAME_HELP = "欄位名稱 (適用於 update 和 get)"
    ARG_VALUE_HELP = "新欄位值 (適用於 update)"
    ARG_VERSION_HELP = "指定版本 (如不指定則自動偵測)"

    # Fields 的實際值顯示
    FIELD_VALUE_SEPARATOR = ": "
    NO_FIELDS_FOUND = "未找到任何欄位"


def format_msg(template: str, **kwargs) -> str:
    """
    格式化訊息。

    使用 Python 內建的 str.format() 方法，將 {} 佔位符替換為實際參數。

    Args:
        template: 訊息模板字串，包含 {} 佔位符用於參數替換
        **kwargs: 格式化參數（鍵必須與 template 中的佔位符相符）

    Returns:
        str: 格式化後的訊息

    Raises:
        KeyError: 若 kwargs 缺少 template 所需的參數

    Examples:
        >>> format_msg(HandoffMessages.TICKET_NOT_FOUND_REASON_1, version="0.31.0")
        '1. 版本偵測錯誤（當前偵測版本: v0.31.0）'
    """
    return template.format(**kwargs)
