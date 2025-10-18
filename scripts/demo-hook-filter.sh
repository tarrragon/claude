#!/bin/bash

# demo-hook-filter.sh
# Hook 系統過濾機制功能演示腳本

# 載入通用函數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../hooks/common-functions.sh"

# 設定專案環境
if ! setup_project_environment; then
    echo "錯誤: 無法設定專案環境" >&2
    exit 1
fi

# 顏色定義
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "======================================"
echo "Hook 系統檔案過濾機制演示"
echo "======================================"
echo ""

# 演示函式
demo_filter() {
    local file="$1"
    local expected="$2"

    echo -n "檢查檔案: ${CYAN}$file${NC} ... "

    if should_check_file "$file"; then
        if [ "$expected" = "check" ]; then
            echo -e "${GREEN}✅ 需要檢查${NC} (正確)"
        else
            echo -e "${RED}❌ 需要檢查${NC} (錯誤，應該跳過)"
        fi
    else
        if [ "$expected" = "skip" ]; then
            echo -e "${YELLOW}⏭️  跳過檢查${NC} (正確)"
        else
            echo -e "${RED}❌ 跳過檢查${NC} (錯誤，應該檢查)"
        fi
    fi
}

# 演示 1: 文件檔案
echo -e "${BLUE}=== 文件檔案 ===${NC}"
demo_filter "README.md" "skip"
demo_filter "docs/architecture.md" "skip"
demo_filter "CHANGELOG.md" "skip"
demo_filter "docs/work-logs/v0.12.0-main.md" "check"
demo_filter "docs/work-logs/v0.12.1-task.md" "check"
echo ""

# 演示 2: 測試檔案
echo -e "${BLUE}=== 測試檔案 ===${NC}"
demo_filter "test/widget_test.dart" "skip"
demo_filter "test/unit/book_test.dart" "skip"
demo_filter "lib/utils_test.dart" "skip"
demo_filter "spec/book_spec.js" "skip"
echo ""

# 演示 3: Hook 系統檔案
echo -e "${BLUE}=== Hook 系統檔案 ===${NC}"
demo_filter ".claude/hooks/post-edit-hook.sh" "skip"
demo_filter ".claude/hooks/common-functions.sh" "skip"
demo_filter ".claude/scripts/test-hook-filter.sh" "skip"
echo ""

# 演示 4: 生成檔案
echo -e "${BLUE}=== 生成檔案 ===${NC}"
demo_filter "lib/models/book.g.dart" "skip"
demo_filter "lib/models/book.freezed.dart" "skip"
demo_filter "lib/generated/intl/messages_en.dart" "skip"
echo ""

# 演示 5: 文檔目錄
echo -e "${BLUE}=== 文檔目錄 ===${NC}"
demo_filter "docs/api.md" "skip"
demo_filter "docs/design/ui.md" "skip"
demo_filter "docs/work-logs/archive/v0.11.0.md" "check"
echo ""

# 演示 6: 程式碼檔案（應該檢查）
echo -e "${BLUE}=== 程式碼檔案 ===${NC}"
demo_filter "lib/main.dart" "check"
demo_filter "lib/domains/library/entities/book.dart" "check"
demo_filter "lib/core/errors/errors.dart" "check"
demo_filter "src/index.js" "check"
demo_filter "src/utils/helper.dart" "check"
echo ""

# 演示 7: 過濾函式整合
echo -e "${BLUE}=== 過濾函式整合演示 ===${NC}"
echo ""

TEST_INPUT="M README.md
M lib/main.dart
M test/widget_test.dart
M docs/work-logs/v0.12.0-main.md
M .claude/hooks/test.sh
M lib/models/book.g.dart
M lib/utils/helper.dart"

echo -e "${YELLOW}輸入檔案清單:${NC}"
echo "$TEST_INPUT" | sed 's/^/  /'
echo ""

FILTERED=$(filter_files_for_dev_check "$TEST_INPUT")

echo -e "${GREEN}過濾後結果 (只保留需要檢查的檔案):${NC}"
if [ -n "$FILTERED" ]; then
    echo "$FILTERED" | sed 's/^/  /'
else
    echo "  (無檔案需要檢查)"
fi
echo ""

# 統計資訊
TOTAL_FILES=$(echo "$TEST_INPUT" | wc -l | tr -d ' ')
FILTERED_FILES=$(echo "$FILTERED" | grep -c "^" 2>/dev/null || echo "0")
SKIPPED_FILES=$((TOTAL_FILES - FILTERED_FILES))

echo -e "${CYAN}統計資訊:${NC}"
echo "  總檔案數: $TOTAL_FILES"
echo "  需要檢查: $FILTERED_FILES"
echo "  已過濾: $SKIPPED_FILES"
echo ""

# 演示 8: 實際使用案例
echo -e "${BLUE}=== 實際使用案例 ===${NC}"
echo ""

echo -e "${YELLOW}案例 1: 編輯 README.md${NC}"
echo "  git status: M README.md"
echo -n "  Hook 行為: "
if should_check_file "README.md"; then
    echo -e "${RED}觸發檢查${NC}"
else
    echo -e "${GREEN}跳過檢查 (不觸發警告)${NC}"
fi
echo ""

echo -e "${YELLOW}案例 2: 修改程式碼${NC}"
echo "  git status: M lib/main.dart"
echo -n "  Hook 行為: "
if should_check_file "lib/main.dart"; then
    echo -e "${GREEN}觸發檢查 (正常執行)${NC}"
else
    echo -e "${RED}跳過檢查${NC}"
fi
echo ""

echo -e "${YELLOW}案例 3: 更新工作日誌${NC}"
echo "  git status: M docs/work-logs/v0.12.1-task.md"
echo -n "  Hook 行為: "
if should_check_file "docs/work-logs/v0.12.1-task.md"; then
    echo -e "${GREEN}觸發檢查 (保留檢查)${NC}"
else
    echo -e "${RED}跳過檢查${NC}"
fi
echo ""

echo -e "${YELLOW}案例 4: 混合修改${NC}"
MIXED_INPUT="M README.md
M lib/main.dart
M test/widget_test.dart"
echo "  git status:"
echo "$MIXED_INPUT" | sed 's/^/    /'
MIXED_FILTERED=$(filter_files_for_dev_check "$MIXED_INPUT")
echo "  過濾結果:"
echo "$MIXED_FILTERED" | sed 's/^/    /'
echo "  說明: 只檢查 lib/main.dart，其他檔案被過濾"
echo ""

# 結論
echo "======================================"
echo -e "${GREEN}演示完成！${NC}"
echo "======================================"
echo ""
echo "過濾機制特點:"
echo "  ✅ 文件編輯不觸發警告"
echo "  ✅ 測試檔案不觸發警告"
echo "  ✅ 程式碼檔案正常檢查"
echo "  ✅ 工作日誌保留檢查"
echo "  ✅ Hook 系統檔案被過濾"
echo ""
echo "相關文檔:"
echo "  - 測試計畫: .claude/hook-logs/hook-filter-test-plan.md"
echo "  - 實作總結: .claude/hook-logs/hook-filter-implementation-summary.md"
echo "  - 測試報告: .claude/hook-logs/filter-test-results.md"
echo ""
