#!/bin/bash

# task-avoidance-block-check.sh
# PreToolUse Hook: 檢查是否存在任務逃避阻止狀態

# 設定路徑
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BLOCK_FILE="$PROJECT_ROOT/.claude/TASK_AVOIDANCE_BLOCK"
FIX_MODE_FILE="$PROJECT_ROOT/.claude/TASK_AVOIDANCE_FIX_MODE"

cd "$PROJECT_ROOT"

# 檢查是否存在修復模式檔案 (新機制)
if [ -f "$FIX_MODE_FILE" ]; then
    echo ""
    echo "🔧🔧🔧 修復模式啟動 🔧🔧🔧"
    echo ""
    echo "✅ 系統已進入修復模式，允許修正逃避問題"
    echo ""

    # 讀取修復模式資訊
    if [ -r "$FIX_MODE_FILE" ]; then
        source "$FIX_MODE_FILE"
        echo "📋 修復原因: $FIX_REASON"
        echo "⏰ 開始時間: $START_TIME"
        echo "📄 詳細報告: $REPORT_FILE"
        echo "🔢 問題數量: $DETECTED_ISSUES_COUNT"
    fi

    echo ""
    echo "🔧 修復步驟:"
    echo "1. 查看詳細報告了解具體問題"
    echo "2. 移除所有逃避性語言"
    echo "3. 完整解決所有技術問題"
    echo "4. 確保所有測試通過"
    echo "5. 執行: ./scripts/fix-mode-complete.sh"
    echo ""
    echo "💡 修復模式將在30分鐘後自動過期"
    echo ""

    # 檢查是否過期
    if [ -n "$(find "$FIX_MODE_FILE" -mmin +30 2>/dev/null)" ]; then
        echo "⚠️  修復模式已過期，請重新執行檢查"
        rm -f "$FIX_MODE_FILE"

        # AI 提示觸發機制 - 修復模式過期提醒
        echo ""
        echo "🤖 CLAUDE AI PROMPT TRIGGER 🤖"
        echo "NOTICE: Fix mode has expired. Please re-run task avoidance detection."
        echo ""
    fi

    # 修復模式下允許繼續操作
    exit 0

# 檢查是否存在舊的阻止檔案 (向後相容)
elif [ -f "$BLOCK_FILE" ]; then
    echo ""
    echo "🚨🚨🚨 任務逃避阻止狀態 🚨🚨🚨"
    echo ""
    echo "❌ 偵測到任務逃避行為，當前操作被阻止"
    echo ""

    # 讀取阻止資訊
    if [ -r "$BLOCK_FILE" ]; then
        source "$BLOCK_FILE"
        echo "📋 阻止原因: $BLOCK_REASON"
        echo "⏰ 偵測時間: $DETECTION_TIME"
        echo "📄 詳細報告: $REPORT_FILE"
        echo "🔢 問題數量: $DETECTED_ISSUES_COUNT"
    fi

    echo ""
    echo "🔧 修正步驟:"
    echo "1. 查看詳細報告了解具體問題"
    echo "2. 按照永不放棄鐵律修正所有逃避行為"
    echo "3. 移除所有禁用詞彙並完整解決問題"
    echo "4. 確保所有測試通過且無 ESLint 錯誤"
    echo "5. 執行: rm .claude/TASK_AVOIDANCE_BLOCK"
    echo ""
    echo "💡 參考修正腳本: .claude/hook-logs/force-fix-avoidance.sh"
    echo ""
    echo "⚠️  在修正完成前，所有開發操作都將被阻止"
    echo ""

    # AI 提示觸發機制 - 引導 Claude 優先處理逃避問題
    echo ""
    echo "🤖 CLAUDE AI PROMPT TRIGGER 🤖"
    echo "URGENT: Task avoidance detected. Please prioritize fixing avoidance issues before continuing."
    echo "Required actions:"
    echo "1. Remove all forbidden phrases from work logs"
    echo "2. Fix all skipped tests and ESLint errors"
    echo "3. Address technical debt properly"
    echo "4. Execute: rm .claude/TASK_AVOIDANCE_BLOCK when complete"
    echo ""
    echo "⚠️  警告：任務逃避偵測狀態存在，AI 應優先處理這些問題"
fi

# 沒有阻止狀態，允許繼續
exit 0