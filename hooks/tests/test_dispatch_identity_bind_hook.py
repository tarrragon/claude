#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dispatch-identity-bind-hook 派發身份綁定測試套件（0.2.1-W3-302）

背景：原掛在 PreToolUse（dispatch-record-hook.py，1.5.0-W5-005.2）的
who.current 綁定，因 PreToolUse(Agent) matcher 下所有 hook 皆會執行、
deny 為彙總結果，混合批次（非 worktree 票 + worktree 票同訊息派發）會
自我阻塞（issue 47 殘留缺口）：非 worktree 票寫入弄髒主 repo，隨後
worktree 票被 PC-019 擋下且仍留下已綁但 agent 從未啟動的半套狀態。
本次修復將綁定遷移至 PostToolUse(Agent)——只在工具實際執行後觸發，
天然具備「派發已成功」語意。

測試覆蓋：
- extract_ticket_id：PC-065 首行 Ticket ID 提取（根票 / 子票多層後綴 / 無 ID / 空 prompt）
- parse_who_value：`ticket track who` 輸出解析（正常 / 夾雜噪音行 / 空輸出）
- bind_dispatch_identity：無主態時綁定 / 已綁定態不覆蓋 / CLI 失敗路徑全放行
- main() 整合：有 ID + subagent_type 才觸發綁定，缺任一者跳過；worktree 隔離跳過
- 混合批次回歸：非 worktree 派發（PostToolUse 實際觸發）正常綁定；
  PreToolUse 端（dispatch-record-hook.py）不再持有任何身份綁定邏輯，
  即使 worktree 票被 PC-019 擋下也不留下寫入
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 動態載入（檔名含 dash）
hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "dispatch-identity-bind-hook.py"
spec = importlib.util.spec_from_file_location("dispatch_identity_bind_hook", hook_file)
dispatch_identity_bind_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch_identity_bind_hook)

