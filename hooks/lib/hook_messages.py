"""
Hook 系統訊息常數模組 - 集中管理所有 Hook 的使用者訊息

統一管理 19 個 Hook 中的所有使用者訊息（阻擋訊息、警告訊息、建議訊息、狀態訊息）。
遵循 DRY 原則和 implementation-quality.md 1.3.1 節規範，消除硬編碼訊息。

訊息分類：
- CoreMessages: Hook 執行通用訊息
- GateMessages: 5 個 Gate Hook 阻擋訊息
- WorkflowMessages: 工作流指導訊息
- QualityMessages: 品質檢查訊息
- ValidationMessages: 驗證相關訊息
- ProcessSkipMessages: 流程省略相關訊息

注意：AskUserQuestionMessages/AskUserQuestionReminders 已提取至獨立模組
  → from lib.ask_user_question_reminders import AskUserQuestionReminders
  backward-compatible alias 仍在此模組可用（見下方）
"""

from lib.ask_user_question_reminders import AskUserQuestionReminders, AskUserQuestionMessages  # noqa: F401


class CoreMessages:
    """Hook 執行通用訊息 - 所有 Hook 共用"""

    HOOK_START = "{hook_name} 啟動"
    INPUT_EMPTY = "輸入為空，預設允許"
    JSON_PARSE_ERROR = "JSON 解析錯誤，預設允許: {error}"
    HOOK_ERROR = "Hook 執行錯誤，預設允許: {error}"
    HOOK_EXECUTION_FAILED = "Hook 執行錯誤: {error}"
    DEFAULT_ALLOW = "預設允許"


