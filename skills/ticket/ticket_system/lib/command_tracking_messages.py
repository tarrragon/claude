"""
commands/ 批次 B 硬編碼字串集中化模組

本模組集中化 Batch 2 命令檔案中的硬編碼字串常數，包括：
- track_query.py
- track_board.py
- track_batch.py
- track_acceptance.py
- track_audit.py
- track_relations.py
- track.py
- migrate.py
- generate.py

統一管理所有使用者可見的訊息字串，避免重複定義和提高可維護性。
"""


# ============================================================================
# TrackQueryMessages - track_query.py 相關訊息
# ============================================================================

class TrackQueryMessages:
    """track_query.py 相關訊息常數"""

    # execute_summary 中的標題格式
    SUMMARY_TITLE = "[Summary] {version} ({completed}/{total} 完成)"

    # execute_version 中的標題格式
    VERSION_TITLE = "[Summary] {display_version} ({completed}/{total} 完成)"

    # execute_list 中的標題格式
    LIST_TITLE = "[List] {version} ({completed}/{total} 完成)"

    # execute_summary 中找不到 Tickets 的標題
    SUMMARY_NO_TICKETS_TITLE = "[Summary] {version} (0/0 完成)"

    # execute_version 中找不到 Tickets 的標題
    VERSION_NO_TICKETS_TITLE = "[Summary] {display_version} (0/0 完成)"

    # execute_list 中找不到 Tickets 的標題
    LIST_NO_TICKETS_TITLE = "[Summary] {version} (0/0 完成)"

    # execute_chain 中找不到 root 時的警告
    CHAIN_ROOT_NOT_FOUND_HINT = "   嘗試將本身視為 root 展開"

    # 無 Tickets 時的提示訊息
    NO_TICKETS_MESSAGE = "   沒有 Tickets"

    # YAML 格式錯誤訊息格式
    YAML_ERROR_FORMAT = "Ticket {ticket_id} 的 YAML 格式錯誤：{error}"

    # 跨版本未完成任務警告
    CROSS_VERSION_WARNING_HEADER = "[WARNING] 其他版本有未完成的 Ticket："
    CROSS_VERSION_WARNING_ITEM = "   v{version}: {pending} 個 pending, {in_progress} 個 in_progress"
    CROSS_VERSION_WARNING_HINT = "   使用 --version <version> 查看詳情"


# ============================================================================
# TrackBoardMessages - track_board.py 相關訊息
# ============================================================================

class TrackBoardMessages:
    """track_board.py 相關訊息常數"""

    # render_board_tree 中的標題格式
    TREE_TITLE_ALL = "TICKET TREE - v{version} (所有任務)"
    TREE_TITLE_INCOMPLETE = "TICKET TREE - v{version} (未完成任務)"

    # render_board_tree 中無任務時的文字
    NO_TASKS_TEXT = "(無任務)"

    # render_tree_node 中的 Wave 標題格式
    WAVE_TITLE_FORMAT = "{wave} ({count} tasks)"

    # render_board_unicode 中的標題
    UNICODE_BOARD_TITLE = "TICKET BOARD - v0.31.0 (W7)"

    # render_board_unicode 中的統計行標籤
    UNICODE_STATS_PENDING = "[待處理]"
    UNICODE_STATS_IN_PROGRESS = "[進行中]"
    UNICODE_STATS_COMPLETED = "[已完成]"
    UNICODE_STATS_BLOCKED = "[被阻塞]"
    UNICODE_STATS_TASKS_SUFFIX = "tasks"

    # render_board_unicode 中的欄標題
    UNICODE_HEADERS = ["PENDING", "IN_PROGRESS", "COMPLETED", "BLOCKED"]

    # render_board_unicode 中的圖例
    UNICODE_LEGEND_TITLE = "Legend:"
    UNICODE_LEGEND_PRIORITY_HIGH = "[P0] - Priority 0 (Urgent)    [P1] - Priority 1 (High)"
    UNICODE_LEGEND_PRIORITY_LOW = "[P2] - Priority 2 (Medium)    [P3] - Priority 3 (Low)"

    # render_board_ascii 中的標題
    ASCII_BOARD_TITLE = "TICKET BOARD"

    # render_board_ascii 中的欄標題
    ASCII_HEADER_ROW = "Status    | Count | Tickets"

    # execute_board 中的錯誤訊息前綴
    ERROR_RENDERING_BOARD_PREFIX = "Error rendering board:"


