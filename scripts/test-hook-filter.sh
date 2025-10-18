#!/bin/bash

# test-hook-filter.sh
# Hook 系統過濾機制自動化測試腳本

# 載入通用函數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../hooks/common-functions.sh"

# 設定專案環境
if ! setup_project_environment; then
    echo "錯誤: 無法設定專案環境" >&2
    exit 1
fi

PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
TEST_RESULTS="$PROJECT_ROOT/.claude/hook-logs/filter-test-results.md"
TEMP_DIR="$PROJECT_ROOT/.claude/hook-logs/.test-temp"

# 確保目錄存在
mkdir -p "$TEMP_DIR"

# 測試結果統計
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 顏色定義
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日誌函數
log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}✅ PASS${NC} $1"
}

log_fail() {
    echo -e "${RED}❌ FAIL${NC} $1"
}

log_info() {
    echo -e "${YELLOW}ℹ️  INFO${NC} $1"
}

# 初始化測試報告
init_report() {
    cat > "$TEST_RESULTS" << EOF
# Hook 過濾機制測試結果

**測試時間**: $(date '+%Y-%m-%d %H:%M:%S')
**專案路徑**: $PROJECT_ROOT

## 測試摘要

EOF
}

# 完成測試報告
finish_report() {
    cat >> "$TEST_RESULTS" << EOF

## 測試統計

- **總測試數**: $TOTAL_TESTS
- **通過**: $PASSED_TESTS ✅
- **失敗**: $FAILED_TESTS ❌
- **通過率**: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%

---

*此報告由自動化測試腳本生成*
EOF

    echo ""
    echo "======================================"
    echo "測試統計"
    echo "======================================"
    echo "總測試數: $TOTAL_TESTS"
    echo -e "${GREEN}通過: $PASSED_TESTS${NC}"
    echo -e "${RED}失敗: $FAILED_TESTS${NC}"
    echo "通過率: $(( PASSED_TESTS * 100 / TOTAL_TESTS ))%"
    echo "======================================"
    echo ""
    echo "完整報告: $TEST_RESULTS"
}

# 執行單一測試
run_test() {
    local test_name="$1"
    local test_func="$2"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    log_test "執行測試: $test_name"

    if $test_func; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        log_pass "$test_name"
        echo "### ✅ $test_name" >> "$TEST_RESULTS"
        echo "" >> "$TEST_RESULTS"
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        log_fail "$test_name"
        echo "### ❌ $test_name" >> "$TEST_RESULTS"
        echo "" >> "$TEST_RESULTS"
    fi
}

# 測試 1: should_check_file 函式 - 文件檔案
test_should_check_file_markdown() {
    # 一般 .md 檔案應該跳過
    if should_check_file "README.md"; then
        echo "- 失敗: README.md 應該被跳過" >> "$TEST_RESULTS"
        return 1
    fi

    # 工作日誌應該檢查
    if ! should_check_file "docs/work-logs/v0.12.0-main.md"; then
        echo "- 失敗: 工作日誌應該被檢查" >> "$TEST_RESULTS"
        return 1
    fi

    echo "- 通過: 文件檔案過濾正確" >> "$TEST_RESULTS"
    return 0
}

# 測試 2: should_check_file 函式 - 測試檔案
test_should_check_file_test() {
    # 測試檔案應該跳過
    if should_check_file "test/widget_test.dart"; then
        echo "- 失敗: 測試檔案應該被跳過" >> "$TEST_RESULTS"
        return 1
    fi

    if should_check_file "lib/utils_test.dart"; then
        echo "- 失敗: _test.dart 檔案應該被跳過" >> "$TEST_RESULTS"
        return 1
    fi

    echo "- 通過: 測試檔案過濾正確" >> "$TEST_RESULTS"
    return 0
}

# 測試 3: should_check_file 函式 - Hook 檔案
test_should_check_file_hooks() {
    # Hook 系統檔案應該跳過
    if should_check_file ".claude/hooks/post-edit-hook.sh"; then
        echo "- 失敗: Hook 檔案應該被跳過" >> "$TEST_RESULTS"
        return 1
    fi

    echo "- 通過: Hook 檔案過濾正確" >> "$TEST_RESULTS"
    return 0
}

# 測試 4: should_check_file 函式 - 生成檔案
test_should_check_file_generated() {
    # 生成檔案應該跳過
    if should_check_file "lib/models/book.g.dart"; then
        echo "- 失敗: .g.dart 檔案應該被跳過" >> "$TEST_RESULTS"
        return 1
    fi

    if should_check_file "lib/models/book.freezed.dart"; then
        echo "- 失敗: .freezed.dart 檔案應該被跳過" >> "$TEST_RESULTS"
        return 1
    fi

    echo "- 通過: 生成檔案過濾正確" >> "$TEST_RESULTS"
    return 0
}

