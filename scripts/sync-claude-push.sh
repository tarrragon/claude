#!/bin/bash
# .claude 資料夾同步腳本 - 推送到獨立 repo
# 使用方式: ./.claude/scripts/sync-claude-push.sh "提交訊息"
#
# 推送內容:
# - .claude/ 目錄（包含 templates/CLAUDE-template.md、project-templates/FLUTTER.md）
#
# 不推送內容:
# - 根目錄 CLAUDE.md（專案特定配置）

set -e

# 顏色定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 檢查是否提供提交訊息
if [ -z "$1" ]; then
    echo -e "${RED}錯誤: 請提供提交訊息${NC}"
    echo "使用方式: $0 \"提交訊息\""
    exit 1
fi

COMMIT_MESSAGE="$1"

echo -e "${YELLOW}開始推送 .claude 資料夾到獨立 repo...${NC}"

# 1. 確保 .claude 變更已提交到主專案（不再檢查 CLAUDE.md）
echo -e "${YELLOW}檢查 .claude 資料夾狀態...${NC}"
if git status --porcelain .claude | grep -q .; then
    echo -e "${RED}警告: .claude 有未提交的變更${NC}"
    echo "請先提交到主專案，或使用 git add .claude"
    exit 1
fi

# 2. Clone 遠端 repo（保留歷史）
echo -e "${YELLOW}Clone 遠端 repo（保留歷史）...${NC}"
TEMP_DIR=$(mktemp -d)
git clone https://github.com/tarrragon/claude.git "$TEMP_DIR"
cd "$TEMP_DIR"

# 讀取遠端版本號和 CHANGELOG（在刪除前保存）
echo -e "${YELLOW}讀取遠端版本號...${NC}"
if [ -f "VERSION" ]; then
    REMOTE_VERSION=$(cat VERSION | tr -d '\n')
    echo -e "${GREEN}   遠端版本: v${REMOTE_VERSION}${NC}"
else
    REMOTE_VERSION="1.0.0"
    echo -e "${YELLOW}   遠端無版本檔案，使用預設 v1.0.0${NC}"
fi

# 保存 CHANGELOG 內容
if [ -f "CHANGELOG.md" ]; then
    SAVED_CHANGELOG=$(cat CHANGELOG.md)
fi

# 清空現有內容（保留 .git 目錄）
echo -e "${YELLOW}清空舊內容...${NC}"
find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +

# 複製 .claude/ 目錄內容（排除本機暫存檔案）
echo -e "${YELLOW}複製 .claude 配置檔案...${NC}"
rsync -av \
    --exclude='hook-logs' \
    --exclude='PM_INTERVENTION_REQUIRED' \
    --exclude='ARCHITECTURE_REVIEW_REQUIRED' \
    --exclude='pm-status.json' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    "$OLDPWD/.claude/" .

echo -e "${YELLOW}   注意: CLAUDE.md 不再同步（專案特定配置）${NC}"
echo -e "${GREEN}   FLUTTER.md 位於 project-templates/ 目錄中（已由 rsync 複製）${NC}"
echo -e "${GREEN}   CLAUDE-template.md 位於 templates/ 目錄中${NC}"

# 計算新版本號（使用之前保存的 REMOTE_VERSION）
echo -e "${YELLOW}計算新版本號...${NC}"
IFS='.' read -r major minor patch <<< "$REMOTE_VERSION"
NEW_VERSION="${major}.${minor}.$((patch + 1))"

# 更新 VERSION 檔案
echo "$NEW_VERSION" > VERSION

# 恢復並更新 CHANGELOG
CURRENT_DATE=$(date '+%Y-%m-%d')

# 建立新版本區塊
NEW_ENTRY="## [${NEW_VERSION}] - ${CURRENT_DATE}

### Summary
${COMMIT_MESSAGE}

---

"

if [ -n "$SAVED_CHANGELOG" ]; then
    # 寫入新版本區塊到臨時檔案
    echo "$NEW_ENTRY" > CHANGELOG.md.new
    # 將舊 CHANGELOG 從第一個版本標題開始附加
    echo "$SAVED_CHANGELOG" | sed -n '/^## \[/,$p' >> CHANGELOG.md.new
    mv CHANGELOG.md.new CHANGELOG.md
else
    # 沒有舊 CHANGELOG，建立新的
    echo "# CHANGELOG

$NEW_ENTRY" > CHANGELOG.md
fi

echo -e "${GREEN}版本: v${NEW_VERSION} (自動遞增)${NC}"
COMMIT_MSG="v${NEW_VERSION}: ${COMMIT_MESSAGE}"

echo -e "${YELLOW}提交變更...${NC}"
git add -A

# 檢查是否有實際變更
if git diff --cached --quiet; then
    echo -e "${YELLOW}沒有變更需要推送${NC}"
    cd "$OLDPWD"
    rm -rf "$TEMP_DIR"
    exit 0
fi

git commit -m "$COMMIT_MSG"

echo -e "${YELLOW}推送到獨立 repo (claude-shared)...${NC}"
# remote 已存在（clone 時建立），直接推送
git push origin main

# 3. 清理臨時目錄
cd "$OLDPWD"
rm -rf "$TEMP_DIR"

echo -e "${GREEN}成功推送 .claude 到獨立 repo！${NC}"
echo -e "${GREEN}Remote: https://github.com/tarrragon/claude.git${NC}"
echo -e "${GREEN}遠端 commit 歷史已保留${NC}"
echo -e "${YELLOW}注意: 根目錄 CLAUDE.md 未被推送（專案特定配置）${NC}"
