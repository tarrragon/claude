#!/bin/bash

# post-test-hook.sh
# PostToolUse Hook: 測試執行後結果分析和問題追蹤

# 設定路徑和日誌
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/post-test-$(date +%Y%m%d_%H%M%S).log"

# 確保日誌目錄存在
mkdir -p "$PROJECT_ROOT/.claude/hook-logs"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🧪 PostToolUse Hook (Test): 開始執行測試後分析"

cd "$PROJECT_ROOT"

# 1. 檢查測試結果狀態
log "📊 檢查測試結果狀態"

# 檢查最近的測試輸出 (從預設位置或日誌)
TEST_OUTPUT_FILE=""
if [ -f "coverage-private/latest-test-output.log" ]; then
    TEST_OUTPUT_FILE="coverage-private/latest-test-output.log"
elif [ -f "test-output.log" ]; then
    TEST_OUTPUT_FILE="test-output.log"
fi

if [ -n "$TEST_OUTPUT_FILE" ]; then
    log "📁 分析測試輸出: $TEST_OUTPUT_FILE"

    # 分析測試結果
    if grep -q "Tests:.*failed" "$TEST_OUTPUT_FILE"; then
        FAILED_COUNT=$(grep "Tests:.*failed" "$TEST_OUTPUT_FILE" | sed -E 's/.*([0-9]+) failed.*/\1/')
        log "❌ 發現 $FAILED_COUNT 個測試失敗"
        echo "fail" > "coverage-private/test-status.txt"
    elif grep -q "All tests passed" "$TEST_OUTPUT_FILE" || grep -q "Tests:.*passed" "$TEST_OUTPUT_FILE"; then
        log "✅ 所有測試通過"
        echo "pass" > "coverage-private/test-status.txt"
    else
        log "⚠️  無法確定測試狀態"
        echo "unknown" > "coverage-private/test-status.txt"
    fi
else
    log "⚠️  未找到測試輸出檔案"
fi

# 2. 三大鐵律檢查 - 100% 測試通過率
log "🚨 三大鐵律檢查 - 100% 測試通過率"

TEST_STATUS=$(cat "coverage-private/test-status.txt" 2>/dev/null || echo "unknown")
if [ "$TEST_STATUS" != "pass" ]; then
    log "🚨 違反測試通過率鐵律! 當前狀態: $TEST_STATUS"

    # 生成強制問題追蹤
    CRITICAL_ISSUE="$PROJECT_ROOT/.claude/hook-logs/critical-test-failure-$(date +%Y%m%d_%H%M%S).md"
    echo "## 🚨 CRITICAL: 違反測試通過率鐵律 - $(date)" > "$CRITICAL_ISSUE"
    echo "" >> "$CRITICAL_ISSUE"
    echo "- 🔄 **[測試失敗] 測試通過率不是100%**" >> "$CRITICAL_ISSUE"
    echo "  - 發現位置: 測試執行結果" >> "$CRITICAL_ISSUE"
    echo "  - 影響評估: Critical" >> "$CRITICAL_ISSUE"
    echo "  - 預期修復時間: 立即" >> "$CRITICAL_ISSUE"
    echo "  - 當前狀態: $TEST_STATUS" >> "$CRITICAL_ISSUE"
    echo "" >> "$CRITICAL_ISSUE"
    echo "**CLAUDE.md 鐵律**: 任何測試失敗 = 立即修正，其他工作全部暫停" >> "$CRITICAL_ISSUE"

    log "📋 已生成關鍵問題追蹤: $CRITICAL_ISSUE"
    log "⚠️  根據CLAUDE.md鐵律，必須立即修正測試問題!"
else
    log "✅ 測試通過率鐵律檢查通過"
fi

# 3. 測試覆蓋率分析
log "📈 測試覆蓋率分析"

# 檢查覆蓋率報告
if [ -d "coverage" ] || [ -d "coverage-private" ]; then
    COVERAGE_DIR=""
    if [ -d "coverage" ]; then
        COVERAGE_DIR="coverage"
    else
        COVERAGE_DIR="coverage-private"
    fi

    if [ -f "$COVERAGE_DIR/lcov-report/index.html" ]; then
        log "📊 覆蓋率報告可用: $COVERAGE_DIR/lcov-report/index.html"

        # 嘗試提取覆蓋率數據
        if [ -f "$COVERAGE_DIR/lcov.info" ]; then
            COVERAGE_SUMMARY=$(grep -E "^LF:|^LH:" "$COVERAGE_DIR/lcov.info" | tail -2)
            log "📊 覆蓋率摘要: $COVERAGE_SUMMARY"
        fi
    else
        log "📊 覆蓋率報告不可用"
    fi
else
    log "📊 未找到覆蓋率目錄"
fi

# 4. 錯誤分析和分類
log "🔍 錯誤分析和分類"

