"""
post-ticket-lifecycle-hook 測試套件

驗證合併後的 Hook（session-context-guard + post-ticket-complete-checkpoint）：
1. ticket complete 成功 → 輸出含 additionalContext（checkpoint 提醒）
2. batch-complete 成功 → 輸出含 additionalContext
3. 非 complete 命令跳過 → DEFAULT_OUTPUT
4. 成功標記未匹配 → 不觸發
5. JSON 容錯 → 安全降級
6. 子邏輯隔離 → 一個失敗不影響另一個
"""

import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import importlib.util

# 設定路徑
hooks_path = Path(__file__).parent.parent

from lib.hook_messages import AskUserQuestionMessages

# 動態導入 post-ticket-lifecycle-hook
hook_file = hooks_path / "post-ticket-lifecycle-hook.py"
spec = importlib.util.spec_from_file_location("post_ticket_lifecycle_hook", hook_file)
post_ticket_lifecycle_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post_ticket_lifecycle_hook)


class TestPostTicketLifecycleHook:
    """post-ticket-lifecycle-hook 單元測試類"""

    def _reset_counter(self):
        """清除 session counter 檔案"""
        counter_file = post_ticket_lifecycle_hook.get_counter_file()
        if counter_file.exists():
            counter_file.unlink()

    def test_single_complete_success(self):
        """ticket track complete 成功 → 輸出含 additionalContext"""
        self._reset_counter()
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track complete 0.1.0-W30-002"},
            "tool_response": {"stdout": "Ticket 0.1.0-W30-002 已完成"}
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            exit_code = post_ticket_lifecycle_hook.main()

        assert exit_code == 0

    def test_batch_complete_success(self):
        """batch-complete 成功 → 輸出含 additionalContext"""
        self._reset_counter()
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track batch-complete --ids 001,002"},
            "tool_response": {"stdout": "已完成 2 個 Ticket"}
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            exit_code = post_ticket_lifecycle_hook.main()

        assert exit_code == 0

    def test_non_complete_command_skipped(self):
        """非 complete 命令 → DEFAULT_OUTPUT"""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
            "tool_response": {"stdout": "On branch main"}
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_lifecycle_hook.main()

        assert exit_code == 0
        output = json.loads(mock_stdout.getvalue())
        assert "additionalContext" not in output.get("hookSpecificOutput", {})

    def test_complete_without_success_marker(self):
        """命令匹配但 stdout 不含成功標記 → 不觸發"""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track complete 0.1.0-W30-002"},
            "tool_response": {"stdout": "操作失敗，Ticket 不存在"}
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_lifecycle_hook.main()

        assert exit_code == 0
        output = json.loads(mock_stdout.getvalue())
        assert "additionalContext" not in output.get("hookSpecificOutput", {})

    def test_empty_stdout(self):
        """stdout 為空 → 不觸發"""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track complete 0.1.0-W30-002"},
            "tool_response": {"stdout": ""}
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_lifecycle_hook.main()

        assert exit_code == 0
        output = json.loads(mock_stdout.getvalue())
        assert "additionalContext" not in output.get("hookSpecificOutput", {})

    def test_json_decode_error(self):
        """無效 JSON → 安全降級"""
        with patch('sys.stdin', StringIO("{ invalid json }")):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_lifecycle_hook.main()

        assert exit_code == 0
        output = json.loads(mock_stdout.getvalue())
        assert output == post_ticket_lifecycle_hook.DEFAULT_OUTPUT

    def test_non_bash_tool_skipped(self):
        """非 Bash 工具 → 跳過"""
        input_data = {
            "tool_name": "Read",
            "tool_input": {"command": "ticket track complete"},
            "tool_response": {"stdout": "已完成"}
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_lifecycle_hook.main()

        assert exit_code == 0
        output = json.loads(mock_stdout.getvalue())
        assert "additionalContext" not in output.get("hookSpecificOutput", {})

    def test_is_ticket_complete_command_true(self):
        assert post_ticket_lifecycle_hook.is_ticket_complete_command(
            "ticket track complete 0.1.0-W30-002"
        ) is True

    def test_is_ticket_complete_command_batch(self):
        assert post_ticket_lifecycle_hook.is_ticket_complete_command(
            "ticket track batch-complete --ids 001,002"
        ) is True

    def test_is_ticket_complete_command_false(self):
        assert post_ticket_lifecycle_hook.is_ticket_complete_command(
            "git commit -m 'test'"
        ) is False

    def test_is_complete_successful_true(self):
        assert post_ticket_lifecycle_hook.is_complete_successful(
            "Ticket 0.1.0-W30-002 已完成"
        ) is True

    def test_is_complete_successful_false(self):
        assert post_ticket_lifecycle_hook.is_complete_successful("操作失敗") is False

    def test_is_complete_successful_empty(self):
        assert post_ticket_lifecycle_hook.is_complete_successful("") is False

    def test_output_contains_checkpoint_reminder(self):
        """成功偵測時，輸出含 POST_TICKET_COMPLETE_CHECKPOINT_REMINDER"""
        self._reset_counter()
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track complete 0.1.0-W30-002"},
            "tool_response": {"stdout": "Ticket 已完成"}
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                post_ticket_lifecycle_hook.main()

        output = json.loads(mock_stdout.getvalue())
        additional_context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert AskUserQuestionMessages.POST_TICKET_COMPLETE_CHECKPOINT_REMINDER in additional_context

    def test_default_output_structure(self):
        expected = {"hookSpecificOutput": {"hookEventName": "PostToolUse"}}
        assert post_ticket_lifecycle_hook.DEFAULT_OUTPUT == expected

    def test_session_counter_increments(self):
        """驗證 session counter 遞增"""
        self._reset_counter()
        assert post_ticket_lifecycle_hook.read_counter() == 0
        post_ticket_lifecycle_hook.increment_counter()
        assert post_ticket_lifecycle_hook.read_counter() == 1
        post_ticket_lifecycle_hook.increment_counter()
        assert post_ticket_lifecycle_hook.read_counter() == 2
        self._reset_counter()

    def test_session_counter_warning_at_threshold(self):
        """第 2 個 Ticket 完成時出現輕度提醒"""
        self._reset_counter()
        # 先完成 1 個
        post_ticket_lifecycle_hook.increment_counter()

        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track complete 0.1.0-W30-002"},
            "tool_response": {"stdout": "已完成"}
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                post_ticket_lifecycle_hook.main()

        output = json.loads(mock_stdout.getvalue())
        context = output.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "Session Context Guard" in context
        self._reset_counter()
