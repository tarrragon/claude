#!/bin/bash

# performance-monitor-hook.sh
# 通用 Hook: 監控 hook 執行時間並優化建議

# 設定路徑和日誌
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PERF_LOG_DIR="$PROJECT_ROOT/.claude/hook-logs/performance"
LOG_FILE="$PERF_LOG_DIR/perf-monitor-$(date +%Y%m%d).log"

# 確保效能日誌目錄存在
mkdir -p "$PERF_LOG_DIR"

# 日誌函數
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 獲取效能指標函數
get_performance_metrics() {
    local start_time=$1
    local end_time=$2
    local hook_name=$3

    local duration=$((end_time - start_time))
    local memory_usage=$(ps -o rss= -p $$ 2>/dev/null | tr -d ' ' || echo "0")

    # 記錄效能指標
    echo "$(date +%s),$hook_name,$duration,$memory_usage" >> "$PERF_LOG_DIR/metrics.csv"

    # 效能警示檢查
    if [ "$duration" -gt 5 ]; then
        log "⚠️  $hook_name 執行時間過長: ${duration}秒"
        return 1
    elif [ "$duration" -gt 2 ]; then
        log "💡 $hook_name 執行時間: ${duration}秒 (建議優化)"
        return 2
    else
        log "✅ $hook_name 執行時間: ${duration}秒 (正常)"
        return 0
    fi
}

