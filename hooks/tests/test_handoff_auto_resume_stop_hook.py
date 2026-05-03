"""
handoff-auto-resume-stop-hook tests.

W17-095.2：驗證 should_preserve_pending_json 引用 is_handoff_stale 後的行為，
覆蓋 5 個情境（任務鏈目標已啟動 / 已完成 / 仍 pending；非任務鏈來源已完成 / 仍 pending）。
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock


HOOK_PATH = Path(__file__).parent.parent / "handoff-auto-resume-stop-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "handoff_auto_resume_stop_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patch_is_handoff_stale(monkeypatch, return_value):
    """以 monkeypatch 替換 module 的 is_handoff_stale，避開實際 ticket fs 依賴。"""
    hook = load_hook_module()
    monkeypatch.setattr(hook, "is_handoff_stale", lambda record: return_value)
    return hook


def test_task_chain_target_in_progress_should_not_preserve(monkeypatch):
    """任務鏈方向 + 目標已 in_progress → stale → return False（GC）。"""
    hook = _patch_is_handoff_stale(
        monkeypatch, (True, "任務鏈目標 0.18.0-W17-002 已 in_progress")
    )
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "to-sibling:0.18.0-W17-002",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is False


def test_task_chain_target_completed_should_not_preserve(monkeypatch):
    """任務鏈方向 + 目標已 completed → stale → return False（GC）。"""
    hook = _patch_is_handoff_stale(
        monkeypatch, (True, "任務鏈目標 0.18.0-W17-002 已 completed")
    )
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "to-sibling:0.18.0-W17-002",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is False


def test_task_chain_target_pending_should_preserve(monkeypatch):
    """任務鏈方向 + 目標仍 pending → 非 stale → return True（保留）。"""
    hook = _patch_is_handoff_stale(monkeypatch, (False, ""))
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "to-sibling:0.18.0-W17-002",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is True


def test_non_chain_with_completed_source_should_not_preserve(monkeypatch):
    """非任務鏈方向 + 來源 ticket 已 completed → stale → return False。"""
    hook = _patch_is_handoff_stale(
        monkeypatch, (True, "來源 ticket 0.18.0-W17-001 已 completed")
    )
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "context_refresh",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is False


def test_non_chain_pending_should_preserve(monkeypatch):
    """非任務鏈方向 + 來源仍 pending → 非 stale → return True。"""
    hook = _patch_is_handoff_stale(monkeypatch, (False, ""))
    record = {
        "ticket_id": "0.18.0-W17-001",
        "direction": "context_refresh",
    }
    assert hook.should_preserve_pending_json(record, MagicMock()) is True
