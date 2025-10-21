#!/bin/bash
#
# Ticket Quality Gate - 快取統計查詢腳本
#
# 使用方式:
#   ./show-cache-stats.sh
#

set -euo pipefail

# 定位專案根目錄
get_project_root() {
    local current_dir="$PWD"
    while [[ "$current_dir" != "/" ]]; do
        if [[ -f "$current_dir/CLAUDE.md" ]]; then
            echo "$current_dir"
            return 0
        fi
        current_dir="$(dirname "$current_dir")"
    done
    echo "錯誤: 找不到 CLAUDE.md" >&2
    return 1
}

# 設定專案環境
PROJECT_ROOT="$(get_project_root)"
if [[ -z "$PROJECT_ROOT" ]]; then
    echo "❌ 無法定位專案根目錄" >&2
    exit 1
fi

CACHE_DIR="$PROJECT_ROOT/.claude/hook-logs/ticket-quality-gate/cache"
STATS_FILE="$CACHE_DIR/cache_stats.json"

# 檢查統計檔案是否存在
if [ ! -f "$STATS_FILE" ]; then
    echo "📊 Ticket Quality Gate 快取統計"
    echo "================================"
    echo ""
    echo "❌ 無快取統計資料"
    echo ""
    echo "快取統計將在首次執行 Ticket Quality Gate Hook 後開始記錄。"
    exit 0
fi

echo "📊 Ticket Quality Gate 快取統計"
echo "================================"
echo ""

# 使用 Python 格式化輸出（確保正確解析 JSON）
python3 << EOF
import json
import sys

try:
    with open('$STATS_FILE', 'r', encoding='utf-8') as f:
        stats = json.load(f)

    total = stats.get('total_checks', 0)
    hits = stats.get('cache_hits', 0)
    misses = stats.get('cache_misses', 0)
    hit_rate = (hits / total * 100) if total > 0 else 0

    with_cache = stats.get('avg_execution_time_with_cache', 0)
    without_cache = stats.get('avg_execution_time_without_cache', 0)
    speedup = (without_cache / with_cache) if with_cache > 0 else 1.0

    print(f"總檢測次數: {total:,}")
    print(f"快取命中: {hits:,} ({hit_rate:.1f}%)")
    print(f"快取未命中: {misses:,} ({100 - hit_rate:.1f}%)")
    print("")
    print(f"快取命中平均時間: {with_cache:.3f}s")
    print(f"快取未命中平均時間: {without_cache:.3f}s")
    print(f"效能提升: {speedup:.1f}x")
    print("")

    # 效能評級
    if hit_rate >= 70:
        print("效能評級: ✅ 優秀（命中率 > 70%）")
    elif hit_rate >= 50:
        print("效能評級: 🟡 良好（命中率 50-70%）")
    else:
        print("效能評級: 🔴 需改善（命中率 < 50%）")

    print("")
    print(f"版本: {stats.get('version', 'unknown')}")
    print(f"最後更新: {stats.get('last_updated', 'N/A')}")

except Exception as e:
    print(f"❌ 讀取統計資料失敗: {e}", file=sys.stderr)
    sys.exit(1)
EOF

echo ""
echo "---"
echo "統計檔案位置: $STATS_FILE"
