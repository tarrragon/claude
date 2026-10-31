#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""主控接續提示（SessionStart hook）。

名為「主控」的 session 在 /clear 或 /compact 之後啟動時，以 additionalContext 提示模型：
先呼叫 line-board 的 line_status 判讀各線，再依 line-continuity.md §4 完成自我接續，才處理訊息。
其他名稱、或 source 為 startup／resume 時不輸出任何東西。

判讀邏輯不在此重寫：各線狀態由 line_status 工具判讀，本 hook 只負責「在對的時機提醒去呼叫它」。

session 名稱取自 ~/.claude/sessions/<pid>.json（只讀 *.json，不讀同目錄的 *.key），兩條路徑依序：
1. payload 的 session_id 比對檔內 sessionId，且檔案的行程仍存活（pid 存在、啟動時間與 procStart 相同）。
   resume／compact 沿用同一個 id，已結束行程留下的舊檔可能同 id，所以必須驗存活。
2. 比對不到（/clear 後檔案可能尚未寫入新 id）時，沿父行程鏈找第一個執行檔名含 claude 的祖先，
   只讀那個 pid 的檔，同樣驗存活。停在第一個 claude 祖先，不會走到外層另一個 claude（例如主控以 claude -p 開的子 session）。

失敗一律不阻擋 session 啟動：錯誤寫 stderr 與日誌檔（含 traceback，quality-baseline 規則 4），exit 0。
"""

import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

# 主控線的 session 名稱（用戶裁定：名稱為「主控」的 session 就是主控線）
MASTER_NAME = "主控"
# 要提示的 SessionStart 來源：clear 清空對話、compact 只剩摘要；startup／resume 不提示
HINT_SOURCES = ("clear", "compact")
# 沿父行程鏈找 claude 祖先的最多層數（實際鏈約為 python → uv → sh → claude）
MAX_ANCESTOR_DEPTH = 6
# 祖先行程的執行檔名含此字串即視為 Claude Code 行程
CLAUDE_COMM_MARK = "claude"
# ps -o lstart 須以 UTC、C locale 輸出，才能與 session 檔的 procStart 逐字比對（line-board sessions.ts 同一判準）
PS_ENV = {"TZ": "UTC", "LC_ALL": "C", "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
PROJECT_CONFIG = Path(".claude/project-integration/multi-session.json")
CONTINUITY_DOC = ".claude/skills/multi-session-orchestration/references/line-continuity.md"
LOG_DIR_PARTS = (".claude", "hook-logs", "master-resume-hint")


def sessions_dir() -> Path:
    return Path(os.environ.get("HOME", "")) / ".claude" / "sessions"


def read_json_file(path: Path) -> dict | None:
    """讀一個 JSON 檔；讀不到或格式無效時回傳 None（session 檔可能寫到一半、設定檔可能不存在，屬正常情形，不記錯）。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def ps_field(pid: int, field: str) -> str | None:
    """以 ps 取行程欄位；行程不存在或 ps 無法執行時回傳 None（呼叫端把 None 當「無此行程」，不需另記錯）。"""
    try:
        out = subprocess.run(["ps", "-o", f"{field}=", "-p", str(pid)], capture_output=True, text=True, timeout=5, env=PS_ENV)
    except (OSError, subprocess.SubprocessError):
        return None
    text = out.stdout.strip()
    return text if out.returncode == 0 and text else None


def parent_pid(pid: int) -> int | None:
    text = ps_field(pid, "ppid")
    return int(text) if text is not None and text.isdigit() else None


def process_comm(pid: int) -> str:
    return ps_field(pid, "comm") or ""


def is_alive_session(data: dict) -> bool:
    """session 檔的行程是否仍是同一個：pid 存在且啟動時間與 procStart 相同；檔內沒有 procStart 時只看 pid 存在。"""
    pid = data.get("pid")
    if not isinstance(pid, int):
        return False
    lstart = ps_field(pid, "lstart")
    if lstart is None:
        return False
    recorded = data.get("procStart")
    if not isinstance(recorded, str):
        return True
    return " ".join(lstart.split()) == " ".join(recorded.split())


def name_of(data: dict) -> str | None:
    name = data.get("name")
    return name if isinstance(name, str) else None


