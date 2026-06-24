#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
SKILL CLI 錯誤自動偵測與引導不足回饋機制 - PostToolUse Hook

功能: 當 Bash 工具執行 ticket/skill CLI 命令失敗時，自動偵測錯誤類型
     （參數不存在、格式錯誤、未知子命令）並提示 SKILL 引導可能不足。

觸發時機: Bash 工具執行後，命令包含 ticket 或 skill CLI
檢測邏輯:
  1. 驗證 tool_name == "Bash"
  2. 檢查命令是否為 ticket/skill 相關命令
  3. 檢查是否有非零退出碼（錯誤發生）
  4. 分析 stderr/stdout 中的錯誤類型：
     - "unrecognized arguments" → 參數不存在
     - "error: argument" → 參數格式錯誤
     - "invalid choice" → 未知子命令
  5. 排除業務邏輯錯誤（如 Ticket 不存在、無法認領等）
  6. 若為 SKILL 引導缺陷，輸出回饋訊息

行為: 不阻擋（exit 0），僅在 additionalContext 輸出回饋訊息

設計原則:
- 關注於「SKILL 引導不足」的信號，而非一般 CLI 失敗
- 幫助改進 SKILL 文檔的完整性
- 記錄所有 SKILL CLI 錯誤，便於後續分析和改善

Envelope 偵測模式 (W17-008.5.5):
- 偵測 stdout/stderr 是否含 ErrorEnvelope 版本標記 `__error_envelope_v1__`
- 命中表示 CLI 已輸出完整結構化錯誤訊息（format_error 雙路徑），hook 不需重複補充引導
- Marker 來源: .claude/skills/ticket/ticket_system/lib/messages.py:ERROR_ENVELOPE_VERSION_MARKER
- 升級至 v2 時兩處須同改

HOOK_METADATA (JSON):
{
  "event_type": "PostToolUse",
  "matcher": "Bash",
  "timeout": 5000,
  "description": "SKILL CLI 錯誤自動偵測與引導不足回饋",
  "dependencies": [],
  "version": "1.0.0"
}
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

_FRAMEWORK_HOOKS = str(Path(__file__).resolve().parents[3] / "hooks")
sys.path.insert(0, _FRAMEWORK_HOOKS)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # .claude/ — for `from lib import ...`

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, emit_hook_output  # noqa: E402

# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

# 需要偵測的 CLI 命令前綴
SKILL_CLI_COMMANDS = [
    "ticket",
    "skill",
    "/ticket",
    "/skill",
]

# SKILL 引導缺陷的錯誤模式
# 格式: (pattern, error_type)
SKILL_ERROR_PATTERNS = [
    # 參數不存在
    (r"unrecognized arguments?:", "參數不存在"),
    (r"unrecognized sub-command", "參數不存在"),
    (r"argument .+ not recognized", "參數不存在"),

    # 參數格式錯誤
    (r"error: argument .+: ", "參數格式錯誤"),
    (r"invalid argument", "參數格式錯誤"),
    (r"argument .+ expected", "參數格式錯誤"),

    # 未知子命令
    (r"invalid choice: '([^']+)'", "未知子命令"),
    (r"unknown command '([^']+)'", "未知子命令"),
    (r"no such command", "未知子命令"),
]

# ErrorEnvelope 版本標記
# 與 .claude/skills/ticket/ticket_system/lib/messages.py:ERROR_ENVELOPE_VERSION_MARKER 同步
# 升級至 v2 時兩處須同改
ENVELOPE_VERSION_MARKER = "__error_envelope_v1__"

# 系統功能缺失分類訊號（W3-073）
# 結構：set-<dict-field> 子命令 + 子欄位 flag 不被接受 → 暗示 CLI 缺子欄位寫入路徑
# 參考案例：W3-072 暴露的 ticket track set-where --layer 缺口
# 對應 ticket frontmatter dict 欄位 → 已知子欄位清單
DICT_FIELD_SUBFIELDS = {
    "set-where": ["layer", "files"],
    "set-who": ["current", "history"],
    "set-how": ["task_type", "strategy"],
}

