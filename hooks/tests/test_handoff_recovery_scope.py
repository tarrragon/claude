"""handoff 恢復模式放行範圍限縮測試（兩支派發守衛 + 共用集合函式）。

背景：殘留的 pending handoff 檔使派發守衛整體放行。限縮後只有 prompt 引用
handoff 指向的 ticket（來源或目標）時才放行。

| 測試 | 場景 | 驗證 |
|------|------|------|
| E1 | prompt 引用 handoff 指向的票 | 放行（rc=0） |
| E2 | 殘留檔指向不存在的票 + prompt 缺 Ticket 行 | validation 守衛 rc=2；readiness 守衛 stdout deny |
| 集合函式 | 來源 + 目標、損壞檔、無目錄 | 回傳集合正確 |
"""

from __future__ import annotations

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
VALIDATION_HOOK = CLAUDE_DIR / "skills" / "ticket" / "hooks" / "agent-ticket-validation-hook.py"
READINESS_HOOK = HOOKS_DIR / "task-dispatch-readiness-check.py"

SRC_ID = "demo-src"
TGT_ID = "demo-tgt"


def _make_root(tmp_path: Path, records=None) -> Path:
    if records:
        pending = tmp_path / ".claude" / "handoff" / "pending"
        pending.mkdir(parents=True)
        for name, rec in records.items():
            (pending / name).write_text(json.dumps(rec), encoding="utf-8")
    return tmp_path


def _stale_record():
    return {"ticket_id": SRC_ID, "target_ticket_id": TGT_ID}


def _run_validation_full(root: Path, prompt: str):
    payload = {
        "tool_name": "Agent",
        "tool_input": {"prompt": prompt, "subagent_type": "thyme-python-developer"},
    }
    env = dict(os.environ, HOOK_TEST_ISOLATION="1", CLAUDE_PROJECT_DIR=str(root))
    return subprocess.run(
        [sys.executable, str(VALIDATION_HOOK)],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
    )


def _run_validation(root: Path, prompt: str) -> int:
    payload = {
        "tool_name": "Agent",
        "tool_input": {"prompt": prompt, "subagent_type": "thyme-python-developer"},
    }
    env = dict(os.environ, HOOK_TEST_ISOLATION="1", CLAUDE_PROJECT_DIR=str(root))
    proc = subprocess.run(
        [sys.executable, str(VALIDATION_HOOK)],
        input=json.dumps(payload), capture_output=True, text=True, env=env,
    )
    return proc.returncode


