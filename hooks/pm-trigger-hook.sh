#!/bin/bash
# PM 自動觸發 Hook - 敏捷開發進度監控與介入機制
# 檔案: scripts/pm-trigger-hook.sh

set -e

# === 配置參數 ===
# 使用官方環境變數（如果存在）
if [ -n "$CLAUDE_PROJECT_DIR" ]; then
    PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
else
    # Fallback 到手動定位
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

CLAUDE_DIR="$PROJECT_ROOT/.claude"
HOOK_LOGS_DIR="$CLAUDE_DIR/hook-logs"
PM_TRIGGER_LOG="$HOOK_LOGS_DIR/pm-trigger-$(date +%Y%m%d_%H%M%S).log"
PM_STATUS_FILE="$CLAUDE_DIR/pm-status.json"
WORK_LOGS_DIR="$PROJECT_ROOT/docs/work-logs"
TODO_FILE="$PROJECT_ROOT/docs/todolist.md"
REPORT_TRACKER="$HOOK_LOGS_DIR/agent-reports-tracker.md"

# 建立必要目錄
mkdir -p "$HOOK_LOGS_DIR"

# === 日誌函數 ===
log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ℹ️  $1" | tee -a "$PM_TRIGGER_LOG"
}

log_warning() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  $1" | tee -a "$PM_TRIGGER_LOG"
}

log_trigger() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚨 PM TRIGGER: $1" | tee -a "$PM_TRIGGER_LOG"
}

# === PM 觸發決策引擎 ===
check_phase_transition() {
    log_info "檢查 TDD 階段轉換觸發條件"

    # 檢查最新工作日誌的完成狀態標記
    if [[ -d "$WORK_LOGS_DIR" ]]; then
        latest_log=$(ls -t "$WORK_LOGS_DIR"/v*.md 2>/dev/null | head -1)
        if [[ -f "$latest_log" ]]; then
            # 檢查階段完成標記
            if grep -q "✅.*Phase [1-4].*完成" "$latest_log" 2>/dev/null; then
                log_trigger "TDD 階段完成 - 需要 PM 檢視階段轉換"
                return 0
            fi

            # 檢查工作完成標記
            if grep -q "🏁.*工作完成" "$latest_log" 2>/dev/null; then
                log_trigger "工作項目完成 - 需要 PM 規劃下一步"
                return 0
            fi
        fi
    fi
    return 1
}

check_progress_stagnation() {
    log_info "檢查進度停滯情況"

    # 檢查最後工作日誌更新時間 (超過 2 天)
    if [[ -d "$WORK_LOGS_DIR" ]]; then
        latest_log=$(ls -t "$WORK_LOGS_DIR"/v*.md 2>/dev/null | head -1)
        if [[ -f "$latest_log" ]]; then
            last_modified=$(stat -f "%m" "$latest_log" 2>/dev/null || stat -c "%Y" "$latest_log" 2>/dev/null)
            current_time=$(date +%s)
            time_diff=$((current_time - last_modified))

            # 2 天 = 172800 秒
            if [[ $time_diff -gt 172800 ]]; then
                log_trigger "進度停滯超過 2 天 - 需要 PM 介入檢查阻礙"
                return 0
            fi
        fi
    fi

    # 檢查 todolist 中高優先級任務停滯
    if [[ -f "$TODO_FILE" ]]; then
        if grep -q "🔴.*Critical" "$TODO_FILE" && ! grep -q "🔄.*進行中" "$TODO_FILE"; then
            log_trigger "Critical 任務無進展 - 需要 PM 重新評估優先級"
            return 0
        fi
    fi

    return 1
}

check_complexity_overflow() {
    log_info "檢查任務複雜度超標"

    # 檢查技術債務累積 (超過 15 個 TODO/FIXME)
    # 注意: 此專案是 Flutter/Dart 專案，檢查 lib/ 目錄中的 .dart 檔案
    todo_count=$(find "$PROJECT_ROOT/lib" -name "*.dart" -exec grep -l "//todo:\|//fixme:\|TODO:\|FIXME:" {} \; 2>/dev/null | wc -l || echo "0")
    if [[ $todo_count -gt 15 ]]; then
        log_trigger "技術債務累積過多 ($todo_count 個) - 需要 PM 重新規劃債務清理策略"
        return 0
    fi

    # 檢查 Dart analyze 錯誤數量 (超過 50 個)
    if command -v dart >/dev/null 2>&1; then
        analyze_errors=$(cd "$PROJECT_ROOT" && dart analyze 2>/dev/null | grep -c "error •" || echo "0")
        if [[ $analyze_errors -gt 50 ]]; then
            log_trigger "Dart analyze 錯誤過多 ($analyze_errors 個) - 需要 PM 規劃品質修復策略"
            return 0
        fi
    fi

    return 1
}

