#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
coordination-queue-line-check-hook - PostToolUse Hook（Bash / Edit / Write / MultiEdit）

目的: 協調票（multi-session.json 的 coordinationTicket）被寫入後，從磁碟重讀票檔，
      檢查現行佇列行的兩種寫法錯誤，以 additionalContext 提示模型（不阻擋，exit 0）。
      文字約定兩度失守，故由機械層在寫入當下指出。

檢查（解析規則照 .claude/skills/line-board/hooks/lanes.ts：行首、只掃 Solution、每線取最後一行）:
  1. 作用中（票序不是（無））且有括號的線，括號內文不等於任何存活 session 名稱
     （~/.claude/sessions/*.json，cwd 屬本 repo 任一 checkout）-> 提示兩種可能原因
  2. 票序票號全部可解析且狀態皆 completed/closed，卻未寫（無）-> 提示可結束，附完整格式
  3. 以「**L<n> 現行佇列**」開頭卻不符 LANE_LINE 的行（如漏冒號），若在該線最後一筆合格行之後
     -> 報出原文與格式；解析層照 lanes.ts 不採用此行，不報會被誤以為已寫入

受眾: 模型 -> emit_model_reminder("PostToolUse", ...)。multi-session.json 缺席/不成立時不輸出。
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

HOOK_NAME = "coordination-queue-line-check"
CONFIG_PATH = ".claude/project-integration/multi-session.json"
LANE_ENDED = "（無）"
TERMINAL_STATUSES = ("completed", "closed")
WRITE_TOOLS = ("Edit", "Write", "MultiEdit")

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


def read_coordination_ticket(logger, root: Path) -> Optional[str]:
    try:
        d = json.loads((root / CONFIG_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.debug("multi-session.json 不可用: %s", e)
        return None
    cid = d.get("coordinationTicket") if isinstance(d, dict) else None
    return cid if isinstance(cid, str) and ticket_prefix_of(cid) else None


def touches_coordination_ticket(input_data: dict, coord_id: str) -> bool:
    tool = input_data.get("tool_name", "")
    ti = input_data.get("tool_input") or {}
    if tool == "Bash":
        cmd = ti.get("command", "")
        return "ticket track" in cmd and re.search(r"(?<![\w.-])%s(?![\w.-])" % re.escape(coord_id), cmd) is not None
    if tool in WRITE_TOOLS:
        return Path(str(ti.get("file_path", ""))).name == coord_id + ".md"
    return False


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0
    root = get_project_root()
    coord_id = read_coordination_ticket(logger, root)
    if coord_id is None:
        return 0
    if not touches_coordination_ticket(input_data, coord_id):
        logger.debug("跳過: 未寫入協調票")
        return 0
    text = None
    for rel in ticket_file_candidates(coord_id):
        try:
            text = (root / rel).read_text(encoding="utf-8")
            break
        except OSError:
            continue
    if text is None:
        logger.info("協調票檔讀不到: %s", coord_id)
        return 0
    lanes = parse_lanes(text, ticket_prefix_of(coord_id))
    alive = alive_session_names(logger, list_checkouts(logger, root))
    msgs = find_malformed_lines(text) + find_problems(
        lanes, alive, lambda tid: read_ticket_status(root, tid)
    )
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
