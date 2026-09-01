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

# 骨架（權威版）——與 .claude/references/agent-dispatch-template.md「骨架
# （3 段）」逐字一致。修改本常數須同步該文件（單一權威決策：CLI 為權威，
# 文件端改為引用本模組輸出）。
SKELETON_TEMPLATE_NORMAL = """Ticket: {ticket_id}

## 任務

{task_summary}

讀取 ticket：`ticket track full {ticket_id}`
認領：`ticket track claim {ticket_id} --as {agent_name}`
依 Context Bundle 執行流程。
發現 prompt 與 ticket/框架正本衝突，停手寫入 ticket NeedsContext 上報，不自行選邊。
遇阻立即停下回報，禁繞過 Hook。
收尾：`ticket track set-acceptance {ticket_id} --check <編號>` → 填 Solution / Test Results → commit → `ticket track complete {ticket_id} --as {agent_name}`。"""

# review 變體：審查派發不觸發 claim/complete 生命週期（審查非執行票，票本身
# 只是審查標的，任務書在 prompt），欄位改為審查標的/視角/裁決問題/回報格式。
SKELETON_TEMPLATE_REVIEW = """Ticket: {ticket_id}

## 審查任務

{task_summary}

審查標的：`ticket track full {ticket_id}`
審查視角：{review_perspective}
裁決問題：{decision_question}
回報格式：結論 + 理由 + 建議 ticket（不 claim/complete 本票，審查結果寫回派發者指定位置）。
發現 prompt 與 ticket/框架正本衝突，停手回報，不自行選邊。"""

# 精準 staging 制式句（權威版全文，PC-092 / PC-BAL-008）——與
# .claude/references/agent-dispatch-template.md「精準 staging 制式句
# （權威版）」節逐字一致（該文件段落改為引用本命令輸出，不再手動同步）。
# 主路徑改為 `ticket track commit`（隔離索引提交 where.files 子集，全程不
# 觸碰共用 index）；裸 git add/commit 降為 fallback，僅於新命令失敗或不可
# 用時使用。fallback 段落仍保留 Category A/B/C 片語齊備（dispatch-staging-
# phrase-guard-hook 的 _missing_categories 判定為空集——該 hook 不在本票
# where.files，不可修改片語表，故以保留片語文字而非改寫方式維持相容）。
#
# 骨架瘦身後用途變更：本常數 26 行全文不再直接嵌入骨架（會使骨架超出
# agent-prompt-length-guard 的 30 行硬上限），改由 `execute_dispatch` 冪等
# 寫入 ticket body 的「### Commit 規範」固定子節（見 `_ensure_commit_section`
# / `COMMIT_SECTION_HEADING`）。骨架本身改附 `STAGING_PHRASE_AGENT_PROMPT`
# 短版指標句，並指向本節供代理人 `ticket track full` 讀取全文。
STAGING_PHRASE_AGENT = """Recommended: commit via isolated index (files must be a subset of this
ticket's where.files; never touches the shared index):
  ticket track commit <ticket-id> -m "..." -- {exact files}
Fallback (not recommended; only if `ticket track commit` fails or is
unavailable) — use precise staging + verified bare commit only (no pathspec):
  git add {exact files}
  git diff --cached --name-only   # confirm index contains ONLY {exact files}
  git commit -m "..."             # bare commit; no -- <paths> / --only / -o / -a
Forbidden: git add . / git add -A; git commit -- <paths> / --only / -o / -a
  (pathspec-style commit discards the index and rebuilds it from working-tree
   content for the given paths — it silently absorbs unstaged edits other
   sessions may have on the same path, not just already-staged ones)
Before fallback commit: git diff --cached --name-only to check staged scope; git restore --staged <path> for any non-owned file
If bare `git commit` fallback is DENYed by bare-commit-guard-hook (another
dispatch active), stop and escalate to PM; never switch to pathspec /
--only / -o / -a to get around it.
If a commit is later found to have swept in out-of-scope content (e.g. a
peer session's staged changes):
Forbidden recovery actions: git revert; git reset --soft; git commit
--amend; any "reverse apply"/reapply of the diff. None of these may be
used to undo or rewrite the commit.
The ONLY permitted actions are: stop, record the commit SHA and file
list in the ticket, report to PM.
Reason: swept-in content is diff-indistinguishable from a peer's
legitimate concurrent write in the same window, so any of the forbidden
actions above would also undo the peer's legitimate work."""

