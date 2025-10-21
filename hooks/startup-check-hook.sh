#!/bin/bash

# startup-check-hook.sh
# SessionStart Hook: 自動執行啟動檢查流程

# 載入通用函數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 設定專案環境
if ! setup_project_environment; then
    echo "錯誤: 無法設定專案環境" >&2
    exit 1
fi

# 設定日誌檔案
LOG_FILE="$CLAUDE_LOGS_DIR/startup-$(date +%Y%m%d_%H%M%S).log"

# 確保日誌目錄存在 (已在 setup_project_environment 中處理)

# SessionStart 時總是執行清理 (因為是新會話開始)
"$SCRIPT_DIR/cleanup-hook-logs.sh" >/dev/null 2>&1 &

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 SessionStart Hook: 開始執行啟動檢查"

# 1. Git 環境檢查
log "📊 Git 環境檢查"
cd "$CLAUDE_PROJECT_DIR"

# 檢查 Git 狀態
git fetch origin &>/dev/null
GIT_STATUS=$(git status --porcelain)
CURRENT_BRANCH=$(git branch --show-current)
COMMIT_COUNT=$(git log --oneline -3 | wc -l)

if [ -n "$GIT_STATUS" ]; then
    log "⚠️  工作目錄有未提交變更"
else
    log "✅ 工作目錄乾淨"
fi

log "📍 當前分支: $CURRENT_BRANCH"
log "📝 最近提交數: $COMMIT_COUNT"

# 2. 專案檔案載入確認
log "📁 專案檔案載入確認"
KEY_FILES=(
    "CLAUDE.md"
    "docs/todolist.md"
    "pubspec.yaml"
    ".claude/tdd-collaboration-flow.md"
    ".claude/document-responsibilities.md"
)

for file in "${KEY_FILES[@]}"; do
    if [ -f "$CLAUDE_PROJECT_DIR/$file" ]; then
        log "✅ $file 存在"
    else
        log "❌ $file 缺失"
    fi
done

# 3. 開發狀態檢查
log "🔧 開發狀態檢查"

# 檢查 Flutter 依賴項
if [ -f "$CLAUDE_PROJECT_DIR/pubspec.lock" ]; then
    log "✅ pubspec.lock 存在，依賴項已解析"
else
    log "⚠️  pubspec.lock 不存在，可能需要執行 flutter pub get"
fi

# 檢查 .dart_tool 目錄
if [ -d "$CLAUDE_PROJECT_DIR/.dart_tool" ]; then
    log "✅ .dart_tool 目錄存在"
else
    log "⚠️  .dart_tool 目錄不存在，可能需要執行 flutter pub get"
fi

# 檢查當前版本 (從 pubspec.yaml)
if [ -f "$CLAUDE_PROJECT_DIR/pubspec.yaml" ]; then
    CURRENT_VERSION=$(grep '^version:' "$CLAUDE_PROJECT_DIR/pubspec.yaml" | sed 's/version: *//')
    if [ -n "$CURRENT_VERSION" ]; then
        log "📦 當前版本: $CURRENT_VERSION"
    else
        log "📦 版本未在 pubspec.yaml 中定義"
    fi
fi

# 檢查最新工作日誌
LATEST_WORKLOG=$(ls "$CLAUDE_PROJECT_DIR/docs/work-logs/" 2>/dev/null | grep '^v[0-9]' | sort -V | tail -1)
if [ -n "$LATEST_WORKLOG" ]; then
    log "📋 最新工作日誌: $LATEST_WORKLOG"
else
    log "⚠️  未找到工作日誌檔案"
fi

# 4. 專案規範文檔檢查
log "📋 專案規範文檔檢查"

# 檢查 Flutter 專案檔案
if [ -f "pubspec.yaml" ]; then
    log "✅ pubspec.yaml 存在 (Flutter 專案)"
else
    log "❌ pubspec.yaml 缺失"
fi

if [ -f "docs/README.md" ]; then
    log "✅ docs/README.md 存在 (文檔導引)"
else
    log "❌ docs/README.md 缺失"
fi

# 核心規範文檔
CORE_DOCS=(
    "docs/app-requirements-spec.md"
    "docs/app-use-cases.md"
    "docs/ui_design_specification.md"
    "docs/test-pyramid-design.md"
    "docs/code-quality-examples.md"
    "docs/app-error-handling-design.md"
    "test/TESTING_GUIDELINES.md"
    "docs/domain-transformation-layer-design.md"
    "docs/data-mapper-architecture-specification.md"
    "docs/json-serialization-specification.md"
    "docs/value-objects-serialization-catalog.md"
    "docs/database-domain-mapping-verification.md"
    "docs/event-driven-architecture-design.md"
    "docs/event-driven-architecture.md"
)

MISSING_CORE_DOCS=0
for doc in "${CORE_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        log "✅ $doc 存在"
    else
        log "⚠️  $doc 缺失"
        MISSING_CORE_DOCS=$((MISSING_CORE_DOCS + 1))
    fi
