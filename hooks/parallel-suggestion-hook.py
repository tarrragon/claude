#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Parallel Suggestion Hook - 並行任務分析與建議

在用戶說「繼續任務鏈」時主動分析並建議可並行執行的任務。

功能：
- 識別「繼續」「下一個」「任務鏈」等關鍵字
- 掃描並行 Ticket（無 blockedBy，檔案無重疊）
- 輸出並行執行建議
- 提醒主線程主動建議並行派發，而非詢問單一任務

Exit Code：
- 0 (EXIT_SUCCESS): Hook 執行成功
- 1 (EXIT_ERROR): Hook 執行錯誤

Hook 類型: UserPromptSubmit
觸發時機: 接收用戶命令時

使用方式:
    UserPromptSubmit Hook 自動觸發，或手動測試:
    echo '{"prompt":"繼續任務鏈"}' | python3 parallel-suggestion-hook.py
    echo '{"prompt":"執行下一個"}' | python3 parallel-suggestion-hook.py
    echo '{"prompt":"接著做下一個"}' | python3 parallel-suggestion-hook.py

環境變數:
    HOOK_DEBUG: 啟用詳細日誌（true/false）
    CLAUDE_PROJECT_DIR: 專案根目錄

改進 (v1.1.0):
- 使用 common_functions 統一 logging 和 input/output
- 避免 stderr 污染
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, Set

# 設置 sys.path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from hook_utils import (
        setup_hook_logging,
        parse_ticket_frontmatter,
        read_json_from_stdin,
        run_hook_safely,
        get_project_root,
        find_ticket_files,
        validate_hook_input,
    )
    from lib.hook_messages import AskUserQuestionMessages
except ImportError as e:
    # 輸出合法 JSON 到 stdout（遵守 Hook 協定）
    print(json.dumps({"result": "continue"}))
    # 同時輸出錯誤到 stderr（雙通道要求）
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(1)

# ============================================================================
# 常數定義
# ============================================================================

# 關鍵字識別
CONTINUATION_KEYWORDS = [
    "繼續", "繼續執行", "繼續任務鏈",
    "下一個", "執行下一個", "接著做",
    "接續", "任務鏈", "子任務", "批量"
]

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1


# ============================================================================
# 輸入讀取和驗證
# ============================================================================

def get_json_from_input(input_data: Optional[Dict[str, Any]], logger) -> Dict[str, Any]:
    """
    從已解析的輸入提取 JSON 資料

    Args:
        input_data: read_hook_input() 的輸出
        logger: 日誌物件

    Returns:
        dict - 驗證後的 JSON 資料
    """
    if not input_data:
        logger.warning("No input data received")
        return {}

    logger.debug(f"輸入 JSON: {json.dumps(input_data, ensure_ascii=False, indent=2)}")
    return input_data


def validate_input(input_data: Dict[str, Any], logger) -> bool:
    """驗證輸入格式 - 已遷移至 hook_utils.validate_hook_input"""
    return validate_hook_input(input_data, logger, ("prompt",))


# ============================================================================
# 關鍵字識別
# ============================================================================

def is_continuation_request(prompt: str, logger) -> bool:
    """
    判斷是否為「繼續任務鏈」請求

    Args:
        prompt: 用戶提示文本
        logger: 日誌物件

    Returns:
        bool - 是否為繼續請求
    """
    if not prompt:
        return False

    prompt_lower = prompt.lower()

    # 檢查是否包含繼續關鍵字
    for keyword in CONTINUATION_KEYWORDS:
        if keyword.lower() in prompt_lower:
            logger.info(f"識別繼續請求關鍵字: {keyword}")
            return True

    logger.debug(f"未識別為繼續請求: {prompt[:50]}...")
    return False


# ============================================================================
# Ticket 掃描和分析
# ============================================================================


