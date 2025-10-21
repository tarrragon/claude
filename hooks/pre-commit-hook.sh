#!/bin/bash

# pre-commit-hook.sh
# PreToolUse Hook: Git commit 前自動執行檢查

# 設定路徑和日誌
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/pre-commit-$(date +%Y%m%d_%H%M%S).log"

# 確保日誌目錄存在
mkdir -p "$PROJECT_ROOT/.claude/hook-logs"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "📝 PreToolUse Hook (Git Commit): 開始執行提交前檢查"

cd "$PROJECT_ROOT"

# 1. 執行工作日誌檢查
log "📋 執行工作日誌檢查"
if [ -f "./scripts/check-work-log.sh" ]; then
    log "🔍 執行 check-work-log.sh"
    bash "./scripts/check-work-log.sh" >> "$LOG_FILE" 2>&1
    WORKLOG_EXIT_CODE=$?

    if [ $WORKLOG_EXIT_CODE -ne 0 ]; then
        log "⚠️  工作日誌檢查發現問題 (退出碼: $WORKLOG_EXIT_CODE)"
    else
        log "✅ 工作日誌檢查通過"
    fi
else
    log "⚠️  check-work-log.sh 腳本不存在"
fi

# 2. 強制問題追蹤檢查
log "🚨 強制問題追蹤檢查"

# 檢查暫存區中的變更
STAGED_FILES=$(git diff --cached --name-only)
if [ -n "$STAGED_FILES" ]; then
    log "📁 暫存區檔案:"
    echo "$STAGED_FILES" | while read file; do
        log "  - $file"
    done

    # 檢查是否有TODO、FIXME等標記
    DEBT_IN_STAGED=$(git diff --cached | grep -E "TODO|FIXME|HACK|XXX" | wc -l)
    if [ "$DEBT_IN_STAGED" -gt 0 ]; then
        log "⚠️  暫存區發現 $DEBT_IN_STAGED 個技術債務標記"

        # 創建問題追蹤提醒
        REMINDER_FILE="$PROJECT_ROOT/.claude/hook-logs/commit-issues-$(date +%Y%m%d_%H%M%S).md"
        echo "## 🚨 提交中發現的問題 - $(date)" > "$REMINDER_FILE"
        echo "### 技術債務標記" >> "$REMINDER_FILE"
        git diff --cached | grep -E "TODO|FIXME|HACK|XXX" >> "$REMINDER_FILE"
        echo "" >> "$REMINDER_FILE"
        echo "**影響評估**: Medium" >> "$REMINDER_FILE"
        echo "**建議行動**: 確認這些標記是否需要立即處理或加入todolist.md追蹤" >> "$REMINDER_FILE"

        log "📋 已生成問題追蹤報告: $REMINDER_FILE"
    fi
fi

# 3. 檢查是否包含工作日誌更新
log "📊 檢查工作日誌更新狀態"
if echo "$STAGED_FILES" | grep -q "docs/work-logs/"; then
    log "✅ 提交包含工作日誌更新"
else
    log "💡 提醒: 提交中未包含工作日誌更新"

    # 檢查是否有最新的工作日誌需要更新
    LATEST_WORKLOG=$(ls "docs/work-logs/" 2>/dev/null | grep '^v[0-9]' | sort -V | tail -1)
    if [ -n "$LATEST_WORKLOG" ]; then
        WORKLOG_PATH="docs/work-logs/$LATEST_WORKLOG"
        WORKLOG_MOD_TIME=$(stat -f %m "$WORKLOG_PATH" 2>/dev/null || echo "0")
        CURRENT_TIME=$(date +%s)
        TIME_DIFF=$((CURRENT_TIME - WORKLOG_MOD_TIME))

        if [ "$TIME_DIFF" -gt 1800 ]; then # 超過30分鐘
            log "💡 最新工作日誌 ($LATEST_WORKLOG) 超過30分鐘未更新，建議檢查是否需要記錄此次變更"
        fi
    fi
fi

# 4. 文檔格式檢查
log "📝 Markdown 文檔格式檢查"

# 檢查 markdownlint 是否可用
if command -v markdownlint >/dev/null 2>&1; then
    # 取得所有已暫存的 Markdown 文件
    STAGED_MD_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep "\.md$" || true)

    if [ -n "$STAGED_MD_FILES" ]; then
        log "🔍 檢查暫存的 Markdown 文件..."

        # 自動修正格式錯誤
        echo "$STAGED_MD_FILES" | while read -r file; do
            if [ -f "$file" ]; then
                log "  檢查: $file"
                if markdownlint --fix "$file" 2>/dev/null; then
                    log "  ✅ $file 格式正確或已自動修正"
                    # 如果文件被修改，重新加入暫存區
                    git add "$file"
                else
                    log "  ⚠️  $file 有無法自動修正的格式問題"
                fi
            fi
        done

        # 再次檢查是否還有格式錯誤
        LINT_ERRORS=$(echo "$STAGED_MD_FILES" | xargs markdownlint 2>&1 | grep -c "MD" || echo "0")
        if [ "$LINT_ERRORS" -eq 0 ]; then
            log "✅ 所有 Markdown 文件格式正確"
        else
            log "⚠️  仍有 $LINT_ERRORS 個格式問題需手動修正"
        fi
    else
        log "📄 無暫存的 Markdown 文件需要檢查"
    fi
else
    log "⚠️  markdownlint-cli 未安裝，跳過 Markdown 格式檢查"
fi

# 5. Flutter 程式碼檢查
log "🎯 Flutter 程式碼品質檢查"

# Flutter analyze 檢查
if command -v flutter >/dev/null 2>&1; then
    if flutter analyze --no-fatal-infos --no-fatal-warnings 2>/dev/null; then
        log "✅ Flutter analyze 檢查通過"
    else
        log "⚠️  Flutter analyze 發現問題，建議修復後再提交"
    fi
fi

# 5. 版本同步檢查
log "🔢 版本同步檢查"
if [ -f "./scripts/check-version-sync.sh" ]; then
    bash "./scripts/check-version-sync.sh" >> "$LOG_FILE" 2>&1
    VERSION_EXIT_CODE=$?

    if [ $VERSION_EXIT_CODE -ne 0 ]; then
        log "⚠️  版本同步檢查發現問題"
    else
        log "✅ 版本同步檢查通過"
    fi
fi

log "✅ PreToolUse Hook (Git Commit) 檢查完成"

# 返回成功 (不阻止提交，僅記錄和提醒)
exit 0