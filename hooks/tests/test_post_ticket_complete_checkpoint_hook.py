"""
post-ticket-complete-checkpoint-hook 測試套件

驗證：
1. 單一 complete 成功：command 含 "ticket track complete"，stdout 含 "已完成" → 輸出含 additionalContext
2. batch-complete 成功：command 含 "ticket track batch-complete"，stdout 含 "已完成" → 輸出含 additionalContext
3. 非 complete 命令跳過：command 不含 complete 相關字串 → 輸出 DEFAULT_OUTPUT
4. 成功標記識別：stdout 不含 "已完成"（如含 "失敗" 或空字串）→ 即使命令匹配也不觸發
5. JSON 容錯：stdin 為無效 JSON → 安全降級，輸出 DEFAULT_OUTPUT，exit 0
"""

import json
import logging
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import importlib.util

# 設定路徑
hooks_path = Path(__file__).parent.parent

from lib.hook_messages import AskUserQuestionMessages

# 動態導入 post-ticket-complete-checkpoint-hook（檔案名含 dash，需用 importlib）
hook_file = hooks_path / "post-ticket-complete-checkpoint-hook.py"
spec = importlib.util.spec_from_file_location("post_ticket_complete_checkpoint_hook", hook_file)
post_ticket_complete_checkpoint_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post_ticket_complete_checkpoint_hook)