class GateMessages:
    """Gate Hook 阻擋訊息 - 5 個 gate hooks 使用

    包含：command-entrance-gate, acceptance-gate, creation-acceptance-gate,
    main-thread-edit-restriction, ticket-path-guard
    """

    # ========================================================================
    # Command Entrance Gate Hook
    # ========================================================================

    COMMAND_GATE_START = "Command Entrance Gate Hook 啟動（阻塞式）"
    COMMAND_GATE_COMPLETE = "Command Entrance Gate Hook 檢查完成：允許執行"
    COMMAND_GATE_BLOCKED = "Command Entrance Gate Hook：開發命令驗證失敗，阻止執行"

    TICKET_NOT_FOUND_ERROR = """錯誤：未找到待處理的 Ticket

為什麼阻止執行：
  開發命令必須有對應的 Ticket，確保工作可追蹤和驗收。

建議操作:
  1. 執行 `/ticket create` 建立新 Ticket
  2. 或執行 `/ticket track claim {id}` 認領現有 Ticket

詳見: .claude/rules/core/decision-tree.md
詳見: .claude/rules/forbidden/skip-gate.md"""

    TICKET_NOT_CLAIMED_ERROR = """錯誤：Ticket {ticket_id} 尚未認領

為什麼阻止執行：
  Ticket 必須被認領後才能開始工作，這確保任務責任清晰。

建議操作:
  1. 派發給對應代理人處理（推薦）
  2. 或執行 `/ticket track claim {ticket_id}` 親自認領
  3. 使用 `/ticket track query {ticket_id}` 查看詳細資訊

詳見: .claude/rules/core/decision-tree.md
詳見: .claude/rules/forbidden/skip-gate.md"""

    DECISION_TREE_MISSING_ERROR = """錯誤：Ticket {ticket_id} 缺少決策樹欄位

為什麼阻止執行：
  Ticket 必須包含決策樹路徑或決策過程，確保決策可追蹤。

建議操作:
  1. 編輯 Ticket 檔案，添加決策樹資訊：
     - 在 YAML frontmatter 中添加 decision_tree_path 欄位，或
     - 在內容中添加「## 決策樹」區段
  2. 使用 `/ticket track query {ticket_id}` 查看當前 Ticket
  3. 完成編輯後重新執行命令

詳見: .claude/rules/core/decision-tree.md
詳見: .claude/rules/forbidden/skip-gate.md"""

    TICKET_STATUS_UNKNOWN_ERROR = """錯誤：Ticket {ticket_id} 狀態不明 ({status})

為什麼阻止執行：
  Ticket 狀態應為 pending 或 in_progress，其他狀態不可執行操作。

建議操作:
  使用 `/ticket track query {ticket_id}` 查看詳細資訊，
  或聯繫專案管理員。

詳見: .claude/rules/flows/ticket-lifecycle.md"""

    TICKET_RELEVANCE_WARNING = """
============================================================
[WARNING] Ticket 關聯性警告
============================================================

當前 Ticket: {ticket_id}
Ticket 標題: {title}

您的命令可能與當前 Ticket 無關。
如果這是正確的 Ticket，請忽略此警告。
如果不是，請先建立或認領正確的 Ticket。

詳見: .claude/rules/forbidden/skip-gate.md

============================================================
"""

    # 子任務未完成錯誤訊息（acceptance-gate-hook.py）
    CHILDREN_INCOMPLETE_ERROR = """[ERROR] Acceptance Gate: 子任務未全部完成

Ticket: {ticket_id}
標題: {title}
未完成的子任務：
{incomplete_list}

請先完成所有子任務後再執行 complete。"""

    # 驗收記錄缺失警告訊息（acceptance-gate-hook.py）
    ACCEPTANCE_RECORD_MISSING_WARNING = """[WARNING] Acceptance Gate: 未找到驗收記錄

Ticket: {ticket_id} (type: {ticket_type})
標題: {title}
建議在 complete 前派發 acceptance-auditor 執行驗收。"""

    # 建立後品質驗收未通過錯誤訊息（creation-acceptance-gate-hook.py）
    CREATION_NOT_ACCEPTED_ERROR = """錯誤：Ticket {ticket_id} 尚未通過建立後品質驗收

為什麼阻止執行：
  Ticket 必須通過建立後品質驗收才能認領，確保 Task Summary 完整且 Solution 已評估並行化。

建議操作:
  1. 派發 acceptance-auditor 執行建立後品質驗收
  2. 驗收通過後執行 `ticket track accept-creation {ticket_id}`
  3. 再次執行 `ticket track claim {ticket_id}`

詳見: .claude/rules/flows/ticket-lifecycle.md（建立後品質驗收）"""

    CONTRADICTORY_STATE_WARNING = """[WARNING] Ticket {ticket_id} 存在矛盾狀態（in_progress + creation_accepted: false）

說明：
  此 Ticket 已被認領（status: in_progress），但建立後品質驗收尚未通過（creation_accepted: false）。
  此狀態通常發生在 Ticket 於建立審核機制加入前就已認領，系統允許繼續執行。

建議操作：
  執行 `ticket track accept-creation {ticket_id}` 修正矛盾狀態"""

    # ========================================================================
    # Main Thread Edit Restriction Hook
    # ========================================================================

    EDIT_ALLOWED = "編輯操作被允許"
    EDIT_RESTRICTED = "編輯操作受限"

    # ========================================================================
    # Ticket Path Guard Hook
    # ========================================================================

    TICKET_PATH_ALLOWED = "Ticket 路徑檢查通過，允許編輯"
    TICKET_PATH_DENIED = "Ticket 路徑檢查失敗，禁止編輯"


class WorkflowMessages:
    """工作流指導訊息 - 5 個工作流 hooks 使用

    包含：prompt-submit, external-query-guide, handoff-reminder,
    pre-fix-evaluation, handoff-prompt-reminder
    """

    # ========================================================================
    # External Query Guide Hook
    # ========================================================================

    EXTERNAL_QUERY_DETECTED = "檢測到 {tool_name} 調用，工作流指導已輸出，允許執行"

    EXTERNAL_QUERY_GUIDE = """
============================================================
[工作流指導] 外部資源查詢建議
============================================================

您正在使用 {tool_name} 執行外部資源查詢。

根據專案規範（skip-gate.md），外部資源研究應由
oregano-data-miner 代理人執行，以獲得更專業的蒐集
和整理。

推薦做法:
  1. 建立 Ticket 記錄外部查詢需求
  2. 派發 oregano-data-miner 執行查詢
  3. oregano-data-miner 完成資源蒐集和整理
  4. 回傳結果

好處:
  - 專業的資源蒐集和整理
  - 更好的上下文管理
  - 完整的執行記錄和追蹤
  - 遵循工作流規範

詳見: .claude/rules/forbidden/skip-gate.md
詳見: .claude/agents/oregano-data-miner.md

============================================================
"""

    # ========================================================================
    # Pre-Fix Evaluation Hook
    # ========================================================================

    PRE_FIX_EVAL_REQUIRED = """
============================================================
[強制] 修復前評估（Pre-Fix Evaluation）
============================================================

檢測到錯誤/失敗。根據專案規範，必須先執行修復前評估
以避免跳過 Skip-gate 防護機制。

強制執行步驟:
  1. 執行 `/pre-fix-eval`
  2. 派發 incident-responder 分析
  3. 建立對應 Ticket
  4. 對應代理人執行修復

詳見: .claude/rules/flows/incident-response.md
詳見: .claude/rules/forbidden/skip-gate.md

============================================================
"""


    # ========================================================================
    # CLI Failure Help Reminder Hook
    # ========================================================================

    CLI_FAILURE_HELP_REMINDER = """
============================================================
[PC-005 防護] CLI 失敗 - 先查語法再歸因
============================================================

偵測到 Bash 命令非零退出碼。

禁止基於假設歸因，必須依序調查：
  [Step 1] 查語法：執行 --help 或查閱 SKILL.md 確認完整語法
  [Step 2] 字面解讀：錯誤訊息的字面意義是什麼？
  [Step 3] 比對狀態：實際資料狀態是否符合工具預期？
  [Step 4] 歸因：排除語法和參數問題後，才考慮邏輯層原因

詳見: .claude/error-patterns/process-compliance/PC-005-cli-failure-assumption-attribution.md
============================================================
"""


