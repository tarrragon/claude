"""
commit-handoff-hook 測試套件

驗證：
1. 情境 A（#11a）：Ticket 仍 in_progress → 輸出 Context 刷新提醒
2. 情境 B（#11b）：Ticket completed + 同 Wave 有 pending → 輸出任務切換提醒
3. 情境 C 提示訊息：WAVE_COMPLETION_REMINDER 常數存在且格式正確
4. 情境 C 偵測邏輯：detect_wave_completion() 函式
5. commit type 判斷邏輯（skip #16）
"""

import logging
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
import importlib.util

# 設定路徑
hooks_path = Path(__file__).parent.parent

from lib.ask_user_question_reminders import AskUserQuestionReminders
from lib.hook_messages import AskUserQuestionMessages

# 動態導入 commit-handoff-hook（檔案名含 dash，需用 importlib）
hook_file = hooks_path / "commit-handoff-hook.py"
spec = importlib.util.spec_from_file_location("commit_handoff_hook", hook_file)
commit_handoff_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(commit_handoff_hook)


def test_wave_completion_reminder_exists():
    """驗證 WAVE_COMPLETION_REMINDER 常數已新增"""
    assert hasattr(AskUserQuestionReminders, 'WAVE_COMPLETION_REMINDER'), \
        "WAVE_COMPLETION_REMINDER 常數不存在"

    reminder = AskUserQuestionReminders.WAVE_COMPLETION_REMINDER
    assert reminder, "WAVE_COMPLETION_REMINDER 常數為空"
    assert isinstance(reminder, str), "WAVE_COMPLETION_REMINDER 應為字串類型"


def test_wave_completion_reminder_content():
    """驗證 WAVE_COMPLETION_REMINDER 常數包含必需的內容"""
    reminder = AskUserQuestionReminders.WAVE_COMPLETION_REMINDER

    required_keywords = [
        "Wave 完成審查",
        "情境 C",
        "/parallel-evaluation",
        "情境 C1",
        "情境 C2",
        "/version-release check",
        "AskUserQuestion",
    ]

    for keyword in required_keywords:
        assert keyword in reminder, \
            f"WAVE_COMPLETION_REMINDER 缺少必需的內容: {keyword}"


def test_wave_completion_reminder_format():
    """驗證 WAVE_COMPLETION_REMINDER 格式正確"""
    reminder = AskUserQuestionReminders.WAVE_COMPLETION_REMINDER

    assert "=" * 60 in reminder, \
        "WAVE_COMPLETION_REMINDER 缺少標準的分隔線"

    assert "[Step 1]" in reminder, "WAVE_COMPLETION_REMINDER 缺少 [Step 1]"
    assert "[Step 2]" in reminder, "WAVE_COMPLETION_REMINDER 缺少 [Step 2]"


def test_commit_handoff_reminder_unchanged():
    """驗證 COMMIT_HANDOFF_REMINDER 保持不變（回歸測試）"""
    reminder = AskUserQuestionReminders.COMMIT_HANDOFF_REMINDER

    assert "情境 A" in reminder
    assert "情境 B" in reminder
    assert "情境 C" in reminder
    assert "#16" in reminder
    assert "#11" in reminder


def test_commit_handoff_skip16_reminder_unchanged():
    """驗證 COMMIT_HANDOFF_SKIP16_REMINDER 保持不變（回歸測試）"""
    reminder = AskUserQuestionReminders.COMMIT_HANDOFF_SKIP16_REMINDER

    assert "情境 A" in reminder
    assert "情境 B" in reminder
    assert "情境 C" in reminder
    assert "#11" in reminder


def test_backward_compatibility_alias():
    """驗證向後相容性別名仍可用"""
    assert hasattr(AskUserQuestionMessages, 'WAVE_COMPLETION_REMINDER'), \
        "AskUserQuestionMessages 別名缺少 WAVE_COMPLETION_REMINDER"

    assert AskUserQuestionMessages.WAVE_COMPLETION_REMINDER == \
           AskUserQuestionReminders.WAVE_COMPLETION_REMINDER, \
        "別名指向的物件不一致"


def test_detect_wave_completion_true():
    """驗證 detect_wave_completion() 在同 Wave 無 pending 時回傳 True"""
    logger = logging.getLogger("test")

    with TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        docs_dir = project_dir / "docs"
        tickets_dir = docs_dir / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text("current_version: 0.1.0\n", encoding="utf-8")

        in_progress_ticket = tickets_dir / "0.1.0-W1-001.md"
        in_progress_ticket.write_text(
            "---\nid: 0.1.0-W1-001\nstatus: in_progress\nwave: 1\n---\nContent",
            encoding="utf-8"
        )

        completed_ticket = tickets_dir / "0.1.0-W1-002.md"
        completed_ticket.write_text(
            "---\nid: 0.1.0-W1-002\nstatus: completed\nwave: 1\n---\nContent",
            encoding="utf-8"
        )

        pending_other_wave = tickets_dir / "0.1.0-W2-001.md"
        pending_other_wave.write_text(
            "---\nid: 0.1.0-W2-001\nstatus: pending\nwave: 2\n---\nContent",
            encoding="utf-8"
        )

        with patch.object(commit_handoff_hook, 'get_project_root', return_value=project_dir):
            result = commit_handoff_hook.detect_wave_completion(logger)

        assert result is True, \
            "detect_wave_completion() 應在同 Wave 無 pending 時回傳 True"


