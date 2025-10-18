#!/bin/bash

# 🧹 上下文恢復任務完成清理器
#
# 功能：清理上下文恢復相關記憶檔案，避免重複執行和累積
# 使用時機：成功恢復工作狀態後執行
# 安全機制：保留最新檔案，備份重要記錄，提供確認機制

set -e

# 設定變數
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HOOK_LOGS_DIR="${PROJECT_DIR}/.claude/hook-logs"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# 顏色設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧹 上下文恢復任務完成清理${NC}"
echo "📁 專案目錄: ${PROJECT_DIR}"
echo "📂 Hook日誌目錄: ${HOOK_LOGS_DIR}"
echo ""

# 建立hook-logs目錄（如果不存在）
mkdir -p "${HOOK_LOGS_DIR}"

# 收集要清理的檔案
CONTEXT_RESUME_FILES=()
PRE_COMPACT_FILES=()
OLD_HOOK_LOGS=()

# 查找恢復提示詞檔案
if ls "${HOOK_LOGS_DIR}"/context-resume-*.md >/dev/null 2>&1; then
    while IFS= read -r -d '' file; do
        CONTEXT_RESUME_FILES+=("$file")
    done < <(find "${HOOK_LOGS_DIR}" -name "context-resume-*.md" -print0)
fi

# 查找PreCompact日誌檔案
if ls "${HOOK_LOGS_DIR}"/pre-compact-*.log >/dev/null 2>&1; then
    while IFS= read -r -d '' file; do
        PRE_COMPACT_FILES+=("$file")
    done < <(find "${HOOK_LOGS_DIR}" -name "pre-compact-*.log" -print0)
fi

