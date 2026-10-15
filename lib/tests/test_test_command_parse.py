#!/usr/bin/env python3
"""
test_command_parse 模組單元測試（0.5.0-W1-232.1）

驗證項目：
1. 應偵測：flutter／dart／pytest／npm 測試呼叫，含前綴、包裝腳本、uv run 啟動形態
2. 不應偵測：測試指令字樣位於引號、參數或其他命令引數內
3. 失敗語意：無法 tokenize 回 None，可解析但無命中回 []
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.test_command_parse import (
    ALL_RUNNERS,
    WEIGHT_HEAVY,
    WEIGHT_LIGHT,
    classify_argv_weight,
    find_test_invocations,
)

WRAPPER = "python3 .claude/scripts/run-with-timeout.py 300 --"


def _runners(command):
    invocations = find_test_invocations(command)
    return None if invocations is None else [inv.runner for inv in invocations]


@pytest.mark.parametrize("command, expected", [
    ("flutter test", ["flutter"]),
    ("fvm flutter test test/unit", ["flutter"]),
    ("dart test", ["dart"]),
    ("FLUTTER_TEST_SEED=1 fvm flutter test", ["flutter"]),
    ("env A=1 flutter test", ["flutter"]),
    ("timeout 600 fvm flutter test", ["flutter"]),
    ("timeout -k 5 600 dart test", ["dart"]),
    ("cd app && fvm flutter test 2>&1 | tail -20", ["flutter"]),
    ("(cd packages/core && dart test) | tail -5", ["dart"]),
    ("cd app\nfvm flutter test", ["flutter"]),
    # 包裝腳本後接的命令（E 線轉交）
    (f"{WRAPPER} fvm flutter test", ["flutter"]),
    (".claude/scripts/run-with-timeout.py 60 -- flutter test", ["flutter"]),
    ("python3 -I .claude/scripts/run-with-timeout.py 600 -- fvm flutter test", ["flutter"]),
    ("uv run python3 .claude/scripts/run-with-timeout.py 600 -- dart test", ["dart"]),
    # pytest 三種形態
    ("pytest tests/test_x.py -q", ["pytest"]),
    ("python3 -m pytest tests/ -q", ["pytest"]),
    ("uv --directory .claude/hooks run --with pytest --with pyyaml python -m pytest tests/test_x.py -q", ["pytest"]),
    (f"{WRAPPER} uv --directory .claude/scripts run --with pytest python -m pytest tests -q", ["pytest"]),
    ("uv run pytest -q", ["pytest"]),
    # npm（既有 post-test 覆蓋範圍）
    ("npm test", ["npm"]),
    ("npm test:unit", ["npm"]),
    ("npm run test:hooks", ["npm"]),
    ("NODE_ENV=test npm test", ["npm"]),
    # 多個測試呼叫
    ("flutter test && pytest -q", ["flutter", "pytest"]),
])
def test_test_invocations_detected(command, expected):
    assert _runners(command) == expected


@pytest.mark.parametrize("command", [
    # 測試指令字樣在參數或引號內
    "grep -rn 'flutter test' .claude/rules",
    'grep -n "TEST_COMMAND_PATTERN\\|flutter test\\|dart test" hook.py',
    "echo x | grep 'dart test'",
    'ticket create --why "執行 flutter test 時 swap 耗盡" --what "閘門"',
    "ticket track append-log X --section Solution \"$(cat <<'EOF'\nfvm flutter test 全綠\nEOF\n)\"",
    'echo "npm test"',
    "echo dart test result",
    # 包裝器不在命令位置
    "grep run-with-timeout.py -- flutter test",
    # pytest 字樣只是 uv 選項值或其他命令的引數
    "uv run --with pytest python script.py",
    "pip install pytest",
    "python3 -m pip install pytest",
    # 非 test 子命令
    "flutter analyze",
    "npm run build",
    "uv sync",
    "",
])
def test_non_test_commands_not_detected(command):
    assert _runners(command) == []


def test_unparseable_command_returns_none():
    assert find_test_invocations("echo 'flutter test") is None


def test_statement_keeps_launch_prefix_for_display():
    (invocation,) = find_test_invocations(f"{WRAPPER} fvm flutter test")
    assert invocation.statement[0] == "python3"


def test_all_runners_constant_covers_every_runner():
    assert ALL_RUNNERS == {"flutter", "dart", "npm", "pytest"}


# 0.5.0-W1-239：漏判形態（本機閘門以此判定 heavy 工作，漏判即繞過）
@pytest.mark.parametrize("command, expected", [
    ("python3 -X dev -m pytest", ["pytest"]),
    ("python3 -W ignore -m pytest tests -q", ["pytest"]),
    ("python3 -X dev -W error -m pytest", ["pytest"]),
    ("uv run python -X dev -m pytest", ["pytest"]),
    ("python3 -X dev .claude/scripts/run-with-timeout.py 60 -- flutter test", ["flutter"]),
    ("sudo -u x pytest -q", ["pytest"]),
    ("sudo -E flutter test", ["flutter"]),
    ("env -u FOO flutter test", ["flutter"]),
    ("env -i A=1 dart test", ["dart"]),
    ("dart --enable-asserts test", ["dart"]),
    ("flutter --no-color test", ["flutter"]),
    ("flutter -v test", ["flutter"]),
    ("flutter --device-id macos test", ["flutter"]),
    ("npm --prefix app test", ["npm"]),
    ("npm --silent run test:unit", ["npm"]),
    ("npm run -w pkg test", ["npm"]),
    ("npm t", ["npm"]),
])
def test_hardened_forms_detected(command, expected):
    assert _runners(command) == expected


@pytest.mark.parametrize("command", [
    "python3 -X dev script.py",
    "sudo -u x ls",
    "env -u FOO printenv",
    "flutter --no-color analyze",
    "npm --prefix app run build",
])
def test_hardened_forms_do_not_overmatch(command):
    assert _runners(command) == []


def test_private_skip_prefix_alias_still_importable():
    from lib import git_command_parse as g

    assert g._skip_prefix_wrapper_count is g.skip_prefix_wrapper_count


# 0.5.0-W1-239 追修：Phase 4 審查三項漏判
@pytest.mark.parametrize("command, expected", [
    ("nohup sudo -u x pytest", ["pytest"]),
    ("time sudo -u x flutter test", ["flutter"]),
    ("nohup env -u X pytest", ["pytest"]),
    ("xargs nohup env -u X dart test", ["dart"]),
])
def test_wrapper_prefix_then_sudo_env_detected(command, expected):
    assert _runners(command) == expected


@pytest.mark.parametrize("command, expected", [
    ("sudo -iu x pytest", ["pytest"]),
    ("sudo -Eu x flutter test", ["flutter"]),
    ("flutter -vd macos test", ["flutter"]),
])
def test_merged_short_options_consume_value(command, expected):
    assert _runners(command) == expected


@pytest.mark.parametrize("command, expected", [
    ("env -P /usr/bin pytest", ["pytest"]),
    ("flutter --local-engine host_debug test", ["flutter"]),
    ("flutter --local-engine-src-path /e test", ["flutter"]),
    ("flutter --local-engine-host host_debug test", ["flutter"]),
    ("flutter --local-web-sdk wasm_release test", ["flutter"]),
])
def test_missing_value_options_added(command, expected):
    assert _runners(command) == expected


@pytest.mark.parametrize("argv", [
    ["flutter", "test"],
    ["flutter", "test", "test/"],
    ["fvm", "flutter", "test"],
    ["flutter", "build", "macos"],
    ["xcodebuild", "-scheme", "Runner"],
    ["pytest"],
    ["pytest", "tests/"],
    ["python3", "-m", "pytest"],
    ["uv", "run", "pytest", "-q"],
    ["dart", "test"],
    ["flutter", "test", "integration_test/app_test.dart"],
    ["flutter", "test", "integration_test"],
])
def test_argv_weight_heavy(argv):
    assert classify_argv_weight(argv) == WEIGHT_HEAVY


@pytest.mark.parametrize("argv", [
    ["flutter", "test", "test/a_test.dart"],
    ["dart", "test", "test/a_test.dart"],
    ["pytest", "tests/test_a.py"],
    ["pytest", "tests/a_test.py"],
    ["pytest", "tests/test_a.py::test_x"],
    ["pytest", "-q", "tests/test_a.py", "-k", "x"],
    ["python3", "-m", "pytest", "tests/test_a.py"],
    ["uv", "run", "pytest", "tests/test_a.py"],
    ["echo", "hi"],
    ["python3", "script.py"],
    [],
])
def test_argv_weight_light(argv):
    assert classify_argv_weight(argv) == WEIGHT_LIGHT


@pytest.mark.parametrize("argv", [
    ["env", "A=1", "./scripts/run.sh"],
    ["sudo", "./build.sh"],
    ["nohup", "./all.sh"],
    ["timeout", "10", "./x.sh"],
    ["xargs", "./x.sh"],
])
def test_argv_weight_launcher_led_unknown_runner_is_heavy(argv):
    """判定退路：launcher 開頭而剝除後判不出 runner，保守視為 heavy。"""
    assert classify_argv_weight(argv) == WEIGHT_HEAVY


@pytest.mark.parametrize("argv", [
    ["pytest", "tests/", "tests/test_a.py"],
    ["flutter", "test", "test/", "test/a_test.dart"],
    ["pytest", "tests/test_a.py", "tests/"],
    ["pytest", "tests/", "-k", "test_a.py"],
    ["pytest", "-c", "test_cfg.py", "tests/"],
    ["pytest", "-m", "slow", "--rootdir", "test_root.py", "tests/"],
    ["pytest", "-k", "x"],
    ["xcrun", "xcodebuild", "-scheme", "Runner"],
    ["flutter", "drive", "--target=integration_test/app.dart"],
    ["flutter", "test", "-d", "macos", "test/"],
])
def test_argv_weight_heavy_bypass_forms(argv):
    """light 須是全部位置參數皆為具體測試檔；帶值選項的值不是路徑。"""
    assert classify_argv_weight(argv) == WEIGHT_HEAVY


@pytest.mark.parametrize("argv", [
    ["pytest", "tests/test_a.py", "tests/test_b.py"],
    ["pytest", "-k", "foo", "tests/test_a.py"],
    ["pytest", "-c", "cfg.ini", "tests/test_a.py::test_x"],
    ["flutter", "test", "--name", "foo", "test/a_test.dart"],
    ["xcrun", "simctl", "list"],
])
def test_argv_weight_light_after_option_values_removed(argv):
    assert classify_argv_weight(argv) == WEIGHT_LIGHT


@pytest.mark.parametrize("argv", [
    ["flutter", "test", "--coverage", "test/", "test/a_test.dart"],
    ["flutter", "test", "--run-skipped", "test/", "test/a_test.dart"],
    ["pytest", "--cov", "tests/", "tests/test_a.py"],
    ["pytest", "--cov", "src", "tests/test_a.py"],
])
def test_argv_weight_heavy_flag_not_swallowing_next_arg(argv):
    """不帶值的開關（或值可省略者）不得吞掉後一個位置參數。"""
    assert classify_argv_weight(argv) == WEIGHT_HEAVY


def test_argv_weight_flag_forms_still_light_with_specific_file():
    assert classify_argv_weight(["flutter", "test", "--coverage", "test/a_test.dart"]) == WEIGHT_LIGHT
    assert classify_argv_weight(["pytest", "--cov=src", "tests/test_a.py"]) == WEIGHT_LIGHT


def test_argv_weight_option_value_that_is_a_path_is_heavy(tmp_path):
    """根本防線：被當成選項值吞掉的 token 若像路徑，整體判 heavy，白名單分錯類也只會多排隊。"""
    assert classify_argv_weight(["pytest", "--basetemp", "some/dir", "tests/test_a.py"]) == WEIGHT_HEAVY
    assert classify_argv_weight(["pytest", "--ignore", str(tmp_path), "tests/test_a.py"]) == WEIGHT_HEAVY
    assert classify_argv_weight(["pytest", "-k", "name", "tests/test_a.py"]) == WEIGHT_LIGHT


def test_find_unwrapped_heavy_distinguishes_wrapped():
    from lib.test_command_parse import find_unwrapped_heavy
    assert find_unwrapped_heavy("fvm flutter test") == [("fvm", "flutter", "test")]
    assert find_unwrapped_heavy("python3 ../scripts/run-with-timeout.py 60 -- uv run pytest -q") == []
    assert find_unwrapped_heavy("uv run pytest -q tests/test_x.py") == []
    assert find_unwrapped_heavy("env FOO=1 ls") == []
    assert find_unwrapped_heavy("echo 'x") is None


@pytest.mark.parametrize("argv", [
    ["flutter", "test", "--help"],
    ["dart", "test", "-h"],
    ["flutter", "build", "--help"],
    ["xcodebuild", "-version"],
    ["pytest", "--collect-only", "tests/"],
    ["pytest", "--version"],
])
def test_query_flags_classified_light(argv):
    from lib.test_command_parse import classify_argv_weight, WEIGHT_LIGHT
    assert classify_argv_weight(argv) == WEIGHT_LIGHT


def test_no_query_flag_still_heavy():
    from lib.test_command_parse import classify_argv_weight, WEIGHT_HEAVY
    assert classify_argv_weight(["pytest", "tests/"]) == WEIGHT_HEAVY
    assert classify_argv_weight(["pytest", "-k", "foo"]) == WEIGHT_HEAVY


def test_unwrapped_heavy_strips_trailing_control_operators():
    from lib.test_command_parse import find_unwrapped_heavy
    assert find_unwrapped_heavy("nohup flutter test &") == [("nohup", "flutter", "test")]
    assert find_unwrapped_heavy("flutter build macos;") == [("flutter", "build", "macos")]


# ---- 重導向不計入位置參數 ----

REDIRECT_SUFFIXES = ["2>&1", "> out.log", "2> /tmp/e", "2>/tmp/e", "&> x", ">>log", "< in", ">out 2>&1"]


@pytest.mark.parametrize("suffix", REDIRECT_SUFFIXES)
@pytest.mark.parametrize("runner", ["pytest tests/test_x.py -q", "uv run pytest -q tests/test_x.py",
                                    "flutter test test/a_test.dart"])
def test_single_file_with_redirect_is_not_unwrapped_heavy(runner, suffix):
    from lib.test_command_parse import find_unwrapped_heavy
    assert find_unwrapped_heavy("{} {}".format(runner, suffix)) == []


@pytest.mark.parametrize("suffix", REDIRECT_SUFFIXES)
@pytest.mark.parametrize("runner", ["pytest tests/", "flutter test", "uv run pytest -q"])
def test_directory_with_redirect_stays_heavy(runner, suffix):
    """E2 對照：同形但目標為目錄或全套件者仍判 heavy，命令部分不含重導向。"""
    from lib.test_command_parse import find_unwrapped_heavy
    found = find_unwrapped_heavy("{} {}".format(runner, suffix))
    assert len(found) == 1
    assert not any(t in ("2>&1", ">", "<", "&>", ">>", "out.log", "x", "in") for t in found[0])


def test_redirect_rendering_for_suggestion():
    from lib.test_command_parse import find_unwrapped_heavy_with_redirects
    assert find_unwrapped_heavy_with_redirects("pytest tests/ 2>&1") == [(("pytest", "tests/"), "2>&1")]
    assert find_unwrapped_heavy_with_redirects("pytest tests/ 2> /tmp/e") == [(("pytest", "tests/"), "2> /tmp/e")]
    assert find_unwrapped_heavy_with_redirects("pytest tests/ >out 2>&1 &") == [
        (("pytest", "tests/"), "> out 2>&1")]


def test_classify_argv_weight_unchanged_for_redirect_like_argv():
    from lib.test_command_parse import classify_argv_weight, WEIGHT_HEAVY
    assert classify_argv_weight(["pytest", "tests/test_x.py", "2>&1"]) == WEIGHT_HEAVY


# ---- 明確指定的既存一般檔案（不論命名）判 light ----


def _make_files(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a.py").write_text("def test_one():\n    pass\n")
    (tmp_path / "tests" / "b.dart").write_text("void main() {}\n")
    (tmp_path / "tests" / "notes.txt").write_text("x\n")
    return tmp_path


def test_explicit_non_test_named_file_is_light_both_ends(tmp_path):
    from lib.test_command_parse import find_unwrapped_heavy
    root = _make_files(tmp_path)
    py = str(root / "tests" / "a.py")
    assert classify_argv_weight(["pytest", py]) == WEIGHT_LIGHT
    assert classify_argv_weight(["uv", "run", "pytest", py, "-q"]) == WEIGHT_LIGHT
    assert find_unwrapped_heavy("uv run pytest {} -q".format(py)) == []
    assert find_unwrapped_heavy("pytest {} 2>&1 | tail -5".format(py)) == []
    assert classify_argv_weight(["flutter", "test", str(root / "tests" / "b.dart")]) == WEIGHT_LIGHT


def test_explicit_file_counterpart_directory_stays_heavy(tmp_path):
    """E2 對照：同一批 fixture 下指向目錄仍 heavy。"""
    from lib.test_command_parse import find_unwrapped_heavy
    root = _make_files(tmp_path)
    directory = str(root / "tests")
    assert classify_argv_weight(["pytest", directory]) == WEIGHT_HEAVY
    assert find_unwrapped_heavy("uv run pytest {}".format(directory)) != []
    assert classify_argv_weight(["pytest", str(root / "tests" / "a.py"), directory]) == WEIGHT_HEAVY


def test_missing_glob_wrong_extension_and_integration_stay_heavy(tmp_path):
    root = _make_files(tmp_path)
    assert classify_argv_weight(["pytest", str(root / "tests" / "missing.py")]) == WEIGHT_HEAVY
    assert classify_argv_weight(["pytest", str(root / "tests" / "*.py")]) == WEIGHT_HEAVY
    assert classify_argv_weight(["pytest", str(root / "tests" / "notes.txt")]) == WEIGHT_HEAVY
    (root / "integration_test").mkdir()
    (root / "integration_test" / "app.dart").write_text("void main() {}\n")
    assert classify_argv_weight(
        ["flutter", "test", str(root / "integration_test" / "app.dart")]) == WEIGHT_HEAVY


def test_relative_path_resolved_against_uv_directory(tmp_path, monkeypatch):
    """路徑基準與 pytest 一致：uv --directory 改變子程序 cwd，相對路徑對該目錄解析。"""
    from lib.test_command_parse import find_unwrapped_heavy
    root = _make_files(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    argv = ["uv", "--directory", str(root), "run", "pytest", "tests/a.py"]
    assert classify_argv_weight(argv) == WEIGHT_LIGHT
    assert find_unwrapped_heavy("uv --directory {} run pytest tests/a.py".format(root)) == []
    assert find_unwrapped_heavy("uv --directory={} run pytest tests/a.py".format(root)) == []
    # 不帶 --directory：對 cwd 解析，該檔不存在 -> heavy
    assert classify_argv_weight(["uv", "run", "pytest", "tests/a.py"]) == WEIGHT_HEAVY
    monkeypatch.chdir(root)
    assert classify_argv_weight(["pytest", "tests/a.py"]) == WEIGHT_LIGHT


def test_file_check_exception_falls_back_to_heavy(tmp_path, monkeypatch):
    """失敗語意：判準本身例外時保守判 heavy。"""
    import os
    root = _make_files(tmp_path)

    def boom(_path):
        raise OSError("simulated")

    monkeypatch.setattr(os.path, "isfile", boom)
    assert classify_argv_weight(["pytest", str(root / "tests" / "a.py")]) == WEIGHT_HEAVY
    # 命名樣式命中者不經檔案檢查，維持 light
    assert classify_argv_weight(["pytest", "tests/test_a.py"]) == WEIGHT_LIGHT