# 分析效能趨勢
analyze_performance_trends() {
    local metrics_file="$PERF_LOG_DIR/metrics.csv"

    if [ ! -f "$metrics_file" ]; then
        log "📊 建立效能指標檔案"
        echo "timestamp,hook_name,duration_seconds,memory_kb" > "$metrics_file"
        return 0
    fi

    log "📈 分析效能趨勢"

    # 檢查今日的效能資料
    local today=$(date +%Y%m%d)
    local today_start=$(date -j -f "%Y%m%d" "$today" +%s 2>/dev/null || date -d "$today" +%s 2>/dev/null || echo "0")

    # 統計今日各 hook 的執行次數和平均時間
    awk -F',' -v start_time="$today_start" '
    NR > 1 && $1 >= start_time {
        count[$2]++
        total_time[$2] += $3
        if ($3 > max_time[$2]) max_time[$2] = $3
        if (min_time[$2] == 0 || $3 < min_time[$2]) min_time[$2] = $3
    }
    END {
        print "📊 今日 Hook 效能統計:"
        for (hook in count) {
            avg = total_time[hook] / count[hook]
            printf "  %s: %d次執行, 平均%.2f秒, 最大%.2f秒\n", hook, count[hook], avg, max_time[hook]
        }
    }' "$metrics_file" >> "$LOG_FILE"

    # 檢查是否有效能惡化趨勢
    local slow_hooks=$(awk -F',' -v start_time="$today_start" '
    NR > 1 && $1 >= start_time && $3 > 3 {
        count[$2]++
    }
    END {
        for (hook in count) {
            if (count[hook] >= 3) {
                print hook
            }
        }
    }' "$metrics_file")

    if [ -n "$slow_hooks" ]; then
        log "🚨 發現效能問題 Hook:"
        echo "$slow_hooks" | while read hook; do
            log "  - $hook (多次執行超過3秒)"
        done

        generate_optimization_report "$slow_hooks"
    fi
}

# 生成優化建議報告
generate_optimization_report() {
    local slow_hooks="$1"
    local report_file="$PERF_LOG_DIR/optimization-report-$(date +%Y%m%d_%H%M%S).md"

    log "📋 生成優化建議報告: $report_file"

    cat > "$report_file" << EOF
# 🚀 Hook 效能優化建議報告

**生成時間**: $(date)

## 🐌 發現的效能問題

EOF

    echo "$slow_hooks" | while read hook; do
        cat >> "$report_file" << EOF
### $hook

**問題**: 多次執行超過3秒閾值

**可能原因**:
- 大量檔案掃描操作
- 外部指令執行過慢
- 網路請求或資料庫查詢
- 沒有適當的快取機制

**優化建議**:
1. **檔案掃描優化**:
   \`\`\`bash
   # 使用 find 限制搜尋深度
   find src/ -maxdepth 3 -name "*.js"

   # 使用 grep 的 --include 選項
   grep -r --include="*.js" "pattern" src/
   \`\`\`

2. **快取機制**:
   \`\`\`bash
   # 建立快取檔案避免重複計算
   CACHE_FILE="/tmp/hook_cache_\${hook_name}.txt"
   if [ -f "\$CACHE_FILE" ] && [ \$((\$(date +%s) - \$(stat -f %m "\$CACHE_FILE"))) -lt 300 ]; then
       # 使用快取結果
       cat "\$CACHE_FILE"
   else
       # 執行計算並快取
       expensive_operation > "\$CACHE_FILE"
   fi
   \`\`\`

3. **平行處理**:
   \`\`\`bash
   # 使用背景處理加速
   for file in \$files; do
       process_file "\$file" &
   done
   wait  # 等待所有背景工作完成
   \`\`\`

4. **條件執行**:
   \`\`\`bash
   # 只在必要時執行耗時操作
   if [ "\$CHANGED_FILES_COUNT" -gt 10 ]; then
       # 大量變更才執行完整檢查
       full_analysis
   else
       # 少量變更執行快速檢查
       quick_analysis
   fi
   \`\`\`

EOF
    done

    cat >> "$report_file" << EOF

## 📊 效能基準

| Hook 類型 | 理想時間 | 警告閾值 | 錯誤閾值 |
|-----------|----------|----------|----------|
| SessionStart | < 1秒 | 2秒 | 5秒 |
| UserPromptSubmit | < 0.5秒 | 1秒 | 3秒 |
| PreToolUse | < 0.3秒 | 0.5秒 | 2秒 |
| PostToolUse | < 1秒 | 2秒 | 5秒 |
| Stop | < 0.5秒 | 1秒 | 3秒 |

## 🎯 最佳化策略

### 1. 檔案操作最佳化
- 使用 \`git diff --name-only\` 而非 \`git status --porcelain\`
- 限制搜尋範圍和深度
- 避免重複的檔案系統存取

### 2. 外部指令最佳化
- 使用 \`command -v\` 檢查指令存在性
- 重定向不需要的輸出到 \`/dev/null\`
- 設定合理的超時時間

### 3. 記憶體使用最佳化
- 避免載入大檔案到記憶體
- 使用管道處理大量資料
- 適當清理暫存變數

### 4. 並行執行策略
- 獨立的檢查可以平行執行
- 使用 \`&\` 和 \`wait\` 控制並行度
- 避免資源競爭

## 🔧 實施建議

1. **立即行動**: 修復超過5秒的 hooks
2. **短期目標**: 所有 hooks 執行時間 < 2秒
3. **長期目標**: 建立自動化效能回歸測試

EOF
}

# 主要執行邏輯
main() {
    # 如果被其他 hook 調用，記錄呼叫資訊
    if [ $# -eq 2 ]; then
        local hook_name="$1"
        local action="$2"  # start 或 end

        if [ "$action" = "start" ]; then
            echo "$(date +%s)" > "/tmp/hook_start_${hook_name}"
            log "⏱️  開始監控: $hook_name"
        elif [ "$action" = "end" ]; then
            local start_file="/tmp/hook_start_${hook_name}"
            if [ -f "$start_file" ]; then
                local start_time=$(cat "$start_file")
                local end_time=$(date +%s)
                get_performance_metrics "$start_time" "$end_time" "$hook_name"
                rm -f "$start_file"
            fi
        fi
    else
        # 獨立執行時，分析整體效能趨勢
        log "🚀 Performance Monitor Hook: 開始效能分析"
        analyze_performance_trends
    fi
}

# 清理舊的效能日誌 (保留7天)
cleanup_old_logs() {
    find "$PERF_LOG_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null

    # 保持 metrics.csv 在合理大小 (保留最近1000條記錄)
    local metrics_file="$PERF_LOG_DIR/metrics.csv"
    if [ -f "$metrics_file" ] && [ $(wc -l < "$metrics_file") -gt 1000 ]; then
        tail -n 1000 "$metrics_file" > "${metrics_file}.tmp"
        mv "${metrics_file}.tmp" "$metrics_file"
    fi
}

# 執行主邏輯
main "$@"

# 每天清理一次舊日誌
cleanup_old_logs

log "✅ Performance Monitor Hook 執行完成"
exit 0