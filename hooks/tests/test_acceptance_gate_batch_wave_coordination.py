"""acceptance-gate 對 `ticket track batch-complete --wave N` 的協調票未配對待辦檢查。

--wave 不帶票號，hook 展開為該 wave 的 in_progress 協調票後檢查；
不含協調票維持 allow；解析失敗 fail-open。
"""

import json
import logging
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
_gate_path = _hooks_dir.parent / "skills" / "ticket" / "hooks" / "acceptance-gate-hook.py"
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))


@pytest.fixture(scope="module")
def gate():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gate_batch_wave", _gate_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def logger():
    log = logging.getLogger("test-gate-batch-wave")
    log.addHandler(logging.NullHandler())
    log.setLevel(logging.CRITICAL)
    return log


UNPAIRED = "**用戶待辦**（U1）：請處理 X"


def _write(project_dir: Path, ticket_id: str, coordination: bool, solution: str,
           wave: int = 1, status: str = "in_progress") -> None:
    version = ticket_id.split("-W")[0]
    d = project_dir / "docs" / "work-logs" / f"v{version}" / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    coord = "coordination: true\n" if coordination else ""
    (d / f"{ticket_id}.md").write_text(
        f"---\nid: {ticket_id}\ntitle: t\ntype: IMP\nstatus: {status}\n"
        f"version: {version}\nwave: {wave}\n{coord}---\n\n## Solution\n\n{solution}\n",
        encoding="utf-8",
    )


def _write_child(project_dir: Path, ticket_id: str, parent: str, coordination: bool,
                 solution: str) -> None:
    _write(project_dir, ticket_id, coordination, solution)
    version = ticket_id.split("-W")[0]
    f = project_dir / "docs" / "work-logs" / f"v{version}" / "tickets" / f"{ticket_id}.md"
    f.write_text(f.read_text(encoding="utf-8").replace(
        "status: in_progress\n", f"status: in_progress\nparent_id: {parent}\n", 1), encoding="utf-8")


def _patch_root(gate, monkeypatch, root):
    monkeypatch.setattr(gate, "get_project_root", lambda: root)
    monkeypatch.setattr(gate, "get_shared_state_root", lambda p: p)


def test_selectors_parse(gate, logger):
    assert gate.extract_batch_wave_selectors(
        "ticket track batch-complete --wave 1", logger
    ) == [(1, "in_progress", None)]
    assert gate.extract_batch_wave_selectors(
        "ticket track batch-complete --wave=2 --version 0.6.0", logger
    ) == [(2, "in_progress", "0.6.0")]


def test_selectors_unparseable_fail_open(gate, logger):
    assert gate.extract_batch_wave_selectors(
        'ticket track batch-complete --wave "1', logger
    ) == []
    assert gate.extract_batch_wave_selectors(
        "ticket track batch-complete --wave abc", logger
    ) == []
    assert gate.extract_batch_wave_selectors("ls -la", logger) == []


def test_wave_with_unpaired_coordination_denied(gate, logger, tmp_path, monkeypatch, capsys):
    _write(tmp_path, "0.6.0-W1-001", True, UNPAIRED)
    _patch_root(gate, monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as exc:
        gate._extract_ticket_ids_or_skip(
            "Bash", "ticket track batch-complete --wave 1", logger
        )
    assert exc.value.code == gate.EXIT_BLOCK
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "complete 被阻擋" in out["hookSpecificOutput"]["additionalContext"]


def test_wave_without_coordination_allowed(gate, logger, tmp_path, monkeypatch, capsys):
    _write(tmp_path, "0.6.0-W1-002", False, UNPAIRED)
    _patch_root(gate, monkeypatch, tmp_path)
    ids = gate._extract_ticket_ids_or_skip(
        "Bash", "ticket track batch-complete --wave 1", logger
    )
    assert ids == []
    assert capsys.readouterr().out == ""  # 放行不輸出 decision


def test_wave_other_wave_or_status_not_expanded(gate, logger, tmp_path):
    _write(tmp_path, "0.6.0-W2-001", True, UNPAIRED, wave=2)
    _write(tmp_path, "0.6.0-W1-003", True, UNPAIRED, status="pending")
    assert gate.expand_wave_coordination_ids([(1, "in_progress", None)], tmp_path, logger) == []


def test_parent_selectors_parse(gate, logger):
    assert gate.extract_batch_parent_ids(
        "ticket track batch-complete --parent 0.6.0-W1-010", logger
    ) == ["0.6.0-W1-010"]
    assert gate.extract_batch_parent_ids('ticket track batch-complete --parent "x', logger) == []


def test_parent_with_unpaired_coordination_child_denied(gate, logger, tmp_path, monkeypatch, capsys):
    _write_child(tmp_path, "0.6.0-W1-011", "0.6.0-W1-010", True, UNPAIRED)
    _patch_root(gate, monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as exc:
        gate._extract_ticket_ids_or_skip(
            "Bash", "ticket track batch-complete --parent 0.6.0-W1-010", logger
        )
    assert exc.value.code == gate.EXIT_BLOCK
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "complete 被阻擋" in out["hookSpecificOutput"]["additionalContext"]


def test_parent_without_coordination_child_allowed(gate, logger, tmp_path, monkeypatch):
    _write_child(tmp_path, "0.6.0-W1-012", "0.6.0-W1-010", False, UNPAIRED)
    _write_child(tmp_path, "0.6.0-W1-013", "0.6.0-W1-099", True, UNPAIRED)
    _patch_root(gate, monkeypatch, tmp_path)
    gate._check_parent_coordination(
        "ticket track batch-complete --parent 0.6.0-W1-010", logger
    )
