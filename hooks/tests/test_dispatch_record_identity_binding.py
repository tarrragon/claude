#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dispatch-record-hook 派發身份前移測試套件（1.5.0-W5-005.2）

測試覆蓋：
- extract_ticket_id：PC-065 首行 Ticket ID 提取（根票 / 子票多層後綴 / 無 ID / 空 prompt）
- parse_who_value：`ticket track who` 輸出解析（正常 / 夾雜噪音行 / 空輸出）
- bind_dispatch_identity：無主態綁定 / 已綁定態不覆蓋 / CLI 失敗路徑全放行
- main() 整合：有 ID + subagent_type 才觸發綁定，缺任一者跳過

設計背景（W5-005 F1a）：17% completed 票身份從未回填；派發時 PM 已知
subagent_type 但未落 ticket。本 hook 在 PreToolUse(Agent) 做條件式綁定，
已綁定態不覆蓋（防審查型派發 clobber 真執行者）。
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 動態載入（檔名含 dash）
hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "dispatch-record-hook.py"
spec = importlib.util.spec_from_file_location("dispatch_record_hook", hook_file)
dispatch_record_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch_record_hook)

extract_ticket_id = dispatch_record_hook.extract_ticket_id
parse_who_value = dispatch_record_hook.parse_who_value
bind_dispatch_identity = dispatch_record_hook.bind_dispatch_identity
EXIT_SUCCESS = dispatch_record_hook.EXIT_SUCCESS


class TestExtractTicketId:
    """PC-065 prompt 首行 Ticket ID 提取"""

    def test_root_ticket_id(self):
        assert extract_ticket_id("Ticket: 1.0.0-W2-001\n依規格實作") == "1.0.0-W2-001"

    def test_sub_ticket_single_suffix(self):
        assert extract_ticket_id("[Ticket] 1.5.0-W5-005.2") == "1.5.0-W5-005.2"

    def test_sub_ticket_multi_level_suffix(self):
        assert (
            extract_ticket_id("#Ticket-0.18.0-W10-017.9.1 執行清理")
            == "0.18.0-W10-017.9.1"
        )

    def test_no_ticket_id_returns_none(self):
        assert extract_ticket_id("探索 src/ 目錄結構並回報") is None

    def test_empty_prompt_returns_none(self):
        assert extract_ticket_id("") is None
        assert extract_ticket_id("   \n  ") is None

    def test_id_only_matched_on_first_line(self):
        """ID 出現在後續行不算（PC-065 規範首行）"""
        assert extract_ticket_id("執行審查\n參考 1.5.0-W5-005.2 的結論") is None


class TestParseWhoValue:
    """`ticket track who` 輸出解析"""

    def test_normal_output(self):
        assert parse_who_value("Who: rosemary-project-manager\n") == (
            "rosemary-project-manager"
        )

    def test_pending_value(self):
        assert parse_who_value("Who: pending\n") == "pending"

    def test_output_with_noise_lines(self):
        """hook 提醒等噪音行夾雜時仍能定位 Who: 行"""
        stdout = "[某 hook 提示] 請注意\nWho: thyme-python-developer\n其他行"
        assert parse_who_value(stdout) == "thyme-python-developer"

    def test_empty_output_returns_none(self):
        assert parse_who_value("") is None

    def test_no_who_line_returns_none(self):
        assert parse_who_value("[Error] ticket 不存在") is None


