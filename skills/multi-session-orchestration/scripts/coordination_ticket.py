#!/usr/bin/env python3
"""協調票解析：找出 active 版本中標記 `coordination: true` 且 `status: in_progress` 的票。

可 import（resolve_coordination_ticket），亦可 CLI：
    python3 coordination_ticket.py --json [--project-dir DIR] [--override 票號]

回傳 kind：ok／none／multiple／error，不靜默。覆寫來源依序為呼叫端傳入的票號、
`.claude/project-integration/multi-session.json` 的 `coordinationTicket`；
覆寫票已結案時加 warning 並退回自動解析。

todolist 以逐行 regex 解析而不用 PyYAML：執行環境（hook／statusline 的 python3）不保證裝有
第三方套件。代價是只認 2 格縮排 `  - version:` 與 4 格縮排 `    status:`；格式不符時
todolist 非空卻解析出 0 個版本，視為 error 並寫 stderr，不回 none。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

TODOLIST_RELATIVE_PATH = "docs/todolist.yaml"
CONFIG_RELATIVE_PATH = ".claude/project-integration/multi-session.json"
WORK_LOGS_DIR = "docs/work-logs"
CLOSED_STATUSES = frozenset({"completed", "closed"})
# 與 line-board hooks/shared.ts 的 TICKET_ID 同一規則。
TICKET_ID = re.compile(r"^(.+?)-(W\d+-)\d+(?:\.\d+)*$")
VERSION_LINE = re.compile(r'^  - version:\s*["\']?([^"\'\s#]+)')
STATUS_LINE = re.compile(r'^    status:\s*["\']?([^"\'\s#]+)')
WORKLOG_LINE = re.compile(r'^    worklog:\s*["\']?([^"\'#]+?)["\']?\s*$')


# 以下 U1 配對規則逐項對應 line-board hooks/userTodos.ts 的 parseUserTodos 與 lanes.ts 的
# solutionLines／unfencedSolutionLines；共用案例 user-todo-cases.json 防漂移。
SOLUTION_HEADING = "## Solution"
CODE_FENCE = "```"
TODO_LINE = re.compile(r"^\*\*用戶待辦(完成)?\*\*(?:（([^）]*)）)?：(.*)$")
KEY_PREFIX = "key:"
TEXT_KEY_PREFIX = "text:"


def unfenced_solution_lines(text: str) -> list:
    """Solution 段中不在 fenced code block 內的行（界線行本身去掉）。"""
    lines = [ln.rstrip() for ln in text.split("\n")]
    start = next(
        (i for i, ln in enumerate(lines) if ln == SOLUTION_HEADING or ln.startswith(SOLUTION_HEADING + " ")),
        -1,
    )
    if start == -1:
        return []
    rest = lines[start + 1:]
    end = next((i for i, ln in enumerate(rest) if ln.startswith("## ")), len(rest))
    result, in_fence = [], False
    for ln in rest[:end]:
        if ln.startswith(CODE_FENCE):
            in_fence = not in_fence
        elif not in_fence:
            result.append(ln)
    return result


def parse_user_todos(text: str) -> list:
    """未配對的用戶待辦（U1），依各鍵最後一次寫入待辦行的順序；回傳 [{"key": str|None, "item": str}]。

    帶鍵與不帶鍵分開配對；空括號行略過；完成行配不到待辦時不影響其他項。
    """
    pending = {}
    for line in unfenced_solution_lines(text):
        match = TODO_LINE.match(line)
        if match is None:
            continue
        key = None if match.group(2) is None else match.group(2).strip()
        content = match.group(3).strip()
        if key == "" or (key is None and content == ""):
            continue
        match_key = (TEXT_KEY_PREFIX + content) if key is None else (KEY_PREFIX + key)
        pending.pop(match_key, None)
        if match.group(1) is None:
            pending[match_key] = {"key": key, "item": content}
    return list(pending.values())


def _warn(message: str) -> None:
    sys.stderr.write(f"[coordination_ticket] {message}\n")


def ticket_file_candidates(ticket_id: str) -> list:
    """票號對應票檔路徑候選（相對專案根）：hierarchical 優先，再 flat；非票號為空。"""
    match = TICKET_ID.match(ticket_id)
    if match is None:
        return []
    version = match.group(1).lstrip("v")
    file = f"v{version}/tickets/{ticket_id}.md"
    flat = f"{WORK_LOGS_DIR}/{file}"
    parts = version.split(".")
    if len(parts) < 2:
        return [flat]
    major, minor = parts[0], parts[1]
    return [f"{WORK_LOGS_DIR}/v{major}/v{major}.{minor}/{file}", flat]


def resolve_ticket_file(ticket_id: str, project_dir: Path) -> Optional[Path]:
    candidates = [project_dir / c for c in ticket_file_candidates(ticket_id)]
    return next((c for c in candidates if c.exists()), candidates[0] if candidates else None)


def active_version_worklogs(todolist_text: str) -> list:
    """回傳 status=active 版本的 (版本, worklog 目錄) 清單。"""
    entries, current = [], None
    for line in todolist_text.split("\n"):
        version = VERSION_LINE.match(line)
        if version:
            current = {"version": version.group(1), "status": None, "worklog": None}
            entries.append(current)
            continue
        if current is None:
            continue
        status = STATUS_LINE.match(line)
        if status and current["status"] is None:
            current["status"] = status.group(1)
        worklog = WORKLOG_LINE.match(line)
        if worklog and current["worklog"] is None:
            current["worklog"] = worklog.group(1)
    return [(e["version"], e["worklog"]) for e in entries if e["status"] == "active"]


def read_frontmatter_fields(path: Path) -> dict:
    """只取 status 與 coordination 兩欄；無 frontmatter 或不可讀回傳空 dict。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _warn(f"略過無法讀取的票檔 {path}：{exc}")
        return {}
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = re.match(r"^(status|coordination):\s*(.*?)\s*$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip("'\"").lower()
    return fields


def scan_candidates(project_dir: Path, worklogs: list) -> list:
    """掃 active 版本票目錄，回傳 [{ticket, path}]（coordination 且 in_progress）。"""
    found = []
    for _version, worklog in worklogs:
        if not worklog:
            continue
        tickets_dir = project_dir / worklog / "tickets"
        for path in sorted(tickets_dir.glob("*.md")):
            fields = read_frontmatter_fields(path)
            if fields.get("coordination") == "true" and fields.get("status") == "in_progress":
                found.append({"ticket": path.stem, "path": str(path)})
    return found


def read_config_override(project_dir: Path) -> Optional[str]:
    """設定檔不存在視為無覆寫；存在但損壞寫 stderr 並視為無覆寫。"""
    config_path = project_dir / CONFIG_RELATIVE_PATH
    if not config_path.exists():
        return None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _warn(f"專案設定不可用 {config_path}：{exc}")
        return None
    value = config.get("coordinationTicket") if isinstance(config, dict) else None
    return value if isinstance(value, str) and value else None


def _result(kind: str, **extra) -> dict:
    base = {"kind": kind, "ticket": None, "path": None, "source": None,
            "warnings": [], "candidates": [], "reason": None}
    base.update(extra)
    return base


def _try_override(ticket_id: str, project_dir: Path, warnings: list) -> Optional[dict]:
    """覆寫票未結案回傳 ok 結果；已結案或不存在加 warning 回傳 None。"""
    path = resolve_ticket_file(ticket_id, project_dir)
    if path is None or not path.exists():
        warnings.append(f"覆寫的協調票 {ticket_id} 票檔不存在，改用自動解析")
        return None
    if read_frontmatter_fields(path).get("status") in CLOSED_STATUSES:
        warnings.append(f"覆寫的協調票 {ticket_id} 已結案，改用自動解析")
        return None
    return _result("ok", ticket=ticket_id, path=str(path), source="override", warnings=warnings)


def resolve_coordination_ticket(project_dir: Path, override: Optional[str] = None) -> dict:
    """解析現行協調票；回傳含 kind／ticket／path／source／warnings／candidates／reason 的 dict。"""
    warnings: list = []
    override_id = override or read_config_override(project_dir)
    if override_id:
        hit = _try_override(override_id, project_dir, warnings)
        if hit:
            return hit
    todolist = project_dir / TODOLIST_RELATIVE_PATH
    try:
        todolist_text = todolist.read_text(encoding="utf-8")
        worklogs = active_version_worklogs(todolist_text)
    except OSError as exc:
        _warn(f"todolist 不可用 {todolist}：{exc}")
        return _result("error", warnings=warnings, reason=f"todolist 不可用：{exc}")
    if todolist_text.strip() and not any(VERSION_LINE.match(ln) for ln in todolist_text.split("\n")):
        reason = f"todolist 非空但解析出 0 個版本（縮排或欄位格式不符）：{todolist}"
        _warn(reason)
        return _result("error", warnings=warnings, reason=reason)
    candidates = scan_candidates(project_dir, worklogs)
    if not candidates:
        return _result("none", warnings=warnings)
    if len(candidates) > 1:
        return _result("multiple", warnings=warnings, candidates=candidates)
    only = candidates[0]
    return _result("ok", ticket=only["ticket"], path=only["path"], source="auto", warnings=warnings)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="解析現行協調票")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    parser.add_argument("--project-dir", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    parser.add_argument("--override", default=None, help="覆寫票號")
    args = parser.parse_args(argv)
    result = resolve_coordination_ticket(Path(args.project_dir), args.override)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"{result['kind']} {result['ticket'] or ''}".strip())
    return 1 if result["kind"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
