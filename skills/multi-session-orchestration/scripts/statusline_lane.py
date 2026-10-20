#!/usr/bin/env python3
"""多線協調狀態列 wrapper：在內層狀態列輸出前加一行 `L<n> │ <名稱>`。

用法（statusLine.command）：
    python3 statusline_lane.py --coord-ticket <協調票路徑> [--inner <命令>]

任何解析失敗只省略前綴，內層輸出照常；不得讓狀態列消失。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

SOLUTION_HEADING = "## Solution"
# 與 tools/line-board/hooks/lanes.ts 的 LANE_LINE 同一規則：只比對行首。
LANE_LINE = re.compile(r"^\*\*L(\d+) 現行佇列\*\*(?:（([^）]*)）)?：(.*)$")
ENDED_MARKERS = frozenset({"（結束）", "（無）"})  # 看板用（無），票面慣例亦見（結束）
INNER_TIMEOUT_SECONDS = 10
PREFIX_SEPARATOR = " │ "


def _warn(message: str) -> None:
    sys.stderr.write(f"[statusline_lane] {message}\n")


def parse_stdin(raw: str) -> dict:
    """解析 stdin JSON；失敗或非物件時回傳空 dict。"""
    try:
        data = json.loads(raw)
    except ValueError as exc:
        _warn(f"stdin 解析失敗：{exc}")
        return {}
    return data if isinstance(data, dict) else {}


def name_from_sessions(session_id: str) -> Optional[str]:
    """session_name 缺席時，以 sessionId 對 ~/.claude/sessions/*.json 取 name。"""
    sessions_dir = Path.home() / ".claude" / "sessions"
    for path in sorted(sessions_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _warn(f"略過無法讀取的 session 檔 {path.name}：{exc}")
            continue
        if isinstance(record, dict) and record.get("sessionId") == session_id:
            name = record.get("name")
            return name if isinstance(name, str) and name else None
    return None


def resolve_session_name(payload: dict) -> Optional[str]:
    name = payload.get("session_name")
    if isinstance(name, str) and name:
        return name
    session_id = payload.get("session_id")
    if isinstance(session_id, str) and session_id:
        return name_from_sessions(session_id)
    return None


def active_lanes(ticket_text: str) -> dict:
    """掃 Solution 段，每線取最後一行；回傳 {線號: session 名稱}，結束的線不含。"""
    in_solution = False
    latest = {}
    for line in (raw.rstrip() for raw in ticket_text.split("\n")):
        if line == SOLUTION_HEADING or line.startswith(SOLUTION_HEADING + " "):
            in_solution = True
            continue
        if in_solution and line.startswith("## "):
            break
        match = LANE_LINE.match(line) if in_solution else None
        if match:
            latest[int(match.group(1))] = (match.group(2), match.group(3).strip())
    return {n: s for n, (s, queue) in latest.items() if queue not in ENDED_MARKERS}


def lane_label(name: str, ticket_path: Path) -> str:
    """名稱對到的線號，例如 `L6·L13`；無對應回傳空字串。"""
    try:
        text = ticket_path.read_text(encoding="utf-8")
    except OSError as exc:
        _warn(f"協調票不可讀：{exc}")
        return ""
    lanes = sorted(n for n, session in active_lanes(text).items() if session == name)
    return "·".join(f"L{n}" for n in lanes)


def build_prefix(payload: dict, coord_ticket: Optional[str]) -> str:
    name = resolve_session_name(payload)
    if not name:
        return ""
    label = ""
    if coord_ticket:
        ticket_path = Path(coord_ticket)
        if not ticket_path.is_absolute():
            project_dir = (payload.get("workspace") or {}).get("project_dir")
            ticket_path = Path(project_dir or ".") / ticket_path
        label = lane_label(name, ticket_path)
    return f"{label}{PREFIX_SEPARATOR}{name}" if label else name


def default_inner_command() -> Optional[str]:
    settings_path = Path.home() / ".claude" / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        command = settings["statusLine"]["command"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _warn(f"讀不到內層 statusLine.command：{exc}")
        return None
    return command if isinstance(command, str) and command else None


def run_inner(command: Optional[str], raw_stdin: str) -> str:
    if not command or Path(__file__).name in command:  # 指回本腳本則不遞迴
        return ""
    try:
        result = subprocess.run(
            command, shell=True, input=raw_stdin, capture_output=True,
            text=True, timeout=INNER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _warn(f"內層命令失敗：{exc}")
        return ""
    return result.stdout


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coord-ticket")
    parser.add_argument("--inner")
    args = parser.parse_args(argv)
    raw_stdin = sys.stdin.read()
    try:
        prefix = build_prefix(parse_stdin(raw_stdin), args.coord_ticket)
    except Exception as exc:  # 前綴是附加品，任何失敗都不得影響內層輸出
        _warn(f"前綴產生失敗：{exc}")
        prefix = ""
    inner_command = args.inner if args.inner is not None else default_inner_command()
    inner_output = run_inner(inner_command, raw_stdin)
    if prefix:
        sys.stdout.write(prefix + "\n")
    sys.stdout.write(inner_output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