def test_detect_wave_completion_false():
    """驗證 detect_wave_completion() 在同 Wave 有 pending 時回傳 False"""
    logger = logging.getLogger("test")

    with TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        docs_dir = project_dir / "docs"
        tickets_dir = docs_dir / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text("current_version: 0.1.0\n", encoding="utf-8")

        in_progress_ticket = tickets_dir / "0.1.0-W1-001.md"
        in_progress_ticket.write_text(
            "---\nid: 0.1.0-W1-001\nstatus: in_progress\nwave: 1\n---\nContent",
            encoding="utf-8"
        )

        pending_ticket = tickets_dir / "0.1.0-W1-002.md"
        pending_ticket.write_text(
            "---\nid: 0.1.0-W1-002\nstatus: pending\nwave: 1\n---\nContent",
            encoding="utf-8"
        )

        with patch.object(commit_handoff_hook, 'get_project_root', return_value=project_dir):
            result = commit_handoff_hook.detect_wave_completion(logger)

        assert result is False, \
            "detect_wave_completion() 應在同 Wave 有 pending 時回傳 False"


def test_detect_wave_completion_no_in_progress():
    """驗證 detect_wave_completion() 在無 in_progress ticket 時安全降級為 False"""
    logger = logging.getLogger("test")

    with TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        docs_dir = project_dir / "docs"
        tickets_dir = docs_dir / "work-logs" / "v0.1.0" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)

        todolist_file = docs_dir / "todolist.yaml"
        todolist_file.write_text("current_version: 0.1.0\n", encoding="utf-8")

        pending_ticket = tickets_dir / "0.1.0-W1-001.md"
        pending_ticket.write_text(
            "---\nid: 0.1.0-W1-001\nstatus: pending\nwave: 1\n---\nContent",
            encoding="utf-8"
        )

        with patch.object(commit_handoff_hook, 'get_project_root', return_value=project_dir):
            result = commit_handoff_hook.detect_wave_completion(logger)

        assert result is False, \
            "detect_wave_completion() 應在無 in_progress ticket 時安全降級為 False"


def test_detect_wave_completion_file_error():
    """驗證 detect_wave_completion() 在檔案讀取錯誤時安全降級為 False"""
    logger = logging.getLogger("test")

    with patch.object(commit_handoff_hook, 'get_project_root', return_value=Path("/nonexistent")):
        result = commit_handoff_hook.detect_wave_completion(logger)

    assert result is False, \
        "detect_wave_completion() 應在檔案讀取失敗時安全降級為 False"


def test_subagent_environment_detection_skips_reminder():
    """驗證 subagent 環境（含 agent_id）中不輸出 AskUserQuestion 提醒"""
    import json
    import sys
    from io import StringIO

    # 模擬 subagent 環境的輸入（含 agent_id）
    input_json = {
        "tool_name": "Bash",
        "agent_id": "parsley-flutter-developer",  # subagent 特有欄位
        "tool_input": {
            "command": "git commit -m \"feat(0.1.0-W47-004): Phase 3b 實作完成\""
        },
        "tool_response": {
            "stdout": "1 file changed, 10 insertions(+)"
        }
    }

    # 捕捉標準輸出
    captured_output = StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured_output

    try:
        with patch('sys.stdin', StringIO(json.dumps(input_json))):
            with patch.object(commit_handoff_hook, 'setup_hook_logging') as mock_logger:
                mock_logger.return_value = logging.getLogger("test")
                exit_code = commit_handoff_hook.main()

        # 驗證
        assert exit_code == 0, "main() 應回傳 EXIT_SUCCESS"

        output_str = captured_output.getvalue()
        output_json = json.loads(output_str)

        # 驗證輸出不含 AskUserQuestion 提醒（應為預設輸出）
        assert output_json == commit_handoff_hook.DEFAULT_OUTPUT, \
            "subagent 環境應輸出預設輸出，不含 AskUserQuestion 提醒"

    finally:
        sys.stdout = original_stdout


def test_main_environment_outputs_reminder():
    """驗證主線程環境（無 agent_id）中正常輸出 AskUserQuestion 提醒"""
    import json
    import sys
    from io import StringIO

    # 模擬主線程環境的輸入（無 agent_id）
    input_json = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "git commit -m \"feat(0.1.0-W47-004): Phase 3b 實作完成\""
        },
        "tool_response": {
            "stdout": "1 file changed, 10 insertions(+)"
        }
    }

    # 捕捉標準輸出
    captured_output = StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured_output

    try:
        with patch('sys.stdin', StringIO(json.dumps(input_json))):
            with patch.object(commit_handoff_hook, 'setup_hook_logging') as mock_logger:
                mock_logger.return_value = logging.getLogger("test")
                with patch.object(commit_handoff_hook, 'detect_wave_completion', return_value=False):
                    exit_code = commit_handoff_hook.main()

        # 驗證
        assert exit_code == 0, "main() 應回傳 EXIT_SUCCESS"

        output_str = captured_output.getvalue()
        output_json = json.loads(output_str)

        # 驗證輸出含 additionalContext（AskUserQuestion 提醒）
        assert "additionalContext" in output_json.get("hookSpecificOutput", {}), \
            "主線程環境應輸出 additionalContext 欄位（AskUserQuestion 提醒）"

    finally:
        sys.stdout = original_stdout
