#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
測試前環境檢查 Hook (PreToolUse)

功能:
  在執行 flutter test 前檢查開發環境就緒狀態:
  1. Flutter SDK 可用性
  2. pubspec.lock 存在（依賴已安裝）
  3. .dart_tool/package_config.json 存在（pub get 已執行）

封堵（deny）:
  名額閘門只對經 run-with-timeout.py 的命令生效，本 hook 封住繞過它的兩條路徑:
  1. Bash 直接執行 heavy 命令（未指定具體測試檔的 flutter／dart／pytest 測試、
     npm test、integration_test、flutter build／drive、xcodebuild）而未經
     run-with-timeout.py 包裝 -> deny，訊息附可直接複製的包裝寫法。
  2. mcp__dart__run_tests 未帶 paths（會跑全套件）-> deny，指向 Bash 包裝寫法；帶 paths 放行。
  light 命令（指定具體測試檔）不經包裝亦放行。
  判定失敗（命令無法解析、判定拋例外）一律 fail-open 放行並寫 stderr：
  封堵端誤判會擋掉正當命令，代價高於漏擋。
  liveness：deny 時 hook 日誌（.claude/hook-logs/pre-test-hook/）記一行 warning；
  實地確認以「裸 heavy 命令被 deny、包裝後同一命令放行」成對觸發。

不涵蓋（已知破口，不在封堵範圍）:
  - bash -c '...'／sh -c／python -c：命令在引號字串內，需二次解析
  - 經 shell 腳本間接執行（腳本檔內含 flutter test）：命令在腳本檔內
  - yarn／pnpm／npx 的測試，以及 test_command_parse 未列入帶值集合的自訂選項
  - mcp__dart__run_tests 帶 paths 但 paths 指向整個目錄：視為明示範圍而放行
  - 測試目標含未展開 shell 變數（`t=tests/x.py` 後 `pytest $t`）：無法由字面判定，
    視為無法判定而 fail-open 放行（變數若實際指向目錄也不擋），stderr 與日誌各記一行

觸發時機: PreToolUse (Bash: flutter test, mcp__dart__run_tests)

輸出:
  環境就緒: allow，附帶確認訊息
  環境異常: allow + stderr 警告（不阻止，但提醒問題）