# ============================================================================
# TrackBatchMessages - track_batch.py 相關訊息
# ============================================================================

class TrackBatchMessages:
    """track_batch.py 相關訊息常數"""

    # _execute_batch_operation 中的操作頭訊息格式
    BATCH_OPERATION_HEADER = "[Batch {operation_name}] 處理 {count} 個 Ticket"

    # _process_batch_claim 中的成功訊息格式
    CLAIM_SUCCESS_FORMAT = "{ticket_id} 已接手"

    # _process_batch_complete 中的成功訊息格式
    COMPLETE_SUCCESS_FORMAT = "{ticket_id} 已完成"

    # _process_batch_complete 中的已完成訊息格式
    ALREADY_COMPLETE_FORMAT = "{ticket_id} 已完成"

    # _process_batch_complete 中的驗收條件錯誤格式
    ACCEPTANCE_INCOMPLETE_FORMAT = "{ticket_id} 有未完成的驗收條件 ({count} 項)"

    # _execute_batch_operation 中的成功訊息前綴
    OK_PREFIX = "[OK]"

    # 批量操作的優先操作類型
    VALID_OPERATION_CLAIM = "claim"
    VALID_OPERATION_COMPLETE = "complete"

    # YAML 解析錯誤訊息格式
    YAML_ERROR_FORMAT = "Ticket {ticket_id} 的 YAML 格式錯誤：{error}"


# ============================================================================
# TrackAcceptanceMessages - track_acceptance.py 相關訊息
# ============================================================================

class TrackAcceptanceMessages:
    """track_acceptance.py 相關訊息常數"""

    # execute_check_acceptance 中的狀態訊息（勾選時）
    ALREADY_CHECKED_INFO = "[Info] index {index} 已是勾選狀態"

    # execute_check_acceptance 中的狀態訊息（取消勾選時）
    ALREADY_UNCHECKED_INFO = "[Info] index {index} 已是未勾選狀態"

    # execute_check_acceptance 中的新狀態標籤前綴
    NEW_STATUS_PREFIX = "   新狀態:"

    # execute_check_acceptance 中的狀態文字
    STATUS_TEXT_CHECKED = "勾選"
    STATUS_TEXT_UNCHECKED = "取消勾選"

    # execute_append_log 中有效的區段清單
    VALID_SECTIONS = ["Problem Analysis", "Solution", "Test Results", "Execution Log"]

    # execute_append_log 中的有效值提示前綴
    VALID_VALUES_PREFIX = "   有效值:"

    # execute_append_log 中的時間戳標籤
    TIMESTAMP_PREFIX = "   時間戳:"

    # execute_append_log 中的內容標籤
    CONTENT_PREFIX = "   內容:"

    # execute_append_log 中執行日誌的時間戳格式
    LOG_TIMESTAMP_FORMAT = "- [{timestamp}] {content}"

    # execute_accept_creation 中的成功訊息格式
    ACCEPT_CREATION_SUCCESS_FORMAT = "[OK] {ticket_id} 建立後驗收已通過"

    # execute_accept_creation 中的已通過訊息格式
    ACCEPT_CREATION_ALREADY_ACCEPTED_FORMAT = "[Info] {ticket_id} 已通過建立後驗收"


# ============================================================================
# TrackAuditMessages - track_audit.py 相關訊息
# ============================================================================

