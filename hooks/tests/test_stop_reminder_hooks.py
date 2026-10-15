"""Stop 提醒類 hook 的模型可見輸出測試。

涵蓋 session-experience-persistence-reminder 與 evaluate-session：
- 有提醒時輸出單一 JSON，Stop 的 hookSpecificOutput.additionalContext
- stop_hook_active 為真時不輸出提醒（避免續跑後無限迴圈）
- 提醒不再走 stderr
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
EVAL_SCRIPT = CLAUDE_DIR / "skills" / "continuous-learning" / "evaluate-session.py"
REMINDER_PATH = HOOKS_DIR / "session-experience-persistence-reminder-hook.py"

sys.path.insert(0, str(CLAUDE_DIR))


def _load_reminder_module():
    spec = importlib.util.spec_from_file_location("persistence_reminder_hook", REMINDER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(module, monkeypatch, capsys, payload, reminder):
    """以假 stdin 與假掃描結果執行 main，回傳 (exit_code, stdout, stderr)。"""
    calls = []

    def fake_build(logger, session_id=""):
        calls.append(1)
        return reminder

    monkeypatch.setattr(module, "build_reminder", fake_build)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    code = module.main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err, calls


class TestPersistenceReminder:
    def test_reminder_emitted_as_stop_additional_context(self, monkeypatch, capsys):
        module = _load_reminder_module()
        code, out, err, _ = _run_main(module, monkeypatch, capsys, {}, "提醒本文 XYZ")
        assert code == 0
        data = json.loads(out)  # 必須只有一份 JSON
        hso = data["hookSpecificOutput"]
        assert hso["hookEventName"] == "Stop"
        assert "提醒本文 XYZ" in hso["additionalContext"]
        assert "提醒本文 XYZ" not in err
        assert "decision" not in data

    def test_stop_hook_active_true_emits_no_reminder(self, monkeypatch, capsys):
        module = _load_reminder_module()
        code, out, err, calls = _run_main(
            module, monkeypatch, capsys, {"stop_hook_active": True}, "提醒本文 XYZ"
        )
        assert code == 0
        assert "additionalContext" not in out
        assert "提醒本文" not in out + err
        assert calls == [], "stop_hook_active 為真時不應再掃描"

    def test_no_reminder_stays_silent(self, monkeypatch, capsys):
        module = _load_reminder_module()
        code, out, err, _ = _run_main(module, monkeypatch, capsys, {}, None)
        assert code == 0
        assert "additionalContext" not in out
        assert err == ""


def _tk(tid):
    return {"id": tid, "title": f"title-{tid}", "type": "ANA"}


def _run_throttled(module, monkeypatch, capsys, tmp_path, payload, tickets):
    """假掃描清單 + 假狀態目錄，走真實節流邏輯，回傳 stdout 解析結果（無輸出為 None）。"""
    monkeypatch.setattr(module, "scan_tickets", lambda logger: tickets)
    monkeypatch.setattr(module, "get_state_dir", lambda: tmp_path / "hook-state")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert module.main() == 0
    data = json.loads(capsys.readouterr().out)
    return data.get("hookSpecificOutput", {}).get("additionalContext")


class TestPersistenceReminderThrottle:
    def test_same_session_same_list_second_stop_silent(self, monkeypatch, capsys, tmp_path):
        module = _load_reminder_module()
        tickets = [_tk("A-1"), _tk("A-2")]
        first = _run_throttled(module, monkeypatch, capsys, tmp_path, {"session_id": "s1"}, tickets)
        assert first and "A-1" in first and "A-2" in first
        state = json.loads((tmp_path / "hook-state" / "persistence-reminder-s1.json").read_text())
        assert state["notified_ids"] == ["A-1", "A-2"]
        second = _run_throttled(module, monkeypatch, capsys, tmp_path, {"session_id": "s1"}, tickets)
        assert second is None

    def test_new_ticket_lists_only_the_new_one(self, monkeypatch, capsys, tmp_path):
        module = _load_reminder_module()
        _run_throttled(module, monkeypatch, capsys, tmp_path, {"session_id": "s1"}, [_tk("A-1"), _tk("A-2")])
        out = _run_throttled(
            module, monkeypatch, capsys, tmp_path, {"session_id": "s1"},
            [_tk("A-1"), _tk("A-2"), _tk("A-3")],
        )
        assert out and "A-3" in out
        assert "A-1" not in out and "A-2" not in out
        state = json.loads((tmp_path / "hook-state" / "persistence-reminder-s1.json").read_text())
        assert state["notified_ids"] == ["A-1", "A-2", "A-3"]

    def test_different_sessions_each_reminded(self, monkeypatch, capsys, tmp_path):
        module = _load_reminder_module()
        tickets = [_tk("A-1")]
        a = _run_throttled(module, monkeypatch, capsys, tmp_path, {"session_id": "s1"}, tickets)
        b = _run_throttled(module, monkeypatch, capsys, tmp_path, {"session_id": "s2"}, tickets)
        assert a and "A-1" in a and b and "A-1" in b
        assert (tmp_path / "hook-state" / "persistence-reminder-s1.json").exists()
        assert (tmp_path / "hook-state" / "persistence-reminder-s2.json").exists()

    def test_stop_hook_active_silent_and_no_state(self, monkeypatch, capsys, tmp_path):
        module = _load_reminder_module()
        out = _run_throttled(
            module, monkeypatch, capsys, tmp_path,
            {"session_id": "s1", "stop_hook_active": True}, [_tk("A-1")],
        )
        assert out is None
        assert not (tmp_path / "hook-state").exists()

    def test_missing_session_id_reminds_every_time_without_state(self, monkeypatch, capsys, tmp_path):
        module = _load_reminder_module()
        tickets = [_tk("A-1")]
        assert _run_throttled(module, monkeypatch, capsys, tmp_path, {}, tickets)
        assert _run_throttled(module, monkeypatch, capsys, tmp_path, {}, tickets)
        assert not (tmp_path / "hook-state").exists()

    def test_corrupt_state_fails_open(self, monkeypatch, capsys, tmp_path):
        module = _load_reminder_module()
        d = tmp_path / "hook-state"
        d.mkdir()
        (d / "persistence-reminder-s1.json").write_text("{not json")
        out = _run_throttled(module, monkeypatch, capsys, tmp_path, {"session_id": "s1"}, [_tk("A-1")])
        assert out and "A-1" in out

    def test_session_id_sanitized_in_filename(self, monkeypatch, capsys, tmp_path):
        module = _load_reminder_module()
        _run_throttled(module, monkeypatch, capsys, tmp_path, {"session_id": "../x/y"}, [_tk("A-1")])
        files = [p.name for p in (tmp_path / "hook-state").iterdir()]
        assert files == ["persistence-reminder-___x_y.json"]


def _run_eval(tmp_path, payload, with_transcript_path=True, transcript_exists=True):
    """payload 形狀以實測 Stop payload 為準：transcript_path 為檔案路徑，平台不設
    CLAUDE_TRANSCRIPT_PATH 環境變數（測試中明確移除，防止舊來源假綠）。"""
    transcript = tmp_path / "t.jsonl"
    if transcript_exists:
        transcript.write_text('{"type":"user"}\n' * 60, encoding="utf-8")
    payload = dict(payload)
    if with_transcript_path:
        payload["transcript_path"] = str(transcript)
    env = os.environ.copy()
    env.pop("CLAUDE_TRANSCRIPT_PATH", None)
    return subprocess.run(
        ["python3", str(EVAL_SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(tmp_path),
        env=env,
    )


class TestEvaluateSession:
    def test_long_session_emits_additional_context(self, tmp_path):
        proc = _run_eval(tmp_path, {})
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        hso = data["hookSpecificOutput"]
        assert hso["hookEventName"] == "Stop"
        assert "[ContinuousLearning]" in hso["additionalContext"]
        assert "[ContinuousLearning]" not in proc.stderr

    def test_no_transcript_path_emits_nothing(self, tmp_path):
        """對照組：payload 無 transcript_path → 不輸出（fail-open）。"""
        proc = _run_eval(tmp_path, {}, with_transcript_path=False)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == ""

    def test_transcript_file_missing_fails_open(self, tmp_path):
        """對照組：transcript_path 指向不存在檔案 → exit 0、不輸出。"""
        proc = _run_eval(tmp_path, {}, transcript_exists=False)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == ""

    def test_stop_hook_active_true_emits_nothing(self, tmp_path):
        proc = _run_eval(tmp_path, {"stop_hook_active": True})
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == ""
        assert "[ContinuousLearning]" not in proc.stderr
