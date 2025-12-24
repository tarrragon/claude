#!/bin/bash
# PM 狀態檢查工具 - 為 rosemary-project-manager 提供當前專案狀態概覽
# 檔案: scripts/pm-status-check.sh

set -e

# === 配置參數 ===
CLAUDE_DIR=".claude"
PM_STATUS_FILE="$CLAUDE_DIR/pm-status.json"
WORK_LOGS_DIR="docs/work-logs"
TODO_FILE="docs/todolist.md"

# === 顏色輸出 ===
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# === 狀態檢查函數 ===
check_trigger_status() {
    echo -e "${BLUE}📊 PM 觸發狀態檢查${NC}"
    echo "=========================="

    if [[ -f "$PM_STATUS_FILE" ]]; then
        local trigger_time=$(cat "$PM_STATUS_FILE" | grep '"timestamp"' | sed 's/.*": "\(.*\)".*/\1/')
        local trigger_reason=$(cat "$PM_STATUS_FILE" | grep '"trigger_reason"' | sed 's/.*": "\(.*\)".*/\1/')

        echo -e "${RED}🚨 PM 介入已觸發${NC}"
        echo "觸發時間: $trigger_time"
        echo "觸發原因: $trigger_reason"
        echo ""
    else
        echo -e "${GREEN}✅ 無 PM 觸發狀態${NC}"
        echo ""
    fi
}

check_current_work_status() {
    echo -e "${BLUE}📝 當前工作狀態${NC}"
    echo "=========================="

    # 檢查最新工作日誌
    if [[ -d "$WORK_LOGS_DIR" ]]; then
        local latest_log=$(ls -t "$WORK_LOGS_DIR"/v*.md 2>/dev/null | head -1)
        if [[ -f "$latest_log" ]]; then
            echo "最新工作日誌: $(basename "$latest_log")"

            # 檢查工作完成狀態
            if grep -q "✅.*完成" "$latest_log" 2>/dev/null; then
                echo -e "${GREEN}工作狀態: ✅ 已完成${NC}"
            elif grep -q "🔄.*進行中" "$latest_log" 2>/dev/null; then
                echo -e "${YELLOW}工作狀態: 🔄 進行中${NC}"
            else
                echo -e "${YELLOW}工作狀態: ⚠️ 狀態不明${NC}"
            fi

            # 檢查 TDD 階段
            local tdd_phase=""
            if grep -q "Phase 1.*完成\|功能設計.*完成" "$latest_log" 2>/dev/null; then
                tdd_phase="Phase 1 完成"
            elif grep -q "Phase 2.*完成\|測試設計.*完成" "$latest_log" 2>/dev/null; then
                tdd_phase="Phase 2 完成"
            elif grep -q "Phase 3.*完成\|實作.*完成" "$latest_log" 2>/dev/null; then
                tdd_phase="Phase 3 完成"
            elif grep -q "Phase 4.*完成\|重構.*完成" "$latest_log" 2>/dev/null; then
                tdd_phase="Phase 4 完成"
            else
                tdd_phase="階段不明"
            fi
            echo "TDD 階段: $tdd_phase"

            # 檢查最後更新時間
            local last_modified=$(stat -f "%m" "$latest_log" 2>/dev/null || stat -c "%Y" "$latest_log" 2>/dev/null)
            local current_time=$(date +%s)
            local time_diff=$((current_time - last_modified))
            local days_ago=$((time_diff / 86400))

            if [[ $days_ago -gt 2 ]]; then
                echo -e "${RED}最後更新: $days_ago 天前 (可能停滯)${NC}"
            elif [[ $days_ago -gt 0 ]]; then
                echo -e "${YELLOW}最後更新: $days_ago 天前${NC}"
            else
                echo -e "${GREEN}最後更新: 今天${NC}"
            fi
        else
            echo -e "${RED}⚠️ 找不到工作日誌${NC}"
        fi
    else
        echo -e "${RED}⚠️ 工作日誌目錄不存在${NC}"
    fi
    echo ""
}