# 骨架用短版指標句（6 行，取代直接嵌入 STAGING_PHRASE_AGENT 全文 26 行）。
# 仍逐句保留 dispatch-staging-phrase-guard-hook 判定所需的 Category A/B/C
# 正面片語（"precise staging" / "git diff --cached --name-only" / "verified
# bare commit" + "no pathspec"），故切換後該 hook 的 Layer 2 軟提示行為不變
# （已以該 hook 的 `_missing_categories` 實測驗證為空集）。識別依據不可偽造
# 的顧慮不適用於本取向：本取向未對 agent-prompt-length-guard 的 Layer 1
# 硬上限新增豁免路徑，純粹是縮短骨架本體行數，判準仍是唯一的行數比較。
STAGING_PHRASE_AGENT_PROMPT = """Commit: prefer `ticket track commit <ticket-id> -m "..." -- {exact files}`
  (isolated index, precise staging). Fallback: `git add {exact files}` ->
  `git diff --cached --name-only` to verify -> verified bare commit, no
  pathspec (forbid `-- <paths>` / `--only` / `-o` / `-a` / `git add .` /
  `git add -A`). Swept-in content: forbid revert/reset/amend, stop & report.
Full text: this ticket's "### Commit 規範" section (`ticket track full <ticket-id>`)."""

# --commit-policy pm/none 的對應一行輸出。
STAGING_PHRASE_PM = "Commit policy: PM 統一 commit，agent 不執行 git commit（完成後回報變更檔案清單）。"
STAGING_PHRASE_NONE = "Commit policy: none（本次派發不涉及 git commit）。"

# 防護類 hook 票四項必含提醒（對應 acceptance-gate 之
# hook_protection_acceptance_checker 四項必含：本 session 實地觸發確認 /
# liveness 驗證方式 / 失敗語意 fail-open/fail-closed / 產生路徑盤點表寫入
# how.strategy）。文字與該 checker 的關鍵詞判準保持語意一致，供代理人在
# 執行中即填妥，避免 876.2 事件重演（代理人未填四項、complete 被 gate
# 擋下、PM 事後補料）。
HOOK_TICKET_REMINDER = """本票 where.files 觸及 hooks 目錄，acceptance-gate 要求 acceptance 含四項必含：
  1. 本 session 實地觸發確認（含落檔驗證，或說明何以暫不驗證）
  2. liveness 驗證方式（如何確認 hook 被 runtime 載入並執行）
  3. 失敗語意（fail-open 或 fail-closed）
  4. 產生路徑盤點表（寫入 how.strategy，缺則 Solution；格式見
     .claude/pm-rules/ticket-body-schema.md「防護類 hook ticket 額外
     acceptance」節）
執行中請一併填寫，勿留到 complete 前才補。"""


def _build_skeleton(args: argparse.Namespace) -> str:
    """依 --kind 產生骨架文字（review 變體不含 claim/收尾協議）。"""
    task_summary = args.task_summary or "{一句話動作描述，≤ 40 字}"
    agent_name = args.as_agent or "{agent_name}"

    if args.kind == "review":
        return SKELETON_TEMPLATE_REVIEW.format(
            ticket_id=args.ticket_id,
            task_summary=task_summary,
            review_perspective=args.review_perspective or "{審查視角}",
            decision_question=args.decision_question or "{裁決問題}",
        )

    skeleton = SKELETON_TEMPLATE_NORMAL.format(
        ticket_id=args.ticket_id,
        task_summary=task_summary,
        agent_name=agent_name,
    )

    commit_policy = getattr(args, "commit_policy", "agent") or "agent"
    if commit_policy == "agent":
        skeleton = f"{skeleton}\n\n{STAGING_PHRASE_AGENT_PROMPT}"
    elif commit_policy == "pm":
        skeleton = f"{skeleton}\n\n{STAGING_PHRASE_PM}"
    else:
        skeleton = f"{skeleton}\n\n{STAGING_PHRASE_NONE}"

    if getattr(args, "_touches_hook_scope", False):
        skeleton = f"{skeleton}\n\n{HOOK_TICKET_REMINDER}"

    return skeleton


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

    Args:
        args: 需含 ticket_id / as_agent / note / kind / task_summary /
            review_perspective / decision_question / commit_policy
        version: 已解析版本號

    Returns:
        0 成功；1 票不存在或 body 缺失
    """
    ticket_path = get_ticket_path(version, args.ticket_id)
    commit_policy = getattr(args, "commit_policy", "agent") or "agent"
    needs_commit_section = args.kind == "normal" and commit_policy == "agent"

    if args.note or needs_commit_section:
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
    else:
        # 無 note 且非 agent commit 情境仍需確認票存在，避免對不存在的票輸出骨架造成誤派發
        ticket = load_ticket(version, args.ticket_id)
        if not ticket:
            print(format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id=args.ticket_id))
            return 1

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
