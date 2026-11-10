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
    pytest.param("python3 .claude/scripts/run-with-timeout.py 60 -- flutter test", id="timeout-wrapper-flutter"),
    pytest.param(
        "uv --directory .claude/hooks run --with pytest python -m pytest tests -q",
        id="uv-run-python-m-pytest",
    ),
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
    pytest.param(
        'grep -n "TEST_COMMAND_PATTERN\\|flutter test\\|dart test" hook.py',
        id="grep-quoted-pipe-keywords",
    ),
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


# ---------------------------------------------------------------------------
# 時長達上限：不得終止任何程序，改輸出含清理指引的警告
# ---------------------------------------------------------------------------

import ast
import json
import shlex
import time

_BANNED_MODULES = {"subprocess", "signal", "pty", "multiprocessing"}
_BANNED_OS_EXACT = {"kill", "killpg", "system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp"}
_BANNED_OS_PREFIX = ("spawn", "exec")


def _is_banned_os_attr(name):
    return name in _BANNED_OS_EXACT or name.startswith(_BANNED_OS_PREFIX)


def find_termination_routes(source):
    """對原始碼做語法樹檢查，回傳所有啟動程序／送訊號途徑的描述清單。"""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found += [f"import {a.name}" for a in node.names if a.name.split(".")[0] in _BANNED_MODULES]
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")[0]
            if mod in _BANNED_MODULES:
                found.append(f"from {node.module} import ...")
            elif mod == "os":
                found += [f"from os import {a.name}" for a in node.names if _is_banned_os_attr(a.name)]
            elif mod == "asyncio":
                found += [f"from asyncio import {a.name}" for a in node.names if a.name.startswith("create_subprocess")]
        elif isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and base.id == "os" and _is_banned_os_attr(node.attr):
                found.append(f"os.{node.attr}")
            if node.attr.startswith("create_subprocess"):
                found.append(f"{node.attr}")
    return found


_INJECTED_ROUTES = [
    pytest.param("import subprocess", id="import-subprocess"),
    pytest.param("import signal", id="import-signal"),
    pytest.param("from subprocess import run", id="from-subprocess"),
    pytest.param("from signal import SIGTERM", id="from-signal"),
    pytest.param("import os\nos.kill(1, 15)", id="os.kill"),
    pytest.param("import os\nos.killpg(1, 15)", id="os.killpg"),
    pytest.param("import os\nos.system('x')", id="os.system"),
    pytest.param("import os\nos.popen('x')", id="os.popen"),
    pytest.param("import os\nos.spawnv(0, 'x', [])", id="os.spawnv"),
    pytest.param("import os\nos.execv('x', [])", id="os.execv"),
    pytest.param("import os\nos.posix_spawn('x', [], {})", id="os.posix_spawn"),
    pytest.param("import os\nos.fork()", id="os.fork"),
    pytest.param("from os import kill", id="from-os-kill"),
    pytest.param("from os import killpg as k", id="from-os-killpg-alias"),
    pytest.param("from os import system", id="from-os-system"),
    pytest.param("from os import execvp", id="from-os-execvp"),
    pytest.param("import asyncio\nasyncio.create_subprocess_exec('x')", id="asyncio-exec"),
    pytest.param("import asyncio\nasyncio.create_subprocess_shell('x')", id="asyncio-shell"),
    pytest.param("from asyncio import create_subprocess_exec", id="from-asyncio"),
    pytest.param("import subprocess\nsubprocess.getoutput('x')", id="subprocess.getoutput"),
]


@pytest.mark.parametrize("source", _INJECTED_ROUTES)
def test_route_check_fails_on_injected_source(source):
    """正向對照：注入各途徑的原始碼，檢查必須回報（含 from 匯入形式）。"""
    assert find_termination_routes(source) != []


def test_route_check_passes_on_clean_source():
    assert find_termination_routes("import os\nx = os.path.join('a', 'b')\nos.environ.get('A')") == []


