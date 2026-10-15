"""測試監控檔依 tool_use_id 分檔（0.5.0-W1-187.13.1）：pre 寫入、post 收尾的交錯情境。"""

import importlib.util
import json
import logging
import os
import sys
import time
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load(filename, name):
    sys.path.insert(0, str(HOOKS_DIR))
    sys.path.insert(0, str(HOOKS_DIR.parent))
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pre_module():
    return _load("test-timeout-pre.py", "test_timeout_pre")


@pytest.fixture(scope="module")
def post_module():
    return _load("post-test-hook.py", "post_test_hook_for_pre_tests")


@pytest.fixture
def env(pre_module, post_module, monkeypatch, tmp_path):
    for module in (pre_module, post_module):
        monkeypatch.setattr(module, "get_project_root", lambda: tmp_path)
    return tmp_path


def _pre(pre_module, monkeypatch, **fields):
    data = {"tool_name": "Bash", **fields}
    monkeypatch.setattr(pre_module, "read_json_from_stdin", lambda _l: data)
    assert pre_module.main() == 0


def _post(post_module, tool_use_id, command, logger):
    data = {"tool_use_id": tool_use_id, "tool_name": "Bash",
            "tool_input": {"command": command}}
    return post_module.check_test_timeout(data, data["tool_input"], logger)


def _history(root):
    path = root / ".claude" / "hook-logs" / "test-duration-history.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def _backdate(root, key, seconds):
    f = root / ".claude" / "hook-logs" / "test-monitor" / f"{key}.json"
    d = json.loads(f.read_text())
    d["start_timestamp"] = time.time() - seconds
    f.write_text(json.dumps(d))


@pytest.fixture
def logger():
    return logging.getLogger("test-timeout-pre-test")


def test_parallel_foreground_each_measures_own_duration(
        pre_module, post_module, env, monkeypatch, logger):
    _pre(pre_module, monkeypatch, tool_use_id="A", tool_input={"command": "pytest a"})
    _backdate(env, "A", 60)
    _pre(pre_module, monkeypatch, tool_use_id="B", tool_input={"command": "pytest b"})
    _post(post_module, "A", "pytest a", logger)
    _post(post_module, "B", "pytest b", logger)
    by_cmd = {r["command"]: r for r in _history(env)}
    assert by_cmd["pytest a"]["duration_seconds"] >= 60
    assert by_cmd["pytest b"]["duration_seconds"] < 30
    assert not list((env / ".claude" / "hook-logs" / "test-monitor").glob("*.json"))


def test_background_pre_between_foreground_pre_and_post(
        pre_module, post_module, env, monkeypatch, logger):
    """243 交接：背景的 pre 落在前景 pre 與 post 之間，前景仍量到自身時長。"""
    _pre(pre_module, monkeypatch, tool_use_id="FG", tool_input={"command": "pytest fg"})
    _backdate(env, "FG", 90)
    _pre(pre_module, monkeypatch, tool_use_id="BG",
         tool_input={"command": "pytest bg", "run_in_background": True})
    _post(post_module, "FG", "pytest fg", logger)
    (record,) = _history(env)
    assert record["command"] == "pytest fg" and record["duration_seconds"] >= 90
    monitor_dir = env / ".claude" / "hook-logs"
    assert not (monitor_dir / "test-monitor" / "BG.json").exists()
    assert not list(monitor_dir.rglob("*.json"))  # 無殘留 running 檔


def test_e1_background_flag_changes_outcome(pre_module, env, monkeypatch):
    """E1 對照：同一批 fixture，前景寫檔、背景不寫。"""
    for key, bg in (("F", False), ("G", True)):
        _pre(pre_module, monkeypatch, tool_use_id=key,
             tool_input={"command": "pytest x", "run_in_background": bg})
    written = {p.stem for p in (env / ".claude" / "hook-logs" / "test-monitor").glob("*.json")}
    assert written == {"F"}


