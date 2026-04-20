#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
File Size Guardian Hook - 過大檔案掃描

觸發時機: SessionStart
模式: 提醒為主（不阻擋操作）

掃描 .claude/ 和 src/ 目錄中的檔案行數，
找出超過閾值的檔案並輸出警告。

核心理念：行數超標是症狀，domain 混合是病因。
回合耗盡 = 認知負擔過載的具體訊號。

來源: PC-042
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely, get_project_root

# 閾值設定
RULE_FILE_WARN = 200       # 規則/文件檔案警戒值
RULE_FILE_CRITICAL = 300   # 規則/文件檔案必須拆分值
CODE_FILE_WARN = 300       # 程式碼檔案警戒值
CODE_FILE_CRITICAL = 500   # 程式碼檔案必須拆分值

# 掃描路徑和對應閾值
SCAN_CONFIG = [
    # (路徑 pattern, 副檔名, 警戒值, 拆分值, 類型標籤)
    (".claude/pm-rules", ".md", RULE_FILE_WARN, RULE_FILE_CRITICAL, "PM 規則"),
    (".claude/rules", ".md", RULE_FILE_WARN, RULE_FILE_CRITICAL, "品質規則"),
    (".claude/references", ".md", RULE_FILE_WARN, RULE_FILE_CRITICAL, "參考文件"),
]

# 排除的檔案名稱（不需要檢查的大檔案）
EXCLUDE_FILES = {
    "CHANGELOG.md",
    "README.md",
}


def count_lines(file_path: Path) -> int:
    """計算檔案行數"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except (OSError, UnicodeDecodeError):
        return 0


def scan_directory(root: Path, rel_dir: str, ext: str, warn: int, critical: int, label: str) -> tuple[list, list]:
    """掃描目錄，回傳 (warnings, criticals)"""
    warnings = []
    criticals = []
    scan_path = root / rel_dir

    if not scan_path.exists():
        return warnings, criticals

    for file_path in scan_path.rglob(f"*{ext}"):
        if file_path.name in EXCLUDE_FILES:
            continue
        if "__pycache__" in str(file_path):
            continue

        lines = count_lines(file_path)
        rel = file_path.relative_to(root)

        if lines > critical:
            criticals.append((str(rel), lines, label))
        elif lines > warn:
            warnings.append((str(rel), lines, label))

    return warnings, criticals


def main():
    logger = setup_hook_logging("file-size-guardian")
    root = get_project_root()

    if not root:
        return

    root = Path(root)
    all_warnings = []
    all_criticals = []

    for rel_dir, ext, warn, critical, label in SCAN_CONFIG:
        w, c = scan_directory(root, rel_dir, ext, warn, critical, label)
        all_warnings.extend(w)
        all_criticals.extend(c)

    # 只在有超標檔案時輸出
    if not all_criticals and not all_warnings:
        return

    verbose = os.environ.get("FILE_SIZE_GUARDIAN_VERBOSE") == "1"
    log_path = root / ".claude" / "hook-logs" / "file-size-guardian.log"
    sorted_criticals = sorted(all_criticals, key=lambda x: -x[1])
    sorted_warnings = sorted(all_warnings, key=lambda x: -x[1])

    _write_full_report(log_path, sorted_criticals, sorted_warnings)

    print("============================================================")
    print("[File Size Guardian] 檔案體量掃描")
    print("============================================================")

    if verbose:
        _print_full(sorted_criticals, sorted_warnings)
    else:
        _print_summary(sorted_criticals, sorted_warnings, log_path)

    print("============================================================")


def _print_summary(criticals: list, warnings: list, log_path: Path) -> None:
    """精簡模式: 統計 + Top 3 critical"""
    print(f"超標 {len(criticals)} 個 / 警戒 {len(warnings)} 個")
    if criticals:
        print(f"\nTop 3 超標檔案 (閾值 {RULE_FILE_CRITICAL}):")
        for path, lines, label in criticals[:3]:
            print(f"  {path}: {lines} 行 ({label})")
    print(f"\n完整清單: {log_path.relative_to(log_path.parents[2])}")
    print("(設定 FILE_SIZE_GUARDIAN_VERBOSE=1 還原完整輸出)")


def _print_full(criticals: list, warnings: list) -> None:
    """Verbose 模式: 完整清單"""
    if criticals:
        print()
        print(f"[WARNING] {len(criticals)} 個檔案超過拆分閾值：")
        for path, lines, label in criticals:
            print(f"  {path}: {lines} 行 ({label}, 閾值 {RULE_FILE_CRITICAL})")
        print()
        print("  建議：分析 domain 邊界，考慮拆分為獨立檔案")
        print("  理念：行數超標是症狀，domain 混合是病因")
    if warnings:
        print()
        print(f"[INFO] {len(warnings)} 個檔案接近警戒值：")
        for path, lines, label in warnings:
            print(f"  {path}: {lines} 行 ({label}, 警戒 {RULE_FILE_WARN})")
    print()


def _write_full_report(log_path: Path, criticals: list, warnings: list) -> None:
    """完整清單寫入日誌檔（每次 SessionStart 覆蓋）"""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"# File Size Guardian Report\n")
            f.write(f"# Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
            f.write(f"## 超標檔案 ({len(criticals)})\n\n")
            for path, lines, label in criticals:
                f.write(f"- {path}: {lines} 行 ({label}, 閾值 {RULE_FILE_CRITICAL})\n")
            f.write(f"\n## 警戒檔案 ({len(warnings)})\n\n")
            for path, lines, label in warnings:
                f.write(f"- {path}: {lines} 行 ({label}, 警戒 {RULE_FILE_WARN})\n")
    except OSError:
        pass


if __name__ == "__main__":
    run_hook_safely(main, "file-size-guardian")
