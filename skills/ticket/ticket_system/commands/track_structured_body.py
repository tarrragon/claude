"""
ticket track set-exit-status / set-completion-info 子命令

Exit Status 和 Completion Info 章節有確定性 schema，過去由 agent 自由撰寫再靠
hook 事後檢查格式，格式錯誤率中（1.5.0-W5-020 ANA 結論）。依制式化內容生成
方法論（.claude/methodologies/structured-content-generation-methodology.md），
本模組將格式結構收斂到 CLI：agent 只提供語意值，CLI 負責產生正確的
Markdown / YAML 結構並寫入 ticket body。

實作策略：組出符合 schema 的內容字串後，委派給既有 `execute_append_log`
（`track_acceptance.py`）完成實際寫入（file_lock / precondition / placeholder
替換 / dedupe / auto-commit 皆沿用同一套邏輯，避免重複實作）。
"""

if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track set-exit-status / set-completion-info")
    sys.exit(1)


import argparse
from datetime import datetime

from ticket_system.lib.messages import ErrorMessages, format_error

# Exit Status 合法枚舉（W17-010 schema）
VALID_EXIT_STATUSES = ("success", "needs_context", "blocked", "partial_success", "failed")
# Completion Info review-status 合法枚舉
VALID_REVIEW_STATUSES = ("pending", "reviewed", "n/a")


def _yaml_list_literal(values: list[str] | None) -> str:
    """將字串清單轉為 YAML flow-style 清單字面值（如 `[1, 2]` 或 `[]`）。"""
    if not values:
        return "[]"
    return "[" + ", ".join(values) + "]"


def _build_exit_status_content(args: argparse.Namespace) -> str:
    """依語意值組出 Exit Status fenced YAML 區塊內容。"""
    acceptance_met = _yaml_list_literal(getattr(args, "acceptance_met", None))
    acceptance_unmet = _yaml_list_literal(getattr(args, "acceptance_unmet", None))
    artifacts_raw = getattr(args, "artifacts", None) or []
    artifacts = _yaml_list_literal([f'"{a}"' for a in artifacts_raw])
    reason = (getattr(args, "reason", None) or "").replace('"', '\\"')

    return (
        "```yaml\n"
        f"exit_status: {args.status}\n"
        f'reason: "{reason}"\n'
        f"confidence: {args.confidence}\n"
        f"acceptance_met: {acceptance_met}\n"
        f"acceptance_unmet: {acceptance_unmet}\n"
        f"artifacts: {artifacts}\n"
        "```"
    )


def _build_completion_info_content(args: argparse.Namespace) -> str:
    """依語意值組出 Completion Info Markdown 內容。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"**Completion Time**: {timestamp}\n"
        f"**Executing Agent**: {args.agent}\n"
        f"**Review Status**: {getattr(args, 'review_status', 'pending')}\n"
        f"**Summary**: {getattr(args, 'summary', '') or ''}"
    )


def _delegate_to_append_log(
    args: argparse.Namespace, version: str, section: str, content: str
) -> int:
    """組出 append-log 相容的 args 並委派給 execute_append_log。"""
    from ticket_system.commands.track_acceptance import execute_append_log

    append_args = argparse.Namespace(
        ticket_id=args.ticket_id,
        section=section,
        content=content,
        version=version,
        force=bool(getattr(args, "force", False)),
    )
    return execute_append_log(append_args, version)


def execute_set_exit_status(args: argparse.Namespace, version: str) -> int:
    """執行 set-exit-status 命令：CLI 生成 Exit Status fenced YAML 區塊。"""
    if args.status not in VALID_EXIT_STATUSES:
        print(format_error(ErrorMessages.INVALID_SECTION, section=args.status))
        print(f"   有效值: {', '.join(VALID_EXIT_STATUSES)}")
        return 1

    try:
        confidence = float(args.confidence)
    except (TypeError, ValueError):
        print(f"[ERROR] --confidence 必須為 0.0-1.0 之間的數字：'{args.confidence}'")
        return 1
    if not (0.0 <= confidence <= 1.0):
        print(f"[ERROR] --confidence 超出範圍（0.0-1.0）：{confidence}")
        return 1
    args.confidence = confidence

    content = _build_exit_status_content(args)
    result = _delegate_to_append_log(args, version, "Exit Status", content)
    if result == 0:
        print(f"[INFO] {args.ticket_id} Exit Status 已設定：status={args.status}")
    return result


def execute_set_completion_info(args: argparse.Namespace, version: str) -> int:
    """執行 set-completion-info 命令：CLI 生成 Completion Info 區塊。"""
    review_status = getattr(args, "review_status", "pending")
    if review_status not in VALID_REVIEW_STATUSES:
        print(format_error(ErrorMessages.INVALID_SECTION, section=review_status))
        print(f"   有效值: {', '.join(VALID_REVIEW_STATUSES)}")
        return 1

    content = _build_completion_info_content(args)
    result = _delegate_to_append_log(args, version, "Completion Info", content)
    if result == 0:
        print(f"[INFO] {args.ticket_id} Completion Info 已設定：agent={args.agent}")
    return result