class QualityMessages:
    """品質檢查訊息 - 5 個品質 hooks 使用

    包含：ticket-quality-gate, phase-completion-gate, file-type-permission,
    comment-qa, style-guardian
    """

    # ========================================================================
    # Ticket Quality Gate Hook
    # ========================================================================

    TICKET_QUALITY_CHECK_PASSED = "Ticket 品質檢查通過"
    TICKET_QUALITY_CHECK_FAILED = "Ticket 品質檢查失敗: {reason}"

    # ========================================================================
    # Phase Completion Gate Hook
    # ========================================================================

    PHASE_COMPLETION_CHECK_START = "Phase 完成檢查開始"
    PHASE_COMPLETION_CHECK_PASSED = "Phase 完成檢查通過"
    PHASE_COMPLETION_MISSING_SECTION = "Phase 完成檢查：缺少必要的 {section} 區段"
    PHASE_COMPLETION_EMPTY_SECTION = "Phase 完成檢查：{section} 區段為空（仍為 TODO）"

    # ========================================================================
    # File Type Permission Hook
    # ========================================================================

    FILE_EDIT_WARNING = "{category} 檔案編輯提示已發送，請確認後繼續"

    FILE_TYPE_WARNINGS = {
        "config": """
============================================================
[WARNING] 設定檔編輯提示
============================================================

您正在編輯設定檔（pubspec.yaml, analysis_options.yaml, .env 等）。

請確保：
  1. 修改符合專案設定規範
  2. 依賴版本已驗證相容性
  3. 測試環境已驗證通過

詳見: .claude/rules/core/implementation-quality.md

============================================================
""",
        "workflow": """
============================================================
[WARNING] 工作流檔編輯提示
============================================================

您正在編輯工作流檔（.github/workflows/ 等）。

請確保：
  1. 工作流邏輯正確
  2. 觸發條件已驗證
  3. 測試已完整通過

詳見：專案 CI/CD 設定文檔

============================================================
""",
        "docs": """
============================================================
[WARNING] 文件編輯提示
============================================================

您正在編輯文件檔。

請確保：
  1. 文件内容準確無誤
  2. 格式符合規範（禁用 emoji）
  3. 連結有效

詳見: .claude/rules/core/document-format-rules.md

============================================================
""",
    }

    # ========================================================================
    # Comment QA Hook
    # ========================================================================

    COMMENT_QA_CHECK = "Comment QA Hook 執行檢查"
    COMMENT_QA_ERROR = "Comment QA Hook 錯誤: {error}"

    # ========================================================================
    # Style Guardian Hook
    # ========================================================================

    STYLE_CHECK_PASSED = "程式碼風格檢查通過"
    STYLE_CHECK_WARNING = "程式碼風格警告: {issue}"


