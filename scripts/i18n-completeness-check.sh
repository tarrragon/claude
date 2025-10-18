#!/bin/bash

# 多語系完整性檢查腳本
# 用途：檢查所有語言檔案的翻譯完整性，識別缺失項目

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 專案根目錄
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
L10N_DIR="$PROJECT_ROOT/lib/l10n"

echo -e "${BLUE}===== 多語系翻譯完整性檢查 =====${NC}"
echo "檢查目錄: $L10N_DIR"
echo ""

# 檢查 l10n 目錄是否存在
if [ ! -d "$L10N_DIR" ]; then
    echo -e "${RED}錯誤: l10n 目錄不存在: $L10N_DIR${NC}"
    exit 1
fi

# 基準語言檔案 (最完整的檔案)
REFERENCE_FILE="$L10N_DIR/app_en.arb"

if [ ! -f "$REFERENCE_FILE" ]; then
    echo -e "${RED}錯誤: 基準檔案不存在: $REFERENCE_FILE${NC}"
    exit 1
fi

echo -e "${BLUE}基準檔案:${NC} $REFERENCE_FILE"

# 提取基準檔案中的所有翻譯 key
echo -e "${BLUE}正在分析基準檔案...${NC}"
reference_keys=$(grep -o '"[^"@]*":' "$REFERENCE_FILE" | grep -v '"@@locale"' | sed 's/"//g' | sed 's/://g' | sort)
reference_count=$(echo "$reference_keys" | wc -l | tr -d ' ')

echo -e "${GREEN}基準檔案包含 $reference_count 個翻譯 key${NC}"
echo ""

# 統計變數
total_files=0
complete_files=0
total_missing=0

# 結果儲存
results_file="/tmp/i18n_check_results.txt"
echo "多語系翻譯完整性檢查報告" > "$results_file"
echo "檢查時間: $(date)" >> "$results_file"
echo "==============================" >> "$results_file"
echo "" >> "$results_file"

# 檢查所有語言檔案
echo -e "${BLUE}檢查各語言檔案完整性:${NC}"
echo ""

for arb_file in "$L10N_DIR"/app_*.arb; do
    if [ ! -f "$arb_file" ]; then
        continue
    fi

    filename=$(basename "$arb_file")
    locale=$(echo "$filename" | sed 's/app_//g' | sed 's/.arb//g')

    # 跳過基準檔案
    if [ "$arb_file" = "$REFERENCE_FILE" ]; then
        echo -e "${GREEN}✓ $locale (基準檔案)${NC}"
        echo "$locale: 基準檔案 (100%)" >> "$results_file"
        ((total_files++))
        ((complete_files++))
        continue
    fi

    # 提取當前檔案的翻譯 key
    current_keys=$(grep -o '"[^"@]*":' "$arb_file" | grep -v '"@@locale"' | sed 's/"//g' | sed 's/://g' | sort)
    current_count=$(echo "$current_keys" | wc -l | tr -d ' ')

    # 如果檔案為空，設定計數為 0
    if [ -z "$current_keys" ]; then
        current_count=0
    fi

    # 找出缺失的 key
    missing_keys=""
    missing_count=0

    if [ $current_count -gt 0 ]; then
        missing_keys=$(comm -23 <(echo "$reference_keys") <(echo "$current_keys"))
        missing_count=$(echo "$missing_keys" | wc -l | tr -d ' ')

        # 如果沒有缺失項目，missing_count 應該是 0
        if [ -z "$missing_keys" ]; then
            missing_count=0
        fi
    else
        missing_keys="$reference_keys"
        missing_count=$reference_count
    fi

    # 計算完整度百分比
    completion_percentage=$(( (current_count * 100) / reference_count ))

    # 顯示結果
    if [ $missing_count -eq 0 ]; then
        echo -e "${GREEN}✓ $locale ($current_count/$reference_count keys, 100%)${NC}"
        ((complete_files++))
    elif [ $missing_count -le 5 ]; then
        echo -e "${YELLOW}⚠ $locale ($current_count/$reference_count keys, $completion_percentage%) - 缺失 $missing_count 項${NC}"
    else
        echo -e "${RED}✗ $locale ($current_count/$reference_count keys, $completion_percentage%) - 缺失 $missing_count 項${NC}"
    fi

    # 記錄到結果檔案
    echo "$locale: $current_count/$reference_count keys ($completion_percentage%) - 缺失 $missing_count 項" >> "$results_file"

    # 如果有缺失項目，列出詳細資訊
    if [ $missing_count -gt 0 ]; then
        echo "  缺失的翻譯 key:" >> "$results_file"
        echo "$missing_keys" | while read -r key; do
            if [ -n "$key" ]; then
                echo "    - $key" >> "$results_file"
            fi
        done
        echo "" >> "$results_file"
    fi

    ((total_files++))
    ((total_missing+=missing_count))
done

echo ""

# 生成統計摘要
echo -e "${BLUE}===== 檢查統計摘要 =====${NC}"
echo -e "${GREEN}檢查檔案總數: $total_files${NC}"
echo -e "${GREEN}完整檔案數量: $complete_files${NC}"
echo -e "${YELLOW}不完整檔案數: $((total_files - complete_files))${NC}"
echo -e "${RED}總缺失項目數: $total_missing${NC}"

# 記錄統計摘要
echo "" >> "$results_file"
echo "===== 統計摘要 =====" >> "$results_file"
echo "檢查檔案總數: $total_files" >> "$results_file"
echo "完整檔案數量: $complete_files" >> "$results_file"
echo "不完整檔案數: $((total_files - complete_files))" >> "$results_file"
echo "總缺失項目數: $total_missing" >> "$results_file"

# 建議修復優先級
echo ""
echo -e "${BLUE}===== 修復建議 =====${NC}"

if [ $total_missing -eq 0 ]; then
    echo -e "${GREEN}🎉 所有語言檔案都是完整的！${NC}"
elif [ $total_missing -le 10 ]; then
    echo -e "${YELLOW}⚠️  建議盡快修復少量缺失項目${NC}"
elif [ $total_missing -le 50 ]; then
    echo -e "${RED}❗ 建議分階段修復缺失項目${NC}"
else
    echo -e "${RED}🚨 嚴重缺失，建議立即執行大規模翻譯修復${NC}"
fi

echo ""
echo -e "${BLUE}詳細檢查報告已儲存至: $results_file${NC}"

# 如果有缺失項目，設定非零返回碼
if [ $total_missing -gt 0 ]; then
    echo -e "${YELLOW}警告: 發現翻譯缺失，建議修復後再進行部署${NC}"
    exit 1
else
    echo -e "${GREEN}✅ 多語系翻譯檢查通過${NC}"
    exit 0
fi