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
2. todolist.yaml 中是否有應該移除的已完成項目
3. error-patterns 最後更新時間
4. ticket 與 worklog 的一致性

輸出: 提醒訊息，不阻擋任何操作
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely, get_project_root
from lib.hook_messages import ValidationMessages


def get_latest_version() -> Optional[str]:
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
    """檢查 todolist.yaml 狀態"""
    project_root = get_project_root()
    todolist = project_root / "docs" / "todolist.yaml"

    result = {
        "exists": False,
        "has_pending_items": False,
        "pending_count": 0
    }

    if not todolist.exists():
        return result

    result["exists"] = True

    try:
        import yaml
        with open(todolist, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 檢查是否有 pending 或 active 狀態的項目
        tickets = data.get('tickets', [])
        for ticket in tickets:
            status = ticket.get('status')
            if status in ['pending', 'active']:
                result["has_pending_items"] = True
                result["pending_count"] += 1
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
    lines.append(ValidationMessages.DOC_SYNC_HEADER_FORMAT)
    lines.append(ValidationMessages.DOC_SYNC_TITLE)
    lines.append(ValidationMessages.DOC_SYNC_HEADER_FORMAT)
    lines.append("")

    # Worklog 狀態
    worklog = checks.get("worklog", {})
    if worklog.get("exists"):
        lines.append(ValidationMessages.DOC_SYNC_WORKLOG_EXISTS.format(version=checks.get('version', '?')))
        if worklog.get("has_main"):
            lines.append(ValidationMessages.DOC_SYNC_WORKLOG_MAIN_OK)
        else:
            lines.append(ValidationMessages.DOC_SYNC_WORKLOG_MAIN_WARN)
        if worklog.get("has_tickets"):
            lines.append(ValidationMessages.DOC_SYNC_WORKLOG_TICKETS.format(count=worklog.get('ticket_count', 0)))
    else:
        lines.append(ValidationMessages.DOC_SYNC_WORKLOG_NOT_EXISTS.format(version=checks.get('version', '?')))

    lines.append("")

    # Todolist 狀態
    todo = checks.get("todo", {})
    if todo.get("exists"):
        if todo.get("has_pending_items"):
            lines.append(ValidationMessages.DOC_SYNC_TODOLIST_EXISTS_PENDING.format(count=todo.get('pending_count', 0)))
        else:
            lines.append(ValidationMessages.DOC_SYNC_TODOLIST_EXISTS_NONE)
    else:
        lines.append(ValidationMessages.DOC_SYNC_TODOLIST_NOT_EXISTS)

    lines.append("")

    # Error Patterns 狀態
    error_patterns = checks.get("error_patterns", {})
    if error_patterns.get("exists"):
        lines.append(ValidationMessages.DOC_SYNC_ERROR_PATTERNS_EXISTS.format(count=error_patterns.get('category_count', 0)))
        if error_patterns.get("last_modified"):
            lines.append(ValidationMessages.DOC_SYNC_ERROR_PATTERNS_MODIFIED.format(time=error_patterns.get('last_modified')))
    else:
        lines.append(ValidationMessages.DOC_SYNC_ERROR_PATTERNS_NOT_EXISTS)

    lines.append("")

    # 提醒事項
    reminders = []
    if not worklog.get("exists"):
        reminders.append(ValidationMessages.DOC_SYNC_INIT_WORKLOG)
    if not todo.get("exists"):
        reminders.append(ValidationMessages.DOC_SYNC_CHECK_TODOLIST)

    if reminders:
        lines.append(ValidationMessages.DOC_SYNC_SUGGESTIONS_HEADER)
        for r in reminders:
            lines.append(f"   - {r}")
        lines.append("")

    lines.append(ValidationMessages.DOC_SYNC_HEADER_FORMAT)

    return "\n".join(lines)


def main():
    """主函數"""
    logger = setup_hook_logging("doc-sync-check-hook")
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

    # 輸出結果（SessionStart 格式：純文字提醒）
    print(reminder)
    logger.info("Doc-Flow 檢查完成")
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "doc-sync-check-hook"))
