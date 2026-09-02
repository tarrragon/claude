"""
Ticket track dispatch 子命令模組

負責「派發即落票」：將派發瞬間才被 articulate 的約束/步驟（`--note`）落票至
「派發日誌」章節，並輸出骨架 prompt（normal/review 兩變體）供 PM 直接複製派發。

背景：一次派發 prompt 基線量測顯示，多數派發 prompt 的非骨架文字為票內
不存在的補洞內容，主因不是 PM 重述而是約束/步驟只存在於派發瞬間的對話、
無處可落。本模組把落票與骨架輸出合併為單一原子命令，取代 PM 自律記得補
Context Bundle。

CLI 為單一權威：SKELETON_TEMPLATE_NORMAL / SKELETON_TEMPLATE_REVIEW 為骨架
文字的權威來源，`.claude/references/agent-dispatch-template.md` 改為引用
本模組輸出，不再手動同步逐字模板。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    import sys
    from ticket_system.lib.ui_constants import SEPARATOR_PRIMARY
    print(SEPARATOR_PRIMARY)
    print("[ERROR] 此檔案不支援直接執行")
    print(SEPARATOR_PRIMARY)
    print()
    print("正確使用方式：")
    print("  ticket track dispatch <ticket_id> --as <agent_name>")
    print()
    print("如尚未安裝，請執行：")
    print("  cd .claude/skills/ticket && uv tool install .")
    print()
    print("詳見 SKILL.md")
    print(SEPARATOR_PRIMARY)
    sys.exit(1)


import argparse
import re
import sys
from datetime import datetime
from typing import Optional

from ticket_system.lib.dispatch_skeleton import (
    HOOK_TICKET_REMINDER,
    SKELETON_TEMPLATE_NORMAL,
    SKELETON_TEMPLATE_REVIEW,
    STAGING_PHRASE_AGENT,
    STAGING_PHRASE_AGENT_PROMPT,
    STAGING_PHRASE_NONE,
    STAGING_PHRASE_PM,
    build_skeleton,
)
from ticket_system.lib.file_lock import file_lock
from ticket_system.lib.section_locator import find_section
from ticket_system.lib.ticket_loader import get_ticket_path, load_ticket, save_ticket
from ticket_system.lib.messages import ErrorMessages, format_error
from ticket_system.lib.ticket_ops import resolve_ticket_path

# 派發日誌章節名。掛在 Schema H2「Problem Analysis」下的 H3 子節（非獨立 H2，
# 不受 SCHEMA_H2_SECTIONS canonical 順序與 body-schema-checker 必填檢查約束），
# 只承載暫態內容（commit 歸屬、臨時能力調整等），依父票 Solution 判定不可進
# Context Bundle。原為獨立 H2，觸發 acceptance-gate 對非 Schema H2 的固定
# WARNING；改掛 Problem Analysis 下 H3 消除該噪音。
DISPATCH_LOG_SECTION = "派發日誌"
PARENT_SCHEMA_SECTION = "Problem Analysis"

# Commit 規範章節名（骨架瘦身落地）。同樣掛 Problem Analysis 下 H3 子節，但
# 語意與「派發日誌」不同：本節是**冪等覆寫**的固定內容（每次 dispatch 覆寫
# 為 STAGING_PHRASE_AGENT 最新文字，不逐次累加），供骨架瘦身後代理人透過
# `ticket track full` 讀取完整精準 staging 制式句——骨架本身只保留
# STAGING_PHRASE_AGENT_PROMPT 短版指標句（見下方常數），避免逐字複製 26 行
# 全文導致骨架超出 agent-prompt-length-guard 的 30 行硬上限（PC-040）。
COMMIT_SECTION_HEADING = "Commit 規範"

# 骨架常數與純組裝邏輯已抽離至 ticket_system.lib.dispatch_skeleton（不
# import filelock，供 CLI 與 hooks 測試套件共用同一份組裝路徑）。本模組
# import 上方常數僅為向後相容既有引用（如逐字同步文件的比對），CLI 呼叫
# 一律走下方 `_build_skeleton` 轉呼叫的 `build_skeleton`。


def _build_skeleton(args: argparse.Namespace) -> str:
    """依 --kind 產生骨架文字（review 變體不含 claim/收尾協議）。

    薄轉接層：將 argparse.Namespace 攤平為關鍵字參數後轉呼叫
    `dispatch_skeleton.build_skeleton`（純函式，不觸碰檔案系統/filelock）。
    """
    task_summary = args.task_summary or "{一句話動作描述，≤ 40 字}"
    agent_name = args.as_agent or "{agent_name}"
    commit_policy = getattr(args, "commit_policy", "agent") or "agent"

    return build_skeleton(
        kind=args.kind,
        ticket_id=args.ticket_id,
        task_summary=task_summary,
        agent_name=agent_name,
        review_perspective=args.review_perspective or "{審查視角}",
        decision_question=args.decision_question or "{裁決問題}",
        commit_policy=commit_policy,
        touches_hook_scope=getattr(args, "_touches_hook_scope", False),
    )


def _find_h3_subsection(section_content: str, heading: str) -> Optional[tuple]:
    """在 H2 section 內容中定位單一 H3 子節 `### {heading}`，回傳
    `(start, content_start, end, text)`；未找到回傳 None。

    與 `section_locator.find_section(..., levels=(3,))` 的差異：後者的邊界
    只認下一個 H2（`\\n## `），刻意假設每個 H2 底下只有一個 H3 子節（見
    section_locator.py docstring）。本模組的「## Problem Analysis」現同時
    掛「### 派發日誌」與「### Commit 規範」兩個手足 H3——若沿用該假設，
    查詢在前的子節會把在後的手足子節內容一併吃進自己的範圍（多手足並存
    時的邊界溢出，實測會使後續 dispatch 的新增內容被吞沒不見）。本函式
    改以下一個「## 」或「### 」（不分層級）為界，僅限本模組內部使用，
    不修改 section_locator.py 共用邏輯（其他呼叫端可能依賴既有「一路吃到
    底」語意，例如 acceptance_auditor 的必填章節驗證）。
    """
    header_match = re.search(rf"^###\s+{re.escape(heading)}\s*$", section_content, re.MULTILINE)
    if not header_match:
        return None
    start = header_match.start()
    content_start = header_match.end()
    if content_start < len(section_content) and section_content[content_start] == "\n":
        content_start += 1
    boundary_match = re.search(r"\n#{2,3} ", section_content[content_start:])
    end = content_start + boundary_match.start() if boundary_match else len(section_content)
    return start, content_start, end, section_content[start:end]


def _append_dispatch_note(body: str, note: str) -> str:
    """將 --note 帶時間戳寫入「## Problem Analysis」下的「### 派發日誌」
    子節。Problem Analysis 章節缺失時自動建立於 body 末尾（連同 H3 子節一併
    建立，不可靜默丟 note；不走 insert_missing_schema_section 的 canonical
    順序插入，因本子節非必填 Schema 內容）。
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [{timestamp}] {note}\n"

    parent_match = find_section(body, PARENT_SCHEMA_SECTION)
    if not parent_match.found:
        # Problem Analysis 章節不存在：建立該 H2，內含 ### 派發日誌 子節。
        separator = "" if body.endswith("\n\n") else ("\n" if body.endswith("\n") else "\n\n")
        new_block = (
            f"{separator}## {PARENT_SCHEMA_SECTION}\n\n"
            f"### {DISPATCH_LOG_SECTION}\n\n{entry}\n---\n\n"
        )
        return body.rstrip("\n") + "\n\n" + new_block.lstrip("\n")

    section_start = parent_match.start
    section_end = parent_match.end
    section_content = parent_match.content

    sub_match = _find_h3_subsection(section_content, DISPATCH_LOG_SECTION)
    if sub_match:
        sub_start, _sub_content_start, sub_end, sub_text = sub_match
        header_end = sub_text.find("\n")
        header_line = sub_text[: header_end + 1] if header_end != -1 else sub_text
        rest = sub_text[header_end + 1:] if header_end != -1 else ""
        updated_sub = header_line + rest.rstrip("\n") + ("\n" if rest.strip() else "") + entry
        updated_content = section_content[:sub_start] + updated_sub + section_content[sub_end:]
    else:
        # Problem Analysis 存在但無 ### 派發日誌 子節：附加於該子節理應所在
        # 位置的緊鄰處，不影響其他既有手足子節（如 ### Commit 規範）。若已
        # 有 ### Commit 規範 子節，插在其之前；否則附加於 H2 內容末尾。
        commit_sub = _find_h3_subsection(section_content, COMMIT_SECTION_HEADING)
        insertion_block = f"### {DISPATCH_LOG_SECTION}\n\n{entry}\n"
        if commit_sub:
            insert_at = commit_sub[0]
            updated_content = section_content[:insert_at] + insertion_block + "\n" + section_content[insert_at:]
        else:
            updated_content = section_content.rstrip("\n") + f"\n\n{insertion_block}"

    updated_section = body[section_start:parent_match.content_start] + updated_content
    return body[:section_start] + updated_section + body[section_end:]