class TrackAuditMessages:
    """track_audit.py 相關訊息常數"""

    # _format_audit_report 中的標題
    AUDIT_REPORT_TITLE = "[Acceptance Audit Report]"

    # _format_audit_report 中的基本資訊標籤
    AUDIT_TICKET_PREFIX = "Ticket:"
    AUDIT_TIME_PREFIX = "時間:"
    AUDIT_AUDITOR_NAME = "acceptance-auditor"
    AUDIT_AUDITOR_PREFIX = "驗收者:"

    # _format_audit_report 中的檢查結果標籤
    AUDIT_RESULTS_TITLE = "檢查結果:"

    # _format_audit_report 中的表格標題
    AUDIT_TABLE_HEADER_STEP = "| 檢查步驟 | 結果 | 說明 |"
    AUDIT_TABLE_SEPARATOR = "|---------|------|------|"

    # _format_audit_report 中的描述文字
    AUDIT_DESCRIPTION_SKIPPED = "跳過（無子任務）"
    AUDIT_DESCRIPTION_PASSED = "✓ 通過"
    AUDIT_DESCRIPTION_PASSED_WITH_WARNINGS = "⚠ 通過（有 {count} 項警告）"
    AUDIT_DESCRIPTION_FAILED = "✗ {issue}"

    # _format_audit_report 中的結論標籤
    AUDIT_CONCLUSION_TITLE = "結論:"
    AUDIT_RESULT_PREFIX = "驗收結果:"

    # _format_audit_report 中的失敗項標籤
    AUDIT_FAILED_TITLE = "失敗項:"

    # _format_audit_report 中的失敗項格式
    AUDIT_FAILED_ITEM_FORMAT = "  - {step}:{issue}"

    # _format_audit_report 中的警告項標籤
    AUDIT_WARNINGS_TITLE = "警告項:"

    # _format_audit_report 中的警告項格式
    AUDIT_WARNING_ITEM_FORMAT = "  - {step}:{warning}"

    # execute_audit 中的驗收檢查失敗訊息前綴
    AUDIT_CHECK_FAILED_PREFIX = "驗收檢查失敗："

    # execute_audit 中的驗收過程錯誤訊息前綴
    AUDIT_PROCESS_ERROR_PREFIX = "驗收過程出錯："


# ============================================================================
# TrackRelationsMessages - track_relations.py 相關訊息
# ============================================================================

class TrackRelationsMessages:
    """track_relations.py 相關訊息常數"""

    # execute_add_child 中已存在的子 Ticket 訊息
    CHILD_ALREADY_EXISTS_FORMAT = "[Info] {child_id} 已是 {parent_id} 的子 Ticket"

    # execute_add_child 中的父子關係標籤
    RELATION_PARENT_PREFIX = "   父 Ticket:"
    RELATION_CHILD_PREFIX = "   子 Ticket:"
    RELATION_OLD_PARENT_PREFIX = "   原父 Ticket:"
    RELATION_OLD_PARENT_SUFFIX = "(已更新)"

    # execute_phase 中有效的 Phase 值列表
    VALID_PHASES = [
        "Phase 0",
        "Phase 1",
        "Phase 2",
        "Phase 3a",
        "Phase 3b",
        "Phase 4",
    ]

    # execute_phase 中的有效值提示前綴
    PHASE_VALID_VALUES_PREFIX = "   有效值:"

    # execute_phase 中的 Phase 標籤
    PHASE_PREFIX = "   Phase:"

    # execute_phase 中的 Assignee 標籤
    PHASE_ASSIGNEE_PREFIX = "   Assignee:"

    # execute_agent 中的標題
    AGENT_SEPARATOR = "=" * 60

    # execute_agent 中的統計行標籤
    AGENT_IN_PROGRESS_LABEL = "進行中"
    AGENT_PENDING_LABEL = "待處理"
    AGENT_COMPLETED_LABEL = "已完成"
    AGENT_BLOCKED_LABEL = "被阻塞"

    # execute_agent 中的項目前綴
    AGENT_ITEM_PREFIX = "  -"


# ============================================================================
# TrackMessages - track.py 相關訊息
# ============================================================================

