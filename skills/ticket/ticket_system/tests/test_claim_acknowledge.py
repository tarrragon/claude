"""claim --acknowledge：hook 建議的確認方式必須被 CLI 接受並留下理由紀錄。

契約來源：sibling-blockedby-validator-hook 對條件 3／4 WARN 建議
`claim <id> --acknowledge "理由"`；CLI 端未定義該旗標時 argparse 回 rc=2。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from ticket_system.commands.track import _register_lifecycle_commands
from ticket_system.lib.parser import parse_frontmatter
from ticket_system.tests.test_claim_as_sets_who import (  # noqa: F401
    _WHO_DICT_PENDING,
    _write_pending_ticket,
    patch_ticket_paths,
    tmp_ticket_dir,
)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="track")
    sub = p.add_subparsers(dest="operation")
    _register_lifecycle_commands(sub)
    return p


def test_e1_cli_accepts_acknowledge_flag():
    """E1：hook 建議的命令形式可被 CLI 解析（修前 SystemExit(2)）。"""
    args = _parser().parse_args(["claim", "0.0.0-W0-X1", "--acknowledge", "兩者無時序關係"])
    assert args.acknowledge == "兩者無時序關係"


def test_e1_default_acknowledge_is_none():
    """對照：不傳旗標時為 None，claim 語意不變。"""
    assert _parser().parse_args(["claim", "0.0.0-W0-X1"]).acknowledge is None


def test_e1_claim_records_reason(tmp_ticket_dir: Path, patch_ticket_paths):
    """E1：claim 帶理由成功，理由寫入票面；不帶則票面無該紀錄。"""
    from ticket_system.commands.lifecycle import TicketLifecycle

    t1, t2 = "0.0.0-W0-ACK1", "0.0.0-W0-ACK2"
    p1, p2 = tmp_ticket_dir / f"{t1}.md", tmp_ticket_dir / f"{t2}.md"
    _write_pending_ticket(p1, t1, _WHO_DICT_PENDING)
    _write_pending_ticket(p2, t2, _WHO_DICT_PENDING)

    assert TicketLifecycle("0.0.0").claim(t1, acknowledge="獨立兄弟序列") == 0
    assert TicketLifecycle("0.0.0").claim(t2) == 0

    fm, body = parse_frontmatter(p1.read_text(encoding="utf-8"))
    assert fm["status"] == "in_progress"
    assert "獨立兄弟序列" in body
    assert "acknowledge" in body
    _, body2 = parse_frontmatter(p2.read_text(encoding="utf-8"))
    assert "acknowledge" not in body2
