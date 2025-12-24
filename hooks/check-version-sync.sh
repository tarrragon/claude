#!/bin/bash

# =============================================================================
# 版號同步檢查腳本 - check-version-sync.sh
# =============================================================================
#
# 檢查 pubspec.yaml 版本號與實際開發進度是否同步
# 用於 smart-version-check 指令的第一階段檢查
#
# 檢查內容：
# - pubspec.yaml 版本號是否與當前工作日誌版本一致
# - 版本號格式是否正確 (語意化版本控制)
# - 確保版本號反映真實開發進度
# - CHANGELOG.md 與 work-log 一致性檢查
# =============================================================================

set -e

# 使用官方環境變數（如果存在）
if [ -n "$CLAUDE_PROJECT_DIR" ]; then
    PROJECT_ROOT="$CLAUDE_PROJECT_DIR"
else
    # Fallback 到手動定位
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

# 設定關鍵路徑
PUBSPEC_FILE="$PROJECT_ROOT/pubspec.yaml"
WORK_LOGS_DIR="$PROJECT_ROOT/docs/work-logs"
TODOLIST_FILE="$PROJECT_ROOT/docs/todolist.md"
CHANGELOG="$PROJECT_ROOT/CHANGELOG.md"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 版號同步檢查開始...${NC}"

# 檢查必要文件是否存在
if [[ ! -f "$PUBSPEC_FILE" ]]; then
    echo -e "${RED}❌ 錯誤：找不到 pubspec.yaml 檔案${NC}"
    exit 1
fi

if [[ ! -d "$WORK_LOGS_DIR" ]]; then
    echo -e "${RED}❌ 錯誤：找不到工作日誌目錄 docs/work-logs/${NC}"
    exit 1
fi

if [[ ! -f "$TODOLIST_FILE" ]]; then
    echo -e "${RED}❌ 錯誤：找不到 todolist.md 檔案${NC}"
    exit 1
fi

# 從 pubspec.yaml 提取版本號
PUBSPEC_VERSION=$(grep '^version:' "$PUBSPEC_FILE" | sed 's/version: *//' | tr -d '"' | tr -d "'")

if [[ -z "$PUBSPEC_VERSION" ]]; then
    echo -e "${RED}❌ 錯誤：無法從 pubspec.yaml 讀取版本號${NC}"
    exit 1
fi

echo -e "${BLUE}📋 pubspec.yaml 版本：${NC} $PUBSPEC_VERSION"

