#!/bin/bash

# ================================================================================
# Hook 4: 階段完成驗證檢查
# ================================================================================
# 用途: 確保 TDD 四階段完成時達到所有品質標準
# 觸發時機: Phase 4 完成標記時或 Stop Hook 觸發時
# 阻塞級別: 高 (Exit Code 2 阻塞提交)
# 參考規範: implementation-adjustments.md - Hook 4
# ================================================================================

# 使用官方環境變數
PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/stage-completion-$(date +%Y%m%d_%H%M%S).log"
ISSUES_FILE="$PROJECT_ROOT/.claude/hook-logs/issues-to-track.md"

# 確保日誌目錄存在
mkdir -p "$PROJECT_ROOT/.claude/hook-logs"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日誌函數
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ================================================================================
# 檢查 1/5: 編譯完整性檢查
# ================================================================================
check_compilation_integrity() {
    log "${BLUE}🔍 檢查 1/5: 編譯完整性${NC}"

    cd "$PROJECT_ROOT"
    ANALYZE_OUTPUT=$(flutter analyze lib/ --no-fatal-warnings 2>&1)

    # 只檢查 error 級別問題
    ERROR_COUNT=$(echo "$ANALYZE_OUTPUT" | grep -c "error •" || true)

    if [ "$ERROR_COUNT" -gt 0 ]; then
        log "${RED}❌ 編譯完整性檢查失敗: 發現 $ERROR_COUNT 個 error${NC}"
        echo "$ANALYZE_OUTPUT" | grep "error •" | tee -a "$LOG_FILE"
        return 1
    fi

    log "${GREEN}✅ 編譯完整性檢查通過${NC}"
    return 0
}

# ================================================================================
# 檢查 2/5: 依賴路徑一致性檢查
# ================================================================================
check_dependency_path_consistency() {
    log "${BLUE}🔍 檢查 2/5: 依賴路徑一致性${NC}"

    cd "$PROJECT_ROOT"

    # 檢查 Target of URI doesn't exist
    URI_ERRORS=$(flutter analyze lib/ 2>&1 | grep -c "Target of URI doesn't exist" || true)

    # 檢查相對路徑導入
    RELATIVE_IMPORTS=$(grep -r "import '\.\." lib/ 2>/dev/null | wc -l | xargs)

    if [ "$URI_ERRORS" -gt 0 ] || [ "$RELATIVE_IMPORTS" -gt 0 ]; then
        log "${RED}❌ 依賴路徑一致性檢查失敗${NC}"
        log "   - URI 不存在錯誤: $URI_ERRORS"
        log "   - 相對路徑導入: $RELATIVE_IMPORTS"
        return 1
    fi

    log "${GREEN}✅ 依賴路徑一致性檢查通過${NC}"
    return 0
}

# ================================================================================
# 檢查 3/5: 測試通過率檢查
# ================================================================================
check_test_pass_rate() {
    log "${BLUE}🔍 檢查 3/5: 測試通過率${NC}"

    cd "$PROJECT_ROOT"
    TEST_OUTPUT=$(flutter test 2>&1)
    TEST_EXIT_CODE=$?

    # 檢查是否有測試失敗
    if [ $TEST_EXIT_CODE -ne 0 ] || echo "$TEST_OUTPUT" | grep -q "Some tests failed"; then
        log "${RED}❌ 測試通過率檢查失敗: 部分測試未通過${NC}"
        echo "$TEST_OUTPUT" | grep -E "FAILED|failed|Error" | tee -a "$LOG_FILE"
        return 1
    fi

    log "${GREEN}✅ 測試通過率檢查通過 (100%)${NC}"
    return 0
}

# ================================================================================
# 檢查 4/5: 重複實作檢查
# ================================================================================
check_duplicate_implementation() {
    log "${BLUE}🔍 檢查 4/5: 重複實作檢查${NC}"

    cd "$PROJECT_ROOT/lib"

    # 檢查重複檔案名稱
    DUPLICATE_FILES=$(find . -type f -name "*.dart" | sed 's|.*/||' | sort | uniq -d)

    # 檢查重複服務類別
    DUPLICATE_SERVICES=$(grep -rh "class.*Service" --include="*.dart" 2>/dev/null | sed 's/.*class \([^ {]*\).*/\1/' | sort | uniq -d)

    if [ -n "$DUPLICATE_FILES" ] || [ -n "$DUPLICATE_SERVICES" ]; then
        log "${YELLOW}⚠️  重複實作檢查警告 (非阻塞)${NC}"
        [ -n "$DUPLICATE_FILES" ] && log "   - 重複檔案: $DUPLICATE_FILES"
        [ -n "$DUPLICATE_SERVICES" ] && log "   - 重複服務: $DUPLICATE_SERVICES"
    else
        log "${GREEN}✅ 重複實作檢查通過${NC}"
    fi

    return 0  # 不阻塞
}

