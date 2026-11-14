"""session-context-guard-hook：完成命令辨識（含 finish 別名）。

E2：斷言計數檔的實際計數值與 exit code，不以輸出字樣判定。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "session_context_guard_hook", _HOOKS_DIR / "session-context-guard-hook.py"
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


@pytest.fixture
def counter(tmp_path, monkeypatch):
    f = tmp_path / "counter"
    monkeypatch.setattr(_hook, "get_counter_file", lambda *a, **kw: f)
    return f


def _run(monkeypatch, command, stdout="Ticket X 已完成"):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return _hook.main()


def _count(counter):
    return int(counter.read_text()) if counter.exists() else 0


@pytest.mark.parametrize("command", [
    "ticket track complete T-1",
    "ticket track finish T-1",
    "ticket track batch-complete T-1 T-2",
    "FOO=1 ticket track finish T-1",
    "cd /x && ticket track finish T-1",
])
def test_completion_commands_increment(monkeypatch, counter, command):
    assert _run(monkeypatch, command) == 0
    assert _count(counter) == 1


@pytest.mark.parametrize("command", [
    'ticket track append-log T-1 --section S "ticket track finish T-2"',
    "cat <<'EOF'\nticket track complete T-2\nEOF",
    'ticket track finish "unterminated',
])
def test_non_command_text_does_not_increment(monkeypatch, counter, command):
    assert _run(monkeypatch, command) == 0
    assert _count(counter) == 0


def test_failure_marker_absent_does_not_increment(monkeypatch, counter):
    # 被遮蔽且無票號可讀（退回標記判定）：stdout 無標記不計數
    assert _run(monkeypatch, "ticket track finish T-1; echo rc=$?", stdout="error") == 0
    assert _count(counter) == 0


def test_unmasked_counts_once_regardless_of_stdout(monkeypatch, counter):
    assert _run(monkeypatch, "ticket track finish T-1", stdout="") == 0
    assert _count(counter) == 1


def test_unmasked_recomplete_outside_window_not_counted(monkeypatch, counter):
    """E1：未遮蔽、stdout 為「已完成於 ...」，completed_at 在窗外不計數、窗內計數"""
    out = "0.5.0-W1-286.1 已完成於 2026-10-15T11:52:55"
    monkeypatch.setattr(_hook, "make_completed_verifier", lambda cmd: (lambda: False))
    assert _run(monkeypatch, "ticket track complete 0.5.0-W1-286.1", stdout=out) == 0
    assert _count(counter) == 0
    monkeypatch.setattr(_hook, "make_completed_verifier", lambda cmd: (lambda: True))
    assert _run(monkeypatch, "ticket track complete 0.5.0-W1-286.1", stdout=out) == 0
    assert _count(counter) == 1


@pytest.mark.parametrize("command", [
    "ticket track finish T > log 2>&1; echo rc=$?",
    "out=$(ticket track complete T 2>&1); rc=$?",
])
def test_masked_forms_follow_ticket_state(monkeypatch, counter, command):
    """E1：同一 stdout（rc=0）下，票面已完成計數 1、票面未完成不計數"""
    monkeypatch.setattr(_hook, "make_completed_verifier", lambda cmd: (lambda: True))
    assert _run(monkeypatch, command, stdout="rc=0") == 0
    assert _count(counter) == 1
    counter.unlink()
    monkeypatch.setattr(_hook, "make_completed_verifier", lambda cmd: (lambda: False))
    assert _run(monkeypatch, command, stdout="rc=0") == 0
    assert _count(counter) == 0


# ============================================================================
# 用量檔優先、讀不到才用票數
# ============================================================================

SESSION_ID = "sess-abc_123"


@pytest.fixture
def usage_dir(tmp_path, monkeypatch):
    """用量檔改指向 tmp_path，不讀主 repo 的真實 hook-logs。"""
    d = tmp_path / "context"
    d.mkdir()
    monkeypatch.setattr(_hook, "usage_file_path", lambda sid: d / f"{sid}.json")
    return d


def _write_usage(usage_dir, percent, *, compact_percent=None, auto_threshold=None, session_id=SESSION_ID):
    record = {
        "sessionId": session_id, "phase": None, "tokens": 1, "window": 100,
        "percent": percent, "compactWindow": None, "compactPercent": compact_percent,
        "autoCompactThreshold": auto_threshold, "measuredAt": 0,
    }
    (usage_dir / f"{SESSION_ID}.json").write_text(json.dumps(record), encoding="utf-8")


def _complete_with_session(monkeypatch, capsys):
    """以帶 session_id 的 complete 成功事件跑一次，回傳 additionalContext（無輸出為空字串）。"""
    payload = {
        "session_id": SESSION_ID,
        "tool_name": "Bash",
        "tool_input": {"command": "ticket track complete T-1"},
        "tool_response": {"stdout": "Ticket T-1 已完成"},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    assert _hook.main() == 0
    out = capsys.readouterr().out.strip().splitlines()
    data = json.loads(out[-1]) if out else {}
    return data.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_e1_low_usage_silences_count_warning(monkeypatch, capsys, counter, usage_dir):
    """E1：同為第 3 張票，用量檔 22% 時不提醒；沒有用量檔時以票數提醒"""
    counter.write_text("2")
    _write_usage(usage_dir, 22)
    assert _complete_with_session(monkeypatch, capsys) == ""
    assert _count(counter) == 3  # 計數照常遞增

    counter.write_text("2")
    (usage_dir / f"{SESSION_ID}.json").unlink()
    text = _complete_with_session(monkeypatch, capsys)
    assert "以票數估計" in text and "/compact" in text


def test_e2_usage_at_compact_threshold_warns(monkeypatch, capsys, counter, usage_dir):
    """E2：第 1 張票（票數不會提醒）但用量 47%，提醒在本 session /compact"""
    _write_usage(usage_dir, 47)
    text = _complete_with_session(monkeypatch, capsys)
    assert "47%" in text and "/compact" in text
    assert "新 session" not in text.replace("不換新 session", "")


def test_usage_between_clear_and_compact_hints_clear(monkeypatch, capsys, counter, usage_dir):
    _write_usage(usage_dir, 33)
    text = _complete_with_session(monkeypatch, capsys)
    assert "33%" in text and "/clear" in text


def test_compact_percent_used_when_auto_compact_on(monkeypatch, capsys, counter, usage_dir):
    """autoCompactThreshold 有值時取 compactPercent（同 line-board selectedPercent）"""
    _write_usage(usage_dir, 10, compact_percent=50, auto_threshold=0.9)
    assert "50%" in _complete_with_session(monkeypatch, capsys)


@pytest.mark.parametrize("content", [
    "{not json",
    json.dumps({"sessionId": "other", "percent": 90, "autoCompactThreshold": None}),
    json.dumps({"sessionId": SESSION_ID, "percent": None, "autoCompactThreshold": None}),
])
def test_unusable_usage_falls_back_to_count(monkeypatch, capsys, counter, usage_dir, content):
    """解析失敗、sessionId 不符、百分比缺席：都退回票數判定"""
    (usage_dir / f"{SESSION_ID}.json").write_text(content, encoding="utf-8")
    counter.write_text("2")
    assert "以票數估計" in _complete_with_session(monkeypatch, capsys)


def test_e2_pre_compact_measure_silences_both_paths(monkeypatch, capsys, counter, usage_dir):
    """E2：compact 完成當下寫入的記錄（phase compacted、measuredAt == phase.at、61%），即使計數已 5 張也不提醒"""
    record = {
        "sessionId": SESSION_ID, "phase": {"kind": "compacted", "source": "compact", "at": 1000},
        "tokens": 611445, "window": 1000000, "percent": 61, "compactWindow": None,
        "compactPercent": None, "autoCompactThreshold": None, "measuredAt": 1000,
    }
    (usage_dir / f"{SESSION_ID}.json").write_text(json.dumps(record), encoding="utf-8")
    counter.write_text("4")
    assert _complete_with_session(monkeypatch, capsys) == ""


def test_e1_measure_after_compact_still_warns(monkeypatch, capsys, counter, usage_dir):
    """E1 對照：同為 61%、phase compacted，但量測晚於 compact 完成時照常提醒"""
    record = {
        "sessionId": SESSION_ID, "phase": {"kind": "compacted", "source": "compact", "at": 1000},
        "percent": 61, "autoCompactThreshold": None, "measuredAt": 1001,
    }
    (usage_dir / f"{SESSION_ID}.json").write_text(json.dumps(record), encoding="utf-8")
    assert "61%" in _complete_with_session(monkeypatch, capsys)


def test_count_warning_no_longer_suggests_new_session(monkeypatch, capsys, counter, usage_dir):
    counter.write_text("4")
    text = _complete_with_session(monkeypatch, capsys)
    assert "Handoff" not in text
    assert "不換新 session" in text


def test_thresholds_match_line_board_context_judge():
    """門檻常數與 line-board hooks/contextJudge.ts 一致，防止兩邊漂移"""
    import re
    ts = (_HOOKS_DIR.parent / "skills" / "line-board" / "hooks" / "contextJudge.ts").read_text(encoding="utf-8")
    for name in ("LANE_T_COMPACT", "LANE_T_CLEAR"):
        m = re.search(rf"export const {name} = (\d+)", ts)
        assert m is not None, name
        assert int(m.group(1)) == getattr(_hook, name), name
