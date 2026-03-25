#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0",
#     "pathlib2>=2.3.0; python_version < '3.4'"
# ]
# ///
"""
PostToolUse Hook: ticket-creation-validation-hook.py

驗證新建立的 Ticket 是否包含完整的 decision_tree_path 欄位。

觸發條件：
  - Hook 類型: PostToolUse (Write 工具執行後)
  - 檔案路徑: 符合 docs/work-logs/*/tickets/*.md 模式

驗證邏輯：
  1. 檢查檔案路徑是否為 Ticket 檔案
  2. 檢查豁免條件（子任務或 DOC 類型）
  3. 檢查 decision_tree_path 是否完整
  4. 輸出警告（若缺少）

豁免條件：
  - parent_id 非空：子任務
  - type = "DOC"：文件類型

行為：
  - 缺少 decision_tree_path 時輸出 WARNING 到 stderr
  - 始終返回 exit code 0（不阻止操作）
"""

import sys
import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import yaml
except ImportError:
    yaml = None


# 日誌配置
def setup_logging() -> logging.Logger:
    """設置日誌。"""
    log_dir = Path.home() / ".claude" / "hook-logs" / "ticket-creation-validation"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ticket-creation-validation")
    logger.setLevel(logging.DEBUG)

    handler = logging.FileHandler(log_dir / "hook.log")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = setup_logging()


def is_ticket_file(file_path: Path) -> bool:
    """判斷檔案是否為 Ticket 檔案。

    Ticket 檔案路徑模式：docs/work-logs/*/tickets/*.md

    Args:
        file_path: 檔案路徑

    Returns:
        True 如果是 Ticket 檔案，否則 False
    """
    # 轉換為 posix 路徑便於檢查
    path_str = file_path.as_posix()
    pattern = r"docs/work-logs/[^/]+/tickets/[^/]+\.md$"
    return bool(re.search(pattern, path_str))


def parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
    """解析 YAML frontmatter。

    Ticket 檔案格式：
        ---
        key: value
        ---
        # Body content

    Args:
        content: 檔案內容

    Returns:
        frontmatter 字典，若解析失敗返回 None
    """
    if not content.startswith("---"):
        return None

    try:
        # 找到第二個 --- 的位置
        lines = content.split("\n")
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break

        if end_idx is None:
            logger.warning("Cannot find closing --- in frontmatter")
            return None

        # 提取 frontmatter 內容
        frontmatter_str = "\n".join(lines[1:end_idx])

        if yaml is None:
            logger.error("PyYAML not available, cannot parse frontmatter")
            return None

        frontmatter = yaml.safe_load(frontmatter_str)
        return frontmatter if isinstance(frontmatter, dict) else None
    except Exception as e:
        logger.error(f"Error parsing frontmatter: {e}")
        print(f"[ERROR] Failed to parse frontmatter: {e}", file=sys.stderr)
        return None


def check_ticket_decision_tree_path(
    file_path: Path,
    content: str,
) -> Optional[str]:
    """檢查 Ticket 是否包含完整的 decision_tree_path 欄位。

    Args:
        file_path: Ticket 檔案路徑
        content: Ticket 檔案內容

    Returns:
        警告訊息（若需要輸出），None 表示無警告
    """
    # 1. 判斷是否為 Ticket 檔案
    if not is_ticket_file(file_path):
        logger.debug(f"Not a ticket file: {file_path}")
        return None

    # 2. 解析 frontmatter
    frontmatter = parse_frontmatter(content)
    if frontmatter is None:
        logger.warning(f"Cannot parse frontmatter: {file_path}")
        return None

    # 3. 判斷豁免條件
    parent_id = frontmatter.get("parent_id")
    ticket_type = frontmatter.get("type")

    if parent_id or ticket_type == "DOC":
        logger.debug(f"Ticket {file_path} is exempted (child or DOC)")
        return None

    # 4. 檢查 decision_tree_path 是否完整
    decision_tree_path = frontmatter.get("decision_tree_path")

    if decision_tree_path is None:
        # 缺少欄位
        ticket_id = frontmatter.get("id", str(file_path))
        warning_msg = (
            f"[WARNING] Ticket {ticket_id} 缺少必填欄位 decision_tree_path\n"
            f"         請補填以下三個子欄位：\n"
            f"           - entry_point: 進入決策樹的層級\n"
            f"           - final_decision: 做出的決策\n"
            f"           - rationale: 決策理由\n"
            f"         參考格式：\n"
            f"           decision_tree_path:\n"
            f"             entry_point: \"第五層 TDD 階段判斷\"\n"
            f"             final_decision: \"派發 Phase 3b 給 parsley\"\n"
            f"             rationale: \"Phase 2 已完成\""
        )
        logger.warning(f"Missing decision_tree_path: {ticket_id}")
        return warning_msg

    if isinstance(decision_tree_path, dict):
        # 檢查子欄位完整性
        entry_point = decision_tree_path.get("entry_point")
        final_decision = decision_tree_path.get("final_decision")
        rationale = decision_tree_path.get("rationale")

        if entry_point and final_decision and rationale:
            # 欄位完整
            logger.debug(f"Ticket {file_path} has complete decision_tree_path")
            return None
        else:
            # 子欄位缺失
            ticket_id = frontmatter.get("id", str(file_path))
            missing = []
            if not entry_point:
                missing.append("entry_point")
            if not final_decision:
                missing.append("final_decision")
            if not rationale:
                missing.append("rationale")

            warning_msg = (
                f"[WARNING] Ticket {ticket_id} 的 decision_tree_path 欄位不完整\n"
                f"         缺少子欄位：{', '.join(missing)}"
            )
            logger.warning(f"Incomplete decision_tree_path: {ticket_id}")
            return warning_msg

    # decision_tree_path 存在但不是字典
    logger.debug(f"Ticket {file_path} has decision_tree_path but invalid format")
    return None


def main() -> int:
    """Hook 進入點。

    標準 PostToolUse Hook 輸入格式（JSON from stdin）：
      {
        "tool_name": "Write",
        "tool_input": {
          "file_path": "...",
          "content": "..."
        }
      }

    Returns:
        exit code 0（始終允許操作）
    """
    try:
        # 從 stdin 讀取 Hook 輸入 JSON
        input_text = sys.stdin.read().strip()

        # 空輸入（某些事件類型無輸入）
        if not input_text:
            logger.debug("Hook called with empty input")
            return 0

        try:
            hook_input = json.loads(input_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            print(f"[ERROR] Invalid JSON input: {e}", file=sys.stderr)
            return 0

        # 驗證輸入格式
        if not isinstance(hook_input, dict):
            logger.error(f"Expected dict, got {type(hook_input).__name__}")
            return 0

        # 提取 Write 工具的輸入
        tool_input = hook_input.get("tool_input", {})
        file_path_str = tool_input.get("file_path")
        content = tool_input.get("content")

        if not file_path_str or not isinstance(content, str):
            logger.debug("Missing required fields in tool_input")
            return 0

        file_path = Path(file_path_str)

        # 檢查決策樹路徑
        warning_msg = check_ticket_decision_tree_path(file_path, content)

        if warning_msg:
            # 輸出警告到 stderr
            print(warning_msg, file=sys.stderr)
            logger.info(f"Warning output for: {file_path}")

        # 始終返回 0（不阻止操作）
        return 0

    except Exception as e:
        logger.error(f"Unexpected error in hook: {e}")
        print(f"[ERROR] Hook execution error: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
