#!/bin/bash

# pre-design-dependency-check.sh
# Pre-Design Dependency Check Hook
# 確保 Phase 1 設計基於實際 Domain 模型定義，防止設計-實作脫節

# 載入通用函數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 設定專案環境
if ! setup_project_environment; then
    echo "錯誤: 無法設定專案環境" >&2
    exit 1
fi

# 日誌檔案
LOG_FILE="$CLAUDE_LOGS_DIR/pre-design-check-$(date +%Y%m%d_%H%M%S).log"

# 日誌函數
log() {
    log_with_timestamp "$LOG_FILE" "$1"
}

log "🔍 Pre-Design Dependency Check Hook: 開始執行"

# 檢測是否為 lavender Phase 1 任務分派
is_phase1_design_task() {
    # 檢查最近的命令或用戶輸入
    local recent_context="$1"

    if [[ -z "$recent_context" ]]; then
        return 1
    fi

    # 檢測關鍵詞
    if echo "$recent_context" | grep -qE "lavender.*Phase 1|Phase 1.*lavender"; then
        log "✅ 檢測到 lavender Phase 1 任務分派"
        return 0
    fi

    return 1
}

# 從任務描述中提取版本號
extract_version() {
    local task_description="$1"

    # 提取 v0.X.Y 格式
    local version=$(echo "$task_description" | grep -oE "v[0-9]+\.[0-9]+\.[0-9]+" | head -1)

    if [[ -n "$version" ]]; then
        log "📌 提取到版本號: $version"
        echo "$version"
        return 0
    fi

    log "⚠️  無法提取版本號"
    return 1
}

# 解析前置版本
get_previous_version() {
    local current_version="$1"  # v0.12.4

    # 解析版本號
    local major=$(echo "$current_version" | cut -d. -f1 | tr -d 'v')  # 0
    local minor=$(echo "$current_version" | cut -d. -f2)              # 12
    local patch=$(echo "$current_version" | cut -d. -f3)              # 4

    log "🔍 解析版本: major=$major, minor=$minor, patch=$patch"

    # 小版本號遞減
    if [[ $patch -gt 0 ]]; then
        local prev_patch=$((patch - 1))
        local prev_version="v${major}.${minor}.${prev_patch}"
        log "📍 前置版本（小版本遞減）: $prev_version"
        echo "$prev_version"
        return 0
    fi

    # 跨中版本：查找最新的 v0.$((minor-1)).x
    if [[ $minor -gt 0 ]]; then
        local prev_minor=$((minor - 1))
        local prev_pattern="v${major}.${prev_minor}"
        log "🔍 跨中版本查找: $prev_pattern.*"

        # 查找最新的工作日誌
        local work_log_dir="$CLAUDE_PROJECT_DIR/docs/work-logs"
        local latest_prev=$(find "$work_log_dir" -name "${prev_pattern}*.md" -type f -exec stat -f "%m %N" {} \; 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)

        if [[ -n "$latest_prev" ]]; then
            local prev_version=$(basename "$latest_prev" | grep -oE "v[0-9]+\.[0-9]+\.[0-9]+")
            log "📍 前置版本（跨中版本）: $prev_version"
            echo "$prev_version"
            return 0
        fi
    fi

    log "❌ 無法解析前置版本"
    return 1
}

# 查找工作日誌檔案
find_work_log() {
    local version="$1"
    local work_log_dir="$CLAUDE_PROJECT_DIR/docs/work-logs"

    # 查找對應版本的工作日誌
    local work_log=$(find "$work_log_dir" -name "${version}*.md" -type f | head -1)

    if [[ -n "$work_log" ]]; then
        log "📄 找到工作日誌: $(basename "$work_log")"
        echo "$work_log"
        return 0
    fi

    log "❌ 找不到工作日誌: $version"
    return 1
}

# 提取 Domain 模型定義
extract_domain_models() {
    local work_log="$1"

    log "🔍 提取 Domain 模型定義"

    # 查找 Phase 3 區段
    local phase3_start=$(grep -n "## Phase 3\|## 🛠 Phase 3\|Phase 3.*實作" "$work_log" | cut -d: -f1 | head -1)

    if [[ -z "$phase3_start" ]]; then
        log "⚠️  找不到 Phase 3 區段"
        return 1
    fi

    # 提取 Phase 3 內容
    local phase3_content=$(tail -n +${phase3_start} "$work_log" | sed -n '/## Phase 3/,/## Phase 4\|^## /p')

    # 提取 class 定義
    local models=$(echo "$phase3_content" | grep -E "^class [A-Z]" | sed 's/class //' | sed 's/ {.*//')

    if [[ -z "$models" ]]; then
        log "⚠️  找不到 Domain 模型定義"
        return 1
    fi

    log "✅ 找到 Domain 模型: $models"
    echo "$models"
    return 0
}

# 提取 Domain 模型欄位
extract_model_fields() {
    local work_log="$1"
    local model_name="$2"

    log "🔍 提取 $model_name 欄位定義"

    # 查找 class 定義區塊
    local class_content=$(sed -n "/class $model_name/,/^}/p" "$work_log")

    if [[ -z "$class_content" ]]; then
        log "⚠️  找不到 $model_name 定義"
        return 1
    fi

    # 提取欄位（final/const 類型 名稱）
    local fields=$(echo "$class_content" | grep -E "^\s*(final|const)?\s*\w+\s+\w+" | sed 's/^\s*//')

    if [[ -z "$fields" ]]; then
        log "⚠️  找不到欄位定義"
        return 1
    fi

    log "✅ 提取到 $(echo "$fields" | wc -l | tr -d ' ') 個欄位"
    echo "$fields"
    return 0
}