"""

import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root, read_json_from_stdin, emit_hook_output
from lib.hook_messages import ValidationMessages
from lib.test_command_parse import RUNNER_DART, RUNNER_FLUTTER, find_test_invocations


# 測試命令判定（2026-10-14 改用共用模組）
#
# 判定邏輯在 lib/test_command_parse.py（只認敘述開頭的測試指令，引號內字樣
# 不算）。本 hook 的職責是 Flutter 環境檢查，只關心 flutter／dart。
FLUTTER_RUNNERS = frozenset({RUNNER_FLUTTER, RUNNER_DART})


def is_test_command(tool_name: str, tool_input: dict) -> bool:
    """判斷是否為 Flutter 測試命令：任一測試呼叫的 runner 為 flutter／dart。"""
    if tool_name != "Bash":
        return tool_name == "mcp__dart__run_tests"
    invocations = find_test_invocations(tool_input.get("command", ""))
    # 解析失敗（None）即略過：本 hook 為提示型檢查，漏判一次只少做環境檢查、不擋命令
    return any(inv.runner in FLUTTER_RUNNERS for inv in invocations or [])


WRAPPER_PATH = ".claude/scripts/run-with-timeout.py"
WRAPPER_TIMEOUT_SECONDS = 600
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _wrapped_form(statement: tuple, redirects: str = "") -> str:
    """產生可直接複製的包裝寫法；前導 KEY=VAL 需經 env，否則包裝腳本無法 exec。

    重導向屬於外層 shell，原樣接在包裝命令之後（不可放進 `--` 之後，否則成為命令參數）。
    """
    tokens = list(statement)
    if tokens and _ENV_ASSIGNMENT_RE.match(tokens[0]):
        tokens = ["env"] + tokens
    wrapped = "python3 {} {} -- {}".format(WRAPPER_PATH, WRAPPER_TIMEOUT_SECONDS, shlex.join(tokens))
    return "{} {}".format(wrapped, redirects) if redirects else wrapped


def _mcp_has_paths(tool_input: dict) -> bool:
    """mcp__dart__run_tests 是否限定了測試範圍（頂層 paths 或 roots[].paths 任一非空）。"""
    if tool_input.get("paths"):
        return True
    roots = tool_input.get("roots") or []
    return any(isinstance(r, dict) and r.get("paths") for r in roots)


def build_block_reason(tool_name: str, tool_input: dict):
    """回傳封堵理由；放行回 None。判定失敗由呼叫端 fail-open。"""
    if tool_name == "mcp__dart__run_tests":
        if _mcp_has_paths(tool_input):
            return None
        return (
            "mcp__dart__run_tests 未帶 paths 會跑全套件，繞過本機名額閘門。"
            "請改用 Bash 經包裝執行：python3 {} {} -- fvm flutter test"
            "（{} 為逾時秒數，可依套件大小調整）；"
            "或在 roots 的 paths 指定具體測試檔（指定具體測試檔的執行不需排隊）。".format(
                WRAPPER_PATH, WRAPPER_TIMEOUT_SECONDS, WRAPPER_TIMEOUT_SECONDS)
        )
    if tool_name != "Bash":
        return None
    # 延遲匯入：匯入失敗也走呼叫端的 fail-open，不讓封堵端故障擋掉環境檢查
    from lib.test_command_parse import find_unwrapped_heavy_with_redirects
    unwrapped = find_unwrapped_heavy_with_redirects(tool_input.get("command", ""))
    if not unwrapped:  # None（無法解析）與 []（無 heavy）皆放行
        return None
    suggestions = "\n".join("  " + _wrapped_form(st, rd) for st, rd in unwrapped)
    return (
        "偵測到未經 run-with-timeout 包裝的 heavy 命令（全套件測試或編譯），"
        "會繞過本機名額閘門。請把該命令原樣包進 "
        "python3 {w} <秒> -- <原命令>，可直接複製（{s} 秒為預設逾時，可依需要調整）：\n{sg}\n"
        "只替換該敘述本身，cd、管線與其他敘述保持在包裝之外。"
        "指定具體測試檔的執行不需排隊、不需包裝。".format(
            w=WRAPPER_PATH, s=WRAPPER_TIMEOUT_SECONDS, sg=suggestions)
    )


def _note_variable_target_passthrough(tool_input: dict, logger) -> None:
    """測試目標含未展開 shell 變數而被 fail-open 放行時，stderr 與日誌各記一行。"""
    try:
        from lib.test_command_parse import find_variable_target_statements
        found = find_variable_target_statements(tool_input.get("command", ""))
    except Exception as exc:  # 記錄用途失敗不影響放行
        logger.error("變數目標偵測失敗: %s", exc)
        return
    if found:
        msg = "測試目標含未展開 shell 變數，無法判定是否為單一測試檔，fail-open 放行: {}".format(
            " ".join(found[0]))
        sys.stderr.write("pre-test-hook {}\n".format(msg))
        logger.info(msg)


def check_flutter_sdk() -> tuple[bool, str]:
    """檢查 Flutter SDK 可用性。"""
    try:
        result = subprocess.run(
            ["flutter", "--version", "--machine"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            return True, ValidationMessages.PRE_TEST_SDK_OK
        return False, ValidationMessages.PRE_TEST_SDK_ERROR
    except FileNotFoundError:
        return False, ValidationMessages.PRE_TEST_SDK_NOT_FOUND
    except subprocess.TimeoutExpired:
        return False, ValidationMessages.PRE_TEST_SDK_TIMEOUT


# git checkout 等操作會在同一次寫入批次中依序落盤 pubspec.yaml 與
# pubspec.lock，兩者 mtime 因此可能存在毫秒級的寫入順序差（實測本專案
# 為 0.34 毫秒），此差距與依賴是否過期無關。使用者實際編輯 pubspec.yaml
# 後才執行 flutter pub get 更新 lock，兩檔 mtime 差距通常以秒計；1 秒
# 容差足以濾除檔案系統寫入順序雜訊，同時不影響真正過期案例的偵測。
PUBSPEC_MTIME_TOLERANCE_SECONDS = 1.0


def check_dependencies(project_dir: Path) -> list[str]:
    """檢查依賴是否已安裝。"""
    warnings = []

    pubspec_lock = project_dir / "pubspec.lock"
    if not pubspec_lock.exists():
        warnings.append(ValidationMessages.PRE_TEST_PUBSPEC_LOCK_MISSING)
        return warnings

    package_config = project_dir / ".dart_tool" / "package_config.json"
    if not package_config.exists():
        warnings.append(ValidationMessages.PRE_TEST_PACKAGE_CONFIG_MISSING)
        return warnings

    # 檢查 pubspec.yaml 是否比 pubspec.lock 更新（容差外才視為過期）
    pubspec_yaml = project_dir / "pubspec.yaml"
    if pubspec_yaml.exists() and pubspec_lock.exists():
        yaml_mtime = pubspec_yaml.stat().st_mtime
        lock_mtime = pubspec_lock.stat().st_mtime
        if yaml_mtime - lock_mtime > PUBSPEC_MTIME_TOLERANCE_SECONDS:
            warnings.append(ValidationMessages.PRE_TEST_PUBSPEC_OUTDATED)

    return warnings


def main():
    logger = setup_hook_logging("pre-test-hook")
    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    try:
        block_reason = build_block_reason(tool_name, tool_input)
    except Exception as exc:  # 判定失敗 fail-open：封堵端誤判代價高於漏擋
        sys.stderr.write("pre-test-hook 封堵判定失敗，fail-open 放行: {}\n".format(exc))
        logger.error("封堵判定失敗，fail-open: %s", exc)
        block_reason = None
    if block_reason is None and tool_name == "Bash":
        _note_variable_target_passthrough(tool_input, logger)
    if block_reason:
        try:
            logger.warning("deny: %s", block_reason.splitlines()[0])
            emit_hook_output(
                "PreToolUse",
                permission_decision="deny",
                permission_decision_reason=block_reason,
            )
            return 0
        except Exception as exc:  # deny 組裝失敗同樣 fail-open
            sys.stderr.write("pre-test-hook deny 輸出失敗，fail-open 放行: {}\n".format(exc))

    if not is_test_command(tool_name, tool_input):
        return 0

    project_dir = get_project_root()
    issues = []

    # 1. 檢查 Flutter SDK
    sdk_ok, sdk_msg = check_flutter_sdk()
    if not sdk_ok:
        issues.append(f"[ERROR] {sdk_msg}")

    # 2. 檢查依賴
    dep_warnings = check_dependencies(project_dir)
    for warning in dep_warnings:
        issues.append(f"[WARNING] {warning}")

    # 輸出結果：emit_hook_output 統一出口（合併警告和 permissionDecision）
    decision_reason = (
        f"{ValidationMessages.PRE_TEST_ENV_CHECK_PREFIX}{len(issues)}{ValidationMessages.PRE_TEST_ENV_CHECK_SUFFIX}"
        if issues else ValidationMessages.PRE_TEST_ENV_READY
    )
    additional_context = None
    if issues:
        warning_text = "\n".join(issues)
        additional_context = f"{ValidationMessages.PRE_TEST_CHECK_HEADER}\n{warning_text}"

    # 環境警告為 PM-only（subagent 觸發時過濾訊息，allow 決策不受影響）
    emit_hook_output(
        "PreToolUse",
        additional_context=additional_context,
        permission_decision="allow",
        permission_decision_reason=decision_reason,
        audience="pm_only",
        input_data=input_data,
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "pre-test-hook"))
