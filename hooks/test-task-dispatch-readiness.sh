#!/bin/bash
# 測試任務分派準備度檢查 Hook

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$SCRIPT_DIR/task-dispatch-readiness-check.py"

echo "=========================================="
echo "任務分派準備度檢查 Hook - 測試套件"
echo "=========================================="
echo ""

# 測試函數
run_test() {
    local test_name="$1"
    local input_json="$2"
    local expected_result="$3"  # "allow" 或 "deny"

    echo "測試案例: $test_name"
    echo "---"

    # 執行 Hook
    result=$(echo "$input_json" | python3 "$HOOK_SCRIPT" 2>&1)
    exit_code=$?

    # 檢查結果
    if [ "$expected_result" == "deny" ]; then
        if echo "$result" | grep -q "permissionDecision.*deny"; then
            echo "✅ 通過 - 正確拒絕任務"
        else
            echo "❌ 失敗 - 應該拒絕但未拒絕"
            echo "實際輸出: $result"
        fi
    else
        if [ $exit_code -eq 0 ] && ! echo "$result" | grep -q "permissionDecision.*deny"; then
            echo "✅ 通過 - 正確允許任務"
        else
            echo "❌ 失敗 - 應該允許但被拒絕"
            echo "實際輸出: $result"
        fi
    fi

    echo ""
}

# 測試案例 1: 缺少所有參考文件
echo "========================================"
echo "測試案例 1: 缺少所有參考文件"
echo "========================================"

TEST_JSON_1=$(cat <<'EOF'
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Task",
  "tool_input": {
    "prompt": "請實作一個書籍新增功能",
    "subagent_type": "pepper-test-implementer"
  }
}
EOF
)

run_test "缺少所有參考文件" "$TEST_JSON_1" "deny"

# 測試案例 2: 只缺少 UseCase
echo "========================================"
echo "測試案例 2: 只缺少 UseCase"
echo "========================================"

TEST_JSON_2=$(cat <<'EOF'
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Task",
  "tool_input": {
    "prompt": "請實作書籍新增功能，處理 Event 3 使用者觸發新增，屬於 Application 層，依賴 BookRepository",
    "subagent_type": "pepper-test-implementer"
  }
}
EOF
)

run_test "只缺少 UseCase" "$TEST_JSON_2" "deny"

# 測試案例 3: 完整參考文件
echo "========================================"
echo "測試案例 3: 完整參考文件（應通過）"
echo "========================================"

TEST_JSON_3=$(cat <<'EOF'
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Task",
  "tool_input": {
    "prompt": "請實作 UC-01 書籍新增功能，處理 Event 3 使用者觸發新增，屬於 Application 層，依賴 BookRepository 和 Book Entity",
    "subagent_type": "pepper-test-implementer"
  }
}
EOF
)

run_test "完整參考文件" "$TEST_JSON_3" "allow"

# 測試案例 4: 非 Task 工具（應直接通過）
echo "========================================"
echo "測試案例 4: 非 Task 工具（應直接通過）"
echo "========================================"

TEST_JSON_4=$(cat <<'EOF'
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.dart",
    "content": "test content"
  }
}
EOF
)

run_test "非 Task 工具" "$TEST_JSON_4" "allow"

# 測試案例 5: 空 prompt（應拒絕）
echo "========================================"
echo "測試案例 5: 空 prompt（應拒絕）"
echo "========================================"

TEST_JSON_5=$(cat <<'EOF'
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Task",
  "tool_input": {
    "prompt": "",
    "subagent_type": "pepper-test-implementer"
  }
}
EOF
)

run_test "空 prompt" "$TEST_JSON_5" "deny"

# 測試案例 6: Clean Architecture 不同表達方式
echo "========================================"
echo "測試案例 6: Clean Architecture 不同表達方式"
echo "========================================"

TEST_JSON_6=$(cat <<'EOF'
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Task",
  "tool_input": {
    "prompt": "請實作 UC-02 書籍查詢功能，處理 Event 5 查詢請求，按照 Clean Architecture 原則設計，使用 Repository 和 UseCase",
    "subagent_type": "pepper-test-implementer"
  }
}
EOF
)

run_test "Clean Architecture 表達方式" "$TEST_JSON_6" "allow"

echo "=========================================="
echo "測試完成"
echo "=========================================="
