#!/bin/bash

# post-edit-hook.sh
# PostToolUse Hook: 檔案編輯後強制問題追蹤檢查
#
# 測試方式：
# 1. 主線程職責檢查：直接修改 lib/ 下的任何 .dart 檔案
# 2. 觀察 Hook 是否生成違規追蹤檔案 (.claude/hook-logs/main-thread-violation-*.md)
# 3. 檢查日誌輸出是否正確 (.claude/hook-logs/post-edit-*.log)
# 4. 驗證其他檢查項目（技術債務、錯誤處理、測試覆蓋率等）

# 載入通用函數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 設定專案環境
if ! setup_project_environment; then
    echo "錯誤: 無法設定專案環境" >&2
    exit 1
fi

PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/post-edit-$(date +%Y%m%d_%H%M%S).log"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "✏️  PostToolUse Hook (Edit): 開始執行編輯後檢查"

cd "$PROJECT_ROOT"

# 1. 強制問題追蹤檢查 (CLAUDE.md 核心要求)
log "🚨 強制問題追蹤檢查"

# 檢查最近修改的檔案
RECENT_CHANGES=$(git status --porcelain)
if [ -n "$RECENT_CHANGES" ]; then
    # 過濾檔案
    FILTERED_CHANGES=$(filter_files_for_dev_check "$RECENT_CHANGES")

    if [ -z "$FILTERED_CHANGES" ]; then
        log "📝 偵測到檔案變更，但都不需要開發流程檢查"
        exit 0
    fi

    log "📁 偵測到需要檢查的檔案變更:"
    echo "$FILTERED_CHANGES" | while read status file; do
        log "  $status $file"
    done

    # 使用過濾後的檔案清單進行後續檢查
    RECENT_CHANGES="$FILTERED_CHANGES"

    # 分析變更類型
    ISSUES_FOUND=()

    # 檢查是否有新的 TODO/FIXME 標記
    NEW_DEBT=$(git diff | grep -E "^\+.*TODO|^\+.*FIXME|^\+.*HACK|^\+.*XXX" | wc -l)
    if [ "$NEW_DEBT" -gt 0 ]; then
        ISSUES_FOUND+=("發現 $NEW_DEBT 個新的技術債務標記")
        log "⚠️  發現 $NEW_DEBT 個新的技術債務標記"
    fi

    # 檢查是否有錯誤處理相關變更
    ERROR_CHANGES=$(git diff | grep -E "^\+.*throw|^\+.*catch|^\+.*Error|^\+.*try" | wc -l)
    if [ "$ERROR_CHANGES" -gt 0 ]; then
        ISSUES_FOUND+=("發現 $ERROR_CHANGES 處錯誤處理相關變更")
        log "🔍 發現 $ERROR_CHANGES 處錯誤處理相關變更"
    fi

    # 檢查是否有測試檔案變更
    TEST_CHANGES=$(echo "$RECENT_CHANGES" | grep -E "test\.js$|spec\.js$" | wc -l)
    if [ "$TEST_CHANGES" -gt 0 ]; then
        log "🧪 發現 $TEST_CHANGES 個測試檔案變更"
    fi

    # 如果發現問題，生成追蹤提醒
    if [ ${#ISSUES_FOUND[@]} -gt 0 ]; then
        REMINDER_FILE="$PROJECT_ROOT/.claude/hook-logs/edit-issues-$(date +%Y%m%d_%H%M%S).md"
        echo "## 🚨 編輯後發現的問題 - $(date)" > "$REMINDER_FILE"
        echo "" >> "$REMINDER_FILE"

        for issue in "${ISSUES_FOUND[@]}"; do
            echo "- 🔄 **[檔案變更] $issue**" >> "$REMINDER_FILE"
            echo "  - 發現位置: 最近的檔案變更" >> "$REMINDER_FILE"
            echo "  - 影響評估: Medium" >> "$REMINDER_FILE"
            echo "  - 預期修復時間: 下一循環" >> "$REMINDER_FILE"
            echo "" >> "$REMINDER_FILE"
        done

        log "📋 已生成問題追蹤提醒: $REMINDER_FILE"
        log "⚠️  請依照CLAUDE.md規範，將這些問題更新到 todolist.md"
    fi
else
    log "📝 未偵測到檔案變更"
fi

# 2. 程式碼品質即時檢查
log "🔍 程式碼品質即時檢查"

# 檢查修改的JavaScript檔案是否有語法錯誤
JS_FILES=$(echo "$RECENT_CHANGES" | grep -E "\.js$" | awk '{print $2}')
if [ -n "$JS_FILES" ]; then
    log "🔍 檢查JavaScript檔案語法"

    while IFS= read -r file; do
        if [ -f "$file" ]; then
            # 簡單語法檢查
            if node -c "$file" 2>/dev/null; then
                log "✅ $file 語法正確"
            else
                log "❌ $file 語法錯誤"

                # 加入問題追蹤
                SYNTAX_REMINDER="$PROJECT_ROOT/.claude/hook-logs/syntax-error-$(date +%Y%m%d_%H%M%S).md"
                echo "## 🚨 語法錯誤 - $(date)" > "$SYNTAX_REMINDER"
                echo "- 🔄 **[語法錯誤] $file 語法檢查失敗**" >> "$SYNTAX_REMINDER"
                echo "  - 發現位置: $file" >> "$SYNTAX_REMINDER"
                echo "  - 影響評估: Critical" >> "$SYNTAX_REMINDER"
                echo "  - 預期修復時間: 立即" >> "$SYNTAX_REMINDER"

                log "📋 已生成語法錯誤追蹤: $SYNTAX_REMINDER"
            fi
        fi
    done <<< "$JS_FILES"
fi

# 3. 架構債務檢查 (三大鐵律之一)
log "🏗️  架構債務檢查"

# 檢查是否有違反 src/ 路徑規範的匯入
SRC_PATH_VIOLATIONS=$(git diff | grep -E "^\+.*require\(.*\.\./\.\./\.\." | wc -l)
if [ "$SRC_PATH_VIOLATIONS" -gt 0 ]; then
    log "⚠️  發現 $SRC_PATH_VIOLATIONS 處違反 src/ 路徑規範的匯入"

    ARCH_REMINDER="$PROJECT_ROOT/.claude/hook-logs/arch-debt-$(date +%Y%m%d_%H%M%S).md"
    echo "## 🚨 架構債務 - $(date)" > "$ARCH_REMINDER"
    echo "- 🔄 **[路徑規範] 違反 src/ 語意化路徑規範**" >> "$ARCH_REMINDER"
    echo "  - 發現位置: 檔案匯入語句" >> "$ARCH_REMINDER"
    echo "  - 影響評估: High" >> "$ARCH_REMINDER"
    echo "  - 預期修復時間: 下一循環" >> "$ARCH_REMINDER"

    log "📋 已生成架構債務追蹤: $ARCH_REMINDER"
fi

# 4. 測試覆蓋率提醒
log "🧪 測試覆蓋率提醒"

# 如果修改了 src/ 下的檔案，提醒檢查測試覆蓋
SRC_CHANGES=$(echo "$RECENT_CHANGES" | grep -E "^M.*src/.*\.js$" | wc -l)
if [ "$SRC_CHANGES" -gt 0 ]; then
    log "💡 發現 $SRC_CHANGES 個 src/ 檔案變更，建議檢查對應的測試覆蓋率"

    # 檢查是否有對應的測試檔案
    echo "$RECENT_CHANGES" | grep -E "^M.*src/.*\.js$" | while read status file; do
        # 嘗試找到對應的測試檔案
        BASE_NAME=$(basename "$file" .js)
        POSSIBLE_TEST="tests/unit/${BASE_NAME}.test.js"

        if [ ! -f "$POSSIBLE_TEST" ]; then
            log "💡 建議為 $file 建立測試檔案: $POSSIBLE_TEST"
        fi
    done
fi

# 5. 文件同步檢查
log "📚 文件同步檢查"

# 檢查是否需要更新文件
if echo "$RECENT_CHANGES" | grep -q -E "src/.*\.js$"; then
    # 檢查工作日誌是否需要更新
    LATEST_WORKLOG=$(ls "docs/work-logs/" 2>/dev/null | grep '^v[0-9]' | sort -V | tail -1)
    if [ -n "$LATEST_WORKLOG" ]; then
        WORKLOG_PATH="docs/work-logs/$LATEST_WORKLOG"
        WORKLOG_MOD_TIME=$(stat -f %m "$WORKLOG_PATH" 2>/dev/null || echo "0")
        CURRENT_TIME=$(date +%s)
        TIME_DIFF=$((CURRENT_TIME - WORKLOG_MOD_TIME))

        if [ "$TIME_DIFF" -gt 1800 ]; then # 超過30分鐘
            log "💡 程式碼有變更，建議更新工作日誌: $LATEST_WORKLOG"
        fi
    fi
fi

# 6. 主線程職責檢查 (敏捷重構方法論要求)
log "🔍 主線程職責檢查"

# 檢查是否修改 lib/ 目錄程式碼檔案
LIB_CHANGES=$(echo "$RECENT_CHANGES" | grep -E "^[AM].*lib/.*\.dart$" | wc -l)
if [ "$LIB_CHANGES" -gt 0 ]; then
    log "⚠️  偵測到主線程修改 lib/ 目錄程式碼"
    log "📋 敏捷重構方法論要求: 主線程禁止親自修改程式碼"
    log "✅ 正確做法: 使用 Task 工具分派給專業 agent 執行"

    # 進入修復模式
    REMINDER_FILE="$PROJECT_ROOT/.claude/hook-logs/main-thread-violation-$(date +%Y%m%d_%H%M%S).md"
    cat > "$REMINDER_FILE" <<EOF
## 🚨 主線程職責違規 - $(date)

### 違規行為
- 主線程直接修改 lib/ 目錄程式碼
- 修改檔案數: $LIB_CHANGES 個

### 受影響檔案
$(echo "$RECENT_CHANGES" | grep -E "^[AM].*lib/.*\.dart$")

### 正確做法
1. 使用 Task 工具分派任務給專業 agent
2. 例如: mint-format-specialist (格式化)
3. 例如: pepper-test-implementer (實作)
4. 例如: cinnamon-refactor-owl (重構)

### 參考文件
- 敏捷重構方法論: .claude/methodologies/agile-refactor-methodology.md
- 主線程職責: 只負責分派和統籌，禁止親自執行程式碼修改

### 修復指引
請撤銷這些修改，使用正確的 Task 工具分派流程重新執行。

EOF

    log "📋 已生成主線程違規追蹤: $REMINDER_FILE"
    log "🚨 請遵循敏捷重構方法論規範，使用 Task 工具分派任務"
fi

log "✅ PostToolUse Hook (Edit) 檢查完成"

# 返回成功 (不阻止後續操作)
exit 0