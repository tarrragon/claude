#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Strategic Compact Suggester

Runs on PreToolUse or periodically to suggest manual compaction at logical intervals.

Why manual over auto-compact:
- Auto-compact happens at arbitrary points, often mid-task
- Strategic compacting preserves context through logical phases
- Compact after exploration, before execution
- Compact after completing a milestone, before starting next

Criteria for suggesting compact:
- Session has been running for extended period
- Large number of tool calls made
- Transitioning from research/exploration to implementation
- Plan has been finalized
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# .claude/skills/strategic-compact/ -> .claude/（lib package 所在）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lib import emit_model_reminder  # noqa: E402


# 環境變數覆寫僅供測試隔離，避免測試誤刪真實 /tmp 檔
LEGACY_TMP_DIR = Path(os.environ.get("SUGGEST_COMPACT_LEGACY_TMP_DIR", "/tmp"))
LEGACY_NAME_RE = re.compile(r"claude-tool-count-\d+")
COUNTER_PREFIX = "compact-count-"
STALE_SECONDS = 7 * 24 * 3600


def _log(msg):
    """fail-open 路徑的日誌：寫 stderr 以外的 hook-logs 檔，不干擾使用者畫面。"""
    try:
        log_dir = _project_dir() / ".claude" / "hook-logs" / "suggest-compact"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "suggest-compact.log", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass  # 日誌本身失敗不得影響 hook（fail-open）


def _project_dir():
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent.parent


def _counter_path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[:100]
    return _project_dir() / ".claude" / "hook-state" / f"{COUNTER_PREFIX}{safe}"


def _cleanup_stale(state_dir, keep):
    """清除逾 7 天的他 session 計數檔。"""
    now = time.time()
    for p in state_dir.glob(f"{COUNTER_PREFIX}*"):
        try:
            if p != keep and now - p.stat().st_mtime > STALE_SECONDS:
                p.unlink()
        except OSError:
            _log(f"stale cleanup failed: {p.name}")


def _cleanup_legacy_tmp():
    """清除舊版以 pid 命名遺留於 /tmp 的檔案；僅刪檔名完全符合 claude-tool-count-<數字> 的一般檔。"""
    try:
        for p in LEGACY_TMP_DIR.glob("claude-tool-count-*"):
            if LEGACY_NAME_RE.fullmatch(p.name) and p.is_file() and not p.is_symlink():
                try:
                    p.unlink()
                except OSError:
                    pass  # 單檔刪除失敗略過，下次呼叫再試
    except OSError:
        _log("legacy /tmp cleanup failed")


def _bump_count(session_id):
    """以 session_id 分檔累加計數並回傳新值；首次建檔時順便清理殘留。"""
    counter_file = _counter_path(session_id)
    counter_file.parent.mkdir(parents=True, exist_ok=True)
    count = 1
    if counter_file.exists():
        try:
            count = int(counter_file.read_text().strip()) + 1
        except (ValueError, OSError):
            count = 1
    else:
        _cleanup_legacy_tmp()
        _cleanup_stale(counter_file.parent, counter_file)
    counter_file.write_text(str(count))
    return count


def main():
    threshold = int(os.environ.get('COMPACT_THRESHOLD', '50'))
    input_data = _read_stdin_json()
    session_id = input_data.get("session_id") if isinstance(input_data, dict) else None
    if not isinstance(session_id, str) or not session_id.strip():
        _log("session_id missing in payload; skip counting (fail-open)")
        return
    try:
        count = _bump_count(session_id.strip())
    except OSError as e:
        _log(f"counter io failed: {e}")
        return

    message = None
    # Suggest compact after threshold tool calls
    if count == threshold:
        message = f"[StrategicCompact] {threshold} tool calls reached - consider /compact if transitioning phases"
    # Suggest at regular intervals after threshold
    elif count > threshold and count % 25 == 0:
        message = f"[StrategicCompact] {count} tool calls - good checkpoint for /compact if context is stale"

    if message is None:
        return

    # additionalContext 讓模型讀到（stderr + exit 0 模型不可見）。
    # /compact 僅主線程可執行，subagent 不需看到（pm_only）。
    emit_model_reminder("PreToolUse", message, audience="pm_only", input_data=input_data)


def _read_stdin_json():
    """讀取 stdin JSON；空輸入或解析失敗回傳 None（僅影響受眾判斷，不影響提醒輸出）。"""
    try:
        raw = sys.stdin.read().strip()
        return json.loads(raw) if raw else None
    except (ValueError, OSError):
        return None


if __name__ == "__main__":
    main()
