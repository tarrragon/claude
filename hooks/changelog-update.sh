#!/bin/bash
# CHANGELOG 自動更新 Hook
# 在 pre-commit 時自動偵測 .claude 變更並更新版本號和 CHANGELOG
#
# 版本號規則：
# - Major (X.0.0): CLAUDE.md 或 FLUTTER.md 變更
# - Minor (X.Y.0): 新增檔案
# - Patch (X.Y.Z): 修改既有檔案

set -e

# 顏色定義
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 檔案路徑
VERSION_FILE=".claude/VERSION"
CHANGELOG_FILE=".claude/CHANGELOG.md"

# 檢查是否在 git repo 中
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ 錯誤: 不在 git 倉庫中${NC}"
    exit 1
fi

# 取得當前版本號
get_current_version() {
    if [ -f "$VERSION_FILE" ]; then
        cat "$VERSION_FILE" | tr -d '\n'
    else
        echo "1.0.0"
    fi
}

# 解析版本號
parse_version() {
    local version=$1
    IFS='.' read -r major minor patch <<< "$version"
    echo "$major $minor $patch"
}

# 計算新版本號
calc_new_version() {
    local version_type=$1
    local current_version=$(get_current_version)
    read major minor patch <<< $(parse_version "$current_version")

    case "$version_type" in
        major)
            echo "$((major + 1)).0.0"
            ;;
        minor)
            echo "${major}.$((minor + 1)).0"
            ;;
        patch)
            echo "${major}.${minor}.$((patch + 1))"
            ;;
        *)
            echo "$current_version"
            ;;
    esac
}

# 檢測 .claude 相關變更
detect_claude_changes() {
    # 優先檢查 staging 區（pre-commit 場景）
    local staged_changes=$(git diff --cached --name-status -- .claude/ CLAUDE.md FLUTTER.md 2>/dev/null || echo "")

    if [ -n "$staged_changes" ]; then
        echo "$staged_changes"
        return
    fi

    # 檢查是否是第一個 commit（臨時 repo 場景，如 sync-push）
    if ! git rev-parse HEAD~1 >/dev/null 2>&1; then
        # 第一個 commit，檢查所有 staged 檔案
        git diff --cached --name-status 2>/dev/null || echo ""
        return
    fi

    # 如果 staging 區為空，檢查最近的 commit（sync-push 場景）
    # 取得最近一次 commit 的變更
    git diff-tree --no-commit-id --name-status -r HEAD -- .claude/ CLAUDE.md FLUTTER.md 2>/dev/null || echo ""
}

# 判斷版本類型
determine_version_type() {
    local changes=$1
    local version_type="none"

    # 檢查是否有變更
    if [ -z "$changes" ]; then
        echo "none"
        return
    fi

    # 檢查 CLAUDE.md 或 FLUTTER.md 變更 → major
    if echo "$changes" | grep -qE '^[AMD]\s+(CLAUDE\.md|FLUTTER\.md)$'; then
        echo "major"
        return
    fi

    # 檢查是否有新增檔案 → minor
    if echo "$changes" | grep -qE '^A\s+\.claude/'; then
        echo "minor"
        return
    fi

    # 檢查是否有修改或刪除 → patch
    if echo "$changes" | grep -qE '^[MD]\s+\.claude/'; then
        echo "patch"
        return
    fi

    echo "none"
}

# 分類變更（Added/Changed/Removed）
categorize_changes() {
    local changes=$1
    local added=""
    local changed=""
    local removed=""

    while IFS= read -r line; do
        if [ -z "$line" ]; then
            continue
        fi

        local status=$(echo "$line" | awk '{print $1}')
        local file=$(echo "$line" | awk '{print $2}')

        # 跳過 CHANGELOG 和 VERSION 本身
        if [[ "$file" == "$CHANGELOG_FILE" ]] || [[ "$file" == "$VERSION_FILE" ]]; then
            continue
        fi

        case "$status" in
            A)
                added="${added}- ${file}\n"
                ;;
            M)
                changed="${changed}- ${file}\n"
                ;;
            D)
                removed="${removed}- ${file}\n"
                ;;
        esac
    done <<< "$changes"

    echo -e "ADDED:${added}CHANGED:${changed}REMOVED:${removed}"
}

