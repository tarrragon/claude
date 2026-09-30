"""指向 ANA 時的耦合後果提示測試（0.4.0-W1-068.4）。

覆蓋：
1. create --parent <ANA>，且該 ANA 已被其他票 blockedBy：stderr 提示並列出受影響的票
2. create --blocked-by / track set-blocked-by 指向有非終態 children 的 ANA：同型提示
3. E1 對照：非 ANA 父票、ANA 無 blockedBy 依賴者、ANA children 皆終態時不提示
4. 每一案 exit code 不變（提示只寫 stderr，不阻擋）
"""
from __future__ import annotations

import argparse
import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from ticket_system.commands import create as create_cmd
from ticket_system.commands import track_relations
from ticket_system.lib.parser import load_ticket, save_ticket
from ticket_system.lib.ticket_loader import list_tickets
from ticket_system.lib.ticket_ops import resolve_ticket_path

VERSION = "1.0.1"
HINT_KEY = "ANA 將保持開啟"


def _make_args(**overrides):
    defaults = dict(
        version=VERSION,
        wave=1,
        seq=None,
        action="實作",
        target="ANA 耦合提示測試",
        title=None,
        type="IMP",
        priority=None,
        who="待派發",
        what=None,
        when="立即",
        where_layer=None,
        where_files="ticket_system/commands/create.py",
        why="測試 ANA 耦合提示",
        how_type=None,
        how_strategy="驗證提示行為",
        parent=None,
        source_ticket=None,
        blocked_by=None,
        related_to=None,
        acceptance=["測試通過"],
        decision_tree_entry="Ticket",
        decision_tree_decision="直接派發",
        decision_tree_rationale="測試情境",
        quiet=False,
        verbose=False,
        json_output=False,
        force=False,
        allow_duplicate=False,
        topic=None,
        new_topic=None,
        no_topic=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _run(func, *a):
    out, err = io.StringIO(), io.StringIO()
    code = None
    try:
        with redirect_stdout(out), redirect_stderr(err):
            code = func(*a)
    except SystemExit as exc:
        code = exc.code
    return out.getvalue(), err.getvalue(), code


def _create(seq, **kw):
    """建票並回傳 ticket id；建票本身必須成功。"""
    kw.setdefault("target", f"票{seq}")
    return _create_via(_make_args(seq=seq, **kw))


def _create_via(args):
    """執行 create 並以票庫差集取得新票 ID。"""
    before = {t["id"] for t in list_tickets(VERSION)}
    _, _, code = _run(create_cmd.execute, args)
    assert code == 0
    (new_id,) = {t["id"] for t in list_tickets(VERSION)} - before
    return new_id


def _set_status(ticket_id, status):
    ticket = load_ticket(VERSION, ticket_id)
    ticket["status"] = status
    save_ticket(ticket, resolve_ticket_path(ticket, VERSION, ticket_id))


@pytest.fixture
def repo(seeded_repo_root):
    return seeded_repo_root


# --- create --parent <ANA> ---------------------------------------------------


def test_create_parent_ana_with_dependents_hints(repo):
    ana = _create(1, type="ANA", target="分析")
    dep = _create(2, blocked_by=[ana], target="等待者")
    _, err, code = _run(create_cmd.execute, _make_args(seq=3, parent=ana, target="子票"))
    assert code == 0
    assert HINT_KEY in err
    assert dep in err
    assert "1 張" in err


def test_create_parent_ana_without_dependents_no_hint(repo):
    ana = _create(1, type="ANA", target="分析")
    _, err, code = _run(create_cmd.execute, _make_args(seq=2, parent=ana, target="子票"))
    assert code == 0
    assert HINT_KEY not in err


def test_create_parent_non_ana_with_dependents_no_hint(repo):
    parent = _create(1, type="IMP", target="實作父")
    _create(2, blocked_by=[parent], target="等待者")
    _, err, code = _run(create_cmd.execute, _make_args(seq=3, parent=parent, target="子票"))
    assert code == 0
    assert HINT_KEY not in err


def test_create_parent_ana_dependent_terminal_no_hint(repo):
    ana = _create(1, type="ANA", target="分析")
    dep = _create(2, blocked_by=[ana], target="等待者")
    _set_status(dep, "closed")
    _, err, code = _run(create_cmd.execute, _make_args(seq=3, parent=ana, target="子票"))
    assert code == 0
    assert HINT_KEY not in err


# --- create --blocked-by <ANA> ----------------------------------------------


def test_create_blocked_by_ana_with_open_children_hints(repo):
    ana = _create(1, type="ANA", target="分析")
    child = _create(2, parent=ana, target="子票")
    _, err, code = _run(create_cmd.execute, _make_args(seq=3, blocked_by=[ana], target="等待者"))
    assert code == 0
    assert HINT_KEY in err
    assert child in err


def test_create_blocked_by_ana_children_all_terminal_no_hint(repo):
    ana = _create(1, type="ANA", target="分析")
    child = _create(2, parent=ana, target="子票")
    _set_status(child, "closed")
    _, err, code = _run(create_cmd.execute, _make_args(seq=3, blocked_by=[ana], target="等待者"))
    assert code == 0
    assert HINT_KEY not in err


def test_create_blocked_by_non_ana_with_open_children_no_hint(repo):
    parent = _create(1, type="IMP", target="實作父")
    _create(2, parent=parent, target="子票")
    _, err, code = _run(create_cmd.execute, _make_args(seq=3, blocked_by=[parent], target="等待者"))
    assert code == 0
    assert HINT_KEY not in err


# --- track set-blocked-by ----------------------------------------------------


def _set_blocked_by(target, value, **flags):
    ns = argparse.Namespace(ticket_id=target, value=value, add=False, remove=False, **flags)
    return _run(track_relations.execute_set_blocked_by, ns, VERSION)


def test_set_blocked_by_ana_with_open_children_hints(repo):
    ana = _create(1, type="ANA", target="分析")
    child = _create(2, parent=ana, target="子票")
    waiter = _create(3, target="等待者")
    _, err, code = _set_blocked_by(waiter, ana)
    assert code == 0
    assert HINT_KEY in err
    assert child in err


def test_set_blocked_by_ana_children_all_terminal_no_hint(repo):
    ana = _create(1, type="ANA", target="分析")
    child = _create(2, parent=ana, target="子票")
    _set_status(child, "closed")
    waiter = _create(3, target="等待者")
    _, err, code = _set_blocked_by(waiter, ana)
    assert code == 0
    assert HINT_KEY not in err


def test_set_blocked_by_non_ana_no_hint(repo):
    parent = _create(1, type="IMP", target="實作父")
    _create(2, parent=parent, target="子票")
    waiter = _create(3, target="等待者")
    _, err, code = _set_blocked_by(waiter, parent)
    assert code == 0
    assert HINT_KEY not in err


def test_set_blocked_by_remove_mode_no_hint(repo):
    ana = _create(1, type="ANA", target="分析")
    _create(2, parent=ana, target="子票")
    waiter = _create(3, target="等待者", blocked_by=[ana])
    _, err, code = _set_blocked_by(waiter, ana, )
    assert code == 0
    ns = argparse.Namespace(ticket_id=waiter, value=ana, add=False, remove=True)
    _, err2, code2 = _run(track_relations.execute_set_blocked_by, ns, VERSION)
    assert code2 == 0
    assert HINT_KEY not in err2
