r"""
test_post_test_hook.py

驗證 post-test-hook.py 的 ANALYZER_WARNING_PATTERNS 經 W1-059 縮窄後：
- 不誤報 jest console.warn 輸出（含 "warning - ..." 樣態）
- 仍正確偵測 eslint stylish formatter 真實 lint warning

實證背景：W1-048.8 thyme 回報 npm test (4962 passed / 0 failed) + eslint exit 0
完全無警告情境下，舊 regex r"warning\s*-" 誤報 lint 警告 3 次。
"""

import importlib.util
import logging
import sys
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).resolve().parent.parent / "post-test-hook.py"


def _load_hook_module():
    """以動態 import 載入 post-test-hook.py（含 hyphen 無法直接 import）。"""
    spec = importlib.util.spec_from_file_location("post_test_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["post_test_hook"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook_module():
    return _load_hook_module()


@pytest.fixture
def logger():
    return logging.getLogger("test-post-test-hook")


# ---------------------------------------------------------------------------
# 反向案例：jest console.warn / 一般輸出不應被誤報為 lint warning
# ---------------------------------------------------------------------------

JEST_FALSE_POSITIVE_SAMPLES = [
    pytest.param(
        "console.warn\n    warning - some deprecation message\n      at Object.<anonymous>",
        id="jest-console-warn-with-dash",
    ),
    pytest.param(
        "  console.warn: warning - migration suggested",
        id="indented-warning-dash",
    ),
    pytest.param(
        "Test: should display warning - when input invalid\n    PASS",
        id="test-name-contains-warning-dash",
    ),
    pytest.param(
        "Tests:       4962 passed, 4962 total\nSnapshots:   0 total\nTime:        12.345 s",
        id="jest-summary-all-pass",
    ),
]


@pytest.mark.parametrize("output", JEST_FALSE_POSITIVE_SAMPLES)
def test_jest_console_warn_not_misclassified_as_lint_warning(hook_module, logger, output):
    """jest console.warn 輸出含 'warning - ...' 不應被誤報為 lint 警告。"""
    error_type, errors = hook_module._classify_errors(output, logger)
    lint_warnings = [e for e in errors if e["description"] == "lint 警告"]
    assert lint_warnings == [], (
        f"jest 輸出被誤報為 lint 警告：{lint_warnings}\n原始輸出：{output!r}"
    )


# ---------------------------------------------------------------------------
# 正向案例：真實 eslint stylish formatter 輸出仍正確偵測
# ---------------------------------------------------------------------------

ESLINT_TRUE_POSITIVE_SAMPLES = [
    pytest.param(
        "/path/to/file.js\n  12:34  warning  Unused variable 'x'  no-unused-vars\n\n1 problem",
        id="eslint-stylish-basic",
    ),
    pytest.param(
        "  5:1  warning  Missing semicolon  semi",
        id="eslint-stylish-simple-rule",
    ),
    pytest.param(
        "  100:20  warning  Prefer const over let  prefer-const\n  101:5  warning  Unexpected console statement  no-console",
        id="eslint-stylish-multiple-warnings",
    ),
    pytest.param(
        "  3:10  warning  Some message  @typescript-eslint/no-unused-vars",
        id="eslint-stylish-scoped-rule",
    ),
]


@pytest.mark.parametrize("output", ESLINT_TRUE_POSITIVE_SAMPLES)
def test_real_eslint_warning_still_detected(hook_module, logger, output):
    """真實 eslint stylish formatter 輸出應正確偵測為 lint 警告。"""
    error_type, errors = hook_module._classify_errors(output, logger)
    lint_warnings = [e for e in errors if e["description"] == "lint 警告"]
    assert lint_warnings, (
        f"真實 eslint warning 未被偵測：{output!r}\n所有錯誤：{errors}"
    )


# ---------------------------------------------------------------------------
# 邊界：完全乾淨輸出
# ---------------------------------------------------------------------------

def test_clean_output_no_errors(hook_module, logger):
    """無錯誤無警告的乾淨輸出應回傳空錯誤列表。"""
    output = "Tests: 100 passed\nAll tests passed"
    error_type, errors = hook_module._classify_errors(output, logger)
    lint_warnings = [e for e in errors if e["description"] == "lint 警告"]
    assert lint_warnings == []


# ---------------------------------------------------------------------------
# W3-066：_is_test_command 改用 word boundary regex
# ---------------------------------------------------------------------------

def _bash_input(command: str) -> dict:
    """組裝 PostToolUse Bash payload（精簡版）。"""
    return {"tool_name": "Bash", "tool_input": {"command": command}}


REAL_TEST_COMMAND_SAMPLES = [
    pytest.param("npm test", id="npm-test"),
    pytest.param("npm test:unit", id="npm-test-colon-suffix"),
    pytest.param("npm test --silent", id="npm-test-with-flag"),
    pytest.param("npm run test:hooks", id="npm-run-test-hooks"),
    pytest.param("npm run test:comprehensive", id="npm-run-test-comprehensive"),
    pytest.param("flutter test", id="flutter-test"),
    pytest.param("dart test", id="dart-test"),
    pytest.param("cd /path && npm test", id="chained-after-and"),
    pytest.param("(cd /path && npm test)", id="parenthesised-subshell"),
    pytest.param("NODE_ENV=test npm test", id="env-prefix"),
    pytest.param("npm test 2>&1 | tail -20", id="npm-test-piped"),
]


@pytest.mark.parametrize("command", REAL_TEST_COMMAND_SAMPLES)
def test_real_test_command_detected(hook_module, command):
    """statement 邊界後出現的 test 命令應被偵測為測試命令。"""
    assert hook_module._is_test_command(_bash_input(command)) is True, (
        f"未偵測為測試命令：{command!r}"
    )


ECHO_FALSE_POSITIVE_SAMPLES = [
    pytest.param('echo "npm test"', id="echo-double-quoted"),
    pytest.param("echo 'flutter test'", id="echo-single-quoted-flutter"),
    pytest.param('cat foo.log | grep "npm test"', id="grep-quoted-keyword"),
    pytest.param("ls", id="ls"),
    pytest.param("git status", id="git-status"),
    pytest.param("", id="empty-command"),
    pytest.param("echo dart test result", id="echo-dart-test-result-tokens"),
]


@pytest.mark.parametrize("command", ECHO_FALSE_POSITIVE_SAMPLES)
def test_echoed_or_quoted_keyword_not_misclassified(hook_module, command):
    """回顯關鍵字或非測試命令不應被誤判為測試命令（W3-066 修正）。"""
    assert hook_module._is_test_command(_bash_input(command)) is False, (
        f"非測試命令被誤判為測試命令：{command!r}"
    )


def test_mcp_dart_run_tests_still_detected(hook_module):
    """mcp__dart__run_tests 仍視為測試命令。"""
    assert hook_module._is_test_command({"tool_name": "mcp__dart__run_tests"}) is True


# ---------------------------------------------------------------------------
# W3-066：TICKET_WRITE_COMMAND_KEYWORDS 補齊 top-level commands
# ---------------------------------------------------------------------------

TICKET_BODY_WRITE_SAMPLES = [
    pytest.param("ticket create --version 0.19.0 --wave 3", id="ticket-create"),
    pytest.param("ticket batch-create --template impl-parsley --targets a,b", id="ticket-batch-create"),
    pytest.param("ticket show 0.19.0-W3-066", id="ticket-show"),
    pytest.param('ticket track append-log W3-066 --section "Solution" "..."', id="ticket-append-log"),
    pytest.param("ticket track complete W3-066", id="ticket-complete"),
    pytest.param("ticket track claim W3-066", id="ticket-claim"),
]


@pytest.mark.parametrize("command", TICKET_BODY_WRITE_SAMPLES)
def test_ticket_body_write_detected(hook_module, command):
    """ticket CLI 寫入 / 回顯命令應被視為 ticket body 寫入操作（W3-041 豁免）。"""
    payload = _bash_input(command)
    assert hook_module._is_ticket_body_write(payload, payload["tool_input"]) is True, (
        f"ticket body 寫入未被偵測：{command!r}"
    )


# ---------------------------------------------------------------------------
# W1-055：綠燈 summary 不誤觸 + 真實失敗仍觸發（雙向回歸）
# ---------------------------------------------------------------------------

GREEN_SUMMARY_SAMPLES = [
    pytest.param(
        "Tests: 4994 passed, 0 failed\nTime: 12.345 s",
        id="jest-summary-0-failed",
    ),
    pytest.param(
        "Tests:       4962 passed, 4962 total\nSnapshots:   0 total\nTime:        12.345 s",
        id="jest-summary-passed-total",
    ),
    pytest.param(
        "===== 100 passed in 5.43s =====",
        id="pytest-summary-passed",
    ),
    pytest.param(
        "我在 Test Results 章節寫：4994 passed / 0 failed / 零 regression",
        id="ticket-body-0-failed-literal",
    ),
    pytest.param(
        "[FAILED-CASES] none\nTests: 100 passed, 0 failed",
        id="failed-hyphen-identifier-with-green-summary",
    ),
    pytest.param(
        "  3 passing\n  0 failing",
        id="mocha-summary-passing",
    ),
]


@pytest.mark.parametrize("output", GREEN_SUMMARY_SAMPLES)
def test_green_summary_not_misclassified_as_test_failure(hook_module, logger, output):
    """綠燈 summary（含 0 failed / FAILED 字面）不應觸發 TEST_FAILURE 評估。"""
    # 直接驗證 _is_green_summary 攔截
    assert hook_module._is_green_summary(output) is True, (
        f"綠燈 summary 未被識別：{output!r}"
    )

    # 端到端：evaluate_test_failure 回傳 None
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "npm test"},
        "tool_response": output,
    }
    result = hook_module.evaluate_test_failure(input_data, input_data["tool_input"], logger)
    assert result is None, (
        f"綠燈 summary 觸發了 test failure 評估：{result!r}\n輸出：{output!r}"
    )


