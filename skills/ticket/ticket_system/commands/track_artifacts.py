"""
ticket track register-artifact / resolve-artifact / list-artifacts 子命令

實驗器材（為觀測而放置於工作區、其存在本身即為觀測手段的檔案）的票面登記
CLI 化。依制式化內容生成方法論（structured-content-generation-methodology）：
規範原僅要求「於 Solution 章節登記路徑/用途/存活期」，格式由撰寫者自由發揮，
收尾者需人工掃描章節才能取得清單。本模組把結構收斂到 CLI——撰寫者只提供
語意值，CLI 產生固定格式的登記項與可複製的首行 header 文字。

完整規範見 `.claude/pm-rules/parallel-dispatch.md`「跨 session 實驗器材的
自我標示與存活期治理（強制）」；本模組只承載條件三（票面登記）與首行
header 文字生成，不承載條件一的檔名前綴（撰寫者自行命名）與存活期治理的
collect-time 強制掃描（該檢查點在 complete acceptance-gate hook，不在
ticket_system/ 範圍內）。

登記位置固定為 Solution 章節內的 `### 實驗器材登記` 子章節（而非新增
CANONICAL_BODY_SECTIONS 頂層章節）：規範原文明訂登記位置為 Solution，
沿用可避免變更 body 章節正典（影響全域 schema 驗證與既有測試），且子章節
內的固定格式（EXP-N 條目，仿 Spawn Requests 的 SR-N 模式）已足以支撐
`list-artifacts` 程式化讀取，不需人工掃描。
"""
if __name__ == "__main__":
    import sys
    print("[ERROR] 此檔案不支援直接執行，請使用 ticket track register-artifact")
    sys.exit(1)


import argparse
import re
import sys as _sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.ticket_loader import get_ticket_path, load_ticket, save_ticket
from ticket_system.lib.messages import ErrorMessages, InfoMessages, format_error, format_info
from ticket_system.lib.precondition import require_in_progress
from ticket_system.lib.ticket_ops import resolve_ticket_path
from ticket_system.lib.section_locator import find_section

SOLUTION_SECTION = "Solution"
ARTIFACT_SUBHEADING = "### 實驗器材登記"
VALID_ARTIFACT_TYPES = ("明示", "盲測")
VALID_RESOLVE_STATUSES = ("removed", "kept")

# 首行 header 範本（逐字對齊 parallel-dispatch.md 條件一），{purpose} 由呼叫端代入
_HEADER_TEMPLATE = (
    "本檔為 {ticket_id} 的實驗器材（{purpose}）。"
    "請勿刪除、勿 git add、勿加入 .gitignore；由該票收尾時移除。"
)

_ENTRY_PATTERN_TEMPLATE = r"(^- \*\*{label}\*\*.*?)(?=^- \*\*EXP-\d+\*\*|\Z)"


def build_artifact_header(ticket_id: str, purpose: str) -> str:
    """組出可直接複製的首行 header 文字（純函式，供測試與 CLI 共用）。"""
    return _HEADER_TEMPLATE.format(ticket_id=ticket_id, purpose=purpose)


