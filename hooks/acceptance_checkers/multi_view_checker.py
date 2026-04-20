"""
Multi-View Status Checker - ANA Ticket Solution multi_view_status 標註檢查

對應 Ticket 0.18.0-W10-051（治本方案 D）：
在 ANA Ticket complete 前，強制 Solution 區段包含 multi_view_status 標註，
讓多視角審查在 ANA 設計階段成為顯式判定，而非事後補救。

Schema 來源（單一事實）：
    .claude/config/ana-solution-schema.yaml

合法值域：reviewed / skipped / n_a
- reviewed: 必須列出 reviewers（代理人 ID）與 conclusion（結論摘要）
- skipped:  必須附 reason（跳過理由）
- n_a:      必須附 reason（判定不適用理由）
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # 若環境無 PyYAML，使用 fallback schema


# 預設 schema（當 YAML 檔案讀取失敗時的 fallback，確保 hook 不會因設定檔缺失而崩潰）
_DEFAULT_SCHEMA = {
    "field_key": "multi_view_status",
    "allowed_values": ["reviewed", "skipped", "n_a"],
    "required_subfields": {
        "reviewed": ["reviewers", "conclusion"],
        "skipped": ["reason"],
        "n_a": ["reason"],
    },
}


def load_schema(project_dir: Path, logger) -> dict:
    """從 .claude/config/ana-solution-schema.yaml 讀取 schema。

    讀取失敗時回傳 _DEFAULT_SCHEMA，確保 hook 永遠可運作。
    """
    schema_path = project_dir / ".claude" / "config" / "ana-solution-schema.yaml"
    if not schema_path.exists():
        logger.info(
            "ana-solution-schema.yaml 不存在，使用預設 schema: %s", schema_path
        )
        return _DEFAULT_SCHEMA

    if yaml is None:
        logger.info("PyYAML 未安裝，使用預設 schema")
        return _DEFAULT_SCHEMA

    try:
        data = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        mv = (data or {}).get("multi_view_status") or {}
        if not mv.get("allowed_values"):
            logger.info("schema 缺少 allowed_values，使用預設 schema")
            return _DEFAULT_SCHEMA
        return {
            "field_key": mv.get("field_key", "multi_view_status"),
            "allowed_values": mv.get("allowed_values", _DEFAULT_SCHEMA["allowed_values"]),
            "required_subfields": mv.get(
                "required_subfields", _DEFAULT_SCHEMA["required_subfields"]
            ),
        }
    except Exception as e:  # noqa: BLE001
        logger.info("讀取 ana-solution-schema.yaml 失敗（使用預設 schema）: %s", e)
        return _DEFAULT_SCHEMA


def _extract_solution_section(content: str) -> Optional[str]:
    """擷取 ## Solution 區段內容（到下一個 ## 或檔尾為止）。"""
    pattern = r"^## Solution\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        return None
    section = match.group(1)
    # 移除 HTML 註解（模板佔位符）
    section = re.sub(r"<!--.*?-->", "", section, flags=re.DOTALL)
    return section


