"""建票後列出 where.files 與未完成票重疊者（查重提示，不阻擋）。

比對範圍：todolist 中 active 與 planned 版本的 pending／in_progress 票，
排除新票自身。無交集不輸出；任何例外寫 stderr 後放行。
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

from ticket_system.lib.constants import STATUS_IN_PROGRESS, STATUS_PENDING

SCAN_VERSION_STATUSES = ("active", "planned")


def _scan_versions() -> List[str]:
    """todolist 中 active／planned 的版本（不含 v 前綴）。"""
    import yaml

    from ticket_system.lib.paths import get_project_root

    path = get_project_root() / "docs" / "todolist.yaml"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return [
        str(v["version"])
        for v in data.get("versions", [])
        if v.get("status") in SCAN_VERSION_STATUSES
    ]


def _ticket_files(ticket: Dict[str, Any]) -> List[str]:
    where = ticket.get("where")
    files = where.get("files") if isinstance(where, dict) else None
    return [str(f) for f in (files or [])]


def find_overlapping_tickets(
    new_ticket_id: str,
    new_files: List[str],
    versions: List[str],
    list_tickets_fn,
) -> List[Dict[str, Any]]:
    """回傳 [{id, title, files}]：未完成且 where.files 與 new_files 有交集的票。"""
    wanted = set(new_files)
    found: List[Dict[str, Any]] = []
    if not wanted:
        return found
    for version in versions:
        for ticket in list_tickets_fn(version) or []:
            if ticket.get("id") == new_ticket_id:
                continue
            if ticket.get("status") not in (STATUS_PENDING, STATUS_IN_PROGRESS):
                continue
            shared = sorted(wanted.intersection(_ticket_files(ticket)))
            if shared:
                found.append({
                    "id": ticket.get("id"),
                    "title": ticket.get("title") or ticket.get("what") or "",
                    "files": shared,
                })
    return found


def format_overlap_hint(overlaps: List[Dict[str, Any]]) -> str:
    """無重疊回傳空字串。"""
    if not overlaps:
        return ""
    lines = ["", "  → where.files 與未完成票重疊（請確認是否重複）："]
    for item in overlaps:
        lines.append(f"    {item['id']}  {item['title']}")
        lines.append(f"      重疊檔案：{', '.join(item['files'])}")
    return "\n".join(lines)


def print_where_overlap_hint(
    new_ticket_id: str, new_files: Optional[List[str]]
) -> None:
    """建票後的重疊提示；例外寫 stderr 後放行。"""
    try:
        from ticket_system.lib.ticket_loader import list_tickets

        overlaps = find_overlapping_tickets(
            new_ticket_id, list(new_files or []), _scan_versions(), list_tickets
        )
        text = format_overlap_hint(overlaps)
        if text:
            print(text)
    except Exception as err:
        sys.stderr.write(
            f"[where_overlap] WARNING: where.files 重疊比對失敗（{err}），略過\n"
        )
