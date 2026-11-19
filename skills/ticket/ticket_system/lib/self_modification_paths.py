"""自我修改類路徑判定（claim 授權提醒用）

where.files 命中三類路徑時，該票可能被 auto mode 分類器擋下：
  1. .claude/settings*.json
  2. .claude/agents/*.md
  3. .claude/hooks/ 或 .claude/skills/*/hooks/ 下，檔名含 guard 或 gate 的 .py

只做判定，不阻擋；`::read` 宣告（唯讀）不計入。
"""
import fnmatch
import posixpath
from typing import Any, Dict, List

_READ_SUFFIX = "::read"

REMINDER_TEXT = (
    "[提醒] where.files 含自我修改類路徑（{paths}）：此票可能被 auto mode "
    "分類器擋下，開工前先以 AskUserQuestion 向用戶取得授權。"
)


def _is_self_modification(path: str) -> bool:
    norm = posixpath.normpath(path)
    name = posixpath.basename(norm)
    if fnmatch.fnmatch(norm, ".claude/settings*.json"):
        return True
    if fnmatch.fnmatch(norm, ".claude/agents/*.md"):
        return True
    in_hooks_dir = fnmatch.fnmatch(norm, ".claude/hooks/*") or fnmatch.fnmatch(
        norm, ".claude/skills/*/hooks/*"
    )
    lowered = name.lower()
    return (
        in_hooks_dir
        and lowered.endswith(".py")
        and ("guard" in lowered or "gate" in lowered)
    )


def find_self_modification_paths(ticket: Dict[str, Any]) -> List[str]:
    """回傳 where.files 中命中三類路徑的寫入宣告（排除 ::read）。"""
    where = ticket.get("where")
    files = (where.get("files") or []) if isinstance(where, dict) else []
    hits: List[str] = []
    for entry in files:
        if not isinstance(entry, str) or entry.endswith(_READ_SUFFIX):
            continue
        path = entry.split("::", 1)[0].strip()
        if _is_self_modification(path):
            hits.append(path)
    return hits


def format_reminder(paths: List[str]) -> str:
    return REMINDER_TEXT.format(paths=", ".join(paths))