if [ "$TEST_STATUS" == "fail" ] && [ -n "$TEST_OUTPUT_FILE" ]; then
    # 分析失敗的測試類型
    SYNTAX_ERRORS=$(grep -c "SyntaxError" "$TEST_OUTPUT_FILE" 2>/dev/null || echo "0")
    REFERENCE_ERRORS=$(grep -c "ReferenceError" "$TEST_OUTPUT_FILE" 2>/dev/null || echo "0")
    TYPE_ERRORS=$(grep -c "TypeError" "$TEST_OUTPUT_FILE" 2>/dev/null || echo "0")
    ASSERTION_ERRORS=$(grep -c "expect.*received" "$TEST_OUTPUT_FILE" 2>/dev/null || echo "0")

    log "🔍 錯誤分類統計:"
    log "  - 語法錯誤: $SYNTAX_ERRORS"
    log "  - 參考錯誤: $REFERENCE_ERRORS"
    log "  - 類型錯誤: $TYPE_ERRORS"
    log "  - 斷言錯誤: $ASSERTION_ERRORS"

    # 為每種錯誤類型生成追蹤
    if [ "$SYNTAX_ERRORS" -gt 0 ]; then
        ERROR_TRACK="$PROJECT_ROOT/.claude/hook-logs/syntax-errors-$(date +%Y%m%d_%H%M%S).md"
        echo "## 🚨 語法錯誤追蹤 - $(date)" > "$ERROR_TRACK"
        echo "- 🔄 **[語法錯誤] 發現 $SYNTAX_ERRORS 個語法錯誤**" >> "$ERROR_TRACK"
        echo "  - 影響評估: Critical" >> "$ERROR_TRACK"
        echo "  - 預期修復時間: 立即" >> "$ERROR_TRACK"
        log "📋 已生成語法錯誤追蹤: $ERROR_TRACK"
    fi

    if [ "$ASSERTION_ERRORS" -gt 0 ]; then
        ASSERTION_TRACK="$PROJECT_ROOT/.claude/hook-logs/assertion-errors-$(date +%Y%m%d_%H%M%S).md"
        echo "## 🚨 斷言錯誤追蹤 - $(date)" > "$ASSERTION_TRACK"
        echo "- 🔄 **[測試邏輯] 發現 $ASSERTION_ERRORS 個斷言錯誤**" >> "$ASSERTION_TRACK"
        echo "  - 影響評估: High" >> "$ASSERTION_TRACK"
        echo "  - 預期修復時間: 下一循環" >> "$ASSERTION_TRACK"
        log "📋 已生成斷言錯誤追蹤: $ASSERTION_TRACK"
    fi
fi

# 5. 效能分析
log "⚡ 測試效能分析"

if [ -f "coverage-private/test-start-time.txt" ]; then
    START_TIME=$(cat "coverage-private/test-start-time.txt")
    CURRENT_TIME=$(date +%s)
    DURATION=$((CURRENT_TIME - START_TIME))

    log "⏱️  測試執行時間: ${DURATION}秒"

    if [ "$DURATION" -gt 300 ]; then # 超過5分鐘
        log "⚠️  測試執行時間超過5分鐘，建議檢查效能"

        PERF_TRACK="$PROJECT_ROOT/.claude/hook-logs/test-performance-$(date +%Y%m%d_%H%M%S).md"
        echo "## 🚨 測試效能問題 - $(date)" > "$PERF_TRACK"
        echo "- 🔄 **[效能問題] 測試執行時間過長 (${DURATION}秒)**" >> "$PERF_TRACK"
        echo "  - 影響評估: Medium" >> "$PERF_TRACK"
        echo "  - 預期修復時間: 規劃中" >> "$PERF_TRACK"
        log "📋 已生成效能問題追蹤: $PERF_TRACK"
    elif [ "$DURATION" -lt 60 ]; then
        log "✅ 測試執行效能良好"
    fi
fi

# 6. 生成測試摘要報告
log "📋 生成測試摘要報告"

SUMMARY_FILE="$PROJECT_ROOT/.claude/hook-logs/test-summary-$(date +%Y%m%d_%H%M%S).md"
echo "# 測試執行摘要 - $(date)" > "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"
echo "## 基本資訊" >> "$SUMMARY_FILE"
echo "- 測試狀態: $TEST_STATUS" >> "$SUMMARY_FILE"
echo "- 執行時間: ${DURATION:-未知}秒" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

if [ "$TEST_STATUS" != "pass" ]; then
    echo "## 問題統計" >> "$SUMMARY_FILE"
    echo "- 語法錯誤: $SYNTAX_ERRORS" >> "$SUMMARY_FILE"
    echo "- 參考錯誤: $REFERENCE_ERRORS" >> "$SUMMARY_FILE"
    echo "- 類型錯誤: $TYPE_ERRORS" >> "$SUMMARY_FILE"
    echo "- 斷言錯誤: $ASSERTION_ERRORS" >> "$SUMMARY_FILE"
    echo "" >> "$SUMMARY_FILE"
    echo "## ⚠️  立即行動要求" >> "$SUMMARY_FILE"
    echo "根據CLAUDE.md三大鐵律，必須立即修正所有測試問題！" >> "$SUMMARY_FILE"
fi

log "📋 測試摘要報告: $SUMMARY_FILE"
log "✅ PostToolUse Hook (Test) 分析完成"

# 返回成功 (不阻止後續操作)
exit 0