class ValidationMessages:
    """驗證相關訊息 - 4 個驗證 hooks 使用

    包含：worklog-format-check, doc-sync-check, mcp-run-tests-validator,
    pre-test-hook
    """

    # ========================================================================
    # Worklog Format Check Hook
    # ========================================================================

    WORKLOG_FORMAT_CHECK_PASSED = "工作日誌格式檢查通過"
    WORKLOG_FORMAT_CHECK_FAILED = "工作日誌格式檢查失敗: {reason}"

    # worklog-format-check.py 局部常數
    WORKLOG_FORMAT_WARNING_HEADER = "worklog-format-check: Warning"
    WORKLOG_EMOJI_DETECTED_MSG = "Detected emoji in markdown table cells."
    WORKLOG_PLAIN_TEXT_ADVICE = "Please use plain text status markers instead."

    # ========================================================================
    # Doc Sync Check Hook
    # ========================================================================

    DOC_SYNC_CHECK_PASSED = "文件同步檢查通過"
    DOC_SYNC_MISMATCH = """
============================================================
[WARNING] 文件同步不匹配
============================================================

偵測到文件版本不同步。

檢查清單:
  - CHANGELOG.md 已更新
  - docs/todolist.yaml 已更新
  - 相關工作日誌已更新

詳見: .claude/rules/core/document-system.md

============================================================
"""

    # doc-sync-check-hook.py 局部常數
    DOC_SYNC_HEADER_FORMAT = "=" * 60
    DOC_SYNC_TITLE = "[Doc-Flow] 五重文件系統狀態檢查"
    DOC_SYNC_WORKLOG_EXISTS = "[worklog] (v{version}): OK - 存在"
    DOC_SYNC_WORKLOG_MAIN_OK = "   主工作日誌: OK"
    DOC_SYNC_WORKLOG_MAIN_WARN = "   主工作日誌: WARN - 未找到"
    DOC_SYNC_WORKLOG_TICKETS = "   Tickets: {count} 個"
    DOC_SYNC_WORKLOG_NOT_EXISTS = "[worklog] (v{version}): WARN - 目錄不存在"
    DOC_SYNC_TODOLIST_EXISTS_PENDING = "[todolist.yaml]: OK - 有 {count} 個待處理項目"
    DOC_SYNC_TODOLIST_EXISTS_NONE = "[todolist.yaml]: OK - 無待處理項目"
    DOC_SYNC_TODOLIST_NOT_EXISTS = "[todolist.yaml]: WARN - 不存在"
    DOC_SYNC_ERROR_PATTERNS_EXISTS = "[error-patterns]: OK - {count} 個分類"
    DOC_SYNC_ERROR_PATTERNS_MODIFIED = "   最後更新: {time}"
    DOC_SYNC_ERROR_PATTERNS_NOT_EXISTS = "[error-patterns]: WARN - 不存在"
    DOC_SYNC_SUGGESTIONS_HEADER = "[建議操作]:"
    DOC_SYNC_INIT_WORKLOG = "建議執行 /doc-flow worklog init 初始化版本日誌"
    DOC_SYNC_CHECK_TODOLIST = "建議檢查 docs/todolist.yaml 是否需要初始化"

    # ========================================================================
    # MCP Run Tests Validator Hook
    # ========================================================================

    MCP_TESTS_VALIDATION_PASSED = "mcp__dart__run_tests 使用規範檢查通過"

    MCP_TESTS_ERROR_FULL_TEST_PATHS = (
        "mcp__dart__run_tests：禁止全量測試 (無 paths)。"
        "改用 `flutter test` 或 `./.claude/hooks/test-summary.sh`"
    )

    MCP_TESTS_ERROR_TOO_MANY_PATHS = (
        "mcp__dart__run_tests：paths 超過上限。"
        "大量測試改用 `./.claude/hooks/test-summary.sh`"
    )

    MCP_TESTS_ERROR_INVALID_PATHS = "mcp__dart__run_tests：提供的 paths 無效"

    MCP_TESTS_VALIDATION_FAILED = "mcp__dart__run_tests 使用規範檢查失敗: {reason}"

    # mcp-run-tests-validator.py 局部常數
    MCP_TESTS_ERROR_TITLE = "[ERROR] MCP run_tests 使用規範違規"
    MCP_TESTS_PROBLEM_HEADER = "問題描述:"
    MCP_TESTS_PROBLEM_DESC = (
        "mcp__dart__run_tests 在無 paths 參數時會執行全量測試，"
        "導致卡住超過 20 分鐘。必須指定 paths 限制測試範圍。"
    )
    MCP_TESTS_VIOLATION_HEADER = "違規詳情:"
    MCP_TESTS_CORRECT_HEADER = "[OK] 正確用法示例:"
    MCP_TESTS_EXAMPLE_1 = "1. 指定單一測試目錄:"
    MCP_TESTS_EXAMPLE_1_CODE = '   mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/domains/"]}])'
    MCP_TESTS_EXAMPLE_2 = "2. 指定多個測試目錄:"
    MCP_TESTS_EXAMPLE_2_CODE = '   mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/unit/core/", "test/unit/models/"]}])'
    MCP_TESTS_EXAMPLE_3 = "3. 指定單一測試檔案:"
    MCP_TESTS_EXAMPLE_3_CODE = '   mcp__dart__run_tests(roots: [{"root": "file:///path", "paths": ["test/domains/import/events_test.dart"]}])'
    MCP_TESTS_RECOMMENDED_HEADER = "[推薦方案]"
    MCP_TESTS_RECOMMENDED_1 = "  • 使用 ./.claude/hooks/test-summary.sh 執行全量測試"
    MCP_TESTS_RECOMMENDED_2 = "  • 或使用 flutter test --reporter compact 直接執行"
    MCP_TESTS_REFERENCE_HEADER = "[相關規範] FLUTTER.md 第 72-101 行"

    # ========================================================================
    # Pre-Test Hook
    # ========================================================================

    ENVIRONMENT_CHECK_STATUS_WITH_ISSUES = "環境檢查: {issue_count} 個問題"
    ENVIRONMENT_CHECK_STATUS_READY = "環境就緒"

    # pre-test-hook.py 局部常數 - Flutter SDK 檢查
    PRE_TEST_SDK_OK = "Flutter SDK 可用"
    PRE_TEST_SDK_ERROR = "Flutter SDK 回傳非零狀態碼"
    PRE_TEST_SDK_NOT_FOUND = "Flutter SDK 未安裝或不在 PATH 中"
    PRE_TEST_SDK_TIMEOUT = "Flutter SDK 版本檢查超時"

    # pre-test-hook.py 局部常數 - 依賴檢查
    PRE_TEST_PUBSPEC_LOCK_MISSING = "pubspec.lock 不存在，請執行 flutter pub get"
    PRE_TEST_PACKAGE_CONFIG_MISSING = ".dart_tool/package_config.json 不存在，請執行 flutter pub get"
    PRE_TEST_PUBSPEC_OUTDATED = "pubspec.yaml 比 pubspec.lock 更新，建議執行 flutter pub get"

    # pre-test-hook.py 局部常數 - 輸出訊息
    PRE_TEST_CHECK_HEADER = "[Pre-Test Check] 環境檢查發現問題:"
    PRE_TEST_ENV_READY = "環境就緒"
    PRE_TEST_ENV_CHECK_PREFIX = "環境檢查: "
    PRE_TEST_ENV_CHECK_SUFFIX = " 個問題"

    # ========================================================================
    # Test Timeout Pre Hook
    # ========================================================================

    TIMEOUT_CHECK_STARTED = "測試超時監控已啟動 (5/15/30 分鐘閾值)"

    # ========================================================================
    # Agent Ticket Validation Hook
    # ========================================================================

    AGENT_DISPATCH_VALIDATION_PASSED = "派發任務驗證通過"
    AGENT_DISPATCH_VALIDATION_FAILED = "派發任務驗證失敗"

    # ========================================================================
    # Bash Edit Guard Hook
    # ========================================================================

    BASH_EDIT_WARNING = "Bash 編輯操作警告已發送，允許執行"

    BASH_EDIT_DETAILED_WARNING = """[Bash Edit Guard] 警告: 偵測到使用 Bash 進行檔案編輯操作

檢測到的命令:
  {command}

建議: 請使用 Edit Tool 替代 Bash sed/awk，以獲得更好的權限控制和變更追蹤

詳情: 參考 .claude/agent-collaboration.md 的「工具使用強制規範」"""

    # ========================================================================
    # Other Hooks
    # ========================================================================

    SKILL_REGISTRATION_CHECK = "Skill 註冊檢查完成"

    L10N_SYNC_AUTO_EXECUTE = "偵測到 L10n 不同步，自動執行 flutter gen-l10n..."


