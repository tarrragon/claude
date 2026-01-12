#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Doc-Flow 五重文件同步檢查 Hook

觸發時機: SessionStart
模式: 提醒為主（不阻擋操作）

檢查項目:
1. 當前版本的 worklog 是否存在
2. todo.md 中是否有應該移除的已完成項目
3. error-patterns 最後更新時間
4. ticket 與 worklog 的一致性

輸出: 提醒訊息，不阻擋任何操作
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    """獲取專案根目錄"""
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")).resolve()


def get_latest_version() -> str | None:
    """從 work-logs 目錄取得最新版本號"""
    project_root = get_project_root()
    work_logs = project_root / "docs" / "work-logs"

    if not work_logs.exists():
        return None

    versions = []
    for item in work_logs.iterdir():
        if item.is_dir() and item.name.startswith("v"):
            versions.append(item.name)

    if not versions:
        return None

    # 簡單排序，取最新
    versions.sort(reverse=True)
    return versions[0].lstrip("v")


def check_worklog_exists(version: str) -> dict:
    """檢查 worklog 是否存在"""
    project_root = get_project_root()
    worklog_dir = project_root / "docs" / "work-logs" / f"v{version}"

    result = {
        "exists": False,
        "has_main": False,
        "has_tickets": False,
        "ticket_count": 0
    }

    if worklog_dir.exists():
        result["exists"] = True

        # 檢查主工作日誌
        main_files = list(worklog_dir.glob(f"v{version}*.md"))
        result["has_main"] = len(main_files) > 0

        # 檢查 tickets 目錄
        tickets_dir = worklog_dir / "tickets"
        if tickets_dir.exists():
            result["has_tickets"] = True
            result["ticket_count"] = len(list(tickets_dir.glob("*.md")))

    return result


def check_todolist() -> dict:
    """檢查 todo.md 狀態"""
    project_root = get_project_root()
    todolist = project_root / "docs" / "todolist.md"

    result = {
        "exists": False,
        "has_completed_items": False,
        "completed_count": 0
    }

    if not todolist.exists():
        return result

    result["exists"] = True

    try:
        content = todolist.read_text(encoding="utf-8")

        # 簡單檢查是否有「已完成」標記但還在清單中的項目
        completed_markers = ["✅ 已完成", "[x]", "已完成"]
        for marker in completed_markers:
            if marker.lower() in content.lower():
                result["has_completed_items"] = True
                result["completed_count"] += content.lower().count(marker.lower())
    except Exception:
        pass

    return result


def check_error_patterns() -> dict:
    """檢查 error-patterns 狀態"""
    project_root = get_project_root()
    error_patterns = project_root / "docs" / "error-patterns"

    result = {
        "exists": False,
        "category_count": 0,
        "last_modified": None
    }

    if not error_patterns.exists():
        return result

    result["exists"] = True

    categories_dir = error_patterns / "categories"
    if categories_dir.exists():
        result["category_count"] = len(list(categories_dir.glob("*.md")))

    # 找最後修改時間
    latest_mtime = 0
    for md_file in error_patterns.rglob("*.md"):
        mtime = md_file.stat().st_mtime
        if mtime > latest_mtime:
            latest_mtime = mtime

    if latest_mtime > 0:
        result["last_modified"] = datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M")

    return result


def generate_reminder(checks: dict) -> str:
    """生成提醒訊息"""
    lines = []
    lines.append("=" * 60)
    lines.append("[Doc-Flow] 五重文件系統狀態檢查")
    lines.append("=" * 60)
    lines.append("")

    # Worklog 狀態
    worklog = checks.get("worklog", {})
    if worklog.get("exists"):
        lines.append(f"[worklog] (v{checks.get('version', '?')}): OK - 存在")
        if worklog.get("has_main"):
            lines.append(f"   主工作日誌: OK")
        else:
            lines.append(f"   主工作日誌: WARN - 未找到")
        if worklog.get("has_tickets"):
            lines.append(f"   Tickets: {worklog.get('ticket_count', 0)} 個")
    else:
        lines.append(f"[worklog] (v{checks.get('version', '?')}): WARN - 目錄不存在")

    lines.append("")

    # Todo 狀態
    todo = checks.get("todo", {})
    if todo.get("exists"):
        if todo.get("has_completed_items"):
            lines.append(f"[todo.md]: WARN - 發現已完成項目 (建議移除)")
        else:
            lines.append(f"[todo.md]: OK - 正常")
    else:
        lines.append(f"[todo.md]: WARN - 不存在")

    lines.append("")

    # Error Patterns 狀態
    error_patterns = checks.get("error_patterns", {})
    if error_patterns.get("exists"):
        lines.append(f"[error-patterns]: OK - {error_patterns.get('category_count', 0)} 個分類")
        if error_patterns.get("last_modified"):
            lines.append(f"   最後更新: {error_patterns.get('last_modified')}")
    else:
        lines.append(f"[error-patterns]: WARN - 不存在")

    lines.append("")

    # 提醒事項
    reminders = []
    if not worklog.get("exists"):
        reminders.append("建議執行 /doc-flow worklog init 初始化版本日誌")
    if todo.get("has_completed_items"):
        reminders.append("建議執行 /doc-flow todo resolve 移除已完成項目")

    if reminders:
        lines.append("[建議操作]:")
        for r in reminders:
            lines.append(f"   - {r}")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """主函數"""
    # 讀取 hook 輸入
    try:
        hook_input = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        hook_input = {}

    # 獲取當前版本
    version = get_latest_version() or "0.0.0"

    # 執行檢查
    checks = {
        "version": version,
        "worklog": check_worklog_exists(version),
        "todo": check_todolist(),
        "error_patterns": check_error_patterns()
    }

    # 生成提醒訊息
    reminder = generate_reminder(checks)

    # 輸出結果（提醒模式，永遠 allow）
    result = {
        "decision": "allow",
        "reason": reminder
    }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