check_todo_priority() {
    echo -e "${BLUE}📋 TodoList 優先級狀態${NC}"
    echo "=========================="

    if [[ -f "$TODO_FILE" ]]; then
        # 適應實際 todolist 格式 - 統計不同狀態的項目
        local completed_count=$(grep -c "✅" "$TODO_FILE" 2>/dev/null || echo "0")
        local in_progress_count=$(grep -c "🔄" "$TODO_FILE" 2>/dev/null || echo "0")
        local pending_count=$(grep -c "⭕\|📋\|- \[" "$TODO_FILE" 2>/dev/null || echo "0")
        local total_sections=$(grep -c "^##\|^###" "$TODO_FILE" 2>/dev/null || echo "0")

        echo "已完成項目: $completed_count"
        echo "進行中項目: $in_progress_count"
        echo "待處理項目: $pending_count"
        echo "總章節數: $total_sections"

        # 檢查是否有緊急或重要的關鍵字
        local urgent_items=$(grep -c "緊急\|Critical\|🔥\|⚠️" "$TODO_FILE" 2>/dev/null || echo "0")
        if [[ $urgent_items -gt 0 ]]; then
            echo -e "${RED}緊急/重要項目: $urgent_items${NC}"
        fi

        # 檢查是否有技術債務相關項目
        local debt_items=$(grep -c "技術債務\|重構\|修復\|ESLint" "$TODO_FILE" 2>/dev/null || echo "0")
        if [[ $debt_items -gt 0 ]]; then
            echo -e "${YELLOW}技術債務相關: $debt_items${NC}"
        fi

        # 警示狀況
        if [[ $urgent_items -gt 0 && $in_progress_count -eq 0 ]]; then
            echo -e "${RED}⚠️ 有緊急項目但無進行中工作${NC}"
        fi
    else
        echo -e "${RED}⚠️ TodoList 檔案不存在${NC}"
    fi
    echo ""
}

check_technical_debt() {
    echo -e "${BLUE}🏗️ 技術債務狀態${NC}"
    echo "=========================="

    # 檢查 TODO/FIXME 標記
    local todo_files=$(find src/ -name "*.js" -exec grep -l "//todo:\|//fixme:\|TODO:\|FIXME:" {} \; 2>/dev/null | wc -l)
    echo "包含技術債務標記的檔案: $todo_files"

    if [[ $todo_files -gt 15 ]]; then
        echo -e "${RED}⚠️ 技術債務過多，建議制定清理計畫${NC}"
    elif [[ $todo_files -gt 10 ]]; then
        echo -e "${YELLOW}⚠️ 技術債務累積中，需要關注${NC}"
    else
        echo -e "${GREEN}✅ 技術債務在可控範圍內${NC}"
    fi

    # 檢查 ESLint 錯誤
    if command -v npm >/dev/null 2>&1; then
        local eslint_output=$(npm run lint 2>/dev/null | tail -10)
        local eslint_errors=$(echo "$eslint_output" | grep -c "error" 2>/dev/null || echo "0")

        echo "ESLint 錯誤數量: $eslint_errors"

        if [[ $eslint_errors -gt 50 ]]; then
            echo -e "${RED}⚠️ ESLint 錯誤過多，需要立即處理${NC}"
        elif [[ $eslint_errors -gt 20 ]]; then
            echo -e "${YELLOW}⚠️ ESLint 錯誤較多，建議優先修復${NC}"
        elif [[ $eslint_errors -eq 0 ]]; then
            echo -e "${GREEN}✅ 無 ESLint 錯誤${NC}"
        else
            echo -e "${GREEN}✅ ESLint 錯誤在可接受範圍內${NC}"
        fi
    fi
    echo ""
}

