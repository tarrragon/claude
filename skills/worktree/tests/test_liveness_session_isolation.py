"""worktree 套件的 liveness 隔離：session id 替換、還原與洩漏哨兵（E2 正向對照）。"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import liveness_session_isolation as iso

CONFTEST_PATH = Path(__file__).resolve().parent / "conftest.py"


def _fresh_conftest():
    """載入獨立的 conftest 模組副本，避免動到執行中套件的 _SENTINEL 狀態。"""
    spec = importlib.util.spec_from_file_location("_worktree_conftest_copy", CONFTEST_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_session_uses_pytest_prefix():
    assert os.environ[iso.ENV_SESSION_ID].startswith(iso.SESSION_ID_PREFIX)


def test_unconfigure_restores_caller_session_id(monkeypatch):
    conftest = _fresh_conftest()
    monkeypatch.setenv(iso.ENV_SESSION_ID, "caller-session")
    conftest.pytest_configure(None)
    assert os.environ[iso.ENV_SESSION_ID].startswith(iso.SESSION_ID_PREFIX)
    conftest.pytest_unconfigure(None)
    assert os.environ[iso.ENV_SESSION_ID] == "caller-session"


def test_unconfigure_removes_id_when_caller_had_none(monkeypatch):
    conftest = _fresh_conftest()
    monkeypatch.delenv(iso.ENV_SESSION_ID, raising=False)
    conftest.pytest_configure(None)
    conftest.pytest_unconfigure(None)
    assert iso.ENV_SESSION_ID not in os.environ


def test_sentinel_fails_when_unmarked_subprocess_writes_real_liveness(tmp_path):
    """正向對照：去掉 HOOK_LIVENESS_TEST_RUN 的子行程寫入 _liveness，套件須判紅。"""
    conftest = _fresh_conftest()
    liveness = tmp_path / iso.LIVENESS_RELATIVE
    liveness.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k != iso.ENV_TEST_RUN}
    env[iso.ENV_SESSION_ID] = iso.new_test_session_id()
    writer = (
        "import os, pathlib, sys;"
        "p = pathlib.Path(sys.argv[1]) / (os.environ['CLAUDE_CODE_SESSION_ID'] + '.jsonl');"
        "p.write_text('{}\\n')"
    )
    subprocess.run([sys.executable, "-c", writer, str(liveness)], env=env, check=True)

    conftest._SENTINEL["root"] = tmp_path
    session = SimpleNamespace(exitstatus=0)
    conftest.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 1


def test_sentinel_passes_when_no_leak(tmp_path):
    conftest = _fresh_conftest()
    conftest._SENTINEL["root"] = tmp_path
    session = SimpleNamespace(exitstatus=0)
    conftest.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 0
