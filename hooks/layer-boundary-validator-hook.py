#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Layer 1/2 邊界驗證 Hook

驗證 Layer 1 檔案中是否引用了 Layer 2 專案特定概念。

功能：
- 掃描 Layer 1 檔案（.claude/rules/*, .claude/skills/tdd/references/portable-*）
- 檢測 7 大禁止項：/ticket CLI、Agent 名稱、Hook 系統、決策樹、/parallel-evaluation、路徑硬編碼、Wave/Patch
- 排除合法上下文（blockquote、程式碼區塊、HTML 註解、行內程式碼、參考連結）
- 輸出清晰的警告訊息，不阻塊操作（exit 0）

Hook 類型: PostToolUse（非阻塊）
Matcher: Write
監控路徑：
  - .claude/rules/core/*.md
  - .claude/rules/flows/*.md
  - .claude/rules/guides/*.md
  - .claude/rules/forbidden/*.md
  - .claude/skills/tdd/references/portable-*.md

使用方式:
    PostToolUse Hook 自動觸發，或手動測試:
    echo '{"tool_name":"Write","tool_input":{"file_path":".claude/rules/core/decision-tree.md"}}' | python3 layer-boundary-validator-hook.py
"""

import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Set, Tuple

# 加入 hook_utils 路徑（相同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    save_check_log,
    validate_hook_input,
    is_subagent_environment,
)

# ============================================================================
# 常數定義
# ============================================================================

# Layer 1 檔案路徑模式
LAYER1_PATTERNS = [
    ".claude/rules/core/",
    ".claude/rules/flows/",
    ".claude/rules/guides/",
    ".claude/rules/forbidden/",
    ".claude/skills/tdd/references/portable-design-boundary.md",
    ".claude/skills/tdd/references/portable-tdd-standard.md",
]

# Exit Code
EXIT_SUCCESS = 0
EXIT_ERROR = 1

# 禁止項定義（7 大類）
PROHIBITED_ITEMS = [
    {
        "id": "ticket_cli",
        "pattern": r"/ticket\s+\w+",
        "description": "/ticket CLI 指令",
        "replacement": ["任務系統", "狀態管理", "認領任務", "更新進度"],
    },
    {
        "id": "agent_names",
        "pattern": r"(lavender|parsley|sage|pepper|cinnamon|saffron|basil|rosemary|oregano|thyme|ginger)[\w-]*(?:developer|architect|designer|auditor|manager|analyzer|tuner|implementer|owl|analyst|miner)",
        "description": "具體 Agent 名稱",
        "replacement": ["設計者", "實作者", "審查者", "代理人", "專業代理人"],
    },
    {
        "id": "hook_system",
        "pattern": [
            r"\.claude/hooks/",
            r"hook_utils",
            r"(PostToolUse|PreToolUse|UserPromptSubmit)(?:\s+Hook)?",
            r"(?<!`)[\w\-]*-hook(?:\.py)?(?!`)",
        ],
        "description": "Hook 系統引用",
        "replacement": ["驗證機制", "檢查點", "自動驗證", "自動化機制"],
    },
    {
        "id": "decision_tree",
        "pattern": [
            r"決策樹|decision-tree",
            r"(?:決策樹|decision[\s-]*tree)第[負\-\d零一二三四五六七八九]層",
        ],
        "description": "decision-tree 引用",
        "replacement": ["路由決策", "階段轉換", "PM 決策邏輯", "主線程決策"],
    },
    {
        "id": "parallel_evaluation",
        "pattern": [
            r"/parallel-evaluation",
            r"parallel[\s-]*evaluation",
        ],
        "description": "/parallel-evaluation 工具引用",
        "replacement": ["多維度分析", "交叉審查", "並行分析", "多視角審核"],
    },
    {
        "id": "path_hardcoding",
        "pattern": [
            r"\.claude/",
            r"docs/(?:work-logs|todolist)",
        ],
        "description": "本專案路徑硬編碼",
        "replacement": ["規則目錄", "配置目錄", "工作目錄", "日誌位置", "文件位置"],
    },
    {
        "id": "version_concepts",
        "pattern": [
            r"\bW\d+\b",
            r"\b(?:Patch|Minor|Major)\b",
        ],
        "description": "Wave/Patch 版本概念",
        "replacement": ["執行週期", "迭代", "版本發布", "相同目標的執行單位"],
    },
]

# ============================================================================
# 檔案識別
# ============================================================================


def is_layer1_file(file_path: str, logger) -> bool:
    """
    判斷檔案是否為 Layer 1 規則檔

    Args:
        file_path: 檔案路徑
        logger: Logger 實例

    Returns:
        bool - 是否為 Layer 1 檔案
    """
    path_str = str(file_path)

    for pattern in LAYER1_PATTERNS:
        if pattern in path_str and path_str.endswith(".md"):
            logger.debug(f"識別為 Layer 1 檔案: {path_str}")
            return True

    logger.debug(f"非 Layer 1 檔案: {path_str}")
    return False


# ============================================================================
# 排除規則（上下文分析）
# ============================================================================


def extract_exclusions(content: str, logger) -> Set[int]:
    """
    提取排除的行號集合

    實現排除規則優先級：
    1. HTML 註解（<!-- ... -->）
    2. 程式碼區塊（```...```）
    3. blockquote（> 開頭的行）
    4. 行內程式碼（` ... `）需在行內進行

    Args:
        content: 檔案內容
        logger: Logger 實例

    Returns:
        Set[int] - 應排除的行號集合（0-indexed）
    """
    exclusions = set()
    lines = content.split("\n")

    in_html_comment = False
    in_code_block = False

    for line_idx, line in enumerate(lines):
        # HTML 註解檢查
        if "<!--" in line:
            in_html_comment = True

        if in_html_comment:
            exclusions.add(line_idx)
            if "-->" in line:
                in_html_comment = False
            continue

        # 程式碼區塊檢查
        if "```" in line:
            in_code_block = not in_code_block

        if in_code_block:
            exclusions.add(line_idx)
            continue

        # blockquote 檢查（> 開頭）
        if line.strip().startswith(">"):
            exclusions.add(line_idx)
            continue

    logger.debug(f"排除 {len(exclusions)} 行內容")
    return exclusions


def is_in_link(line: str, match_start: int, match_end: int) -> bool:
    """
    判斷匹配是否在 Markdown 連結中 [text](path)

    Args:
        line: 行內容
        match_start: 匹配開始位置
        match_end: 匹配結束位置

    Returns:
        bool - 是否在連結中
    """
    # 尋找左括號 (
    left_paren = line.rfind("(", 0, match_start)
    if left_paren == -1:
        return False

    # 確認左括號前有 [
    if left_paren > 0 and line[left_paren - 1] != "]":
        return False

    # 尋找右括號 )
    right_paren = line.find(")", match_end)
    if right_paren == -1:
        return False

    return left_paren < match_start and match_end < right_paren


def is_in_inline_code(line: str, match_start: int, match_end: int) -> bool:
    """
    判斷匹配是否在行內程式碼中（支援單和雙反引號）

    Args:
        line: 行內容
        match_start: 匹配開始位置
        match_end: 匹配結束位置

    Returns:
        bool - 是否在行內程式碼中
    """
    # 檢查是否在反引號對中（支援 ` ... ` 和 `` ... ``）

    # 查找所有反引號位置
    backtick_positions = [i for i, char in enumerate(line) if char == "`"]

    if not backtick_positions:
        return False

    # 查找匹配開始位置之前的最後一個反引號
    before_match = [pos for pos in backtick_positions if pos < match_start]

    if not before_match:
        return False

    last_backtick_before = before_match[-1]

    # 查找匹配結束位置之後的第一個反引號
    after_match = [pos for pos in backtick_positions if pos >= match_end]

    if not after_match:
        return False

    # 檢查是否形成反引號對（中間沒有其他反引號）
    between = [pos for pos in backtick_positions
               if last_backtick_before < pos < after_match[0]]

    # 如果中間只有反引號對本身，則匹配在程式碼中
    return len(between) == 0


# ============================================================================
# 禁止項掃描
# ============================================================================


def scan_prohibited_items(content: str, exclusions: Set[int], logger) -> List[Dict[str, Any]]:
    """
    掃描禁止項

    Args:
        content: 檔案內容
        exclusions: 排除行號集合
        logger: Logger 實例

    Returns:
        List[Dict] - 違規清單，每個違規含行號、列號、類型、內容
    """
    violations = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines):
        # 跳過排除的行
        if line_num in exclusions:
            logger.debug(f"跳過排除行 {line_num + 1}")
            continue

        # 掃描每個禁止項
        for item in PROHIBITED_ITEMS:
            patterns = item["pattern"]
            if isinstance(patterns, str):
                patterns = [patterns]

            for pattern in patterns:
                try:
                    for match in re.finditer(pattern, line):
                        match_start = match.start()
                        match_end = match.end()

                        # 檢查是否在連結中
                        if is_in_link(line, match_start, match_end):
                            logger.debug(
                                f"跳過連結中的內容: Line {line_num + 1}, Pattern: {item['id']}"
                            )
                            continue

                        # 檢查是否在行內程式碼中
                        if is_in_inline_code(line, match_start, match_end):
                            logger.debug(
                                f"跳過行內程式碼: Line {line_num + 1}, Pattern: {item['id']}"
                            )
                            continue

                        # 記錄違規
                        violation = {
                            "line_num": line_num + 1,  # 1-indexed
                            "column": match_start + 1,  # 1-indexed
                            "type": item["description"],
                            "content": match.group(0),
                            "replacement": item["replacement"][0],
                            "item_id": item["id"],
                        }
                        violations.append(violation)
                        logger.debug(f"發現違規: {violation}")

                except re.error as e:
                    logger.error(f"正則表達式錯誤 ({item['id']}): {e}")

    logger.info(f"共掃描到 {len(violations)} 個違規")
    return violations


# ============================================================================
# 輸出生成
# ============================================================================


def format_warning_message(violations: List[Dict[str, Any]], file_path: str) -> str:
    """
    格式化警告訊息

    Args:
        violations: 違規清單
        file_path: 檔案路徑

    Returns:
        str - 格式化後的警告訊息
    """
    if not violations:
        return ""

    output_lines = []

    for violation in violations:
        output_lines.append("[WARNING] Layer 1/2 邊界驗證警告")
        output_lines.append("")
        output_lines.append(f"檔案：{file_path}")
        output_lines.append(
            f"位置：Line {violation['line_num']}, Column {violation['column']}"
        )
        output_lines.append(f"禁止項：{violation['type']}")
        output_lines.append(f"內容：{violation['content']}")
        output_lines.append(f"建議：改為「{violation['replacement']}」")
        output_lines.append("相關規範：.claude/skills/tdd/references/portable-design-boundary.md")
        output_lines.append("")

    return "\n".join(output_lines)


def generate_hook_output(
    has_violations: bool, file_path: str, message: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成 Hook 輸出

    Args:
        has_violations: 是否有違規
        file_path: 檔案路徑
        message: 警告訊息（如有）

    Returns:
        dict - Hook 輸出 JSON
    """
    output = {"hookSpecificOutput": {"hookEventName": "PostToolUse"}}

    if has_violations and message:
        output["hookSpecificOutput"]["additionalContext"] = message

    return output


# ============================================================================
# 主入口點
# ============================================================================


def _validate_input(input_data: Dict[str, Any], logger) -> Tuple[bool, Optional[str]]:
    """
    驗證輸入並提取檔案路徑

    Args:
        input_data: 原始輸入 JSON 資料
        logger: Logger 實例

    Returns:
        Tuple[bool, Optional[str]] - (驗證成功, 檔案路徑)
    """
    if not validate_hook_input(input_data, logger, ("tool_input",)):
        logger.debug("輸入格式不完整，跳過檢查")
        return False, None

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    return True, file_path


def _load_file_content(file_path: str, logger) -> Tuple[bool, Optional[str]]:
    """
    讀取檔案內容

    Args:
        file_path: 檔案路徑
        logger: Logger 實例

    Returns:
        Tuple[bool, Optional[str]] - (成功狀態, 檔案內容)
    """
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        logger.debug(f"讀取檔案成功，共 {len(content)} 字符")
        return True, content
    except FileNotFoundError:
        logger.error(f"檔案不存在: {file_path}")
        return False, None
    except UnicodeDecodeError as e:
        logger.error(f"編碼錯誤: {file_path} - {e}")
        return False, None


def _output_error(file_path: str, error_msg: str) -> None:
    """
    輸出錯誤結果

    Args:
        file_path: 檔案路徑
        error_msg: 錯誤訊息
    """
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": error_msg,
                }
            },
            ensure_ascii=False,
        )
    )


def _output_success() -> None:
    """輸出空白成功結果（無違規）"""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse"}}, ensure_ascii=False))


def main() -> int:
    """
    主入口點

    執行流程:
    1. 初始化 logger
    2. 驗證環境（subagent）
    3. 讀取並驗證輸入
    4. 判斷是否為 Layer 1 檔案
    5. 讀取檔案內容
    6. 掃描禁止項
    7. 生成並輸出結果

    Returns:
        int - Exit code (0=success, 1=error)
    """
    logger = setup_hook_logging("layer-boundary-validator")

    try:
        logger.info("Layer 1/2 邊界驗證 Hook 啟動")

        # 讀取輸入
        input_data = read_json_from_stdin(logger)

        # 檢測 subagent 環境
        if is_subagent_environment(input_data):
            logger.debug("在 subagent 環境中執行，跳過檢查")
            _output_success()
            return EXIT_SUCCESS

        # 驗證輸入
        valid, file_path = _validate_input(input_data, logger)
        if not valid:
            _output_success()
            return EXIT_SUCCESS

        logger.info(f"檢查檔案: {file_path}")

        # 判斷是否為 Layer 1 檔案
        if not is_layer1_file(file_path, logger):
            logger.debug("非 Layer 1 檔案，跳過檢查")
            _output_success()
            return EXIT_SUCCESS

        logger.info(f"檢測到 Layer 1 檔案: {file_path}")

        # 讀取檔案內容
        success, content = _load_file_content(file_path, logger)
        if not success:
            _output_error(file_path, f"無法讀取檔案: {file_path}")
            return EXIT_ERROR

        # 掃描禁止項
        exclusions = extract_exclusions(content, logger)
        violations = scan_prohibited_items(content, exclusions, logger)

        # 生成結果
        warning_msg = format_warning_message(violations, file_path)
        hook_output = generate_hook_output(
            len(violations) > 0, file_path, warning_msg if warning_msg else None
        )

        # 輸出結果
        print(json.dumps(hook_output, ensure_ascii=False, indent=2))
        if warning_msg:
            print(warning_msg, file=sys.stderr)

        # 保存日誌
        log_entry = f"""[{datetime.now().isoformat()}]
  FilePath: {file_path}
  Violations: {len(violations)}
  Details: {json.dumps([{v['type']: v['content']} for v in violations], ensure_ascii=False)}

"""
        save_check_log("layer-boundary-validator", log_entry, logger)

        logger.info(f"Layer 1/2 邊界驗證 Hook 完成，發現 {len(violations)} 個違規")
        return EXIT_SUCCESS

    except Exception as e:
        logger.critical(f"Hook 執行錯誤: {e}", exc_info=True)
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": f"Hook 執行錯誤，詳見日誌: .claude/hook-logs/layer-boundary-validator/",
                    },
                    "error": {"type": type(e).__name__, "message": str(e)},
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "layer-boundary-validator"))
