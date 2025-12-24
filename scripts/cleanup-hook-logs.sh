#!/bin/bash

# cleanup-hook-logs.sh
# Hook日誌自動清理腳本 - 防止日誌無限累積
# 設計原則：保留近期必要日誌，清理過期檔案

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK_LOGS_DIR="$PROJECT_ROOT/.claude/hook-logs"

# 確保日誌目錄存在
mkdir -p "$HOOK_LOGS_DIR"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 清理策略函數
cleanup_hook_logs() {
    log "🧹 開始Hook日誌清理作業"

    # 統計清理前狀態
    local before_count=$(find "$HOOK_LOGS_DIR" -type f | wc -l)
    local before_size=$(du -sh "$HOOK_LOGS_DIR" 2>/dev/null | cut -f1)

    log "📊 清理前: $before_count 個檔案, $before_size"

    # 清理策略1: 刪除超過2小時的臨時日誌檔案
    find "$HOOK_LOGS_DIR" -name "*.log" -mmin +120 -delete 2>/dev/null

    # 清理策略2: 刪除超過4小時的問題追蹤檔案 (保留 issues-to-track.md)
    find "$HOOK_LOGS_DIR" -name "edit-issues-*.md" -mmin +240 -delete 2>/dev/null
    find "$HOOK_LOGS_DIR" -name "syntax-error-*.md" -mmin +240 -delete 2>/dev/null
    find "$HOOK_LOGS_DIR" -name "version-suggestion-*.md" -mmin +240 -delete 2>/dev/null

    # 清理策略3: 刪除超過24小時的所有時間戳檔案
    find "$HOOK_LOGS_DIR" -name "*202[0-9][0-9][0-9][0-9][0-9]_*" -mtime +1 -delete 2>/dev/null

    # 清理策略4: 保護重要檔案，確保不被誤刪
    # issues-to-track.md 是重要的問題追蹤檔案，永久保留

    # 統計清理後狀態
    local after_count=$(find "$HOOK_LOGS_DIR" -type f | wc -l)
    local after_size=$(du -sh "$HOOK_LOGS_DIR" 2>/dev/null | cut -f1)
    local cleaned_count=$((before_count - after_count))

    log "📊 清理後: $after_count 個檔案, $after_size"
    log "🎯 已清理: $cleaned_count 個檔案"

    # 如果檔案數量仍然過多，執行緊急清理
    if [ $after_count -gt 50 ]; then
        log "⚠️  檔案數量過多 ($after_count)，執行緊急清理"
        emergency_cleanup
    fi
}

# 緊急清理函數
emergency_cleanup() {
    log "🚨 執行緊急清理模式"

    # 僅保留最近30分鐘的檔案和重要檔案
    find "$HOOK_LOGS_DIR" -type f -not -name "issues-to-track.md" -mmin +30 -delete 2>/dev/null

    local final_count=$(find "$HOOK_LOGS_DIR" -type f | wc -l)
    log "🎯 緊急清理完成，剩餘檔案: $final_count"
}

# 檢查磁碟使用情況
check_disk_usage() {
    local dir_size=$(du -s "$HOOK_LOGS_DIR" 2>/dev/null | awk '{print $1}')

    # 如果超過5MB，執行強制清理
    if [ "$dir_size" -gt 5120 ]; then
        log "⚠️  Hook日誌目錄過大 (${dir_size}KB > 5MB)，執行強制清理"
        emergency_cleanup
    fi
}

# 主執行邏輯
main() {
    if [ ! -d "$HOOK_LOGS_DIR" ]; then
        log "📁 Hook日誌目錄不存在，無需清理"
        exit 0
    fi

    cleanup_hook_logs
    check_disk_usage

    log "✅ Hook日誌清理作業完成"
}

# 執行主函數
main "$@"