# 檢查 ViewModel 存在性
check_viewmodel_exists() {
    local model_name="$1"  # EnrichmentProgress

    # 轉換為 snake_case
    local snake_name=$(echo "$model_name" | sed 's/\([A-Z]\)/_\L\1/g' | sed 's/^_//')
    local viewmodel_file="${snake_name}_viewmodel.dart"
    local viewmodel_path="$CLAUDE_PROJECT_DIR/lib/presentation/viewmodels/$viewmodel_file"

    log "🔍 檢查 ViewModel: $viewmodel_file"

    if [[ -f "$viewmodel_path" ]]; then
        log "✅ ViewModel 存在: $viewmodel_path"
        echo "exists:$viewmodel_path"
        return 0
    else
        log "❌ ViewModel 不存在: $viewmodel_path"
        echo "missing:$viewmodel_path"
        return 1
    fi
}

# 生成依賴檢查報告
generate_report() {
    local current_version="$1"
    local prev_version="$2"
    local prev_log="$3"
    local domain_models="$4"
    local model_fields="$5"
    local viewmodel_status="$6"

    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    cat <<EOF

---
# 🔍 設計依賴檢查報告

**檢查時間**: $timestamp
**當前版本**: $current_version
**前置版本**: $prev_version
**前置版本工作日誌**: $(basename "$prev_log")

## Domain 模型定義

### $domain_models

$model_fields

## ViewModel 檢查

EOF

    if [[ "$viewmodel_status" == exists:* ]]; then
        local vm_path=$(echo "$viewmodel_status" | cut -d: -f2)
        echo "- ✅ ViewModel 存在: $vm_path"
    else
        local vm_path=$(echo "$viewmodel_status" | cut -d: -f2)
        echo "- ❌ ViewModel 不存在: $vm_path"
        echo "- ⚠️  依據 v0.12-A.2 規範，應建立 ViewModel"
    fi

    cat <<EOF

## 設計建議

1. ✅ Phase 1 設計必須基於上述實際 Domain 定義
2. ⚠️  避免假設 Domain 包含未實作的欄位
3. 💡 建議使用 ViewModel 適配層處理 UI 專用邏輯
4. 📚 參考：.claude/methodologies/mvvm-viewmodel-methodology.md

---
EOF
}

# 追加報告到工作日誌
append_report_to_log() {
    local current_log="$1"
    local report="$2"

    log "📝 追加報告到工作日誌"

    # 檢查是否已有報告
    if grep -q "🔍 設計依賴檢查報告" "$current_log" 2>/dev/null; then
        log "⚠️  報告已存在，跳過追加"
        return 0
    fi

    # 追加報告
    echo "$report" >> "$current_log"
    log "✅ 報告已追加到 $(basename "$current_log")"

    return 0
}

# 主執行流程
main() {
    local task_context="$1"

    # 檢測是否為 Phase 1 設計任務
    if ! is_phase1_design_task "$task_context"; then
        log "ℹ️  非 Phase 1 設計任務，跳過檢查"
        exit 0
    fi

    # 提取版本號
    local current_version=$(extract_version "$task_context")
    if [[ -z "$current_version" ]]; then
        log "⚠️  無法提取版本號，跳過檢查"
        exit 0
    fi

    # 解析前置版本
    local prev_version=$(get_previous_version "$current_version")
    if [[ -z "$prev_version" ]]; then
        log "❌ 無法解析前置版本"
        exit 1
    fi

    # 查找前置版本工作日誌
    local prev_log=$(find_work_log "$prev_version")
    if [[ -z "$prev_log" ]]; then
        log "❌ 找不到前置版本工作日誌"
        exit 1
    fi

    # 提取 Domain 模型
    local domain_models=$(extract_domain_models "$prev_log")
    if [[ -z "$domain_models" ]]; then
        log "⚠️  無法提取 Domain 模型"
        exit 0
    fi

    # 提取模型欄位（以第一個模型為例）
    local first_model=$(echo "$domain_models" | head -1)
    local model_fields=$(extract_model_fields "$prev_log" "$first_model")

    # 檢查 ViewModel
    local viewmodel_status=$(check_viewmodel_exists "$first_model")

    # 生成報告
    local report=$(generate_report "$current_version" "$prev_version" "$prev_log" "$first_model" "$model_fields" "$viewmodel_status")

    # 查找當前版本工作日誌
    local current_log=$(find_work_log "$current_version")
    if [[ -n "$current_log" ]]; then
        append_report_to_log "$current_log" "$report"
    else
        log "⚠️  找不到當前版本工作日誌，無法追加報告"
        echo "$report"  # 輸出到 stdout
    fi

    log "✅ Pre-Design Dependency Check 完成"
    exit 0
}

# 執行主流程
# 從環境變數或參數獲取任務上下文
TASK_CONTEXT="${1:-$USER_PROMPT}"
main "$TASK_CONTEXT"
