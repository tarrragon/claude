#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Dispatch Stall Reminder Hook

功能: 提醒主線程 PM：本 session 派發的代理人回合已結束超過閾值，
      票仍為 in_progress 且之後沒有任何進度（無 commit、票 md 未被改動）。
觸發時機: UserPromptSubmit
受眾: 主線程 PM（模型），經 emit_hook_output 的 additionalContext 輸出。
      subagent 環境直接 exit 0。
行為: 只讀 dispatch-active.json，不清理、不阻擋、不判定代理人已終止。
      時間閾值只用於提醒，不得用於移除記錄（回合結束後代理人仍可能寫檔）。
異常: 任何讀取或 git 失敗皆記 warning 日誌並寫 stderr，exit 0（fail-open）。
去重: 以 (agent_id 或 agent_handle, turn_ended_at) 為鍵，狀態檔在
      .claude/hook-logs/dispatch-stall-reminder/。
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    get_hook_log_dir,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    resolve_session_id,
    is_subagent_environment,
    emit_hook_output,
)
from lib.hook_base import get_shared_state_root
from lib.dispatch_tracker import get_active_dispatches

HOOK_NAME = "dispatch-stall-reminder"
STALL_THRESHOLD_MINUTES = 30
GIT_TIMEOUT_SECONDS = 10
_STATUS_RE = re.compile(r"^status:\s*(\S+)\s*$", re.MULTILINE)


def _parse_time(value: str) -> Optional[datetime]:
    """解析 ISO8601；無時區者視為 UTC。失敗回傳 None。"""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def find_ticket_file(project_root: Path, ticket_id: str) -> Optional[Path]:
    """依票號在 docs/work-logs 下找票 md；找不到回傳 None。"""
    matches = sorted(
        (project_root / "docs" / "work-logs").glob(f"**/tickets/{ticket_id}.md")
    )
    return matches[0] if matches else None


def read_ticket_status(ticket_file: Path) -> Optional[str]:
    """讀 frontmatter 的 status；無法解析回傳 None。"""
    head = ticket_file.read_text(encoding="utf-8").split("\n---", 2)[0]
    found = _STATUS_RE.search(head)
    return found.group(1) if found else None


def has_commit_since(project_root: Path, ticket_id: str, since: str) -> bool:
    """turn_ended_at 之後是否有 commit message 含該票號。"""
    result = subprocess.run(
        ["git", "-C", str(project_root), "log", f"--since={since}",
         f"--grep={ticket_id}", "-1", "--format=%H"],
        capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS, check=True,
    )
    return bool(result.stdout.strip())


def is_stalled(project_root: Path, entry: dict, now: datetime,
               git_root: Optional[Path] = None) -> bool:
    """三項停滯條件皆成立才回傳 True（逾時、in_progress、之後無進度）。"""
    ended_raw = entry["turn_ended_at"]
    ended = _parse_time(ended_raw)
    if ended is None:
        return False
    if (now - ended).total_seconds() < STALL_THRESHOLD_MINUTES * 60:
        return False
    ticket_file = find_ticket_file(project_root, entry["ticket_id"])
    if ticket_file is None or read_ticket_status(ticket_file) != "in_progress":
        return False
    if ticket_file.stat().st_mtime >= ended.timestamp():
        return False
    return not has_commit_since(git_root or project_root, entry["ticket_id"], ended_raw)


def dedup_key(entry: dict) -> str:
    who = entry.get("agent_id") or entry.get("agent_handle") or ""
    return f"{who}|{entry['turn_ended_at']}"


def _state_file() -> Path:
    # linked worktree 內解析到主 checkout，去重狀態跨 checkout 共用
    return get_hook_log_dir(HOOK_NAME) / "reminded.json"


def load_reminded(state_file: Path) -> List[str]:
    if not state_file.exists():
        return []
    return json.loads(state_file.read_text(encoding="utf-8"))


def save_reminded(state_file: Path, keys: List[str]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(keys), encoding="utf-8")


def build_reminders(project_root: Path, session_id: str, now: datetime,
                    git_root: Optional[Path] = None) -> List[tuple]:
    """回傳 [(key, 提醒行)]：本 session、有票號、回合已結束且停滯的條目。"""
    reminders = []
    for entry in get_active_dispatches(project_root):
        if (entry.get("session_id") != session_id or not entry.get("ticket_id")
                or not entry.get("turn_ended_at")):
            continue
        if not is_stalled(project_root, entry, now, git_root):
            continue
        ended = _parse_time(entry["turn_ended_at"])
        minutes = int((now - ended).total_seconds() // 60)
        line = (f"- {entry['ticket_id']}｜{entry.get('agent_description', '')}"
                f"｜回合結束後 {minutes} 分鐘無進度")
        reminders.append((dedup_key(entry), line))
    return reminders


def format_message(lines: List[str]) -> str:
    return ("[派發停滯提醒] 下列代理人回合已結束且票無後續進度：\n"
            + "\n".join(lines)
            + "\n建議：用 SendMessage 詢問代理人，或以 `ticket track full <id>` 查進度。"
            "（僅提醒，未判定代理人已終止）")


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger) or {}
    if is_subagent_environment(input_data):
        return 0
    try:
        git_root = get_project_root()
        state_root = get_shared_state_root(git_root)
        now = datetime.now(timezone.utc)
        reminders = build_reminders(
            state_root, resolve_session_id(input_data), now, git_root)
        state_file = _state_file()
        reminded = load_reminded(state_file)
        fresh = [(k, line) for k, line in reminders if k not in reminded]
        if not fresh:
            return 0
        emit_hook_output(
            "UserPromptSubmit", format_message([line for _, line in fresh])
        )
        save_reminded(state_file, reminded + [k for k, _ in fresh])
        logger.info("提醒 %d 筆停滯派發", len(fresh))
    except Exception as exc:  # fail-open：失敗不阻擋使用者輸入
        logger.warning("停滯偵測失敗（fail-open）：%s", exc)
        sys.stderr.write(f"[{HOOK_NAME}] 偵測失敗，略過提醒：{exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