def test_hook_source_has_no_termination_route():
    """零終止保證：hook 原始碼不含任何啟動程序或送訊號的途徑。"""
    assert find_termination_routes(HOOK_PATH.read_text()) == []


def _arm_monitor(root, seconds_ago):
    log_dir = root / ".claude" / "hook-logs"
    log_dir.mkdir(parents=True)
    f = log_dir / "test-monitor.json"
    f.write_text(json.dumps({"start_timestamp": time.time() - seconds_ago,
                              "status": "running"}))
    return f


def _run_at(module, monkeypatch, tmp_path, logger, seconds_ago):
    monitor = _arm_monitor(tmp_path, seconds_ago)
    monkeypatch.setattr(module, "get_project_root", lambda: tmp_path)
    msg = module.check_test_timeout({}, {}, logger)
    return msg, monitor


def test_limit_reached_warns_on_stderr_once_with_single_label(hook_module, monkeypatch, tmp_path, logger, capsys, caplog):
    caplog.set_level(logging.WARNING, logger=logger.name)
    msg, monitor = _run_at(hook_module, monkeypatch, tmp_path, logger, hook_module.LIMIT_THRESHOLD + 5)
    err = capsys.readouterr().err
    assert "orphan-test-procs.py" in msg and "--kill" in msg
    assert "orphan-test-procs.py" in err
    assert err.startswith("[已達上限]")
    assert err.count("[") == 1 and "[WARNING]" not in err
    assert any("orphan-test-procs.py" in r.getMessage() for r in caplog.records)
    assert json.loads(monitor.read_text())["action"] == "limit_warning"


def test_limit_warning_content(hook_module, monkeypatch, tmp_path, logger):
    msg, _ = _run_at(hook_module, monkeypatch, tmp_path, logger, hook_module.LIMIT_THRESHOLD + 5)
    assert f"{hook_module.LIMIT_THRESHOLD // 60} 分鐘" in msg
    assert "不自動終止" in msg and "其他專案" in msg
    script = tmp_path / ".claude" / "scripts" / "orphan-test-procs.py"
    list_cmd = f"python3 {shlex.quote(str(script))}"
    lines = msg.splitlines()
    assert list_cmd in lines
    assert f"{list_cmd} --kill" in lines
    assert "確屬本專案" in msg and "不再需要" in msg


def test_critical_message_points_to_list_command_only(hook_module, monkeypatch, tmp_path, logger):
    msg, _ = _run_at(hook_module, monkeypatch, tmp_path, logger, hook_module.CRITICAL_THRESHOLD + 5)
    script = tmp_path / ".claude" / "scripts" / "orphan-test-procs.py"
    assert f"python3 {shlex.quote(str(script))}" in msg.splitlines()
    for banned in ("--kill", "pkill", "killall", "手動終止", "建議終止"):
        assert banned not in msg
    assert msg.split("，")[0] != hook_module._limit_message(30.0, tmp_path).split("，")[0]


def test_limit_message_logged_once(hook_module, monkeypatch, tmp_path, logger, caplog):
    caplog.set_level(logging.DEBUG, logger=logger.name)
    _run_at(hook_module, monkeypatch, tmp_path, logger, hook_module.LIMIT_THRESHOLD + 5)
    hits = [r for r in caplog.records if "orphan-test-procs.py" in r.getMessage()]
    assert len(hits) == 1


# (門檻屬性名, 門檻前一秒的 action, 門檻當秒的 action, 當秒訊息開頭)
_BOUNDARY_CASES = [
    pytest.param("WARNING_THRESHOLD", "normal", "warning", "警告：", id="warning-boundary"),
    pytest.param("CRITICAL_THRESHOLD", "warning", "critical_warning", "嚴重警告：", id="critical-boundary"),
    pytest.param("LIMIT_THRESHOLD", "critical_warning", "limit_warning", "[已達上限]", id="limit-boundary"),
]