class TrackMessages:
    """track.py 相關訊息常數"""

    # help 文字（命令註冊時）
    HELP_CLAIM = "認領 Ticket"
    HELP_COMPLETE = "標記完成"
    HELP_RELEASE = "釋放 Ticket"
    HELP_SUMMARY = "快速摘要"
    HELP_QUERY = "查詢單一 Ticket"
    HELP_TREE = "顯示任務鏈樹狀結構"
    HELP_LIST = "列出 Tickets（支援狀態篩選）"
    HELP_CHAIN = "顯示完整任務鏈"
    HELP_FULL = "顯示 Ticket 完整內容"
    HELP_LOG = "顯示執行日誌"
    HELP_VERSION = "指定版本進度摘要"
    HELP_BATCH_CLAIM = "批量認領 Tickets"
    HELP_BATCH_COMPLETE = "批量完成 Tickets"
    HELP_SET_WHO = "設定 Ticket 的 who 欄位"
    HELP_SET_WHAT = "設定 Ticket 的 what 欄位"
    HELP_SET_WHEN = "設定 Ticket 的 when 欄位"
    HELP_SET_WHERE = "設定 Ticket 的 where 欄位"
    HELP_SET_WHY = "設定 Ticket 的 why 欄位"
    HELP_SET_HOW = "設定 Ticket 的 how 欄位"
    HELP_WHO = "查詢 Ticket 的 who 欄位"
    HELP_WHAT = "查詢 Ticket 的 what 欄位"
    HELP_WHEN = "查詢 Ticket 的 when 欄位"
    HELP_WHERE = "查詢 Ticket 的 where 欄位"
    HELP_WHY = "查詢 Ticket 的 why 欄位"
    HELP_HOW = "查詢 Ticket 的 how 欄位"
    HELP_AGENT = "查詢代理人的所有 Tickets"
    HELP_PHASE = "更新 Ticket 的 TDD Phase"
    HELP_CHECK_ACCEPTANCE = "勾選或取消勾選驗收條件"
    HELP_APPEND_LOG = "追加執行日誌到 Ticket"
    HELP_ACCEPT_CREATION = "標記 Ticket 建立後驗收已通過"
    HELP_ADD_CHILD = "建立 Ticket 父子關係"
    HELP_AUDIT = "執行驗收檢查"
    HELP_BOARD = "顯示樹狀看板視圖"
    HELP_TRACK = "追蹤 Ticket 狀態"

    # 命令參數 help 文字
    ARG_TICKET_ID = "Ticket ID"
    ARG_VERSION = "版本號（自動偵測）"
    ARG_PENDING = "只顯示待處理的 Tickets"
    ARG_IN_PROGRESS = "只顯示進行中的 Tickets"
    ARG_COMPLETED = "只顯示已完成的 Tickets"
    ARG_BLOCKED = "只顯示被阻塞的 Tickets"
    ARG_VERSION_STR = "版本號（如 0.31.0 或 v0.31.0）"
    ARG_VERSION_PARAM = "版本號（自動偵測）"
    ARG_ROOT_TICKET_ID = "根 Ticket ID"
    ARG_TICKET_IDS = "Ticket ID 列表（以逗號分隔）"
    ARG_VALUE = "新的值"
    ARG_AGENT_NAME = "代理人名稱（支援模糊匹配，如 parsley）"
    ARG_PHASE = "TDD Phase (Phase 0/1/2/3a/3b/4)"
    ARG_AGENT = "Agent 名稱"
    ARG_PARENT_ID = "父 Ticket ID"
    ARG_CHILD_ID = "子 Ticket ID"
    ARG_INDEX = "驗收條件索引（1 開始）"
    ARG_UNCHECK = "取消勾選（預設為勾選）"
    ARG_SECTION = "日誌區段 (Problem Analysis/Solution/Test Results/Execution Log)"
    ARG_CONTENT = "日誌內容"
    ARG_WAVE = "只顯示特定 Wave"
    ARG_STATUS = "篩選狀態（pending/in_progress/completed/blocked）"
    ARG_FORMAT = "輸出格式（table/ids/yaml，預設 table）"
    ARG_ALL = "顯示所有任務（包含已完成）"


# ============================================================================
# MigrateMessages - migrate.py 相關訊息
# ============================================================================

