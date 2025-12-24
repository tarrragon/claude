#!/bin/bash

# =============================================================================
# 工作日誌狀態檢查腳本 - check-work-log.sh
# =============================================================================
#
# 檢查當前小版本工作完成狀態
# 用於 smart-version-check 指令的第二階段檢查
#
# 分析內容：
# - 當前工作日誌是否標記為完成 (✅)
# - 工作項目完成度和品質狀態
# - 是否有未完成的技術債務
# =============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_LOGS_DIR="$PROJECT_ROOT/docs/work-logs"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📝 工作日誌狀態檢查開始...${NC}"

# 檢查工作日誌目錄
if [[ ! -d "$WORK_LOGS_DIR" ]]; then
    echo -e "${RED}❌ 錯誤：找不到工作日誌目錄 docs/work-logs/${NC}"
    exit 1
fi

# 查找最新的工作日誌檔案 (按檔案修改時間排序)
LATEST_WORK_LOG=$(find "$WORK_LOGS_DIR" -name "v*.md" -type f -exec ls -t {} + | head -1)

if [[ -z "$LATEST_WORK_LOG" ]]; then
    echo -e "${RED}❌ 錯誤：工作日誌目錄中找不到任何版本工作日誌${NC}"
    exit 1
fi

WORK_LOG_BASENAME=$(basename "$LATEST_WORK_LOG")
echo -e "${BLUE}📄 最新工作日誌：${NC} $WORK_LOG_BASENAME"

# 檢查工作日誌完成狀態標記
COMPLETION_MARKERS=()
COMPLETION_MARKERS+=($(grep -c "重構完成時間\|完成時間\|建立時間.*2025" "$LATEST_WORK_LOG" 2>/dev/null || echo "0"))
COMPLETION_MARKERS+=($(grep -c "總執行時間\|重構方法論驗證成功" "$LATEST_WORK_LOG" 2>/dev/null || echo "0"))
COMPLETION_MARKERS+=($(grep -c "成功率.*100%\|重構成功關鍵要素\|品質標準達成" "$LATEST_WORK_LOG" 2>/dev/null || echo "0"))
COMPLETION_MARKERS+=($(grep -c "主要目標.*達成\|重構後期望狀態\|成果總結" "$LATEST_WORK_LOG" 2>/dev/null || echo "0"))

# 檢查是否有明確的完成時間戳記
COMPLETION_TIMESTAMP=""
if grep -q "重構完成時間" "$LATEST_WORK_LOG"; then
    COMPLETION_TIMESTAMP=$(grep "重構完成時間" "$LATEST_WORK_LOG" | head -1)
elif grep -q "完成時間" "$LATEST_WORK_LOG"; then
    COMPLETION_TIMESTAMP=$(grep "完成時間" "$LATEST_WORK_LOG" | head -1)
fi

# 檢查技術債務狀態
TECH_DEBT_INDICATORS=()
TECH_DEBT_INDICATORS+=($(grep -c "TODO" "$LATEST_WORK_LOG" 2>/dev/null || echo "0"))
TECH_DEBT_INDICATORS+=($(grep -c "FIXME" "$LATEST_WORK_LOG" 2>/dev/null || echo "0"))
TECH_DEBT_INDICATORS+=($(grep -c "未完成" "$LATEST_WORK_LOG" 2>/dev/null || echo "0"))
TECH_DEBT_INDICATORS+=($(grep -c "待解決" "$LATEST_WORK_LOG" 2>/dev/null || echo "0"))

# 檢查測試通過率
TEST_STATUS=""
if grep -q "測試.*100%" "$LATEST_WORK_LOG"; then
    TEST_STATUS="PASSED"
elif grep -q "測試.*通過" "$LATEST_WORK_LOG"; then
    TEST_STATUS="PASSED"
elif grep -q "測試.*失敗" "$LATEST_WORK_LOG"; then
    TEST_STATUS="FAILED"
fi

# 分析完成狀態
echo -e "\n${BLUE}🔍 工作完成狀態分析：${NC}"

COMPLETION_SCORE=0
for marker in "${COMPLETION_MARKERS[@]}"; do
    COMPLETION_SCORE=$((COMPLETION_SCORE + marker))
done

echo -e "${BLUE}📊 完成度指標：${NC} $COMPLETION_SCORE 項"

if [[ -n "$COMPLETION_TIMESTAMP" ]]; then
    echo -e "${GREEN}✅ 發現完成時間戳記：${NC}"
    echo -e "   $COMPLETION_TIMESTAMP"
fi

# 技術債務分析
TECH_DEBT_TOTAL=0
for debt in "${TECH_DEBT_INDICATORS[@]}"; do
    TECH_DEBT_TOTAL=$((TECH_DEBT_TOTAL + debt))
done

echo -e "${BLUE}⚠️  技術債務指標：${NC} $TECH_DEBT_TOTAL 項"

# 測試狀態
if [[ "$TEST_STATUS" == "PASSED" ]]; then
    echo -e "${GREEN}✅ 測試狀態：通過${NC}"
elif [[ "$TEST_STATUS" == "FAILED" ]]; then
    echo -e "${RED}❌ 測試狀態：失敗${NC}"
else
    echo -e "${YELLOW}⚠️  測試狀態：未明確標記${NC}"
fi

# 總體評估
echo -e "\n${BLUE}📋 工作狀態評估：${NC}"

WORK_STATUS="UNKNOWN"

# 判斷工作完成狀態
if [[ $COMPLETION_SCORE -ge 3 && $TECH_DEBT_TOTAL -eq 0 && "$TEST_STATUS" == "PASSED" ]]; then
    WORK_STATUS="COMPLETED"
    echo -e "${GREEN}✅ 工作狀態：已完成${NC}"
    echo -e "   • 完成度指標充足 ($COMPLETION_SCORE ≥ 3)"
    echo -e "   • 無技術債務 ($TECH_DEBT_TOTAL = 0)"
    echo -e "   • 測試通過"