@pytest.mark.parametrize("attr,before_action,at_action,at_prefix", _BOUNDARY_CASES)
def test_threshold_boundaries(hook_module, tmp_path, attr, before_action, at_action, at_prefix):
    t = getattr(hook_module, attr)
    before_act, before_msg = hook_module._classify_duration(t - 1, tmp_path)
    at_act, at_msg = hook_module._classify_duration(t, tmp_path)
    assert before_act == before_action
    assert at_act == at_action
    assert at_msg.startswith(at_prefix)
    assert not before_msg.startswith(at_prefix)


def test_below_warning_is_normal(hook_module, tmp_path):
    act, msg = hook_module._classify_duration(0, tmp_path)
    assert act == "normal" and msg.startswith("測試完成：")


def test_no_obsolete_constant_name(hook_module):
    assert not hasattr(hook_module, "AUTO_KILL_THRESHOLD")


# --- 評估紀錄取證欄位 ---

def _run_logged_evaluation(hook_module, monkeypatch, tmp_path, logger, tool_response):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    input_data = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest -q"},
        "tool_response": tool_response,
    }
    hook_module.evaluate_test_failure(input_data, input_data["tool_input"], logger)
    reports = list((tmp_path / ".claude" / "hook-logs").glob("pre-fix-evaluation-*.json"))
    assert len(reports) == 1
    return json.loads(reports[0].read_text(encoding="utf-8"))


def test_evaluation_record_dict_tool_response(hook_module, monkeypatch, tmp_path, logger):
    response = {"stdout": "collected 3 FAILED tests/test_x.py::t - boom", "stderr": ""}
    report = _run_logged_evaluation(hook_module, monkeypatch, tmp_path, logger, response)
    assert report["tool_response_type"] == "dict"
    assert report["tool_response_keys"] == ["stdout", "stderr"]
    assert report["tool_response_value_lengths"] == {
        "stdout": len(response["stdout"]), "stderr": 0}
    assert any("FAILED" in e["matched_excerpt"] for e in report["errors"])


def test_evaluation_record_str_tool_response(hook_module, monkeypatch, tmp_path, logger):
    response = "collected 3\nFAILED tests/test_x.py::t - boom\n"
    report = _run_logged_evaluation(hook_module, monkeypatch, tmp_path, logger, response)
    assert report["tool_response_type"] == "str"
    assert "tool_response_keys" not in report
    assert any("FAILED" in e["matched_excerpt"] for e in report["errors"])


# --- Bash dict 形態只評估 stdout/stderr；pytest -q 綠燈摘要 ---

_EDIT_DIFF = (
    "diff --git a/t.py b/t.py\n+    assert x\n+# Expected: 1 Actual: 2\n"
    "+FAILED tests/test_other.py::t\n"
)


def _eval_response(hook_module, logger, tool_name, tool_response):
    input_data = {
        "tool_name": tool_name,
        "tool_input": {"command": "pytest -q"},
        "tool_response": tool_response,
    }
    return hook_module.evaluate_test_failure(input_data, input_data["tool_input"], logger)


def test_bash_dict_edit_diff_not_evaluated(hook_module, monkeypatch, tmp_path, logger):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    response = {"stdout": "..........\n82 passed in 0.25s\n", "stderr": "",
                "bashEditDiff": _EDIT_DIFF}
    assert _eval_response(hook_module, logger, "Bash", response) is None


def test_bash_dict_real_failure_still_reported(hook_module, monkeypatch, tmp_path, logger):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    response = {"stdout": "x\nFAILED tests/a.py::t - boom\n1 failed, 5 passed in 0.5s\n",
                "stderr": "", "bashEditDiff": ""}
    result = _eval_response(hook_module, logger, "Bash", response)
    assert result is not None and "TEST FAILURE" in result


def test_bash_dict_stderr_failure_reported(hook_module, monkeypatch, tmp_path, logger):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    response = {"stdout": "", "stderr": "AssertionError: expected 1 to equal 2"}
    assert _eval_response(hook_module, logger, "Bash", response) is not None


