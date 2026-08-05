#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dispatch-record-hook 測試套件（0.2.1-W3-302）

背景：派發身份綁定（who.current）已遷移至 dispatch-identity-bind-hook.py
（PostToolUse:Agent，見 test_dispatch_identity_bind_hook.py）。本 hook
（PreToolUse:Agent）此後僅負責記錄派發資訊到 dispatch-active.json，
不再涉及任何 ticket CLI 寫入（who/set-who）。

測試覆蓋：
- main() 基本流程：subagent 環境跳過 / 無 input 跳過 / 正常記錄
- record_dispatch 呼叫參數（isolation 對應 branch_name）
- record_dispatch 失敗不阻擋派發
- tool_use_id 缺失時使用 fallback 識別符
- 身份綁定邏輯已完全移除（不存在對應函式，main() 不觸發任何 ticket CLI）
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

EXIT_SUCCESS = dispatch_record_hook.EXIT_SUCCESS


class TestIdentityBindingRemoved:
    """0.2.1-W3-302：身份綁定已遷移，本 hook 不應再持有相關函式。"""

    def test_no_bind_dispatch_identity_function(self):
        assert not hasattr(dispatch_record_hook, "bind_dispatch_identity")

    def test_no_extract_ticket_id_function(self):
        assert not hasattr(dispatch_record_hook, "extract_ticket_id")

    def test_no_parse_who_value_function(self):
        assert not hasattr(dispatch_record_hook, "parse_who_value")


class TestMainBasicFlow:
    """main() 基本流程：跳過條件與正常記錄路徑"""

    def _run_main(self, input_data, tool_input=None):
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
            mock_stdin.return_value = input_data
            mock_sub.return_value = bool(input_data) and input_data.get(
                "_subagent", False
            )
            mock_input.return_value = tool_input or {}
            mock_root.return_value = Path(".")

            result = dispatch_record_hook.main()

        return result, mock_record

    def test_subagent_environment_skips_recording(self):
        result, mock_record = self._run_main({"_subagent": True})
        assert result == EXIT_SUCCESS
        mock_record.assert_not_called()

    def test_no_input_data_skips_recording(self):
        result, mock_record = self._run_main(None)
        assert result == EXIT_SUCCESS
        mock_record.assert_not_called()

    def test_normal_dispatch_records(self):
        result, mock_record = self._run_main(
            {"tool_use_id": "toolu_01"},
            tool_input={"description": "測試派發", "isolation": ""},
        )
        assert result == EXIT_SUCCESS
        mock_record.assert_called_once()
        kwargs = mock_record.call_args.kwargs
        assert kwargs["agent_description"] == "測試派發"
        assert kwargs["tool_use_id"] == "toolu_01"
        assert kwargs["branch_name"] == ""

    def test_worktree_isolation_sets_branch_name(self):
        result, mock_record = self._run_main(
            {"tool_use_id": "toolu_02"},
            tool_input={"description": "worktree 派發", "isolation": "worktree"},
        )
        assert result == EXIT_SUCCESS
        kwargs = mock_record.call_args.kwargs
        assert kwargs["branch_name"] == "worktree"

    def test_missing_tool_use_id_uses_fallback(self):
        # input_data 需為非空 dict（main() 對空 dict 走 no-input 提前跳過），
        # 僅 tool_use_id 缺失
        result, mock_record = self._run_main(
            {"other_field": "x"}, tool_input={"description": "無 tool_use_id 派發"}
        )
        assert result == EXIT_SUCCESS
        kwargs = mock_record.call_args.kwargs
        assert kwargs["tool_use_id"].startswith("unknown_")

    def test_record_dispatch_failure_does_not_block(self):
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
            dispatch_record_hook,
            "record_dispatch",
            side_effect=RuntimeError("boom"),
        ):
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"tool_use_id": "toolu_03"}
            mock_sub.return_value = False
            mock_input.return_value = {"description": "失敗派發"}
            mock_root.return_value = Path(".")

            assert dispatch_record_hook.main() == EXIT_SUCCESS
