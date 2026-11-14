#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""hook-nonblocking-error-relay-hook（UserPromptSubmit、PostToolUse）

Why:
  直接註冊的 hook 若在 import 期崩潰（exit 1），runtime 記為 non-blocking
  error：stderr 只寫進 transcript 的 attachment（type=hook_non_blocking_error），
  不送模型，工具照常執行。框架的 liveness 寫在 run_hook_safely 內，崩潰的
  hook 到不了那裡，因此兩邊都沒有模型看得到的紀錄（2026-11 實測，
  SessionStart、UserPromptSubmit、PreToolUse、PostToolUse 四個事件結果相同）。

Consequence:
  防護類 hook 在 import 期壞掉時，模型與 liveness 查詢都看不出它沒有在運作，
  守衛失效與「沒有違規」同形。

Action:
  在後續事件讀取 transcript 自上次位置之後新增的完整行，挑出
  hook_non_blocking_error，以 additionalContext 告知模型 hook 檔名、事件與
  一行摘要；同時每筆寫一行紀錄到 hook-logs/_nonblocking_errors/<session>.jsonl，
  供 `ticket track hook-liveness` 統計。

  - 增量讀取：state 記 {offset, recent_uuids}，只讀 offset 之後的完整行；
    檔案變短（offset 超過檔案大小）時從頭讀，以 recent_uuids 去重。
  - 註冊事件：UserPromptSubmit（回合起點，涵蓋 SessionStart 與上回合 Stop
    的錯誤）與 PostToolUse（回合中，涵蓋 PreToolUse／PostToolUse 的錯誤）。
    不註冊 PreToolUse：PostToolUse 已在下一個工具前送達，再加 PreToolUse
    只會讓每次工具呼叫多跑一次。
  - 摘要行：Traceback 的首行固定是 "Traceback (most recent call last):"，
    看不出原因，改取末行（例外類型與訊息）；其餘取首行。
  - 受眾：模型（additionalContext）。
  - 失敗語意：fail-open。讀取端任何例外 exit 0，寫 stderr 與日誌檔；
    觸發條件：transcript 讀不到、state 或紀錄目錄無法寫入、payload 解析失敗。

環境變數（測試隔離）：
  HOOK_NONBLOCKING_RELAY_STATE_DIR、HOOK_NONBLOCKING_RELAY_RECORDS_DIR
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import emit_hook_output, run_hook_safely  # noqa: E402
from lib.hook_base import get_shared_state_root  # noqa: E402

HOOK_NAME = "hook-nonblocking-error-relay"
ATTACHMENT_TYPE = "hook_non_blocking_error"
ATTACHMENT_MARKER = ATTACHMENT_TYPE.encode("utf-8")
# runtime 寫入 stderr 欄位時一律加此前綴；hook 無 stderr 時其後接 NO_STDERR_MARK
RUNTIME_STDERR_PREFIX = "Failed with non-blocking status code:"
NO_STDERR_MARK = "No stderr output"
TRACEBACK_PREFIX = "Traceback (most recent call last)"
SUMMARY_MAX_CHARS = 200
MAX_LISTED_ERRORS = 5
RECENT_UUID_LIMIT = 200
_HOOK_FILE_RE = re.compile(r"([\w.-]+\.py)\b")

ENV_STATE_DIR = "HOOK_NONBLOCKING_RELAY_STATE_DIR"
ENV_RECORDS_DIR = "HOOK_NONBLOCKING_RELAY_RECORDS_DIR"


def _warn(message: str) -> None:
    """stderr 通道（完整 traceback 由 run_hook_safely 寫日誌檔）。"""
    sys.stderr.write(f"[{HOOK_NAME}] {message}\n")


def _hook_logs_dir() -> Path:
    return get_shared_state_root() / ".claude" / "hook-logs"


def _state_dir() -> Path:
    override = os.environ.get(ENV_STATE_DIR)
    return Path(override) if override else _hook_logs_dir() / HOOK_NAME / "state"


def _records_dir() -> Path:
    override = os.environ.get(ENV_RECORDS_DIR)
    return Path(override) if override else _hook_logs_dir() / "_nonblocking_errors"


def _safe_session_id(session_id: str) -> str:
    return re.sub(r"[^\w.-]", "_", session_id) or "unknown"


# ---------------------------------------------------------------------------
# 摘要與檔名
# ---------------------------------------------------------------------------


def _non_empty_lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def summarize_output(stderr: str, stdout: str) -> str:
    """取一行摘要：先去掉 runtime 前綴；Traceback 取末行，其餘取首行；
    runtime 標示無 stderr 時改用 stdout 首行。"""
    text = (stderr or "").strip()
    if text.startswith(RUNTIME_STDERR_PREFIX):
        text = text[len(RUNTIME_STDERR_PREFIX):].strip()
    lines = _non_empty_lines(text)
    if not lines or lines[0] == NO_STDERR_MARK:
        lines = _non_empty_lines(stdout)
        summary = lines[0] if lines else "（無輸出）"
    elif lines[0].startswith(TRACEBACK_PREFIX):
        summary = lines[-1]
    else:
        summary = lines[0]
    if len(summary) > SUMMARY_MAX_CHARS:
        summary = summary[:SUMMARY_MAX_CHARS] + "…"
    return summary


