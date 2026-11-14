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
  4. pubspec.yaml 比 pubspec.lock 新（超過 1 秒容差）時提示依賴過期；但 lock 未改動、
     且 yaml 的依賴區段（environment、dependencies、dev_dependencies、
     dependency_overrides）與 lock 最後一次提交時的 yaml 相同時不提示（只改 version
     等欄位不需 pub get）。非 git、lock 未追蹤或被忽略、lock 已改動、YAML 解析失敗時照常提示。

封堵（deny）:
  名額閘門只對經 run-with-timeout.py 的命令生效，本 hook 封住繞過它的兩條路徑:
  1. Bash 直接執行 heavy 命令（未指定具體測試檔的 flutter／dart／pytest 測試、
     npm test、integration_test、flutter build／drive、xcodebuild）而未經
     run-with-timeout.py 包裝 -> deny，訊息附可直接複製的包裝寫法。
  2. mcp__dart__run_tests 未限定範圍（會跑全套件）-> deny，指向 Bash 包裝寫法。限定範圍指：
     有 roots 時每個 root 都是物件且帶非空 paths；無 roots 時頂層 paths 非空。
     （同一 matcher 原另掛 mcp-run-tests-validator，已併入本 hook，判定取兩者 deny 的聯集。）
  3. 自行取得名額的命令（worktree merge）經 run-with-timeout.py 包裝 -> deny，訊息附
     不包裝的寫法。外層計時器從啟動即開始，會把閘門內部排隊算進逾時；merge 內部的套件
     逾時從取得名額後起算，另有排隊上限，外層包裝沒有防護價值。
  light 命令（指定具體測試檔）不經包裝亦放行。
  判定失敗（命令無法解析、判定拋例外）一律 fail-open 放行並寫 stderr：
  封堵端誤判會擋掉正當命令，代價高於漏擋。
  liveness：deny 時 hook 日誌（.claude/hook-logs/pre-test-hook/）記一行 warning；
  實地確認以「裸 heavy 命令被 deny、包裝後同一命令放行」成對觸發。

間接形態的提醒（不阻擋）:
  命令文字含 runner 字樣（pytest、flutter／dart test、npm test），但辨識不出任何
  測試呼叫時（shell 函式參數 `run uv run pytest`、變數展開 `$CMD`、`bash -c '...'`），
  以 additionalContext 提醒模型改為直接下命令並經 run-with-timeout 包裝。
  不阻擋：`grep pytest <檔>` 這類唯讀命令同樣含 runner 字樣。不用 stderr：
  PreToolUse 的 exit 0 加 stderr 對模型不可見。日誌記一行 info。

不涵蓋（已知破口，不在封堵範圍）:
  - bash -c '...'／sh -c／python -c、shell 函式參數、變數展開：辨識不出測試呼叫，
    不封堵；命令文字含 runner 字樣時只提醒（見上段）
  - 經 shell 腳本間接執行（腳本檔內含 flutter test）：命令在腳本檔內，連提醒也無法觸發
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
    """mcp__dart__run_tests 是否限定了測試範圍。

    有 roots 時每個 root 都須是帶非空 paths 的物件：缺 paths 的 root 會跑該 root 的全套件，
    頂層 paths 不視為涵蓋它。無 roots 時以頂層 paths 非空為準。
    """
    roots = tool_input.get("roots") or []
    if not isinstance(roots, list):
        return False
    if roots:
        return all(isinstance(r, dict) and r.get("paths") for r in roots)
    return bool(tool_input.get("paths"))


def _flutter_test_rewrite(project_dir: str) -> str:
    """deny 訊息中的 flutter test 寫法；判定失敗時退回不帶前綴的寫法。

    只影響訊息內容：判定失敗不可讓 build_block_reason 拋出，否則呼叫端 fail-open
    會把原本恆為 deny 的 mcp 全套件呼叫翻成放行。
    """
    try:
        from lib.flutter_launcher import launch_argv
        return " ".join(launch_argv(["flutter", "test"], project_dir))
    except Exception as exc:  # 訊息組裝失敗：記錄並退回預設寫法，deny 照舊
        sys.stderr.write("pre-test-hook FVM 判定失敗，改寫退回 flutter test: {}\n".format(exc))
        import logging
        logging.getLogger("pre-test-hook").error("FVM 判定失敗，改寫退回 flutter test: %s", exc)
        return "flutter test"


def build_block_reason(tool_name: str, tool_input: dict, project_dir: str = "."):
    """回傳封堵理由；放行回 None。判定失敗由呼叫端 fail-open。

    project_dir 決定改寫中的 flutter 命令是否帶 fvm 前綴（專案使用 FVM 時才帶）。
    """
    if tool_name == "mcp__dart__run_tests":
        if _mcp_has_paths(tool_input):
            return None
        flutter_test = _flutter_test_rewrite(project_dir)
        return (
            "mcp__dart__run_tests 未帶 paths，或有 root 未帶 paths，會跑全套件，繞過本機名額閘門。"
            "請改用 Bash 經包裝執行：python3 {} {} -- {}"
            "（{} 為逾時秒數，可依套件大小調整）；"
            "或在每個 root 的 paths 指定具體測試檔（指定具體測試檔的執行不需排隊）。".format(
                WRAPPER_PATH, WRAPPER_TIMEOUT_SECONDS, flutter_test, WRAPPER_TIMEOUT_SECONDS)
        )
    if tool_name != "Bash":
        return None
    # 延遲匯入：匯入失敗也走呼叫端的 fail-open，不讓封堵端故障擋掉環境檢查
    from lib.test_command_parse import find_unwrapped_heavy_with_redirects, find_wrapped_self_slotted
    command = tool_input.get("command", "")
    wrapped_self_slotted = find_wrapped_self_slotted(command)
    if wrapped_self_slotted:  # None（無法解析）與 []（無命中）皆往下走既有判定
        suggestions = "\n".join(
            "  " + ("{} {}".format(shlex.join(st), rd) if rd else shlex.join(st))
            for st, rd in wrapped_self_slotted)
        return (
            "偵測到以 run-with-timeout 包裝的 worktree merge。merge 會自行排隊取得名額，"
            "外層計時器從啟動就開始計，閘門內的排隊時間會被算進逾時，排得久就會被外層中止；"
            "merge 內部每個套件的逾時從取得名額後才起算，另有排隊上限，外層包裝沒有防護價值。"
            "請去掉包裝直接執行（長時間等待改用背景執行並把輸出寫檔）：\n{}".format(suggestions)
        )
    unwrapped = find_unwrapped_heavy_with_redirects(command)
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