def test_e1_keyed_vs_keyless_under_interleave(
        pre_module, post_module, env, monkeypatch, logger):
    """E1 對照：無鍵（舊單檔）交錯會被覆寫，有鍵不會。"""
    for ids in ({"tool_use_id": "A"}, {}):
        root = env / ("keyed" if ids else "legacy")
        root.mkdir()
        monkeypatch.setattr(pre_module, "get_project_root", lambda r=root: r)
        monkeypatch.setattr(post_module, "get_project_root", lambda r=root: r)
        _pre(pre_module, monkeypatch, **ids, tool_input={"command": "pytest a"})
        if ids:
            _backdate(root, "A", 60)
        else:
            f = root / ".claude" / "hook-logs" / "test-monitor.json"
            d = json.loads(f.read_text()); d["start_timestamp"] -= 60
            f.write_text(json.dumps(d))
        _pre(pre_module, monkeypatch, **({"tool_use_id": "B"} if ids else {}),
             tool_input={"command": "pytest b"})
        data = {**ids, "tool_name": "Bash", "tool_input": {"command": "pytest a"}}
        post_module.check_test_timeout(data, data["tool_input"], logger)
    keyed = _history(env / "keyed")[0]
    legacy = _history(env / "legacy")[0]
    assert keyed["duration_seconds"] >= 60 and keyed["command"] == "pytest a"
    assert legacy["duration_seconds"] < 30 and legacy["command"] == "pytest b"


def test_session_id_fallback_and_legacy_file_readable(
        pre_module, post_module, env, monkeypatch, logger):
    _pre(pre_module, monkeypatch, session_id="s/1", tool_input={"command": "pytest"})
    assert (env / ".claude" / "hook-logs" / "test-monitor" / "s_1.json").exists()
    legacy = env / ".claude" / "hook-logs" / "test-monitor.json"
    legacy.write_text(json.dumps({"start_timestamp": time.time() - 5,
                                  "command": "old", "status": "running"}))
    # 無鍵的 post 讀 running 舊單檔
    msg = post_module.check_test_timeout({}, {}, logger)
    assert msg and json.loads(legacy.read_text())["status"] == "completed"


def _arm_legacy(root, status):
    f = root / ".claude" / "hook-logs" / "test-monitor.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"start_timestamp": time.time() - 5000,
                             "command": "old", "status": status}))
    return f


@pytest.mark.parametrize("status", ["running", "completed"])
def test_keyed_post_with_missing_keyfile_ignores_legacy(
        post_module, env, logger, status):
    """有鍵但鍵檔不存在：不論舊單檔狀態都不計時、不寫 history、舊單檔不動。"""
    legacy = _arm_legacy(env, status)
    before = legacy.read_text()
    assert post_module.check_test_timeout({"tool_use_id": "gone"}, {}, logger) is None
    assert legacy.read_text() == before
    assert not (env / ".claude" / "hook-logs" / "test-duration-history.jsonl").exists()


def test_keyless_post_uses_legacy_only_when_running(post_module, env, logger):
    """E1：同一個舊單檔，無鍵時 running 採用、completed 跳過。"""
    _arm_legacy(env, "completed")
    assert post_module.check_test_timeout({}, {}, logger) is None
    assert not (env / ".claude" / "hook-logs" / "test-duration-history.jsonl").exists()
    _arm_legacy(env, "running")
    assert post_module.check_test_timeout({}, {}, logger) is not None
    assert len(_history(env)) == 1


def _make_keyfile(root, key, age_seconds):
    f = root / ".claude" / "hook-logs" / "test-monitor" / f"{key}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("{}")
    stamp = time.time() - age_seconds
    os.utime(f, (stamp, stamp))
    return f


def test_pre_prunes_stale_keyfiles_but_keeps_fresh_and_legacy(
        pre_module, env, monkeypatch):
    from lib.test_monitor_path import STALE_KEYFILE_SECONDS
    stale = _make_keyfile(env, "old", STALE_KEYFILE_SECONDS + 60)
    fresh = _make_keyfile(env, "fresh", STALE_KEYFILE_SECONDS - 60)
    legacy = _arm_legacy(env, "running")
    _pre(pre_module, monkeypatch, tool_use_id="new", tool_input={"command": "pytest x"})
    assert not stale.exists()
    assert fresh.exists()  # E2：門檻內的新鍵檔不被刪
    assert legacy.exists()
    assert (env / ".claude" / "hook-logs" / "test-monitor" / "new.json").exists()


def test_keyless_pre_does_not_prune(pre_module, env, monkeypatch):
    from lib.test_monitor_path import STALE_KEYFILE_SECONDS
    stale = _make_keyfile(env, "old", STALE_KEYFILE_SECONDS + 60)
    _pre(pre_module, monkeypatch, tool_input={"command": "pytest x"})
    assert stale.exists()


def test_prune_failure_is_fail_open(pre_module, env, monkeypatch):
    import lib.test_monitor_path as tmp_mod

    def boom(self):
        raise OSError("denied")
    _make_keyfile(env, "old", tmp_mod.STALE_KEYFILE_SECONDS + 60)
    monkeypatch.setattr(Path, "unlink", boom)
    assert tmp_mod.prune_stale_keyed_files(env) == 0