done

# 架構與開發文檔
ARCH_DOCS=(
    "docs/event-driven-architecture-design.md"
    "docs/i18n_guide.md"
    "docs/terminology-dictionary.md"
)

MISSING_ARCH_DOCS=0
for doc in "${ARCH_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        log "✅ $doc 存在"
    else
        log "🔍 $doc 缺失 (可選)"
        MISSING_ARCH_DOCS=$((MISSING_ARCH_DOCS + 1))
    fi
done

# 文檔合規性摘要
if [ $MISSING_CORE_DOCS -eq 0 ]; then
    log "🎯 核心規範文檔完整 (0/${#CORE_DOCS[@]} 缺失)"
else
    log "⚠️  核心規範文檔不完整 ($MISSING_CORE_DOCS/${#CORE_DOCS[@]} 缺失)"
fi

# 5. 終端環境檢查
log "🖥️  終端環境已準備就緒"

# 6. 工作評估與建議
log "🎯 工作評估與下一步建議"

# 檢查 todolist.md 狀態
if [ -f "$CLAUDE_PROJECT_DIR/docs/todolist.md" ]; then
    TODO_ITEMS=$(grep -c "^-" "$CLAUDE_PROJECT_DIR/docs/todolist.md" 2>/dev/null || echo "0")
    log "📋 TodoList 項目數: $TODO_ITEMS"

    # 檢查是否有進行中的任務
    ACTIVE_TASKS=$(grep -c "🔄\|進行中\|in_progress" "$CLAUDE_PROJECT_DIR/docs/todolist.md" 2>/dev/null || echo "0")
    if [ "$ACTIVE_TASKS" -gt 0 ]; then
        log "⚡ 發現 $ACTIVE_TASKS 個進行中任務"
    fi
else
    log "⚠️  TodoList 檔案不存在"
fi

# 分析最新工作日誌狀態
if [ -n "$LATEST_WORKLOG" ]; then
    WORKLOG_PATH="$CLAUDE_PROJECT_DIR/docs/work-logs/$LATEST_WORKLOG"

    # 檢查工作日誌是否標記為完成
    if grep -q "版本交付\|🚀 版本交付\|## 🚀" "$WORKLOG_PATH" 2>/dev/null; then
        log "✅ 最新工作日誌已完成，建議評估版本推進"
        log "💡 建議行動: 執行 /smart-version-check 或檢視 todolist 下一個任務"
    elif grep -q "進行中\|開發中\|實作中" "$WORKLOG_PATH" 2>/dev/null; then
        log "🔄 最新工作日誌顯示工作進行中"
        log "💡 建議行動: 繼續完成當前工作日誌中的任務"
    else
        log "📋 最新工作日誌狀態不明確"
        log "💡 建議行動: 檢查工作日誌並確認當前狀態"
    fi

    # 檢查工作日誌的最後修改時間
    LAST_MODIFIED=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$WORKLOG_PATH" 2>/dev/null || echo "未知")
    log "⏰ 工作日誌最後修改: $LAST_MODIFIED"
else
    log "💡 建議行動: 建立新的工作日誌開始開發"
fi

# 檢查是否有測試需要修復 (基於當前修復模式狀態)
if [ -f "$CLAUDE_PROJECT_DIR/.claude/TASK_AVOIDANCE_FIX_MODE" ]; then
    log "🔧 系統處於修復模式 - 需要解決逃避行為問題"
    log "💡 優先行動: 檢查修復模式報告並解決問題"
fi

# 6.5 專案類型與語言代理人檢測
log "🔍 專案類型與語言代理人檢測"

# 檢測專案類型
if [ -f "pubspec.yaml" ] && [ -d "lib" ] && [ -d "test" ]; then
    PROJECT_TYPE="Flutter"
    PHASE_3B_AGENT="parsley-flutter-developer"
    LANG_CONFIG="FLUTTER.md"
elif [ -f "package.json" ] && [ -d "node_modules" ] && [ -d "src" ]; then
    if [ -f "src/App.vue" ] || grep -q "vue" "package.json" 2>/dev/null; then
        PROJECT_TYPE="Vue"
        PHASE_3B_AGENT="(待定義)"
        LANG_CONFIG="(待建立)"
    else
        PROJECT_TYPE="React"
        PHASE_3B_AGENT="(待定義)"
        LANG_CONFIG="(待建立)"
    fi
elif [ -f "requirements.txt" ] || [ -f "setup.py" ]; then
    PROJECT_TYPE="Python"
    PHASE_3B_AGENT="(待定義)"
    LANG_CONFIG="(待建立)"
else
    PROJECT_TYPE="未知"
    PHASE_3B_AGENT="(待識別)"
    LANG_CONFIG="(待建立)"
fi