# 測試 5: should_check_file 函式 - 程式碼檔案
test_should_check_file_code() {
    # 程式碼檔案應該檢查
    if ! should_check_file "lib/main.dart"; then
        echo "- 失敗: 程式碼檔案應該被檢查" >> "$TEST_RESULTS"
        return 1
    fi

    if ! should_check_file "lib/utils/helper.dart"; then
        echo "- 失敗: 程式碼檔案應該被檢查" >> "$TEST_RESULTS"
        return 1
    fi

    echo "- 通過: 程式碼檔案檢查正確" >> "$TEST_RESULTS"
    return 0
}

# 測試 6: filter_files_for_dev_check 函式
test_filter_files_for_dev_check() {
    # 建立測試輸入
    local test_input="M README.md
M lib/main.dart
M test/widget_test.dart
M docs/work-logs/v0.12.0-main.md
M .claude/hooks/test.sh"

    # 執行過濾
    local filtered=$(filter_files_for_dev_check "$test_input")

    # 驗證結果
    if echo "$filtered" | grep -q "README.md"; then
        echo "- 失敗: README.md 不應出現在結果中" >> "$TEST_RESULTS"
        return 1
    fi

    if ! echo "$filtered" | grep -q "lib/main.dart"; then
        echo "- 失敗: lib/main.dart 應該出現在結果中" >> "$TEST_RESULTS"
        return 1
    fi

    if echo "$filtered" | grep -q "widget_test.dart"; then
        echo "- 失敗: widget_test.dart 不應出現在結果中" >> "$TEST_RESULTS"
        return 1
    fi

    if ! echo "$filtered" | grep -q "v0.12.0-main.md"; then
        echo "- 失敗: 工作日誌應該出現在結果中" >> "$TEST_RESULTS"
        return 1
    fi

    if echo "$filtered" | grep -q ".claude/hooks"; then
        echo "- 失敗: Hook 檔案不應出現在結果中" >> "$TEST_RESULTS"
        return 1
    fi

    echo "- 通過: 過濾函式運作正確" >> "$TEST_RESULTS"
    echo "- 過濾結果: $(echo "$filtered" | tr '\n' ',' | sed 's/,$//')" >> "$TEST_RESULTS"
    return 0
}

# 測試 7: 邊界案例 - 空輸入
test_filter_empty_input() {
    local filtered=$(filter_files_for_dev_check "")

    if [ -n "$filtered" ]; then
        echo "- 失敗: 空輸入應該返回空結果" >> "$TEST_RESULTS"
        return 1
    fi

    echo "- 通過: 空輸入處理正確" >> "$TEST_RESULTS"
    return 0
}

# 測試 8: 邊界案例 - 特殊字元檔名
test_filter_special_chars() {
    local test_input="M lib/models/book-model.dart
M lib/utils/api_helper.dart"

    local filtered=$(filter_files_for_dev_check "$test_input")

    if ! echo "$filtered" | grep -q "book-model.dart"; then
        echo "- 失敗: 包含特殊字元的檔名應該正常處理" >> "$TEST_RESULTS"
        return 1
    fi

    echo "- 通過: 特殊字元檔名處理正確" >> "$TEST_RESULTS"
    return 0
}

# 主測試流程
main() {
    echo "======================================"
    echo "Hook 系統過濾機制測試"
    echo "======================================"
    echo ""

    # 初始化報告
    init_report

    # 執行所有測試
    run_test "測試 1: 文件檔案過濾" test_should_check_file_markdown
    run_test "測試 2: 測試檔案過濾" test_should_check_file_test
    run_test "測試 3: Hook 檔案過濾" test_should_check_file_hooks
    run_test "測試 4: 生成檔案過濾" test_should_check_file_generated
    run_test "測試 5: 程式碼檔案檢查" test_should_check_file_code
    run_test "測試 6: 過濾函式整合測試" test_filter_files_for_dev_check
    run_test "測試 7: 空輸入邊界測試" test_filter_empty_input
    run_test "測試 8: 特殊字元檔名測試" test_filter_special_chars

    # 完成報告
    finish_report

    # 清理臨時檔案
    rm -rf "$TEMP_DIR"

    # 返回結果
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${GREEN}所有測試通過！${NC}"
        return 0
    else
        echo -e "${RED}有 $FAILED_TESTS 個測試失敗${NC}"
        return 1
    fi
}

# 執行測試
main "$@"