def _run_readiness(monkeypatch, capsys, root: Path, prompt: str, agent: str) -> str:
    """回傳 stdout；守衛以 stdout deny JSON（rc=0）表達攔截，無輸出表示放行。"""
    spec = importlib.util.spec_from_file_location("readiness_scope_mod", READINESS_HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # 須在隔離環境變數生效前，以真實專案根載入設定（同 test_agent_dispatch_check 的 config fixture）
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(CLAUDE_DIR.parent))
    from lib.config_loader import load_agents_config, clear_config_cache
    clear_config_cache()
    cfg = dict(load_agents_config())
    assert "task_type_priorities" in cfg, "測試前提：設定檔須載入成功"
    cfg.pop("agent_to_task_map", None)  # 強制走關鍵字偵測，才有可攔截的錯誤分派
    monkeypatch.setenv("HOOK_TEST_ISOLATION", "1")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setenv("HOOK_MODE", "strict")
    monkeypatch.setattr(mod, "load_agents_config", lambda: cfg)
    payload = {"tool_name": "Agent", "tool_input": {"prompt": prompt, "subagent_type": agent}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    _LAST_ERR[0] = captured.err
    return captured.out


_LAST_ERR = [""]
WRONG_AGENT_PROMPT = "開發 Hook 腳本來檢查代理人分派"
WRONG_AGENT = "parsley-flutter-developer"


class TestValidationHookScope:
    def test_e2_stale_handoff_missing_ticket_line_blocked(self, tmp_path):
        root = _make_root(tmp_path, {"x.json": _stale_record()})
        assert _run_validation(root, "恢復任務，沒有 Ticket 行") == 2

    def test_e2_prompt_references_unrelated_ticket_not_bypassed(self, tmp_path):
        root = _make_root(tmp_path, {"x.json": _stale_record()})
        assert _run_validation(root, "Ticket: demo-other 做事") == 2

    def test_e1_prompt_references_target_ticket_allowed(self, tmp_path):
        root = _make_root(tmp_path, {"x.json": _stale_record()})
        assert _run_validation(root, "Ticket: {} 恢復".format(TGT_ID)) == 0

    def test_e1_prompt_references_source_ticket_allowed(self, tmp_path):
        root = _make_root(tmp_path, {"x.json": _stale_record()})
        assert _run_validation(root, "Ticket: {} 恢復".format(SRC_ID)) == 0

    def test_child_id_does_not_match_parent_handoff(self, tmp_path):
        root = _make_root(tmp_path, {"x.json": _stale_record()})
        assert _run_validation(root, "Ticket: {}.1 子票".format(TGT_ID)) == 2


class TestReadinessHookScope:
    def test_e2_stale_handoff_missing_ticket_line_blocked(self, tmp_path, monkeypatch, capsys):
        root = _make_root(tmp_path, {"x.json": _stale_record()})
        out = _run_readiness(monkeypatch, capsys, root, WRONG_AGENT_PROMPT, WRONG_AGENT)
        assert '"permissionDecision": "deny"' in out

    def test_e1_prompt_references_handoff_ticket_allowed(self, tmp_path, monkeypatch, capsys):
        root = _make_root(tmp_path, {"x.json": _stale_record()})
        prompt = "Ticket: {}\n{}".format(TGT_ID, WRONG_AGENT_PROMPT)
        out = _run_readiness(monkeypatch, capsys, root, prompt, WRONG_AGENT)
        assert "deny" not in out

    def test_control_without_handoff_is_denied(self, tmp_path, monkeypatch, capsys):
        """對照：無殘留檔時同一 payload 本就被攔，證明 E2 的 deny 來自守衛判準而非 payload 假象。"""
        out = _run_readiness(monkeypatch, capsys, tmp_path, WRONG_AGENT_PROMPT, WRONG_AGENT)
        assert '"permissionDecision": "deny"' in out


class TestSharedSetFunction:
    def test_returns_source_and_target(self, tmp_path):
        from lib.hook_io import get_handoff_recovery_ticket_ids
        root = _make_root(tmp_path, {"x.json": _stale_record()})
        assert get_handoff_recovery_ticket_ids(project_root=root) == {SRC_ID, TGT_ID}

    def test_missing_dir_and_broken_json(self, tmp_path):
        from lib.hook_io import get_handoff_recovery_ticket_ids
        assert get_handoff_recovery_ticket_ids(project_root=tmp_path) == set()
        pending = tmp_path / ".claude" / "handoff" / "pending"
        pending.mkdir(parents=True)
        (pending / "bad.json").write_text("{nope", encoding="utf-8")
        assert get_handoff_recovery_ticket_ids(project_root=tmp_path) == set()

    def test_direction_suffix_target_included_when_no_explicit_target(self, tmp_path):
        """一般 handoff 僅以 direction 後綴表達目標（無 target_ticket_id 欄位）。"""
        from lib.hook_io import get_handoff_recovery_ticket_ids
        rec = {"ticket_id": SRC_ID, "direction": "to-sibling:{}".format(TGT_ID)}
        root = _make_root(tmp_path, {"x.json": rec})
        assert get_handoff_recovery_ticket_ids(project_root=root) == {SRC_ID, TGT_ID}
        rec2 = {"ticket_id": SRC_ID, "direction": "to-parent"}
        root2 = _make_root(tmp_path / "b", {"x.json": rec2})
        assert get_handoff_recovery_ticket_ids(project_root=root2) == {SRC_ID}


SIGNAL_TAG = "[handoff-recovery]"


class TestRecoveryAllowSignal:
    """放行當下輸出一行可見訊號（stderr）：含命中的 pending 檔名與指向票；未命中則無額外輸出。"""

    def test_e2_validation_signal_has_filename_and_ticket(self, tmp_path):
        root = _make_root(tmp_path, {"stale-x.json": _stale_record()})
        proc = _run_validation_full(root, "Ticket: {} 恢復".format(TGT_ID))
        assert proc.returncode == 0
        assert SIGNAL_TAG in proc.stderr
        assert "stale-x.json" in proc.stderr
        assert TGT_ID in proc.stderr

    def test_e1_validation_no_signal_when_not_matched(self, tmp_path):
        root = _make_root(tmp_path, {"stale-x.json": _stale_record()})
        proc = _run_validation_full(root, "Ticket: demo-other 做事")
        assert SIGNAL_TAG not in proc.stderr
        assert "stale-x.json" not in proc.stderr

    def test_e2_readiness_signal_has_filename_and_ticket(self, tmp_path, monkeypatch, capsys):
        root = _make_root(tmp_path, {"stale-x.json": _stale_record()})
        prompt = "Ticket: {}\n{}".format(TGT_ID, WRONG_AGENT_PROMPT)
        _run_readiness(monkeypatch, capsys, root, prompt, WRONG_AGENT)
        err = _LAST_ERR[0]
        assert SIGNAL_TAG in err and "stale-x.json" in err and TGT_ID in err

    def test_e1_readiness_no_signal_without_pending(self, tmp_path, monkeypatch, capsys):
        _run_readiness(monkeypatch, capsys, tmp_path, "沒有票的 prompt", "thyme-python-developer")
        assert SIGNAL_TAG not in _LAST_ERR[0]

    def test_find_hits_returns_filename_ticket_pairs(self, tmp_path):
        from lib.hook_io import find_handoff_recovery_hits
        root = _make_root(tmp_path, {"stale-x.json": _stale_record()})
        hits = find_handoff_recovery_hits("Ticket: {}".format(TGT_ID), project_root=root)
        assert hits == [("stale-x.json", TGT_ID)]
        assert find_handoff_recovery_hits("無關", project_root=root) == []

    def test_signal_write_failure_keeps_allow_decision(self, tmp_path, monkeypatch):
        """失敗語意：stderr 不可寫時不拋例外，命中判定（放行）不變。"""
        from lib.hook_io import emit_handoff_recovery_signal

        class _BrokenErr:
            def write(self, _):
                raise OSError("closed")

        root = _make_root(tmp_path, {"stale-x.json": _stale_record()})
        monkeypatch.setattr(sys, "stderr", _BrokenErr())
        assert emit_handoff_recovery_signal("Ticket: {}".format(TGT_ID), project_root=root) is True

    def test_broken_pending_file_yields_no_signal(self, tmp_path, capsys):
        from lib.hook_io import emit_handoff_recovery_signal
        pending = tmp_path / ".claude" / "handoff" / "pending"
        pending.mkdir(parents=True)
        (pending / "bad.json").write_text("{nope", encoding="utf-8")
        assert emit_handoff_recovery_signal("Ticket: {}".format(TGT_ID), project_root=tmp_path) is False
        assert SIGNAL_TAG not in capsys.readouterr().err