def build_indirect_runner_hint(tool_input: dict, logger):
    """命令含 runner 字樣卻辨識不出測試呼叫時，回傳給模型的提醒文字；否則 None。

    判定失敗不影響放行：記錄後回 None。
    """
    try:
        from lib.test_command_parse import find_unrecognized_runner_mention
        mention = find_unrecognized_runner_mention(tool_input.get("command", ""))
    except Exception as exc:  # 提醒用途，失敗只記錄
        logger.error("間接 runner 偵測失敗: %s", exc)
        return None
    if mention is None:
        return None
    logger.info("命令含 runner 字樣 %r 但辨識不出測試呼叫，已提醒", mention)
    return (
        "[pre-test-hook] 命令中出現測試 runner 字樣「{m}」，但辨識不出測試呼叫"
        "（可能經 shell 函式參數、變數展開或 bash -c 間接執行）。本機名額閘門"
        "只認得直接下的命令：若這是全套件測試或編譯，請改為直接下命令並包進 "
        "python3 {w} <秒> -- <原命令>，否則會繞過名額閘門；指定具體測試檔、"
        "或只是唯讀命令（如 grep {m} 檔案）則可忽略本提醒。".format(m=mention, w=WRAPPER_PATH)
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


# 影響依賴解析的 pubspec.yaml 區段；name、version、description 等不影響
# pubspec.lock，只改這些欄位不需要 flutter pub get。
DEPENDENCY_SECTIONS = ("environment", "dependencies", "dev_dependencies", "dependency_overrides")


def _dependency_sections(text: str) -> dict:
    import yaml
    data = yaml.safe_load(text) or {}
    return {key: data.get(key) for key in DEPENDENCY_SECTIONS}


def _git_stdout(project_dir: Path, *args: str):
    result = subprocess.run(
        ["git", "-C", str(project_dir), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
    )
    return result.stdout if result.returncode == 0 else None


def dependency_sections_match_lock_commit(project_dir: Path, logger=None) -> bool:
    """pubspec.lock 未改動，且 yaml 依賴區段與 lock 最後一次提交時的 yaml 相同時回傳 True。

    基準取 lock 最後一次改動的 commit 裡的 yaml，而非 HEAD：只提交 yaml 依賴
    變更而沒跑 pub get 時，HEAD 的 yaml 已與 lock 脫節。lock 沒動、依賴區段也與
    該 commit 相同，代表 yaml 只改了 version 等不影響解析的欄位。無法判定（非 git、
    lock 未追蹤或被 .gitignore 忽略、lock 已改動、yaml 未追蹤、YAML 解析失敗）
    一律回 False，交回 mtime 判定照常提示。
    """
    try:
        lock_status = _git_stdout(project_dir, "status", "--porcelain", "--", "pubspec.lock")
        if lock_status is None or lock_status.strip():
            return False
        lock_commit = (_git_stdout(project_dir, "log", "-1", "--format=%H", "--", "pubspec.lock") or "").strip()
        if not lock_commit:
            return False
        base_yaml = _git_stdout(project_dir, "show", "{}:./pubspec.yaml".format(lock_commit))
        if base_yaml is None:
            return False
        current_yaml = (project_dir / "pubspec.yaml").read_text(encoding="utf-8")
        return _dependency_sections(current_yaml) == _dependency_sections(base_yaml)
    except Exception as exc:  # 判定失敗回到 mtime 提示：多提示一次的代價低於漏提示
        if logger:
            logger.warning("依賴區段比對失敗，改用 mtime 判定: %s", exc)
        return False


def check_dependencies(project_dir: Path, logger=None) -> list[str]:
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
            if dependency_sections_match_lock_commit(project_dir, logger):
                if logger:
                    logger.info("pubspec.yaml 較新但依賴區段與 lock 最後提交時相同、lock 未改動，不提示依賴過期")
            else:
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
        block_reason = build_block_reason(
            tool_name, tool_input, input_data.get("cwd") or str(get_project_root()))
    except Exception as exc:  # 判定失敗 fail-open：封堵端誤判代價高於漏擋
        sys.stderr.write("pre-test-hook 封堵判定失敗，fail-open 放行: {}\n".format(exc))
        logger.error("封堵判定失敗，fail-open: %s", exc)
        block_reason = None
    if block_reason is None and tool_name == "Bash":
        _note_variable_target_passthrough(tool_input, logger)
        hint = build_indirect_runner_hint(tool_input, logger)
        if hint:
            emit_hook_output("PreToolUse", additional_context=hint, input_data=input_data)
            return 0
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
    dep_warnings = check_dependencies(project_dir, logger)
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
