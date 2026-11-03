#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
coordination-queue-line-check-hook - PostToolUse Hook（Bash / Edit / Write / MultiEdit）

目的: 協調票（票本身 frontmatter 有 `coordination: true`）被寫入後，從磁碟重讀票檔，
      檢查現行佇列行的兩種寫法錯誤，以 additionalContext 提示模型（不阻擋，exit 0）。
      文字約定兩度失守，故由機械層在寫入當下指出。

檢查（解析規則照 .claude/skills/line-board/hooks/lanes.ts：行首、只掃 Solution、每線取最後一行）:
  1. 作用中（票序不是（無））且有括號的線，括號內文不等於任何存活 session 名稱
     （~/.claude/sessions/*.json，cwd 屬本 repo 任一 checkout）-> 提示兩種可能原因
  2. 票序票號全部可解析且狀態皆 completed/closed，卻未寫（無）-> 提示可結束，附完整格式
  3. 以「**L<n> 現行佇列**」開頭卻不符 LANE_LINE 的行（如漏冒號），若在該線最後一筆合格行之後
     -> 報出原文與格式；解析層照 lanes.ts 不採用此行，不報會被誤以為已寫入

  4. 未配對的用戶待辦（U1，規則同 line-board userTodos.ts parseUserTodos，Python 版在
     multi-session-orchestration/scripts/coordination_ticket.py）數大於 0 -> 列鍵、事項與完成行格式；為 0 不輸出

受眾: 模型 -> emit_model_reminder("PostToolUse", ...)。被寫入的票不帶標記時不輸出。
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (  # noqa: E402
    emit_model_reminder,
    get_project_root,
    read_json_from_stdin,
    run_hook_safely,
    setup_hook_logging,
)

sys.path.insert(
    0, str(Path(__file__).parent.parent / "skills" / "multi-session-orchestration" / "scripts")
)
from coordination_ticket import parse_user_todos  # noqa: E402

HOOK_NAME = "coordination-queue-line-check"
TICKET_ID_IN_TEXT = re.compile(r"(?<![\w.-])(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)(?![\w.-])")
LANE_ENDED = "（無）"
TERMINAL_STATUSES = ("completed", "closed")
WRITE_TOOLS = ("Edit", "Write", "MultiEdit")
# 檢查 4 的完成行格式（line-continuity.md §2〈用戶待辦〉）
TODO_DONE_FORMAT = "**用戶待辦完成**（%s）：<結果>"
TODO_DONE_KEYLESS = "**用戶待辦完成**：%s"

# 以下常數與解析函式逐項對應 lanes.ts / shared.ts
LANE_LINE = re.compile(r"^\*\*L(\d+) 現行佇列\*\*(?:（([^）]*)）)?：(.*)$")
LANE_LINE_PREFIX = re.compile(r"^\*\*L(\d+) 現行佇列\*\*")
LANE_FORMAT = "**L%d 現行佇列**（<session 名稱>）：<票序，或（無）>"
QUEUE_SEPARATOR = re.compile(r"\s*(→|∥)\s*")
STEP_SERIAL = re.compile(r"^(\d{3}(?:\.\d+)*)(.*)$")
STEP_FULL_ID = re.compile(r"^(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)(.*)$")
STEP_WAVE_ID = re.compile(r"^(W\d+-\d+(?:\.\d+)*)(.*)$")
PREFIX_VERSION = re.compile(r"^(.+)-W\d+-$")
TICKET_ID = re.compile(r"^v?(\d+\.\d+\.\d+)-(W\d+)-\d+(?:\.\d+)*$")


def ticket_prefix_of(coordinator_id: str) -> Optional[str]:
    m = TICKET_ID.match(coordinator_id)
    return None if m is None else "%s-%s-" % (m.group(1), m.group(2))


def _step_ticket(part: str, prefix: str):
    full = STEP_FULL_ID.match(part)
    if full:
        return full.group(1), full.group(1), full.group(2)
    wave = STEP_WAVE_ID.match(part)
    if wave:
        ver = PREFIX_VERSION.match(prefix)
        if ver is None:
            return None
        return wave.group(1), "%s-%s" % (ver.group(1), wave.group(1)), wave.group(2)
    short = STEP_SERIAL.match(part)
    if short:
        return short.group(1), prefix + short.group(1), short.group(2)
    return None


def parse_queue(queue: str, prefix: str) -> List[Dict[str, str]]:
    """票序拆成票號 token（分隔符與無法辨識文字略過，共用案例只列 ticket token）。"""
    tickets = []
    for part in QUEUE_SEPARATOR.split(queue.strip()):
        if part in ("", "→", "∥"):
            continue
        t = _step_ticket(part, prefix)
        if t is not None:
            tickets.append({"serial": t[0], "id": t[1], "note": t[2].strip()})
    return tickets


def solution_lines(text: str) -> List[str]:
    lines = [ln.rstrip() for ln in text.split("\n")]
    start = next(
        (i for i, ln in enumerate(lines) if ln == "## Solution" or ln.startswith("## Solution ")),
        -1,
    )
    if start == -1:
        return []
    rest = lines[start + 1:]
    for i, ln in enumerate(rest):
        if ln.startswith("## "):
            return rest[:i]
    return rest


def parse_lanes(text: str, prefix: str) -> List[Dict[str, object]]:
    """每線取最後一次出現的現行佇列行；票序為（無）的線不回傳。依線號排序。"""
    latest = {}
    for line in solution_lines(text):
        m = LANE_LINE.match(line)
        if m:
            latest[int(m.group(1))] = (m.group(2), m.group(3).strip())
    return [
        {"lane": lane, "session": session, "tickets": parse_queue(queue, prefix)}
        for lane, (session, queue) in sorted(latest.items())
        if queue != LANE_ENDED
    ]


def ticket_file_candidates(ticket_id: str) -> List[str]:
    m = TICKET_ID.match(ticket_id)
    if m is None:
        return []
    version = m.group(1)
    flat = "docs/work-logs/v%s/tickets/%s.md" % (version, ticket_id)
    major, minor = version.split(".")[:2]
    return ["docs/work-logs/v%s/v%s.%s/v%s/tickets/%s.md" % (major, major, minor, version, ticket_id), flat]


def read_ticket_status(root: Path, ticket_id: str) -> Optional[str]:
    for rel in ticket_file_candidates(ticket_id):
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except OSError:
            # 候選路徑逐一試讀，找不到即試下一個；全部失敗回傳 None，視為非終態，不誤報（規則 4／IMP-013）
            continue
        m = re.search(r"^status:\s*(\S+)", text, re.M)
        return m.group(1).strip("'\"") if m else None
    return None


def find_problems(lanes, alive_names: Optional[set], status_of) -> List[str]:
    """alive_names 為 None 表示無法取得 session 名單，略過檢查 1。status_of(id)->Optional[str]。"""
    msgs = []
    for lane in lanes:
        n, session, tickets = lane["lane"], lane["session"], lane["tickets"]
        if session is not None and alive_names is not None and session not in alive_names:
            msgs.append(
                "L%d 括號內『%s』目前沒有同名 session：若是附註，請移到票序；"
                "若 session 已結束而線仍在，可忽略" % (n, session)
            )
        if tickets:
            statuses = [status_of(t["id"]) for t in tickets]
            if all(s in TERMINAL_STATUSES for s in statuses):
                msgs.append(
                    "L%d 佇列票皆已終態，若線已結束請寫（無），格式：%s" % (n, LANE_FORMAT % n)
                )
    return msgs


def find_malformed_lines(text: str) -> List[str]:
    """檢查 3：每線最後一筆合格行之後，仍以佇列行開頭卻不合格的行（解析層會忽略它）。"""
    pending = {}
    for line in solution_lines(text):
        head = LANE_LINE_PREFIX.match(line)
        if head is None:
            continue
        n = int(head.group(1))
        if LANE_LINE.match(line):
            pending.pop(n, None)
        else:
            pending.setdefault(n, []).append(line)
    return [
        "L%d 有一行佇列行格式不符，未被採用：『%s』；格式：%s" % (n, line, LANE_FORMAT % n)
        for n in sorted(pending)
        for line in pending[n]
    ]


def find_unpaired_todos(text: str) -> List[str]:
    """檢查 4：未配對的用戶待辦（U1）。數量為 0 時不輸出；否則列各鍵、事項與完成行格式。"""
    todos = parse_user_todos(text)
    if not todos:
        return []
    lines = ["尚有 %d 項用戶待辦未寫完成行（已處理的請補完成行，未處理的忽略）：" % len(todos)]
    for todo in todos:
        key = todo["key"]
        if key is None:
            lines.append("- （不帶鍵）%s -> %s" % (todo["item"], TODO_DONE_KEYLESS % todo["item"]))
        else:
            lines.append("- %s：%s -> %s" % (key, todo["item"], TODO_DONE_FORMAT % key))
    return ["\n".join(lines)]


def alive_session_names(logger, checkouts: List[str]) -> Optional[set]:
    sessions_dir = Path(os.environ.get("HOME", "")) / ".claude" / "sessions"
    if not sessions_dir.is_dir():
        logger.info("sessions 目錄不存在，略過檢查 1: %s", sessions_dir)
        return None
    names = set()
    for f in sessions_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.info("session 檔讀取失敗略過 %s: %s", f.name, e)
            continue
        cwd, name = d.get("cwd"), d.get("name")
        if isinstance(cwd, str) and isinstance(name, str) and any(
            cwd == c or cwd.startswith(c + "/") for c in checkouts
        ):
            names.add(name)
    return names


def list_checkouts(logger, root: Path) -> List[str]:
    import subprocess

    try:
        r = subprocess.run(
            ["git", "-C", str(root), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        )
        paths = [ln[9:].strip() for ln in r.stdout.split("\n") if ln.startswith("worktree ")]
        return paths or [str(root)]
    except (OSError, subprocess.SubprocessError) as e:
        logger.info("git worktree list 失敗，改用專案根: %s", e)
        return [str(root)]


def written_ticket_ids(input_data: dict) -> List[str]:
    """本次寫入涉及的票號：Edit 類取檔名，Bash 的 ticket track 命令取命令中的票號。"""
    tool = input_data.get("tool_name", "")
    ti = input_data.get("tool_input") or {}
    if tool == "Bash":
        cmd = ti.get("command", "")
        if "ticket track" not in cmd:
            return []
        return list(dict.fromkeys(TICKET_ID_IN_TEXT.findall(cmd)))
    if tool in WRITE_TOOLS:
        stem = Path(str(ti.get("file_path", ""))).stem
        return [stem] if ticket_prefix_of(stem) else []
    return []


def read_ticket_text(root: Path, ticket_id: str) -> Optional[str]:
    for rel in ticket_file_candidates(ticket_id):
        try:
            return (root / rel).read_text(encoding="utf-8")
        except OSError:
            # 候選路徑逐一試讀；全部失敗回傳 None，視為非協調票（IMP-013）
            continue
    return None


def has_coordination_flag(text: str) -> bool:
    """票本身 frontmatter 是否有 `coordination: true`。"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            return False
        m = re.match(r"^coordination:\s*['\"]?(\w+)['\"]?\s*$", line)
        if m:
            return m.group(1).lower() == "true"
    return False


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0
    root = get_project_root()
    for coord_id in written_ticket_ids(input_data):
        text = read_ticket_text(root, coord_id)
        if text is not None and has_coordination_flag(text):
            return check_coordination_ticket(logger, root, input_data, coord_id, text)
    logger.debug("跳過: 未寫入帶 coordination 標記的票")
    return 0


def check_coordination_ticket(logger, root: Path, input_data: dict, coord_id: str, text: str) -> int:
    lanes = parse_lanes(text, ticket_prefix_of(coord_id))
    alive = alive_session_names(logger, list_checkouts(logger, root))
    msgs = find_malformed_lines(text) + find_problems(
        lanes, alive, lambda tid: read_ticket_status(root, tid)
    ) + find_unpaired_todos(text)
    if not msgs:
        return 0
    logger.info("協調票佇列行提示 %d 項", len(msgs))
    emit_model_reminder(
        "PostToolUse",
        "[協調票佇列行檢查] " + coord_id + "\n" + "\n".join(msgs),
        input_data=input_data,
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
