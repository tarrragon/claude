"""
Tests for process-skip-guard-hook.py

驗證 Hook 協定 JSON 輸出和流程省略意圖偵測。
"""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import importlib.util

import pytest

# 動態導入 Hook 檔案（因為檔名包含連字符）
hook_path = Path(__file__).parent.parent / "process-skip-guard-hook.py"
spec = importlib.util.spec_from_file_location("process_skip_guard_hook", hook_path)
process_skip_guard_hook = importlib.util.module_from_spec(spec)

# 添加 hooks 目錄到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 執行模組
spec.loader.exec_module(process_skip_guard_hook)

# 匯入必要的函式
detect_skip_intent = process_skip_guard_hook.detect_skip_intent
generate_skip_reminder = process_skip_guard_hook.generate_skip_reminder
main = process_skip_guard_hook.main

# 從 hook_utils 匯入 generate_hook_output
from hook_utils import generate_hook_output


class TestDetectSkipIntent:
    """測試省略意圖偵測"""

    def test_detect_skip_phase4(self):
        """偵測 Phase 4 跳過意圖（肯定陳述）"""
        user_input = "跳過 phase 4，程式碼已經完美"
        skip_type, pattern_info = detect_skip_intent(user_input)
        assert skip_type == "SKIP_PHASE4"
        assert pattern_info is not None

    def test_detect_skip_agent_dispatch(self):
        """偵測派發跳過意圖（肯定陳述）"""
        user_input = "我想自行處理這個問題，不派發代理人"
        skip_type, pattern_info = detect_skip_intent(user_input)
        assert skip_type == "SKIP_AGENT_DISPATCH"
        assert pattern_info is not None

    def test_detect_skip_acceptance(self):
        """偵測驗收跳過意圖"""
        user_input = "跳過驗收流程，直接完成"
        skip_type, pattern_info = detect_skip_intent(user_input)
        assert skip_type == "SKIP_ACCEPTANCE"
        assert pattern_info is not None

    def test_no_skip_intent(self):
        """無省略意圖"""
        user_input = "繼續執行下一個任務"
        skip_type, pattern_info = detect_skip_intent(user_input)
        assert skip_type is None
        assert pattern_info is None

    def test_avoid_negative_statements(self):
        """避免使用負面陳述表達省略意圖

        已知限制（TD-019）：當前實作無法區分「跳過」和「不需要跳過」，
        因此負面陳述（如「不需要跳過」）會被誤判為省略意圖。

        用戶應避免使用負面陳述，改用肯定陳述（如「跳過」）來表達省略意圖。
        此測試記錄此已知行為。
        """
        # 負面陳述 - 目前會被誤判（已知限制）
        negative_input = "我的程式碼已經完美，不需要跳過 phase 4 評估"
        skip_type_neg, _ = detect_skip_intent(negative_input)
        # 此行為是已知限制，會在後續 Ticket 中改進
        assert skip_type_neg == "SKIP_PHASE4"  # 實際行為（不理想但已知）

        # 肯定陳述 - 正確被偵測
        positive_input = "跳過 phase 4 評估，程式碼已經完美"
        skip_type_pos, _ = detect_skip_intent(positive_input)
        assert skip_type_pos == "SKIP_PHASE4"  # 正確被偵測

    def test_empty_input(self):
        """空輸入"""
        skip_type, pattern_info = detect_skip_intent("")
        assert skip_type is None
        assert pattern_info is None

    def test_case_insensitive(self):
        """不區分大小寫"""
        user_input = "自行處理，不派發"
        skip_type, pattern_info = detect_skip_intent(user_input)
        assert skip_type == "SKIP_AGENT_DISPATCH"


