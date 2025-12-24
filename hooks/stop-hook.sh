#!/bin/bash

# stop-hook.sh
# Stop Hook: 主要代理完成回應時執行版本推進檢查

# 設定路徑和日誌
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/stop-$(date +%Y%m%d_%H%M%S).log"

# 確保日誌目錄存在
mkdir -p "$PROJECT_ROOT/.claude/hook-logs"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🛑 Stop Hook: 開始執行版本推進檢查"

cd "$PROJECT_ROOT"

# 1. 檢查是否需要執行版本推進檢查
log "🔍 檢查版本推進檢查條件"

# 檢查是否有程式碼變更
GIT_CHANGES=$(git status --porcelain | wc -l)
if [ "$GIT_CHANGES" -gt 0 ]; then
    log "📝 偵測到 $GIT_CHANGES 個檔案變更"
else
    log "📝 未偵測到檔案變更，跳過版本推進檢查"
    exit 0
fi

# 2. 執行智能版本推進檢查
log "🧠 執行智能版本推進檢查"

# 檢查是否有版本推進檢查腳本
if [ -f "./scripts/version-progression-check.sh" ]; then
    log "🔍 執行 version-progression-check.sh"
    bash "./scripts/version-progression-check.sh" >> "$LOG_FILE" 2>&1
    VERSION_CHECK_EXIT_CODE=$?

    if [ $VERSION_CHECK_EXIT_CODE -eq 0 ]; then
        log "✅ 版本推進檢查完成"
    else
        log "⚠️  版本推進檢查發現問題 (退出碼: $VERSION_CHECK_EXIT_CODE)"
    fi
else
    log "⚠️  version-progression-check.sh 腳本不存在，執行簡化檢查"

    # 簡化版本檢查
    log "📊 執行簡化版本狀態檢查"

    # 檢查當前版本
    if [ -f "pubspec.yaml" ]; then
        CURRENT_VERSION=$(grep '^version:' "pubspec.yaml" | sed 's/version: *//')
        log "📦 當前版本: $CURRENT_VERSION"
    fi

    # 檢查最新工作日誌
    LATEST_WORKLOG=$(ls "docs/work-logs/" 2>/dev/null | grep '^v[0-9]' | sort -V | tail -1)
    if [ -n "$LATEST_WORKLOG" ]; then
        log "📋 最新工作日誌: $LATEST_WORKLOG"

        # 檢查工作完成狀態
        if grep -q "✅" "docs/work-logs/$LATEST_WORKLOG" 2>/dev/null; then
            log "✅ 工作日誌顯示任務已完成"
            log "💡 建議考慮版本推進"
        else
            log "🔄 工作日誌顯示任務進行中"
        fi
    fi
fi

# 3. 檢查todolist.md狀態
log "📋 檢查todolist.md狀態"

if [ -f "docs/todolist.md" ]; then
    # 檢查是否有已完成的任務
    COMPLETED_TASKS=$(grep -c "✅" "docs/todolist.md" 2>/dev/null || echo "0")
    PENDING_TASKS=$(grep -c "🔄\|⭕" "docs/todolist.md" 2>/dev/null || echo "0")

    log "📊 任務統計: $COMPLETED_TASKS 已完成, $PENDING_TASKS 待處理"

    if [ "$COMPLETED_TASKS" -gt 0 ] && [ "$PENDING_TASKS" -eq 0 ]; then
        log "💡 所有todolist任務已完成，建議考慮中版本推進"
    fi
else
    log "⚠️  todolist.md 檔案不存在"
fi

# 4. 生成版本推進建議
log "💡 生成版本推進建議"

SUGGESTION_FILE="$PROJECT_ROOT/.claude/hook-logs/version-suggestion-$(date +%Y%m%d_%H%M%S).md"
echo "# 版本推進建議 - $(date)" > "$SUGGESTION_FILE"
echo "" >> "$SUGGESTION_FILE"

# 分析當前狀態並給出建議
if [ -n "$LATEST_WORKLOG" ] && grep -q "✅" "docs/work-logs/$LATEST_WORKLOG" 2>/dev/null; then
    echo "## 🚀 建議推進版本" >> "$SUGGESTION_FILE"
    echo "" >> "$SUGGESTION_FILE"
    echo "**當前狀態**: 工作日誌已標記完成" >> "$SUGGESTION_FILE"
    echo "" >> "$SUGGESTION_FILE"
    echo "**建議行動**:" >> "$SUGGESTION_FILE"
    echo "1. 執行 \`/smart-version-check\` 進行完整版本推進分析" >> "$SUGGESTION_FILE"
    echo "2. 或手動執行 \`./scripts/version-progression-check.sh\`" >> "$SUGGESTION_FILE"
    echo "3. 根據結果選擇適當的版本推進策略" >> "$SUGGESTION_FILE"
    echo "" >> "$SUGGESTION_FILE"
    echo "**可能的推進策略**:" >> "$SUGGESTION_FILE"
    echo "- 小版本推進 (patch): 如果版本系列未完成" >> "$SUGGESTION_FILE"
    echo "- 中版本推進 (minor): 如果版本系列目標已達成" >> "$SUGGESTION_FILE"
else
    echo "## 🔄 建議繼續當前開發" >> "$SUGGESTION_FILE"
    echo "" >> "$SUGGESTION_FILE"
    echo "**當前狀態**: 工作進行中" >> "$SUGGESTION_FILE"
    echo "" >> "$SUGGESTION_FILE"
    echo "**建議行動**:" >> "$SUGGESTION_FILE"
    echo "1. 繼續當前開發工作" >> "$SUGGESTION_FILE"
    echo "2. 完成後更新工作日誌並標記 ✅" >> "$SUGGESTION_FILE"
    echo "3. 然後考慮版本推進" >> "$SUGGESTION_FILE"
fi

log "📋 版本推進建議報告: $SUGGESTION_FILE"

# 5. 檢查是否需要提醒用戶
log "🔔 檢查提醒條件"

# 如果有大量變更且工作可能完成，生成提醒
if [ "$GIT_CHANGES" -gt 5 ] && [ -n "$LATEST_WORKLOG" ]; then
    WORKLOG_MOD_TIME=$(stat -f %m "docs/work-logs/$LATEST_WORKLOG" 2>/dev/null || echo "0")
    CURRENT_TIME=$(date +%s)
    TIME_DIFF=$((CURRENT_TIME - WORKLOG_MOD_TIME))

    if [ "$TIME_DIFF" -gt 3600 ]; then # 超過1小時
        log "💡 大量變更且工作日誌超過1小時未更新，建議檢查工作狀態"

        # 生成提醒
        echo "" >> "$SUGGESTION_FILE"
        echo "## 🔔 重要提醒" >> "$SUGGESTION_FILE"
        echo "- 偵測到大量檔案變更 ($GIT_CHANGES 個)" >> "$SUGGESTION_FILE"
        echo "- 工作日誌超過1小時未更新" >> "$SUGGESTION_FILE"
        echo "- 建議更新工作日誌並考慮提交變更" >> "$SUGGESTION_FILE"
    fi
fi

log "✅ Stop Hook 版本推進檢查完成"

# 返回成功 (不阻止Claude Code操作)
exit 0