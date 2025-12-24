#!/bin/bash

# =============================================================================
# 下一步目標分析腳本 - check-next-objectives.sh
# =============================================================================
#
# 檢查中版本層級的 todolist.md 任務狀態
# 用於 smart-version-check 指令的第三階段檢查
#
# 評估重點：
# - todolist.md 中當前版本系列 (如 v0.7.x) 目標完成度
# - 下一步開發方向和優先級
# - 中版本目標是否已完成
# =============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TODOLIST_FILE="$PROJECT_ROOT/docs/todolist.md"
PUBSPEC_FILE="$PROJECT_ROOT/pubspec.yaml"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🎯 下一步目標分析開始...${NC}"

# 檢查必要文件
if [[ ! -f "$TODOLIST_FILE" ]]; then
    echo -e "${RED}❌ 錯誤：找不到 todolist.md 檔案${NC}"
    exit 1
fi

if [[ ! -f "$PUBSPEC_FILE" ]]; then
    echo -e "${RED}❌ 錯誤：找不到 pubspec.yaml 檔案${NC}"
    exit 1
fi

# 獲取當前版本
CURRENT_VERSION=$(grep '^version:' "$PUBSPEC_FILE" | sed 's/version: *//' | sed 's/+.*//' | tr -d '"' | tr -d "'")
echo -e "${BLUE}📋 當前版本：${NC} $CURRENT_VERSION"

# 從版本號提取版本系列 (例如 0.7.6 -> v0.7.x)
VERSION_SERIES=$(echo "$CURRENT_VERSION" | sed 's/\.[0-9]*$/\.x/' | sed 's/^/v/')
echo -e "${BLUE}🎯 版本系列：${NC} $VERSION_SERIES"

# 分析 todolist.md 中的版本系列狀態
echo -e "\n${BLUE}📊 版本系列目標分析：${NC}"

# 檢查當前版本系列的完成項目
VERSION_PREFIX=$(echo $CURRENT_VERSION | sed 's/\.[0-9]*$//')
COMPLETED_ITEMS=$(grep -c "✅.*v${VERSION_PREFIX}\.[0-9]:.*完成" "$TODOLIST_FILE" 2>/dev/null || echo "0")
TOTAL_ITEMS=$(grep -c "v${VERSION_PREFIX}\.[0-9]:" "$TODOLIST_FILE" 2>/dev/null || echo "0")

echo -e "${BLUE}✅ 已完成項目：${NC} $COMPLETED_ITEMS"
echo -e "${BLUE}📋 總項目數：${NC} $TOTAL_ITEMS"

# 檢查是否有未完成的項目
PENDING_ITEMS=$(grep -c "^- \[ \].*v${VERSION_PREFIX}\.[0-9]" "$TODOLIST_FILE" 2>/dev/null || echo "0")
echo -e "${BLUE}⏳ 待辦項目：${NC} $PENDING_ITEMS"

# 查找版本系列目標達成狀況
VERSION_SERIES_PATTERN="v${VERSION_PREFIX}"
echo -e "\n${BLUE}🔍 檢查 $VERSION_SERIES_PATTERN 系列狀態：${NC}"

# 檢查成功指標達成狀況
SUCCESS_INDICATORS=""
if grep -q "成功指標" "$TODOLIST_FILE"; then
    echo -e "${BLUE}📈 發現成功指標區塊${NC}"

    # 統計已完成的成功指標
    COMPLETED_INDICATORS=$(grep -A 10 "成功指標" "$TODOLIST_FILE" | grep -c "✅" 2>/dev/null || echo "0")
    TOTAL_INDICATORS=$(grep -A 10 "成功指標" "$TODOLIST_FILE" | grep -c "^- " 2>/dev/null || echo "0")

    echo -e "${GREEN}✅ 已達成指標：${NC} $COMPLETED_INDICATORS / $TOTAL_INDICATORS"

    if [[ $COMPLETED_INDICATORS -eq $TOTAL_INDICATORS && $TOTAL_INDICATORS -gt 0 ]]; then
        SUCCESS_INDICATORS="ALL_COMPLETED"
    elif [[ $COMPLETED_INDICATORS -gt 0 ]]; then
        SUCCESS_INDICATORS="PARTIALLY_COMPLETED"
    else
        SUCCESS_INDICATORS="NOT_COMPLETED"
    fi