check_agent_escalation() {
    log_info "檢查 Agent 升級請求"

    # 檢查工作日誌中的升級關鍵字
    if [[ -d "$WORK_LOGS_DIR" ]]; then
        latest_log=$(ls -t "$WORK_LOGS_DIR"/v*.md 2>/dev/null | head -1)
        if [[ -f "$latest_log" ]]; then
            if grep -i -q "升級\|escalat\|無法解決\|超出能力\|重新分配" "$latest_log"; then
                log_trigger "Agent 請求升級 - 需要 PM 進行任務重新分解"
                return 0
            fi
        fi
    fi

    return 1
}

check_milestone_approach() {
    log_info "檢查里程碑接近情況"

    # 檢查版本號接近重要節點
    if [[ -f "pubspec.yaml" ]]; then
        current_version=$(grep '^version:' pubspec.yaml | sed 's/version: *//')

        # 檢查是否接近 1.0.0 (如當前為 0.9.x)
        if [[ "$current_version" =~ ^0\.9\. ]]; then
            log_trigger "接近 1.0.0 里程碑 - 需要 PM 檢視發布準備度"
            return 0
        fi

        # 檢查是否接近中版本節點 (如 x.9.y)
        if [[ "$current_version" =~ \.[9]\. ]]; then
            log_trigger "接近中版本里程碑 - 需要 PM 規劃下一版本目標"
            return 0
        fi
    fi

    return 1
}

# === 代理人回報追蹤 ===
track_agent_reports() {
    log_info "📊 追蹤代理人任務回報"

    # 檢查最近的 agent 任務執行記錄
    RECENT_AGENT_LOGS=$(find "$HOOK_LOGS_DIR" -name "agent-*" -mtime -1 2>/dev/null || true)

    if [ -z "$RECENT_AGENT_LOGS" ]; then
        log_info "ℹ️  過去 24 小時無 agent 任務執行記錄"
        return 0
    fi

    # 統計各類 agent 執行次數
    AGENT_COUNT=$(echo "$RECENT_AGENT_LOGS" | wc -l | tr -d ' ')
    log_info "📈 過去 24 小時內執行了 $AGENT_COUNT 個 agent 任務"

    # 記錄到 agent-reports-tracker.md
    if [ ! -f "$REPORT_TRACKER" ]; then
        echo "# Agent 回報追蹤記錄" > "$REPORT_TRACKER"
        echo "" >> "$REPORT_TRACKER"
    fi

    echo "## $(date '+%Y-%m-%d %H:%M:%S') - Agent 執行統計" >> "$REPORT_TRACKER"
    echo "- 執行次數: $AGENT_COUNT" >> "$REPORT_TRACKER"
    echo "- 詳細記錄: .claude/hook-logs/agent-*" >> "$REPORT_TRACKER"
    echo "" >> "$REPORT_TRACKER"

    log_info "✅ Agent 回報追蹤已更新"
}

# === PM 狀態記錄 ===
record_pm_status() {
    local trigger_reason="$1"
    local current_context="$2"

    cat > "$PM_STATUS_FILE" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "trigger_reason": "$trigger_reason",
  "current_context": "$current_context",
  "triggered": true,
  "pm_intervention_required": true,
  "work_log_path": "$(ls -t "$WORK_LOGS_DIR"/v*.md 2>/dev/null | head -1)",
  "todo_file_path": "$TODO_FILE"
}
EOF

    log_info "PM 狀態已記錄到 $PM_STATUS_FILE"
}

# === 主要觸發邏輯 ===
main() {
    log_info "🚀 PM 觸發檢查開始"

    # 執行代理人回報追蹤
    track_agent_reports

    local triggered=false
    local trigger_reasons=()

    # 檢查各種觸發條件
    if check_phase_transition; then
        trigger_reasons+=("TDD階段轉換")
        triggered=true
    fi

    if check_progress_stagnation; then
        trigger_reasons+=("進度停滯")
        triggered=true
    fi

    if check_complexity_overflow; then
        trigger_reasons+=("複雜度超標")
        triggered=true
    fi

    if check_agent_escalation; then
        trigger_reasons+=("Agent升級請求")
        triggered=true
    fi

    if check_milestone_approach; then
        trigger_reasons+=("里程碑接近")
        triggered=true
    fi

    # 如果觸發條件滿足，記錄狀態並準備 PM 介入
    if [[ "$triggered" == true ]]; then
        local all_reasons=$(IFS=","; echo "${trigger_reasons[*]}")
        record_pm_status "$all_reasons" "自動觸發檢查"

        log_trigger "滿足觸發條件: $all_reasons"
        log_trigger "建議啟動 rosemary-project-manager 進行：
1. 檢視當前工作進度和阻礙
2. 評估 todolist 優先級調整需求
3. 規劃下一階段工作策略
4. 處理技術債務和品質問題"

        # 建立 PM 提醒檔案
        echo "🚨 PM 介入提醒: $all_reasons" > "$CLAUDE_DIR/PM_INTERVENTION_REQUIRED"

        echo "✅ PM 觸發條件滿足，已設置介入提醒"
    else
        log_info "✅ 無 PM 觸發條件，開發進度正常"
        # 清除可能存在的舊提醒
        rm -f "$CLAUDE_DIR/PM_INTERVENTION_REQUIRED"
    fi

    log_info "🏁 PM 觸發檢查完成"
}

# 執行主函數
main "$@"