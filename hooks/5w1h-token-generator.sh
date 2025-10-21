#!/bin/bash

# 5w1h-token-generator.sh
# 生成和管理 5W1H 對話 Token

# 設定路徑
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TOKEN_DIR="$PROJECT_ROOT/.claude/hook-logs/5w1h-tokens"

# 確保 Token 目錄存在
mkdir -p "$TOKEN_DIR"

# 生成新的 5W1H Token
generate_5w1h_token() {
    local timestamp=$(date +%Y%m%d-%H%M%S)
    # 使用更安全的隨機字符生成方式
    local random=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 6)
    local token="5W1H-${timestamp}-${random}"

    echo "$token"
}

# 儲存 Token 到檔案
save_token() {
    local token="$1"
    local session_id="session-$(date +%Y%m%d-%H%M%S)"
    local token_file="$TOKEN_DIR/${session_id}.token"

    cat > "$token_file" << EOF
# 5W1H Session Token
SESSION_START=$(date '+%Y-%m-%d %H:%M:%S')
TOKEN=$token
STATUS=active

# 此 Token 用於監控 5W1H 決策框架合規性
# 每次對話回答都必須以此 Token 開頭
EOF

    echo "$token_file"
}

# 驗證 Token 格式
validate_token() {
    local token="$1"
    if [[ "$token" =~ ^5W1H-[0-9]{8}-[0-9]{6}-[A-Za-z0-9]{6}$ ]]; then
        return 0
    else
        return 1
    fi
}

# 取得當前活躍的 Token
get_current_token() {
    local latest_token_file=$(ls -t "$TOKEN_DIR"/*.token 2>/dev/null | head -n 1)
    if [ -f "$latest_token_file" ]; then
        grep "^TOKEN=" "$latest_token_file" | cut -d'=' -f2
    fi
}

# 主執行邏輯
case "${1:-generate}" in
    generate)
        TOKEN=$(generate_5w1h_token)
        TOKEN_FILE=$(save_token "$TOKEN")
        echo "生成新的 5W1H Token: $TOKEN"
        echo "Token 檔案: $TOKEN_FILE"
        echo "$TOKEN"
        ;;
    current)
        CURRENT_TOKEN=$(get_current_token)
        if [ -n "$CURRENT_TOKEN" ]; then
            echo "$CURRENT_TOKEN"
        else
            echo "無活躍的 Token，建議執行 generate"
            exit 1
        fi
        ;;
    validate)
        if [ -z "$2" ]; then
            echo "使用方式: $0 validate <token>"
            exit 1
        fi
        if validate_token "$2"; then
            echo "Token 格式有效: $2"
            exit 0
        else
            echo "Token 格式無效: $2"
            exit 1
        fi
        ;;
    *)
        echo "使用方式: $0 {generate|current|validate <token>}"
        exit 1
        ;;
esac