fi

# 檢查里程碑達成狀況
MILESTONES_STATUS=""
if grep -q "里程碑檢查點" "$TODOLIST_FILE"; then
    echo -e "${BLUE}🏁 發現里程碑檢查點${NC}"

    COMPLETED_MILESTONES=$(grep -A 5 "里程碑檢查點" "$TODOLIST_FILE" | grep -c "✅" 2>/dev/null || echo "0")
    TOTAL_MILESTONES=$(grep -A 5 "里程碑檢查點" "$TODOLIST_FILE" | grep -c "^- " 2>/dev/null || echo "0")

    echo -e "${GREEN}✅ 已達成里程碑：${NC} $COMPLETED_MILESTONES / $TOTAL_MILESTONES"

    if [[ $COMPLETED_MILESTONES -eq $TOTAL_MILESTONES && $TOTAL_MILESTONES -gt 0 ]]; then
        MILESTONES_STATUS="ALL_COMPLETED"
    elif [[ $COMPLETED_MILESTONES -gt 0 ]]; then
        MILESTONES_STATUS="PARTIALLY_COMPLETED"
    else
        MILESTONES_STATUS="NOT_COMPLETED"
    fi
fi

# 查找下一個開發方向
echo -e "\n${BLUE}🔮 下一步開發方向分析：${NC}"

# 查找低優先級項目或下一個版本系列
NEXT_VERSION_SERIES=""
if grep -q "低優先級項目" "$TODOLIST_FILE"; then
    NEXT_VERSION_SERIES=$(grep -A 3 "低優先級項目" "$TODOLIST_FILE" | grep -o "v[0-9]\+\.[0-9]\+\.[0-9]\+" | head -1)
    if [[ -n "$NEXT_VERSION_SERIES" ]]; then
        echo -e "${BLUE}📋 發現下一個版本系列：${NC} $NEXT_VERSION_SERIES"
    fi
fi

# 總體評估
echo -e "\n${BLUE}📋 版本系列完成度評估：${NC}"

SERIES_STATUS="UNKNOWN"

# 判斷版本系列完成狀態
if [[ "$SUCCESS_INDICATORS" == "ALL_COMPLETED" && "$MILESTONES_STATUS" == "ALL_COMPLETED" && $PENDING_ITEMS -eq 0 ]]; then
    SERIES_STATUS="FULLY_COMPLETED"
    echo -e "${GREEN}✅ 版本系列狀態：完全完成${NC}"
    echo -e "   • 所有成功指標達成"
    echo -e "   • 所有里程碑達成"
    echo -e "   • 無待辦項目"
elif [[ "$SUCCESS_INDICATORS" == "ALL_COMPLETED" || "$MILESTONES_STATUS" == "ALL_COMPLETED" ]]; then
    SERIES_STATUS="MOSTLY_COMPLETED"
    echo -e "${YELLOW}⚠️  版本系列狀態：基本完成${NC}"
    echo -e "   • 主要目標達成"
    echo -e "   • 可能有少量收尾工作"
elif [[ "$SUCCESS_INDICATORS" == "PARTIALLY_COMPLETED" || "$MILESTONES_STATUS" == "PARTIALLY_COMPLETED" ]]; then
    SERIES_STATUS="IN_PROGRESS"
    echo -e "${YELLOW}🔄 版本系列狀態：進行中${NC}"
    echo -e "   • 部分目標達成"
    echo -e "   • 仍有重要工作待完成"
else
    SERIES_STATUS="NOT_COMPLETED"
    echo -e "${RED}❌ 版本系列狀態：未完成${NC}"
    echo -e "   • 主要目標未達成"
fi

# 下一步建議
echo -e "\n${BLUE}💡 下一步建議：${NC}"