check_version_progression() {
    echo -e "${BLUE}🏷️ 版本推進狀態${NC}"
    echo "=========================="

    if [[ -f "pubspec.yaml" ]]; then
        local current_version=$(grep '^version:' pubspec.yaml | sed 's/version: *//')
        echo "當前版本: $current_version"

        # 檢查版本推進建議
        if [[ "$current_version" =~ ^0\.9\. ]]; then
            echo -e "${YELLOW}📈 接近 1.0.0 里程碑，建議檢視發布準備度${NC}"
        elif [[ "$current_version" =~ \.[9]\. ]]; then
            echo -e "${YELLOW}📈 接近中版本里程碑，建議規劃下一版本${NC}"
        else
            echo -e "${GREEN}✅ 版本推進正常${NC}"
        fi
    else
        echo -e "${RED}⚠️ pubspec.yaml 不存在${NC}"
    fi
    echo ""
}

generate_pm_recommendations() {
    echo -e "${BLUE}💡 PM 行動建議${NC}"
    echo "=========================="

    local recommendations=()

    # 基於檢查結果生成建議
    if [[ -f "$PM_STATUS_FILE" ]]; then
        recommendations+=("🔍 檢視觸發原因並制定應對策略")
    fi

    # 檢查工作停滯
    if [[ -d "$WORK_LOGS_DIR" ]]; then
        local latest_log=$(ls -t "$WORK_LOGS_DIR"/v*.md 2>/dev/null | head -1)
        if [[ -f "$latest_log" ]]; then
            local last_modified=$(stat -f "%m" "$latest_log" 2>/dev/null || stat -c "%Y" "$latest_log" 2>/dev/null)
            local current_time=$(date +%s)
            local time_diff=$((current_time - last_modified))

            if [[ $time_diff -gt 172800 ]]; then  # 2 天
                recommendations+=("⏰ 檢查工作停滯原因，重新啟動開發流程")
            fi
        fi
    fi

    # 檢查技術債務
    local todo_files=$(find src/ -name "*.js" -exec grep -l "//todo:\|//fixme:\|TODO:\|FIXME:" {} \; 2>/dev/null | wc -l)
    if [[ $todo_files -gt 15 ]]; then
        recommendations+=("🏗️ 制定技術債務清理計畫")
    fi

    # 檢查緊急任務
    if [[ -f "$TODO_FILE" ]]; then
        local urgent_count=$(grep -c "緊急\|Critical\|🔥\|⚠️" "$TODO_FILE" 2>/dev/null || echo "0")
        if [[ $urgent_count -gt 0 ]]; then
            recommendations+=("🎯 重新評估緊急任務優先級和資源分配")
        fi
    fi

    # 輸出建議
    if [[ ${#recommendations[@]} -gt 0 ]]; then
        for recommendation in "${recommendations[@]}"; do
            echo "$recommendation"
        done
    else
        echo -e "${GREEN}✅ 專案狀態良好，無需特別介入${NC}"
    fi

    echo ""
    echo -e "${BLUE}📞 建議啟動代理人：${NC}"
    echo "Task(subagent_type: 'rosemary-project-manager', description: 'PM狀態檢視', prompt: '檢視當前專案狀態並調整 todolist 優先級')"
}

# === 主函數 ===
main() {
    echo -e "${GREEN}🚀 PM 狀態檢查工具${NC}"
    echo "=============================="
    echo ""

    check_trigger_status
    check_current_work_status
    check_todo_priority
    check_technical_debt
    check_version_progression
    generate_pm_recommendations

    # 清除觸發狀態（已檢視）
    if [[ -f "$PM_STATUS_FILE" ]]; then
        rm -f "$PM_STATUS_FILE"
        rm -f "$CLAUDE_DIR/PM_INTERVENTION_REQUIRED"
        echo -e "${GREEN}✅ PM 觸發狀態已清除${NC}"
    fi
}

# 執行主函數
main "$@"