def extract_ticket_info(file_path: Path, logger) -> Optional[Dict[str, Any]]:
    """
    從 Ticket 檔案提取關鍵資訊

    Args:
        file_path: Ticket 檔案路徑
        logger: 日誌物件

    Returns:
        dict - 票務資訊 (id, status, blockedBy, where_files, chain 等)
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        ticket_id = file_path.stem

        # 解析 frontmatter
        frontmatter = parse_ticket_frontmatter(content)

        # 提取 chain 資訊
        chain = {}
        if isinstance(frontmatter.get("chain"), dict):
            chain = frontmatter["chain"]
        else:
            # 若前面的 YAML 解析失敗，嘗試正則表達式
            root_match = re.search(r'root:\s*"?([^"\n]+)"?', content)
            if root_match:
                chain["root"] = root_match.group(1).strip()

            parent_match = re.search(r'parent:\s*"?([^"\n]+)"?', content)
            if parent_match:
                chain["parent"] = parent_match.group(1).strip()

        # 提取 blockedBy
        blocked_by = frontmatter.get("blockedBy", "")
        if isinstance(blocked_by, list):
            blocked_by = ",".join(blocked_by)

        # 提取關鍵欄位
        ticket_info = {
            "id": ticket_id,
            "path": file_path,
            "status": frontmatter.get("status", "unknown"),
            "type": frontmatter.get("type", "unknown"),
            "priority": frontmatter.get("priority", "P2"),
            "title": frontmatter.get("title", ""),
            "blockedBy": blocked_by,
            "where_files": frontmatter.get("where_files", ""),
            "where_layer": frontmatter.get("where_layer", ""),
            "chain": chain
        }

        return ticket_info

    except Exception as e:
        logger.debug(f"無法提取 Ticket 資訊 {file_path}: {e}")
        return None


def extract_ticket_files(ticket_info: Dict[str, Any], logger) -> Set[str]:
    """
    從 Ticket 資訊中提取修改的檔案清單

    Args:
        ticket_info: Ticket 資訊字典
        logger: 日誌物件

    Returns:
        set - 檔案路徑集合
    """
    files = set()

    # 優先使用 where_files
    where_files = ticket_info.get("where_files", "").strip()
    if where_files:
        # 解析 where_files（逗號分隔或空格分隔）
        for file_path in re.split(r"[,\s]+", where_files):
            if file_path.strip():
                files.add(file_path.strip())
        return files

    # 次優先：where_layer
    where_layer = ticket_info.get("where_layer", "").strip()
    if where_layer:
        for file_path in re.split(r"[,\s]+", where_layer):
            if file_path.strip():
                files.add(file_path.strip())
        return files

    # 若都沒有，嘗試從內容中提取
    try:
        content = ticket_info["path"].read_text(encoding="utf-8")
        # 簡單的啟發式：尋找以 lib/, test/, .claude/ 開頭的行
        for line in content.split("\n"):
            stripped = line.strip()
            if any(stripped.startswith(prefix) for prefix in ["lib/", "test/", ".claude/", "pubspec.yaml"]):
                files.add(stripped)
        return files
    except Exception as e:
        logger.debug(f"無法提取檔案清單: {e}")
        return set()


def glob_matches(pattern: str, path: str) -> bool:
    """
    自定義 glob 匹配，支援 ** 跨越目錄。

    規則:
    - ** 匹配任意層級目錄（包括零個）
    - * 匹配同一層級的任意字符
    - ? 匹配單個字符

    Args:
        pattern: glob 模式
        path: 要匹配的路徑

    Returns:
        bool: 是否匹配
    """
    # 將 glob 模式轉換為正則表達式
    pattern = pattern.replace("\\", "/")
    path = path.replace("\\", "/")

    # 轉換 ** 為特殊標記（防止後續處理時被覆蓋）
    pattern = pattern.replace("**", "\x00DOUBLESTAR\x00")

    # 轉義正則特殊字符
    pattern = re.escape(pattern)

    # 處理萬用字元
    pattern = pattern.replace("\x00DOUBLESTAR\x00", ".*")  # ** → .*
    pattern = pattern.replace(r"\*", "[^/]*")  # * → [^/]*
    pattern = pattern.replace(r"\?", ".")  # ? → .

    # 完整匹配
    regex = f"^{pattern}$"
    return bool(re.match(regex, path))


def paths_overlap(path1: str, path2: str) -> bool:
    """
    檢查兩個路徑是否有重疊關係（語意分析）。

    規則:
    1. 完全相同 → 重疊
    2. 一個路徑是另一個的父目錄 → 重疊（e.g., lib/ 和 lib/models/book.dart）
    3. 同一目錄下的不同檔案 → 不重疊（e.g., lib/a.dart 和 lib/b.dart）
    4. 支援 glob 模式（e.g., lib/**/*.dart）

    Args:
        path1: 路徑 1（可能包含 glob 模式）
        path2: 路徑 2（可能包含 glob 模式）

    Returns:
        bool: 是否有重疊
    """
    # 標準化路徑：轉換反斜線為正斜線，移除末尾斜線
    p1 = path1.replace("\\", "/").rstrip("/")
    p2 = path2.replace("\\", "/").rstrip("/")

    # 完全相同
    if p1 == p2:
        return True

    # 處理 glob 模式
    if "*" in p1 or "?" in p1:
        # path1 是 glob 模式，測試 path2 是否匹配
        return glob_matches(p1, p2)

    if "*" in p2 or "?" in p2:
        # path2 是 glob 模式，測試 path1 是否匹配
        return glob_matches(p2, p1)

    # 使用 Path 物件進行語意分析
    path_obj1 = Path(p1)
    path_obj2 = Path(p2)

    # 父子目錄關係：檢查一個是否是另一個的父目錄
    try:
        # 若 path1 相對於 path2 的路徑不以".."開頭，則 path2 在 path1 下
        path_obj2.relative_to(path_obj1)
        return True
    except ValueError:
        pass

    try:
        # 若 path2 相對於 path1 的路徑不以".."開頭，則 path1 在 path2 下
        path_obj1.relative_to(path_obj2)
        return True
    except ValueError:
        pass

    # 無重疊
    return False


def check_files_overlap(files1: Set[str], files2: Set[str]) -> bool:
    """
    檢查兩個檔案集合是否有重疊

    Args:
        files1: 檔案集合 1
        files2: 檔案集合 2

    Returns:
        bool - 是否有重疊
    """
    # 對於兩個集合中的所有檔案對，檢查是否有路徑重疊
    for file1 in files1:
        for file2 in files2:
            if paths_overlap(file1, file2):
                return True
    return False


def find_pending_tickets_in_chain(root_id: str, all_tickets: List[Dict[str, Any]], logger) -> List[Dict[str, Any]]:
    """
    在任務鏈中找到所有 pending Ticket

    Args:
        root_id: 任務鏈根 ID
        all_tickets: 所有 Ticket 資訊
        logger: 日誌物件

    Returns:
        list - pending Ticket 清單
    """
    pending = []

    for ticket in all_tickets:
        # 檢查是否屬於該任務鏈
        if ticket["chain"].get("root") == root_id and ticket["status"] == "pending":
            pending.append(ticket)
            logger.debug(f"找到待處理 Ticket: {ticket['id']}")

    return pending


def find_parallelizable_tickets(pending_tickets: List[Dict[str, Any]], logger) -> List[List[Dict[str, Any]]]:
    """
    從待處理 Ticket 中找出可並行執行的任務組

    並行安全條件：
    1. 無 blockedBy 關係
    2. 檔案無重疊
    3. 類型一致（都是 IMP/ADJ 等）

    Args:
        pending_tickets: 待處理 Ticket 清單
        logger: 日誌物件

    Returns:
        list - 可並行執行的任務分組
    """
    # 移除有 blockedBy 的 Ticket
    unblocked = [t for t in pending_tickets if not t.get("blockedBy")]
    logger.info(f"無阻塞 Ticket: {len(unblocked)}/{len(pending_tickets)}")

    if len(unblocked) < 2:
        logger.debug("少於 2 個無阻塞 Ticket，無法並行")
        return []

    # 分組可並行執行的任務
    parallelizable_groups = []

    for i, ticket1 in enumerate(unblocked):
        group = [ticket1]
        files1 = extract_ticket_files(ticket1, logger)

        for ticket2 in unblocked[i + 1:]:
            files2 = extract_ticket_files(ticket2, logger)

            # 檢查是否有檔案重疊
            if not check_files_overlap(files1, files2):
                group.append(ticket2)
                files1.update(files2)

        # 只記錄多於 1 個任務的分組
        if len(group) > 1:
            parallelizable_groups.append(group)

    return parallelizable_groups


def find_latest_completed_ticket_root(all_tickets: List[Dict[str, Any]], logger) -> Optional[str]:
    """
    找到最近完成的 Ticket 的任務鏈根

    用於識別用戶「繼續」的是哪個任務鏈

    Args:
        all_tickets: 所有 Ticket 資訊
        logger: 日誌物件

    Returns:
        str - 任務鏈根 ID，或 None
    """
    # 過濾已完成且有有效 chain 的 Ticket
    completed = [
        t for t in all_tickets
        if t and t.get("status") == "completed" and t.get("chain") and t["chain"].get("root")
    ]

    if not completed:
        logger.debug("未找到已完成且有效的 Ticket")
        return None

    try:
        # 取最新修改的一個
        latest = max(completed, key=lambda t: t["path"].stat().st_mtime)

        root_id = latest["chain"].get("root")
        if root_id:
            logger.info(f"最近完成的任務鏈: {root_id} (from {latest['id']})")
            return root_id
    except Exception as e:
        logger.debug(f"取得最新完成 Ticket 失敗: {e}")

    return None


# ============================================================================
# 報告生成
# ============================================================================

def format_ticket_display(ticket: Dict[str, Any], logger) -> str:
    """
    格式化 Ticket 顯示

    Args:
        ticket: Ticket 資訊
        logger: 日誌物件

    Returns:
        str - 格式化的 Ticket 顯示
    """
    ticket_id = ticket["id"]
    title = ticket["title"]
    ticket_type = ticket["type"]

    # 提取檔案資訊
    files = extract_ticket_files(ticket, logger)
    files_str = ", ".join(sorted(files)[:3])  # 顯示前 3 個檔案

    if len(files) > 3:
        files_str += f" ... (+{len(files) - 3})"

    return f"- {ticket_id}: {title} ({ticket_type}) [{files_str}]"


def generate_parallel_suggestion_report(
    parallel_groups: List[List[Dict[str, Any]]],
    prompt: str,
    logger
) -> str:
    """
    生成並行建議報告

    Args:
        parallel_groups: 可並行執行的任務分組
        prompt: 用戶提示文本
        logger: 日誌物件

    Returns:
        str - 並行建議報告
    """
    if not parallel_groups:
        return ""

    # 取第一個分組（最優先的並行任務）
    parallel_tasks = parallel_groups[0]

    report = """============================================================