elif [[ $COMPLETION_SCORE -ge 2 && $TECH_DEBT_TOTAL -le 2 ]]; then
    WORK_STATUS="MOSTLY_COMPLETED"
    echo -e "${YELLOW}⚠️  工作狀態：基本完成${NC}"
    echo -e "   • 完成度指標一般 ($COMPLETION_SCORE ≥ 2)"
    echo -e "   • 技術債務較少 ($TECH_DEBT_TOTAL ≤ 2)"
elif [[ $COMPLETION_SCORE -ge 1 ]]; then
    WORK_STATUS="IN_PROGRESS"
    echo -e "${YELLOW}🔄 工作狀態：進行中${NC}"
    echo -e "   • 有部分完成指標 ($COMPLETION_SCORE ≥ 1)"
    echo -e "   • 可能有未完成項目"
else
    WORK_STATUS="NOT_STARTED"
    echo -e "${RED}❌ 工作狀態：未完成或未開始${NC}"
    echo -e "   • 缺乏完成指標 ($COMPLETION_SCORE = 0)"
fi

# 輸出狀態碼供其他腳本使用
case "$WORK_STATUS" in
    "COMPLETED")
        echo -e "\n${GREEN}結論：當前工作已完成，可推進版本${NC}"
        exit 0
        ;;
    "MOSTLY_COMPLETED")
        echo -e "\n${YELLOW}結論：當前工作基本完成，建議檢查後推進${NC}"
        exit 1
        ;;
    "IN_PROGRESS")
        echo -e "\n${YELLOW}結論：當前工作進行中，建議完成後再推進${NC}"

        # 檢查todolist.md中的未完成任務
        PENDING_TODOS=$(grep -c "\[ \]" "$PROJECT_ROOT/docs/todolist.md" 2>/dev/null || echo "0")

        # 輸出停止原因到 stderr (Claude Code 會顯示)
        cat >&2 <<EOF

🚫 版本推進暫停 - 當前工作尚未完成

📋 停止原因：
• 工作日誌 $WORK_LOG_BASENAME 顯示工作仍在進行中
• 完成度指標不足 ($COMPLETION_SCORE < 3)
• 可能存在技術債務 ($TECH_DEBT_TOTAL 項)
• todolist.md 中有 $PENDING_TODOS 個待辦任務

📝 需要採取的行動：
1. 完成當前版本的核心開發工作
2. 確保測試通過率達到 100%
3. 解決所有技術債務 (TODO、FIXME 等)
4. 更新工作日誌，添加完成時間戳記

💡 建議檢查：
• 執行 'dart analyze' 檢查程式碼品質
• 執行 'dart test' 確認所有測試通過
• 在工作日誌中添加 ✅ 完成標記

🎯 建議的 TodoWrite 任務：
請執行以下 TodoWrite 來管理具體工作項目：

TodoWrite([
  {"content": "完成當前版本核心開發工作", "status": "pending", "activeForm": "完成當前版本核心開發工作"},
  {"content": "執行完整測試確保100%通過率", "status": "pending", "activeForm": "執行完整測試確保100%通過率"},
  {"content": "解決所有技術債務和 TODO 項目", "status": "pending", "activeForm": "解決所有技術債務和 TODO 項目"},
  {"content": "更新工作日誌添加完成時間戳記", "status": "pending", "activeForm": "更新工作日誌添加完成時間戳記"}
])

🔄 完成這些任務後工作狀態會自動變為已完成，可進行版本推進
EOF

        exit 2
        ;;
    *)
        echo -e "\n${RED}結論：當前工作未完成，需要繼續開發${NC}"

        # 檢查todolist.md中的未完成任務
        PENDING_TODOS=$(grep -c "\[ \]" "$PROJECT_ROOT/docs/todolist.md" 2>/dev/null || echo "0")

        # 輸出停止原因到 stderr (Claude Code 會顯示)
        cat >&2 <<EOF

🚫 版本推進暫停 - 工作未開始或缺乏完成指標

📋 停止原因：
• 工作日誌 $WORK_LOG_BASENAME 缺乏完成指標 ($COMPLETION_SCORE = 0)
• 可能存在大量技術債務 ($TECH_DEBT_TOTAL 項)
• 測試狀態：$TEST_STATUS
• todolist.md 中有 $PENDING_TODOS 個待辦任務

📝 需要採取的行動：
1. 開始或繼續當前版本的開發工作
2. 建立明確的工作完成標記
3. 解決所有待處理的技術債務
4. 確保測試通過率達到 100%

💡 建議步驟：
• 檢查工作日誌是否準確反映當前進度
• 添加完成時間戳記和成功指標
• 執行完整的測試和分析
• 更新工作狀態標記

🎯 建議的 TodoWrite 任務：
請執行以下 TodoWrite 開始系統化工作：

TodoWrite([
  {"content": "開始當前版本的核心開發工作", "status": "pending", "activeForm": "開始當前版本的核心開發工作"},
  {"content": "建立工作完成標記和時間戳記", "status": "pending", "activeForm": "建立工作完成標記和時間戳記"},
  {"content": "執行技術債務清理工作", "status": "pending", "activeForm": "執行技術債務清理工作"},
  {"content": "確保測試框架運行正常", "status": "pending", "activeForm": "確保測試框架運行正常"}
])

🔄 開始這些任務後工作狀態會有所改善，逐步達到完成標準
EOF

        exit 3
        ;;
esac