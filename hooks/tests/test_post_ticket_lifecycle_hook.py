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
# W10-092: post-ticket-lifecycle-hook 已遷至 .claude/skills/ticket/hooks/
ticket_skill_hooks_path = hooks_path.parent / "skills" / "ticket" / "hooks"

from lib.hook_messages import AskUserQuestionMessages

# 動態導入 post-ticket-lifecycle-hook
hook_file = ticket_skill_hooks_path / "post-ticket-lifecycle-hook.py"
spec = importlib.util.spec_from_file_location("post_ticket_lifecycle_hook", hook_file)
post_ticket_lifecycle_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(post_ticket_lifecycle_hook)


class TestPostTicketLifecycleHook:
    """post-ticket-lifecycle-hook 單元測試類"""

    def test_single_complete_success(self):
        """ticket track complete 成功 → 輸出含 additionalContext"""
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
        """命令被遮蔽（驗證器無票號可讀、退回標記）且 stdout 不含成功標記 → 不觸發"""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track complete X-NONE; echo rc=$?"},
            "tool_response": {"stdout": "操作失敗，Ticket 不存在"}
        }

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                exit_code = post_ticket_lifecycle_hook.main()

        assert exit_code == 0
        output = json.loads(mock_stdout.getvalue())
        assert "additionalContext" not in output.get("hookSpecificOutput", {})

    def test_empty_stdout(self):
        """被遮蔽且 stdout 為空 → 不觸發"""
        input_data = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track complete X-NONE; echo rc=$?"},
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
            {"stdout": "Ticket 0.1.0-W30-002 已完成"}, "ticket track complete X-NONE; echo"
        ) is True

    def test_is_complete_successful_false(self):
        assert post_ticket_lifecycle_hook.is_complete_successful(
            {"stdout": "操作失敗"}, "ticket track complete X-NONE; echo") is False

    def test_is_complete_successful_empty(self):
        assert post_ticket_lifecycle_hook.is_complete_successful(
            {"stdout": ""}, "ticket track complete X-NONE; echo") is False

    def test_unmasked_success_ignores_stdout(self):
        """未遮蔽的命令收到 PostToolUse 即成功，不看 stdout"""
        assert post_ticket_lifecycle_hook.is_complete_successful(
            {"stdout": ""}, "ticket track complete X-NONE") is True

    def test_unmasked_recomplete_outside_window_not_success(self, monkeypatch):
        """E1：未遮蔽且 stdout 為「已完成於 ...」，窗外為 False、窗內為 True"""
        out = {"stdout": "0.5.0-W1-286.1 已完成於 2026-10-15T11:52:55"}
        cmd = "ticket track complete 0.5.0-W1-286.1"
        for verdict in (False, True):
            monkeypatch.setattr(
                post_ticket_lifecycle_hook, "make_completed_verifier",
                lambda c, v=verdict: (lambda: v))
            assert post_ticket_lifecycle_hook.is_complete_successful(out, cmd) is verdict

    def test_masked_form_uses_ticket_state(self, monkeypatch):
        """E1/E2：stdout 無標記的兩種遮蔽形態，驗證器為真則成功、為假則否"""
        for command in (
            "ticket track finish T > log 2>&1; echo rc=$?",
            "out=$(ticket track complete T 2>&1); rc=$?",
        ):
            for verdict in (True, False):
                monkeypatch.setattr(
                    post_ticket_lifecycle_hook, "make_completed_verifier",
                    lambda cmd, v=verdict: (lambda: v))
                assert post_ticket_lifecycle_hook.is_complete_successful(
                    {"stdout": "rc=0"}, command) is verdict

    def test_output_contains_checkpoint_reminder(self):
        """成功偵測時，輸出含 POST_TICKET_COMPLETE_CHECKPOINT_REMINDER"""
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

    def test_complete_does_not_count_session(self):
        """session 完成計數只由 session-context-guard-hook 負責；本 hook 不計數也不輸出計數警告"""
        assert not hasattr(post_ticket_lifecycle_hook, "increment_counter")
        input_data = {
            "tool_name": "Bash",
            "session_id": "lifecycle-no-count",
            "tool_input": {"command": "ticket track complete 0.1.0-W30-002"},
            "tool_response": {"stdout": "已完成"}
        }
        counter = Path("/tmp/claude-session-completed-tickets-lifecycle-no-count")
        counter.unlink(missing_ok=True)

        with patch('sys.stdin', StringIO(json.dumps(input_data))):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                post_ticket_lifecycle_hook.main()

        context = json.loads(mock_stdout.getvalue()).get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "Session Context Guard" not in context
        assert not counter.exists()