class MigrateMessages:
    """migrate.py 相關訊息常數"""

    # _extract_id_components 中的錯誤訊息
    INVALID_TICKET_ID_FORMAT = "[ERROR] Ticket ID 格式無效"

    # _migrate_single_ticket 中的預覽頭
    DRY_RUN_HEADER = "預覽遷移: {source_id} → {target_id}"

    # _migrate_single_ticket 中的標籤
    DRY_RUN_TITLE_PREFIX = "  標題:"
    DRY_RUN_STATUS_PREFIX = "  狀態:"

    # _load_migration_config 中的錯誤訊息
    CONFIG_FILE_NOT_FOUND = "[ERROR] 配置檔案不存在:"
    CONFIG_FORMAT_NOT_SUPPORTED = "[ERROR] 不支援的配置格式，請使用 .yaml 或 .json"
    CONFIG_FORMAT_INVALID = "[ERROR] 配置格式無效，應包含 'migrations' 欄位"
    MIGRATIONS_FIELD_NOT_LIST = "[ERROR] 'migrations' 應為清單"
    CONFIG_LOAD_FAILED = "[ERROR] 載入配置失敗:"

    # _batch_migrate 中的訊息
    MIGRATION_SUMMARY = "遷移摘要"

    # execute 中的錯誤訊息
    VERSION_NOT_SPECIFIED = "[ERROR] 無法自動偵測版本，請使用 --version 指定"
    MISSING_PARAMETERS = "[ERROR] 缺少必要參數: source_id 和 target_id"

    # _update_cross_references 中的成功訊息
    CROSS_REFERENCES_UPDATED = "[OK] 已更新 {count} 個 Ticket 的交叉引用"

    # 命令參數 help 文字
    ARG_SOURCE_ID = "來源 Ticket ID (格式: {version}-W{wave}-{seq})"
    ARG_TARGET_ID = "目標 Ticket ID (格式: {version}-W{wave}-{seq})"
    ARG_CONFIG = "批量遷移配置檔案 (.yaml 或 .json)"
    ARG_VERSION = "指定版本 (如不指定則自動偵測)"
    ARG_DRY_RUN = "預覽遷移結果，不實際執行"
    ARG_BACKUP = "遷移前備份（預設啟用）"
    ARG_NO_BACKUP = "停用備份"
    HELP_MIGRATE = "遷移 Ticket ID（支援單一和批量遷移）"


# ============================================================================
# BulkCreateMessages - bulk_create.py 相關訊息
# ============================================================================

class BulkCreateMessages:
    """bulk_create.py 相關訊息常數"""

    # execute 中的訊息
    HELP_BATCH_CREATE = "從模板 + 目標清單快速建立多個 Ticket"
    ARG_TEMPLATE = "使用的模板名稱（如 impl-parsley）"
    ARG_TARGETS = "目標清單，逗號分隔（如 'BookCard Widget,LibraryListPage'）"
    ARG_VERSION = "目標版本（如 0.31.0）"
    ARG_WAVE = "Wave 編號"
    ARG_PARENT = "父 Ticket ID（用於建立子任務）"
    ARG_DRY_RUN = "預演模式：只顯示摘要，不建立檔案"

    # _print_batch_summary 中的摘要標題
    BATCH_CREATE_SUMMARY_TITLE = "批次建立摘要"
    SUMMARY_TEMPLATE_PREFIX = "模板："
    SUMMARY_VERSION_PREFIX = "版本："
    SUMMARY_WAVE_PREFIX = "Wave："
    SUMMARY_TOTAL_PREFIX = "待建立："
    SUMMARY_MODE_DRY_RUN = "預演（不建立檔案）"
    SUMMARY_MODE_NORMAL = "實際建立"
    SUMMARY_MODE_PREFIX = "模式："

    # _print_batch_summary 中的待建立 Ticket 清單標題
    TICKETS_LIST_TITLE = "待建立 Ticket："
    TICKET_FORMAT = "  {seq:2d}. {id}: {title}"

    # _print_batch_result 中的完成訊息
    BATCH_CREATE_COMPLETE = "批次建立完成"
    RESULT_FORMAT = "成功: {created}/{total}  警告: {warned}/{total}  失敗: {failed}/{total}"

    # execute 中的錯誤訊息
    TEMPLATE_NOT_FOUND = "模板不存在：{template}"
    VERSION_NOT_DETECTED = "無法偵測版本"
    WAVE_INVALID = "Wave 編號無效"
    TARGETS_EMPTY = "目標清單為空"

    # _create_ticket_config 中的 what 欄位範本
    WHAT_TEMPLATE = "實作 {target}"

    # _print_batch_result 中的失敗項目標籤
    FAILED_ITEMS_TITLE = "失敗項目："

    # _print_batch_result 中的警告項目標籤
    WARNED_ITEMS_TITLE = "警告項目："


