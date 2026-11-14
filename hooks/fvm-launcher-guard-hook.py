#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
FVM Launcher Guard Hook - PreToolUse:Bash

功能: 專案以 FVM 釘選 Flutter 版本時，擋下未經 fvm 的 flutter／dart 命令，
      訊息附 `fvm flutter …`／`fvm dart …` 的改寫。

Why: 有 FVM 設定檔（.fvmrc 或 .fvm/fvm_config.json）的專案，裸 flutter／dart
     會用 PATH 上的全域預設版，test、analyze 與 gen-l10n 的結果和生成檔落在與
     釘選版不同的 Flutter 上。
Consequence: 不擋時，生成檔與分析結果以錯誤版本產生且無任何訊號；擋下時，
     代理人依訊息改寫即可，訊息必附改寫。
Action: 改用 `fvm flutter …`／`fvm dart …`。

判準（lib.test_command_parse.find_unmanaged_flutter_statements）:
  - 只看命令位置：剝除啟動前綴（env、KEY=VAL、sudo、nohup、time、timeout、
    uv run、run-with-timeout.py）後開頭為 flutter／dart；剝除過程經過 fvm 即放行。
  - grep 引數、heredoc 內文、註解中的字樣不在命令位置，不擋。
  - 直接以釘選 SDK 路徑呼叫（專案內 .fvm/flutter_sdk、fvm versions 快取）視同釘選版，放行。
  - 是否使用 FVM 由 lib.flutter_launcher.uses_fvm 判定；起點為 payload 的 cwd，
    命令中 `cd <字面目錄>` 依序更新；cd 目標含變數時其後敘述不判定。

失敗語意: fail-open（放行）。觸發條件：stdin 無法解析、命令無法 tokenize（未閉合
  引號）、判定拋例外；例外時寫 stderr 與 error 日誌。
範疇邊界: `bash -c '…'`、腳本檔內呼叫、變數展開為命令不在命令文字的命令位置，
  本守衛看不到。
"""

import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, emit_hook_output, get_project_root

HOOK_NAME = "fvm-launcher-guard"
_KEYWORDS = ("flutter", "dart")


def build_deny_reason(statements) -> str:
    rewrites = "\n".join("  fvm " + shlex.join(_without_launcher(st)) for st in statements)
    return (
        "本專案以 FVM 釘選 Flutter 版本（有 .fvmrc 或 .fvm/fvm_config.json），"
        "未經 fvm 的 flutter／dart 會用 PATH 上的全域預設版，測試、分析與生成檔會落在錯誤版本。"
        "請改經 fvm 執行：\n{}\n"
        "（若外層有 run-with-timeout.py 等包裝，只把 flutter／dart 那一段改成 fvm 開頭，包裝保留。）"
        .format(rewrites)
    )


def _without_launcher(statement):
    """改寫只示範 flutter／dart 那一段，前綴（包裝、env）由訊息說明保留。"""
    from lib.test_command_parse import strip_prefixes_noting_fvm
    stripped, _ = strip_prefixes_noting_fvm(list(statement))
    return stripped or list(statement)


def find_violations(command: str, start_dir: str):
    from lib.flutter_launcher import uses_fvm
    from lib.test_command_parse import find_unmanaged_flutter_statements
    return find_unmanaged_flutter_statements(command, start_dir, uses_fvm)


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    if not input_data or input_data.get("tool_name") != "Bash":
        return 0
    command = (input_data.get("tool_input") or {}).get("command", "") or ""
    if not any(k in command for k in _KEYWORDS):
        return 0
    start_dir = input_data.get("cwd") or str(get_project_root())
    try:
        violations = find_violations(command, start_dir)
    except Exception as exc:  # 判定失敗 fail-open：誤擋正當命令的代價高於漏擋一次
        sys.stderr.write("fvm-launcher-guard 判定失敗，fail-open 放行: {}\n".format(exc))
        logger.error("判定失敗，fail-open: %s", exc)
        return 0
    if violations is None:
        logger.info("命令無法解析，放行")
        return 0
    if not violations:
        return 0
    reason = build_deny_reason(violations)
    logger.warning("deny: 未經 fvm 的 %s（cwd=%s）",
                   " / ".join(shlex.join(st) for st in violations)[:300], start_dir)
    emit_hook_output("PreToolUse", permission_decision="deny", permission_decision_reason=reason)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
