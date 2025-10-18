#!/bin/bash

# common-functions.sh
# Hook 系統通用函數庫

# 透過 CLAUDE.md 位置動態定位專案根目錄
get_project_root() {
    local current_dir="$PWD"

    # 從當前目錄開始往上搜尋 CLAUDE.md
    while [[ "$current_dir" != "/" ]]; do
        if [[ -f "$current_dir/CLAUDE.md" ]]; then
            echo "$current_dir"
            return 0
        fi
        current_dir="$(dirname "$current_dir")"
    done

    # 如果找不到，回傳錯誤
    echo "錯誤: 找不到 CLAUDE.md，無法確定專案根目錄" >&2
    return 1
}

# 設定專案根目錄和相關環境變數
setup_project_environment() {
    export CLAUDE_PROJECT_DIR="$(get_project_root)"
    if [[ $? -ne 0 ]]; then
        echo "錯誤: 無法設定專案環境" >&2
        return 1
    fi

    export CLAUDE_HOOKS_DIR="$CLAUDE_PROJECT_DIR/.claude/hooks"
    export CLAUDE_LOGS_DIR="$CLAUDE_PROJECT_DIR/.claude/hook-logs"

    # 確保日誌目錄存在
    mkdir -p "$CLAUDE_LOGS_DIR"

    return 0
}

# 通用日誌函數
log_with_timestamp() {
    local log_file="$1"
    local message="$2"

    if [[ -n "$log_file" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" | tee -a "$log_file"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message"
    fi
}

# 檢查關鍵檔案是否存在
check_key_files() {
    local project_root="$1"
    local missing_files=0

    local key_files=(
        "CLAUDE.md"
        "pubspec.yaml"
        "docs/todolist.md"
        ".claude/tdd-collaboration-flow.md"
    )

    for file in "${key_files[@]}"; do
        if [[ ! -f "$project_root/$file" ]]; then
            echo "⚠️  關鍵檔案缺失: $file" >&2
            missing_files=$((missing_files + 1))
        fi
    done

    return $missing_files
}

# 檢查檔案是否應該被開發流程檢查
# 回傳 0 = 應該檢查, 1 = 應該跳過
should_check_file() {
    local file="$1"

    # 排除文件檔案（工作日誌除外）
    if [[ "$file" =~ \.md$ ]] && [[ ! "$file" =~ docs/work-logs/v[0-9]+\.[0-9]+\.[0-9]+ ]]; then
        return 1
    fi

    # 排除測試檔案（包含 test/ 目錄、_test/_spec 結尾檔案）
    if [[ "$file" =~ test/|spec/|_test\.(dart|js|ts)$|_spec\.(dart|js|ts)$ ]]; then
        return 1
    fi

    # 排除整個 .claude 目錄（Hook 系統和腳本）
    if [[ "$file" =~ ^\.claude/ ]]; then
        return 1
    fi

    # 排除生成檔案（包含 .g.dart, .freezed.dart, generated/ 目錄）
    if [[ "$file" =~ \.(g|freezed)\.dart$|/generated/ ]]; then
        return 1
    fi

    # 排除文檔目錄（工作日誌除外）
    if [[ "$file" =~ ^docs/ ]] && [[ ! "$file" =~ ^docs/work-logs/v[0-9]+\.[0-9]+\.[0-9]+ ]]; then
        return 1
    fi

    # 其他檔案應該檢查
    return 0
}

# 過濾檔案清單，只保留應該檢查的檔案
filter_files_for_dev_check() {
    local files="$1"
    local filtered=""

    while IFS= read -r line; do
        if [ -z "$line" ]; then
            continue
        fi

        # 提取檔案路徑（處理 git status 格式）
        local file=$(echo "$line" | awk '{print $NF}')

        if should_check_file "$file"; then
            filtered="${filtered}${line}\n"
        fi
    done <<< "$files"

    echo -e "$filtered"
}# 測試註解