def test_bash_dict_missing_stdout_stderr_fail_open(hook_module, monkeypatch, tmp_path, logger):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    assert _eval_response(hook_module, logger, "Bash", {"bashEditDiff": _EDIT_DIFF}) is None


def test_non_bash_dict_keeps_original_behavior(hook_module, monkeypatch, tmp_path, logger):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    response = {"output": "x FAILED tests/a.py::t"}
    result = _eval_response(hook_module, logger, "mcp__dart__run_tests", response)
    assert result is not None and "TEST FAILURE" in result


@pytest.mark.parametrize("output", [
    "..........\n82 passed in 0.25s\n",
    "82 passed, 2 skipped in 1.20s",
])
def test_pytest_q_green_summary_recognized(hook_module, output):
    assert hook_module._is_green_summary(output)


@pytest.mark.parametrize("output", [
    "1 failed, 81 passed in 0.25s",
    "81 passed, 1 failed in 0.25s",
    "81 passed, 1 error in 0.25s",
])
def test_pytest_q_failure_summary_not_green(hook_module, output):
    assert not hook_module._is_green_summary(output)


# --- 綠燈捷徑：任何一行摘要含 N failed / N error 即不放行 ---

@pytest.mark.parametrize("output", [
    "=== 5 passed, 1 failed in 1s ===",
    "5 passed in 1s\n1 failed in 2s",
    "===== 5 passed in 1.00s =====\n===== 2 passed, 1 error in 0.50s =====",
])
def test_green_shortcut_not_taken_when_any_summary_has_failure(hook_module, output):
    assert not hook_module._is_green_summary(output)


def test_multi_run_pytest_output_reports_test_failure(hook_module, monkeypatch, tmp_path, logger):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    response = {"stdout": "5 passed in 1s\nFAILED tests/a.py::t - boom\n1 failed in 2s\n",
                "stderr": ""}
    result = _eval_response(hook_module, logger, "Bash", response)
    assert result is not None and "TEST FAILURE" in result


@pytest.mark.parametrize("output", [
    "===== 5 passed in 1.00s =====",
    "5 passed in 1s",
    "===== 5 passed, 1 xfailed in 1.00s =====",
    "5 passed, 1 xfailed in 1s",
    "Tests: 10 passed, 0 failed",
])
def test_single_green_summary_still_green(hook_module, output):
    assert hook_module._is_green_summary(output)


# --- 裸 FAILED 樣式區分大小寫 ---

_COMMIT_TITLE_MIXED = (
    "[OK] 已提交 1fc768e\n  fix(x): post-test-hook 任一行摘要含 failed/error 即不走綠燈捷徑\n"
    "rc=0 101 passed in 0.21s"
)


def test_lowercase_failed_in_commit_title_not_test_failure(hook_module, logger):
    error_type, errors = hook_module._classify_errors(_COMMIT_TITLE_MIXED, logger)
    assert errors == []


def test_lowercase_failed_in_commit_title_end_to_end(hook_module, monkeypatch, tmp_path, logger):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    response = {"stdout": _COMMIT_TITLE_MIXED, "stderr": ""}
    assert _eval_response(hook_module, logger, "Bash", response) is None


FRAMEWORK_FAILURE_OUTPUTS = [
    pytest.param("FAILED tests/test_a.py::test_x - assert 1 == 2", id="pytest-FAILED-line"),
    pytest.param("=== 1 failed, 5 passed in 0.5s ===", id="pytest-N-failed-summary"),
    pytest.param("00:02 +3 -1: test/a_test.dart: x [E]\n00:02 +3 -1: Some tests failed.",
                 id="flutter-test"),
    pytest.param("00:01 +0 -1: test/a_test.dart: x [E]\n00:01 +0 -1: Some tests failed.",
                 id="dart-test"),
    pytest.param("FAIL src/a.test.js\n  ● x\nTests:       1 failed, 3 passed, 4 total",
                 id="jest"),
]


