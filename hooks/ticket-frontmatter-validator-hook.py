#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""Ticket Frontmatter Validator Hook (PostToolUse 事後警告)

偵測 Edit/Write ticket .md 檔案時 YAML frontmatter 的合規性，違規時 stderr 警告 +
hook-logs 記錄，不阻擋 Edit。

觸發條件:
- PostToolUse 事件
- tool_name 為 Edit / Write
- 目標路徑符合 docs/work-logs/**/tickets/*.md 或 .claude/tickets/*.md

檢查欄位:
- status / completed_at / acceptance / who
  （詳見 .claude/skills/ticket/ticket_system/validators/frontmatter_validator.py）

設計依據:
- Ticket 0.18.0-W14-028 (源於 W14-024 IMP-1)
- IMP-013 雙通道 observability (stderr + hook-logs)
- IMP-048 避免誤觸 hook error：本 hook 違規視為「已預期的品質警示」，
  使用 logger.info 寫日誌、用 stderr 寫警告（Claude Code 會顯示 hook error
  提示用戶注意；這是預期行為，非 crash）
- 共用驗證邏輯由 ticket_system.validators.frontmatter_validator 提供

Exit Code:
- 0: 永遠成功（事後警告，不阻擋）
- 非 0: 僅 hook 本身 crash 時由 run_hook_safely 回報
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# hook_utils（同目錄）
sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    save_check_log,
    validate_hook_input,
)

# 共用 validator（.claude/skills/ticket/ticket_system/validators）
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SKILL_TICKET_ROOT = _PROJECT_ROOT / ".claude" / "skills" / "ticket"
if str(_SKILL_TICKET_ROOT) not in sys.path:
    sys.path.insert(0, str(_SKILL_TICKET_ROOT))

from ticket_system.validators.frontmatter_validator import (  # noqa: E402
    ValidationIssue,
    validate_frontmatter,
)

import yaml  # noqa: E402


# ============================================================================
# 常數
# ============================================================================

EXIT_SUCCESS = 0
EXIT_ERROR = 1

HOOK_NAME = "ticket-frontmatter-validator"

# Ticket ID 正規：從檔名抽取
_TICKET_ID_FROM_FILENAME = re.compile(
    r"(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*(?:-[a-z0-9][a-z0-9-]*)?)\.md$"
)

# Frontmatter 區塊
_FRONTMATTER_BLOCK = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL
)


# ============================================================================
# 檔案判別
# ============================================================================

def is_ticket_file(file_path: str) -> bool:
    """判斷是否為 ticket .md 檔案。"""
    if not file_path or not file_path.endswith(".md"):
        return False
    p = file_path.replace("\\", "/")
    return (
        ("docs/work-logs/" in p and "/tickets/" in p)
        or ".claude/tickets/" in p
    )


def extract_ticket_id(file_path: str) -> Optional[str]:
    """從檔名抽取 ticket ID（供日誌與錯誤訊息使用）。"""
    match = _TICKET_ID_FROM_FILENAME.search(file_path.replace("\\", "/"))
    return match.group(1) if match else None


# ============================================================================
# Frontmatter 解析
# ============================================================================

def parse_frontmatter(file_path: str, logger) -> Optional[Dict[str, Any]]:
    """讀取檔案並解析 YAML frontmatter。

    Returns:
        dict - 解析後的 frontmatter（dict）
        None - 無 frontmatter 區塊 / 檔案不存在 / 解析失敗
    """
    path = Path(file_path)
    if not path.exists():
        logger.info(f"檔案不存在（可能已被刪除），跳過: {file_path}")
        return None
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.info(f"讀取檔案失敗，跳過: {file_path} ({e})")
        return None

    match = _FRONTMATTER_BLOCK.match(content)
    if not match:
        logger.debug(f"無 frontmatter 區塊: {file_path}")
        return None

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        logger.info(f"YAML 解析失敗: {file_path} ({e})")
        return None

    if not isinstance(data, dict):
        logger.debug(f"frontmatter 非 dict (got {type(data).__name__}): {file_path}")
        return None
    return data


# ============================================================================
# 輸出
# ============================================================================

def format_warning_message(
    ticket_id: Optional[str], file_path: str, issues: List[ValidationIssue]
) -> str:
    """組裝 stderr 警告訊息。"""
    header_id = ticket_id or Path(file_path).name
    lines = [
        f"[{HOOK_NAME}] WARNING: {header_id} frontmatter 違規 ({len(issues)} 項)",
        f"檔案: {file_path}",
    ]
    for issue in issues:
        lines.append(f"  - {issue.format_line()}")
    lines.append(
        "詳細日誌: .claude/hook-logs/ticket-frontmatter-validator/"
    )
    return "\n".join(lines) + "\n"


def emit_allow_output(
    issues: Optional[List[ValidationIssue]] = None,
) -> None:
    """輸出 PostToolUse 放行 JSON（違規時附 additionalContext）。"""
    output: Dict[str, Any] = {
        "hookSpecificOutput": {"hookEventName": "PostToolUse"}
    }
    if issues:
        detail_lines = [
            f"[ticket-frontmatter-validator] 偵測到 {len(issues)} 項 frontmatter 違規："
        ]
        for issue in issues:
            detail_lines.append(f"- {issue.format_line()}")
        output["hookSpecificOutput"]["additionalContext"] = "\n".join(detail_lines)
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ============================================================================
# 主入口
# ============================================================================

def _skip(reason: str, logger) -> int:
    logger.debug(f"跳過: {reason}")
    emit_allow_output(None)
    return EXIT_SUCCESS


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    logger.info(f"{HOOK_NAME} Hook 啟動")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return _skip("stdin 無 JSON 輸入", logger)

    if not validate_hook_input(input_data, logger, ("tool_name", "tool_input")):
        return _skip("輸入格式不符", logger)

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return _skip(f"非 Edit/Write 工具: {tool_name}", logger)

    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")
    if not is_ticket_file(file_path):
        return _skip(f"非 ticket 檔案: {file_path}", logger)

    logger.info(f"檢測到 ticket 檔案: {file_path}")

    frontmatter = parse_frontmatter(file_path, logger)
    if frontmatter is None:
        # 無 frontmatter 或解析失敗：不屬於本 hook 檢查範圍
        emit_allow_output(None)
        return EXIT_SUCCESS

    ticket_id = extract_ticket_id(file_path)
    issues = validate_frontmatter(frontmatter)

    if not issues:
        logger.info(f"frontmatter 合規: {ticket_id or file_path}")
        emit_allow_output(None)
        _save_log(ticket_id, file_path, [], logger)
        return EXIT_SUCCESS

    # 違規：雙通道 observability
    warning_msg = format_warning_message(ticket_id, file_path, issues)
    sys.stderr.write(warning_msg)
    for issue in issues:
        logger.info(f"違規 {issue.field}: {issue.detail}")

    emit_allow_output(issues)
    _save_log(ticket_id, file_path, issues, logger)
    return EXIT_SUCCESS


def _save_log(
    ticket_id: Optional[str],
    file_path: str,
    issues: List[ValidationIssue],
    logger,
) -> None:
    """寫入 hook-logs check log。"""
    status = "COMPLIANT" if not issues else f"VIOLATION ({len(issues)})"
    lines = [
        f"[{datetime.now().isoformat()}]",
        f"  TicketID: {ticket_id}",
        f"  FilePath: {file_path}",
        f"  Status: {status}",
    ]
    for issue in issues:
        lines.append(f"  - {issue.field}: {issue.detail}")
    lines.append("")
    save_check_log(HOOK_NAME, "\n".join(lines) + "\n", logger)


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