def _ensure_commit_section(body: str, content: str) -> str:
    """確保「## Problem Analysis」下含「### Commit 規範」子節，內容**冪等
    覆寫**為 `content`（通常是 `STAGING_PHRASE_AGENT` 全文）。

    與 `_append_dispatch_note` 的差異：後者每次 dispatch 累加一筆帶時間戳的
    暫態紀錄；本函式維護的是單一固定區塊，每次呼叫覆寫為最新內容，不隨
    dispatch 次數增長，代理人 `ticket track full` 讀取到的永遠是與
    `STAGING_PHRASE_AGENT` 常數同步的全文（骨架瘦身後，骨架本體只留短版
    指標句指向本節，見 `STAGING_PHRASE_AGENT_PROMPT`）。

    Returns:
        更新後的 body；若既有內容已與 `content` 相同則原樣回傳（呼叫端可用
        `body_before == body_after` 判斷是否需要落盤，避免無變更也觸發 save）。
    """
    parent_match = find_section(body, PARENT_SCHEMA_SECTION)
    if not parent_match.found:
        separator = "" if body.endswith("\n\n") else ("\n" if body.endswith("\n") else "\n\n")
        new_block = (
            f"{separator}## {PARENT_SCHEMA_SECTION}\n\n"
            f"### {COMMIT_SECTION_HEADING}\n\n{content}\n\n---\n\n"
        )
        return body.rstrip("\n") + "\n\n" + new_block.lstrip("\n")

    section_start = parent_match.start
    section_end = parent_match.end
    section_content = parent_match.content

    sub_match = _find_h3_subsection(section_content, COMMIT_SECTION_HEADING)
    if sub_match:
        sub_start, _sub_content_start, sub_end, existing_text = sub_match
        new_sub = f"### {COMMIT_SECTION_HEADING}\n\n{content}\n"
        if existing_text.rstrip("\n") == new_sub.rstrip("\n"):
            return body  # 內容未變，不需重寫（避免無變更也觸發 save）
        updated_content = section_content[:sub_start] + new_sub + section_content[sub_end:]
    else:
        updated_content = section_content.rstrip("\n") + f"\n\n### {COMMIT_SECTION_HEADING}\n\n{content}\n"

    updated_section = body[section_start:parent_match.content_start] + updated_content
    return body[:section_start] + updated_section + body[section_end:]