def extract_hook_file(command: str) -> Optional[str]:
    """從註冊命令取 hook 檔名（最後一個 *.py）。"""
    matches = _HOOK_FILE_RE.findall(command or "")
    return matches[-1] if matches else None


# ---------------------------------------------------------------------------
# 增量讀取
# ---------------------------------------------------------------------------


def read_new_errors(transcript: Path, offset: int) -> Tuple[List[dict], int]:
    """讀 offset 之後的完整行，回傳 (錯誤 entry 清單, 新 offset)。

    先以位元組比對 marker 再解析 JSON，避免逐行解析整份 transcript。
    檔案比 offset 短時視為重寫，從頭讀。末行未寫完（無換行）不推進位置。
    """
    size = transcript.stat().st_size
    if offset > size:
        offset = 0
    with transcript.open("rb") as fh:
        fh.seek(offset)
        chunk = fh.read(size - offset)
    last_newline = chunk.rfind(b"\n")
    if last_newline < 0:
        return [], offset
    complete = chunk[: last_newline + 1]
    errors: List[dict] = []
    for raw in complete.split(b"\n"):
        if ATTACHMENT_MARKER not in raw:
            continue
        try:
            entry = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue  # 非 JSON 行不屬於本 hook 要找的 attachment，略過
        attachment = entry.get("attachment") if isinstance(entry, dict) else None
        if isinstance(attachment, dict) and attachment.get("type") == ATTACHMENT_TYPE:
            errors.append(entry)
    return errors, offset + len(complete)


# ---------------------------------------------------------------------------
# state 與紀錄
# ---------------------------------------------------------------------------


def _empty_state() -> dict:
    return {"offset": 0, "recent_uuids": []}


def load_state(path: Path) -> dict:
    if not path.is_file():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _warn(f"state 讀取失敗，從頭讀取: {exc}")
        return _empty_state()
    return data if isinstance(data, dict) else _empty_state()


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _to_record(entry: dict, session_id: str) -> dict:
    att = entry["attachment"]
    return {
        "hook_file": extract_hook_file(att.get("command", "")) or att.get("hookName", ""),
        "hook_name": att.get("hookName", ""),
        "hook_event": att.get("hookEvent", ""),
        "exit_code": att.get("exitCode"),
        "summary": summarize_output(att.get("stderr", ""), att.get("stdout", "")),
        "uuid": entry.get("uuid", ""),
        "session_id": session_id,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }


def append_records(path: Path, records: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def format_reminder(records: List[dict]) -> str:
    lines = [
        f"[{HOOK_NAME}] runtime 記錄到 {len(records)} 筆 hook 非阻擋錯誤"
        "（exit 非 0 非 2：runtime 只寫進 transcript、不送模型，工具照常執行，"
        "該 hook 這次沒有發揮作用）："
    ]
    for rec in records[:MAX_LISTED_ERRORS]:
        lines.append(
            f"- {rec['hook_file']}（{rec['hook_name']}，exit {rec['exit_code']}）：{rec['summary']}"
        )
    remaining = len(records) - MAX_LISTED_ERRORS
    if remaining > 0:
        lines.append(f"- 另有 {remaining} 筆未列出")
    lines.append(
        "請告知用戶哪支 hook 失效；累計筆數可用 `ticket track hook-liveness <hook 路徑>` 查詢。"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def _read_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}


def relay(payload: dict) -> Optional[str]:
    """處理一次事件，回傳要送模型的提醒（無則 None）。"""
    transcript_path = payload.get("transcript_path") or ""
    session_id = _safe_session_id(str(payload.get("session_id") or ""))
    transcript = Path(transcript_path)
    if not transcript_path or not transcript.is_file():
        return None

    state_path = _state_dir() / f"{session_id}.json"
    state = load_state(state_path)
    offset = state.get("offset", 0)
    recent = state.get("recent_uuids", [])
    if not isinstance(offset, int) or offset < 0:
        offset = 0
    if not isinstance(recent, list):
        recent = []

    errors, new_offset = read_new_errors(transcript, offset)
    seen = set(recent)
    fresh = [e for e in errors if e.get("uuid") not in seen]

    # 先寫 state：state 無法保存時不送提醒，避免每個事件重複同一批錯誤
    recent = (recent + [e.get("uuid", "") for e in fresh])[-RECENT_UUID_LIMIT:]
    save_state(state_path, {"offset": new_offset, "recent_uuids": recent})

    if not fresh:
        return None
    records = [_to_record(e, session_id) for e in fresh]
    try:
        append_records(_records_dir() / f"{session_id}.jsonl", records)
    except OSError as exc:
        _warn(f"紀錄寫入失敗（hook-liveness 將少計）: {exc}")
    return format_reminder(records)


def main() -> int:
    try:
        payload = _read_payload()
        event = str(payload.get("hook_event_name") or "UserPromptSubmit")
        reminder = relay(payload)
    except Exception as exc:  # noqa: BLE001
        # fail-open：先寫 stderr，再交給 run_hook_safely 寫完整 traceback 到日誌檔
        _warn(f"讀取 transcript 失敗，略過本次轉告: {type(exc).__name__}: {exc}")
        raise
    if reminder:
        emit_hook_output(event, reminder)
    return 0


def _main_fail_open() -> int:
    """run_hook_safely 例外時回 1；本 hook 為提醒性質，一律以 0 結束。"""
    run_hook_safely(main, HOOK_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(_main_fail_open())