# 分類結果常數
CLASSIFICATION_SYSTEM_GAP = "system_functional_gap"
CLASSIFICATION_SKILL_DOC = "skill_documentation_gap"
CLASSIFICATION_USER_TYPO = "user_typo"

# 排除的錯誤模式（業務邏輯錯誤，不是 SKILL 引導問題）
EXCLUDED_ERROR_PATTERNS = [
    r"ticket not found",
    r"no pending ticket",
    r"ticket already .+",
    r"cannot .+ completed ticket",
    r"not in progress",
    r"blocked ticket",
    r"insufficient permission",
    r"version mismatch",
    r"no such file or directory",
    r"permission denied",
    r"json decode error",
    r"invalid json",
]

# PostToolUse Hook 的標準輸出結構
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}

# 訊息範本（系統功能缺失，W3-073）
SYSTEM_GAP_FEEDBACK_TEMPLATE = """
============================================================
[系統功能缺失評估] CLI 子欄位寫入路徑可能缺失
============================================================

檢測到 `{subcommand}` 子命令拒絕了子欄位 flag `{flag}`，
但該 flag 在概念上對應 ticket frontmatter 中既有的子欄位。

失敗命令：{command_summary}
偵測訊號：{subcommand} 拒絕 --{flag}（已知子欄位之一：{known_subfields}）

可能原因：
  CLI 缺少對應子欄位的寫入路徑（非單純文檔缺失），使用者
  意圖背後反映系統功能缺口（如 set-where --layer 類缺口）。

建議動作：
  1. 不要僅補 SKILL.md，先評估是否為系統功能缺口
  2. 建立 ANA ticket 評估該子欄位寫入路徑的設計方案：
     ticket track create --type ANA \\
       --title "[ANA] 評估 {subcommand} 是否需支援 --{flag} 子欄位 flag" \\
       --source-ticket <當前 ticket>
  3. ANA 完成後決定 spawn IMP / 維持現狀 / 補 SKILL.md 三方案
  4. Fallback：直接 Edit ticket frontmatter 對應子欄位

詳見：.claude/skills/ticket/SKILL.md

============================================================
"""

# 訊息範本
SKILL_CLI_ERROR_FEEDBACK_TEMPLATE = """
============================================================
[SKILL 引導品質回饋] CLI 錯誤偵測
============================================================

檢測到 SKILL/Ticket CLI 命令使用了不存在或格式錯誤的參數。

錯誤類型：{error_type}
失敗命令：{command_summary}

可能原因：
  SKILL 引導不足，使用者嘗試了 SKILL.md 中未明確說明的用法

建議動作：
  1. 確認 SKILL.md 是否有此使用情境的說明
  2. 查閱完整語法：執行 `{command_base} --help`
  3. 若多人遇到同樣困惑，建立改善 Ticket
     `/ticket create --type ADJ --title "[ADJ] 補充 SKILL.md 文檔"`

詳見: .claude/skills/ticket/SKILL.md

============================================================
"""


# ============================================================================
# 輔助函式
# ============================================================================

def is_skill_cli_command(command: str) -> bool:
    """判斷命令是否為 ticket/skill CLI 命令（首 token 比對）

    處理 && 鏈式命令、管道命令、子 shell 等情況，避免子字串誤判
    （例如 echo "ticket" 或 grep ticket 不應被認為是 ticket CLI 命令）
    """
    # 將命令分段：處理 && 鏈式、管道、子 shell 等
    for segment in re.split(r'[|&;]+', command):
        segment = segment.strip().lstrip('(').strip()
        if not segment:
            continue
        # 取第一個 token（空格分隔）
        tokens = segment.split()
        if tokens:
            first_token = tokens[0]
            # 移除斜線前綴（/ticket → ticket）
            if first_token.startswith("/"):
                first_token = first_token[1:]
            if first_token in SKILL_CLI_COMMANDS:
                return True
    return False