def _directory_declaration_block_message(ticket: dict, ticket_id: str, version: str) -> Optional[str]:
    """目錄級寫入宣告硬擋判定（PC-BAL-040）。

    dispatch 是派發鏈最晚且 PM 在場的攔截點，對無 `::read` 的目錄級寫入
    宣告拒絕輸出骨架（create/set-where 層只發 WARNING，因建票時檔案未必
    可知；dispatch 時機已知曉具體路徑，應硬擋）。

    Returns:
        None：無目錄級寫入宣告，可正常輸出骨架
        str：命中時的錯誤訊息（含每個目錄下其他活躍票的受影響清單）
    """
    from ticket_system.lib.file_conflict import files_intersect, is_directory_declaration, write_files
    from ticket_system.lib.ticket_loader import list_tickets

    dir_paths = [p for p in write_files(ticket) if is_directory_declaration(p)]
    if not dir_paths:
        return None

    try:
        others = list_tickets(version) or []
    except Exception:
        others = []
    active_others = [
        t for t in others
        if t.get("id") != ticket_id and t.get("status") in ("pending", "in_progress")
    ]

    lines = [
        "[BLOCKED] where.files 含目錄級寫入宣告（結尾 '/' 或指向既有目錄），"
        "未帶 ::read 標記，dispatch 拒絕輸出骨架（PC-BAL-040）：",
    ]
    for dp in dir_paths:
        lines.append(f"  - {dp}")
        affected = sorted({
            o.get("id")
            for o in active_others
            for op in write_files(o)
            if files_intersect(dp, op)
        })
        if affected:
            lines.append(f"    受影響（同目錄下已有其他活躍票宣告寫入）: {', '.join(affected)}")
    lines.append("請改列精確路徑，或若僅需唯讀存取請加註 ::read（如 'path::read'）。")
    return "\n".join(lines)