# ================================================================================
# 檢查 5/5: 架構一致性檢查
# ================================================================================
check_architecture_consistency() {
    log "${BLUE}🔍 檢查 5/5: 架構一致性${NC}"

    cd "$PROJECT_ROOT/lib"

    # 檢查 core → presentation 反向依賴
    CORE_TO_PRES=$(grep -r "import.*presentation" core/ 2>/dev/null | wc -l | xargs)

    # 檢查 domains → presentation 反向依賴
    DOMAIN_TO_PRES=$(grep -r "import.*presentation" domains/ 2>/dev/null | wc -l | xargs)

    # 檢查 domains → infrastructure 反向依賴
    DOMAIN_TO_INFRA=$(grep -r "import.*infrastructure" domains/ 2>/dev/null | wc -l | xargs)

    if [ "$CORE_TO_PRES" -gt 0 ] || [ "$DOMAIN_TO_PRES" -gt 0 ] || [ "$DOMAIN_TO_INFRA" -gt 0 ]; then
        log "${RED}❌ 架構一致性檢查失敗${NC}"
        [ "$CORE_TO_PRES" -gt 0 ] && log "   - core → presentation: $CORE_TO_PRES 處違規"
        [ "$DOMAIN_TO_PRES" -gt 0 ] && log "   - domains → presentation: $DOMAIN_TO_PRES 處違規"
        [ "$DOMAIN_TO_INFRA" -gt 0 ] && log "   - domains → infrastructure: $DOMAIN_TO_INFRA 處違規"
        return 1
    fi

    log "${GREEN}✅ 架構一致性檢查通過${NC}"
    return 0
}

# ================================================================================
# 修復模式機制
# ================================================================================
enter_fix_mode() {
    local failed_checks="$1"

    log "${RED}🚨 進入修復模式 - 階段完成驗證失敗${NC}"
    log ""
    log "${YELLOW}📋 失敗項目:${NC}"
    echo "$failed_checks" | tee -a "$LOG_FILE"
    log ""
    log "${GREEN}✅ 修復指引:${NC}"
    log "   1. 修正所有失敗檢查項目"
    log "   2. 重新執行階段驗證: .claude/hooks/stage-completion-validation-check.sh"
    log "   3. 確保 100% 通過後才能標記階段完成"

    # 記錄到 issues-to-track.md
    {
        echo ""
        echo "## 🚨 階段完成驗證失敗 - $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        echo "$failed_checks"
        echo ""
        echo "**修復步驟**:"
        echo "1. 修正所有失敗檢查項目"
        echo "2. 執行: \`.claude/hooks/stage-completion-validation-check.sh\`"
        echo "3. 確保 100% 通過後才能標記階段完成"
        echo ""
    } >> "$ISSUES_FILE"
}

# ================================================================================
# 主執行邏輯
# ================================================================================
main() {
    log "${BLUE}🚀 階段完成驗證開始${NC}"
    log ""

    local failed_checks=()

    # 執行 5 項檢查
    if ! check_compilation_integrity; then
        failed_checks+=("編譯完整性")
    fi

    if ! check_dependency_path_consistency; then
        failed_checks+=("依賴路徑一致性")
    fi

    if ! check_test_pass_rate; then
        failed_checks+=("測試通過率")
    fi

    check_duplicate_implementation  # 不加入 failed_checks (非阻塞)

    if ! check_architecture_consistency; then
        failed_checks+=("架構一致性")
    fi

    log ""

    # 判斷是否通過
    if [ ${#failed_checks[@]} -gt 0 ]; then
        local failed_list=$(IFS=$'\n'; echo "${failed_checks[*]}")
        enter_fix_mode "$failed_list"
        exit 2  # 阻塞錯誤
    fi

    log "${GREEN}✅ 階段完成驗證通過 - 所有檢查項目 100% 達標${NC}"
    log ""
    exit 0
}

# 執行主函數
main "$@"