def name_by_session_id(session_id: str) -> str | None:
    """路徑 1：sessionId 相同且行程存活的 session 檔；多份都符合時記 warning 並取第一份（依檔名排序）。"""
    if not session_id:
        return None
    matches = [
        data
        for path in sorted(sessions_dir().glob("*.json"))
        if (data := read_json_file(path)) is not None and data.get("sessionId") == session_id and is_alive_session(data)
    ]
    if len(matches) > 1:
        log_line(f"WARNING sessionId {session_id[:8]} 對應 {len(matches)} 份存活的 session 檔，取第一份")
    return name_of(matches[0]) if matches else None


def nearest_claude_ancestor(start_pid: int) -> int | None:
    """路徑 2 的起點：沿父行程鏈找第一個執行檔名含 claude 的祖先；找不到時回傳 None。"""
    pid: int | None = start_pid
    for _ in range(MAX_ANCESTOR_DEPTH):
        if pid is None or pid <= 1:
            return None
        if CLAUDE_COMM_MARK in os.path.basename(process_comm(pid)).lower():
            return pid
        pid = parent_pid(pid)
    return None


def name_by_ancestor() -> str | None:
    """路徑 2：最近的 claude 祖先的 <pid>.json，且行程存活。"""
    pid = nearest_claude_ancestor(os.getppid())
    if pid is None:
        return None
    data = read_json_file(sessions_dir() / f"{pid}.json")
    return name_of(data) if data is not None and is_alive_session(data) else None


def session_name(session_id: str) -> str | None:
    """本 session 的名稱：路徑 1 優先（比對到就不看路徑 2），比對不到才走路徑 2；都找不到時回傳 None。"""
    by_id = name_by_session_id(session_id)
    return by_id if by_id is not None else name_by_ancestor()


def coordination_ticket(project_dir: Path) -> str | None:
    """專案設定的協調票；設定不存在或不成立時回傳 None。"""
    data = read_json_file(project_dir / PROJECT_CONFIG)
    ticket = data.get("coordinationTicket") if data is not None else None
    return ticket if isinstance(ticket, str) and ticket else None


def hint_text(source: str, ticket: str | None) -> str:
    """提示模型的文字：要求先呼叫 line_status 完成自我接續，再處理訊息。"""
    ticket_line = (
        f"2. 讀協調票 {ticket} 的 ## Solution 最後幾段（ticket track full {ticket}），找出前一個主控最後處理的事項與待辦"
        if ticket is not None
        else f"2. 專案設定 {PROJECT_CONFIG} 讀不到協調票：先請用戶確認協調票，再繼續"
    )
    return "\n".join(
        [
            f"[主控接續提示] 本 session 名為「{MASTER_NAME}」，剛經過 /{source}。處理任何訊息之前，先完成自我接續：",
            "1. 以 ToolSearch 搜尋 line_status，呼叫 mcp__line-board__line_status，取得各線接續狀態與過期項",
            ticket_line,
            f"3. 依 {CONTINUITY_DOC} §4 在協調票追加〈主控接續（{source}，<日期 時間>）〉段、推送，並先向用戶回報各線狀態與下一步",
            "line_status 不可用時，改依同檔 §3 的備援步驟判讀。",
        ]
    )


def build_output(payload: dict, project_dir: Path) -> dict | None:
    """依 payload 決定是否輸出提示；不提示時回傳 None。"""
    source = payload.get("source")
    if source not in HINT_SOURCES:
        return None
    if session_name(str(payload.get("session_id") or "")) != MASTER_NAME:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": hint_text(source, coordination_ticket(project_dir)),
        }
    }


def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def log_line(message: str) -> None:
    """寫日誌檔；寫不進去時只能放棄（錯誤路徑已另寫 stderr）。"""
    try:
        log_dir = project_dir().joinpath(*LOG_DIR_PARTS)
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "hook.log").open("a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except OSError:
        pass


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        output = build_output(payload if isinstance(payload, dict) else {}, project_dir())
        if output is not None:
            print(json.dumps(output, ensure_ascii=False))
    except Exception as exc:  # 任何失敗都不阻擋 session 啟動；雙通道記錄
        sys.stderr.write(f"[master-resume-hint] error: {exc!r}\n")
        log_line(f"ERROR {traceback.format_exc()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
