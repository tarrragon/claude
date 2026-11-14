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

檢查（解析由 multi-session-orchestration/scripts/queue_line.py 負責，規則與 line-board lanes.ts 相同：
行首、只掃 Solution、每線取最後一行；收線（（無）、（結束））不檢查）:
  1. 作用中（票序不是（無））且有括號的線，括號內文不等於任何存活 session 名稱
     （~/.claude/sessions/*.json，cwd 屬本 repo 任一 checkout）-> 提示兩種可能原因
  2. 票序票號全部可解析且狀態皆 completed/closed，卻未寫（無）-> 提示可結束，附完整格式。
     本檢查另收步驟內任一位置的票號並展開範圍寫法（queue_check_ids），不用 queue_line 只認步驟開頭的
     解析；任一步驟收不到票號時不下全終態結論（自然語句步驟的狀態無從判定）
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
# 佇列行解析的 Python 唯一實作（與 line-board lanes.ts 共用 queue-line-cases.json 案例）
from queue_line import (  # noqa: E402
    LANE_LINE,
    LANE_LINE_PREFIX,
    QUEUE_SEPARATOR,
    parse_lane_lines,
    parse_lanes,
    solution_lines,
    ticket_prefix_of,
)
from lib.ticket_command_parse import find_ticket_track_invocations  # noqa: E402

HOOK_NAME = "coordination-queue-line-check"
TERMINAL_STATUSES = ("completed", "closed")
# 檢查 2 用：步驟內任一位置的票號（完整票號、W<波次>-<序號>、三位數短號），可接範圍終點 ～.<末段>
STEP_ID_ANYWHERE = re.compile(
    r"(?<![\w.-])(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*|W\d+-\d+(?:\.\d+)*|\d{3}(?:\.\d+)*)"
    r"(?:[～~]\.(\d+))?(?![\w-])"
)
PREFIX_VERSION = re.compile(r"^(.+)-W\d+-$")
# 範圍寫法展開上限：超過視為寫錯，只取起點與終點，不展開
RANGE_EXPAND_MAX = 50


class _AnyTrackVerb(tuple):
    """find_ticket_track_invocations 的 verbs：任何 ticket track 子命令都算（寫入目標由參數決定）。"""

    def __contains__(self, verb) -> bool:
        return True
WRITE_TOOLS = ("Edit", "Write", "MultiEdit")
# 檢查 4 的完成行格式（line-continuity.md §2〈用戶待辦〉）
TODO_DONE_FORMAT = "**用戶待辦完成**（%s）：<結果>"
TODO_DONE_KEYLESS = "**用戶待辦完成**：%s"

LANE_FORMAT = "**L%d 現行佇列**（<session 名稱>）：<票序，或（無）>"
# 票檔路徑推導用（非佇列行解析）：完整票號拆出版本
TICKET_ID = re.compile(r"^v?(\d+\.\d+\.\d+)-(W\d+)-\d+(?:\.\d+)*$")


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


def _resolve_step_id(token: str, prefix: Optional[str]) -> Optional[str]:
    """步驟內的票號 token 轉完整票號；短號或 W 開頭寫法缺前綴時回 None。"""
    if TICKET_ID.match(token):
        return token
    if prefix is None:
        return None
    if token.startswith("W"):
        ver = PREFIX_VERSION.match(prefix)
        return None if ver is None else "%s-%s" % (ver.group(1), token)
    return prefix + token


def _expand_range(start: str, end_last: Optional[str]) -> List[str]:
    """<起點>～.<末段> 展開為同層連號；沒有終點、終點不大於起點或跨度過大時不展開。"""
    if end_last is None:
        return [start]
    base, _, first = start.rpartition(".")
    if not base or not first.isdigit():
        return [start]
    lo, hi = int(first), int(end_last)
    if hi <= lo or hi - lo > RANGE_EXPAND_MAX:
        return [start, "%s.%s" % (base, end_last)]
    return ["%s.%d" % (base, k) for k in range(lo, hi + 1)]


def queue_check_ids(queue: str, prefix: Optional[str]) -> Optional[List[str]]:
    """檢查 2 用的票號：每一步收任一位置的票號並展開範圍；任一步收不到或無法轉成完整票號時回 None。"""
    ids: List[str] = []
    for part in QUEUE_SEPARATOR.split(queue.strip()):
        if part in ("", "→", "∥"):
            continue
        found = STEP_ID_ANYWHERE.findall(part)
        if not found:
            return None
        for token, end_last in found:
            for raw in _expand_range(token, end_last or None):
                full = _resolve_step_id(raw, prefix)
                if full is None:
                    return None
                ids.append(full)
    return list(dict.fromkeys(ids))


def lanes_for_check(text: str, prefix: Optional[str]) -> List[Dict[str, object]]:
    """parse_lanes 的線，另加 check_ids（queue_check_ids 的結果，可能為 None）。"""
    queues = {line["lane"]: line["queue"] for line in parse_lane_lines(text)}
    lanes = parse_lanes(text, prefix)
    for lane in lanes:
        lane["check_ids"] = queue_check_ids(queues[lane["lane"]], prefix)
    return lanes


def find_problems(lanes, alive_names: Optional[set], status_of) -> List[str]:
    """lanes 來自 lanes_for_check。alive_names 為 None 表示無法取得 session 名單，略過檢查 1。
    status_of(id)->Optional[str]。check_ids 為 None（有步驟收不到票號）時不下全終態結論。"""
    msgs = []
    for lane in lanes:
        n, session, check_ids = lane["lane"], lane["session"], lane["check_ids"]
        if session is not None and alive_names is not None and session not in alive_names:
            msgs.append(
                "L%d 括號內『%s』目前沒有同名 session：若是附註，請移到票序；"
                "若 session 已結束而線仍在，可忽略" % (n, session)
            )
        if check_ids:
            statuses = [status_of(tid) for tid in check_ids]
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


def _track_targets(args: List[str]) -> List[str]:
    """`ticket track <子命令>` 之後、第一個選項之前的完整票號（寫入目標）；選項值與內文不算。"""
    targets = []
    for arg in args:
        if arg.startswith("-"):
            break
        if TICKET_ID.match(arg):
            targets.append(arg)
    return targets


def written_ticket_ids(input_data: dict, logger=None) -> List[str]:
    """本次寫入涉及的票號：Edit 類取檔名；Bash 取每個 `ticket track <子命令>` 的目標票號，
    不取參數內文提到的票號。命令無法解析時回空清單（只少一次提示，不阻擋）。"""
    tool = input_data.get("tool_name", "")
    ti = input_data.get("tool_input") or {}
    if tool == "Bash":
        cmd = ti.get("command", "")
        if "ticket track" not in cmd:
            return []
        invocations = find_ticket_track_invocations(cmd, _AnyTrackVerb())
        if invocations is None:
            if logger is not None:
                logger.info("命令無法解析，略過協調票檢查: %s", cmd[:120])
            return []
        ids = [tid for _verb, args in invocations for tid in _track_targets(args)]
        return list(dict.fromkeys(ids))
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
    for coord_id in written_ticket_ids(input_data, logger):
        text = read_ticket_text(root, coord_id)
        if text is not None and has_coordination_flag(text):
            return check_coordination_ticket(logger, root, input_data, coord_id, text)
    logger.debug("跳過: 未寫入帶 coordination 標記的票")
    return 0


def check_coordination_ticket(logger, root: Path, input_data: dict, coord_id: str, text: str) -> int:
    lanes = lanes_for_check(text, ticket_prefix_of(coord_id))
    for lane in lanes:
        if lane["check_ids"] is None:
            logger.info("L%d 有步驟收不到票號，不判全終態", lane["lane"])
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
