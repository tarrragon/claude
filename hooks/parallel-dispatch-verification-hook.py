#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
並行派發驗證 Hook

功能：監聽 ticket track complete 命令，驗證代理人回報的完成情況
是否與實際修改的檔案一致。

觸發：PostToolUse (Bash) — 當 ticket track complete 成功執行後

輸出：
- 正常通過：靜默（DEFAULT_OUTPUT）
- 偵測缺失：警告訊息到 additionalContext
- 異常：錯誤日誌到 stderr + 日誌檔（雙通道）

行為：永遠返回 exit 0（不阻擋工作流）
"""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from hook_utils.hook_base import get_project_root
from hook_utils.hook_logging import setup_hook_logging
from hook_utils.hook_io import read_json_from_stdin
from hook_utils.hook_ticket import parse_ticket_frontmatter, find_ticket_file


# ============================================================================
# 常數定義
# ============================================================================

HOOK_NAME = "parallel-dispatch-verification-hook"

# 預設輸出格式（靜默通過）
DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}

# 訊息常數
MSG_WARNING_HEADER = "============================================================"
MSG_WARNING_TITLE = "[並行派發驗證警告]"
MSG_MISSING_FILES_TITLE = "缺失檔案"
MSG_EXPECTED_TITLE = "預期修改"
MSG_ACTUAL_TITLE = "實際變更"
MSG_ADVICE_TITLE = "建議動作"

# Git 命令超時設定（秒）
GIT_DIFF_TIMEOUT = 10

# 成功標記清單（用於識別 ticket complete 成功）
TICKET_COMPLETE_SUCCESS_MARKERS = ["已完成", "成功"]


# ============================================================================
# 核心邏輯函式
# ============================================================================


def normalize_path(path: str) -> str:
    """標準化路徑格式，用於跨來源比對

    規則：
    1. 統一使用正斜線 "/"
    2. 簡化多重斜線 "//"
    3. 移除前綴 "./"
    4. 移除尾斜線 "/"
    5. 轉為小寫

    Args:
        path: 原始路徑字串

    Returns:
        str: 標準化後的路徑
    """
    if not path:
        return ""

    # 轉換反斜線為正斜線（Windows 相容）
    path = path.replace("\\", "/")

    # 簡化多重斜線（必須在移除前綴前進行）
    while "//" in path:
        path = path.replace("//", "/")

    # 移除前綴 "./"
    while path.startswith("./"):
        path = path[2:]

    # 移除尾斜線
    path = path.rstrip("/")

    # 轉為小寫
    path = path.lower()

    return path


def find_missing_files(where_files: list[str], git_changed: list[str]) -> list[str]:
    """比對預期與實際，找出缺失的檔案

    使用集合差運算：missing = where_files - git_changed
    不計算 extra_files（git_changed 中多出的）

    Args:
        where_files: Ticket where.files 清單（已規範化）
        git_changed: git diff 結果（已規範化）

    Returns:
        list[str]: 出現在 where_files 但不在 git_changed 的檔案
    """
    if not where_files:
        return []

    where_set = set(where_files)
    git_set = set(git_changed)

    # 處理目錄路徑前綴匹配
    missing = where_set - git_set

    # 移除被前綴匹配覆蓋的目錄路徑
    missing_filtered = set()
    for file in missing:
        # 若此檔案是目錄路徑（以 "/" 結尾）
        if file.endswith("/"):
            # 檢查是否有其他 git_changed 檔案以此開頭
            if any(g.startswith(file) for g in git_set):
                continue  # 被前綴匹配覆蓋，跳過

        missing_filtered.add(file)

    return sorted(missing_filtered)


def extract_ticket_id(input_data: dict) -> Optional[str]:
    """從命令或輸出中提取 Ticket ID

    支援格式：
    - 從命令：ticket track complete 0.1.0-W41-002
    - 從輸出：[OK] 已完成 Ticket 0.1.0-W41-002

    Args:
        input_data: PostToolUse Hook 的 stdin JSON

    Returns:
        str | None: Ticket ID 或 None（無法提取時）
    """
    # 優先從命令中提取
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # 正則提取 Ticket ID（格式：v.x.y-Wz-nnn）
    match = re.search(r"(\d+\.\d+\.\d+-W\d+-\d+)", command)
    if match:
        return match.group(1)

    # 備選：從輸出中提取
    tool_response = input_data.get("tool_response", {})
    stdout = tool_response.get("stdout", "")

    match = re.search(r"(\d+\.\d+\.\d+-W\d+-\d+)", stdout)
    if match:
        return match.group(1)

    return None


def is_ticket_complete_success(input_data: dict) -> bool:
    """判斷是否為 ticket track complete 成功執行

    Args:
        input_data: PostToolUse Hook 的 stdin JSON

    Returns:
        bool: 是否符合觸發條件
    """
    # 驗證工具類型
    tool_name = input_data.get("tool_name")
    if tool_name != "Bash":
        return False

    # 提取命令
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if "ticket track complete" not in command:
        return False

    # 檢查執行結果
    tool_response = input_data.get("tool_response", {})
    exit_code = tool_response.get("exit_code", -1)
    if exit_code != 0:
        return False

    # 檢查成功標記
    stdout = tool_response.get("stdout", "")
    for marker in TICKET_COMPLETE_SUCCESS_MARKERS:
        if marker in stdout:
            return True

    return False


def read_ticket_where_files(ticket_id: str, project_root: Path,
                            logger: logging.Logger) -> list[str]:
    """讀取 Ticket 的 where.files 清單

    Args:
        ticket_id: Ticket ID（如 "0.1.0-W41-002"）
        project_root: 專案根目錄
        logger: Logger 實例

    Returns:
        list[str]: 規範化後的路徑清單（空列表若讀取失敗）
    """
    try:
        # 使用 find_ticket_file 定位 Ticket 檔案
        ticket_file = find_ticket_file(ticket_id, project_root, logger)
        if not ticket_file or not ticket_file.exists():
            logger.warning(f"Ticket 檔案不存在: {ticket_id}")
            return []

        # 解析 Ticket frontmatter
        frontmatter = parse_ticket_frontmatter(ticket_file, logger)
        if not frontmatter:
            logger.debug(f"無法解析 Ticket frontmatter: {ticket_id}")
            return []

        # 提取 where.files
        where_dict = frontmatter.get("where", {})
        if not isinstance(where_dict, dict):
            return []

        where_files_raw = where_dict.get("files", [])
        if not where_files_raw:
            logger.debug(f"Ticket 無 where.files: {ticket_id}")
            return []

        # 規範化每個路徑
        where_files_normalized = []
        for file_path in where_files_raw:
            normalized = normalize_path(str(file_path))
            if normalized:
                where_files_normalized.append(normalized)

        logger.debug(f"讀取 where.files: {len(where_files_normalized)} 個")
        return where_files_normalized

    except Exception as e:
        logger.error(f"讀取 Ticket where.files 失敗: {e}")
        sys.stderr.write(f"[Hook Error] 讀取 Ticket 失敗: {e}\n")
        return []


def get_git_changed_files(project_root: Path, logger: logging.Logger) -> list[str]:
    """執行 git diff HEAD --name-only 取得實際變更檔案

    Args:
        project_root: 專案根目錄（執行 git 命令的工作目錄）
        logger: Logger 實例

    Returns:
        list[str]: 規範化後的變更檔案清單（空列表若執行失敗）
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--name-only"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=GIT_DIFF_TIMEOUT
        )

        if result.returncode != 0:
            logger.warning(f"git diff 失敗 (exit code {result.returncode})")
            sys.stderr.write(f"[Hook Error] git diff 命令失敗\n")
            return []

        if not result.stdout.strip():
            return []

        # 解析輸出並規範化
        git_changed = []
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line:
                normalized = normalize_path(line)
                if normalized:
                    git_changed.append(normalized)

        logger.debug(f"git diff 返回: {len(git_changed)} 個檔案")
        return git_changed

    except subprocess.TimeoutExpired:
        logger.error(f"git diff 超時 ({GIT_DIFF_TIMEOUT}s)")
        sys.stderr.write(f"[Hook Error] git diff 命令超時\n")
        return []

    except FileNotFoundError:
        logger.error("git 命令未找到")
        sys.stderr.write(f"[Hook Error] git 命令未找到\n")
        return []

    except Exception as e:
        logger.error(f"執行 git diff 失敗: {e}")
        sys.stderr.write(f"[Hook Error] git 命令執行失敗: {e}\n")
        return []


