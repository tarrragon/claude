#!/bin/bash

# 5w1h-compliance-hook.sh
# 5W1H 合規檢查 Hook - 監控對話是否遵循 5W1H 框架

# 設定路徑和日誌
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/.claude/hook-logs/5w1h-compliance-$(date +%Y%m%d_%H%M%S).log"
TOKEN_DIR="$PROJECT_ROOT/.claude/hook-logs/5w1h-tokens"
COMPLIANCE_LOG="$PROJECT_ROOT/.claude/hook-logs/5w1h-compliance.log"

# 確保日誌目錄存在
mkdir -p "$PROJECT_ROOT/.claude/hook-logs"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE" >> "$COMPLIANCE_LOG"
}

# 取得當前 Token
get_current_token() {
    local latest_token_file=$(ls -t "$TOKEN_DIR"/*.token 2>/dev/null | head -n 1)
    if [ -f "$latest_token_file" ]; then
        grep "^TOKEN=" "$latest_token_file" | cut -d'=' -f2
    else
        echo ""
    fi
}

# 檢查 Token 格式
validate_token_format() {
    local token="$1"
    if [[ "$token" =~ ^5W1H-[0-9]{8}-[0-9]{6}-[A-Za-z0-9]{6}$ ]]; then
        return 0
    else
        return 1
    fi
}

# 檢查回答是否包含 5W1H 分析
check_5w1h_analysis() {
    local content="$1"

    # 檢查是否包含 5W1H 要素
    local has_who=$(echo "$content" | grep -i "Who:" | wc -l)
    local has_what=$(echo "$content" | grep -i "What:" | wc -l)
    local has_when=$(echo "$content" | grep -i "When:" | wc -l)
    local has_where=$(echo "$content" | grep -i "Where:" | wc -l)
    local has_why=$(echo "$content" | grep -i "Why:" | wc -l)
    local has_how=$(echo "$content" | grep -i "How:" | wc -l)

    local total_elements=$((has_who + has_what + has_when + has_where + has_why + has_how))

    if [ $total_elements -ge 5 ]; then
        return 0  # 符合 5W1H 分析
    else
        return 1  # 不符合 5W1H 分析
    fi
}

# 檢查回答是否以正確 Token 開頭
check_token_compliance() {
    local response_content="$1"
    local current_token="$2"

    # 檢查是否以 🎯 和正確 Token 開頭
    if echo "$response_content" | head -n 3 | grep -q "🎯.*$current_token"; then
        return 0  # Token 合規
    else
        return 1  # Token 不合規
    fi
}

# 生成違規報告
generate_violation_report() {
    local violation_type="$1"
    local details="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    cat >> "$PROJECT_ROOT/.claude/hook-logs/5w1h-violations.log" << EOF
=== 5W1H 合規違規報告 ===
時間: $timestamp
違規類型: $violation_type
詳細說明: $details
當前 Token: $(get_current_token)
修復要求: 必須重新回答並遵循 5W1H 格式

EOF
}

# 主要檢查函數
main_compliance_check() {
    local response_content="$1"

    log "🔍 開始 5W1H 合規檢查"

    # 取得當前 Token
    CURRENT_TOKEN=$(get_current_token)
    if [ -z "$CURRENT_TOKEN" ]; then
        log "⚠️  無法取得當前 5W1H Token，可能需要重新啟動 Session"
        generate_violation_report "Token 缺失" "無法找到當前 Session 的 5W1H Token"
        return 1
    fi

    log "🔑 當前 Token: $CURRENT_TOKEN"

    # 檢查 Token 格式
    if ! validate_token_format "$CURRENT_TOKEN"; then
        log "❌ Token 格式無效: $CURRENT_TOKEN"
        generate_violation_report "Token 格式錯誤" "Token 不符合標準格式"
        return 1
    fi

    # 檢查回答是否以正確 Token 開頭
    if ! check_token_compliance "$response_content" "$CURRENT_TOKEN"; then
        log "❌ 回答未以正確 Token 開頭"
        log "📋 要求格式: 🎯 $CURRENT_TOKEN"
        generate_violation_report "Token 不合規" "回答未以正確的 5W1H Token 開頭"
        return 1
    fi

    log "✅ Token 合規檢查通過"

    # 檢查 5W1H 分析完整性
    if ! check_5w1h_analysis "$response_content"; then
        log "❌ 5W1H 分析不完整"
        log "📋 需要包含: Who, What, When, Where, Why, How"
        generate_violation_report "5W1H 分析不完整" "回答缺少足夠的 5W1H 要素分析"
        return 1
    fi

    log "✅ 5W1H 分析檢查通過"
    log "🎯 5W1H 合規檢查完成 - 全部通過"

    return 0
}

# 根據傳入的參數執行檢查
if [ "$1" = "check" ]; then
    if [ -z "$2" ]; then
        echo "使用方式: $0 check <response_content>"
        exit 1
    fi

    # 執行主要檢查
    if main_compliance_check "$2"; then
        echo "5W1H 合規檢查: 通過"
        exit 0
    else
        echo "5W1H 合規檢查: 違規"
        exit 1
    fi
else
    echo "使用方式: $0 check <response_content>"
    echo ""
    echo "功能:"
    echo "  - 檢查回答是否包含正確的 5W1H Token"
    echo "  - 驗證 5W1H 分析完整性"
    echo "  - 生成違規報告"
    exit 1
fi