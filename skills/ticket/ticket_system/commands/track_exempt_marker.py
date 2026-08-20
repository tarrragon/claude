"""ticket track add-exempt-marker 子命令。

補救面：自由撰寫章節（Solution / Test Results / NeedsContext 等）以
append-log 寫入後即無法修改——append-log 僅能追加、CLI 無編輯指令、該
區段不在 ticket-file-access-guard-hook 白名單內故 Edit 工具被拒。三層
疊加使 PC-093-exempt 這類行級標記完全無法事後補上，唯一出路是本命令。

定位設計：--match 為既有行內的文字子字串（非行號——行號隨後續編輯漂移，
文字比對可驗證且不受插入位置影響）。命中 0 行或多行一律拒絕寫入，要求
使用者提供更精確的 --match 收窄至單一行，避免誤標到非目標行。

寫入設計（僅追加，不修改原文字）：marker 一律以獨立新行插入於命中行的
「前一行」，never 附加到命中行本身或改動其字元——與
phase4-decision-enforcement-hook 的豁免距離規則（marker 在 phrase 同行或
前 1 行內生效，DIST-2）一致，同時保證原文字逐字元不變，可用單元測試
直接斷言。

防濫用結論：
1. 本命令不是通用文字插入工具——它只能指向 ticket body 內既有的行，不能
   憑空產生新內容；能寫入的唯一產出是格式受驗證的 marker 行本身。
2. marker 是否真正產生豁免效果，最終仍由 phase4-decision-enforcement-hook
   在 `ticket track phase <id> phase4` 與 `ticket track complete <id>` 時
   重新掃描整份 body 判定——本命令的寫入路徑不繞過、不停用該 hook，
   只是提供一個「把格式合法的 marker 放進去」的合法管道。若 hook 判定
   該行根本不是延後話術命中（無 Hit），marker 存在與否對結果無影響
   （`is_hit_exempted` 只對有 Hit 的行生效）；若命中且 marker 格式不合法
   ，hook 仍會擋下——本命令的 fail-fast 驗證與 hook 的權威驗證使用同一套
   規則，不會讓不合格的 marker 蒙混過關。
3. 每次呼叫只能標記一行、只能提供呼叫者自行輸入的 reason，沒有 --all /
   --scan-all 之類的批次或萬用字元入口，杜絕一次性大量灌入豁免標記。
4. 寫入沿用 append-log 系列既有的 status precondition（僅 in_progress /
   completed 可寫，pending/blocked/closed 需 --force 且記入 hook-logs）與
   auto-commit（每次呼叫都有可追蹤的 git commit），與其他 body 操作同等
   審計強度，不是獨立於既有治理之外的捷徑。
"""
if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track add-exempt-marker")
    sys.exit(1)


import argparse
import re
import sys as _sys
from pathlib import Path

from ticket_system.lib.exempt_marker import (
    ERR_MESSAGE_MAP,
    build_marker_line,
    resolve_ticket_id_pattern,
    validate_exempt_fields,
)
from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.messages import (
    ErrorMessages,
    InfoMessages,
    format_error,
    format_info,
)
from ticket_system.lib.command_tracking_messages import TrackAcceptanceMessages
from ticket_system.lib.precondition import require_in_progress
from ticket_system.lib.section_locator import find_section
from ticket_system.lib.ticket_loader import get_ticket_path, load_ticket, save_ticket
from ticket_system.lib.ticket_ops import resolve_ticket_path

_OPERATION = "add-exempt-marker"


def execute_add_exempt_marker(args: argparse.Namespace, version: str) -> int:
    """對指定章節既有行補上 PC-093-exempt marker（file_lock 包圍 load → 定位 →
    驗證 → 寫入 → save，與 append-log / resolve-spawn-request 同保護等級）。
    """
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        return _execute_add_exempt_marker_locked(args, version)


def _execute_add_exempt_marker_locked(args: argparse.Namespace, version: str) -> int:
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

    section = args.section
    if section not in TrackAcceptanceMessages.VALID_SECTIONS:
        print(format_error(ErrorMessages.INVALID_SECTION, section=section))
        print(
            f"{TrackAcceptanceMessages.VALID_VALUES_PREFIX} "
            f"{', '.join(TrackAcceptanceMessages.VALID_SECTIONS)}"
        )
        return 1

    category = args.category
    reason = args.reason
    valid, err_code = validate_exempt_fields(
        category, reason, ticket_id_pattern=resolve_ticket_id_pattern()
    )
    if not valid:
        # 直接組字串（不經 format_error）：ERR_MESSAGE_MAP 訊息含字面
        # "W{wave}-{seq}" illustration，經 format_error 的 str.format()
        # 路徑會被誤判為待代入欄位而拋 KeyError。
        print(f"[Error] Exempt marker 驗證失敗：{ERR_MESSAGE_MAP[err_code]}")
        return 1

    match_text = args.match_text
    if not match_text:
        print(format_error("[Error] --match 不可為空"))
        return 1

    body = ticket.get("_body", "")
    if not body:
        print(format_error(ErrorMessages.BODY_CONTENT_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    match = find_section(body, section)
    if match is None or not match.found:
        print(format_error(ErrorMessages.SECTION_NOT_FOUND, ticket_id=args.ticket_id, section=section))
        return 1

    # 逐行搜尋 --match 子字串（非 regex 語意，re.escape 避免特殊字元誤判）；
    # `^.*...*$` + MULTILINE 取得整行範圍，供插入點定位。
    line_pattern = re.compile(r"^.*" + re.escape(match_text) + r".*$", re.MULTILINE)
    hits = list(line_pattern.finditer(match.content))

    # 下兩則錯誤訊息含使用者提供的 match_text，不經 format_error()——後者對
    # str 走 .format(**kwargs) 路徑，match_text 若含字面「{」會被誤判為待
    # 代入欄位而拋 KeyError（同上方 marker 驗證訊息的理由）。
    if not hits:
        print(
            f"[Error] {args.ticket_id} 的 '{section}' 章節找不到含「{match_text}」的行，未寫入"
        )
        return 1

    if len(hits) > 1:
        print(
            f"[Error] {args.ticket_id} 的 '{section}' 章節有 {len(hits)} 行含「{match_text}」，"
            "定位不明確，未寫入。請提供更精確的 --match 收窄至單一行，候選行："
        )
        for hit in hits:
            snippet = hit.group().strip()
            print(f"   - {snippet[:120]}")
        return 1

    hit = hits[0]
    marker_line = build_marker_line(category, reason)
    # 僅在命中行前插入獨立新行；match.content[hit.start():] 起的原文字
    # 逐字元不變（只被整體平移，未被讀寫觸碰）。
    new_content = match.content[: hit.start()] + marker_line + "\n" + match.content[hit.start():]
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
        InfoMessages.FIELD_UPDATED, ticket_id=args.ticket_id, field_name=f"'{section}' exempt marker"
    ))
    print(f"   已插入: {marker_line}")

    try:
        with open(ticket_path, "r", encoding="utf-8") as _vf:
            line_count = sum(1 for _ in _vf)
        print(f"[verify] ticket md: {line_count} lines after write")
    except OSError:
        pass

    return 0
