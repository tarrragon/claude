"""claim 自我修改路徑提醒：每類一組命中／未命中對照（E1），rc 相同。"""
import argparse

import pytest

from ticket_system.commands import track
from ticket_system.lib import parser as parser_mod
from ticket_system.lib.self_modification_paths import find_self_modification_paths

MARK = "auto mode"

CASES = [
    ("settings", ".claude/settings.local.json", ".claude/settings-notes.md"),
    ("agents", ".claude/agents/thyme.md", ".claude/agents/README.txt"),
    ("guard", ".claude/hooks/foo-guard-hook.py", ".claude/hooks/foo-hook.py"),
    ("gate", ".claude/hooks/command-entrance-gate-hook.py", ".claude/hooks/foo-hook.py"),
    (
        "skill-gate",
        ".claude/skills/ticket/hooks/acceptance-gate-hook.py",
        ".claude/skills/ticket/hooks/plain-hook.py",
    ),
    (
        "skill-guard",
        ".claude/skills/ticket/hooks/foo-guard-hook.py",
        ".claude/skills/ticket/hooks/plain-hook.py",
    ),
]


def _run(monkeypatch, capsys, files):
    monkeypatch.setattr(track, "execute_claim", lambda a, v: 0)
    monkeypatch.setattr(track, "claim_lease", lambda v, t: None)
    monkeypatch.setattr(
        parser_mod, "load_ticket", lambda v, t: {"where": {"files": files}}
    )
    rc = track._execute_claim(argparse.Namespace(ticket_id="X-1"), "9.9.9")
    return rc, capsys.readouterr().out


@pytest.mark.parametrize("name,hit,miss", CASES)
def test_hit_vs_miss(monkeypatch, capsys, name, hit, miss):
    rc_hit, out_hit = _run(monkeypatch, capsys, [hit])
    rc_miss, out_miss = _run(monkeypatch, capsys, [miss])
    assert MARK in out_hit and hit in out_hit
    assert MARK not in out_miss
    assert rc_hit == rc_miss == 0


@pytest.mark.parametrize("name,hit,miss", CASES)
def test_read_declaration_no_hint(monkeypatch, capsys, name, hit, miss):
    rc, out = _run(monkeypatch, capsys, [hit + "::read"])
    assert MARK not in out
    assert rc == 0


def test_detection_error_does_not_block(monkeypatch, capsys):
    monkeypatch.setattr(track, "execute_claim", lambda a, v: 0)
    monkeypatch.setattr(track, "claim_lease", lambda v, t: None)

    def boom(v, t):
        raise RuntimeError("x")

    monkeypatch.setattr(parser_mod, "load_ticket", boom)
    rc = track._execute_claim(argparse.Namespace(ticket_id="X-1"), "9.9.9")
    cap = capsys.readouterr()
    assert rc == 0 and MARK not in cap.out and "失敗" in cap.err


def test_non_dict_where():
    assert find_self_modification_paths({"where": None}) == []
