#!/usr/bin/env python3
"""
pre-test-hook - 測試程式碼

涵蓋 check_dependencies() 的 pubspec.yaml / pubspec.lock mtime 容差比較
（0.2.1-W3-987）：同批寫入（如 git checkout）產生的毫秒級 mtime 順序差
不應誤報，真正過期（使用者編輯後未執行 pub get）仍須告警。
"""

import os
import sys
import time
from pathlib import Path

import pytest

# 將 Hook 腳本路徑加入 sys.path
hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))

# 動態導入 Hook 模組（檔名含連字號，無法直接 import）
import importlib.util

spec = importlib.util.spec_from_file_location(
    "pre_test_hook_module",
    hook_dir / "pre-test-hook.py",
)
pre_test_hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pre_test_hook_module)

check_dependencies = pre_test_hook_module.check_dependencies
PUBSPEC_MTIME_TOLERANCE_SECONDS = pre_test_hook_module.PUBSPEC_MTIME_TOLERANCE_SECONDS


def _make_project(tmp_path: Path) -> Path:
    (tmp_path / ".dart_tool").mkdir()
    (tmp_path / ".dart_tool" / "package_config.json").write_text("{}")
    return tmp_path


def test_same_batch_write_does_not_warn(tmp_path):
    """Given yaml 與 lock 為同批寫入（毫秒級順序差）
    When 檢查依賴
    Then 不應告警（避免 git checkout 產生的假警告）"""
    project = _make_project(tmp_path)
    (project / "pubspec.lock").write_text("packages: {}\n")
    (project / "pubspec.yaml").write_text("name: x\n")

    lock_mtime = (project / "pubspec.lock").stat().st_mtime
    # 模擬 git checkout 依序寫入產生的毫秒級順序差（實測本專案為 0.34ms）
    os.utime(project / "pubspec.yaml", (lock_mtime + 0.0003, lock_mtime + 0.0003))

    warnings = check_dependencies(project)

    assert warnings == []


def test_actually_stale_yaml_warns(tmp_path):
    """Given yaml 比 lock 晚寫入超過容差（秒級差距，模擬使用者編輯後未 pub get）
    When 檢查依賴
    Then 應告警"""
    project = _make_project(tmp_path)
    (project / "pubspec.lock").write_text("packages: {}\n")
    lock_mtime = (project / "pubspec.lock").stat().st_mtime
    stale_mtime = lock_mtime + PUBSPEC_MTIME_TOLERANCE_SECONDS + 1
    (project / "pubspec.yaml").write_text("name: x\ndependencies:\n  foo: 2.0.0\n")
    os.utime(project / "pubspec.yaml", (stale_mtime, stale_mtime))

    warnings = check_dependencies(project)

    assert warnings == [pre_test_hook_module.ValidationMessages.PRE_TEST_PUBSPEC_OUTDATED]


def test_missing_lock_keeps_existing_behavior(tmp_path):
    """Given pubspec.lock 不存在
    When 檢查依賴
    Then 應回報 lock 缺失，不受本次容差變更影響"""
    project = tmp_path
    (project / "pubspec.yaml").write_text("name: x\n")

    warnings = check_dependencies(project)

    assert warnings == [pre_test_hook_module.ValidationMessages.PRE_TEST_PUBSPEC_LOCK_MISSING]


# ---------------------------------------------------------------------------
# is_test_command：只認敘述開頭的測試指令（0.5.0-W1-232）
#
# 舊判定以子字串比對整段命令文字，grep 的 pattern、建票命令的參數只要含
# 測試指令字樣即被當成測試執行。以下兩組輸入互為對照：應觸發組驗證辨識
# 範圍（環境變數前綴、fvm、逾時包裝、串接與子 shell），應不觸發組是測試
# 指令字樣只出現在參數或引號內的命令。
# ---------------------------------------------------------------------------

is_test_command = pre_test_hook_module.is_test_command

SHOULD_TRIGGER = [
    "flutter test",
    "fvm flutter test test/unit",
    "FLUTTER_TEST_SEED=1 fvm flutter test",
    "cd app && fvm flutter test 2>&1 | tail -20",
    "python3 .claude/scripts/run-with-timeout.py 600 -- fvm flutter test",
    ".claude/scripts/run-with-timeout.py 600 -- dart test",
    "(cd packages/core && dart test) | tail -5",
    "cd app\nfvm flutter test",
    # 包裝器前的直譯器帶旗標或經 uv 啟動
    "python3 -I .claude/scripts/run-with-timeout.py 600 -- fvm flutter test",
    "uv run python3 .claude/scripts/run-with-timeout.py 600 -- flutter test",
]

