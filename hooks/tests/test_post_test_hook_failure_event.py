r"""
test_post_test_hook_failure_event.py

0.5.0-W1-281.2：post-test-hook 與 cli-error-feedback-hook 處理 PostToolUseFailure:Bash。

背景：未遮蔽的失敗命令（Exit code N）只觸發 PostToolUseFailure，payload 無 tool_response，
改帶 error 欄位（首行 `Exit code N`，其後為交錯的 stdout 與 stderr）。
fixture 依 post-tool-failure-liveness-hook 日誌中的真實樣本形狀構造。

E2：未遮蔽失敗 pytest 的 PostToolUseFailure 樣本，斷言產生結構化失敗評估紀錄。
"""

import importlib.util
import io
import json
import logging
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
POST_TEST_HOOK = HOOKS_DIR / "post-test-hook.py"
CLI_FEEDBACK_HOOK = HOOKS_DIR.parent / "skills" / "ticket" / "hooks" / "cli-error-feedback-hook.py"

PYTEST_FAILURE_ERROR = (
    "Exit code 1\n"
    "============================= test session starts ==============================\n"
    "collected 2 items\n\n"
    "tests/test_sample.py .F                                                  [100%]\n\n"
    "=================================== FAILURES ===================================\n"
    "FAILED tests/test_sample.py::test_b - assert 1 == 2\n"
    "========================= 1 failed, 1 passed in 0.12s =========================\n"
)

CLI_ARGPARSE_ERROR = (
    "Exit code 2\n"
    "usage: ticket track close [-h] ticket_id\n"
    "ticket track close: error: unrecognized arguments: --bogus\n"
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def post_test():
    return _load(POST_TEST_HOOK, "post_test_hook_failure_event")


@pytest.fixture(scope="module")
def cli_feedback():
    return _load(CLI_FEEDBACK_HOOK, "cli_error_feedback_failure_event")


@pytest.fixture
def logger():
    return logging.getLogger("test-failure-event")


def _failure_payload(command: str, error, **extra):
    payload = {
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "is_interrupt": False,
        "duration_ms": 1200,
        "error": error,
    }
    payload.update(extra)
    return payload


def _reports(root: Path):
    return sorted((root / ".claude" / "hook-logs").glob("pre-fix-evaluation-*.json"))


def _run_main(module, monkeypatch, capsys, raw_stdin: str):
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw_stdin))
    rc = module.main()
    return rc, capsys.readouterr()


# ---------------------------------------------------------------------------
# E2：未遮蔽失敗 pytest 產生失敗評估紀錄
# ---------------------------------------------------------------------------

