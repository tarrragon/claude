"""
ticket track validate 子命令

驗證 Ticket frontmatter 的 4 個關鍵欄位合規性，
回傳合規/違規清單與建議修復命令。

驗證行為委派至共用模組 `ticket_system.validators.frontmatter_validator`
（與 PostToolUse hook 共用同一份規則，確保 CLI 與 hook 行為一致）。

追蹤欄位：status, completed_at, acceptance, who
"""

if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track validate")
    sys.exit(1)


import argparse

from ticket_system.lib.ticket_loader import load_ticket
from ticket_system.lib.messages import (
    ErrorMessages,
    format_error,
)
from ticket_system.validators.frontmatter_validator import (
    ValidationIssue,
    validate_frontmatter as _shared_validate_frontmatter,
)


# ============================================================
# 追蹤欄位（與 hook 一致：status / completed_at / acceptance / who）
# ============================================================

_TRACKED_FIELDS: tuple[str, ...] = ("status", "completed_at", "acceptance", "who")


def validate_frontmatter(ticket: dict) -> tuple[list[str], list[tuple[str, str]]]:
    """驗證 Ticket frontmatter 4 欄位（CLI adapter）。

    委派至共用 validator，再把 ValidationIssue 清單適配為
    `(合規欄位, [(違規欄位, 訊息), ...])` 的 CLI 呈現格式。
    """
    issues: list[ValidationIssue] = _shared_validate_frontmatter(ticket)

    violated_fields: set[str] = set()
    violations: list[tuple[str, str]] = []
    for issue in issues:
        if issue.field in _TRACKED_FIELDS:
            violations.append((issue.field, issue.detail))
            violated_fields.add(issue.field)

    ok_fields = [f for f in _TRACKED_FIELDS if f not in violated_fields]
    return ok_fields, violations


# ============================================================
# 建議修復命令
# ============================================================

_FIX_SUGGESTIONS: dict[str, str] = {
    "status": "ticket track claim <id> / ticket track complete <id> / ticket track release <id>",
    "completed_at": "由 ticket track complete <id> 自動設定（勿手工編輯）",
    "acceptance": (
        "ticket track add-acceptance <id> '<text>'\n"
        "    ticket track remove-acceptance <id> <index>\n"
        "    ticket track set-acceptance <id> --check <index>"
    ),
    "who": "ticket track claim <id>（自動設定 current/history）",
}


def _suggest_fix(field_name: str) -> str:
    return _FIX_SUGGESTIONS.get(field_name, "（無建議，請對照 frontmatter 格式手工修復）")


# ============================================================
# CLI entry
# ============================================================

def execute_validate(args: argparse.Namespace, version: str) -> int:
    """執行 validate 命令。"""
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    ok_fields, violations = validate_frontmatter(ticket)

    print(f"[VALIDATE] {args.ticket_id}")
    print(f"  合規欄位 ({len(ok_fields)}/4)：{', '.join(ok_fields) if ok_fields else '（無）'}")

    if not violations:
        print("  狀態：全部合規")
        return 0

    print(f"  違規欄位 ({len(violations)}/4)：")
    for field_name, msg in violations:
        print(f"    - {field_name}: {msg}")
        print(f"      建議修復：{_suggest_fix(field_name)}")
    return 1