[並行執行建議]
============================================================

偵測到「繼續任務鏈」請求。

以下 {} 個任務可並行執行：
""".format(len(parallel_tasks))

    for task in parallel_tasks:
        report += format_ticket_display(task, logger) + "\n"

    report += """
並行安全確認：
- [x] 檔案無重疊
- [x] 無依賴關係

建議主線程：
主動建議並行派發這些任務，而非詢問單一任務。

例如：「以下 {} 個任務可並行執行，是否派發？」

詳見: .claude/rules/guides/parallel-dispatch.md
詳見: .claude/rules/core/decision-tree.md 第四層半

============================================================
""".format(len(parallel_tasks))

    return report


# ============================================================================
# 輸出生成
# ============================================================================

def generate_hook_output(
    is_continuation: bool,
    parallel_suggestion: Optional[str]
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        is_continuation: 是否為繼續請求
        parallel_suggestion: 並行建議報告（如有）

    Returns:
        dict - Hook 輸出 JSON
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit"
        }
    }

    # 如果有並行建議，添加到額外上下文
    if is_continuation and parallel_suggestion:
        output["hookSpecificOutput"]["additionalContext"] = parallel_suggestion

    return output


def save_analysis_log(
    is_continuation: bool,
    root_id: Optional[str],
    parallel_count: int,
    logger
) -> None:
    """
    儲存分析日誌

    Args:
        is_continuation: 是否為繼續請求
        root_id: 任務鏈根 ID
        parallel_count: 並行任務數
        logger: 日誌物件
    """
    project_dir = get_project_root()
    log_dir = project_dir / ".claude" / "hook-logs" / "parallel-suggestion"
    log_dir.mkdir(parents=True, exist_ok=True)

    report_file = log_dir / f"analysis-{datetime.now().strftime('%Y%m%d')}.log"

    try:
        log_entry = f"""[{datetime.now().isoformat()}]
  IsContinuationRequest: {is_continuation}
  ChainRoot: {root_id}
  ParallelTaskCount: {parallel_count}

