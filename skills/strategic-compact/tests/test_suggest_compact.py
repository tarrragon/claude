"""suggest-compact 計數鍵測試：斷言磁碟上的計數檔，非僅輸出。"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "suggest-compact.py"


def run(proj, tmp_legacy, payload, threshold="3"):
    env = dict(os.environ)
    env.update(
        CLAUDE_PROJECT_DIR=str(proj),
        SUGGEST_COMPACT_LEGACY_TMP_DIR=str(tmp_legacy),
        COMPACT_THRESHOLD=threshold,
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True, text=True, env=env, timeout=30,
    )


def counters(proj):
    d = proj / ".claude" / "hook-state"
    return {p.name: p.read_text().strip() for p in d.glob("compact-count-*")} if d.exists() else {}


def test_same_session_accumulates_and_reminds_at_threshold(tmp_path):
    proj, legacy = tmp_path / "p", tmp_path / "t"
    proj.mkdir(); legacy.mkdir()
    outs = [run(proj, legacy, {"session_id": "s1", "tool_name": "Edit"}) for _ in range(3)]
    assert counters(proj) == {"compact-count-s1": "3"}
    assert "StrategicCompact" not in outs[0].stdout
    assert "StrategicCompact" not in outs[1].stdout
    assert "3 tool calls reached" in outs[2].stdout


def test_sessions_counted_separately(tmp_path):
    proj, legacy = tmp_path / "p", tmp_path / "t"
    proj.mkdir(); legacy.mkdir()
    for sid in ("a", "a", "b"):
        run(proj, legacy, {"session_id": sid})
    assert counters(proj) == {"compact-count-a": "2", "compact-count-b": "1"}


def test_missing_session_id_does_not_count_and_logs(tmp_path):
    proj, legacy = tmp_path / "p", tmp_path / "t"
    proj.mkdir(); legacy.mkdir()
    for payload in (None, {}, {"session_id": ""}):
        r = run(proj, legacy, payload)
        assert r.returncode == 0
    assert counters(proj) == {}
    log = proj / ".claude" / "hook-logs" / "suggest-compact" / "suggest-compact.log"
    assert "session_id missing" in log.read_text()
    assert list(legacy.iterdir()) == []


def test_session_id_sanitized(tmp_path):
    proj, legacy = tmp_path / "p", tmp_path / "t"
    proj.mkdir(); legacy.mkdir()
    run(proj, legacy, {"session_id": "../../x/y"})
    assert list(counters(proj)) == ["compact-count-______x_y"]


def test_legacy_tmp_cleanup_only_matching_names(tmp_path):
    proj, legacy = tmp_path / "p", tmp_path / "t"
    proj.mkdir(); legacy.mkdir()
    for n in ("claude-tool-count-123", "claude-tool-count-abc", "other-file"):
        (legacy / n).write_text("1")
    run(proj, legacy, {"session_id": "s"})
    assert sorted(p.name for p in legacy.iterdir()) == ["claude-tool-count-abc", "other-file"]


def test_stale_other_session_files_removed(tmp_path):
    proj, legacy = tmp_path / "p", tmp_path / "t"
    state = proj / ".claude" / "hook-state"
    state.mkdir(parents=True); legacy.mkdir()
    old = state / "compact-count-old"
    old.write_text("9")
    os.utime(old, (1, 1))
    run(proj, legacy, {"session_id": "new"})
    assert list(counters(proj)) == ["compact-count-new"]
