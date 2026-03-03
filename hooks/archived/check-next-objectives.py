#!/usr/bin/env python3
"""
check-next-objectives.py
檢查中版本層級的 todolist.yaml 任務狀態
用於 smart-version-check 指令的第三階段檢查
"""

import os
import sys
import re
from pathlib import Path

def get_project_root():
    script_dir = Path(__file__).parent.absolute()
    return str(Path(script_dir).parent.parent)

def read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""

def main():
    project_root = get_project_root()
    todolist_file = Path(project_root) / "docs" / "todolist.yaml"
    pubspec_file = Path(project_root) / "pubspec.yaml"

    print("[START] 下一步目標分析開始...")

    # 檢查必要文件
    if not todolist_file.exists():
        print("[ERROR] 錯誤：找不到 todolist.yaml 檔案")
        return 1

    if not pubspec_file.exists():
        print("[ERROR] 錯誤：找不到 pubspec.yaml 檔案")
        return 1

    # 獲取當前版本
    pubspec_content = read_file(pubspec_file)
    version_match = re.search(r'version:\s*([^\s+]+)', pubspec_content)
    if not version_match:
        print("[ERROR] 無法從 pubspec.yaml 提取版本")
        return 1

    current_version = version_match.group(1).strip('"').strip("'")
    print(f"[INFO] 當前版本：{current_version}")

    # 提取版本系列
    version_series = "v" + current_version.rsplit('.', 1)[0] + ".x"
    print(f"[INFO] 版本系列：{version_series}")

    # 讀取 todolist.yaml
    todolist_content = read_file(todolist_file)

    # 分析版本系列狀態
    print("[STAT] 版本系列目標分析：")

    # 簡化分析：計算完成和待辦項目
    completed_items = todolist_content.count('[x]')
    pending_items = todolist_content.count('[ ]')

    print(f"[INFO] 已完成項目：{completed_items}")
    print(f"[INFO] 待辦項目：{pending_items}")

    # 檢查成功指標
    success_indicators_found = "成功指標" in todolist_content
    if success_indicators_found:
        print("[INFO] 發現成功指標區塊")

    # 檢查里程碑
    milestones_found = "里程碑" in todolist_content
    if milestones_found:
        print("[INFO] 發現里程碑檢查點")

    # 版本系列完成度評估
    print("[STAT] 版本系列完成度評估：")

    series_status = "UNKNOWN"
    if pending_items == 0 and completed_items > 0:
        series_status = "FULLY_COMPLETED"
        print("[OK] 版本系列狀態：完全完成")
    elif completed_items > 0:
        series_status = "MOSTLY_COMPLETED"
        print("[INFO] 版本系列狀態：基本完成")
    elif pending_items > 0:
        series_status = "IN_PROGRESS"
        print("[INFO] 版本系列狀態：進行中")
    else:
        series_status = "NOT_COMPLETED"
        print("[WARNING] 版本系列狀態：未完成")

    # 下一步建議
    print("[INFO] 下一步建議：")

    if series_status == "FULLY_COMPLETED":
        print("[OK] 建議：準備推進到下一個中版本系列")
        return 0
    elif series_status == "MOSTLY_COMPLETED":
        print("[INFO] 建議：完成收尾工作後推進中版本")
        return 1
    elif series_status == "IN_PROGRESS":
        print("[INFO] 建議：繼續當前版本系列開發")
        print(f"[WARNING] 版本系列 {version_series} 的目標尚未完全達成")
        return 2
    else:
        print("[WARNING] 建議：專注完成當前版本系列目標")
        return 3

if __name__ == "__main__":
    sys.exit(main())