def _touches_hook_protection_scope(ticket: dict) -> bool:
    """ticket 的 where.files（寫入意圖）是否觸及 `.claude/hooks/` 或
    `.claude/skills/<skill>/hooks/`（防護類 hook 票判定範圍）。

    Lazy import `.claude/hooks/acceptance_checkers` 共用判定邏輯（避免與
    acceptance-gate 的 hook_protection_acceptance_checker 雙實作漂移，
    沿用 ticket_validator._detect_self_check_subsection 既有慣例）；
    import 失敗時降級為 False（不阻擋派發，僅少提醒一次）。
    """
    if not isinstance(ticket, dict):
        return False
    try:
        import logging
        import sys
        from pathlib import Path as _Path

        # track_dispatch.py: .claude/skills/ticket/ticket_system/commands/track_dispatch.py
        # → 上溯 4 層至 .claude/
        claude_dir = _Path(__file__).resolve().parents[4]
        hooks_dir = claude_dir / "hooks"
        if str(hooks_dir) not in sys.path:
            sys.path.insert(0, str(hooks_dir))
        from acceptance_checkers.hook_protection_acceptance_checker import (
            touches_hook_protection_scope,
        )
        from acceptance_checkers.ticket_parser import extract_where_files_write_only

        where_files = extract_where_files_write_only(ticket, logging.getLogger(__name__))
        return any(touches_hook_protection_scope(f) for f in where_files)
    except Exception:  # noqa: BLE001 — import 失敗降級為不提醒
        return False