"""
        with open(report_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
        logger.debug(f"分析日誌已儲存: {report_file}")
    except Exception as e:
        logger.warning(f"儲存分析日誌失敗: {e}")


# ============================================================================
# 主入口點
# ============================================================================

def main() -> int:
    """
    主入口點

    執行流程:
    1. 讀取 JSON 輸入
    2. 驗證輸入格式
    3. 判斷是否為繼續請求
    4. 如果是，掃描 Ticket 並分析並行可行性
    5. 生成並行建議報告
    6. 產出 Hook 輸出

    Returns:
        int - Exit code (EXIT_SUCCESS 或 EXIT_ERROR)
    """
    # 步驟 0: 初始化日誌
    logger = setup_hook_logging("parallel-suggestion-hook")

    logger.info("Parallel Suggestion Hook 啟動")

    # 步驟 1: 讀取 JSON 輸入
    input_data = read_json_from_stdin(logger)
    if not input_data:
        input_data = {}

    # 步驟 2: 驗證輸入格式
    if not validate_input(input_data, logger):
        logger.error("輸入格式錯誤")
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}
        }, ensure_ascii=False, indent=2))
        return EXIT_SUCCESS

    prompt = input_data.get("prompt", "")

    # 步驟 3: 判斷是否為繼續請求
    is_continuation = is_continuation_request(prompt, logger)
    logger.info(f"繼續請求判斷: {is_continuation}")

    parallel_suggestion = None
    parallel_count = 0
    root_id = None

    if is_continuation:
        # 步驟 4: 掃描 Ticket 並分析
        logger.info("開始掃描並行任務...")

        project_root = get_project_root()
        all_tickets = find_ticket_files(project_root, logger=logger)
        tickets_info = []

        for ticket_file in all_tickets:
            ticket_info = extract_ticket_info(ticket_file, logger)
            if ticket_info:
                tickets_info.append(ticket_info)

        logger.info(f"掃描到 {len(tickets_info)} 個 Ticket")

        # 統計狀態分佈
        status_counts = {}
        for ticket in tickets_info:
            status = ticket.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        logger.debug(f"狀態分佈: {status_counts}")

        # 找到最近完成的任務鏈
        root_id = find_latest_completed_ticket_root(tickets_info, logger)

        if root_id:
            logger.info(f"找到最近任務鏈根: {root_id}")
            # 在該任務鏈中找待處理 Ticket
            pending = find_pending_tickets_in_chain(root_id, tickets_info, logger)
            logger.info(f"找到 {len(pending)} 個待處理 Ticket")

            if pending:
                # 分析可並行執行的任務
                parallel_groups = find_parallelizable_tickets(pending, logger)
                logger.info(f"找到 {len(parallel_groups)} 個並行分組")

                if parallel_groups:
                    parallel_count = len(parallel_groups[0])
                    # 步驟 6: 生成並行建議報告
                    parallel_suggestion = generate_parallel_suggestion_report(
                        parallel_groups, prompt, logger
                    )
                    logger.info(f"生成並行建議: {parallel_count} 個任務")
        else:
            logger.info("未找到最近完成的任務鏈根")

    # 步驟 6.5: 繼續請求但無並行建議時，提示 Wave 收尾
    if is_continuation and not parallel_suggestion:
        parallel_suggestion = AskUserQuestionMessages.WAVE_WRAP_UP_REMINDER
        logger.info("無並行建議，輸出 Wave 收尾提醒")

    # 步驟 7: 產出 Hook 輸出
    hook_output = generate_hook_output(is_continuation, parallel_suggestion)
    print(json.dumps(hook_output, ensure_ascii=False, indent=2))

    # 儲存分析日誌（直接使用已有的 root_id，避免重複掃描）
    save_analysis_log(is_continuation, root_id, parallel_count, logger)

    logger.info("Parallel Suggestion Hook 執行完成")
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = run_hook_safely(main, "parallel-suggestion-hook")
    sys.exit(exit_code)
