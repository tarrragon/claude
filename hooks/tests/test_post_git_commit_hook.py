"""
test_post_git_commit_hook.py

驗證 post-git-commit-hook.py 的背景 fetch 逾時改走 lib 溫和終止函式
（先 SIGTERM、寬限後才 SIGKILL），而非 subprocess.run 逾時直接 SIGKILL。
"""

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).resolve().parent.parent / "post-git-commit-hook.py"
COMMIT_STDOUT = "[main abc1234] feat: x\n 1 file changed"


def _load_hook_module():
    """以動態 import 載入 post-git-commit-hook.py（含 hyphen 無法直接 import）。"""
    spec = importlib.util.spec_from_file_location("post_git_commit_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["post_git_commit_hook"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook_module():
    return _load_hook_module()


@pytest.fixture
def logger():
    return logging.getLogger("test-post-git-commit-hook")


def _input_data():
    return {"tool_response": {"stdout": COMMIT_STDOUT}}


def test_fetch_uses_graceful_timeout(hook_module, logger, monkeypatch):
    calls = []

    def fake(args, timeout, **kwargs):
        calls.append((args, timeout))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(hook_module, "run_with_graceful_timeout", fake)
    hook_module.run_background_fetch(_input_data(), {}, logger)

    assert calls == [(["git", "fetch", "--quiet", "--all"], 4)]


def test_fetch_timeout_warns_and_does_not_raise(hook_module, logger, monkeypatch, capsys):
    def fake(args, timeout, **kwargs):
        raise subprocess.TimeoutExpired(args, timeout)

    monkeypatch.setattr(hook_module, "run_with_graceful_timeout", fake)
    hook_module.run_background_fetch(_input_data(), {}, logger)

    assert "git fetch timeout after 4s" in capsys.readouterr().err


def test_fetch_timeout_sends_sigterm_first(hook_module, logger, monkeypatch):
    """真實 lib 路徑：逾時時整個群組先收到 SIGTERM。"""
    sent = []
    import lib.git_utils as git_utils

    real = git_utils._signal_process_group

    def spy(proc, sig):
        sent.append(sig)
        real(proc, sig)

    monkeypatch.setattr(git_utils, "_signal_process_group", spy)
    monkeypatch.setattr(hook_module, "FETCH_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(hook_module, "FETCH_ARGS", ["sleep", "30"])
    hook_module.run_background_fetch(_input_data(), {}, logger)

    import signal

    assert sent and sent[0] == signal.SIGTERM
    assert signal.SIGKILL not in sent


def test_fetch_skipped_when_commit_failed(hook_module, logger, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("不應呼叫 fetch")

    monkeypatch.setattr(hook_module, "run_with_graceful_timeout", boom)
    hook_module.run_background_fetch({"tool_response": {"stdout": ""}}, {}, logger)
