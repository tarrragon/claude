"""acceptance-gate 對 `ticket track close` 的協調票未配對用戶待辦檢查（E2）。

close 只執行協調票待辦檢查，不套用 complete 的其他步驟；complete 行為不變。
"""

import io
import json
import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
_gate_path = _hooks_dir.parent / "skills" / "ticket" / "hooks" / "acceptance-gate-hook.py"
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

from acceptance_checkers.coordination_todo_checker import check_unpaired_user_todos


def _load_gate():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gate_close_coord", _gate_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


@pytest.fixture
def logger():
    log = logging.getLogger("test-gate-close-coord")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


def _write_ticket(project_dir: Path, ticket_id: str, coordination: bool, solution: str) -> None:
    version = ticket_id.split("-W")[0]
    d = project_dir / "docs" / "work-logs" / f"v{version}" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    coord = "coordination: true\n" if coordination else ""
    (d / f"{ticket_id}.md").write_text(
        f"---\nid: {ticket_id}\ntitle: t\ntype: IMP\nstatus: in_progress\n"
        f"version: {version}\n{coord}---\n\n## Solution\n\n{solution}\n",
        encoding="utf-8",
    )


UNPAIRED = "**用戶待辦**（U1）：請處理 X"
PAIRED = UNPAIRED + "\n**用戶待辦完成**（U1）：已處理"


def test_extract_close_ids(gate, logger):
    ids = gate.extract_close_ticket_ids(
        "ticket track close 0.6.0-W1-001 --reason done", logger
    )
    assert ids == ["0.6.0-W1-001"]


def test_extract_close_ids_ignores_complete_and_unparseable(gate, logger):
    assert gate.extract_close_ticket_ids("ticket track complete 0.6.0-W1-001", logger) == []
    assert gate.extract_close_ticket_ids('ticket track close "0.6.0-W1-001', logger) == []


def test_close_unpaired_coordination_ticket_blocked(gate, logger, tmp_path):
    _write_ticket(tmp_path, "0.6.0-W1-001", True, UNPAIRED)
    result = gate.check_close_coordination_todos(["0.6.0-W1-001"], tmp_path, logger)
    assert result is not None
    assert result[0] == "0.6.0-W1-001"
    assert "close 被阻擋" in result[1]


def test_close_non_coordination_ticket_allowed(gate, logger, tmp_path):
    _write_ticket(tmp_path, "0.6.0-W1-002", False, UNPAIRED)
    assert gate.check_close_coordination_todos(["0.6.0-W1-002"], tmp_path, logger) is None


def test_close_fully_paired_coordination_ticket_allowed(gate, logger, tmp_path):
    _write_ticket(tmp_path, "0.6.0-W1-003", True, PAIRED)
    assert gate.check_close_coordination_todos(["0.6.0-W1-003"], tmp_path, logger) is None


def test_close_missing_ticket_file_fail_open(gate, logger, tmp_path):
    assert gate.check_close_coordination_todos(["0.6.0-W1-099"], tmp_path, logger) is None


def test_handle_close_outputs_deny_and_exit_block(gate, logger, tmp_path, monkeypatch, capsys):
    _write_ticket(tmp_path, "0.6.0-W1-004", True, UNPAIRED)
    monkeypatch.setattr(gate, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(gate, "get_shared_state_root", lambda p: p)
    rc = gate._handle_close_command("ticket track close 0.6.0-W1-004", logger)
    out = json.loads(capsys.readouterr().out)
    assert rc == gate.EXIT_BLOCK
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_handle_close_allows_non_close_command(gate, logger, capsys):
    rc = gate._handle_close_command("ls -la", logger)
    out = json.loads(capsys.readouterr().out)
    assert rc == gate.EXIT_SUCCESS
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_complete_message_unchanged(logger):
    """complete 既有行為不變：預設 action 仍為 complete。"""
    content = "## Solution\n\n" + UNPAIRED + "\n"
    blocked, msg = check_unpaired_user_todos(
        content, {"coordination": "true"}, "0.6.0-W1-005", logger
    )
    assert blocked and "complete 被阻擋" in msg