# ============================================================================
# GenerateMessages - generate.py 相關訊息
# ============================================================================

class GenerateMessages:
    """generate.py 相關訊息常數"""

    # execute 中的錯誤訊息
    PLAN_PARSE_FAILED = "Plan 解析失敗:"

    # execute 中的成功訊息格式
    TICKETS_SAVED_FORMAT = "已保存 {saved}/{total} 個 Tickets"

    # _print_generation_summary 中的標題
    GENERATION_SUMMARY_TITLE = "[Generation Summary]"

    # _print_generation_summary 中的標籤
    SUMMARY_PLAN_FILE_PREFIX = "Plan 檔案:"
    SUMMARY_GENERATED_COUNT_PREFIX = "生成 Tickets:"
    SUMMARY_GENERATED_COUNT_SUFFIX = "個"
    SUMMARY_MODE_PREFIX = "模式:"
    SUMMARY_MODE_DRY_RUN = "預演"
    SUMMARY_MODE_NORMAL = "正常"
    SUMMARY_TICKETS_LIST_TITLE = "Tickets 清單:"

    # _print_generation_summary 中的 Ticket 列表格式
    SUMMARY_TICKET_FORMAT = "   {id}:{title}"
    SUMMARY_TICKET_DETAILS_FORMAT = "      Wave: W{wave}, TDD:{phases}"
    SUMMARY_TICKET_DETAILS_NO_TDD = "無 TDD"

    # _save_tickets 中的錯誤訊息（使用 BACKUP_FAILED，但這裡保留以供參考）
    # 注：實際使用來自 WarningMessages.BACKUP_FAILED

    # register 中的命令 help 文字
    HELP_GENERATE = "從 Plan 檔案生成 Atomic Tickets"

    # register 中的命令參數 help 文字
    ARG_PLAN_FILE = "Plan 檔案路徑（Markdown 格式）"
    ARG_VERSION = "版本號（如 0.31.0）"
    ARG_WAVE = "基礎 Wave 編號"
    ARG_DRY_RUN = "預演模式（不實際建立檔案）"


# ============================================================================
# VersionShiftMessages - version_shift.py 相關訊息
# ============================================================================