class TestPostTicketCompleteCheckpointHook:
    """post-ticket-complete-checkpoint-hook 單元測試類"""

    def test_single_complete_success(self):
        """
        場景 1：單一 complete 成功
        command 含 "ticket track complete"，stdout 含 "已完成"
        → 輸出含 additionalContext
        """
        input_data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "ticket track complete 0.1.0-W30-002"
            },
            "tool_response": {
                "stdout": "Ticket 0.1.0-W30-002 已完成"
            }
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            exit_code = post_ticket_complete_checkpoint_hook.main()

        assert exit_code == 0, "exit code 應為 0"

    def test_batch_complete_success(self):
        """
        場景 2：batch-complete 成功
        command 含 "ticket track batch-complete"，stdout 含 "已完成"
        → 輸出含 additionalContext
        """
        input_data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "ticket track batch-complete --ids 001,002"
            },
            "tool_response": {
                "stdout": "已完成 2 個 Ticket"
            }
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            exit_code = post_ticket_complete_checkpoint_hook.main()

        assert exit_code == 0, "exit code 應為 0"

    def test_non_complete_command_skipped(self):
        """
        場景 3：非 complete 命令跳過
        command 不含 complete 相關字串
        → 輸出 DEFAULT_OUTPUT（無 additionalContext）
        """
        input_data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "git status"
            },
            "tool_response": {
                "stdout": "On branch main"
            }
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_complete_checkpoint_hook.main()

        assert exit_code == 0, "exit code 應為 0"

        output = json.loads(mock_stdout.getvalue())
        assert "additionalContext" not in output.get("hookSpecificOutput", {}), \
            "非 complete 命令輸出不應含 additionalContext"

    def test_complete_without_success_marker(self):
        """
        場景 4：成功標記識別
        command 匹配但 stdout 不含 "已完成"（如含 "失敗" 或空字串）
        → 即使命令匹配也不觸發
        """
        input_data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "ticket track complete 0.1.0-W30-002"
            },
            "tool_response": {
                "stdout": "操作失敗，Ticket 不存在"
            }
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_complete_checkpoint_hook.main()

        assert exit_code == 0, "exit code 應為 0"

        output = json.loads(mock_stdout.getvalue())
        assert "additionalContext" not in output.get("hookSpecificOutput", {}), \
            "未偵測成功標記時輸出不應含 additionalContext"

    def test_empty_stdout(self):
        """
        場景 4 變體：stdout 為空字串
        即使命令匹配也不觸發
        """
        input_data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "ticket track complete 0.1.0-W30-002"
            },
            "tool_response": {
                "stdout": ""
            }
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_complete_checkpoint_hook.main()

        assert exit_code == 0, "exit code 應為 0"

        output = json.loads(mock_stdout.getvalue())
        assert "additionalContext" not in output.get("hookSpecificOutput", {}), \
            "stdout 為空時輸出不應含 additionalContext"

    def test_json_decode_error(self):
        """
        場景 5：JSON 容錯
        stdin 為無效 JSON
        → 安全降級，輸出 DEFAULT_OUTPUT，exit 0
        """
        invalid_json = "{ this is not valid json }"

        with patch('sys.stdin', StringIO(invalid_json)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_complete_checkpoint_hook.main()

        assert exit_code == 0, "exit code 應為 0（安全降級）"

        output = json.loads(mock_stdout.getvalue())
        assert output == post_ticket_complete_checkpoint_hook.DEFAULT_OUTPUT, \
            "JSON 解析失敗應輸出 DEFAULT_OUTPUT"

    def test_non_bash_tool_skipped(self):
        """
        非 Bash 工具時跳過
        """
        input_data = {
            "tool_name": "Read",
            "tool_input": {
                "command": "ticket track complete"
            },
            "tool_response": {
                "stdout": "已完成"
            }
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_complete_checkpoint_hook.main()

        assert exit_code == 0, "exit code 應為 0"

        output = json.loads(mock_stdout.getvalue())
        assert "additionalContext" not in output.get("hookSpecificOutput", {}), \
            "非 Bash 工具輸出不應含 additionalContext"

    def test_is_ticket_complete_command_true(self):
        """
        測試 is_ticket_complete_command() 函式 - 'ticket track complete' 命令
        """
        assert post_ticket_complete_checkpoint_hook.is_ticket_complete_command(
            "ticket track complete 0.1.0-W30-002"
        ) is True

    def test_is_ticket_complete_command_batch(self):
        """
        測試 is_ticket_complete_command() 函式 - 'ticket track batch-complete' 命令
        """
        assert post_ticket_complete_checkpoint_hook.is_ticket_complete_command(
            "ticket track batch-complete --ids 001,002"
        ) is True

    def test_is_ticket_complete_command_false(self):
        """
        測試 is_ticket_complete_command() 函式 - 不符合的命令
        """
        assert post_ticket_complete_checkpoint_hook.is_ticket_complete_command(
            "git commit -m 'test'"
        ) is False

    def test_is_complete_successful_true(self):
        """
        測試 is_complete_successful() 函式 - 含成功標記
        """
        assert post_ticket_complete_checkpoint_hook.is_complete_successful(
            "Ticket 0.1.0-W30-002 已完成"
        ) is True

    def test_is_complete_successful_false(self):
        """
        測試 is_complete_successful() 函式 - 不含成功標記
        """
        assert post_ticket_complete_checkpoint_hook.is_complete_successful(
            "操作失敗"
        ) is False

    def test_is_complete_successful_empty(self):
        """
        測試 is_complete_successful() 函式 - 空字串
        """
        assert post_ticket_complete_checkpoint_hook.is_complete_successful(
            ""
        ) is False

    def test_output_contains_checkpoint_reminder(self):
        """
        驗證成功偵測時，輸出的 additionalContext 含 POST_TICKET_COMPLETE_CHECKPOINT_REMINDER
        """
        input_data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "ticket track complete 0.1.0-W30-002"
            },
            "tool_response": {
                "stdout": "Ticket 已完成"
            }
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                post_ticket_complete_checkpoint_hook.main()

        output = json.loads(mock_stdout.getvalue())
        additional_context = output.get("hookSpecificOutput", {}).get("additionalContext", "")

        assert AskUserQuestionMessages.POST_TICKET_COMPLETE_CHECKPOINT_REMINDER in additional_context, \
            "輸出應含 POST_TICKET_COMPLETE_CHECKPOINT_REMINDER 常數"

    def test_default_output_structure(self):
        """
        驗證 DEFAULT_OUTPUT 結構正確
        """
        expected_structure = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse"
            }
        }

        assert post_ticket_complete_checkpoint_hook.DEFAULT_OUTPUT == expected_structure, \
            "DEFAULT_OUTPUT 結構應符合 PostToolUse 格式"

    def test_complete_success_marker_in_output(self):
        """
        驗證成功偵測時，輸出含有 hookEventName 和 additionalContext
        """
        input_data = {
            "tool_name": "Bash",
            "tool_input": {
                "command": "ticket track complete 0.1.0-W30-002"
            },
            "tool_response": {
                "stdout": "已完成"
            }
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                post_ticket_complete_checkpoint_hook.main()

        output = json.loads(mock_stdout.getvalue())
        hook_output = output.get("hookSpecificOutput", {})

        assert hook_output.get("hookEventName") == "PostToolUse", \
            "輸出應含 hookEventName: PostToolUse"
        assert "additionalContext" in hook_output, \
            "成功偵測時輸出應含 additionalContext 欄位"
