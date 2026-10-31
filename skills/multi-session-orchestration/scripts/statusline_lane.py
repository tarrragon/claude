#!/usr/bin/env python3
"""多線協調狀態列 wrapper：在內層狀態列輸出前加一行 `L<n> │ <名稱>`。

用法（statusLine.command）：
    python3 statusline_lane.py --coord-ticket <協調票路徑> [--inner <命令>]

任何解析失敗只省略前綴，內層輸出照常；不得讓狀態列消失。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

SOLUTION_HEADING = "## Solution"
# 與 .claude/skills/line-board/hooks/lanes.ts 的 LANE_LINE 同一規則：只比對行首。
LANE_LINE = re.compile(r"^\*\*L(\d+) 現行佇列\*\*(?:（([^）]*)）)?：(.*)$")
ENDED_MARKERS = frozenset({"（結束）", "（無）"})  # 看板用（無），票面慣例亦見（結束）
INNER_TIMEOUT_SECONDS = 10
PREFIX_SEPARATOR = " │ "
CONFIG_RELATIVE_PATH = ".claude/project-integration/multi-session.json"
WORK_LOGS_DIR = "docs/work-logs"
# 與 line-board hooks/shared.ts 的 TICKET_ID 同一規則。
TICKET_ID = re.compile(r"^(.+?)-(W\d+-)\d+(?:\.\d+)*$")


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
    """第一個存在的候選；皆不存在取第一個候選（與 shared.ts resolveTicketFile 一致）。"""
    candidates = [project_dir / c for c in ticket_file_candidates(ticket_id)]
    return next((c for c in candidates if c.exists()), candidates[0] if candidates else None)


def coord_ticket_from_config(project_dir: Path) -> Optional[Path]:
    """讀專案設定的 coordinationTicket 並推導票檔路徑；任何失敗回傳 None 並寫 stderr。"""
    config_path = project_dir / CONFIG_RELATIVE_PATH
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _warn(f"專案設定不可用 {config_path}：{exc}")
        return None
    ticket_id = config.get("coordinationTicket") if isinstance(config, dict) else None
    ticket_path = resolve_ticket_file(ticket_id, project_dir) if isinstance(ticket_id, str) else None
    if ticket_path is None:
        _warn(f"專案設定缺少有效的 coordinationTicket：{config_path}")
    return ticket_path


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
    ticket_path = None
    if coord_ticket:
        ticket_path = Path(coord_ticket)
        if not ticket_path.is_absolute():
            project_dir = (payload.get("workspace") or {}).get("project_dir")
            ticket_path = Path(project_dir or ".") / ticket_path
    elif os.environ.get("CLAUDE_PROJECT_DIR"):
        ticket_path = coord_ticket_from_config(Path(os.environ["CLAUDE_PROJECT_DIR"]))
    if ticket_path is not None:
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