def format_warning_message(
    ticket_id: str,
    missing_files: list[str],
    where_files: list[str],
    git_changed_relevant: list[str]
) -> str:
    """生成警告訊息文字

    Args:
        ticket_id: Ticket ID
        missing_files: 缺失的檔案清單
        where_files: 完整的 where.files 清單
        git_changed_relevant: git diff 中與 where.files 相關的檔案

    Returns:
        str: 格式化的警告訊息
    """
    lines = []

    lines.append(MSG_WARNING_HEADER)
    lines.append(MSG_WARNING_TITLE)
    lines.append(MSG_WARNING_HEADER)
    lines.append("")

    lines.append(f"Ticket {ticket_id} 完成後，偵測到以下預期修改的檔案")
    lines.append("未出現在 git diff 中：")
    lines.append("")

    # 列出缺失檔案
    lines.append(f"{MSG_MISSING_FILES_TITLE}（{len(missing_files)} 個）：")
    for file in sorted(missing_files):
        lines.append(f"  - {file}")
    lines.append("")

    # 列出預期修改清單
    lines.append(f"{MSG_EXPECTED_TITLE}（where.files 清單，共 {len(where_files)} 個）：")
    for file in sorted(where_files):
        lines.append(f"  - {file}")
    lines.append("")

    # 列出實際變更清單
    lines.append(f"{MSG_ACTUAL_TITLE}（git diff HEAD --name-only，共 {len(git_changed_relevant)} 個相關檔案）：")
    for file in sorted(git_changed_relevant):
        lines.append(f"  - {file}")
    lines.append("")

    # 添加建議
    lines.append(f"{MSG_ADVICE_TITLE}：")
    lines.append("1. 確認代理人是否確實完成了這些檔案的修改")
    lines.append("2. 若代理人遺漏了修改，手動補完或重新派發")
    lines.append("3. 補完後執行 git diff 確認")
    lines.append("")

    lines.append("注意：此驗證使用 git diff HEAD，包含所有未提交的變更。")
    lines.append("若有其他任務的未提交變更，可能影響比對結果。")
    lines.append("")

    lines.append(MSG_WARNING_HEADER)

    return "\n".join(lines)


