"""add-spawned 寫入反向 source_ticket，與 remove-spawned 對稱（0.4.1-W1-012）。"""

import argparse

import pytest
import yaml

from ticket_system.commands.fields import (
    execute_add_spawned,
    execute_remove_spawned,
)


def _write_ticket(base, ticket_id, version, **extra):
    major = version.split(".")[0]
    minor = ".".join(version.split(".")[:2])
    tickets_dir = base / "docs" / "work-logs" / f"v{major}" / f"v{minor}" / f"v{version}" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    fm = {
        "id": ticket_id,
        "title": "T",
        "type": "IMP",
        "status": "in_progress",
        "version": version,
        "wave": 1,
        "priority": "P2",
        "acceptance": ["[ ] AC"],
        "spawned_tickets": [],
        "source_ticket": None,
    }
    fm.update(extra)
    path = tickets_dir / f"{ticket_id}.md"
    path.write_text(
        "---\n" + yaml.dump(fm, allow_unicode=True) + "---\n\n# Execution Log\n",
        encoding="utf-8",
    )
    return path


def _fm(path):
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])


def _args(ticket_id, value):
    return argparse.Namespace(ticket_id=ticket_id, version=None, value=[value])


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return tmp_path


A = "0.99.0-W1-001"
B = "0.99.0-W2-001"
A_OLD = "0.98.0-W1-070"
B_NEW = "0.99.0-W1-011"


def test_e1_add_spawned_writes_reverse_source(env):
    pa = _write_ticket(env, A, "0.99.0")
    pb = _write_ticket(env, B, "0.99.0")
    assert execute_add_spawned(_args(A, B), "0.99.0") == 0
    assert _fm(pa)["spawned_tickets"] == [B]
    assert _fm(pb)["source_ticket"] == A


def test_e2_existing_different_source_kept_with_warning(env, capsys):
    _write_ticket(env, A, "0.99.0")
    pb = _write_ticket(env, B, "0.99.0", source_ticket="0.99.0-W9-009")
    assert execute_add_spawned(_args(A, B), "0.99.0") == 0
    assert _fm(pb)["source_ticket"] == "0.99.0-W9-009"
    err = capsys.readouterr().err
    assert "0.99.0-W9-009" in err and "不會覆蓋" in err


def test_symmetry_add_then_remove_restores_both(env):
    pa = _write_ticket(env, A, "0.99.0")
    pb = _write_ticket(env, B, "0.99.0")
    execute_add_spawned(_args(A, B), "0.99.0")
    execute_remove_spawned(_args(A, B), "0.99.0")
    assert _fm(pa)["spawned_tickets"] == []
    assert _fm(pb)["source_ticket"] is None


def test_cross_version(env):
    pa = _write_ticket(env, A_OLD, "0.98.0")
    pb = _write_ticket(env, B_NEW, "0.99.0")
    assert execute_add_spawned(_args(A_OLD, B_NEW), "0.98.0") == 0
    assert _fm(pa)["spawned_tickets"] == [B_NEW]
    assert _fm(pb)["source_ticket"] == A_OLD
    execute_remove_spawned(_args(A_OLD, B_NEW), "0.98.0")
    assert _fm(pb)["source_ticket"] is None


def test_idempotent_rerun_keeps_source(env):
    _write_ticket(env, A, "0.99.0")
    pb = _write_ticket(env, B, "0.99.0")
    execute_add_spawned(_args(A, B), "0.99.0")
    execute_add_spawned(_args(A, B), "0.99.0")
    assert _fm(pb)["source_ticket"] == A