class ProcessSkipMessages:
    """流程省略偵測訊息 - process-skip-guard-hook 使用

    包含 6 個省略類型各自的描述和完整流程說明。
    用於輸出 AskUserQuestionMessages.PROCESS_SKIP_REMINDER 的參數。
    """

    # ========================================================================
    # 省略類型 1：Phase 4 重構評估
    # ========================================================================

    SKIP_PHASE4_DESCRIPTION = "跳過 Phase 4 重構評估"
    SKIP_PHASE4_FULL_PROCESS = (
        "執行 Phase 4 重構評估（不可跳過，即使程式碼品質 A+ 也必須評估；"
        "可產出『無需重構』結論）"
    )

    # ========================================================================
    # 省略類型 2：SA 前置審查
    # ========================================================================

    SKIP_SA_REVIEW_DESCRIPTION = "跳過 SA 前置審查"
    SKIP_SA_REVIEW_FULL_PROCESS = (
        "派發 system-analyst 進行架構審查（新功能或架構變更必須執行，修復類可能不需要）"
    )

    # ========================================================================
    # 省略類型 3：派發代理人
    # ========================================================================

    SKIP_AGENT_DISPATCH_DESCRIPTION = "不派發代理人，主線程親自處理"
    SKIP_AGENT_DISPATCH_FULL_PROCESS = (
        "根據決策樹分類並派發對應代理人，"
        "確保工作責任清晰、並行化機制正常運作"
    )

    # ========================================================================
    # 省略類型 4：驗收檢查
    # ========================================================================

    SKIP_ACCEPTANCE_DESCRIPTION = "跳過驗收檢查"
    SKIP_ACCEPTANCE_FULL_PROCESS = (
        "派發 acceptance-auditor 執行完整驗收（標準驗收）或簡化驗收"
        "（任務範圍單純 或 DOC 類型）"
    )

    # ========================================================================
    # 省略類型 5：並行化評估
    # ========================================================================

    SKIP_PARALLEL_EVAL_DESCRIPTION = "跳過並行化評估（parallel-evaluation）"
    SKIP_PARALLEL_EVAL_FULL_PROCESS = (
        "執行 /parallel-evaluation 進行多視角掃描，識別併行可能性，"
        "確保決策樹第負一層並行化評估執行"
    )

    # ========================================================================
    # 省略類型 6：TDD 步驟
    # ========================================================================

    SKIP_TDD_PHASE_DESCRIPTION = "跳過 TDD 步驟"
    SKIP_TDD_PHASE_FULL_PROCESS = (
        "完成 TDD 四階段（Phase 1 功能設計 → Phase 2 測試設計 → "
        "Phase 3a 策略規劃 → Phase 3b 實作 → Phase 4 重構評估）"
    )