def execute_dispatch(args: argparse.Namespace, version: str) -> int:
    """派發即落票：--note 寫入派發日誌章節 + kind="normal" 且
    commit_policy="agent" 時冪等寫入/更新「### Commit 規範」固定章節（骨架
    瘦身落地：骨架本體只留短版指標句，全文由此章節承載） + 輸出骨架 prompt。

    `--dry-run` 時完全略過票面寫入（不落盤、不觸發 file_lock），僅唯讀確認
    票存在；骨架輸出與非 dry-run 完全相同（`_build_skeleton` 不依賴票面
    寫入結果），供 PM 量測骨架行數或預覽 prompt 時可自由重複執行，不再需要
    事後 checkout 還原票面（2026-09-02 新增）。

    Args:
        args: 需含 ticket_id / as_agent / note / kind / task_summary /
            review_perspective / decision_question / commit_policy / dry_run
        version: 已解析版本號

    Returns:
        0 成功；1 票不存在或 body 缺失
    """
    ticket_path = get_ticket_path(version, args.ticket_id)
    commit_policy = getattr(args, "commit_policy", "agent") or "agent"
    dry_run = getattr(args, "dry_run", False)
    needs_commit_section = args.kind == "normal" and commit_policy == "agent"

    if dry_run or not (args.note or needs_commit_section):
        # --dry-run，或無 note 且非 agent commit 情境：僅唯讀確認票存在，
        # 避免對不存在的票輸出骨架造成誤派發；不落盤。
        ticket = load_ticket(version, args.ticket_id)
        if not ticket:
            print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
            return 1
    else:
        with file_lock(ticket_path):
            ticket = load_ticket(version, args.ticket_id)
            if not ticket:
                print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
                return 1

            body = ticket.get("_body", "")
            if not body:
                print(format_error(ErrorMessages.BODY_CONTENT_NOT_FOUND, ticket_id=args.ticket_id))
                return 1

            updated_body = body
            if args.note:
                updated_body = _append_dispatch_note(updated_body, args.note)
            if needs_commit_section:
                updated_body = _ensure_commit_section(updated_body, STAGING_PHRASE_AGENT)

            if updated_body != body:
                ticket["_body"] = updated_body
                save_path = resolve_ticket_path(ticket, version, args.ticket_id)
                save_ticket(ticket, save_path)

    block_message = _directory_declaration_block_message(ticket, args.ticket_id, version)
    if block_message:
        print(block_message)
        return 1

    args._touches_hook_scope = _touches_hook_protection_scope(ticket)

    print(_build_skeleton(args))
    return 0


def register_dispatch_command(subparsers: "argparse._SubParsersAction") -> None:
    """註冊 dispatch 子命令。"""
    p_dispatch = subparsers.add_parser(
        "dispatch",
        help="派發即落票：--note 寫入派發日誌章節 + 輸出骨架 prompt（normal/review）",
    )
    p_dispatch.add_argument("ticket_id", help="Ticket ID")
    p_dispatch.add_argument("--version", help="版本號（自動偵測）")
    p_dispatch.add_argument(
        "--as",
        dest="as_agent",
        default=None,
        metavar="AGENT_NAME",
        help="派發對象 agent 名稱，代入骨架的 claim/complete --as",
    )
    p_dispatch.add_argument(
        "--note",
        dest="note",
        default=None,
        help="派發瞬間的暫態約束/步驟，帶時間戳寫入票的「派發日誌」章節（不進 Context Bundle）",
    )
    p_dispatch.add_argument(
        "--kind",
        dest="kind",
        choices=["normal", "review"],
        default="normal",
        help="骨架變體：normal（預設，含 claim/收尾協議）或 review（審查派發，不含 claim/收尾）",
    )
    p_dispatch.add_argument(
        "--task-summary",
        dest="task_summary",
        default=None,
        help="一句話動作描述（≤ 40 字），代入骨架任務段",
    )
    p_dispatch.add_argument(
        "--review-perspective",
        dest="review_perspective",
        default=None,
        help="--kind review 專用：審查視角，代入骨架",
    )
    p_dispatch.add_argument(
        "--decision-question",
        dest="decision_question",
        default=None,
        help="--kind review 專用：裁決問題，代入骨架",
    )
    p_dispatch.add_argument(
        "--commit-policy",
        dest="commit_policy",
        choices=["agent", "pm", "none"],
        default="agent",
        help=(
            "commit 歸屬：agent（預設，嵌入精準 staging 制式句權威版全文）/"
            " pm（PM 統一 commit，agent 不執行）/ none（本次派發不涉及 commit）"
        ),
    )
    p_dispatch.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="只輸出骨架，不寫入票面（不落 --note、不冪等寫入 Commit 規範子節）；預設行為不變",
    )
