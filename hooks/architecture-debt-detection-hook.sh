#!/bin/bash

# architecture-debt-detection-hook.sh
# 架構債務偵測 Hook - 檢測重複實作和架構設計問題
# 強制執行正確的修正順序：文件 → 測試 → 實作

# 載入通用函數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 設定專案環境
if ! setup_project_environment; then
    echo "錯誤: 無法設定專案環境" >&2
    exit 1
fi

PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
HOOK_LOGS_DIR="$CLAUDE_LOGS_DIR"
ARCHITECTURE_ISSUES_FILE="$HOOK_LOGS_DIR/architecture-issues.md"

# 顏色定義
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 日誌函數
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$HOOK_LOGS_DIR/architecture-debt-$(date +%Y%m%d).log"
}

error_log() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$HOOK_LOGS_DIR/architecture-debt-$(date +%Y%m%d).log"
}

warning_log() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$HOOK_LOGS_DIR/architecture-debt-$(date +%Y%m%d).log"
}

# =============================================================================
# 架構債務偵測邏輯
# =============================================================================

detect_duplicate_implementations() {
    # 使用重導向分離日誌和檢測結果
    {
        log "🔍 檢查重複實作模式..."
    } >&2

    local duplicate_found=false
    local issues=""

    # 檢查是否有多個相同名稱的服務在不同 Domain
    local service_files=$(find "$PROJECT_ROOT/lib" -name "*_service.dart" -o -name "*_api.dart" 2>/dev/null)

    # 過濾檔案
    local filtered_files=""
    for file in $service_files; do
        if should_check_file "$file"; then
            filtered_files="$filtered_files $file"
        fi
    done
    service_files="$filtered_files"

    # 建立服務名稱對應檔案的映射（使用檔案儲存，避免 macOS bash 版本問題）
    local service_map_file="$HOOK_LOGS_DIR/.service_map.tmp"
    > "$service_map_file"

    for file in $service_files; do
        # 提取服務名稱（移除路徑和副檔名）
        local service_name=$(basename "$file" .dart)

        # 檢查是否已經存在相同名稱的服務
        local existing_file=$(grep "^$service_name=" "$service_map_file" | cut -d'=' -f2)
        if [[ -n "$existing_file" ]]; then
            duplicate_found=true
            issues+="- **重複服務**: $service_name 存在於:\n"
            issues+="  - $existing_file\n"
            issues+="  - $file\n\n"
            { warning_log "⚠️  發現重複服務: $service_name"; } >&2
        else
            echo "$service_name=$file" >> "$service_map_file"
        fi
    done

    # 特定檢查 GoogleBooksApiService 類型的重複
    local google_books_count=$(grep -r "class.*GoogleBooks.*Service" "$PROJECT_ROOT/lib" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$google_books_count" -gt 1 ]; then
        duplicate_found=true
        issues+="- **Google Books API 重複實作**: 發現 $google_books_count 個實作\n\n"
        { warning_log "⚠️  發現 Google Books API 多重實作: $google_books_count 個"; } >&2
    fi

    # 檢查相似的 API 整合邏輯
    local api_integration_count=$(grep -r "Future.*query.*Book\|Future.*search.*Book" "$PROJECT_ROOT/lib" --include="*.dart" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$api_integration_count" -gt 3 ]; then
        { warning_log "⚠️  發現過多的書籍查詢方法: $api_integration_count 個，可能存在重複邏輯"; } >&2
        issues+="- **API 查詢邏輯分散**: 發現 $api_integration_count 個書籍查詢方法\n\n"
    fi

    # 清理臨時檔案
    rm -f "$service_map_file"

    if [ "$duplicate_found" = true ]; then
        echo "$issues"
        return 0
    fi

    return 1
}

check_architecture_principles() {
    {
        log "🏗️  檢查架構原則遵循狀況..."
    } >&2

    local violations=""
    local has_violations=false

    # 檢查 Domain 層是否直接依賴具體實作
    local domain_concrete_deps=$(grep -r "import.*infrastructure" "$PROJECT_ROOT/lib/domains" --include="*.dart" 2>/dev/null | grep -v "abstract\|interface" | wc -l | tr -d ' ')
    if [ "$domain_concrete_deps" -gt 0 ]; then
        has_violations=true
        violations+="- **Domain 層依賴具體實作**: 發現 $domain_concrete_deps 個違規\n"
        { warning_log "⚠️  Domain 層不應直接依賴 Infrastructure 具體實作"; } >&2
    fi

    # 檢查是否有跨 Domain 的直接依賴
    local cross_domain_deps=$(find "$PROJECT_ROOT/lib/domains" -name "*.dart" -exec grep -l "import.*domains/.*/.*domains/" {} \; 2>/dev/null | wc -l | tr -d ' ')
    if [ "$cross_domain_deps" -gt 0 ]; then
        has_violations=true
        violations+="- **跨 Domain 直接依賴**: 發現 $cross_domain_deps 個違規\n"
        { warning_log "⚠️  Domain 之間不應有直接依賴"; } >&2
    fi

    if [ "$has_violations" = true ]; then
        echo "$violations"
        return 0
    fi

    return 1
}

check_test_architecture_consistency() {
    {
        log "🧪 檢查測試架構一致性..."
    } >&2

    local issues=""
    local has_issues=false

    # 檢查是否有多個 Mock 實作相同服務
    local mock_duplicates=$(find "$PROJECT_ROOT/test" -name "mock_*.dart" -exec basename {} \; | sort | uniq -d)
    if [ -n "$mock_duplicates" ]; then
        has_issues=true
        issues+="- **Mock 服務重複**: 發現以下 Mock 有多個版本:\n"
        for mock in $mock_duplicates; do
            issues+="  - $mock\n"
        done
        { warning_log "⚠️  發現重複的 Mock 服務實作"; } >&2
    fi

    # 檢查測試中是否使用真實服務而非 Mock
    local real_service_in_tests=$(grep -r "= [A-Z][a-zA-Z]*Service()" "$PROJECT_ROOT/test" --include="*_test.dart" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$real_service_in_tests" -gt 0 ]; then
        has_issues=true
        issues+="- **測試使用真實服務**: 發現 $real_service_in_tests 處違規\n"
        { warning_log "⚠️  單元測試不應使用真實服務實作"; } >&2
    fi

    if [ "$has_issues" = true ]; then
        echo "$issues"
        return 0
    fi

    return 1
}

generate_refactoring_order() {
    cat <<EOF

## 🔄 正確的架構債務修正順序

### Phase 1: 規劃文件修正 📝
1. 檢查並更新架構設計文件
2. 統一 API 整合需求描述
3. 移除重複的設計規格

### Phase 2: 測試架構統一 🧪
1. 建立統一的 Mock 服務介面
2. 統一測試環境管理
3. 確保測試隔離原則

### Phase 3: Domain 重構 🏗️
1. 移除重複實作
2. 實施依賴注入模式
3. 確保 Domain 純淨性

### Phase 4: Infrastructure 建立 🔧
1. 建立統一的基礎設施層
2. 實作抽象介面
3. 配置依賴注入

**重要**: 絕不可跳過前面的步驟直接進行程式碼重構！

EOF
}

write_architecture_issues_report() {
    local issues="$1"

    # 先寫入報告內容，使用 printf 處理轉義字符
    {
        echo "# 架構債務偵測報告"
        echo ""
        echo "**檢測時間**: $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        echo "## 🚨 發現的架構問題"
        echo ""
        printf "%b" "$issues"
        echo ""
        echo "## ✅ 建議修正流程"
        echo ""
        generate_refactoring_order
        echo ""
        echo "## ⚠️ 注意事項"
        echo ""
        echo "1. **不要直接重構程式碼** - 先修正文件和測試"
        echo "2. **遵循正確順序** - 文件 → 測試 → 實作 → 介面"
        echo "3. **確保測試通過** - 每個階段都要維持 100% 測試通過率"
        echo "4. **記錄變更** - 在工作日誌中詳細記錄每個修正步驟"
        echo ""
        echo "---"
        echo ""
        echo "*此報告由架構債務偵測 Hook 自動生成*"
    } > "$ARCHITECTURE_ISSUES_FILE"

    log "📄 架構問題報告已寫入: $ARCHITECTURE_ISSUES_FILE"
}

trigger_architecture_review() {
    error_log "🚨 偵測到架構債務，觸發架構審查流程"

    # 建立架構審查標記檔案
    touch "$PROJECT_ROOT/.claude/ARCHITECTURE_REVIEW_REQUIRED"

    # 輸出警告訊息到 stderr（避免干擾 Hook 系統）
    {
        cat <<EOF

${RED}════════════════════════════════════════════════════════════════${NC}
${RED}🚨 架構債務警告 🚨${NC}
${RED}════════════════════════════════════════════════════════════════${NC}

${YELLOW}偵測到潛在的架構設計問題！${NC}

${CYAN}請遵循以下步驟：${NC}

1. ${GREEN}查看架構問題報告${NC}
   cat $ARCHITECTURE_ISSUES_FILE

2. ${GREEN}執行架構審查${NC}
   - 檢查規劃文件是否需要更新
   - 確認測試架構是否一致
   - 評估重構的影響範圍

3. ${GREEN}按照正確順序修正${NC}
   文件 → 測試 → 實作 → 介面

${YELLOW}⚠️  請勿直接進行程式碼重構！${NC}

${RED}════════════════════════════════════════════════════════════════${NC}

EOF
    } >&2

    return 0
}

# =============================================================================
# 主執行邏輯
# =============================================================================

main() {
    log "🏗️  架構債務偵測 Hook 開始執行"

    local has_issues=false
    local all_issues=""

    # 使用臨時檔案避免日誌混入變數
    local temp_dir="$HOOK_LOGS_DIR/.temp"
    mkdir -p "$temp_dir"

    local duplicate_file="$temp_dir/duplicate.tmp"
    local arch_file="$temp_dir/arch.tmp"
    local test_file="$temp_dir/test.tmp"

    # 執行各項檢查，將純淨結果寫入臨時檔案，日誌重導向到 stderr
    if detect_duplicate_implementations 2>&2 > "$duplicate_file" && [ -s "$duplicate_file" ]; then
        has_issues=true
        all_issues+="### 重複實作問題\n$(cat "$duplicate_file")\n"
    fi

    if check_architecture_principles 2>&2 > "$arch_file" && [ -s "$arch_file" ]; then
        has_issues=true
        all_issues+="### 架構原則違規\n$(cat "$arch_file")\n"
    fi

    if check_test_architecture_consistency 2>&2 > "$test_file" && [ -s "$test_file" ]; then
        has_issues=true
        all_issues+="### 測試架構問題\n$(cat "$test_file")\n"
    fi

    # 清理臨時檔案
    rm -rf "$temp_dir"

    # 如果發現問題，生成報告並觸發審查
    if [ "$has_issues" = true ]; then
        log "📋 生成正確的重構順序..."
        write_architecture_issues_report "$all_issues"
        trigger_architecture_review
        log "🚨 架構債務已記錄，請查看報告進行修正"
        # Hook 系統中不使用 exit 1，通過報告文件傳遞問題
    else
        log "✅ 未發現架構債務問題"
        # 清理架構審查標記（如果存在）
        rm -f "$PROJECT_ROOT/.claude/ARCHITECTURE_REVIEW_REQUIRED"
    fi

    log "✅ 架構債務偵測 Hook 執行完成"
}

# 執行主函數
main "$@"