class TestBindDispatchIdentity:
    """條件式綁定決策（mock CLI 層）"""

    def _bind(self, who_stdout, set_stdout="[OK]"):
        """以指定 CLI 回應執行 bind；回傳 (result, cli_calls)"""
        calls = []

        def fake_cli(args, project_root, logger):
            calls.append(args)
            if args[0] == "who":
                return who_stdout
            return set_stdout

        with patch.object(dispatch_record_hook, "_run_ticket_cli", side_effect=fake_cli):
            result = bind_dispatch_identity(
                "1.5.0-W5-005.2", "thyme-python-developer", Path("."), MagicMock()
            )
        return result, calls

    def test_unbound_pending_binds(self):
        result, calls = self._bind("Who: pending\n")
        assert result is True
        assert calls == [
            ["who", "1.5.0-W5-005.2"],
            ["set-who", "1.5.0-W5-005.2", "thyme-python-developer"],
        ]

    def test_unbound_chinese_placeholder_binds(self):
        result, calls = self._bind("Who: 待派發\n")
        assert result is True
        assert calls[-1][0] == "set-who"

    def test_bound_who_not_overwritten(self):
        """已綁定態不覆蓋——審查型派發不得 clobber 真執行者"""
        result, calls = self._bind("Who: parsley-flutter-developer\n")
        assert result is False
        assert calls == [["who", "1.5.0-W5-005.2"]]

    def test_who_cli_failure_skips_binding(self):
        result, calls = self._bind(None)
        assert result is False
        assert len(calls) == 1

    def test_unparseable_who_output_skips_binding(self):
        result, calls = self._bind("[Error] envelope 輸出")
        assert result is False
        assert len(calls) == 1

    def test_set_who_failure_returns_false(self):
        result, _ = self._bind("Who: pending\n", set_stdout=None)
        assert result is False


class TestMainIntegration:
    """main() 觸發條件：Ticket ID 與 subagent_type 齊備才綁定"""

    def _run_main(self, tool_input):
        with patch.object(dispatch_record_hook, "setup_hook_logging") as mock_log, \
             patch.object(dispatch_record_hook, "read_json_from_stdin") as mock_stdin, \
             patch.object(dispatch_record_hook, "is_subagent_environment") as mock_sub, \
             patch.object(dispatch_record_hook, "extract_tool_input") as mock_input, \
             patch.object(dispatch_record_hook, "get_project_root") as mock_root, \
             patch.object(dispatch_record_hook, "record_dispatch"), \
             patch.object(dispatch_record_hook, "bind_dispatch_identity") as mock_bind:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"tool_use_id": "toolu_01"}
            mock_sub.return_value = False
            mock_input.return_value = tool_input
            mock_root.return_value = Path(".")

            result = dispatch_record_hook.main()

        return result, mock_bind

    def test_ticket_prompt_with_subagent_type_triggers_binding(self):
        result, mock_bind = self._run_main(
            {
                "prompt": "Ticket: 1.5.0-W5-005.2\nRead ticket md 依規格實作",
                "subagent_type": "thyme-python-developer",
            }
        )
        assert result == EXIT_SUCCESS
        mock_bind.assert_called_once()
        assert mock_bind.call_args[0][0] == "1.5.0-W5-005.2"
        assert mock_bind.call_args[0][1] == "thyme-python-developer"

    def test_missing_subagent_type_skips_binding(self):
        result, mock_bind = self._run_main(
            {"prompt": "Ticket: 1.5.0-W5-005.2\n實作"}
        )
        assert result == EXIT_SUCCESS
        mock_bind.assert_not_called()

    def test_non_ticket_prompt_skips_binding(self):
        result, mock_bind = self._run_main(
            {"prompt": "探索 src/ 結構", "subagent_type": "Explore"}
        )
        assert result == EXIT_SUCCESS
        mock_bind.assert_not_called()

    def test_binding_exception_does_not_block_dispatch(self):
        """綁定拋例外時派發仍放行（非阻擋 hook）"""
        with patch.object(dispatch_record_hook, "setup_hook_logging") as mock_log, \
             patch.object(dispatch_record_hook, "read_json_from_stdin") as mock_stdin, \
             patch.object(dispatch_record_hook, "is_subagent_environment") as mock_sub, \
             patch.object(dispatch_record_hook, "extract_tool_input") as mock_input, \
             patch.object(dispatch_record_hook, "get_project_root") as mock_root, \
             patch.object(dispatch_record_hook, "record_dispatch"), \
             patch.object(
                 dispatch_record_hook,
                 "bind_dispatch_identity",
                 side_effect=RuntimeError("boom"),
             ):
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"tool_use_id": "toolu_01"}
            mock_sub.return_value = False
            mock_input.return_value = {
                "prompt": "Ticket: 1.0.0-W1-001\n實作",
                "subagent_type": "thyme-python-developer",
            }
            mock_root.return_value = Path(".")

            assert dispatch_record_hook.main() == EXIT_SUCCESS