def _find_artifact_subsection(solution_content: str):
    """在 Solution 章節內容中定位 `### 實驗器材登記` 子章節。

    回傳 (found, start, end, content) tuple：
    - found=False 時 start/end/content 為 0/0/""，呼叫端須新建子章節。
    - 邊界以下一個 `### ` 子標題或 Solution 章節結尾為終點——不使用
      find_section() 的 (2,3) 雙層級模式，因為該模式邊界統一以 H2 為終止，
      無法區分同層級的多個 H3 子章節（會把後續其他 ### 小節一併吃入）。
    """
    pattern = re.compile(
        rf"^{re.escape(ARTIFACT_SUBHEADING)}\s*$\n(.*?)(?=^### |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(solution_content)
    if m is None:
        return False, 0, 0, ""
    return True, m.start(), m.end(), m.group(1)


def _next_exp_label(body: str) -> str:
    """自動編號：掃描既有 body 中 EXP-\\d+ 最大值 +1（與 SR-N 同模式）。"""
    existing_ids = [int(n) for n in re.findall(r"EXP-(\d+)", body)]
    next_id = max(existing_ids, default=0) + 1
    return f"EXP-{next_id}"


def execute_register_artifact(args: argparse.Namespace, version: str) -> int:
    """結構化登記實驗器材至 Solution 章節的「實驗器材登記」子章節。"""
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        return _execute_register_artifact_locked(args, version)


def _execute_register_artifact_locked(args: argparse.Namespace, version: str) -> int:
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    force = bool(getattr(args, "force", False))
    status_ok, status_error = require_in_progress(
        ticket, args.ticket_id, "register-artifact",
        allow_completed=True, allow_pending=False, force=force,
    )
    if not status_ok:
        _sys.stderr.write(status_error + "\n")
        return 2

    artifact_type = args.type or "明示"
    if artifact_type not in VALID_ARTIFACT_TYPES:
        print(format_error(f"[Error] --type 須為 {'/'.join(VALID_ARTIFACT_TYPES)}，收到：{artifact_type}"))
        return 1

    body = ticket.get("_body", "")
    if not body:
        print(format_error(ErrorMessages.BODY_CONTENT_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    match = find_section(body, SOLUTION_SECTION)
    if match is None or not match.found:
        print(format_error(ErrorMessages.SECTION_NOT_FOUND, ticket_id=args.ticket_id, section=SOLUTION_SECTION))
        return 1

    label = _next_exp_label(body)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n- **{label}** ({timestamp})\n"
        f"  - path: {args.path}\n"
        f"  - purpose: {args.purpose}\n"
        f"  - expiry: {args.expiry}\n"
        f"  - type: {artifact_type}\n"
        f"  - status: active\n"
    )

    found, sub_start, sub_end, _sub_content = _find_artifact_subsection(match.content)
    if found:
        new_content = (
            match.content[:sub_end] + entry + match.content[sub_end:]
        )
    else:
        # 子章節不存在：附加到 Solution 內容末尾（保留既有內容不動）
        separator = "" if match.content.endswith("\n\n") else (
            "\n" if match.content.endswith("\n") else "\n\n"
        )
        new_content = match.content + separator + ARTIFACT_SUBHEADING + "\n" + entry

    new_body = body[: match.content_start] + new_content + body[match.end :]

    try:
        from ticket_system.lib.ticket_builder import dedupe_schema_sections
        new_body = dedupe_schema_sections(new_body)
    except Exception as exc:
        _sys.stderr.write(f"[register-artifact] dedupe_schema_sections skipped: {exc}\n")

    ticket["_body"] = new_body
    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    save_ticket(ticket, ticket_path)

    from ticket_system.lib import git_utils
    try:
        commit_status = git_utils._auto_commit_ticket_md(
            str(ticket_path), args.ticket_id, SOLUTION_SECTION, operation="register-artifact"
        )
        if commit_status in ("not_git_repo", "git_failed"):
            _sys.stderr.write(
                f"[register-artifact] auto-commit skipped（{commit_status}，非致命）；"
                f"body 已保留 working tree，可手動 git commit 持久化。\n"
            )
    except Exception as exc:
        _sys.stderr.write(f"[register-artifact] auto-commit 失敗（非致命）：{exc}\n")

    print(format_info(InfoMessages.LOG_APPENDED, ticket_id=args.ticket_id, section=SOLUTION_SECTION))
    print(f"   編號: {label}")
    print(f"   path: {args.path}")
    print()
    print("複製以下文字為器材檔案首行 header：")
    print(f"  {build_artifact_header(args.ticket_id, args.purpose)}")

    try:
        with open(ticket_path, "r", encoding="utf-8") as _vf:
            line_count = sum(1 for _ in _vf)
        print(f"[verify] ticket md: {line_count} lines after write")
    except OSError:
        pass

    return 0


def _build_artifact_status_value(status: str, reason: Optional[str], successor: Optional[str]) -> str:
    """組出 status 行新值。kept 須有 successor（規範強制「未指名接手者視為漏處置」，
    此處在寫入端即擋下，不讓不合規登記進入 body）。"""
    if status == "kept":
        note = f"接手：{successor}"
        if reason:
            note = f"{reason}，{note}"
        return f"kept（{note}）"
    if reason:
        return f"removed（{reason}）"
    return "removed"


def execute_resolve_artifact(args: argparse.Namespace, version: str) -> int:
    """標記指定實驗器材（EXP-N）狀態為 removed 或 kept。"""
    lock_target = Path(get_ticket_path(version, args.ticket_id))
    with file_lock(lock_target):
        return _execute_resolve_artifact_locked(args, version)


def _execute_resolve_artifact_locked(args: argparse.Namespace, version: str) -> int:
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    force = bool(getattr(args, "force", False))
    status_ok, status_error = require_in_progress(
        ticket, args.ticket_id, "resolve-artifact",
        allow_completed=True, allow_pending=False, force=force,
    )
    if not status_ok:
        _sys.stderr.write(status_error + "\n")
        return 2

    if args.status == "kept" and not args.successor:
        print(format_error(
            "[Error] --status kept 必須帶 --successor（規範：未指名接手者視為漏處置）"
        ))
        return 1

    body = ticket.get("_body", "")
    if not body:
        print(format_error(ErrorMessages.BODY_CONTENT_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    match = find_section(body, SOLUTION_SECTION)
    if match is None or not match.found:
        print(format_error(ErrorMessages.SECTION_NOT_FOUND, ticket_id=args.ticket_id, section=SOLUTION_SECTION))
        return 1

    found, sub_start, sub_end, sub_content = _find_artifact_subsection(match.content)
    if not found:
        print(format_error(
            f"[Error] {args.ticket_id} 的 Solution 章節找不到「{ARTIFACT_SUBHEADING}」子章節"
        ))
        return 1

    label = args.exp_label
    entry_pattern = re.compile(
        _ENTRY_PATTERN_TEMPLATE.format(label=re.escape(label)),
        re.MULTILINE | re.DOTALL,
    )
    entry_match = entry_pattern.search(sub_content)
    if entry_match is None:
        print(format_error(f"[Error] {args.ticket_id} 的實驗器材登記找不到 {label}"))
        return 1

    entry_text = entry_match.group(1)
    status_line_pattern = re.compile(r"^(\s*-\s*status:\s*).*$", re.MULTILINE)
    if not status_line_pattern.search(entry_text):
        print(format_error(f"[Error] {label} 條目缺少 status 行，格式無法辨識（未修改）"))
        return 1

    new_value = _build_artifact_status_value(args.status, args.reason, args.successor)
    new_entry_text = status_line_pattern.sub(
        lambda m: m.group(1) + new_value, entry_text, count=1
    )
    new_sub_content = (
        sub_content[: entry_match.start()] + new_entry_text + sub_content[entry_match.end() :]
    )
    new_solution_content = (
        match.content[:sub_start] + ARTIFACT_SUBHEADING + "\n" + new_sub_content + match.content[sub_end:]
    )
    new_body = body[: match.content_start] + new_solution_content + body[match.end :]

    try:
        from ticket_system.lib.ticket_builder import dedupe_schema_sections
        new_body = dedupe_schema_sections(new_body)
    except Exception as exc:
        _sys.stderr.write(f"[resolve-artifact] dedupe_schema_sections skipped: {exc}\n")

    ticket["_body"] = new_body
    ticket_path = resolve_ticket_path(ticket, version, args.ticket_id)
    save_ticket(ticket, ticket_path)

    from ticket_system.lib import git_utils
    try:
        commit_status = git_utils._auto_commit_ticket_md(
            str(ticket_path), args.ticket_id, SOLUTION_SECTION, operation="resolve-artifact"
        )
        if commit_status in ("not_git_repo", "git_failed"):
            _sys.stderr.write(
                f"[resolve-artifact] auto-commit skipped（{commit_status}，非致命）\n"
            )
    except Exception as exc:
        _sys.stderr.write(f"[resolve-artifact] auto-commit 失敗（非致命）：{exc}\n")

    print(f"[OK] {args.ticket_id} 的 {label} status 已更新")
    print(f"   status: {new_value}")
    return 0


def parse_artifact_registrations(body: str) -> list[dict]:
    """從 body 解析所有實驗器材登記條目，回傳結構化清單（不需人工掃描章節）。

    供 `list-artifacts` CLI 輸出使用，亦可被未來的 complete-time 檢查
    （在 ticket_system/ 範圍外的 hook）直接匯入呼叫，取代反向掃描章節文字。
    """
    match = find_section(body, SOLUTION_SECTION)
    if match is None or not match.found:
        return []
    found, _s, _e, sub_content = _find_artifact_subsection(match.content)
    if not found:
        return []

    entries = []
    entry_pattern = re.compile(
        r"^- \*\*(EXP-\d+)\*\* \(([^)]*)\)\n((?:  - .+\n?)*)",
        re.MULTILINE,
    )
    for em in entry_pattern.finditer(sub_content):
        label, timestamp, fields_block = em.group(1), em.group(2), em.group(3)
        fields: dict = {"label": label, "timestamp": timestamp}
        for fm in re.finditer(r"^  - (\w+): (.*)$", fields_block, re.MULTILINE):
            fields[fm.group(1)] = fm.group(2)
        entries.append(fields)
    return entries


def execute_list_artifacts(args: argparse.Namespace, version: str) -> int:
    """輸出指定 ticket 已登記的實驗器材清單（結構化，供程式化讀取）。"""
    ticket = load_ticket(version, args.ticket_id)
    if not ticket:
        print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
        return 1

    body = ticket.get("_body", "")
    entries = parse_artifact_registrations(body)

    if getattr(args, "json", False):
        import json
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0

    if not entries:
        print(f"{args.ticket_id} 無已登記的實驗器材")
        return 0

    print(f"{args.ticket_id} 已登記 {len(entries)} 項實驗器材：")
    for e in entries:
        print(f"  {e.get('label', '?')} ({e.get('timestamp', '?')})")
        print(f"    path: {e.get('path', '')}")
        print(f"    purpose: {e.get('purpose', '')}")
        print(f"    expiry: {e.get('expiry', '')}")
        print(f"    type: {e.get('type', '')}")
        print(f"    status: {e.get('status', '')}")
    return 0
