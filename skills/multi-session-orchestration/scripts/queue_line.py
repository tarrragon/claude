"""協調票現行佇列行的解析：Python 端的唯一實作。

讀者：statusline_lane.py（狀態列線號）與 .claude/hooks/coordination-queue-line-check-hook.py（佇列行檢查）。
規則與 .claude/skills/line-board/hooks/lanes.ts 相同，兩邊都以
.claude/skills/line-board/tests/queue-line-cases.json 的同一批案例測試；任一邊的分類改動，另一邊的測試會翻紅。

佇列行的分類（每線只看最後一次出現的行）：
- 收線（ended_form 為 exact）：票序恰為（無）或（結束），parse_lanes 不回傳
- 收線寫法（ended_form 為 with-note）：以（無）、（結束）或「無（」開頭附說明，回傳且 ended 為 "with-note"
- 無票號：票序拆不出任何票號（空字串、只有分隔符、只有文字），回傳且 tickets 為空
- 現行：有票號且不是收線寫法
"""

import re
from typing import Dict, List, Optional

SOLUTION_HEADING = "## Solution"

# 只比對行首：清單項、表格內與以反引號引用範本的行都不算。
LANE_LINE = re.compile(r"^\*\*L(\d+) 現行佇列\*\*(?:（([^）]*)）)?：(.*)$")
# 以佇列行開頭但整行不一定合格；檢查層用來找出被解析層略過的寫錯行。
LANE_LINE_PREFIX = re.compile(r"^\*\*L(\d+) 現行佇列\*\*")

LANE_ENDED = "（無）"
ENDED_MARKS = (LANE_ENDED, "（結束）")
# 「無（附說明）」這類少了前括號的收線寫法
BARE_ENDED_WITH_NOTE = re.compile(r"^無（")

QUEUE_SEPARATOR = re.compile(r"\s*(→|∥)\s*")
STEP_SERIAL = re.compile(r"^(\d{3}(?:\.\d+)*)(.*)$")
STEP_FULL_ID = re.compile(r"^(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)(.*)$")
STEP_WAVE_ID = re.compile(r"^(W\d+-\d+(?:\.\d+)*)(.*)$")
PREFIX_VERSION = re.compile(r"^(.+)-W\d+-$")
COORDINATOR_ID = re.compile(r"^v?(\d+\.\d+\.\d+)-(W\d+)-\d+(?:\.\d+)*$")


def ticket_prefix_of(coordinator_id: str) -> Optional[str]:
    """協調票號推導的短票號前綴（<版本>-W<波次>-<序號> → <版本>-W<波次>-）；不是票號時回 None。"""
    m = COORDINATOR_ID.match(coordinator_id)
    return None if m is None else "%s-%s-" % (m.group(1), m.group(2))


def ended_form(queue: str) -> Optional[str]:
    """收線寫法：恰為收線標記回 "exact"，以收線標記開頭附說明回 "with-note"，其餘回 None。"""
    if queue in ENDED_MARKS:
        return "exact"
    if any(queue.startswith(mark) for mark in ENDED_MARKS) or BARE_ENDED_WITH_NOTE.match(queue):
        return "with-note"
    return None


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
    """票序拆成票號 token（分隔符與無法辨識的文字略過，只列 ticket token）。"""
    tickets = []
    for part in QUEUE_SEPARATOR.split(queue.strip()):
        if part in ("", "→", "∥"):
            continue
        t = _step_ticket(part, prefix)
        if t is not None:
            tickets.append({"serial": t[0], "id": t[1], "note": t[2].strip()})
    return tickets


def solution_lines(text: str) -> List[str]:
    """## Solution 段的各行（到下一個 ## 標題為止）；沒有 Solution 段回空清單。"""
    lines = [ln.rstrip() for ln in text.split("\n")]
    start = next(
        (i for i, ln in enumerate(lines) if ln == SOLUTION_HEADING or ln.startswith(SOLUTION_HEADING + " ")),
        -1,
    )
    if start == -1:
        return []
    rest = lines[start + 1:]
    for i, ln in enumerate(rest):
        if ln.startswith("## "):
            return rest[:i]
    return rest


def parse_lane_lines(text: str) -> List[Dict[str, object]]:
    """每線只取最後一次出現的現行佇列行，依線號排序；保留票序原文（含收線的線）。"""
    latest = {}
    for line in solution_lines(text):
        m = LANE_LINE.match(line)
        if m:
            latest[int(m.group(1))] = (m.group(2), m.group(3).strip())
    return [
        {"lane": lane, "session": session, "queue": queue}
        for lane, (session, queue) in sorted(latest.items())
    ]


def parse_lanes(text: str, prefix: str) -> List[Dict[str, object]]:
    """收線（exact）以外的線：{lane, session, tickets, ended}；ended 為 "with-note" 或 None。"""
    result = []
    for line in parse_lane_lines(text):
        form = ended_form(line["queue"])
        if form == "exact":
            continue
        result.append({
            "lane": line["lane"],
            "session": line["session"],
            "tickets": parse_queue(line["queue"], prefix),
            "ended": "with-note" if form == "with-note" else None,
        })
    return result


def is_current_lane(lane: Dict[str, object]) -> bool:
    """現行線：有票號且不是收線寫法。只有文字、只有分隔符或附說明收線的行都不算。"""
    return lane["ended"] is None and bool(lane["tickets"])
