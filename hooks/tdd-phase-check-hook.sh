#!/bin/bash

# tdd-phase-check-hook.sh
# TDD Phase 完整性檢查 Hook
# 確保 TDD 四階段完整執行，不可跳過或簡化

# 載入通用函數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# 設定專案環境
if ! setup_project_environment; then
    echo "錯誤: 無法設定專案環境" >&2
    exit 1
fi

# 日誌檔案
LOG_FILE="$CLAUDE_LOGS_DIR/tdd-phase-check-$(date +%Y%m%d_%H%M%S).log"

# 日誌函數
log() {
    log_with_timestamp "$LOG_FILE" "$1"
}

log "🚨 TDD Phase 完整性檢查 Hook: 開始執行"

# 取得最新的工作日誌檔案
get_latest_work_log() {
    local work_log_dir="$CLAUDE_PROJECT_DIR/docs/work-logs"

    if [[ ! -d "$work_log_dir" ]]; then
        echo ""
        return 1
    fi

    # 找出最新修改的 v*.md 檔案
    local latest_log=$(find "$work_log_dir" -name "v*.md" -type f -exec stat -f "%m %N" {} \; 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-)

    echo "$latest_log"
}

# 檢查工作日誌是否包含所有四個 Phase
check_tdd_phases() {
    local work_log="$1"

    if [[ -z "$work_log" ]] || [[ ! -f "$work_log" ]]; then
        log "⚠️  找不到工作日誌檔案"
        return 0  # 不阻止執行，只警告
    fi

    log "📋 檢查工作日誌: $(basename "$work_log")"

    # 檢查是否有 Phase 1-4 的標記
    local phase1=$(grep -c "Phase 1\|🎨.*Phase 1\|Phase 1.*功能設計" "$work_log" 2>/dev/null || echo "0")
    local phase2=$(grep -c "Phase 2\|🧪.*Phase 2\|Phase 2.*測試" "$work_log" 2>/dev/null || echo "0")
    local phase3=$(grep -c "Phase 3\|💻.*Phase 3\|Phase 3.*實作" "$work_log" 2>/dev/null || echo "0")
    local phase4=$(grep -c "Phase 4\|🏗️.*Phase 4\|Phase 4.*重構" "$work_log" 2>/dev/null || echo "0")

    log "📊 Phase 狀態統計:"
    log "   Phase 1 (功能設計): $phase1 次提及"
    log "   Phase 2 (測試驗證): $phase2 次提及"
    log "   Phase 3 (實作執行): $phase3 次提及"
    log "   Phase 4 (重構優化): $phase4 次提及"

    # 檢查是否有 Phase 缺失
    local missing_phases=0

    if [[ $phase1 -gt 0 ]] && [[ $phase2 -gt 0 ]] && [[ $phase3 -gt 0 ]]; then
        # Phase 1-3 都存在，檢查 Phase 4
        if [[ $phase4 -eq 0 ]]; then
            log "⚠️  發現 Phase 1-3 已執行，但缺少 Phase 4"
            log "🚨 違反 TDD 四階段完整執行鐵律"
            log "✅ 正確做法: 分派 cinnamon-refactor-owl 執行 Phase 4 評估"
            missing_phases=1
        else
            log "✅ TDD 四階段都有記錄"
        fi
    else
        log "ℹ️  TDD 流程尚未完成或正在進行中"
    fi

    return $missing_phases
}

# 檢測逃避語言
check_avoidance_language() {
    local work_log="$1"

    if [[ -z "$work_log" ]] || [[ ! -f "$work_log" ]]; then
        return 0
    fi

    log "🔍 檢測 Phase 4 逃避語言"

    # 定義逃避語言模式
    local avoidance_patterns=(
        "跳過.*Phase 4"
        "Phase 4.*跳過"
        "輕量.*檢查"
        "簡化.*重構"
        "Phase 4.*可選"
        "看起來.*不用.*重構"
        "品質.*好.*跳過"
        "不需要.*Phase 4"
    )

    local found_avoidance=0

    for pattern in "${avoidance_patterns[@]}"; do
        if grep -qE "$pattern" "$work_log" 2>/dev/null; then
            log "🚨 檢測到逃避語言: 符合模式 \"$pattern\""
            found_avoidance=1
        fi
    done

    if [[ $found_avoidance -eq 0 ]]; then
        log "✅ 未檢測到 Phase 4 逃避語言"
    else
        log "⚠️  發現 Phase 4 逃避語言"
        log "📋 提醒: TDD 四階段是強制性的，不可基於任何理由跳過"
    fi

    return $found_avoidance
}

# 檢查 Phase 3 完成後是否建議跳過 Phase 4
check_phase3_to_phase4_transition() {
    local work_log="$1"

    if [[ -z "$work_log" ]] || [[ ! -f "$work_log" ]]; then
        return 0
    fi

    log "🔍 檢查 Phase 3 → Phase 4 轉換"

    # 檢查是否有 Phase 3 完成的標記
    if grep -qE "Phase 3.*完成|Phase 3.*✅|實作執行.*完成" "$work_log" 2>/dev/null; then
        log "✓ 檢測到 Phase 3 完成標記"

        # 檢查是否有建議跳過 Phase 4 的語言
        if grep -qE "建議.*跳過|選項.*跳過.*Phase 4|可以.*不用.*Phase 4" "$work_log" 2>/dev/null; then
            log "🚨 發現 Phase 3 完成後建議跳過 Phase 4"
            log "❌ 這違反了 TDD 四階段強制執行鐵律"
            log "✅ 正確做法: 立即分派 cinnamon-refactor-owl 執行 Phase 4"
            return 1
        else
            log "✅ Phase 3 → Phase 4 轉換正常"
        fi
    fi

    return 0
}

# 主執行流程
main() {
    # 取得最新工作日誌
    local latest_log=$(get_latest_work_log)

    if [[ -z "$latest_log" ]]; then
        log "ℹ️  未找到工作日誌，跳過檢查"
        log "✅ TDD Phase 檢查完成"
        exit 0
    fi

    # 執行檢查
    check_tdd_phases "$latest_log"
    local phases_result=$?

    check_avoidance_language "$latest_log"
    local avoidance_result=$?

    check_phase3_to_phase4_transition "$latest_log"
    local transition_result=$?

    # 總結檢查結果
    if [[ $phases_result -ne 0 ]] || [[ $avoidance_result -ne 0 ]] || [[ $transition_result -ne 0 ]]; then
        log "⚠️  TDD Phase 檢查發現問題"
        log "📋 請確保遵循 TDD 四階段完整執行鐵律"
    else
        log "✅ TDD Phase 檢查通過"
    fi

    log "✅ TDD Phase 完整性檢查 Hook: 執行完成"

    # 不阻止執行，只提供警告
    exit 0
}

# 執行主流程
main
