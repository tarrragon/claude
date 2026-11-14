"""ticket-path-guard-hook 的路徑正規化測試。

Edit／Write 工具傳入絕對路徑；守衛須先剝除專案根再比對 .claude/tickets/，
否則絕對路徑恆放行。commit 階段（commit_content_guards）傳相對路徑，行為不變。
"""

import importlib.util
import logging
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent
_TICKET_HOOKS_DIR = _HOOKS_DIR.parent / "skills" / "ticket" / "hooks"
for _p in (str(_HOOKS_DIR.parent), str(_HOOKS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_LOGGER = logging.getLogger("test-ticket-path-guard")
_FAKE_ROOT = "/tmp/fake-project-root"


@pytest.fixture
def guard(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "ticket_path_guard_under_test", _TICKET_HOOKS_DIR / "ticket-path-guard-hook.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "get_project_root", lambda: Path(_FAKE_ROOT))
    return module


@pytest.mark.parametrize(
    "file_path",
    [
        f"{_FAKE_ROOT}/.claude/tickets/x.md",
        ".claude/tickets/x.md",
        "./.claude/tickets/x.md",
    ],
)
def test_forbidden_path_detected_absolute_and_relative(guard, file_path):
    assert guard.is_forbidden_ticket_path(file_path, _LOGGER) is True


@pytest.mark.parametrize(
    "file_path",
    [
        f"{_FAKE_ROOT}/docs/work-logs/v0.1.0/tickets/x.md",
        f"{_FAKE_ROOT}-other/.claude/tickets/x.md",
        "/elsewhere/.claude/tickets/x.md",
    ],
)
def test_non_forbidden_paths_allowed(guard, file_path):
    assert guard.is_forbidden_ticket_path(file_path, _LOGGER) is False


def test_absolute_write_denied(guard):
    allowed, _ = guard.check_write_permission(f"{_FAKE_ROOT}/.claude/tickets/x.md", _LOGGER)
    assert allowed is False


def test_absolute_edit_denied(guard):
    allowed, _ = guard.check_edit_permission(f"{_FAKE_ROOT}/.claude/tickets/x.md", _LOGGER)
    assert allowed is False


def test_correct_ticket_path_absolute_allowed(guard):
    allowed, _ = guard.check_write_permission(
        f"{_FAKE_ROOT}/docs/work-logs/v0.1.0/tickets/x.md", _LOGGER
    )
    assert allowed is True
