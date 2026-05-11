#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dispatch-count-guard-hook 測試套件

測試覆蓋（W17-141 stdin field naming bug fix 驗證重點）：
- stdin 欄位 snake_case 解析（hook_event_name）
- PostToolUse 與 UserPromptSubmit 路由命中
- 完整 main() 流程非 fall-through

修復背景：原實作從 stdin 讀取 camelCase（hookEventName），
導致 hook 始終 fall-through 到「未知的 Hook 事件」分支失效。
本測試確保使用官方 spec 的 snake_case 後路由正確命中。
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 動態載入（檔名含 dash）
hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "dispatch-count-guard-hook.py"
spec = importlib.util.spec_from_file_location("dispatch_count_guard_hook", hook_file)
dispatch_count_guard_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch_count_guard_hook)

main = dispatch_count_guard_hook.main
EXIT_SUCCESS = dispatch_count_guard_hook.EXIT_SUCCESS


class TestStdinFieldNaming:
    """W17-141 stdin field naming bug 直接驗證"""

    def test_post_tool_use_routes_to_handler_with_snake_case(self):
        """PostToolUse + snake_case 應路由至 handle_post_tool_use（非 fall-through）"""
        with patch.object(dispatch_count_guard_hook, "setup_hook_logging") as mock_log, \
             patch.object(dispatch_count_guard_hook, "read_json_from_stdin") as mock_stdin, \
             patch.object(dispatch_count_guard_hook, "handle_post_tool_use") as mock_handler:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"hook_event_name": "PostToolUse"}
            mock_handler.return_value = EXIT_SUCCESS

            result = main()

            assert result == EXIT_SUCCESS
            mock_handler.assert_called_once()

    def test_user_prompt_submit_routes_to_handler_with_snake_case(self):
        """UserPromptSubmit + snake_case 應路由至 handle_user_prompt_submit"""
        with patch.object(dispatch_count_guard_hook, "setup_hook_logging") as mock_log, \
             patch.object(dispatch_count_guard_hook, "read_json_from_stdin") as mock_stdin, \
             patch.object(dispatch_count_guard_hook, "handle_user_prompt_submit") as mock_handler:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"hook_event_name": "UserPromptSubmit"}
            mock_handler.return_value = EXIT_SUCCESS

            result = main()

            assert result == EXIT_SUCCESS
            mock_handler.assert_called_once()

    def test_camel_case_does_not_route_regression_guard(self):
        """回歸防護：camelCase（hookEventName）不應命中任何 handler"""
        with patch.object(dispatch_count_guard_hook, "setup_hook_logging") as mock_log, \
             patch.object(dispatch_count_guard_hook, "read_json_from_stdin") as mock_stdin, \
             patch.object(dispatch_count_guard_hook, "handle_post_tool_use") as mock_post, \
             patch.object(dispatch_count_guard_hook, "handle_user_prompt_submit") as mock_submit:
            mock_log.return_value = MagicMock()
            # 模擬 bug 重現：若實作回退用 camelCase，這個 stdin 不會命中任何 handler
            mock_stdin.return_value = {"hookEventName": "PostToolUse"}

            result = main()

            assert result == EXIT_SUCCESS
            mock_post.assert_not_called()
            mock_submit.assert_not_called()

    def test_empty_stdin_exits_success(self):
        """空 stdin 應安全退出"""
        with patch.object(dispatch_count_guard_hook, "setup_hook_logging") as mock_log, \
             patch.object(dispatch_count_guard_hook, "read_json_from_stdin") as mock_stdin:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = None

            result = main()

            assert result == EXIT_SUCCESS

    def test_unknown_event_exits_success_no_handler(self):
        """未知 event 安全退出，不呼叫 handler"""
        with patch.object(dispatch_count_guard_hook, "setup_hook_logging") as mock_log, \
             patch.object(dispatch_count_guard_hook, "read_json_from_stdin") as mock_stdin, \
             patch.object(dispatch_count_guard_hook, "handle_post_tool_use") as mock_post, \
             patch.object(dispatch_count_guard_hook, "handle_user_prompt_submit") as mock_submit:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"hook_event_name": "SessionStart"}

            result = main()

            assert result == EXIT_SUCCESS
            mock_post.assert_not_called()
            mock_submit.assert_not_called()


class TestFileOwnershipStdinFieldNaming:
    """順帶驗證 file-ownership-guard-hook 的 is_valid_trigger 也用 snake_case"""

    def test_is_valid_trigger_uses_snake_case(self):
        fo_hook_file = hooks_path / "file-ownership-guard-hook.py"
        fo_spec = importlib.util.spec_from_file_location("file_ownership_guard_hook_w17141", fo_hook_file)
        fo_mod = importlib.util.module_from_spec(fo_spec)
        fo_spec.loader.exec_module(fo_mod)

        # snake_case 命中
        assert fo_mod.is_valid_trigger({
            "hook_event_name": "PreToolUse",
            "tool_name": "Agent",
        }) is True

        # camelCase 不命中（回歸防護）
        assert fo_mod.is_valid_trigger({
            "hookEventName": "PreToolUse",
            "toolName": "Agent",
        }) is False
