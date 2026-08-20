"""ticket track fix-multi-view-status 子命令。

補救面：ANA Ticket Solution 區段的 `multi_view_status:` 行一旦寫入非法值
（非 reviewed / skipped / n_a），無合法途徑修正——append-log 僅能追加、
CLI 無編輯指令、該區段不在 ticket-file-access-guard-hook 白名單內故 Edit
工具被拒。三層疊加使非法值永久固定，且 acceptance-gate 僅警告不阻擋
complete。本命令提供唯一合法出路。

定位設計：鎖定該 ticket 的 `multi_view_status:` 這一行本身（欄位名固定，
非任意子字串比對）。命中 0 行或多行一律拒絕寫入。

寫入設計（原地覆寫，僅該行）：新值取代命中行的整行內容
（`multi_view_status: <value>`），前後其他行完全不變——與
add-exempt-marker 的「僅追加」語意相反，本命令是「僅覆寫單行」，因為
語意是修正既有錯誤值而非補充新內容。

防濫用結論：
1. 本命令只能覆寫 `multi_view_status:` 這一行的值，不能觸碰章節其他內容。
2. 新值必須屬 .claude/config/ana-solution-schema.yaml 定義的合法值域，
   reason 為必填（呼叫端須提供修正依據，供 commit 訊息與稽核追蹤），但
   reason 本身不寫入 ticket body——只覆寫欄位行，不擴大寫入面。
3. 命中 0 行或多行一律拒絕，避免誤改非目標行。
4. 沿用 append-log 系列既有的 status precondition（in_progress /
   completed 可寫，pending/blocked/closed 需 --force）與
   auto-commit（每次呼叫都有可追蹤的 git commit）。
"""
if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track fix-multi-view-status")
    sys.exit(1)


import argparse
import sys as _sys
from pathlib import Path

from ticket_system.lib.multi_view_status import (
    FIELD_LINE_PATTERN,
    build_field_line,
    validate_new_value,
    validate_reason,
)
from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.messages import (
    ErrorMessages,
    InfoMessages,
    format_error,
    format_info,
)
from ticket_system.lib.precondition import require_in_progress
from ticket_system.lib.section_locator import find_section
from ticket_system.lib.ticket_loader import get_ticket_path, load_ticket, save_ticket
from ticket_system.lib.ticket_ops import resolve_ticket_path

_OPERATION = "fix-multi-view-status"

_ERR_MESSAGE_MAP = {
    "value-whitelist": "新值不在合法值域（合法值：n_a, reviewed, skipped）",
    "reason-too-short": "reason 太短（< 10 字元）或未提供",
}


def execute_fix_multi_view_status(args: argparse.Namespace, version: str) -> int:
    """對指定 ticket 的 multi_view_status 行原地覆寫其值（file_lock 包圍
    load → 定位 → 驗證 → 寫入 → save，與 add-exempt-marker 同保護等級）。
    """
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        return _execute_fix_multi_view_status_locked(args, version)


def _execute_fix_multi_view_status_locked(args: argparse.Namespace, version: str) -> int:
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    force = bool(getattr(args, "force", False))
    status_ok, status_error = require_in_progress(
        ticket, args.ticket_id, _OPERATION,
        allow_completed=True, allow_pending=False, force=force,
    )
    if not status_ok:
        _sys.stderr.write(status_error + "\n")
        return 2

    section = getattr(args, "section", None) or "Solution"

    new_value = args.value
    valid, err_code = validate_new_value(new_value)
    if not valid:
        print(f"[Error] multi_view_status 驗證失敗：{_ERR_MESSAGE_MAP[err_code]}")
        return 1

    reason = args.reason
    valid, err_code = validate_reason(reason)
    if not valid:
        print(f"[Error] multi_view_status 驗證失敗：{_ERR_MESSAGE_MAP[err_code]}")
        return 1

    body = ticket.get("_body", "")
    if not body:
        print(format_error(ErrorMessages.BODY_CONTENT_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    match = find_section(body, section)
    if match is None or not match.found:
        print(format_error(ErrorMessages.SECTION_NOT_FOUND, ticket_id=args.ticket_id, section=section))
        return 1

    hits = list(FIELD_LINE_PATTERN.finditer(match.content))

    if not hits:
        print(
            f"[Error] {args.ticket_id} 的 '{section}' 章節找不到 multi_view_status 行，未寫入"
        )
        return 1

    # 多重命中時（如既有非法值行 + 事後 append-log 補正的合法值行並存），
    # 允許用 --match 子字串收窄至單一行，語意同 add-exempt-marker 的 --match。
    match_text = getattr(args, "match_text", None)
    if match_text and len(hits) > 1:
        hits = [h for h in hits if match_text in h.group()]

    if not hits:
        print(
            f"[Error] {args.ticket_id} 的 '{section}' 章節找不到含「{match_text}」的 "
            "multi_view_status 行，未寫入"
        )
        return 1

    if len(hits) > 1:
        print(
            f"[Error] {args.ticket_id} 的 '{section}' 章節有 {len(hits)} 行 multi_view_status，"
            "定位不明確，未寫入。候選行："
        )
        for hit in hits:
            snippet = hit.group().strip()
            print(f"   - {snippet[:120]}")
        return 1

    hit = hits[0]
    indent = hit.group(1) or ""
    new_line = build_field_line(indent, new_value)
    # 僅取代命中行本身的整段範圍；命中行前後的原文字逐字元不變（未被讀寫觸碰）。
    new_content = match.content[: hit.start()] + new_line + match.content[hit.end():]
    new_body = body[: match.content_start] + new_content + body[match.end:]

    try:
        from ticket_system.lib.ticket_builder import dedupe_schema_sections
        new_body = dedupe_schema_sections(new_body)
    except Exception as exc:
        _sys.stderr.write(f"[{_OPERATION}] dedupe_schema_sections skipped: {exc}\n")

    ticket["_body"] = new_body
    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    save_ticket(ticket, ticket_path)

    from ticket_system.lib import git_utils
    try:
        commit_status = git_utils._auto_commit_ticket_md(
            str(ticket_path), args.ticket_id, section, operation=_OPERATION
        )
        if commit_status in ("not_git_repo", "git_failed"):
            _sys.stderr.write(
                f"[{_OPERATION}] auto-commit skipped（{commit_status}，非致命）；"
                "body 已保留 working tree，可手動 git commit 持久化。\n"
            )
    except Exception as exc:
        _sys.stderr.write(
            f"[{_OPERATION}] auto-commit 失敗（非致命，body 已保留 working tree）：{exc}\n"
        )

    print(format_info(
        InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name="multi_view_status"
    ))
    print(f"   已覆寫為: {new_line.strip()}")
    print(f"   理由（未寫入 body，僅供稽核）: {reason}")

    try:
        with open(ticket_path, "r", encoding="utf-8") as _vf:
            line_count = sum(1 for _ in _vf)
        print(f"[verify] ticket md: {line_count} lines after write")
    except OSError:
        pass

    return 0
