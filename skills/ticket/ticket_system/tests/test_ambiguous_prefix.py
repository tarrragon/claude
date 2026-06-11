"""test_ambiguous_prefix
========================

驗證 argparse 縮寫歧義模式化治理（1.0.0-W1-028）。

涵蓋 4+1 個高誤打可能 token 的中文提示攔截，以及反向回歸（確保 `--all`
攔截 scoped 到 set-acceptance，不外溢至 list/stale-list/td-status/stuck-anas）。

Source: ticket 1.0.0-W1-028（源自 1.0.0-W1-024 對抗性複審）
"""
import argparse

import pytest

from ticket_system.commands import create as create_cmd
from ticket_system.commands import handoff as handoff_cmd
from ticket_system.commands import track as track_cmd
from ticket_system.lib.ambiguous_prefix import (
    AmbiguousPrefixAction,
    make_ambiguous_action,
    register_ambiguous_prefix,
)


# ---------------------------------------------------------------------------
# Parser fixtures：呼叫各命令的 register() 建立真實 parser
# ---------------------------------------------------------------------------


@pytest.fixture
def create_parser():
    parser = argparse.ArgumentParser(prog="ticket")
    sub = parser.add_subparsers(dest="command")
    create_cmd.register(sub)
    return parser


@pytest.fixture
def handoff_parser():
    parser = argparse.ArgumentParser(prog="ticket")
    sub = parser.add_subparsers(dest="command")
    handoff_cmd.register(sub)
    return parser


@pytest.fixture
def track_parser():
    parser = argparse.ArgumentParser(prog="ticket")
    sub = parser.add_subparsers(dest="command")
    track_cmd.register(sub)
    return parser


def _parse_expect_error(parser, argv):
    """解析預期失敗的 argv，回傳 argparse 寫入 stderr 的錯誤訊息。"""
    with pytest.raises(SystemExit):
        parser.parse_args(argv)


# ---------------------------------------------------------------------------
# helper 單元測試
# ---------------------------------------------------------------------------


def test_make_ambiguous_action_carries_hint():
    cls = make_ambiguous_action("請改用完整旗標")
    assert issubclass(cls, AmbiguousPrefixAction)
    assert cls.hint == "請改用完整旗標"


def test_register_ambiguous_prefix_intercepts(capsys):
    parser = argparse.ArgumentParser(prog="demo")
    register_ambiguous_prefix(parser, "--xx", "請改用 --xx-full")
    parser.add_argument("--xx-full")
    with pytest.raises(SystemExit):
        parser.parse_args(["--xx"])
    err = capsys.readouterr().err
    assert "請改用 --xx-full" in err


# ---------------------------------------------------------------------------
# 正向：4+1 token 攔截後輸出中文提示
# ---------------------------------------------------------------------------


def test_create_decision_tree_intercepted(create_parser, capsys):
    _parse_expect_error(create_parser, ["create", "--decision-tree", "x"])
    err = capsys.readouterr().err
    assert "--decision-tree-entry" in err
    assert "決策" in err  # 中文提示


def test_create_how_short_prefix_intercepted(create_parser, capsys):
    # --ho 更短前綴決策：落地為攔截（約束 2）
    _parse_expect_error(create_parser, ["create", "--ho", "x"])
    err = capsys.readouterr().err
    assert "--how-type" in err or "--how-strategy" in err
    assert "完整旗標" in err or "請使用" in err


def test_handoff_from_intercepted(handoff_parser, capsys):
    _parse_expect_error(handoff_parser, ["handoff", "--from", "x"])
    err = capsys.readouterr().err
    assert "--from-ticket-id" in err
    assert "完整旗標" in err or "請使用" in err


def test_handoff_to_intercepted(handoff_parser, capsys):
    _parse_expect_error(handoff_parser, ["handoff", "--to", "x"])
    err = capsys.readouterr().err
    assert "--to-parent" in err
    assert "完整旗標" in err or "請使用" in err


def test_set_acceptance_all_intercepted(track_parser, capsys):
    _parse_expect_error(track_parser, ["track", "set-acceptance", "T-1", "--all"])
    err = capsys.readouterr().err
    assert "--all-check" in err
    assert "完整旗標" in err or "請使用" in err


# ---------------------------------------------------------------------------
# 反向回歸：--all 攔截不外溢
# ---------------------------------------------------------------------------


def test_list_all_still_valid(track_parser):
    """list --all 仍是合法 flag（dest=list_all），不應被攔截。"""
    args = track_parser.parse_args(["track", "list", "--all"])
    assert args.list_all is True


def test_stale_list_all_still_valid(track_parser):
    args = track_parser.parse_args(["track", "stale-list", "--all"])
    assert getattr(args, "all", False) is True


def test_stuck_anas_all_still_valid(track_parser):
    args = track_parser.parse_args(["track", "stuck-anas", "--all"])
    assert getattr(args, "all", False) is True


# ---------------------------------------------------------------------------
# 既有完整旗標行為不受影響
# ---------------------------------------------------------------------------


def test_create_decision_tree_full_flags_work(create_parser):
    args = create_parser.parse_args(
        [
            "create",
            "--action", "實作",
            "--target", "x",
            "--decision-tree-entry", "E",
            "--decision-tree-decision", "D",
            "--decision-tree-rationale", "R",
        ]
    )
    assert args.decision_tree_entry == "E"
    assert args.decision_tree_decision == "D"
    assert args.decision_tree_rationale == "R"


def test_handoff_to_parent_full_flag_works(handoff_parser):
    args = handoff_parser.parse_args(["handoff", "T-1", "--to-parent"])
    assert args.to_parent is True


def test_handoff_from_ticket_id_full_flag_works(handoff_parser):
    args = handoff_parser.parse_args(
        ["handoff", "--auto", "--from-ticket-id", "T-1", "--direction", "to-parent"]
    )
    assert args.from_ticket_id == "T-1"


def test_set_acceptance_all_check_full_flag_works(track_parser):
    args = track_parser.parse_args(["track", "set-acceptance", "T-1", "--all-check"])
    assert args.all_check is True
