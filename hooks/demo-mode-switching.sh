#!/bin/bash
# Hook 模式切換功能示範腳本
# 用於展示 Strict 和 Warning 模式的差異

set -e

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
HOOK_SCRIPT="$PROJECT_ROOT/.claude/hooks/task-dispatch-readiness-check.py"
LOG_DIR="$PROJECT_ROOT/.claude/hook-logs"

echo "=========================================="
echo "🔧 Hook 模式切換功能示範"
echo "=========================================="
echo ""

# 建立測試用 JSON 輸入（錯誤分派：Hook 開發 → Flutter 開發者）
TEST_INPUT_WRONG=$(cat <<'EOF'
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Task",
  "tool_input": {
    "prompt": "開發 Hook 腳本來檢查代理人分派",
    "subagent_type": "parsley-flutter-developer",
    "description": "開發 Hook 腳本"
  }
}
EOF
)

# 建立測試用 JSON 輸入（正確分派：Hook 開發 → Hook 架構師）
TEST_INPUT_CORRECT=$(cat <<'EOF'
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Task",
  "tool_input": {
    "prompt": "開發 Hook 腳本來檢查代理人分派",
    "subagent_type": "basil-hook-architect",
    "description": "開發 Hook 腳本"
  }
}
EOF
)

# 測試 1: Strict 模式（預設）
echo "📋 測試 1: Strict 模式（預設）"
echo "-------------------------------------------"
echo "場景：錯誤分派（Hook 開發 → Flutter 開發者）"
echo "預期：阻擋執行 + 返回錯誤訊息"
echo ""

unset HOOK_MODE  # 確保使用預設值

echo "執行 Hook..."
if echo "$TEST_INPUT_WRONG" | "$HOOK_SCRIPT" 2>&1; then
    echo "❌ 錯誤：應該被阻擋但卻執行了"
    exit 1
else
    echo "✅ 正確：執行被阻擋"
fi
echo ""

# 測試 2: Warning 模式
echo "📋 測試 2: Warning 模式"
echo "-------------------------------------------"
echo "場景：錯誤分派（Hook 開發 → Flutter 開發者）"
echo "預期：顯示警告 + 允許執行"
echo ""

export HOOK_MODE=warning

echo "執行 Hook..."
OUTPUT=$(echo "$TEST_INPUT_WRONG" | "$HOOK_SCRIPT" 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 正確：允許執行（Exit Code: 0）"
    echo ""
    echo "輸出訊息："
    echo "$OUTPUT" | grep "WARNING" || echo "（無警告訊息）"
else
    echo "❌ 錯誤：應該允許執行但被阻擋了"
    exit 1
fi
echo ""

# 測試 3: 檢查警告記錄
echo "📋 測試 3: 檢查警告記錄"
echo "-------------------------------------------"

WARNING_FILE="$LOG_DIR/agent-dispatch-warnings.jsonl"

if [ -f "$WARNING_FILE" ]; then
    echo "✅ 警告記錄檔案存在"
    echo ""
    echo "最近一筆記錄："
    tail -n 1 "$WARNING_FILE" | jq '.' 2>/dev/null || tail -n 1 "$WARNING_FILE"
else
    echo "⚠️ 警告記錄檔案不存在（可能是 Hook 未記錄）"
fi
echo ""

# 測試 4: 正確分派測試（兩種模式都應通過）
echo "📋 測試 4: 正確分派測試"
echo "-------------------------------------------"
echo "場景：正確分派（Hook 開發 → Hook 架構師）"
echo "預期：兩種模式都允許執行"
echo ""

# Strict 模式
echo "測試 Strict 模式..."
unset HOOK_MODE
if echo "$TEST_INPUT_CORRECT" | "$HOOK_SCRIPT" > /dev/null 2>&1; then
    echo "✅ Strict 模式：正確分派通過"
else
    echo "❌ Strict 模式：正確分派被阻擋（錯誤）"
    exit 1
fi

# Warning 模式
echo "測試 Warning 模式..."
export HOOK_MODE=warning
if echo "$TEST_INPUT_CORRECT" | "$HOOK_SCRIPT" > /dev/null 2>&1; then
    echo "✅ Warning 模式：正確分派通過"
else
    echo "❌ Warning 模式：正確分派被阻擋（錯誤）"
    exit 1
fi
echo ""

# 總結
echo "=========================================="
echo "✅ 所有測試通過！"
echo "=========================================="
echo ""
echo "📚 使用方式："
echo ""
echo "  切換到 Warning 模式："
echo "    export HOOK_MODE=warning"
echo ""
echo "  切換到 Strict 模式："
echo "    export HOOK_MODE=strict"
echo ""
echo "  使用配置檔案："
echo "    參考 .claude/hook-config.json.example"
echo ""
echo "  查看警告記錄："
echo "    cat .claude/hook-logs/agent-dispatch-warnings.jsonl"
echo ""
