"""complete / finish 別名等價性測試。

背景：CC runtime 的 worktree isolation guard 對 argv 逐元素做 basename
查集合比對其可處理的 shell 命令清單，`complete` 命中 bash builtin
`complete`，`ticket track complete` 在 worktree 派發下條件性被誤判阻擋。
裁示為別名共存（Never break userspace）：新增 `finish` 子命令，與
`complete` 共用同一 handler 與全部旗標，complete 本身不動、不加棄用警告。

本檔驗證：
1. `finish` 與 `complete` 在 `_create_command_handlers()` 指向同一 handler
2. argparse 層兩子命令的旗標定義完全一致（單一事實來源，非手動同步兩份）
3. 端到端解析：`track finish ...` 與 `track complete ...` 產生等價 Namespace
   （除 `operation` 欄位外）
4. `--as` / `--force` 等全旗標在兩名下行為等價（透過 identity_guard 與
   execute_complete 呼叫參數比對）
5. complete 原名不受影響：既有 test_cli_complete_precondition.py 測試套件
   本檔不重複，僅驗證別名層不影響原路徑
"""

from __future__ import annotations

import argparse
from unittest.mock import patch

import pytest


def _build_top_parser() -> argparse.ArgumentParser:
    """比照 scripts/ticket.py 的組裝方式建立含 track 子命令的頂層 parser。"""
    from ticket_system.commands import track as track_mod

    top = argparse.ArgumentParser(prog="ticket")
    top_subparsers = top.add_subparsers(dest="command")
    track_mod.register(top_subparsers)
    return top