SHOULD_NOT_TRIGGER = [
    # grep 型：測試指令字樣是搜尋 pattern
    "grep -rn 'flutter test' .claude/rules",
    # grep 型：pattern 內的 \| 會被 regex 型判定誤當成管線
    'grep -n "TEST_COMMAND_PATTERN\\|flutter test\\|dart test" hook.py',
    # 建票型：測試指令字樣在參數文字內
    'ticket create --why "執行 flutter test 時 swap 耗盡" --what "閘門"',
    "ticket track append-log X --section Solution \"$(cat <<'EOF'\nfvm flutter test 全綠\nEOF\n)\"",
    # 管線後的敘述是 grep，測試指令字樣在其 pattern 內
    "echo x | grep 'dart test'",
    # 引號未閉合：shell 本身無法執行，不可能是一次測試執行
    "echo 'flutter test",
]


@pytest.mark.parametrize("command", SHOULD_TRIGGER)
def test_statement_head_test_command_triggers(command):
    """Given 敘述開頭為測試指令（含前綴、包裝、串接）
    When 判定是否為測試命令
    Then 應觸發"""
    assert is_test_command("Bash", {"command": command}) is True


@pytest.mark.parametrize("command", SHOULD_NOT_TRIGGER)
def test_test_words_inside_arguments_do_not_trigger(command):
    """Given 測試指令字樣只出現在參數或引號內
    When 判定是否為測試命令
    Then 不應觸發"""
    assert is_test_command("Bash", {"command": command}) is False


def test_dart_mcp_run_tests_triggers():
    """Given 工具為 mcp__dart__run_tests
    When 判定是否為測試命令
    Then 應觸發（不受 Bash 命令解析影響）"""
    assert is_test_command("mcp__dart__run_tests", {}) is True


def test_non_test_flutter_subcommand_does_not_trigger():
    """回歸檢查（非對照組：舊實作同樣不觸發）
    Given 敘述開頭為 flutter 的非 test 子命令
    When 判定是否為測試命令
    Then 不應觸發"""
    assert is_test_command("Bash", {"command": "flutter analyze"}) is False


# ---- 封堵：未包裝 heavy 與不帶 paths 的 MCP ----

build_block_reason = pre_test_hook_module.build_block_reason

UNWRAPPED_HEAVY = [
    "flutter test",
    "fvm flutter test",
    "FLUTTER_TEST_SEED=1 fvm flutter test",
    "timeout 600 flutter test",
    "flutter test integration_test/app_test.dart",
    "flutter build macos",
    "xcodebuild -scheme Runner",
    "uv run pytest -q",
    "(cd .claude/hooks && uv run pytest -q)",
]

PASS_THROUGH = [
    # 經包裝（含相對路徑呼叫、不帶路徑的全套件 pytest）
    "python3 .claude/scripts/run-with-timeout.py 600 -- fvm flutter test",
    "(cd /some/snapshot/.claude/hooks && python3 ../scripts/run-with-timeout.py 2400 -- uv run pytest -q -rfE)",
    # light：指定具體測試檔
    "flutter test test/unit/a_test.dart",
    "uv run pytest -q tests/test_x.py",
    "(cd .claude/hooks && uv run pytest -q tests/test_x.py)",
    # 非測試／非 heavy
    "flutter analyze",
    "flutter pub get",
    "git status",
    "env FOO=1 ls",
    "grep -rn 'flutter test' .claude",
    # 無法解析：fail-open
    "echo 'flutter test",
]


@pytest.mark.parametrize("command", UNWRAPPED_HEAVY)
def test_unwrapped_heavy_is_denied_with_copyable_wrapper(command):
    reason = build_block_reason("Bash", {"command": command})
    assert reason is not None
    assert "python3 .claude/scripts/run-with-timeout.py 600 -- " in reason
    assert "不需排隊" in reason


@pytest.mark.parametrize("command", PASS_THROUGH)
def test_wrapped_light_and_unrelated_commands_pass(command):
    assert build_block_reason("Bash", {"command": command}) is None


def test_wrapping_same_command_flips_deny_to_pass():
    """E2 正反對照：同一命令未包裝 deny、包裝後放行。"""
    bare = "fvm flutter test"
    assert build_block_reason("Bash", {"command": bare}) is not None
    wrapped = "python3 .claude/scripts/run-with-timeout.py 600 -- " + bare
    assert build_block_reason("Bash", {"command": wrapped}) is None


def test_env_prefix_suggestion_uses_env():
    reason = build_block_reason("Bash", {"command": "FOO=1 flutter test"})
    assert "-- env FOO=1 flutter test" in reason


def test_mcp_run_tests_without_paths_denied():
    for tool_input in ({}, {"roots": [{"root": "file:///x"}]}, {"roots": [{"root": "file:///x", "paths": []}]}):
        reason = build_block_reason("mcp__dart__run_tests", tool_input)
        assert reason is not None and "run-with-timeout.py" in reason


