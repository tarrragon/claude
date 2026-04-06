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

來源: PC-042, 0.17.2-W3-009
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

    print("============================================================")
    print("[File Size Guardian] 檔案體量掃描結果")
    print("============================================================")

    if all_criticals:
        print()
        print(f"[WARNING] {len(all_criticals)} 個檔案超過拆分閾值：")
        for path, lines, label in sorted(all_criticals, key=lambda x: -x[1]):
            print(f"  {path}: {lines} 行 ({label}, 閾值 {RULE_FILE_CRITICAL})")
        print()
        print("  建議：分析 domain 邊界，考慮拆分為獨立檔案")
        print("  理念：行數超標是症狀，domain 混合是病因")

    if all_warnings:
        print()
        print(f"[INFO] {len(all_warnings)} 個檔案接近警戒值：")
        for path, lines, label in sorted(all_warnings, key=lambda x: -x[1]):
            print(f"  {path}: {lines} 行 ({label}, 警戒 {RULE_FILE_WARN})")

    print()
    print("============================================================")


if __name__ == "__main__":
    run_hook_safely(main, "file-size-guardian")
