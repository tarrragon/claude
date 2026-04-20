"""Ticket Frontmatter 合規驗證器（共用模組）

驗證 Ticket YAML frontmatter 4 個欄位：
- status: enum ∈ {pending, in_progress, completed, blocked, closed}
- completed_at: ISO 8601 `YYYY-MM-DDTHH:MM:SS`（或 null）；HH ∈ [00, 23]
- acceptance: YAML list，每項為獨立字串，不含 `,[ ]` 或 `,[x]` 合併分隔
- who: 必為 object 含 `current` 欄位（非 plain string）

使用者：
- .claude/hooks/ticket-frontmatter-validator-hook.py (PostToolUse 事後警告)
- ticket_system CLI 子命令 (W14-030+)

設計原則：
- Pure function：不依賴 logger / 檔案 I/O / 外部狀態
- 純驗證：回傳 `ValidationIssue` 清單，由呼叫端決定如何呈現（stderr / 日誌 / CLI 回饋）
- Python 3.9 相容（Hook 環境限制）
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ============================================================================
# 常數
# ============================================================================

VALID_STATUS_ENUM = {"pending", "in_progress", "completed", "blocked", "closed"}

# ISO 8601 `YYYY-MM-DDTHH:MM:SS`（允許小數秒、Z 或 +HH:MM 時區）
# HH 必須 ∈ [00, 23]；排除 T24:00:00 等無效值
_ISO_8601_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)

# 合併單行 acceptance 偵測：單一字串含兩個以上 `[x]` 或 `[ ]` checkbox
# 範例違規：'[x] A,[ ] B' 或 '[x] A [ ] B'（以逗號或空格分隔）
_MULTI_CHECKBOX_IN_ONE_LINE = re.compile(r"\[[ xX]\].*?\[[ xX]\]")


# ============================================================================
# 結果結構
# ============================================================================

@dataclass
class ValidationIssue:
    """單一違規項目。

    Attributes:
        field: 違規欄位名稱（status / completed_at / acceptance / who）
        severity: 嚴重程度（error / warning）——目前統一 warning（事後提醒不阻擋）
        detail: 人類可讀的違規描述
        suggestion: 修復建議（可選）
    """
    field: str
    severity: str
    detail: str
    suggestion: Optional[str] = None

    def format_line(self) -> str:
        """格式化為單行警告訊息（供 stderr 輸出）。"""
        base = f"{self.field}: {self.detail}"
        if self.suggestion:
            base += f"\n    建議: {self.suggestion}"
        return base


# ============================================================================
# 個別欄位驗證
# ============================================================================

def validate_status(value: Any) -> List[ValidationIssue]:
    """驗證 status 欄位。"""
    issues: List[ValidationIssue] = []
    if value is None:
        # status 缺失不在本驗證範圍（其他 hook 處理），放行
        return issues
    if not isinstance(value, str):
        issues.append(ValidationIssue(
            field="status",
            severity="warning",
            detail=f"非字串型別 (got {type(value).__name__})",
            suggestion=f"使用字串值，可選: {sorted(VALID_STATUS_ENUM)}",
        ))
        return issues
    if value not in VALID_STATUS_ENUM:
        issues.append(ValidationIssue(
            field="status",
            severity="warning",
            detail=f"值 '{value}' 不在合法 enum",
            suggestion=f"合法值: {sorted(VALID_STATUS_ENUM)}（常見錯誤: 'complete' 應為 'completed'）",
        ))
    return issues


def validate_completed_at(value: Any) -> List[ValidationIssue]:
    """驗證 completed_at 欄位。"""
    issues: List[ValidationIssue] = []
    if value is None:
        return issues  # null 合規
    if not isinstance(value, str):
        issues.append(ValidationIssue(
            field="completed_at",
            severity="warning",
            detail=f"非字串型別 (got {type(value).__name__})",
            suggestion="使用 ISO 8601 字串 'YYYY-MM-DDTHH:MM:SS' 或 null",
        ))
        return issues

    match = _ISO_8601_PATTERN.match(value)
    if not match:
        issues.append(ValidationIssue(
            field="completed_at",
            severity="warning",
            detail=f"非 ISO 8601 格式: '{value}'",
            suggestion="格式 'YYYY-MM-DDTHH:MM:SS'（範例: '2026-04-18T10:30:00'）",
        ))
        return issues

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    second = int(match.group("second"))
    if not (0 <= hour <= 23):
        issues.append(ValidationIssue(
            field="completed_at",
            severity="warning",
            detail=f"小時值無效: {hour:02d}（合法範圍 00-23）",
            suggestion="T24:00:00 非法，隔日凌晨請用 'YYYY-MM-DDT00:00:00'",
        ))
    if not (0 <= minute <= 59):
        issues.append(ValidationIssue(
            field="completed_at",
            severity="warning",
            detail=f"分鐘值無效: {minute:02d}（合法範圍 00-59）",
        ))
    if not (0 <= second <= 59):
        issues.append(ValidationIssue(
            field="completed_at",
            severity="warning",
            detail=f"秒數值無效: {second:02d}（合法範圍 00-59）",
        ))
    return issues


def validate_acceptance(value: Any) -> List[ValidationIssue]:
    """驗證 acceptance 欄位（必須為 list，每項為獨立 AC 字串）。"""
    issues: List[ValidationIssue] = []
    if value is None:
        return issues
    if not isinstance(value, list):
        issues.append(ValidationIssue(
            field="acceptance",
            severity="warning",
            detail=f"非 list 型別 (got {type(value).__name__})",
            suggestion="使用 YAML list 語法，每條 AC 一個 `- '[ ] ...'` 項目",
        ))
        return issues

    for idx, item in enumerate(value):
        if not isinstance(item, str):
            issues.append(ValidationIssue(
                field="acceptance",
                severity="warning",
                detail=f"第 {idx + 1} 項非字串 (got {type(item).__name__})",
            ))
            continue
        if _MULTI_CHECKBOX_IN_ONE_LINE.search(item):
            issues.append(ValidationIssue(
                field="acceptance",
                severity="warning",
                detail=f"第 {idx + 1} 項含多個 checkbox 合併於單行: {item[:60]}...",
                suggestion="拆分為獨立 list items；可用 CLI: ticket track check-acceptance <id> --all",
            ))
    return issues


def validate_who(value: Any) -> List[ValidationIssue]:
    """驗證 who 欄位（必須為 object 含 current 欄位，非 plain string）。"""
    issues: List[ValidationIssue] = []
    if value is None:
        return issues
    if isinstance(value, str):
        issues.append(ValidationIssue(
            field="who",
            severity="warning",
            detail=f"plain string 形式 '{value}'（應為 object）",
            suggestion="改為 object: who:\\n  current: <agent>\\n  history: {}",
        ))
        return issues
    if not isinstance(value, dict):
        issues.append(ValidationIssue(
            field="who",
            severity="warning",
            detail=f"非 object 型別 (got {type(value).__name__})",
            suggestion="使用 object 形式含 current 欄位",
        ))
        return issues
    if "current" not in value:
        issues.append(ValidationIssue(
            field="who",
            severity="warning",
            detail="object 缺少 'current' 欄位",
            suggestion="新增 current: <agent-name>",
        ))
    return issues


# ============================================================================
# 主入口
# ============================================================================

def validate_frontmatter(frontmatter: Dict[str, Any]) -> List[ValidationIssue]:
    """驗證 ticket frontmatter 的 4 個目標欄位。

    Args:
        frontmatter: 已解析的 YAML frontmatter dict

    Returns:
        ValidationIssue 清單（空清單代表合規）
    """
    if not isinstance(frontmatter, dict):
        return [ValidationIssue(
            field="<root>",
            severity="warning",
            detail=f"frontmatter 非 dict (got {type(frontmatter).__name__})",
        )]

    issues: List[ValidationIssue] = []
    issues.extend(validate_status(frontmatter.get("status")))
    issues.extend(validate_completed_at(frontmatter.get("completed_at")))
    issues.extend(validate_acceptance(frontmatter.get("acceptance")))
    issues.extend(validate_who(frontmatter.get("who")))
    return issues