def test_mcp_run_tests_with_paths_passes():
    assert build_block_reason(
        "mcp__dart__run_tests",
        {"roots": [{"root": "file:///x", "paths": ["test/a_test.dart"]}]}) is None


def test_judgement_exception_fails_open(monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(pre_test_hook_module, "build_block_reason", boom)
    monkeypatch.setattr(pre_test_hook_module, "read_json_from_stdin",
                        lambda logger: {"tool_name": "Bash", "tool_input": {"command": "flutter test"}})
    monkeypatch.setattr(pre_test_hook_module, "check_flutter_sdk", lambda: (True, "ok"))
    monkeypatch.setattr(pre_test_hook_module, "check_dependencies", lambda d: [])
    assert pre_test_hook_module.main() == 0
    captured = capsys.readouterr()
    assert "fail-open" in captured.err
    assert "deny" not in captured.out


def _run_main_with(monkeypatch, command):
    monkeypatch.setattr(pre_test_hook_module, "read_json_from_stdin",
                        lambda logger: {"tool_name": "Bash", "tool_input": {"command": command}})
    monkeypatch.setattr(pre_test_hook_module, "check_flutter_sdk", lambda: (True, "ok"))
    monkeypatch.setattr(pre_test_hook_module, "check_dependencies", lambda d: [])


def test_parse_module_import_failure_fails_open(monkeypatch, capsys):
    """test_command_parse 匯入失敗（延遲匯入納入 try）時放行並寫 stderr。"""
    _run_main_with(monkeypatch, "fvm flutter test")
    monkeypatch.setitem(sys.modules, "lib.test_command_parse", None)
    assert pre_test_hook_module.main() == 0
    captured = capsys.readouterr()
    assert "fail-open" in captured.err
    assert "deny" not in captured.out


def test_deny_emit_failure_fails_open(monkeypatch, capsys):
    """deny 輸出組裝失敗時放行並寫 stderr，不讓例外外洩成 hook error。"""
    _run_main_with(monkeypatch, "fvm flutter test")
    real_emit = pre_test_hook_module.emit_hook_output

    def emit(*args, **kwargs):
        if kwargs.get("permission_decision") == "deny":
            raise RuntimeError("emit boom")
        return real_emit(*args, **kwargs)

    monkeypatch.setattr(pre_test_hook_module, "emit_hook_output", emit)
    assert pre_test_hook_module.main() == 0
    assert "fail-open" in capsys.readouterr().err


def test_suggestion_puts_redirect_outside_wrapper():
    import shlex
    reason = build_block_reason("Bash", {"command": "pytest tests/ -q 2>&1"})
    line = [ln.strip() for ln in reason.splitlines() if ln.strip().startswith("python3 ")][0]
    tokens = shlex.split(line)
    after = tokens[tokens.index("--") + 1:]
    assert after == ["pytest", "tests/", "-q", "2>&1"]
    assert line.endswith(" -q 2>&1")
    # 命令部分（-- 之後、重導向之前）不含重導向 token
    assert "2>&1" not in line.split(" -- ", 1)[1].rsplit(" 2>&1", 1)[0]
    assert "'2>&1'" not in line


# --- shell 變數指定測試目標：無法判定即 fail-open ---

VARIABLE_TARGET_PASS = [
    "t=tests/test_x.py && pytest $t -m wallclock",
    "t=tests/test_x.py; uv run pytest -q ${t}",
    "f=test/a_test.dart && flutter test $f",
    "pytest -m wallclock $t",
]


@pytest.mark.parametrize("command", VARIABLE_TARGET_PASS)
def test_variable_target_passes(command):
    assert build_block_reason("Bash", {"command": command}) is None


def test_variable_target_flips_against_literal_and_bare():
    """E1／E2 對照：字面路徑放行、變數放行、未指定測試檔仍 deny。"""
    assert build_block_reason("Bash", {"command": "pytest tests/test_x.py -m wallclock"}) is None
    assert build_block_reason("Bash", {"command": "t=tests/test_x.py && pytest $t -m wallclock"}) is None
    assert build_block_reason("Bash", {"command": "t=tests/test_x.py && pytest -m wallclock"}) is not None
    assert build_block_reason("Bash", {"command": "t=a && pytest -m $t"}) is not None  # 變數是選項值非目標


def test_variable_target_does_not_hide_other_bare_heavy_statement():
    reason = build_block_reason("Bash", {"command": "pytest $t && flutter test"})
    assert reason is not None and "flutter test" in reason


def test_variable_target_writes_stderr_and_passes_main(monkeypatch, capsys):
    _run_main_with(monkeypatch, "t=tests/test_x.py && pytest $t")
    assert pre_test_hook_module.main() == 0
    captured = capsys.readouterr()
    assert "fail-open" in captured.err and "$t" in captured.err
    assert "deny" not in captured.out