# 查找過期的Hook日誌檔案（保留最新5個）
for log_type in startup prompt-submit stop; do
    if ls "${HOOK_LOGS_DIR}"/${log_type}-*.log >/dev/null 2>&1; then
        # 找出超過5個的舊檔案
        mapfile -t log_files < <(find "${HOOK_LOGS_DIR}" -name "${log_type}-*.log" | sort -r)
        if [ ${#log_files[@]} -gt 5 ]; then
            for ((i=5; i<${#log_files[@]}; i++)); do
                OLD_HOOK_LOGS+=("${log_files[i]}")
            done
        fi
    fi
done

# 顯示要清理的檔案
total_files=0
total_size=0

echo -e "${YELLOW}🗑️ 將要清理的檔案:${NC}"

if [ ${#CONTEXT_RESUME_FILES[@]} -gt 0 ]; then
    echo -e "${YELLOW}  📄 恢復提示詞檔案:${NC}"
    for file in "${CONTEXT_RESUME_FILES[@]}"; do
        size=$(stat -f%z "$file" 2>/dev/null || echo 0)
        echo "    - $(basename "$file") ($(awk '{if($1>1024*1024) printf "%.1fMB", $1/1024/1024; else if($1>1024) printf "%.1fKB", $1/1024; else printf "%dB", $1}' $size))"
        ((total_files++))
        ((total_size += size))
    done
fi

if [ ${#PRE_COMPACT_FILES[@]} -gt 0 ]; then
    echo -e "${YELLOW}  📋 PreCompact日誌檔案:${NC}"
    for file in "${PRE_COMPACT_FILES[@]}"; do
        size=$(stat -f%z "$file" 2>/dev/null || echo 0)
        echo "    - $(basename "$file") ($(awk '{if($1>1024*1024) printf "%.1fMB", $1/1024/1024; else if($1>1024) printf "%.1fKB", $1/1024; else printf "%dB", $1}' $size))"
        ((total_files++))
        ((total_size += size))
    done
fi

if [ ${#OLD_HOOK_LOGS[@]} -gt 0 ]; then
    echo -e "${YELLOW}  🗂️ 過期Hook日誌檔案:${NC}"
    for file in "${OLD_HOOK_LOGS[@]}"; do
        size=$(stat -f%z "$file" 2>/dev/null || echo 0)
        echo "    - $(basename "$file") ($(awk '{if($1>1024*1024) printf "%.1fMB", $1/1024/1024; else if($1>1024) printf "%.1fKB", $1/1024; else printf "%dB", $1}' $size))"
        ((total_files++))
        ((total_size += size))
    done
fi

if [ $total_files -eq 0 ]; then
    echo -e "${GREEN}✅ 沒有需要清理的檔案${NC}"
    echo ""
    echo "📊 清理統計:"
    echo "- 系統狀態: 乾淨"
    echo "- 上下文恢復: 已完成或無記錄"
    echo ""
    echo -e "${GREEN}✅ 系統已準備好進行新的開發工作${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}📊 清理統計預覽:${NC}"
echo "- 檔案總數: ${total_files}個"
echo "- 預計釋放空間: $(awk '{if($1>1024*1024) printf "%.1fMB", $1/1024/1024; else if($1>1024) printf "%.1fKB", $1/1024; else printf "%dB", $1}' $total_size)"
echo ""

# 確認清理
echo -e "${YELLOW}⚠️ 確認清理操作 (此操作不可逆)${NC}"
read -p "是否確定要清理這些檔案? [y/N]: " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ 清理操作已取消${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}🗑️ 開始清理...${NC}"

# 執行清理
cleaned_files=0
cleaned_size=0

# 清理恢復提示詞檔案
for file in "${CONTEXT_RESUME_FILES[@]}"; do
    if [ -f "$file" ]; then
        size=$(stat -f%z "$file" 2>/dev/null || echo 0)
        rm "$file"
        echo "✅ 已移除: $(basename "$file")"
        ((cleaned_files++))
        ((cleaned_size += size))
    fi
done

# 清理PreCompact日誌檔案
for file in "${PRE_COMPACT_FILES[@]}"; do
    if [ -f "$file" ]; then
        size=$(stat -f%z "$file" 2>/dev/null || echo 0)
        rm "$file"
        echo "✅ 已移除: $(basename "$file")"
        ((cleaned_files++))
        ((cleaned_size += size))
    fi
done

# 清理過期Hook日誌檔案
for file in "${OLD_HOOK_LOGS[@]}"; do
    if [ -f "$file" ]; then
        size=$(stat -f%z "$file" 2>/dev/null || echo 0)
        rm "$file"
        echo "✅ 已移除: $(basename "$file")"
        ((cleaned_files++))
        ((cleaned_size += size))
    fi
done

# 建立完成標記
COMPLETION_MARKER="${HOOK_LOGS_DIR}/resume-mission-completed-${TIMESTAMP}.marker"
cat > "${COMPLETION_MARKER}" << EOF
# 🧹 上下文恢復任務完成標記
完成時間: $(date '+%Y-%m-%d %H:%M:%S')
清理檔案數: ${cleaned_files}
釋放空間: $(awk '{if($1>1024*1024) printf "%.1fMB", $1/1024/1024; else if($1>1024) printf "%.1fKB", $1/1024; else printf "%dB", $1}' $cleaned_size)
專案目錄: ${PROJECT_DIR}

此標記表示上下文恢復任務已成功完成並清理。
系統已準備好進行新的開發工作。
EOF

echo ""
echo -e "${GREEN}✅ 清理完成${NC}"
echo ""
echo -e "${BLUE}📊 清理統計:${NC}"
echo "- 清理檔案數: ${cleaned_files}個"
echo "- 釋放空間: $(awk '{if($1>1024*1024) printf "%.1fMB", $1/1024/1024; else if($1>1024) printf "%.1fKB", $1/1024; else printf "%dB", $1}' $cleaned_size)"
echo "- 完成標記: $(basename "${COMPLETION_MARKER}")"
echo ""
echo -e "${GREEN}🎉 系統已準備好進行新的開發工作${NC}"
echo ""

# 建議下一步行動
echo -e "${BLUE}💡 建議下一步:${NC}"
echo "1. 檢查 docs/todolist.md 了解當前開發任務"
echo "2. 執行 git status 檢查工作狀態"
echo "3. 運行 flutter analyze 確認編譯狀態"
echo "4. 開始進行 v0.10.0 系列開發工作"
echo ""