def _find_operation_subparsers_action(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction:
    """從頂層 parser 找出 `track` 底下 operation 層級的 SubParsersAction。

    抽為模組層級共用函式，避免各測試類別各自重複同一段內部結構走訪
    （argparse 私有屬性走訪本身已是脆弱依賴，不應再重複兩次）。
    """
    for action in parser._subparsers._group_actions:
        if isinstance(action, argparse._SubParsersAction):
            track_parser = action.choices["track"]
            for op_action in track_parser._subparsers._group_actions:
                if isinstance(op_action, argparse._SubParsersAction):
                    return op_action
    raise AssertionError("找不到 operation 層級的 SubParsersAction")


# ============================================================
# AC1: handler 字典層級——finish 與 complete 指向同一函式物件
# ============================================================


class TestHandlerIdentity:
    def test_finish_and_complete_share_same_handler(self):
        from ticket_system.commands import track as track_mod

        handlers = track_mod._create_command_handlers()
        assert "complete" in handlers
        assert "finish" in handlers
        assert handlers["finish"] is handlers["complete"], (
            "finish 應與 complete 指向同一 handler（別名而非獨立實作）"
        )


# ============================================================
# AC2: argparse 層——兩子命令旗標定義完全一致
# ============================================================


class TestArgparseSurfaceEquivalence:
    def _get_subparser_actions(self, parser: argparse.ArgumentParser, name: str):
        """從頂層 parser 找出 track <name> 對應的 argparse action 清單。"""
        operation_action = _find_operation_subparsers_action(parser)
        target_parser = operation_action.choices[name]
        return target_parser._actions

    def test_complete_and_finish_have_identical_argument_dest_set(self):
        top = _build_top_parser()
        complete_actions = self._get_subparser_actions(top, "complete")
        finish_actions = self._get_subparser_actions(top, "finish")

        complete_dests = sorted(a.dest for a in complete_actions if a.dest != "help")
        finish_dests = sorted(a.dest for a in finish_actions if a.dest != "help")
        assert complete_dests == finish_dests, (
            f"complete/finish 旗標 dest 集合應完全一致，"
            f"complete={complete_dests}, finish={finish_dests}"
        )

    def test_complete_and_finish_have_identical_option_strings(self):
        top = _build_top_parser()
        complete_actions = self._get_subparser_actions(top, "complete")
        finish_actions = self._get_subparser_actions(top, "finish")

        complete_opts = sorted(
            opt for a in complete_actions for opt in a.option_strings
        )
        finish_opts = sorted(opt for a in finish_actions for opt in a.option_strings)
        assert complete_opts == finish_opts


# ============================================================
# AC3: 端到端解析——Namespace 除 operation 外完全等價
# ============================================================


class TestEndToEndParsing:
    def test_parsed_namespace_equivalent_except_operation(self):
        top = _build_top_parser()

        ns_complete = top.parse_args(
            [
                "track",
                "complete",
                "0.0.0-W0-ALIAS",
                "--as",
                "test-agent",
                "--force",
                "--skip-body-check",
            ]
        )
        ns_finish = top.parse_args(
            [
                "track",
                "finish",
                "0.0.0-W0-ALIAS",
                "--as",
                "test-agent",
                "--force",
                "--skip-body-check",
            ]
        )

        d_complete = vars(ns_complete).copy()
        d_finish = vars(ns_finish).copy()
        assert d_complete.pop("operation") == "complete"
        assert d_finish.pop("operation") == "finish"
        assert d_complete == d_finish, (
            "除 operation 欄位外，complete 與 finish 解析出的 Namespace 應完全等價"
        )


# ============================================================
# AC4: --as / --force 全旗標行為等價（透過 execute() 分派驗證）
# ============================================================


class TestBehaviorEquivalenceViaExecute:
    def test_finish_dispatches_to_same_underlying_complete_call(self):
        """兩名經 execute() 分派後，底層 execute_complete 收到的參數等價。"""
        from ticket_system.commands import track as track_mod

        calls = []

        def _fake_execute_complete(args, version):
            calls.append((args.ticket_id, args.as_agent, args.force, version))
            return 0

        with patch.object(track_mod, "execute_complete", _fake_execute_complete):
            with patch(
                "ticket_system.lib.identity_guard.check_identity",
                return_value=None,
            ):
                rc_complete = track_mod._execute_complete(
                    argparse.Namespace(
                        ticket_id="0.0.0-W0-ALIAS",
                        as_agent="test-agent",
                        force=True,
                        operation="complete",
                    ),
                    "0.0.0",
                )
                rc_finish = track_mod._execute_complete(
                    argparse.Namespace(
                        ticket_id="0.0.0-W0-ALIAS",
                        as_agent="test-agent",
                        force=True,
                        operation="finish",
                    ),
                    "0.0.0",
                )

        assert rc_complete == 0
        assert rc_finish == 0
        assert len(calls) == 2
        assert calls[0] == calls[1], "complete 與 finish 呼叫底層 execute_complete 的參數應完全一致"

    def test_identity_guard_telemetry_attributes_to_actual_operation_name(self):
        """W1-083 telemetry 歸因：finish 呼叫應記為 'finish'，不誤記為 'complete'。"""
        from ticket_system.commands import track as track_mod

        recorded_commands = []

        def _fake_check_identity(version, ticket_id, as_value, command="(unknown)"):
            recorded_commands.append(command)
            return None

        with patch.object(track_mod, "execute_complete", return_value=0):
            with patch(
                "ticket_system.lib.identity_guard.check_identity",
                side_effect=_fake_check_identity,
            ):
                track_mod._execute_complete(
                    argparse.Namespace(
                        ticket_id="0.0.0-W0-ALIAS",
                        as_agent=None,
                        operation="finish",
                    ),
                    "0.0.0",
                )
                track_mod._execute_complete(
                    argparse.Namespace(
                        ticket_id="0.0.0-W0-ALIAS",
                        as_agent=None,
                        operation="complete",
                    ),
                    "0.0.0",
                )

        assert recorded_commands == ["finish", "complete"], (
            f"telemetry command 欄位應反映實際呼叫的子命令名，實得 {recorded_commands}"
        )


# ============================================================
# AC5: complete 原名不受影響（回歸防護，非重複既有測試）
# ============================================================


class TestCompleteUnaffected:
    def test_complete_still_registered(self):
        top = _build_top_parser()
        operation_action = _find_operation_subparsers_action(top)
        assert "complete" in operation_action.choices
        assert "finish" in operation_action.choices

    def test_complete_help_text_not_polluted_by_alias_wording(self):
        """complete 的 help 文字仍為既有常數，不含別名說明（別名說明只應出現在 finish）。"""
        top = _build_top_parser()
        operation_action = _find_operation_subparsers_action(top)

        complete_help = None
        for choice_action in operation_action._choices_actions:
            if choice_action.dest == "complete":
                complete_help = choice_action.help
        assert complete_help is not None
        assert "別名" not in complete_help
        assert "alias" not in complete_help.lower()

    def test_finish_help_text_explicitly_documents_alias_relationship(self):
        """finish 的 help 應明確說明其與 complete 的別名關係（讀者可查）。"""
        top = _build_top_parser()
        operation_action = _find_operation_subparsers_action(top)

        finish_help = None
        for choice_action in operation_action._choices_actions:
            if choice_action.dest == "finish":
                finish_help = choice_action.help
        assert finish_help is not None
        assert "complete" in finish_help
