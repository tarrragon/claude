#!/bin/bash

# auto-documentation-update-hook.sh
# PostToolUse Hook: 程式碼變更時自動提醒文件更新

# 設定路徑和日誌
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/doc-update-$(date +%Y%m%d_%H%M%S).log"

# 確保日誌目錄存在
mkdir -p "$PROJECT_ROOT/.claude/hook-logs"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "📚 Auto-Documentation Update Hook: 開始檢查文件更新需求"

cd "$PROJECT_ROOT"

# 1. 檢查程式碼變更類型
log "🔍 分析程式碼變更類型"

# 獲取變更的檔案
CHANGED_FILES=$(git status --porcelain)
if [ -z "$CHANGED_FILES" ]; then
    log "📝 未偵測到檔案變更，跳過文件更新檢查"
    exit 0
fi

# 分析變更類型並生成文件更新建議
DOCS_TO_UPDATE=()
UPDATE_REASONS=()

# 檢查 API 變更
API_CHANGES=$(echo "$CHANGED_FILES" | grep -E "(handler|controller|api|route)" | wc -l)
if [ "$API_CHANGES" -gt 0 ]; then
    DOCS_TO_UPDATE+=("docs/api/")
    UPDATE_REASONS+=("API相關檔案變更 ($API_CHANGES 個)")
    log "🔌 偵測到 $API_CHANGES 個 API 相關檔案變更"
fi

# 檢查核心架構變更
ARCH_CHANGES=$(echo "$CHANGED_FILES" | grep -E "src/core|src/background|src/domain" | wc -l)
if [ "$ARCH_CHANGES" -gt 0 ]; then
    DOCS_TO_UPDATE+=("docs/domains/architecture/")
    UPDATE_REASONS+=("核心架構檔案變更 ($ARCH_CHANGES 個)")
    log "🏗️  偵測到 $ARCH_CHANGES 個架構檔案變更"
fi

# 檢查配置檔案變更
CONFIG_CHANGES=$(echo "$CHANGED_FILES" | grep -E "(config|setting|manifest)" | wc -l)
if [ "$CONFIG_CHANGES" -gt 0 ]; then
    DOCS_TO_UPDATE+=("docs/setup/" "README.md")
    UPDATE_REASONS+=("配置檔案變更 ($CONFIG_CHANGES 個)")
    log "⚙️  偵測到 $CONFIG_CHANGES 個配置檔案變更"
fi

# 檢查新功能開發
NEW_FEATURES=$(echo "$CHANGED_FILES" | grep -E "^A.*src/" | wc -l)
if [ "$NEW_FEATURES" -gt 0 ]; then
    DOCS_TO_UPDATE+=("CHANGELOG.md" "docs/features/")
    UPDATE_REASONS+=("新功能檔案 ($NEW_FEATURES 個)")
    log "✨ 偵測到 $NEW_FEATURES 個新功能檔案"
fi

# 檢查測試變更
TEST_CHANGES=$(echo "$CHANGED_FILES" | grep -E "test\.js$|spec\.js$" | wc -l)
if [ "$TEST_CHANGES" -gt 0 ]; then
    DOCS_TO_UPDATE+=("docs/testing/")
    UPDATE_REASONS+=("測試檔案變更 ($TEST_CHANGES 個)")
    log "🧪 偵測到 $TEST_CHANGES 個測試檔案變更"
fi