REAL_TEST_FAILURE_SAMPLES = [
    pytest.param(
        "Tests: 3 failed, 100 passed\nFAILED tests/foo.test.js",
        id="jest-3-failed",
    ),
    pytest.param(
        "Expected: 42\n  Actual: 0\nat Object.<anonymous>",
        id="jest-assertion-expected-actual",
    ),
    pytest.param(
        "AssertionError: expected 'a' to equal 'b'\n  at Context.<anonymous>",
        id="raw-assertion-error",
    ),
    pytest.param(
        "FAILED tests/integration/foo.test.js > should pass\n  reason: timeout",
        id="bare-FAILED-with-context",
    ),
]


@pytest.mark.parametrize("output", REAL_TEST_FAILURE_SAMPLES)
def test_real_test_failure_still_detected(hook_module, logger, output):
    """真實測試失敗輸出仍應被偵測為 TEST_FAILURE。"""
    error_type, errors = hook_module._classify_errors(output, logger)
    test_failures = [e for e in errors if e["type"] == "test_failure"]
    assert test_failures, (
        f"真實測試失敗未被偵測：{output!r}\n所有錯誤：{errors}"
    )


def test_zero_failed_pattern_not_match(hook_module, logger):
    """『0 tests failed』不應觸發 N 個測試失敗 pattern。"""
    output = "Result: 0 tests failed, 100 passed"
    error_type, errors = hook_module._classify_errors(output, logger)
    # 即使有 0 failed，N tests failed pattern 不應命中
    count_failures = [e for e in errors if "個測試失敗" in e["description"]]
    assert count_failures == [], (
        f"『0 tests failed』被誤判為計數失敗：{count_failures}"
    )


def test_obsolete_ticket_track_create_removed(hook_module):
    """W3-066: TICKET_WRITE_COMMAND_KEYWORDS 不應再含已過時的 `ticket track create`。"""
    keywords = hook_module.TICKET_WRITE_COMMAND_KEYWORDS
    assert "ticket track create" not in keywords, (
        "ticket track create 為不存在的命令，應已移除"
    )
    assert "ticket track update" not in keywords, (
        "ticket track update 為不存在的命令，應已移除"
    )
    # 補齊的 top-level 命令存在
    assert "ticket create" in keywords
    assert "ticket batch-create" in keywords
    assert "ticket show" in keywords