log "📱 偵測到專案類型: $PROJECT_TYPE"
log "🤖 Phase 3b 代理人分派: $PHASE_3B_AGENT"
if [ -f ".claude/$LANG_CONFIG" ]; then
    log "📖 語言配置文件: .claude/$LANG_CONFIG (已存在)"
else
    log "📖 語言配置文件: .claude/$LANG_CONFIG (待建立)"
fi
log "💡 提醒: Phase 3 分為兩階段執行"
log "   - Phase 3a (pepper): 語言無關策略規劃"
log "   - Phase 3b ($PHASE_3B_AGENT): $PROJECT_TYPE 特定實作"

# 7. 5W1H 強制執行機制初始化
log "🎯 初始化 5W1H 強制執行機制"

# 生成新的 5W1H Token
NEW_5W1H_TOKEN=$("$SCRIPT_DIR/5w1h-token-generator.sh" generate 2>/dev/null | tail -1)
if [ -n "$NEW_5W1H_TOKEN" ]; then
    log "🔑 已生成 5W1H Session Token: $NEW_5W1H_TOKEN"
    log "📋 重要提醒: 請查閱 CLAUDE.md 中的 5W1H 決策框架章節"
    log "📖 所有對話必須遵循 5W1H 分析格式，詳見 CLAUDE.md 規範"
else
    log "⚠️  5W1H Token 生成失敗，請檢查腳本權限"
fi

# 8. Session 啟動檢查清單顯示
log "📋 Session 啟動檢查清單 (參考 CLAUDE.md)"
log ""
log "✅ 建議使用 DO-CONFIRM 模式（先執行後確認）"
log ""
log "環境狀態檢查:"
log "  [ ] Git 狀態確認: git status 無未追蹤的關鍵檔案"
log "  [ ] 依賴檢查: 專案依賴已正確安裝"
log "  [ ] 測試狀態: 最新提交的測試 100% 通過"
log "  [ ] 分支確認: 當前分支與工作版本一致"
log ""
log "專案狀態檢查:"
log "  [ ] 工作日誌存在: 當前版本的 vX.Y.Z-main.md 或 vX.Y.Z-ticket-NNN.md 可讀取"
log "  [ ] Todolist 同步: docs/todolist.md 與工作日誌任務狀態一致"
log "  [ ] 進行中 Ticket: 確認是否有未完成的 Ticket，優先完成再開始新任務"
log "  [ ] 版本狀態確認: 執行 git log --oneline -3 確認最新提交版本號"
log ""
log "📝 思考過程記錄檢查（第一優先）:"
log "  [ ] .0-main.md 工作日誌存在且可讀取"
log "  [ ] 最新討論和決策已記錄到主工作日誌"
log "  [ ] 記錄內容包含四個必要元素（討論、分析、決策、效益）"
log "  [ ] 記錄內容足夠讓他人重新進入狀況"
log ""
log "方法論合規性檢查:"
log "  [ ] 三重文件一致性: CHANGELOG、todolist、work-log 版本號對應"
log "  [ ] Ticket 設計標準: 進行中的 Ticket 包含 5 個核心欄位"
log "  [ ] TDD 階段連貫性: 當前階段與前一階段產出完整對接"
log ""
log "下一步行動確認:"
log "  [ ] 明確本次 Session 的目標任務"
log "  [ ] 確認任務優先級和依賴關係"
log "  [ ] 預估任務時間和資源需求"
log ""
log "💡 提醒: 完整的檢查清單和使用方式請參考 CLAUDE.md 檔案"
log "📖 詳細說明: CLAUDE.md - 🔍 主線程強制檢查清單"
log ""

# 9. 敏捷重構原則強制提醒
log "🤖 敏捷重構原則強制提醒"
log "📋 主線程職責: 只負責分派和統籌，禁止親自執行程式碼修改"
log "❌ 禁止行為: 親自閱讀/修改程式碼、執行具體重構、繞過子代理人"
log "✅ 正確做法: 分派任務給專業 agent、監控進度、維持敏捷節奏"
log "📖 詳細規範請參考: .claude/methodologies/agile-refactor-methodology.md"

# 10. 敏捷重構合規性檢查
log "🔍 執行敏捷重構合規性檢查"
if [ -x "$SCRIPT_DIR/check-agile-refactor-compliance.sh" ]; then
    "$SCRIPT_DIR/check-agile-refactor-compliance.sh"
    COMPLIANCE_EXIT_CODE=$?

    if [ $COMPLIANCE_EXIT_CODE -eq 0 ]; then
        log "✅ 敏捷重構合規性檢查通過"
    else
        log "⚠️  敏捷重構合規性檢查發現問題，請查看詳細記錄"
    fi
else
    log "⚠️  敏捷重構合規性檢查腳本不存在或無執行權限"
fi

# 11. 生成啟動報告摘要
log "📊 啟動檢查完成，詳細記錄: $LOG_FILE"

# 返回成功狀態
exit 0