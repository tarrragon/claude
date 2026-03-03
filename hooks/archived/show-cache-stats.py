#!/usr/bin/env python3
"""
show-cache-stats.py - Ticket Quality Gate 快取統計查詢腳本
"""

import json
import sys
from pathlib import Path

def get_project_root():
    """定位專案根目錄"""
    current_dir = Path.cwd()
    while current_dir != current_dir.parent:
        if (current_dir / "CLAUDE.md").exists():
            return current_dir
        current_dir = current_dir.parent

    print("[ERROR] 無法定位專案根目錄")
    return None

def main():
    project_root = get_project_root()
    if not project_root:
        return 1

    cache_stats_file = project_root / ".claude" / "hook-logs" / "ticket-quality-gate" / "cache" / "cache_stats.json"

    print("[STAT] Ticket Quality Gate 快取統計")
    print("=" * 32)
    print()

    if not cache_stats_file.exists():
        print("[ERROR] 無快取統計資料")
        print()
        print("快取統計將在首次執行 Ticket Quality Gate Hook 後開始記錄。")
        return 0

    try:
        with open(cache_stats_file, 'r', encoding='utf-8') as f:
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
        print()
        print(f"快取命中平均時間: {with_cache:.3f}s")
        print(f"快取未命中平均時間: {without_cache:.3f}s")
        print(f"效能提升: {speedup:.1f}x")
        print()

        # 效能評級
        if hit_rate >= 70:
            print("[OK] 效能評級: 優秀（命中率 > 70%）")
        elif hit_rate >= 50:
            print("[INFO] 效能評級: 良好（命中率 50-70%）")
        else:
            print("[WARNING] 效能評級: 需改善（命中率 < 50%）")

        print()
        print(f"版本: {stats.get('version', 'unknown')}")
        print(f"最後更新: {stats.get('last_updated', 'N/A')}")
        print()
        print("---")
        print(f"統計檔案位置: {cache_stats_file}")

        return 0

    except Exception as e:
        print(f"[ERROR] 讀取統計資料失敗: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