def save_analysis_log(
    logger: logging.Logger,
    ticket_id: str,
    where_files: list[str],
    git_changed: list[str],
    missing_files: list[str],
    result: str
) -> None:
    """記錄執行摘要到日誌檔

    Args:
        logger: Logger 實例
        ticket_id: Ticket ID
        where_files: where.files 清單
        git_changed: git_changed 清單
        missing_files: 缺失檔案清單
        result: 結果（PASS/WARN/SKIP/ERROR）
    """
    logger.info(f"Verification result: {result}")
    logger.debug(f"TicketID: {ticket_id}")
    logger.debug(f"WhereFiles: {len(where_files)} 個")
    logger.debug(f"GitChanged: {len(git_changed)} 個")
    logger.debug(f"MissingFiles: {len(missing_files)} 個")

    if missing_files:
        for file in sorted(missing_files):
            logger.debug(f"  Missing: {file}")


# ============================================================================
# Hook 主邏輯
# ============================================================================


def main() -> int:
    """Hook 主入口點

    流程：
    1. 初始化日誌
    2. 讀取 stdin JSON
    3. 驗證觸發條件（ticket track complete 成功）
    4. 提取 Ticket ID
    5. 讀取 Ticket 的 where.files
    6. 執行 git diff 取得實際變更
    7. 比對並識別 missing_files
    8. 若有缺失，輸出警告訊息
    9. 記錄日誌

    Returns:
        int: 永遠為 0（不阻擋）
    """
    logger = setup_hook_logging(HOOK_NAME)
    logger.debug("Hook 啟動")

    try:
        # 讀取 stdin JSON
        input_data = read_json_from_stdin(logger)
        if not input_data:
            logger.debug("無 stdin JSON 輸入，靜默結束")
            print(json.dumps(DEFAULT_OUTPUT))
            return 0

        # 驗證觸發條件
        if not is_ticket_complete_success(input_data):
            logger.debug("非 ticket track complete 成功，靜默結束")
            print(json.dumps(DEFAULT_OUTPUT))
            return 0

        # 提取 Ticket ID
        ticket_id = extract_ticket_id(input_data)
        if not ticket_id:
            logger.warning("無法提取 Ticket ID")
            print(json.dumps(DEFAULT_OUTPUT))
            return 0

        logger.info(f"Ticket: {ticket_id}")

        # 獲取專案根目錄
        project_root = get_project_root()

        # 讀取 Ticket 的 where.files
        where_files = read_ticket_where_files(ticket_id, project_root, logger)
        if not where_files:
            logger.debug("Ticket 無 where.files，靜默結束")
            print(json.dumps(DEFAULT_OUTPUT))
            return 0

        # 執行 git diff
        git_changed = get_git_changed_files(project_root, logger)

        # 比對
        missing_files = find_missing_files(where_files, git_changed)

        # 記錄日誌
        save_analysis_log(logger, ticket_id, where_files, git_changed,
                          missing_files, "WARN" if missing_files else "PASS")

        # 輸出結果
        if missing_files:
            # 生成警告訊息
            warning_msg = format_warning_message(
                ticket_id, missing_files, where_files, git_changed
            )

            logger.warning(f"偵測到 {len(missing_files)} 個缺失檔案")
            logger.warning(warning_msg)

            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": warning_msg
                }
            }
        else:
            # 靜默通過
            logger.info("所有檔案都在 git diff 中，通過驗證")
            output = DEFAULT_OUTPUT

        print(json.dumps(output))
        return 0

    except Exception as e:
        logger.critical(f"未預期的異常: {e}", exc_info=True)
        sys.stderr.write(f"[Hook Error] {HOOK_NAME} 執行失敗\n")
        print(json.dumps(DEFAULT_OUTPUT))
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