def test_unmasked_failing_pytest_writes_evaluation_report(post_test, logger, tmp_path, monkeypatch):
    monkeypatch.setattr(post_test, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(post_test, "get_hook_log_dir", lambda n: tmp_path / ".claude" / "hook-logs" / n)
    payload = _failure_payload("uv run pytest tests/test_sample.py", PYTEST_FAILURE_ERROR)

    message = post_test.evaluate_test_failure(payload, payload["tool_input"], logger)

    reports = _reports(tmp_path)
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["hook_event_name"] == "PostToolUseFailure"
    assert report["error_type"] == "test_failure"
    assert report["error_count"] >= 1
    assert message is not None


def test_main_emits_failure_event_name(post_test, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(post_test, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(post_test, "get_hook_log_dir", lambda n: tmp_path / ".claude" / "hook-logs" / n)
    payload = _failure_payload("pytest tests/test_sample.py", PYTEST_FAILURE_ERROR)

    rc, captured = _run_main(post_test, monkeypatch, capsys, json.dumps(payload))

    assert rc == 0
    out = json.loads(captured.out)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUseFailure"
    assert len(_reports(tmp_path)) == 1


def test_masked_failure_post_tool_use_still_evaluated(post_test, logger, tmp_path, monkeypatch):
    monkeypatch.setattr(post_test, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(post_test, "get_hook_log_dir", lambda n: tmp_path / ".claude" / "hook-logs" / n)
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/ ; echo done"},
        "tool_response": {"stdout": PYTEST_FAILURE_ERROR.split("\n", 1)[1], "stderr": ""},
    }

    assert post_test.evaluate_test_failure(payload, payload["tool_input"], logger) is not None
    report = json.loads(_reports(tmp_path)[0].read_text(encoding="utf-8"))
    assert report["hook_event_name"] == "PostToolUse"


# ---------------------------------------------------------------------------
# fail-open
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("error", [None, 123, "", "no exit code line\nFAILED x", "Exit code abc\nFAILED x"])
def test_post_test_unparseable_error_is_skipped(post_test, logger, tmp_path, monkeypatch, error):
    monkeypatch.setattr(post_test, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(post_test, "get_hook_log_dir", lambda n: tmp_path / ".claude" / "hook-logs" / n)
    payload = _failure_payload("pytest tests/", error)

    assert post_test.evaluate_test_failure(payload, payload["tool_input"], logger) is None
    assert _reports(tmp_path) == []


@pytest.mark.parametrize("raw", ["", "not json {{{", "[1, 2"])
def test_post_test_bad_stdin_does_not_block(post_test, monkeypatch, capsys, raw):
    rc, captured = _run_main(post_test, monkeypatch, capsys, raw)
    assert rc == 0
    assert captured.out == ""


@pytest.mark.parametrize("raw", ["", "not json {{{"])
def test_cli_feedback_bad_stdin_does_not_block(cli_feedback, monkeypatch, capsys, raw):
    rc, captured = _run_main(cli_feedback, monkeypatch, capsys, raw)
    assert rc == 0
    assert "additionalContext" not in captured.out


@pytest.mark.parametrize("error", [None, 5, "garbage without exit line"])
def test_cli_feedback_unparseable_error_is_skipped(cli_feedback, logger, error):
    payload = _failure_payload("ticket track close 1 --bogus", error)

    assert cli_feedback.check_skill_cli_error(payload, logger) is None
    assert cli_feedback.check_general_cli_failure(payload, logger) is None


# ---------------------------------------------------------------------------
# cli-error-feedback：失敗事件
# ---------------------------------------------------------------------------

def test_cli_feedback_detects_argparse_failure_event(cli_feedback, logger):
    payload = _failure_payload("ticket track close 1 --bogus", CLI_ARGPARSE_ERROR)

    context = cli_feedback.check_skill_cli_error(payload, logger)

    assert context is not None
    assert "參數不存在" in context


def test_cli_feedback_general_failure_event_returns_reminder(cli_feedback, logger):
    payload = _failure_payload("some-tool --flag", "Exit code 1\nsome-tool: boom\n")

    assert cli_feedback.check_general_cli_failure(payload, logger) is not None


def test_cli_feedback_main_emits_failure_event_name(cli_feedback, monkeypatch, capsys):
    payload = _failure_payload("ticket track close 1 --bogus", CLI_ARGPARSE_ERROR)

    rc, captured = _run_main(cli_feedback, monkeypatch, capsys, json.dumps(payload))

    assert rc == 0
    assert json.loads(captured.out)["hookSpecificOutput"]["hookEventName"] == "PostToolUseFailure"


# ---------------------------------------------------------------------------
# mcp__dart__run_tests 的 PostToolUseFailure
# 欄位依官方文件（頂層 error 字串，無 tool_response）；未在 dart consumer 實機確認，
# 缺欄位或形狀不同時只記日誌、不輸出、不拋例外。
# ---------------------------------------------------------------------------

DART_FAILURE_ERROR = (
    "Some tests failed.\n"
    "00:02 +3 -1: test/widget_test.dart: counter increments [E]\n"
    "  Expected: <1>\n    Actual: <0>\n"
    "00:02 +3 -1: Some tests failed.\n"
)


def _dart_failure_payload(**fields):
    payload = {
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "mcp__dart__run_tests",
        "tool_input": {"roots": [{"root": "file:///proj"}]},
        "is_interrupt": False,
        "duration_ms": 2300,
    }
    payload.update(fields)
    return payload


def test_dart_failure_event_is_evaluated(post_test, tmp_path, monkeypatch, capsys):
    """正向對照：error 為字串時產出失敗評估，事件名為 PostToolUseFailure。"""
    monkeypatch.setattr(post_test, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(post_test, "get_hook_log_dir", lambda n: tmp_path / ".claude" / "hook-logs" / n)
    payload = _dart_failure_payload(error=DART_FAILURE_ERROR)

    rc, captured = _run_main(post_test, monkeypatch, capsys, json.dumps(payload))

    assert rc == 0
    out = json.loads(captured.out)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUseFailure"
    assert "修復前強制評估" in out["hookSpecificOutput"]["additionalContext"]
    assert len(_reports(tmp_path)) == 1


@pytest.mark.parametrize("fields", [
    {},                                   # 缺 error
    {"error": None},
    {"error": ""},
    {"error": {"message": "x"}},          # 形狀不同
    {"error": ["Some tests failed."]},
    {"tool_response": {"content": [{"type": "text", "text": "Some tests failed."}]}},  # 只有 tool_response
])
def test_dart_failure_event_unusable_payload_is_silent(post_test, tmp_path, monkeypatch, capsys, caplog, fields):
    monkeypatch.setattr(post_test, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(post_test, "get_hook_log_dir", lambda n: tmp_path / ".claude" / "hook-logs" / n)
    payload = _dart_failure_payload(**fields)

    with caplog.at_level(logging.INFO):
        rc, captured = _run_main(post_test, monkeypatch, capsys, json.dumps(payload))

    assert rc == 0
    assert captured.out == ""
    assert _reports(tmp_path) == []
    assert any("mcp__dart__run_tests 失敗事件的 error 不可用" in r.getMessage() for r in caplog.records)


def test_dart_failure_registered_in_settings():
    settings = json.loads((HOOKS_DIR.parent / "settings.json").read_text(encoding="utf-8"))
    entries = [
        h["command"]
        for m in settings["hooks"].get("PostToolUseFailure", [])
        if m.get("matcher") == "mcp__dart__run_tests"
        for h in m["hooks"]
    ]
    assert any(c.endswith("/.claude/hooks/post-test-hook.py") for c in entries)