case "$SERIES_STATUS" in
    "FULLY_COMPLETED")
        echo -e "${GREEN}建議：準備推進到下一個中版本系列${NC}"
        if [[ -n "$NEXT_VERSION_SERIES" ]]; then
            echo -e "   目標：$NEXT_VERSION_SERIES"
        fi
        exit 0
        ;;
    "MOSTLY_COMPLETED")
        echo -e "${YELLOW}建議：完成收尾工作後推進中版本${NC}"
        exit 1
        ;;
    "IN_PROGRESS")
        echo -e "${YELLOW}建議：繼續當前版本系列開發${NC}"

        # 檢查todolist.md中的未完成任務
        PENDING_TODOS=$(grep -c "\[ \]" "$PROJECT_ROOT/docs/todolist.md" 2>/dev/null || echo "0")

        # 獲取部分具體的待辦任務
        SAMPLE_TODOS=$(grep "\[ \]" "$PROJECT_ROOT/docs/todolist.md" | head -3 | sed 's/^[ ]*- \[ \] /• /')

        # 輸出停止原因到 stderr (Claude Code 會顯示)
        cat >&2 <<EOF

🚫 版本推進暫停 - 當前版本系列仍在進行中

📋 停止原因：
• 版本系列 $VERSION_SERIES_PATTERN 的目標尚未完全達成
• 成功指標或里程碑仍有待完成項目
• todolist.md 中有 $PENDING_TODOS 個待辦任務

📝 部分待完成任務範例：
$SAMPLE_TODOS

📝 需要採取的行動：
1. 繼續完成當前版本系列的開發工作
2. 達成 todolist.md 中標記的成功指標
3. 完成所有里程碑檢查點
4. 工作完成後，系統會自動建議版本推進

💡 快速檢查：
• 執行 'dart analyze' 確認程式碼品質
• 執行 'dart test' 確認測試通過
• 檢查 todolist.md 中待辦事項

🎯 建議的 TodoWrite 任務：
請執行以下 TodoWrite 繼續版本系列開發：

TodoWrite([
  {"content": "完成當前版本系列的核心開發工作", "status": "pending", "activeForm": "完成當前版本系列的核心開發工作"},
  {"content": "達成 todolist.md 中的成功指標", "status": "pending", "activeForm": "達成 todolist.md 中的成功指標"},
  {"content": "完成所有里程碑檢查點", "status": "pending", "activeForm": "完成所有里程碑檢查點"},
  {"content": "執行程式碼品質和測試檢查", "status": "pending", "activeForm": "執行程式碼品質和測試檢查"}
])

🔄 完成後會自動建議推進到下一個版本
EOF

        exit 2
        ;;
    *)
        echo -e "${RED}建議：專注完成當前版本系列目標${NC}"

        # 檢查todolist.md中的未完成任務
        PENDING_TODOS=$(grep -c "\[ \]" "$PROJECT_ROOT/docs/todolist.md" 2>/dev/null || echo "0")

        # 獲取高優先級的待辦任務
        HIGH_PRIORITY_TODOS=$(grep -A 10 "HIGH.*優先級" "$PROJECT_ROOT/docs/todolist.md" | grep "\[ \]" | head -3 | sed 's/^[ ]*- \[ \] /• /')

        # 輸出停止原因到 stderr (Claude Code 會顯示)
        cat >&2 <<EOF

🚫 版本推進暫停 - 當前版本系列未完成

📋 停止原因：
• 版本系列 $VERSION_SERIES_PATTERN 的主要目標未達成
• 缺乏足夠的完成指標和里程碑
• todolist.md 中有 $PENDING_TODOS 個待辦任務

🔥 高優先級待完成任務：
$HIGH_PRIORITY_TODOS

📝 需要採取的行動：
1. 檢查並完成 todolist.md 中的核心任務
2. 確保所有成功指標都有進展
3. 完成關鍵里程碑檢查點
4. 提升整體完成度後再推進版本

💡 建議步驟：
• 專注於最重要的核心功能開發
• 確認測試通過率達到 100%
• 更新工作日誌記錄進展

🎯 建議的 TodoWrite 任務：
請執行以下 TodoWrite 專注核心目標：

TodoWrite([
  {"content": "完成 todolist.md 中的高優先級任務", "status": "pending", "activeForm": "完成 todolist.md 中的高優先級任務"},
  {"content": "確保所有成功指標都有進展", "status": "pending", "activeForm": "確保所有成功指標都有進展"},
  {"content": "完成關鍵里程碑檢查點", "status": "pending", "activeForm": "完成關鍵里程碑檢查點"},
  {"content": "提升整體版本系列完成度", "status": "pending", "activeForm": "提升整體版本系列完成度"}
])

🔄 完成重要任務後會自動建議版本推進
EOF

        exit 3
        ;;
esac