class TestGenerateHookOutput:
    """測試 Hook 輸出生成（來自 hook_utils）"""

    def test_basic_output(self):
        """基本輸出（無額外上下文）"""
        output = generate_hook_output("UserPromptSubmit")
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "additionalContext" not in output["hookSpecificOutput"]

    def test_output_with_context(self):
        """帶額外上下文的輸出"""
        reminder_msg = "警告：偵測到流程省略意圖"
        output = generate_hook_output("UserPromptSubmit", reminder_msg)
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert output["hookSpecificOutput"]["additionalContext"] == reminder_msg

    def test_output_with_none_context(self):
        """額外上下文為 None 時不添加"""
        output = generate_hook_output("UserPromptSubmit", None)
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "additionalContext" not in output["hookSpecificOutput"]

    def test_output_with_empty_context(self):
        """額外上下文為空字符串時不添加"""
        output = generate_hook_output("UserPromptSubmit", "")
        assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "additionalContext" not in output["hookSpecificOutput"]

    def test_output_is_json_serializable(self):
        """輸出可序列化為 JSON"""
        output = generate_hook_output("UserPromptSubmit", "test reminder")
        json_str = json.dumps(output, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert parsed["hookSpecificOutput"]["additionalContext"] == "test reminder"

    def test_different_hook_event_names(self):
        """支援不同的 Hook 事件名稱"""
        for event_name in ["UserPromptSubmit", "PreToolUse", "PostToolUse"]:
            output = generate_hook_output(event_name)
            assert output["hookSpecificOutput"]["hookEventName"] == event_name


class TestMainFunction:
    """測試主函式的 Hook 協定合規性"""

    def test_main_with_skip_intent_outputs_json_and_stderr(self):
        """主函式在偵測到省略意圖時輸出 JSON 和 stderr 訊息"""
        input_data = json.dumps({
            "prompt": "我想自行處理，不需要派發代理人"
        })

        with patch("sys.stdin", StringIO(input_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                        with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                            exit_code = main()

        assert exit_code == 0

        # 驗證 stdout 有 JSON 輸出
        stdout_output = mock_stdout.getvalue()
        assert stdout_output.strip(), "stdout 應有輸出"
        parsed_output = json.loads(stdout_output)
        assert parsed_output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "additionalContext" in parsed_output["hookSpecificOutput"]

        # 驗證 stderr 有提醒訊息
        stderr_output = mock_stderr.getvalue()
        assert stderr_output.strip(), "stderr 應有提醒訊息"

    def test_main_without_skip_intent_outputs_basic_json(self):
        """主函式在無省略意圖時輸出基本 JSON"""
        input_data = json.dumps({
            "prompt": "繼續執行下一個任務"
        })

        with patch("sys.stdin", StringIO(input_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                        with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                            exit_code = main()

        assert exit_code == 0

        # 驗證 stdout 有 JSON 輸出
        stdout_output = mock_stdout.getvalue()
        parsed_output = json.loads(stdout_output)
        assert parsed_output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "additionalContext" not in parsed_output["hookSpecificOutput"]

        # stderr 無訊息
        stderr_output = mock_stderr.getvalue()
        assert not stderr_output or not stderr_output.strip()

    def test_main_in_subagent_environment(self):
        """主函式在 subagent 環境中輸出基本 JSON"""
        input_data = json.dumps({
            "prompt": "跳過 phase 4",
            "agent_id": "some-agent"
        })

        with patch("sys.stdin", StringIO(input_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                    with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=True):
                        exit_code = main()

        assert exit_code == 0

        # 驗證輸出基本 JSON（無 additionalContext）
        stdout_output = mock_stdout.getvalue()
        parsed_output = json.loads(stdout_output)
        assert parsed_output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "additionalContext" not in parsed_output["hookSpecificOutput"]

    def test_main_with_invalid_json(self):
        """主函式處理無效 JSON 輸入"""
        invalid_input = "this is not json"

        with patch("sys.stdin", StringIO(invalid_input)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                    exit_code = main()

        assert exit_code == 0

        # 驗證輸出基本 JSON
        stdout_output = mock_stdout.getvalue()
        parsed_output = json.loads(stdout_output)
        assert parsed_output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
        assert "additionalContext" not in parsed_output["hookSpecificOutput"]

    def test_main_with_empty_prompt(self):
        """主函式處理空 prompt"""
        input_data = json.dumps({"prompt": ""})

        with patch("sys.stdin", StringIO(input_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                    with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                        exit_code = main()

        assert exit_code == 0

        # 驗證輸出基本 JSON
        stdout_output = mock_stdout.getvalue()
        parsed_output = json.loads(stdout_output)
        assert parsed_output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"


class TestHookModuleIntegrity:
    """測試 Hook 模組完整性"""

    def test_hook_module_exists(self):
        """驗證 Hook 檔案存在"""
        hook_dir = Path(__file__).parent.parent
        hook_file = hook_dir / "process-skip-guard-hook.py"
        assert hook_file.exists(), f"Hook file not found: {hook_file}"

    def test_hook_has_required_functions(self):
        """驗證 Hook 具有必要函式"""
        assert hasattr(process_skip_guard_hook, "detect_skip_intent")
        assert hasattr(process_skip_guard_hook, "generate_hook_output")
        assert hasattr(process_skip_guard_hook, "main")
