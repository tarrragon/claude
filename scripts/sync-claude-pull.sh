#!/bin/bash
# .claude 資料夾同步腳本 - 從獨立 repo 拉取更新
# 使用方式: ./.claude/scripts/sync-claude-pull.sh
#
# 拉取內容:
# - .claude/ 目錄所有檔案
# - FLUTTER.md
#
# 不覆蓋內容:
# - 根目錄 CLAUDE.md（保留專案特定配置）

set -e

# 顏色定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}開始從獨立 repo 拉取 .claude 更新...${NC}"

# 1. 檢查本地是否有未提交的變更（不再檢查 CLAUDE.md）
echo -e "${YELLOW}檢查本地狀態...${NC}"
if git status --porcelain .claude FLUTTER.md | grep -q .; then
    echo -e "${RED}警告: .claude 或 FLUTTER.md 有未提交的變更${NC}"
    echo "請先提交或暫存變更，避免衝突"
    exit 1
fi

# 2. Clone 獨立 repo 到臨時目錄
echo -e "${YELLOW}從獨立 repo 拉取更新...${NC}"
TEMP_DIR=$(mktemp -d)
git clone https://github.com/tarrragon/claude.git "$TEMP_DIR"

# 3. 備份當前 .claude 和 FLUTTER.md（不備份 CLAUDE.md）
echo -e "${YELLOW}備份當前配置...${NC}"
BACKUP_DIR=$(mktemp -d)
cp -r .claude "$BACKUP_DIR/"
[ -f FLUTTER.md ] && cp FLUTTER.md "$BACKUP_DIR/" 2>/dev/null || true

# 4. 更新 .claude 資料夾（排除 project-templates）
echo -e "${YELLOW}更新 .claude 資料夾...${NC}"
rm -rf .claude
mkdir -p .claude
cd "$TEMP_DIR"
for item in *; do
    if [ "$item" != "project-templates" ]; then
        cp -r "$item" "$OLDPWD/.claude/"
    fi
done
cd "$OLDPWD"

# 5. 只更新 FLUTTER.md（不更新 CLAUDE.md）
if [ -d "$TEMP_DIR/project-templates" ]; then
    echo -e "${YELLOW}更新專案模板檔案...${NC}"
    [ -f "$TEMP_DIR/project-templates/FLUTTER.md" ] && cp "$TEMP_DIR/project-templates/FLUTTER.md" .
    echo -e "${GREEN}   已更新 FLUTTER.md${NC}"
    echo -e "${YELLOW}   注意: CLAUDE.md 未被覆蓋（保留專案特定配置）${NC}"
fi

# 6. 清理臨時目錄
rm -rf "$TEMP_DIR"

echo -e "${GREEN}成功拉取 .claude 更新！${NC}"
echo -e "${GREEN}備份位置: $BACKUP_DIR${NC}"
echo -e "${GREEN}請檢查變更並測試 Hook 系統是否正常運作${NC}"
echo -e "${YELLOW}如需還原，執行: cp -r $BACKUP_DIR/.claude .${NC}"
echo ""
echo -e "${YELLOW}=== 新專案初始化提示 ===${NC}"
echo -e "${YELLOW}如果是新專案，請手動建立 CLAUDE.md:${NC}"
echo -e "${YELLOW}  1. cp .claude/templates/CLAUDE-template.md CLAUDE.md${NC}"
echo -e "${YELLOW}  2. 填入專案特定資訊${NC}"
echo -e "${YELLOW}  3. 驗證所有連結有效${NC}"
