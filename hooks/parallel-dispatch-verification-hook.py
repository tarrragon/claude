#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # .claude/ — for `from lib.* import ...`

from lib.hook_base import get_project_root  # noqa: E402
from lib.hook_logging import setup_hook_logging, run_hook_safely  # noqa: E402
from lib.hook_io import read_json_from_stdin, is_subagent_environment
from lib.ticket_command_parse import has_complete_command, complete_statement_args  # noqa: E402
from lib.git_command_parse import parse_command_statements  # noqa: E402
from lib.ticket_id_pattern import SEARCH_WITH_SUFFIX_RE  # noqa: E402
from lib.bash_tool_response import (  # noqa: E402
    FAILURE_EVENT_NAME, is_bash_success, is_failure_event, auto_commit_failure_as_success,
)
from lib.ticket_completed_verifier import (  # noqa: E402
    make_completed_verifier, is_complete_transition_success,
)
from lib.hook_ticket import (
    parse_ticket_frontmatter,
    find_ticket_file,
    extract_where_files,
)

# 讀寫意圖後綴（::read / ::write）解析共用 ticket_system 實作，與 track_commit 一致
# （比照 file-ownership-guard-hook.py 的落地方式）。
_TICKET_SYSTEM_SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "ticket"
if str(_TICKET_SYSTEM_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_TICKET_SYSTEM_SKILL_DIR))
from ticket_system.lib.file_conflict import parse_file_intent  # noqa: E402


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
# ticket CLI 寫入命令「動作已完成、僅 auto-commit 失敗」的專用退出碼（sysexits EX_TEMPFAIL）
EXIT_AUTO_COMMIT_FAILED = 75

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
    # 以 token 位置辨識完成類語句，只取其動詞後第一個完整符合票號形狀的 token
    # （含子任務多層後綴）；不從 stdout 或命令任意位置擷取
    command = input_data.get("tool_input", {}).get("command", "")
    statements = parse_command_statements(command)
    if not statements:
        return None
    for tokens in statements:
        args = complete_statement_args(tokens)
        if args is None:
            continue
        for token in args:
            m = SEARCH_WITH_SUFFIX_RE.fullmatch(token)
            if m:
                return m.group(1)
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

    # 以 token 位置辨識完成類命令（complete / finish / batch-complete）；
    # 解析失敗（None）視為非完成命令，維持提示類不觸發的失敗語意
    if has_complete_command(command) is not True:
        return False

    # 檢查執行結果
    # 真實 payload 無 exit_code，由共用 helper 判定（interrupted + 成功標記）
    # 分層判定：未遮蔽即成功；遮蔽時以票面 completed 狀態驗證；其餘退回標記
    return is_complete_transition_success(
        input_data.get("tool_response"),
        TICKET_COMPLETE_SUCCESS_MARKERS,
        command,
        make_completed_verifier(command),
    )


def read_ticket_where_files(ticket_id: str, project_root: Path,
                            logger: logging.Logger) -> list[str]:
    """讀取 Ticket 的 where.files 清單

    W11-004.7.2：raw 抽取統一委派 hook_utils.extract_where_files；
    本函式僅保留路徑規範化（normalize_path）與錯誤觀察（雙通道日誌）。

    Args:
        ticket_id: Ticket ID（如 "0.1.0-W41-002"）
        project_root: 專案根目錄
        logger: Logger 實例

    Returns:
        list[str]: 規範化後的路徑清單（空列表若讀取失敗）
    """
    try:
        # 剝除 ::read / ::write 後綴；::read 為讀取範圍，不列入預期修改
        raw_files = extract_where_files(
            ticket_id, project_root, logger, intent="write"
        )
        if not raw_files:
            logger.debug(f"Ticket 無 where.files: {ticket_id}")
            return []

        normalized = []
        for file_path in raw_files:
            n = normalize_path(file_path)
            if n:
                normalized.append(n)

        logger.debug(f"讀取 where.files: {len(normalized)} 個")
        return normalized

    except Exception as e:
        logger.error(f"讀取 Ticket where.files 失敗: {e}")
        sys.stderr.write(f"[Hook Error] 讀取 Ticket 失敗: {e}\n")
        return []


def read_ticket_type_and_children(ticket_id: str, project_root: Path,
                                  logger: logging.Logger) -> tuple[Optional[str], bool]:
    """讀取票的 type 與是否有子票（fail-open：失敗回 (None, False)）

    ANA 的 where.files 是分析範圍而非修改範圍（ticket-body-schema），
    有子票的父票其修改落在子票提交，兩者都不能以「父票自身 commit」判缺失。
    """
    try:
        ticket_file = find_ticket_file(ticket_id, project_root, logger)
        if not ticket_file or not ticket_file.exists():
            return None, False
        fm = parse_ticket_frontmatter(ticket_file, logger)
        if not fm:
            return None, False
        ticket_type = fm.get("type")
        children = fm.get("children")
        return (str(ticket_type).strip().upper() if ticket_type else None,
                bool(children))
    except Exception as e:
        logger.warning(f"讀取票 type/children 失敗（fail-open）: {e}")
        return None, False