@pytest.mark.parametrize("output", FRAMEWORK_FAILURE_OUTPUTS)
def test_framework_real_failure_output_reports_test_failure(hook_module, logger, output):
    _, errors = hook_module._classify_errors(output, logger)
    assert any(e["type"] == "test_failure" for e in errors), output


# --- -q 綠燈摘要不要求行首 ---

def test_green_summary_with_prefix_short_circuits_despite_uppercase_title(
        hook_module, monkeypatch, tmp_path, logger):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    stdout = ("fix(x): post-test-hook 裸 FAILED 改區分大小寫並補小寫摘要樣式\n"
              "rc=0 108 passed in 2.27s")
    response = {"stdout": stdout, "stderr": ""}
    assert _eval_response(hook_module, logger, "Bash", response) is None


@pytest.mark.parametrize("stdout", [
    "rc=0 1 failed, 108 passed in 2.27s",
    "FAILED tests/x.py::t - assert\n1 failed, 3 passed in 1s",
])
def test_prefixed_failure_summary_still_reported(
        hook_module, monkeypatch, tmp_path, logger, stdout):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    result = _eval_response(hook_module, logger, "Bash", {"stdout": stdout, "stderr": ""})
    assert result is not None and "TEST FAILURE" in result


# --- 失敗摘要單一來源：綠燈前置排除與錯誤分類共用 ---

@pytest.mark.parametrize("output", [
    "3 passed in 0.1s\n00:02 +3 -1: Some tests failed.",
    "rc=0 3 passed in 0.1s\n00:02 +3 -1: Some tests failed.",
])
def test_green_shortcut_not_covering_flutter_failure(hook_module, monkeypatch, tmp_path, logger, output):
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    assert not hook_module._is_green_summary(output)
    result = _eval_response(hook_module, logger, "Bash", {"stdout": output, "stderr": ""})
    assert result is not None and "TEST FAILURE" in result


def test_green_exclusion_reuses_classifier_summary_patterns(hook_module, logger):
    for sample in ["Some tests failed", "2 failed", "1 error"]:
        assert any(p.search(sample) for p, _ in hook_module.FAILURE_SUMMARY_PATTERNS)
        _, errors = hook_module._classify_errors(sample, logger)
        assert errors and not hook_module._is_green_summary(sample + "\n5 passed in 1s")


# --- run_in_background：跳過計時與失敗評估（前景同命令照常，E1 對照） ---

_FAILING_RESPONSE = {"stdout": "FAILED tests/a.py::t - boom\n1 failed in 1s", "stderr": ""}


def _run_main(hook_module, monkeypatch, tmp_path, tool_input):
    monitor = _arm_monitor(tmp_path, 2000)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    data = {"tool_name": "Bash", "tool_input": tool_input,
            "tool_response": _FAILING_RESPONSE}
    monkeypatch.setattr(hook_module, "read_json_from_stdin", lambda _logger: data)
    return monitor


def test_foreground_command_is_timed_and_evaluated(hook_module, monkeypatch, tmp_path, capsys):
    monitor = _run_main(hook_module, monkeypatch, tmp_path, {"command": "pytest -q"})
    assert hook_module.main() == 0
    out = capsys.readouterr().out
    assert "TEST FAILURE" in out
    assert json.loads(monitor.read_text())["status"] == "completed"


def test_background_command_skips_timing_and_evaluation(
        hook_module, monkeypatch, tmp_path, capsys):
    monitor = _run_main(hook_module, monkeypatch, tmp_path,
                        {"command": "pytest -q", "run_in_background": True})
    before = monitor.read_text()
    assert hook_module.main() == 0
    assert capsys.readouterr().out == ""
    assert monitor.read_text() == before
    assert not list((tmp_path / ".claude" / "hook-logs").glob("pre-fix-evaluation-*.json"))


def test_background_false_treated_as_foreground(hook_module, monkeypatch, tmp_path, capsys):
    _run_main(hook_module, monkeypatch, tmp_path,
              {"command": "pytest -q", "run_in_background": False})
    assert hook_module.main() == 0
    assert "TEST FAILURE" in capsys.readouterr().out
