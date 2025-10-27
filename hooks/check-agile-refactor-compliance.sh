#!/bin/bash

# check-agile-refactor-compliance.sh
# 敏捷重構合規性檢查模組

# 載入通用函數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 設定專案環境
if ! setup_project_environment; then
    echo "錯誤: 無法設定專案環境" >&2
    exit 1
fi

# 設定日誌檔案
LOG_FILE="$CLAUDE_LOGS_DIR/agile-refactor-compliance-$(date +%Y%m%d_%H%M%S).log"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 初始化檢查結果
COMPLIANCE_ISSUES=0

log "🔍 開始敏捷重構合規性檢查"
log "================================================"

# ========================================
# 檢查項目 1: Ticket 設計標準合規性
# ========================================
log ""
log "📋 檢查項目 1: Ticket 設計標準合規性"
log "檢查最新 Ticket 工作日誌是否包含 5 個核心欄位"

# 查找最新的 Ticket 工作日誌
LATEST_TICKET=$(ls "$CLAUDE_PROJECT_DIR/docs/work-logs/" 2>/dev/null | \
    grep 'ticket-[0-9]' | \
    sort -V | \
    tail -1)

if [ -n "$LATEST_TICKET" ]; then
    TICKET_PATH="$CLAUDE_PROJECT_DIR/docs/work-logs/$LATEST_TICKET"
    log "✅ 找到最新 Ticket: $LATEST_TICKET"

    # 檢查 5 個核心欄位
    MISSING_FIELDS=()

    # 欄位 1: 背景 (Background)
    if ! grep -q "## 1. 背景\|## 背景\|## Background" "$TICKET_PATH" 2>/dev/null; then
        MISSING_FIELDS+=("背景 (Background)")
    fi

    # 欄位 2: 目標 (Objective)
    if ! grep -q "## 2. 目標\|## 目標\|## Objective" "$TICKET_PATH" 2>/dev/null; then
        MISSING_FIELDS+=("目標 (Objective)")
    fi

    # 欄位 3: 驗收條件 (Acceptance Criteria)
    if ! grep -q "## 驗收條件\|## Acceptance Criteria\|## ✅ 驗收條件" "$TICKET_PATH" 2>/dev/null; then
        MISSING_FIELDS+=("驗收條件 (Acceptance Criteria)")
    fi

    # 欄位 4: 依賴 Ticket (Dependencies)
    if ! grep -q "## 依賴 Ticket\|## Dependencies\|## 6. 依賴 Ticket" "$TICKET_PATH" 2>/dev/null; then
        MISSING_FIELDS+=("依賴 Ticket (Dependencies)")
    fi

    # 欄位 5: 執行步驟 (Steps)
    if ! grep -q "## 執行步驟\|## Steps\|## 3. 執行步驟" "$TICKET_PATH" 2>/dev/null; then
        MISSING_FIELDS+=("執行步驟 (Steps)")
    fi

    if [ ${#MISSING_FIELDS[@]} -eq 0 ]; then
        log "✅ Ticket 設計標準合規：5 個核心欄位完整"
    else
        log "⚠️  Ticket 設計標準不合規：缺少以下欄位"
        for field in "${MISSING_FIELDS[@]}"; do
            log "   - $field"
        done
        COMPLIANCE_ISSUES=$((COMPLIANCE_ISSUES + 1))
        log "💡 修復建議: 請補充缺失的欄位到 Ticket 工作日誌"
        log "📖 參考: .claude/methodologies/ticket-design-dispatch-methodology.md"
    fi
else
    log "🔍 未找到 Ticket 工作日誌，跳過此檢查"
fi

# ========================================
# 檢查項目 2: 三重文件一致性
# ========================================
log ""
log "📚 檢查項目 2: 三重文件一致性"
log "檢查 CHANGELOG、todolist、work-log 版本號是否對應"

# 讀取 CHANGELOG.md 最新版本
CHANGELOG_VERSION=""
if [ -f "$CLAUDE_PROJECT_DIR/CHANGELOG.md" ]; then
    CHANGELOG_VERSION=$(grep -E '^## \[[0-9]+\.[0-9]+\.[0-9]+\]' "$CLAUDE_PROJECT_DIR/CHANGELOG.md" | \
        head -1 | \
        sed 's/.*\[\([0-9.]*\)\].*/\1/')

    if [ -n "$CHANGELOG_VERSION" ]; then
        log "📋 CHANGELOG.md 最新版本: $CHANGELOG_VERSION"
    else
        log "🔍 CHANGELOG.md 未找到版本號"
    fi
else
    log "⚠️  CHANGELOG.md 不存在"
    COMPLIANCE_ISSUES=$((COMPLIANCE_ISSUES + 1))
fi

# 讀取 work-log 最新版本
WORKLOG_VERSION=""
if [ -n "$LATEST_WORKLOG" ]; then
    # 從檔名提取版本號 (例如 v0.12.7-main.md -> 0.12.7)
    WORKLOG_VERSION=$(echo "$LATEST_WORKLOG" | \
        sed -E 's/v([0-9]+\.[0-9]+\.[0-9A-Z]+).*/\1/')
    log "📝 work-log 最新版本: $WORKLOG_VERSION"
else
    log "⚠️  work-log 不存在"
fi

# 讀取 todolist.md 進行中的版本
TODOLIST_VERSION=""
if [ -f "$CLAUDE_PROJECT_DIR/docs/todolist.md" ]; then
    # 查找標記為進行中的版本號
    TODOLIST_VERSION=$(grep -E "v[0-9]+\.[0-9]+\.[0-9A-Z]+" "$CLAUDE_PROJECT_DIR/docs/todolist.md" | \
        grep -E "🔄|進行中|in_progress" | \
        head -1 | \
        sed -E 's/.*v([0-9]+\.[0-9]+\.[0-9A-Z]+).*/\1/')

    if [ -n "$TODOLIST_VERSION" ]; then
        log "✅ todolist.md 進行中版本: $TODOLIST_VERSION"
    else
        log "🔍 todolist.md 未找到進行中版本"
    fi
else
    log "⚠️  todolist.md 不存在"
    COMPLIANCE_ISSUES=$((COMPLIANCE_ISSUES + 1))
fi

# 比對版本一致性
if [ -n "$WORKLOG_VERSION" ] && [ -n "$CHANGELOG_VERSION" ]; then
    # 移除可能的字母後綴 (如 v0.12.I -> 0.12)
    WORKLOG_MAJOR=$(echo "$WORKLOG_VERSION" | sed -E 's/([0-9]+\.[0-9]+).*/\1/')
    CHANGELOG_MAJOR=$(echo "$CHANGELOG_VERSION" | sed -E 's/([0-9]+\.[0-9]+).*/\1/')

    if [ "$WORKLOG_MAJOR" = "$CHANGELOG_MAJOR" ]; then
        log "✅ 三重文件版本一致 (work-log: $WORKLOG_VERSION, CHANGELOG: $CHANGELOG_VERSION)"
    else
        log "⚠️  版本不一致: work-log ($WORKLOG_VERSION) vs CHANGELOG ($CHANGELOG_VERSION)"
        log "💡 修復建議: 檢查是否需要更新 CHANGELOG 或建立新版本 work-log"
        COMPLIANCE_ISSUES=$((COMPLIANCE_ISSUES + 1))
    fi
fi

# ========================================
# 檢查項目 3: 主線程分派提醒
# ========================================
log ""
log "🤖 檢查項目 3: 主線程分派提醒"
log "提醒主線程職責：只負責分派和統籌"

log "📋 主線程職責提醒:"
log "   ✅ 依照主版本工作日誌分派任務給相應的子代理人"
log "   ✅ 維持敏捷開發節奏和品質標準"
log "   ✅ 監控整體進度和三重文件一致性"
log "   ✅ 處理升級請求和任務重新分派"

log ""
log "❌ 主線程禁止行為:"
log "   ❌ 禁止親自閱讀或修改程式碼"
log "   ❌ 禁止執行具體的重構或實作工作"
log "   ❌ 禁止繞過子代理人直接操作"

log ""
log "💡 分派任務時請使用 Ticket 設計方法論:"
log "   - 評估任務複雜度 (Simple/Medium/Complex)"
log "   - 設計 SMART 驗收條件"
log "   - 標註 Ticket 依賴關係"
log "   - 明確執行代理人"

log "📖 詳細規範: .claude/methodologies/ticket-design-dispatch-methodology.md"

# ========================================
# 檢查項目 4: 思考過程記錄檢查
# ========================================
log ""
log "🧠 檢查項目 4: 思考過程記錄檢查"
log "檢查主線程是否定期更新思考記錄"

# 檢查思考記錄檔案是否存在
THINKING_LOG="$CLAUDE_PROJECT_DIR/.claude/thinking-process.md"
if [ -f "$THINKING_LOG" ]; then
    # 檢查最後修改時間
    LAST_MODIFIED=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$THINKING_LOG" 2>/dev/null || echo "未知")
    LAST_MODIFIED_EPOCH=$(stat -f "%m" "$THINKING_LOG" 2>/dev/null || echo "0")
    CURRENT_EPOCH=$(date +%s)
    TIME_DIFF=$(( (CURRENT_EPOCH - LAST_MODIFIED_EPOCH) / 3600 ))

    log "📝 思考記錄檔案存在"
    log "⏰ 最後更新時間: $LAST_MODIFIED"

    if [ "$TIME_DIFF" -gt 48 ]; then
        log "⚠️  思考記錄超過 48 小時未更新 (${TIME_DIFF} 小時)"
        log "💡 修復建議: 主線程應定期更新思考記錄，記錄重要決策和規劃"
        COMPLIANCE_ISSUES=$((COMPLIANCE_ISSUES + 1))
    else
        log "✅ 思考記錄時效性良好 (最近 ${TIME_DIFF} 小時內更新)"
    fi

    # 檢查記錄完整性（至少包含版本規劃和當前狀態）
    if grep -q "## 當前狀態\|## Current Status\|## 版本規劃\|## Version Planning" "$THINKING_LOG" 2>/dev/null; then
        log "✅ 思考記錄格式完整 (包含當前狀態或版本規劃)"
    else
        log "⚠️  思考記錄缺少必要章節 (當前狀態、版本規劃)"
        log "💡 修復建議: 思考記錄應包含「當前狀態」和「版本規劃」章節"
        COMPLIANCE_ISSUES=$((COMPLIANCE_ISSUES + 1))
    fi
else
    log "⚠️  思考記錄檔案不存在: $THINKING_LOG"
    log "💡 建議: 主線程應建立思考記錄檔案，記錄重要決策和規劃"
    log "📖 參考: CLAUDE.md 中的「主線程強制記錄原則」章節"
    COMPLIANCE_ISSUES=$((COMPLIANCE_ISSUES + 1))
fi

# 檢查派工前是否確認思考記錄
log ""
log "⚠️  派工前檢查清單提醒:"
log "   1️⃣  確認思考記錄已更新（記錄當前狀態和規劃）"
log "   2️⃣  評估任務複雜度並設計 Ticket"
log "   3️⃣  確認 Ticket 包含 5 個核心欄位"
log "   4️⃣  標註 Ticket 依賴關係和執行代理人"
log "   5️⃣  記錄派工決策到思考記錄"

# ========================================
# 生成合規性報告摘要
# ========================================
log ""
log "================================================"
log "📊 敏捷重構合規性檢查完成"
log ""

if [ $COMPLIANCE_ISSUES -eq 0 ]; then
    log "✅ 所有檢查項目通過，系統合規"
    log "💡 建議: 繼續保持良好的開發流程"
    exit 0
else
    log "⚠️  發現 $COMPLIANCE_ISSUES 個合規性問題"
    log "🔧 建議: 根據上述修復建議進行改善"
    log "📋 詳細記錄: $LOG_FILE"
    log ""
    log "📚 相關方法論參考:"
    log "   - .claude/methodologies/agile-refactor-methodology.md"
    log "   - .claude/methodologies/ticket-design-dispatch-methodology.md"
    log "   - .claude/methodologies/ticket-lifecycle-management-methodology.md"
    log "   - CLAUDE.md 中的「🚀 敏捷重構開發流程」章節"
    exit 1
fi