# 2. 生成文件更新提醒
if [ ${#DOCS_TO_UPDATE[@]} -gt 0 ]; then
    log "📋 生成文件更新提醒"

    REMINDER_FILE="$PROJECT_ROOT/.claude/hook-logs/doc-update-reminder-$(date +%Y%m%d_%H%M%S).md"
    echo "# 📚 文件更新提醒 - $(date)" > "$REMINDER_FILE"
    echo "" >> "$REMINDER_FILE"
    echo "## 🔍 偵測到的變更" >> "$REMINDER_FILE"
    echo "" >> "$REMINDER_FILE"

    for reason in "${UPDATE_REASONS[@]}"; do
        echo "- $reason" >> "$REMINDER_FILE"
    done

    echo "" >> "$REMINDER_FILE"
    echo "## 📝 建議更新的文件" >> "$REMINDER_FILE"
    echo "" >> "$REMINDER_FILE"

    for doc in "${DOCS_TO_UPDATE[@]}"; do
        echo "- [ ] $doc" >> "$REMINDER_FILE"
    done

    echo "" >> "$REMINDER_FILE"
    echo "## 🎯 優先級評估" >> "$REMINDER_FILE"
    echo "" >> "$REMINDER_FILE"

    # 根據變更類型評估優先級
    if [[ " ${DOCS_TO_UPDATE[@]} " =~ " docs/api/ " ]]; then
        echo "- **High**: API 文件更新 (影響使用者介面)" >> "$REMINDER_FILE"
    fi

    if [[ " ${DOCS_TO_UPDATE[@]} " =~ " README.md " ]]; then
        echo "- **High**: README 更新 (影響專案說明)" >> "$REMINDER_FILE"
    fi

    if [[ " ${DOCS_TO_UPDATE[@]} " =~ " CHANGELOG.md " ]]; then
        echo "- **Medium**: CHANGELOG 更新 (版本記錄)" >> "$REMINDER_FILE"
    fi

    if [[ " ${DOCS_TO_UPDATE[@]} " =~ " docs/domains/architecture/ " ]]; then
        echo "- **Medium**: 架構文件更新 (設計文件)" >> "$REMINDER_FILE"
    fi

    echo "" >> "$REMINDER_FILE"
    echo "## 🔄 建議執行時機" >> "$REMINDER_FILE"
    echo "" >> "$REMINDER_FILE"
    echo "- **立即**: High 優先級文件" >> "$REMINDER_FILE"
    echo "- **提交前**: Medium 優先級文件" >> "$REMINDER_FILE"
    echo "- **版本推進時**: 全面文件檢查" >> "$REMINDER_FILE"

    log "📋 文件更新提醒已生成: $REMINDER_FILE"

    # 3. 檢查文件過期情況
    log "⏰ 檢查文件過期情況"

    CURRENT_TIME=$(date +%s)
    OUTDATED_DOCS=()

    # 檢查重要文件的修改時間
    IMPORTANT_DOCS=(
        "README.md"
        "CHANGELOG.md"
        "docs/api/overview.md"
        "docs/domains/architecture/overview.md"
    )

    for doc in "${IMPORTANT_DOCS[@]}"; do
        if [ -f "$doc" ]; then
            DOC_MOD_TIME=$(stat -f %m "$doc" 2>/dev/null || echo "0")
            TIME_DIFF=$((CURRENT_TIME - DOC_MOD_TIME))

            # 如果文件超過7天未更新且有相關程式碼變更
            if [ "$TIME_DIFF" -gt 604800 ]; then # 7天
                OUTDATED_DOCS+=("$doc ($(( TIME_DIFF / 86400 )) 天未更新)")
            fi
        fi
    done

    if [ ${#OUTDATED_DOCS[@]} -gt 0 ]; then
        echo "" >> "$REMINDER_FILE"
        echo "## ⚠️  過期文件警示" >> "$REMINDER_FILE"
        echo "" >> "$REMINDER_FILE"

        for doc in "${OUTDATED_DOCS[@]}"; do
            echo "- $doc" >> "$REMINDER_FILE"
        done

        log "⚠️  發現 ${#OUTDATED_DOCS[@]} 個過期文件"
    fi

    # 4. 整合到工作流程
    echo "" >> "$REMINDER_FILE"
    echo "## 🔧 整合建議" >> "$REMINDER_FILE"
    echo "" >> "$REMINDER_FILE"
    echo "### 立即行動" >> "$REMINDER_FILE"
    echo "```bash" >> "$REMINDER_FILE"
    echo "# 使用 TodoWrite 工具將文件更新任務加入追蹤" >> "$REMINDER_FILE"
    echo "# 優先級: High → Critical, Medium → High" >> "$REMINDER_FILE"
    echo "```" >> "$REMINDER_FILE"
    echo "" >> "$REMINDER_FILE"
    echo "### 提交前檢查" >> "$REMINDER_FILE"
    echo "```bash" >> "$REMINDER_FILE"
    echo "# 確保相關文件已更新並包含在提交中" >> "$REMINDER_FILE"
    echo "git add docs/ README.md CHANGELOG.md" >> "$REMINDER_FILE"
    echo "```" >> "$REMINDER_FILE"

else
    log "📝 未偵測到需要文件更新的變更類型"
fi

# 5. 檢查工作日誌同步
log "📋 檢查工作日誌同步狀態"

LATEST_WORKLOG=$(ls "docs/work-logs/" 2>/dev/null | grep '^v[0-9]' | sort -V | tail -1)
if [ -n "$LATEST_WORKLOG" ]; then
    WORKLOG_PATH="docs/work-logs/$LATEST_WORKLOG"
    WORKLOG_MOD_TIME=$(stat -f %m "$WORKLOG_PATH" 2>/dev/null || echo "0")
    TIME_DIFF=$((CURRENT_TIME - WORKLOG_MOD_TIME))

    if [ "$TIME_DIFF" -gt 1800 ]; then # 超過30分鐘
        log "💡 工作日誌超過30分鐘未更新，建議同步當前進度"

        if [ -n "$REMINDER_FILE" ]; then
            echo "" >> "$REMINDER_FILE"
            echo "## 📋 工作日誌同步提醒" >> "$REMINDER_FILE"
            echo "- 工作日誌: $LATEST_WORKLOG" >> "$REMINDER_FILE"
            echo "- 上次更新: $(( TIME_DIFF / 60 )) 分鐘前" >> "$REMINDER_FILE"
            echo "- 建議: 更新工作進度並標記完成狀態" >> "$REMINDER_FILE"
        fi
    fi
fi

log "✅ Auto-Documentation Update Hook 檢查完成"

# 返回成功 (不阻止後續操作)
exit 0