extract_ticket_id = dispatch_identity_bind_hook.extract_ticket_id
parse_who_value = dispatch_identity_bind_hook.parse_who_value
bind_dispatch_identity = dispatch_identity_bind_hook.bind_dispatch_identity
EXIT_SUCCESS = dispatch_identity_bind_hook.EXIT_SUCCESS


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

        with patch.object(
            dispatch_identity_bind_hook, "_run_ticket_cli", side_effect=fake_cli
        ):
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
    """main() 觸發條件：Ticket ID 與 subagent_type 齊備才綁定（PostToolUse:Agent）"""

    def _run_main(self, tool_input):
        with patch.object(
            dispatch_identity_bind_hook, "setup_hook_logging"
        ) as mock_log, patch.object(
            dispatch_identity_bind_hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            dispatch_identity_bind_hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            dispatch_identity_bind_hook, "extract_tool_input"
        ) as mock_input, patch.object(
            dispatch_identity_bind_hook, "get_project_root"
        ) as mock_root, patch.object(
            dispatch_identity_bind_hook, "bind_dispatch_identity"
        ) as mock_bind:
            mock_log.return_value = MagicMock()
            # PostToolUse payload：頂層另含 tool_response / duration_ms，
            # 綁定邏輯僅需 tool_input，與本測試無關欄位略過
            mock_stdin.return_value = {
                "tool_use_id": "toolu_01",
                "tool_response": {"agentId": "agent_01"},
            }
            mock_sub.return_value = False
            mock_input.return_value = tool_input
            mock_root.return_value = Path(".")

            result = dispatch_identity_bind_hook.main()

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

    def test_worktree_isolation_skips_binding(self):
        """0.2.1-W3-226：worktree 隔離派發跳過主 repo 端身份綁定（行為原封不動延用）。

        worktree 尚未建立、寫入必落在主 repo；worktree 代理人依 dispatch
        指示會自行執行 claim --as（正確落在 worktree 副本）。此處綁定會
        造成與 worktree 內 claim 寫入的雙寫合併衝突（0.2.1-W3-219/222/223
        三次實證），故延用跳過行為，僅將觸發時機遷移至 PostToolUse。
        """
        result, mock_bind = self._run_main(
            {
                "prompt": "Ticket: 1.5.0-W5-005.2\nRead ticket md 依規格實作",
                "subagent_type": "thyme-python-developer",
                "isolation": "worktree",
            }
        )
        assert result == EXIT_SUCCESS
        mock_bind.assert_not_called()

    def test_non_worktree_isolation_still_binds(self):
        """非 worktree 隔離（共享 working tree）維持原行為，不受本次修復影響。"""
        result, mock_bind = self._run_main(
            {
                "prompt": "Ticket: 1.5.0-W5-005.3\nRead ticket md 依規格實作",
                "subagent_type": "thyme-python-developer",
                "isolation": "",
            }
        )
        assert result == EXIT_SUCCESS
        mock_bind.assert_called_once()
        assert mock_bind.call_args[0][0] == "1.5.0-W5-005.3"
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
        with patch.object(
            dispatch_identity_bind_hook, "setup_hook_logging"
        ) as mock_log, patch.object(
            dispatch_identity_bind_hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            dispatch_identity_bind_hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            dispatch_identity_bind_hook, "extract_tool_input"
        ) as mock_input, patch.object(
            dispatch_identity_bind_hook, "get_project_root"
        ) as mock_root, patch.object(
            dispatch_identity_bind_hook,
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

            assert dispatch_identity_bind_hook.main() == EXIT_SUCCESS


class TestMixedBatchRegression:
    """0.2.1-W3-302 混合批次回歸：issue 47 殘留缺口

    情境：同一訊息內派發一張非 worktree 票與一張 worktree 票。worktree
    票在 PreToolUse 階段被 worktree-commit-before-dispatch-hook.py（PC-019）
    以 exit 2 擋下，Agent 工具呼叫因此從未實際執行；依 CC runtime 生命週期
    （PostToolUse 僅在工具已執行後觸發，見 .claude/references/
    hook-architect-technical-reference.md「PostToolUse」章節「工具已執行」
    前提，並經 .claude/logs/agent-dispatch.jsonl 實測驗證 tool_input 於
    PostToolUse(Agent) 含 prompt/subagent_type/isolation 完整欄位），
    本 hook 對該筆派發完全不會被呼叫——不需要程式碼層面「偵測是否被拒」
    的邏輯，因為 hook 進程根本不會啟動。

    本測試驗證 hook 自身可控的兩半：
    (1) 非 worktree 票的 PostToolUse 確實觸發並完成綁定
    (2) PreToolUse 端（dispatch-record-hook.py）已完全不含身份綁定邏輯，
        即使 worktree 票在 PreToolUse 階段被擋下，也不存在任何寫入路徑
    """

    def test_non_worktree_dispatch_binds_when_posttooluse_fires(self):
        """混合批次中，非 worktree 派發的 PostToolUse 正常觸發並綁定。"""
        with patch.object(
            dispatch_identity_bind_hook, "setup_hook_logging"
        ) as mock_log, patch.object(
            dispatch_identity_bind_hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            dispatch_identity_bind_hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            dispatch_identity_bind_hook, "extract_tool_input"
        ) as mock_input, patch.object(
            dispatch_identity_bind_hook, "get_project_root"
        ) as mock_root, patch.object(
            dispatch_identity_bind_hook, "_run_ticket_cli"
        ) as mock_cli:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"tool_use_id": "toolu_non_worktree"}
            mock_sub.return_value = False
            mock_input.return_value = {
                "prompt": "Ticket: 0.2.1-W3-900\n非 worktree 派發",
                "subagent_type": "thyme-python-developer",
                "isolation": "",
            }
            mock_root.return_value = Path(".")
            mock_cli.side_effect = lambda args, *_: (
                "Who: pending\n" if args[0] == "who" else "[OK]"
            )

            result = dispatch_identity_bind_hook.main()

        assert result == EXIT_SUCCESS
        assert mock_cli.call_args_list[0][0][0] == ["who", "0.2.1-W3-900"]
        assert mock_cli.call_args_list[1][0][0] == [
            "set-who",
            "0.2.1-W3-900",
            "thyme-python-developer",
        ]

    def test_dispatch_record_hook_no_longer_performs_identity_binding(self):
        """PreToolUse 端（dispatch-record-hook.py）已完全移除身份綁定邏輯。

        即使 tool_input 同時含 Ticket ID 與 subagent_type、isolation=worktree
        （issue 47 混合批次觸發條件之一），dispatch-record-hook.main() 也
        不再呼叫任何 ticket CLI（who/set-who）——根除「PreToolUse 無條件
        寫入、deny 為彙總結果」這條自我阻塞路徑的源頭；被 PC-019 擋下的
        worktree 派發不會因此留下 who.current 半套狀態。
        """
        record_hook_file = hooks_path / "dispatch-record-hook.py"
        record_spec = importlib.util.spec_from_file_location(
            "dispatch_record_hook_regression", record_hook_file
        )
        dispatch_record_hook = importlib.util.module_from_spec(record_spec)
        record_spec.loader.exec_module(dispatch_record_hook)

        # 綁定相關函式已不存在於 PreToolUse hook
        assert not hasattr(dispatch_record_hook, "bind_dispatch_identity")
        assert not hasattr(dispatch_record_hook, "extract_ticket_id")

        with patch.object(
            dispatch_record_hook, "setup_hook_logging"
        ) as mock_log, patch.object(
            dispatch_record_hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            dispatch_record_hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            dispatch_record_hook, "extract_tool_input"
        ) as mock_input, patch.object(
            dispatch_record_hook, "get_project_root"
        ) as mock_root, patch.object(
            dispatch_record_hook, "record_dispatch"
        ) as mock_record:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"tool_use_id": "toolu_worktree_denied"}
            mock_sub.return_value = False
            mock_input.return_value = {
                "prompt": "Ticket: 0.2.1-W3-901\nworktree 派發（將被 PC-019 擋下）",
                "subagent_type": "parsley-flutter-developer",
                "isolation": "worktree",
            }
            mock_root.return_value = Path(".")

            result = dispatch_record_hook.main()

        assert result == dispatch_record_hook.EXIT_SUCCESS
        mock_record.assert_called_once()