class VersionShiftMessages:
    """version-shift 命令相關訊息常數"""

    # CLI 幫助信息
    HELP_VERSION_SHIFT = "將整個版本的 Ticket 遷移至新版本"
    ARG_FROM_VERSION = "來源版本號（無 v 前綴，如 0.1.0）"
    ARG_TO_VERSION = "目標版本號（無 v 前綴，如 0.2.0）"
    ARG_DRY_RUN = "預覽模式，不執行任何修改"
    ARG_NO_BACKUP = "跳過備份步驟（風險自負）"
    ARG_SKIP_TODOLIST = "不更新 todolist.yaml"

    # 步驟訊息
    STEP_VALIDATE = "[1/8] 前置驗證..."
    STEP_BACKUP = "[2/8] 備份原始目錄..."
    STEP_UPDATE_TICKETS = "[3/8] 更新 Ticket 版本欄位..."
    STEP_RENAME_TICKETS = "[4/8] 重新命名 Ticket 檔案..."
    STEP_CROSS_REFS = "[5/8] 更新跨版本交叉引用..."
    STEP_RENAME_DIR = "[6/8] 重新命名 worklog 目錄..."
    STEP_UPDATE_TODOLIST = "[7/8] 更新 todolist.yaml..."
    STEP_SUMMARY = "[8/8] 輸出操作摘要..."

    # 驗證訊息
    ERROR_INVALID_VERSION_FORMAT = "版本號格式無效：{version}（預期 N.N.N 格式）"
    ERROR_FROM_VERSION_NOT_EXISTS = "版本目錄不存在：docs/work-logs/v{version}/"
    ERROR_TO_VERSION_EXISTS = "目標版本目錄已存在：docs/work-logs/v{version}/，請先確認目標目錄內容"
    INFO_SAME_VERSION = "來源版本與目標版本相同（{version}），無需遷移"

    # 備份訊息
    BACKUP_SUCCESS = "備份完成：{path}"
    BACKUP_SKIP = "跳過備份步驟（已指定 --no-backup）"
    ERROR_BACKUP_FAILED = "備份失敗：{error}。操作已中止。如需跳過備份，請使用 --no-backup（風險自負）"

    # 處理訊息
    TICKETS_UPDATED = "處理 {count} 個 Ticket"
    TICKET_PARSE_ERROR = "跳過無法解析的檔案：{filename}"
    AUXILIARY_FILES_UPDATED = "附屬文件更新: {count} 個"
    CROSS_REFS_UPDATED = "跨版本引用更新: {count} 個"
    DIRECTORY_RENAMED = "docs/work-logs/v{from_version}/ → docs/work-logs/v{to_version}/"
    TODOLIST_FIELDS_UPDATED = "todolist.yaml 欄位更新: {count} 個"

    # 警告訊息
    WARNING_NO_TICKETS_DIR = "找不到 tickets/ 子目錄，跳過 Ticket 更新"
    WARNING_TODOLIST_NOT_EXISTS = "todolist.yaml 不存在，跳過版本記錄更新"
    WARNING_CURRENT_VERSION_MISMATCH = "當前版本號不匹配，todolist.yaml 的 current_version 未更新"

    # Dry-run 訊息
    DRY_RUN_HEADER = "[DRY-RUN] 以下為預計執行的操作（未實際修改任何檔案）："
    DRY_RUN_PLAN_TITLE = "版本遷移計畫："
    DRY_RUN_FROM = "  來源: {version}"
    DRY_RUN_TO = "  目標: {version}"
    DRY_RUN_TICKETS_PREVIEW = "Ticket 更新預覽（{count} 個）："
    DRY_RUN_AUXILIARY_PREVIEW = "附屬文件更新預覽："
    DRY_RUN_DIRECTORY_OPERATION = "目錄操作："
    DRY_RUN_TODOLIST_PREVIEW = "todolist.yaml 更新預覽："
    DRY_RUN_BACKUP = "備份：不執行（dry-run 模式）"
    DRY_RUN_FOOTER = "執行實際遷移請移除 --dry-run 旗標。"
    DRY_RUN_PREVIEW_ELLIPSIS = "（以及其他 {count} 個 Ticket）"

    # 摘要訊息
    SUMMARY_TITLE = "============================================================\nversion-shift 完成摘要\n============================================================"
    SUMMARY_FROM_VERSION = "來源版本: {version}"
    SUMMARY_TO_VERSION = "目標版本: {version}"
    SUMMARY_BACKUP_LOCATION = "備份位置: {path}"
    SUMMARY_RESULTS = "處理結果:"
    SUMMARY_TICKETS_UPDATED = "  Ticket 更新: {count} 個"
    SUMMARY_AUXILIARY_UPDATED = "  附屬文件更新: {count} 個"
    SUMMARY_CROSS_REFS_UPDATED = "  跨版本引用更新: {count} 個"
    SUMMARY_TODOLIST_UPDATED = "  todolist.yaml 欄位更新: {count} 個"
    SUMMARY_FILES_SKIPPED = "  跳過的檔案: {count} 個"
    SUMMARY_DIR_OPERATION = "目錄操作:"
    SUMMARY_SEPARATOR = "============================================================"


# ============================================================================
# 輔助函式
# ============================================================================

def format_msg(template: str, **kwargs) -> str:
    """
    格式化訊息範本

    Args:
        template: 包含 {placeholder} 的訊息範本
        **kwargs: 替換值字典

    Returns:
        格式化後的訊息字串

    Example:
        >>> format_msg(TrackQueryMessages.SUMMARY_TITLE, version="0.31.0", completed=5, total=10)
        "[Summary] 0.31.0 (5/10 完成)"
    """
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"缺少格式化參數: {e}")


__all__ = [
    "TrackQueryMessages",
    "TrackBoardMessages",
    "TrackBatchMessages",
    "TrackAcceptanceMessages",
    "TrackAuditMessages",
    "TrackRelationsMessages",
    "TrackMessages",
    "BulkCreateMessages",
    "MigrateMessages",
    "GenerateMessages",
    "format_msg",
]