def _parse_field(section: str, field_key: str) -> Optional[str]:
    """在 Solution 區段中尋找 `field_key: value` 行，回傳 value（小寫、trim）。"""
    pattern = rf"^\s*{re.escape(field_key)}\s*:\s*(.+?)\s*$"
    match = re.search(pattern, section, re.MULTILINE | re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip().strip("\"'`").lower()
    # 正規化 n/a、na → n_a
    if value in ("n/a", "na"):
        return "n_a"
    return value


def _has_subfield(section: str, subfield: str) -> bool:
    """檢查 Solution 區段是否含有非空的 subfield（`key: value` 格式）。

    reviewers 特殊處理：允許 `reviewers: [a, b]` 或多行 `- id` list。
    """
    pattern = rf"^\s*{re.escape(subfield)}\s*:\s*(.+?)\s*$"
    match = re.search(pattern, section, re.MULTILINE | re.IGNORECASE)
    if not match:
        return False
    value = match.group(1).strip().strip("\"'`")
    # 空字串、空 list、空括號視為無效
    if not value or value in ("[]", "{}", "-"):
        return False
    return True


def check_multi_view_status(
    content: str, frontmatter: dict, project_dir: Path, logger
) -> Tuple[bool, Optional[str]]:
    """檢查 ANA Ticket 的 Solution 是否含合法 multi_view_status 標註。

    Args:
        content: Ticket 檔案完整內容
        frontmatter: 已解析的 frontmatter dict
        project_dir: 專案根目錄（用於讀取 schema）
        logger: 日誌物件

    Returns:
        (should_warn, warning_message)
            - should_warn=False 代表通過（非 ANA 或標註完整）
            - should_warn=True 代表應輸出警告（阻塞由 orchestrator 決定）
    """
    ticket_type = (frontmatter.get("type") or "").strip().upper()
    if ticket_type != "ANA":
        logger.debug("非 ANA ticket（type=%s），跳過 multi_view_status 檢查", ticket_type)
        return False, None

    schema = load_schema(project_dir, logger)
    field_key: str = schema["field_key"]
    allowed_values: List[str] = [v.lower() for v in schema["allowed_values"]]
    required_subfields: dict = schema["required_subfields"]

    ticket_id = frontmatter.get("id", "未知")

    section = _extract_solution_section(content)
    if section is None or not section.strip():
        msg = _format_missing_warning(ticket_id, field_key, allowed_values)
        logger.info("ANA Ticket %s Solution 區段缺失或為空", ticket_id)
        return True, msg

    value = _parse_field(section, field_key)
    if value is None:
        msg = _format_missing_warning(ticket_id, field_key, allowed_values)
        logger.info("ANA Ticket %s Solution 缺少 %s 欄位", ticket_id, field_key)
        return True, msg

    if value not in allowed_values:
        msg = _format_invalid_value_warning(ticket_id, field_key, value, allowed_values)
        logger.info(
            "ANA Ticket %s %s 值非法: %s（合法值 %s）",
            ticket_id,
            field_key,
            value,
            allowed_values,
        )
        return True, msg

    # 驗證必填子欄位
    subs = required_subfields.get(value, [])
    missing = [s for s in subs if not _has_subfield(section, s)]
    if missing:
        msg = _format_missing_subfields_warning(ticket_id, field_key, value, missing)
        logger.info(
            "ANA Ticket %s %s=%s 缺少必填子欄位: %s",
            ticket_id,
            field_key,
            value,
            missing,
        )
        return True, msg

    logger.info("ANA Ticket %s multi_view_status=%s 檢查通過", ticket_id, value)
    return False, None


# ----------------------------------------------------------------------------
# 訊息格式化
# ----------------------------------------------------------------------------

def _format_missing_warning(ticket_id: str, field_key: str, allowed: List[str]) -> str:
    return (
        f"[WARNING] Acceptance Gate: ANA Ticket 缺少 {field_key} 標註\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"\n"
        f"ANA Ticket 的 Solution 區段必須顯式標註 {field_key}，"
        f"讓多視角審查成為設計階段的判定，而非事後補救。\n"
        f"\n"
        f"合法值：{', '.join(allowed)}\n"
        f"  - reviewed: 需附 reviewers（代理人 ID 清單）與 conclusion（結論摘要）\n"
        f"  - skipped:  需附 reason（跳過理由）\n"
        f"  - n_a:      需附 reason（判定不適用理由）\n"
        f"\n"
        f"Schema 來源：.claude/config/ana-solution-schema.yaml"
    )


def _format_invalid_value_warning(
    ticket_id: str, field_key: str, value: str, allowed: List[str]
) -> str:
    return (
        f"[WARNING] Acceptance Gate: ANA Ticket {field_key} 值非法\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"目前值: {value}\n"
        f"合法值: {', '.join(allowed)}\n"
        f"\n"
        f"Schema 來源：.claude/config/ana-solution-schema.yaml"
    )


def _format_missing_subfields_warning(
    ticket_id: str, field_key: str, value: str, missing: List[str]
) -> str:
    return (
        f"[WARNING] Acceptance Gate: ANA Ticket {field_key}={value} 缺少必填子欄位\n"
        f"\n"
        f"Ticket: {ticket_id}\n"
        f"缺少欄位: {', '.join(missing)}\n"
        f"\n"
        f"Schema 來源：.claude/config/ana-solution-schema.yaml"
    )