# 驗證版本號格式 (語意化版本控制: x.y.z+build)
if [[ ! "$PUBSPEC_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(\+[0-9]+)?$ ]]; then
    echo -e "${YELLOW}⚠️  警告：版本號格式不符合語意化版本控制規範${NC}"
    echo -e "   當前格式：$PUBSPEC_VERSION"
    echo -e "   預期格式：x.y.z+build (例如: 0.7.6+1)"
fi

# 從版本號提取主版本 (例如 0.7.6+1 -> v0.7.6)
MAIN_VERSION=$(echo "$PUBSPEC_VERSION" | sed 's/+.*//' | sed 's/^/v/')
echo -e "${BLUE}🎯 主版本號：${NC} $MAIN_VERSION"

# 查找最新的工作日誌檔案 (按檔案名稱中的版本號排序)
LATEST_WORK_LOG=$(find "$WORK_LOGS_DIR" -name "v*.md" -type f | sort -V | tail -1)

if [[ -z "$LATEST_WORK_LOG" ]]; then
    echo -e "${RED}❌ 錯誤：工作日誌目錄中找不到任何版本工作日誌${NC}"
    exit 1
fi

# 從工作日誌檔名提取版本號
WORK_LOG_BASENAME=$(basename "$LATEST_WORK_LOG")
WORK_LOG_VERSION=$(echo "$WORK_LOG_BASENAME" | grep -o '^v[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)

if [[ -z "$WORK_LOG_VERSION" ]]; then
    echo -e "${YELLOW}⚠️  警告：無法從工作日誌檔名提取版本號${NC}"
    echo -e "   檔案：$WORK_LOG_BASENAME"
else
    echo -e "${BLUE}📝 最新工作日誌版本：${NC} $WORK_LOG_VERSION"
fi

# 檢查 todolist.md 中的專案版本狀態
TODOLIST_VERSION=$(grep -o "專案版本.*v[0-9]\+\.[0-9]\+\.[0-9]\+" "$TODOLIST_FILE" | grep -o "v[0-9]\+\.[0-9]\+\.[0-9]\+" | head -1)

if [[ -n "$TODOLIST_VERSION" ]]; then
    echo -e "${BLUE}📋 todolist.md 專案版本：${NC} $TODOLIST_VERSION"
else
    echo -e "${YELLOW}⚠️  警告：todolist.md 中找不到明確的專案版本標記${NC}"
fi

# 版本同步分析
echo -e "\n${BLUE}🔍 版本同步分析：${NC}"

SYNC_STATUS="SYNCED"
SYNC_ISSUES=()

# 比較 pubspec.yaml 與最新工作日誌版本
if [[ -n "$WORK_LOG_VERSION" && "$MAIN_VERSION" != "$WORK_LOG_VERSION" ]]; then
    SYNC_STATUS="OUT_OF_SYNC"
    SYNC_ISSUES+=("pubspec.yaml ($MAIN_VERSION) 與最新工作日誌 ($WORK_LOG_VERSION) 版本不一致")
fi

# 比較 pubspec.yaml 與 todolist.md 版本
if [[ -n "$TODOLIST_VERSION" && "$MAIN_VERSION" != "$TODOLIST_VERSION" ]]; then
    SYNC_STATUS="OUT_OF_SYNC"
    SYNC_ISSUES+=("pubspec.yaml ($MAIN_VERSION) 與 todolist.md ($TODOLIST_VERSION) 版本不一致")
fi

# 檢查 CHANGELOG.md 與 work-log 一致性
echo -e "\n${BLUE}📚 檢查 CHANGELOG 與 work-log 一致性...${NC}"

if [[ -f "$CHANGELOG" ]]; then
    # 從工作日誌檔名提取版本號（已在前面取得 WORK_LOG_VERSION）
    if [[ -n "$WORK_LOG_VERSION" ]]; then
        # 移除版本號前的 'v' 以匹配 CHANGELOG 格式 (例如: v0.12.7 -> 0.12.7)
        WORK_LOG_VERSION_NO_V=$(echo "$WORK_LOG_VERSION" | sed 's/^v//')

        # 檢查 CHANGELOG 是否包含此版本
        # 支援多種格式：## [X.Y.Z] 或 ## X.Y.Z 或 ### [X.Y.Z] 或 ## [vX.Y.Z]
        if grep -q "^##\{1,3\} \?\[\?v\?$WORK_LOG_VERSION_NO_V\]\?" "$CHANGELOG" 2>/dev/null; then
            echo -e "${GREEN}✅ CHANGELOG 包含版本 $WORK_LOG_VERSION${NC}"
        else
            SYNC_STATUS="OUT_OF_SYNC"
            SYNC_ISSUES+=("CHANGELOG 缺少版本 $WORK_LOG_VERSION 的記錄")
            echo -e "${YELLOW}⚠️  CHANGELOG 缺少版本 $WORK_LOG_VERSION 的記錄${NC}"
            echo -e "   💡 建議：版本發布時從 work-log 提取功能變動更新到 CHANGELOG"
        fi
    fi

    # 檢查 CHANGELOG 版本號與 pubspec.yaml 是否同步
    # 支援 [X.Y.Z] 或 [vX.Y.Z] 格式
    CHANGELOG_LATEST_VERSION=$(grep -o "^##\{1,3\} \?\[\?v\?[0-9]\+\.[0-9]\+\.[0-9]\+\]\?" "$CHANGELOG" | head -1 | grep -o "v\?[0-9]\+\.[0-9]\+\.[0-9]\+" | sed 's/^\([0-9]\)/v\1/')

    if [[ -n "$CHANGELOG_LATEST_VERSION" ]]; then
        echo -e "${BLUE}📋 CHANGELOG 最新版本：${NC} $CHANGELOG_LATEST_VERSION"

        if [[ "$MAIN_VERSION" != "$CHANGELOG_LATEST_VERSION" ]]; then
            SYNC_STATUS="OUT_OF_SYNC"
            SYNC_ISSUES+=("CHANGELOG 最新版本 ($CHANGELOG_LATEST_VERSION) 與 pubspec.yaml ($MAIN_VERSION) 不一致")
        fi
    else
        echo -e "${YELLOW}⚠️  警告：無法從 CHANGELOG 提取版本號${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  警告：找不到 CHANGELOG.md 檔案${NC}"
    echo -e "   💡 建議：建立 CHANGELOG.md 記錄版本變更歷史"
fi

# 輸出結果
if [[ "$SYNC_STATUS" == "SYNCED" ]]; then
    echo -e "${GREEN}✅ 版本同步狀態：正常${NC}"
    echo -e "   所有版本號一致：$MAIN_VERSION"
    exit 0
else
    echo -e "${RED}❌ 版本同步狀態：不一致${NC}"
    echo -e "\n${YELLOW}發現的同步問題：${NC}"
    for issue in "${SYNC_ISSUES[@]}"; do
        echo -e "   • $issue"
    done

    echo -e "\n${BLUE}建議修正操作：${NC}"
    echo -e "   1. 確認當前實際開發進度"
    echo -e "   2. 選擇正確的版本號作為標準"
    echo -e "   3. 更新不一致的檔案至正確版本"
    echo -e "   4. 重新執行此檢查確認同步"

    exit 1
fi