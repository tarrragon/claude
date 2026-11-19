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


@pytest.fixture(autouse=True)
def session_names(monkeypatch):
    """session 名稱解析改為假的：預設為一般線（None）。

    真實解析會讀 ~/.claude/sessions 並沿父行程找 claude 祖先，跑測試的 session 若名為「主控」，
    結果就會隨執行者改變；呼叫紀錄供斷言「未達門檻時不解析名稱」。
    """
    state = {"name": None, "calls": 0}

    def fake(session_id):
        state["calls"] += 1
        return state["name"]

    monkeypatch.setattr(_hook, "session_name", fake, raising=False)
    return state


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
    for name in ("LANE_T_COMPACT", "LANE_T_CLEAR", "COORDINATOR_T_COMPACT"):
        m = re.search(rf"export const {name} = (\d+)", ts)
        assert m is not None, name
        assert int(m.group(1)) == getattr(_hook, name), name


def test_master_name_matches_line_board_coordinator_name():
    """主控名稱與 line-board resumeNotice.ts 的 COORDINATOR_SESSION_NAME 一致"""
    import re
    ts = (_HOOKS_DIR.parent / "skills" / "line-board" / "hooks" / "resumeNotice.ts").read_text(encoding="utf-8")
    m = re.search(r"export const COORDINATOR_SESSION_NAME = '([^']+)'", ts)
    assert m is not None
    assert m.group(1) == _hook.MASTER_NAME


# ============================================================================
# 主控 session：門檻 60%、不判 /clear（同 line-board contextMarkOf 的 coordinator 分支）
# ============================================================================

@pytest.mark.parametrize("percent, lane_expect, coordinator_expect", [
    (25, None, None),          # 未達任何門檻
    (35, "/clear", None),      # 一般線提示 /clear；主控不判待 clear
    (50, "/compact", None),    # 一般線達 45%；主控未達 60%
    (65, "/compact", "/compact"),
])
def test_e1_coordinator_vs_lane_same_usage(monkeypatch, capsys, counter, usage_dir, session_names,
                                           percent, lane_expect, coordinator_expect):
    """E1：同一份用量檔，名稱為「主控」與一般線各跑一次，結果對應 contextMarkOf 的兩個分支"""
    _write_usage(usage_dir, percent)
    lane = _complete_with_session(monkeypatch, capsys)
    session_names["name"] = _hook.MASTER_NAME
    coordinator = _complete_with_session(monkeypatch, capsys)
    for text, expect in ((lane, lane_expect), (coordinator, coordinator_expect)):
        if expect is None:
            assert text == ""
        else:
            assert expect in text and f"{percent}%" in text


def test_coordinator_warning_names_coordinator_threshold(monkeypatch, capsys, counter, usage_dir, session_names):
    session_names["name"] = _hook.MASTER_NAME
    _write_usage(usage_dir, 61)
    text = _complete_with_session(monkeypatch, capsys)
    assert f"（{_hook.COORDINATOR_T_COMPACT}%）" in text
    assert "/clear" not in text


def test_session_name_not_resolved_below_clear_threshold(monkeypatch, capsys, counter, usage_dir, session_names):
    """未達 LANE_T_CLEAR 時兩種角色都不提醒，不解析名稱（名稱解析要跑 ps）"""
    _write_usage(usage_dir, 20)
    assert _complete_with_session(monkeypatch, capsys) == ""
    assert session_names["calls"] == 0
    _write_usage(usage_dir, 40)
    _complete_with_session(monkeypatch, capsys)
    assert session_names["calls"] == 1


def test_name_resolution_exception_falls_back_to_lane(monkeypatch, capsys, counter, usage_dir):
    """名稱解析拋例外時判為一般線：50% 仍提醒 /compact（45%），不因例外而靜默"""
    def boom(session_id):
        raise AttributeError("injected")

    monkeypatch.setattr(_hook, "session_name", boom)
    _write_usage(usage_dir, 50)
    text = _complete_with_session(monkeypatch, capsys)
    assert "/compact" in text and f"（{_hook.LANE_T_COMPACT}%）" in text