def is_envelope_output(stderr: str, stdout: str) -> bool:
    """偵測輸出是否含 ErrorEnvelope 版本標記。

    與 messages.py:ERROR_ENVELOPE_VERSION_MARKER 同步。命中表示 CLI
    已輸出完整結構化錯誤，hook 不需重複補充引導。
    """
    return ENVELOPE_VERSION_MARKER in stderr or ENVELOPE_VERSION_MARKER in stdout


def is_excluded_error(stderr: str, stdout: str) -> bool:
    """判斷錯誤是否為排除類型（業務邏輯錯誤）"""
    combined = (stderr + " " + stdout).lower()
    for pattern in EXCLUDED_ERROR_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return True
    return False


def detect_skill_error_type(stderr: str, stdout: str) -> Optional[str]:
    """
    偵測 SKILL 引導缺陷錯誤類型

    Args:
        stderr: 標準錯誤輸出
        stdout: 標準輸出

    Returns:
        錯誤類型字串，若無匹配返回 None
    """
    combined = stderr + " " + stdout

    for pattern, error_type in SKILL_ERROR_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return error_type

    return None


def extract_command_summary(command: str, stderr: str) -> tuple[str, str]:
    """
    提取命令摘要和基本命令

    Args:
        command: 完整命令行
        stderr: 錯誤訊息

    Returns:
        (command_summary, command_base) 元組
    """
    # 簡化命令（最多 80 字符）
    command_summary = command[:80] if len(command) > 80 else command

    # 提取基本命令（第一個空格前）
    parts = command.strip().split()
    command_base = parts[0] if parts else command

    # 移除斜線前綴（/ticket → ticket）
    if command_base.startswith("/"):
        command_base = command_base[1:]

    return command_summary, command_base


def detect_system_gap(command: str, stderr: str, stdout: str) -> Optional[Dict[str, str]]:
    """偵測系統功能缺失訊號（W3-073）。

    判定條件（同時成立）：
    1. 命令包含 set-where / set-who / set-how 子命令之一
    2. stderr/stdout 含 "unrecognized arguments" 類錯誤
    3. 錯誤訊息或命令中出現對應 dict 欄位的已知子欄位 flag（如 --layer）

    Returns:
        {"subcommand": "set-where", "flag": "layer",
         "known_subfields": "layer, files"} 或 None
    """
    combined = (stderr + " " + stdout).lower()
    # 必要訊號：unrecognized arguments 類錯誤
    if not re.search(r"unrecognized arguments?:", combined, re.IGNORECASE):
        return None

    for subcommand, subfields in DICT_FIELD_SUBFIELDS.items():
        if subcommand not in command:
            continue
        # 找命令或錯誤訊息中的 --<subfield> flag
        for subfield in subfields:
            flag_pattern = rf"--{re.escape(subfield)}\b"
            if re.search(flag_pattern, command, re.IGNORECASE) or \
               re.search(flag_pattern, stderr + stdout, re.IGNORECASE):
                return {
                    "subcommand": subcommand,
                    "flag": subfield,
                    "known_subfields": ", ".join(subfields),
                }
    return None


def classify_error(command: str, stderr: str, stdout: str) -> str:
    """三類分類（W3-073）。

    - CLASSIFICATION_USER_TYPO: 業務邏輯錯誤（排除清單命中）
    - CLASSIFICATION_SYSTEM_GAP: dict 欄位子 flag 缺寫入路徑
    - CLASSIFICATION_SKILL_DOC: 其他 SKILL 引導缺陷（既有路徑）

    呼叫者應預先處理 envelope / 空輸出 / 非 SKILL CLI 等情境。
    """
    if is_excluded_error(stderr, stdout):
        return CLASSIFICATION_USER_TYPO
    if detect_system_gap(command, stderr, stdout) is not None:
        return CLASSIFICATION_SYSTEM_GAP
    return CLASSIFICATION_SKILL_DOC


