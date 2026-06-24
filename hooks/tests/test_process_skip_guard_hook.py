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
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 執行模組
spec.loader.exec_module(process_skip_guard_hook)

# 匯入必要的函式
detect_skip_intent = process_skip_guard_hook.detect_skip_intent
generate_skip_reminder = process_skip_guard_hook.generate_skip_reminder
main = process_skip_guard_hook.main
_should_suppress_sa_review_reference = (
    process_skip_guard_hook._should_suppress_sa_review_reference
)

# 從 hook_utils 匯入 generate_hook_output
from lib import generate_hook_output


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


class TestSaReviewReferenceSuppression:
    """測試 SKIP_SA_REVIEW 引用/討論抑制（W1-005）

    方向強制保守：只在「明確引用/討論」時抑制，絕不可漏放真正跳過意圖。
    """

    # --- 抑制成立：引用 span ---

    def test_suppress_quote_prefix_line(self):
        """命中關鍵字落在引用行（行首 >）→ detect 觸發但 suppress 抑制"""
        user_input = "> 跳過 SA 前置審查"
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type == "SKIP_SA_REVIEW"
        assert _should_suppress_sa_review_reference(user_input) is True

    def test_suppress_quote_prefix_fullwidth(self):
        """全形 ▎ quote 前綴亦視為引用行"""
        user_input = "▎ 不需要 SA 審查"
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type == "SKIP_SA_REVIEW"
        assert _should_suppress_sa_review_reference(user_input) is True

    def test_suppress_system_reminder_region(self):
        """命中關鍵字落在 system-reminder 區段 → 抑制"""
        user_input = (
            "<system-reminder>\n"
            "規則範例：跳過 SA 前置審查屬違規\n"
            "</system-reminder>"
        )
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type == "SKIP_SA_REVIEW"
        assert _should_suppress_sa_review_reference(user_input) is True

    # --- 抑制成立：meta 討論詞共現 ---

    def test_suppress_meta_false_positive_zh(self):
        """與「假陽性 / 誤觸」共現 → 判為討論 hook 本身，抑制"""
        user_input = "這個跳過 SA 的誤觸是假陽性，要怎麼修"
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type == "SKIP_SA_REVIEW"
        assert _should_suppress_sa_review_reference(user_input) is True

    def test_suppress_meta_false_positive_en(self):
        """與英文 false positive 共現 → 抑制"""
        user_input = "the 跳過 SA detection is a false positive"
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type == "SKIP_SA_REVIEW"
        assert _should_suppress_sa_review_reference(user_input) is True

    def test_suppress_meta_boundary_discussion(self):
        """討論「邊界 / 固化」hook 提示 → 抑制"""
        user_input = "固化跳過 SA 提醒的假陽性邊界"
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type == "SKIP_SA_REVIEW"
        assert _should_suppress_sa_review_reference(user_input) is True

    # --- false-negative 防回歸：真意圖仍觸發，禁止抑制 ---

    def test_no_suppress_true_intent_plain(self):
        """真正跳過意圖（無引用/meta 語境）→ 不抑制（false-negative 防回歸）"""
        user_input = "這次直接跳過 SA 審查不派 saffron"
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type == "SKIP_SA_REVIEW"
        assert _should_suppress_sa_review_reference(user_input) is False

    def test_no_suppress_intent_outside_quote(self):
        """引用行外仍有命中關鍵字 → 不抑制（保守，維持觸發）

        即使輸入含一段引用，只要引用之外用戶仍表達跳過意圖，必須觸發。
        """
        user_input = (
            "> 規則說 SA 前置審查很重要\n"
            "但這次跳過 SA 審查吧"
        )
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type == "SKIP_SA_REVIEW"
        assert _should_suppress_sa_review_reference(user_input) is False

    def test_no_suppress_partial_keyword_in_quote(self):
        """部分關鍵字在引用、部分在正文 → 不抑制

        keyword_a（跳過）在引用行，keyword_b（sa）在正文行，
        代表正文行單獨持有命中關鍵字 → 維持觸發。
        """
        user_input = (
            "> 範例：跳過\n"
            "我要跳過 SA 審查"
        )
        skip_type, _ = detect_skip_intent(user_input)
        assert skip_type == "SKIP_SA_REVIEW"
        # 第二行同時持有「跳過」與「sa」→ 非引用行有命中 → 不抑制
        assert _should_suppress_sa_review_reference(user_input) is False

    def test_main_suppressed_outputs_basic_json(self):
        """main：引用/討論語境的 SKIP_SA_REVIEW 不輸出提醒（整合測試）"""
        input_data = json.dumps({
            "prompt": "這個跳過 SA 的誤觸是假陽性，hook 要修"
        })

        with patch("sys.stdin", StringIO(input_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                        with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                            with patch.object(
                                process_skip_guard_hook,
                                "has_active_dispatch",
                                return_value=False,
                                create=True,
                            ):
                                exit_code = main()

        assert exit_code == 0
        stdout_output = mock_stdout.getvalue()
        parsed_output = json.loads(stdout_output)
        assert "additionalContext" not in parsed_output["hookSpecificOutput"]
        # stderr 無提醒
        assert not mock_stderr.getvalue().strip()

    def test_main_true_intent_still_triggers(self):
        """main：真意圖（無引用/meta）仍觸發提醒（false-negative 防回歸整合測試）"""
        input_data = json.dumps({
            "prompt": "這次直接跳過 SA 審查不派 saffron"
        })

        with patch("sys.stdin", StringIO(input_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                    with patch.object(process_skip_guard_hook, "setup_hook_logging"):
                        with patch.object(process_skip_guard_hook, "is_subagent_environment", return_value=False):
                            with patch.object(
                                process_skip_guard_hook,
                                "has_active_dispatch",
                                return_value=False,
                                create=True,
                            ):
                                # 無 in_progress ticket → type/phase guard 不靜音
                                with patch.object(
                                    process_skip_guard_hook,
                                    "get_active_in_progress_ticket",
                                    return_value=None,
                                    create=True,
                                ):
                                    exit_code = main()

        assert exit_code == 0
        stdout_output = mock_stdout.getvalue()
        parsed_output = json.loads(stdout_output)
        assert "additionalContext" in parsed_output["hookSpecificOutput"]
        # stderr 有提醒
        assert mock_stderr.getvalue().strip()


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
                            # W11-004.3：mock 無 active dispatch 避免 guard 靜音
                            with patch.object(
                                process_skip_guard_hook,
                                "has_active_dispatch",
                                return_value=False,
                                create=True,
                            ):
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