def test_count_fallback_unchanged_for_coordinator(monkeypatch, capsys, counter, usage_dir, session_names):
    """沒有用量檔時退回票數判定，不分角色（line-board 沒有用量檔時不標，guard 的票數路徑是另一條來源）"""
    session_names["name"] = _hook.MASTER_NAME
    counter.write_text("2")
    assert "以票數估計" in _complete_with_session(monkeypatch, capsys)
    assert session_names["calls"] == 0


# ============================================================================
# SessionStart source=compact：計數器重新起算（沒有用量檔的 session 走票數路徑）
# ============================================================================

def _session_start(monkeypatch, capsys, source):
    """以 SessionStart 事件跑一次，回傳 (結束碼, stdout)。"""
    payload = {"session_id": SESSION_ID, "hook_event_name": "SessionStart", "source": source}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    rc = _hook.main()
    return rc, capsys.readouterr().out


@pytest.mark.parametrize("source, expect_warning", [
    ("compact", False),   # compact 後重新起算：第 1 張票不提醒
    ("resume", True),     # 對照：同票數、非 compact 來源，計數延續，照常提醒
    ("startup", True),
])
def test_e1_compact_resets_count_same_prior_count(monkeypatch, capsys, counter, usage_dir, source, expect_warning):
    """E1：compact 前同為 4 張；source=compact 後第 1 張不提醒，其他來源第 5 張照常提醒"""
    counter.write_text("4")
    rc, out = _session_start(monkeypatch, capsys, source)
    assert rc == 0
    assert "additionalContext" not in out
    text = _complete_with_session(monkeypatch, capsys)
    assert ("以票數估計" in text) is expect_warning
    assert _count(counter) == (5 if expect_warning else 1)


def test_compact_reset_still_warns_after_enough_tickets(monkeypatch, capsys, counter, usage_dir):
    """正向對照：compact 歸零後再完成到 SOFT_WARN_THRESHOLD 張，仍會提醒"""
    counter.write_text("4")
    _session_start(monkeypatch, capsys, "compact")
    texts = [_complete_with_session(monkeypatch, capsys) for _ in range(_hook.SOFT_WARN_THRESHOLD)]
    assert texts[0] == ""
    assert "以票數估計" in texts[-1]


def test_compact_reset_unlink_failure_keeps_count(monkeypatch, capsys, counter, usage_dir, caplog):
    """刪除計數檔失敗時記 warning、保留原計數，結束碼 0"""
    counter.write_text("4")
    real_unlink = Path.unlink

    def failing_unlink(self, *args, **kwargs):
        if self == counter:
            raise PermissionError("injected")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    warnings = []
    monkeypatch.setattr(_hook, "setup_hook_logging", lambda name: _RecordingLogger(warnings))
    rc, _ = _session_start(monkeypatch, capsys, "compact")
    assert rc == 0
    assert counter.read_text() == "4"
    assert any("計數器" in w for w in warnings)


def test_compact_reset_without_counter_file_is_quiet(monkeypatch, capsys, counter, usage_dir):
    assert not counter.exists()
    rc, out = _session_start(monkeypatch, capsys, "compact")
    assert rc == 0 and "additionalContext" not in out


class _RecordingLogger:
    def __init__(self, warnings):
        self._warnings = warnings

    def warning(self, msg, *args):
        self._warnings.append(msg % args if args else msg)

    def __getattr__(self, name):
        return lambda *a, **k: None


def test_settings_registers_guard_on_session_start_compact():
    """settings.json 的 SessionStart 有 matcher compact 的群組執行本 hook（接線測試）"""
    settings = json.loads((_HOOKS_DIR.parent / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in settings["hooks"]["SessionStart"]
        if group.get("matcher") == "compact"
        for hook in group["hooks"]
    ]
    assert any("hooks/session-context-guard-hook.py" in c for c in commands)