def _run_git(project_root: Path, args: list[str]) -> Optional[str]:
    """執行 git 命令，回傳 stdout；非零退出回傳 None（超時等例外由呼叫端處理）。"""
    result = subprocess.run(
        ["git", "--no-optional-locks"] + args,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_DIFF_TIMEOUT,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _split_paths(out: str) -> list[str]:
    """-z 輸出（NUL 分隔，不受 quotepath 影響）轉為規範化路徑清單。"""
    return [n for n in (normalize_path(p) for p in out.split("\0")) if n]


def get_git_changed_files(project_root: Path, logger: logging.Logger,
                          ticket_id: str,
                          include_descendants: bool = False) -> list[str]:
    """取得該票的實際變更檔案：票相關 commit 範圍 + 未提交變更

    比對基準：
    1. 訊息含該票號的 commit（子任務票號不吃父票的 commit，後綴須精確相等）。
       含 merge commit：以 first-parent diff 取得合併帶入的變更。
       理由：worktree 隔離派發下 complete 在合併提交後執行，此時
       git diff HEAD 恆為空；票號是此刻唯一與該票綁定的穩定識別。
    2. 聯集 git diff HEAD：程式碼尚未提交即 complete 的情境仍可比對。

    git 呼叫失敗時記錄雙通道並略過該來源（fail-open，不阻擋）。

    Args:
        project_root: 專案根目錄（執行 git 命令的工作目錄）
        logger: Logger 實例
        ticket_id: 完整票號（含子任務後綴）

    Returns:
        list[str]: 規範化後的變更檔案清單
    """
    changed: set[str] = set()
    try:
        log_out = _run_git(project_root, [
            "log", "--fixed-strings", f"--grep={ticket_id}",
            "--format=%H%x00%s", "-n", "500"])
        if log_out is None:
            logger.warning("git log 失敗")
            sys.stderr.write("[Hook Error] git log 命令失敗\n")
        else:
            # 票號後不可再接「.數字」，避免父票吃到子任務票的 commit
            # include_descendants（有子票的父票）：後綴 .N 的子孫票提交併入
            suffix = r"(?:\.\d+)*(?!\d)" if include_descendants else r"(?!\.?\d)"
            id_re = re.compile(re.escape(ticket_id) + suffix)
            for line in log_out.splitlines():
                sha, _, subject = line.partition("\0")
                if not sha or not id_re.search(subject):
                    continue
                out = _run_git(project_root, [
                    "diff-tree", "-r", "--name-only", "-z", "--no-commit-id",
                    "--diff-merges=first-parent", sha])
                if out is None:
                    logger.warning(f"git diff-tree 失敗: {sha}")
                    continue
                changed.update(_split_paths(out))

        head_out = _run_git(project_root, ["diff", "HEAD", "--name-only", "-z"])
        if head_out is None:
            logger.warning("git diff HEAD 失敗")
            sys.stderr.write("[Hook Error] git diff 命令失敗\n")
        else:
            changed.update(_split_paths(head_out))

    except subprocess.TimeoutExpired:
        logger.error(f"git 命令超時 ({GIT_DIFF_TIMEOUT}s)")
        sys.stderr.write("[Hook Error] git 命令超時\n")
    except FileNotFoundError:
        logger.error("git 命令未找到")
        sys.stderr.write("[Hook Error] git 命令未找到\n")
    except Exception as e:
        logger.error(f"執行 git 失敗: {e}")
        sys.stderr.write(f"[Hook Error] git 命令執行失敗: {e}\n")

    logger.debug(f"票相關變更: {len(changed)} 個檔案")
    return sorted(changed)


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
    lines.append("未出現在該票的提交範圍或未提交變更中：")
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
    lines.append(f"{MSG_ACTUAL_TITLE}（該票 commit 範圍 + git diff HEAD，共 {len(git_changed_relevant)} 個相關檔案）：")
    for file in sorted(git_changed_relevant):
        lines.append(f"  - {file}")
    lines.append("")

    # 添加建議
    lines.append(f"{MSG_ADVICE_TITLE}：")
    lines.append("1. 確認代理人是否確實完成了這些檔案的修改")
    lines.append("2. 若代理人遺漏了修改，手動補完或重新派發")
    lines.append("3. 補完後執行 git diff 確認")
    lines.append("")

    lines.append("注意：此驗證比對訊息含該票號的 commit（含 merge）與未提交變更。")
    lines.append("若該票 commit 訊息未帶票號，可能誤報缺失。")
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

        # PostToolUseFailure：僅結束碼 75（動作完成、auto-commit 失敗）沿用完成後處理；
        # 正規化後的 payload 仍經 is_ticket_complete_success（286.2 的 completed 驗證器）判定
        event_name = "PostToolUse"
        if is_failure_event(input_data):
            input_data = auto_commit_failure_as_success(input_data)
            if input_data is None:
                logger.debug("失敗事件非結束碼 75，不處理")
                print(json.dumps(DEFAULT_OUTPUT))
                return 0
            event_name = FAILURE_EVENT_NAME
            logger.info("PostToolUseFailure 結束碼 75，視為完成並執行驗證")

        # subagent 環境跳過（代理人不執行 complete）
        if is_subagent_environment(input_data):
            logger.debug("subagent 環境，跳過")
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

        # ANA 的 where.files 為分析範圍：略過驗證
        ticket_type, has_children = read_ticket_type_and_children(
            ticket_id, project_root, logger)
        if ticket_type == "ANA":
            logger.info(f"Verification result: SKIP（ANA 票 where.files 為分析範圍）: {ticket_id}")
            print(json.dumps(DEFAULT_OUTPUT))
            return 0

        # 執行 git diff（有子票的父票併入子孫票提交）
        git_changed = get_git_changed_files(
            project_root, logger, ticket_id, include_descendants=has_children)

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
                    "hookEventName": event_name,
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
    sys.exit(run_hook_safely(main, HOOK_NAME))