# ============================================================================
# Helper Functions
# ============================================================================


def format_message(template: str, **kwargs) -> str:
    """
    格式化訊息模板

    使用 Python 內建的 str.format() 方法，將 {{}} 佔位符替換為實際參數。

    Args:
        template: 訊息模板字串，包含 {{}} 佔位符用於參數替換
        **kwargs: 格式化參數（鍵必須與 template 中的佔位符相符）

    Returns:
        str: 格式化後的訊息

    Raises:
        KeyError: 若 kwargs 缺少 template 所需的參數

    Examples:
        >>> format_message(GateMessages.TICKET_NOT_CLAIMED_ERROR, ticket_id="0.31.0-W4-001")
        '錯誤：Ticket 0.31.0-W4-001 尚未認領\\n\\n為什麼阻止執行：...'
    """
    return template.format(**kwargs)


def format_multiline_block(lines: list[str], indent: str = "  ") -> str:
    """
    格式化多行區塊（如阻擋訊息的詳細說明）

    將多行文本轉換為縮進的區塊，便於顯示結構化訊息。

    Args:
        lines: 字串清單（每個元素為一行）
        indent: 縮進字串（預設 2 個空格）

    Returns:
        str: 格式化後的多行訊息（各行前加縮進）

    Examples:
        >>> lines = ["第一行", "第二行", "第三行"]
        >>> format_multiline_block(lines)
        '  第一行\\n  第二行\\n  第三行'
    """
    return "\n".join(f"{indent}{line}" for line in lines)


# ============================================================================
# Module Guard
# ============================================================================


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("[ERROR] 此檔案不支援直接執行")
    print("=" * 60)
    print()
    print("正確使用方式：")
    print("  from lib.hook_messages import CoreMessages, GateMessages")
    print("  message = CoreMessages.HOOK_START.format(hook_name='my-hook')")
    print()
    print("詳見各 Hook 檔案的使用範例")
    print("=" * 60)
    sys.exit(1)