# 取得 commit 訊息（從 .git/COMMIT_EDITMSG 或環境變數）
get_commit_message() {
    if [ -f ".git/COMMIT_EDITMSG" ]; then
        # 只取第一行（標題）
        head -n 1 ".git/COMMIT_EDITMSG" | tr -d '\n'
    else
        echo ""
    fi
}

# 更新 CHANGELOG
update_changelog() {
    local new_version=$1
    local categorized_changes=$2
    local commit_message=$3
    local current_date=$(date '+%Y-%m-%d')

    # 解析分類變更
    local added=$(echo "$categorized_changes" | sed -n 's/^ADDED://p' | tr -d '\n')
    local changed=$(echo "$categorized_changes" | sed -n 's/^CHANGED://p' | tr -d '\n')
    local removed=$(echo "$categorized_changes" | sed -n 's/^REMOVED://p' | tr -d '\n')

    # 建立新版本區塊
    local new_entry="## [${new_version}] - ${current_date}\n\n"

    # 如果有 commit 訊息，加入摘要
    if [ -n "$commit_message" ]; then
        new_entry="${new_entry}### Summary\n${commit_message}\n\n"
    fi

    # 加入變更分類
    if [ -n "$added" ]; then
        new_entry="${new_entry}### Added\n${added}\n"
    fi

    if [ -n "$changed" ]; then
        new_entry="${new_entry}### Changed\n${changed}\n"
    fi

    if [ -n "$removed" ]; then
        new_entry="${new_entry}### Removed\n${removed}\n"
    fi

    new_entry="${new_entry}---\n\n"

    # 在 CHANGELOG 中找到第一個 ## [版本] 的位置，插入新版本
    if [ -f "$CHANGELOG_FILE" ]; then
        # 使用 awk 在第一個版本區塊前插入新內容
        awk -v new_entry="$new_entry" '
            /^## \[/ && !inserted {
                print new_entry
                inserted=1
            }
            { print }
        ' "$CHANGELOG_FILE" > "${CHANGELOG_FILE}.tmp"

        mv "${CHANGELOG_FILE}.tmp" "$CHANGELOG_FILE"
    else
        echo -e "${RED}❌ 錯誤: CHANGELOG 檔案不存在${NC}"
        return 1
    fi
}

# 更新 VERSION 檔案
update_version_file() {
    local new_version=$1
    echo "$new_version" > "$VERSION_FILE"
}

# 主邏輯
main() {
    echo -e "${BLUE}🔍 檢查 .claude 相關變更...${NC}"

    # 檢測變更
    local changes=$(detect_claude_changes)

    if [ -z "$changes" ]; then
        echo -e "${YELLOW}ℹ️  沒有 .claude 相關變更，跳過版本更新${NC}"
        exit 0
    fi

    echo -e "${GREEN}📝 偵測到以下變更：${NC}"
    echo "$changes" | while read line; do
        echo "  $line"
    done
    echo ""

    # 判斷版本類型
    local version_type=$(determine_version_type "$changes")

    if [ "$version_type" == "none" ]; then
        echo -e "${YELLOW}ℹ️  無需更新版本${NC}"
        exit 0
    fi

    # 計算新版本號
    local current_version=$(get_current_version)
    local new_version=$(calc_new_version "$version_type")

    echo -e "${GREEN}📊 版本更新：${NC}"
    echo -e "  當前版本: ${current_version}"
    echo -e "  新版本: ${new_version} (${version_type})"
    echo ""

    # 分類變更
    local categorized=$(categorize_changes "$changes")

    # 取得 commit 訊息
    local commit_msg=$(get_commit_message)

    # 更新 CHANGELOG
    echo -e "${BLUE}📝 更新 CHANGELOG...${NC}"
    update_changelog "$new_version" "$categorized" "$commit_msg"

    # 更新 VERSION
    echo -e "${BLUE}🔢 更新 VERSION...${NC}"
    update_version_file "$new_version"

    # 將 CHANGELOG 和 VERSION 加入 staging
    git add "$CHANGELOG_FILE" "$VERSION_FILE"

    echo -e "${GREEN}✅ CHANGELOG 和 VERSION 已更新並加入 staging 區${NC}"
    echo -e "${GREEN}   版本: ${new_version}${NC}"
}

# 執行主邏輯
main
