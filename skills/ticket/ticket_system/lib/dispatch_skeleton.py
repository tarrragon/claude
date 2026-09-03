"""
Dispatch 骨架純組裝邏輯（不依賴 filelock，供 CLI 與測試共用）。

抽離自 `ticket_system.commands.track_dispatch`：hooks 測試套件的獨立 python
環境未必安裝 `filelock`，先前只能以 ast 靜態解析 track_dispatch.py 常數、或
重建 `_build_skeleton` 的組裝順序驗證行數，兩者皆測「代理物」而非 CLI 本體，
重建物與本體一旦漂移即無訊號（同型於骨架瘦身票的原根因：驗關鍵字不驗行數）。

本模組不 import filelock、不做檔案 I/O，只含骨架常數與純函式 `build_skeleton`
；`track_dispatch.py` 的 `_build_skeleton(args)` 與 hooks 測試套件皆直接呼叫
本模組的 `build_skeleton`，兩者量測的是同一份程式碼路徑。
"""

# 骨架（權威版）——與 .claude/references/agent-dispatch-template.md「骨架
# （3 段）」逐字一致。修改本常數須同步該文件（單一權威決策：CLI 為權威，
# 文件端改為引用本模組輸出）。
SKELETON_TEMPLATE_NORMAL = """Ticket: {ticket_id}

## 任務

{task_summary}

讀取 ticket：`ticket track full {ticket_id}`
認領：`ticket track claim {ticket_id} --as {agent_name}`
依 Context Bundle 執行流程。
測試與其結果為後續步驟前置的命令一律前景執行（加 timeout、`| tail`），run_in_background 僅限真正可並行的旁路任務。
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

# 精準 staging 制式句（權威版全文）——與
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
In a linked worktree (files changed under a worktree dir, not the main repo):
add `--worktree <abs-worktree-path>` to the command above.
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
  (isolated index, precise staging; in a linked worktree add `--worktree
  <abs-worktree-path>`). Fallback: `git add {exact files}` ->
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
# 執行中即填妥，避免代理人未填四項、complete 被 gate 擋下、PM 事後補料重演。
HOOK_TICKET_REMINDER = """本票 where.files 觸及 hooks 目錄，acceptance-gate 要求 acceptance 含四項必含：
  1. 本 session 實地觸發確認（含落檔驗證，或說明何以暫不驗證）
  2. liveness 驗證方式（如何確認 hook 被 runtime 載入並執行）
  3. 失敗語意（fail-open 或 fail-closed）
  4. 產生路徑盤點表（寫入 how.strategy，缺則 Solution；格式見
     .claude/pm-rules/ticket-body-schema.md「防護類 hook ticket 額外
     acceptance」節）
執行中請一併填寫，勿留到 complete 前才補。"""


def build_skeleton(
    *,
    kind: str,
    ticket_id: str,
    task_summary: str,
    agent_name: str = "{agent_name}",
    review_perspective: str = "{審查視角}",
    decision_question: str = "{裁決問題}",
    commit_policy: str = "agent",
    touches_hook_scope: bool = False,
) -> str:
    """依 `kind` 產生骨架文字（review 變體不含 claim/收尾協議）。

    純函式：不觸碰檔案系統、不 import filelock。CLI（`track_dispatch.py`
    的 `_build_skeleton`）與 hooks 測試套件皆呼叫本函式，行數綁定測試量測
    的即為 CLI 實際使用的組裝路徑，非重建物。
    """
    if kind == "review":
        return SKELETON_TEMPLATE_REVIEW.format(
            ticket_id=ticket_id,
            task_summary=task_summary,
            review_perspective=review_perspective,
            decision_question=decision_question,
        )

    skeleton = SKELETON_TEMPLATE_NORMAL.format(
        ticket_id=ticket_id,
        task_summary=task_summary,
        agent_name=agent_name,
    )

    if commit_policy == "agent":
        skeleton = f"{skeleton}\n\n{STAGING_PHRASE_AGENT_PROMPT}"
    elif commit_policy == "pm":
        skeleton = f"{skeleton}\n\n{STAGING_PHRASE_PM}"
    else:
        skeleton = f"{skeleton}\n\n{STAGING_PHRASE_NONE}"

    if touches_hook_scope:
        skeleton = f"{skeleton}\n\n{HOOK_TICKET_REMINDER}"

    return skeleton
