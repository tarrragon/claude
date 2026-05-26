"""
install-guide-edit-reminder-hook tests (PC-159 Hook 層防護)

驗證觸發條件、節流、非匹配跳過、reminder 訊息內容。
"""

import importlib.util
import json
import time
from pathlib import Path
from unittest.mock import MagicMock


HOOK_PATH = Path(__file__).parent.parent / "install-guide-edit-reminder-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "install_guide_edit_reminder_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# === is_install_guide_path ===


def test_matches_development_setup():
    hook = load_hook_module()
    assert hook.is_install_guide_path("docs/development-setup.md") is True


def test_matches_environment_recovery_guide():
    hook = load_hook_module()
    assert hook.is_install_guide_path("docs/environment-recovery-guide.md") is True


def test_matches_absolute_path():
    hook = load_hook_module()
    assert hook.is_install_guide_path(
        "/Users/x/project/docs/development-setup.md"
    ) is True


def test_does_not_match_unrelated_file():
    hook = load_hook_module()
    assert hook.is_install_guide_path("src/foo.js") is False
    assert hook.is_install_guide_path("docs/struct.md") is False
    assert hook.is_install_guide_path("") is False


def test_case_insensitive():
    hook = load_hook_module()
    assert hook.is_install_guide_path("docs/Development-Setup.md") is True


# === throttle ===


def test_is_throttled_no_prior():
    hook = load_hook_module()
    assert hook.is_throttled("a.md", {}, time.time()) is False


def test_is_throttled_within_window():
    hook = load_hook_module()
    now = time.time()
    cache = {"a.md": now - 10}
    assert hook.is_throttled("a.md", cache, now) is True


def test_is_throttled_outside_window():
    hook = load_hook_module()
    now = time.time()
    cache = {"a.md": now - hook.THROTTLE_SECONDS - 10}
    assert hook.is_throttled("a.md", cache, now) is False


def test_prune_expired_removes_old_entries():
    hook = load_hook_module()
    now = time.time()
    cache = {
        "fresh.md": now - 10,
        "stale.md": now - hook.THROTTLE_SECONDS - 100,
    }
    pruned = hook.prune_expired(cache, now)
    assert "fresh.md" in pruned
    assert "stale.md" not in pruned


# === emit_reminder ===


def test_emit_reminder_writes_to_stderr(capsys):
    hook = load_hook_module()
    hook.emit_reminder("docs/development-setup.md", MagicMock())
    captured = capsys.readouterr()
    assert "install-guide-reminder" in captured.err
    assert "fresh shell" in captured.err
    assert "development-setup.md" in captured.err
    assert "PC-159" in captured.err


# === main flow ===


def test_main_skips_non_edit_write_tool(monkeypatch, capsys):
    hook = load_hook_module()
    payload = json.dumps({"tool_name": "Bash", "tool_input": {}})
    monkeypatch.setattr("sys.stdin", _StringIO(payload))
    rc = hook.main()
    assert rc == 0
    assert "install-guide-reminder" not in capsys.readouterr().err


def test_main_skips_non_install_guide_file(monkeypatch, capsys):
    hook = load_hook_module()
    payload = json.dumps(
        {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.js"}}
    )
    monkeypatch.setattr("sys.stdin", _StringIO(payload))
    rc = hook.main()
    assert rc == 0
    assert "install-guide-reminder" not in capsys.readouterr().err


def test_main_emits_reminder_for_install_guide(monkeypatch, tmp_path, capsys):
    hook = load_hook_module()
    # 重定向節流檔到 tmp 避免污染 hook-logs
    monkeypatch.setattr(hook, "THROTTLE_FILE", tmp_path / "throttle.json")
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": "docs/development-setup.md"},
        }
    )
    monkeypatch.setattr("sys.stdin", _StringIO(payload))
    rc = hook.main()
    assert rc == 0
    err = capsys.readouterr().err
    assert "install-guide-reminder" in err
    assert "development-setup.md" in err


def test_main_throttles_second_call(monkeypatch, tmp_path, capsys):
    hook = load_hook_module()
    monkeypatch.setattr(hook, "THROTTLE_FILE", tmp_path / "throttle.json")
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {"file_path": "docs/development-setup.md"},
        }
    )
    # 第一次
    monkeypatch.setattr("sys.stdin", _StringIO(payload))
    hook.main()
    capsys.readouterr()  # 清空
    # 第二次（應被節流）
    monkeypatch.setattr("sys.stdin", _StringIO(payload))
    rc = hook.main()
    assert rc == 0
    assert "install-guide-reminder" not in capsys.readouterr().err


class _StringIO:
    """Minimal stdin replacement supporting .read()."""

    def __init__(self, data: str):
        self._data = data

    def read(self) -> str:
        return self._data
