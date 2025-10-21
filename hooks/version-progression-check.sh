#!/bin/bash

# =============================================================================
# 版本推進決策腳本 - version-progression-check.sh
# =============================================================================
#
# 整合分析，提供版本推進建議
# 用於 smart-version-check 指令的第四階段檢查
#
# 決策輸出：系統將提供以下四種決策之一：
# - 決策A: 繼續當前版本開發 (decision_code = 0)
# - 決策B: 小版本推進 (decision_code = 1)
# - 決策C: 中版本推進 (decision_code = 2)
# - 決策D: 完成當前工作並總結 (decision_code = 3)
# =============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${PURPLE}🚀 版本推進決策分析開始...${NC}"

# 執行各階段檢查並收集結果
echo -e "\n${BLUE}📊 執行四階段檢查...${NC}"

# 階段 1: 版號同步檢查
echo -e "${CYAN}1️⃣ 版號同步檢查...${NC}"
VERSION_SYNC_STATUS=0
if ! "$PROJECT_ROOT/.claude/hooks/check-version-sync.sh" >/dev/null 2>&1; then
    VERSION_SYNC_STATUS=1
    echo -e "${YELLOW}   ⚠️  版本同步問題${NC}"
else
    echo -e "${GREEN}   ✅ 版本同步正常${NC}"
fi

# 階段 2: 工作日誌狀態檢查
echo -e "${CYAN}2️⃣ 工作日誌狀態檢查...${NC}"
WORK_LOG_STATUS=$("$PROJECT_ROOT/.claude/hooks/check-work-log.sh" >/dev/null 2>&1; echo $?)
case $WORK_LOG_STATUS in
    0) echo -e "${GREEN}   ✅ 工作已完成${NC}" ;;
    1) echo -e "${YELLOW}   ⚠️  工作基本完成${NC}" ;;
    2) echo -e "${YELLOW}   🔄 工作進行中${NC}" ;;
    *) echo -e "${RED}   ❌ 工作未完成${NC}" ;;
esac

# 階段 3: 下一步目標分析
echo -e "${CYAN}3️⃣ 下一步目標分析...${NC}"
OBJECTIVES_STATUS=$("$PROJECT_ROOT/.claude/hooks/check-next-objectives.sh" >/dev/null 2>&1; echo $?)
case $OBJECTIVES_STATUS in
    0) echo -e "${GREEN}   ✅ 版本系列完全完成${NC}" ;;
    1) echo -e "${YELLOW}   ⚠️  版本系列基本完成${NC}" ;;
    2) echo -e "${YELLOW}   🔄 版本系列進行中${NC}" ;;
    *) echo -e "${RED}   ❌ 版本系列未完成${NC}" ;;
esac

# 決策邏輯分析
echo -e "\n${PURPLE}🧠 決策邏輯分析...${NC}"

DECISION_CODE=0
DECISION_TYPE=""
DECISION_REASON=""
SUGGESTED_ACTION=""

# 決策矩陣
if [[ $WORK_LOG_STATUS -ge 2 ]]; then
    # 當前工作未完成或進行中
    DECISION_CODE=0
    DECISION_TYPE="繼續當前版本開發"
    DECISION_REASON="當前工作尚未完成"
    SUGGESTED_ACTION="更新工作進度，繼續當前開發"

elif [[ $WORK_LOG_STATUS -le 1 && $OBJECTIVES_STATUS -ge 2 ]]; then
    # 當前工作完成，但版本系列目標未完成
    DECISION_CODE=1
    DECISION_TYPE="小版本推進"
    DECISION_REASON="當前工作完成，版本系列目標未完成"
    SUGGESTED_ACTION="推進到下一個小版本 (patch 版本)"

elif [[ $WORK_LOG_STATUS -le 1 && $OBJECTIVES_STATUS -le 1 ]]; then
    # 當前工作完成，版本系列目標也完成
    DECISION_CODE=2
    DECISION_TYPE="中版本推進"
    DECISION_REASON="當前工作完成，版本系列目標完成"
    SUGGESTED_ACTION="推進到下一個中版本 (minor 版本)"

else
    # 特殊情況：需要總結
    DECISION_CODE=3
    DECISION_TYPE="完成當前工作並總結"
    DECISION_REASON="工作狀態需要明確總結"
    SUGGESTED_ACTION="完成當前工作日誌並總結"
fi

# 版本同步問題的特殊處理
if [[ $VERSION_SYNC_STATUS -ne 0 ]]; then
    echo -e "${RED}⚠️  檢測到版本同步問題，需要優先處理${NC}"
    DECISION_CODE=3
    DECISION_TYPE="修正版本同步問題"
    DECISION_REASON="版本號不同步，需要修正"
    SUGGESTED_ACTION="修正版本同步問題後重新檢查"
fi

# 輸出決策結果
echo -e "\n${PURPLE}📋 版本推進決策結果：${NC}"
echo -e "${BLUE}決策代碼：${NC} $DECISION_CODE"
echo -e "${BLUE}決策類型：${NC} $DECISION_TYPE"
echo -e "${BLUE}決策理由：${NC} $DECISION_REASON"
echo -e "${BLUE}建議操作：${NC} $SUGGESTED_ACTION"

# 具體操作指引
echo -e "\n${CYAN}💡 具體操作指引：${NC}"

case $DECISION_CODE in
    0)
        echo -e "${YELLOW}繼續當前版本開發：${NC}"
        echo -e "   1. 檢查當前工作項目進度"
        echo -e "   2. 更新工作日誌記錄進展"
        echo -e "   3. 完成未完成的開發任務"
        echo -e "   4. 確保測試通過率100%"
        ;;
    1)
        echo -e "${GREEN}小版本推進操作：${NC}"
        echo -e "   1. 更新 pubspec.yaml 版本號 (patch: x.y.z → x.y.z+1)"
        echo -e "   2. 建立新版本工作日誌"
        echo -e "   3. 開始下一個小版本開發"
        echo -e "   4. 提交當前完成狀態"
        ;;
    2)
        echo -e "${GREEN}中版本推進操作：${NC}"
        echo -e "   1. 更新 pubspec.yaml 版本號 (minor: x.y.z → x.y+1.0)"
        echo -e "   2. 更新 todolist.md 規劃新版本系列目標"
        echo -e "   3. 建立新版本系列工作日誌"
        echo -e "   4. 提交完整的版本系列成果"
        ;;
    3)
        echo -e "${RED}問題修正操作：${NC}"
        echo -e "   1. 檢查並修正發現的問題"
        echo -e "   2. 確保工作狀態明確"
        echo -e "   3. 完成必要的總結工作"
        echo -e "   4. 重新執行版本推進檢查"
        ;;
esac

# 版本推進驗證提醒
echo -e "\n${BLUE}📋 推進後驗證檢查清單：${NC}"
echo -e "   □ 版本號一致性檢查"
echo -e "   □ 工作日誌檔案建立確認"
echo -e "   □ todolist.md 更新狀態驗證"
echo -e "   □ 文件架構完整性檢查"

# 輸出決策代碼供其他腳本使用
echo -e "\n${PURPLE}🔢 決策代碼：$DECISION_CODE${NC}"
exit $DECISION_CODE