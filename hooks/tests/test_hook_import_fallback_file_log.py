"""lib 匯入失敗進入 fallback 時，檔案日誌須留下 ERROR 行（0.5.0-W1-383）。

E2 正向對照：匯入成功時 fallback 不執行，不得產生匯入失敗的日誌行。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# (hook 檔案相對路徑, hook-logs 子目錄名)
HOOKS = [
    (".claude/skills/worktree/hooks/worktree-branch-check-hook.py", "worktree-branch-check"),
    (".claude/hooks/branch-status-reminder.py", "branch-status-reminder"),
    (".claude/hooks/build-staleness-check-hook.py", "build-staleness-check"),
    (".claude/hooks/uncommitted-ticket-md-reminder-hook.py", "uncommitted-ticket-md-reminder"),
]
LIB_MODULES = [
    "lib",
    "lib.git_command_parse",
    "lib.common_functions",
    "lib.git_utils",
]


def _load(rel_path: str) -> None:
    path = REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location("hook_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)


def _read_logs(log_root: Path, log_dir_name: str) -> str:
    log_dir = log_root / ".claude" / "hook-logs" / log_dir_name
    if not log_dir.is_dir():
        return ""
    return "".join(p.read_text(encoding="utf-8") for p in log_dir.glob("*.log"))


@pytest.mark.parametrize("rel_path,log_dir_name", HOOKS)
def test_import_failure_writes_error_line_to_file_log(
    rel_path, log_dir_name, tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    for name in LIB_MODULES:
        monkeypatch.setitem(sys.modules, name, None)

    _load(rel_path)

    assert "[Hook Import Warning]" in capsys.readouterr().err
    logs = _read_logs(tmp_path, log_dir_name)
    assert "ERROR" in logs
    assert "import of lib halted" in logs or "lib" in logs


@pytest.mark.parametrize("rel_path,log_dir_name", HOOKS)
def test_import_failure_with_unwritable_log_dir_does_not_crash(
    rel_path, log_dir_name, tmp_path, monkeypatch, capsys
):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(blocker))
    for name in LIB_MODULES:
        monkeypatch.setitem(sys.modules, name, None)

    _load(rel_path)

    err = capsys.readouterr().err
    assert "[Hook Import Warning]" in err
    assert "log write failed" in err


@pytest.mark.parametrize("rel_path,log_dir_name", HOOKS)
def test_import_success_writes_no_fallback_log(
    rel_path, log_dir_name, tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    _load(rel_path)

    assert "[Hook Import Warning]" not in capsys.readouterr().err
    assert "Hook Import Warning" not in _read_logs(tmp_path, log_dir_name)