def main() -> int:
    """
    主入口點

    流程:
    1. 讀取 stdin JSON（PostToolUse 格式）
    2. 驗證工具類型是否為 Bash
    3. 檢查命令是否為 ticket/skill CLI 命令
    4. 分析錯誤類型，排除業務邏輯錯誤
    5. 若為 SKILL 引導缺陷，輸出回饋訊息
    """
    logger = setup_hook_logging("skill-cli-error-feedback")

    try:
        input_data = read_json_from_stdin(logger)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析錯誤: %s", e)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    if not input_data:
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 驗證工具類型
    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 取得命令和回應
    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    # 檢查是否為 SKILL CLI 命令
    if not is_skill_cli_command(command):
        logger.debug("跳過: 非 ticket/skill CLI 命令")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 檢查是否有錯誤
    tool_response = input_data.get("tool_response") or {}

    # 支援 tool_response 為字串或字典
    if isinstance(tool_response, str):
        stderr = ""
        stdout = tool_response
    else:
        stderr = tool_response.get("stderr", "")
        stdout = tool_response.get("stdout", "")

    # 檢查退出碼：exit_code=0 表示命令成功，跳過
    if isinstance(tool_response, dict):
        exit_code = tool_response.get("exit_code")
        if exit_code is not None and exit_code == 0:
            logger.debug("命令成功（exit_code=0），跳過")
            print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
            return EXIT_SUCCESS

    # 若無錯誤信息，命令可能成功，跳過
    if not stderr and not stdout:
        logger.debug("無錯誤信息，跳過")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 排除業務邏輯錯誤（Ticket 不存在、無法認領等）
    if is_excluded_error(stderr, stdout):
        logger.debug("業務邏輯錯誤，跳過: %s", command[:80])
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 跳過 ErrorEnvelope 已輸出完整結構化訊息的情況（W17-008.5.5）
    if is_envelope_output(stderr, stdout):
        logger.debug("ErrorEnvelope 已輸出完整訊息，跳過補充: %s", command[:80])
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # W3-073: 系統功能缺失偵測（優先於 SKILL 文檔缺失分類）
    system_gap = detect_system_gap(command, stderr, stdout)
    if system_gap is not None:
        logger.info("偵測到系統功能缺失訊號: %s --%s",
                    system_gap["subcommand"], system_gap["flag"])
        command_summary, _ = extract_command_summary(command, stderr)
        feedback_message = SYSTEM_GAP_FEEDBACK_TEMPLATE.format(
            subcommand=system_gap["subcommand"],
            flag=system_gap["flag"],
            known_subfields=system_gap["known_subfields"],
            command_summary=command_summary,
        )
        # 系統功能缺失回饋為 PM-only：統一出口過濾 subagent 觸發（PC-V1-004 防護 C）
        emit_hook_output(
            "PostToolUse",
            additional_context=feedback_message,
            audience="pm_only",
            input_data=input_data,
        )
        return EXIT_SUCCESS

    # 偵測 SKILL 引導缺陷錯誤
    error_type = detect_skill_error_type(stderr, stdout)

    if not error_type:
        logger.debug("未偵測到 SKILL 引導缺陷錯誤")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    # 檢測到 SKILL 引導缺陷，輸出回饋訊息
    logger.info("偵測到 SKILL 引導缺陷錯誤: %s", error_type)
    logger.info("失敗命令: %s", command[:120])
    logger.info("stderr 摘要: %s", stderr[:200])

    command_summary, command_base = extract_command_summary(command, stderr)

    feedback_message = SKILL_CLI_ERROR_FEEDBACK_TEMPLATE.format(
        error_type=error_type,
        command_summary=command_summary,
        command_base=command_base,
    )

    # SKILL 引導缺陷回饋為 PM-only：統一出口過濾 subagent 觸發（PC-V1-004 防護 C）
    emit_hook_output(
        "PostToolUse",
        additional_context=feedback_message,
        audience="pm_only",
        input_data=input_data,
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "skill-cli-error-feedback")
    sys.exit(exit_code)
