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

from pathlib import Path

# --dry-run 輸出首行浮水印（3-F M-7）。正式骨架（SKELETON_TEMPLATE_* 與
# 下方 build_skeleton 的組裝結果）本身不變；浮水印由呼叫端（track_dispatch
# 的 execute_dispatch）在 dry-run 分支對 build_skeleton 輸出做後處理式
# 前綴，使貼入 prompt 的文字帶有「未落票」的可辨識標記，取代原本 dry-run
# 與正式派發骨架逐字相同、貼入 prompt 後無從辨識是否曾落票的狀態。
DRY_RUN_WATERMARK = "[DRY-RUN 未落票]"

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
{closing}"""

# normal 變體收尾句（依 isolation 對表選用，不在 format 字串內寫條件分支）。
# worktree：代理人收尾止於 ticket track commit 並回報 PM，complete 由 PM 於合併並驗證後執行。
# {pre_commit} 為閘門逐檔檢查子句（GATE_CHECK_CLAUSE），無檢查時代入空字串，
# 收尾句與加入本欄位前逐字相同。
CLOSING_BY_ISOLATION = {
    "none": (
        "收尾：`ticket track set-acceptance {ticket_id} --check <編號>` → 填 Solution（含 ### 自檢結果與 Phase 4 評估）/ "
        "Test Results → {pre_commit}commit → `ticket track complete {ticket_id} --as {agent_name}`。"
    ),
    "worktree": (
        "收尾：`ticket track set-acceptance {ticket_id} --check <編號>` → 填 Solution（含 ### 自檢結果與 Phase 4 評估）/ "
        "Test Results → {pre_commit}`ticket track commit {ticket_id} -m \"<描述>\" --worktree <worktree 絕對路徑> -- <檔案>`"
        "（只提交產品檔；票面由主 repo CLI 寫入並自動提交，禁止複製或提交票面副本）。"
        "收尾到 ticket track commit 為止，回報 PM。"
    ),
}

# 非 worktree 派發豁免路徑（與 .claude/hooks/branch-verify-hook.py
# is_exempt_path_on_protected_branch 的 same-repo 清單一致；該 hook 為權威）。
EXEMPT_PATH_PREFIXES = (".claude/", "docs/", "scripts/experiments/")
EXEMPT_EXACT_PATHS = (
    "CLAUDE.md",
    "README.md",
    "CHANGELOG.md",
    "package.json",
    "manifest.json",
    ".gitignore",
    ".gitattributes",
)


def non_exempt_paths(paths) -> list:
    """回傳 paths 中不屬豁免清單的路徑（需 worktree 隔離的候選）。"""
    return [
        p for p in paths
        if not p.startswith(EXEMPT_PATH_PREFIXES) and p not in EXEMPT_EXACT_PATHS
    ]

# review 變體：審查派發不觸發 claim/complete 生命週期（審查非執行票，票本身
# 只是審查標的，任務書在 prompt），欄位改為審查標的/視角/裁決問題/回報格式。
SKELETON_TEMPLATE_REVIEW = """Dispatch-Mode: readonly
Ticket: {ticket_id}

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
Fallback (not recommended; only if `ticket track commit` hits an environmental
failure that persists after re-running it, or is unavailable. Scope/criteria
rejections must NOT use fallback: stop and report to PM) — use precise staging + verified bare commit only (no pathspec):
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
STAGING_PHRASE_AGENT_PROMPT = """Commit: `ticket track commit <ticket-id> -m "..." -- {exact files}` (isolated index, precise staging; linked worktree: add `--worktree <abs-path>`). Scope/criteria rejection: no fallback, stop & report PM. Swept-in content: forbid revert/reset/amend, stop & report.
Environmental failure: re-run first; if it persists, fallback `git add {exact files}` -> `git diff --cached --name-only` to verify -> verified bare commit, no pathspec (forbid `-- <paths>` / `--only` / `-o` / `-a` / `git add .` / `git add -A`).
Full text: this ticket's "### Commit 規範" section (`ticket track full <ticket-id>`)."""

# --commit-policy pm/none 的對應一行輸出。
STAGING_PHRASE_PM = "Commit policy: PM 統一 commit，agent 不執行 git commit（完成後回報變更檔案清單）。"
STAGING_PHRASE_NONE = "Commit policy: none（本次派發不涉及 git commit）。"

# 防護類 hook 票四項必含提醒（對應 acceptance-gate 之
# hook_protection_acceptance_checker 四項必含：本 session 實地觸發確認 /
# liveness 驗證方式 / 失敗語意 fail-open/fail-closed / 產生路徑盤點表寫入
# how.strategy）。文字與該 checker 的關鍵詞判準保持語意一致，供代理人在
# 執行中即填妥，避免代理人未填四項、complete 被 gate 擋下、PM 事後補料重演。
HOOK_TICKET_REMINDER = """本票觸及 hooks 目錄，acceptance 中 hook 模板各條的 <待填：…> 說明即為須填的證據；寫入 Test Results/Solution：hook-logs/ 日誌行（實地觸發、liveness，或貼 `ticket track hook-liveness` 輸出）、fail-open 或 fail-closed 並附「觸發條件：...」。
產生路徑盤點表寫入 how.strategy，格式見 .claude/pm-rules/ticket-body-schema.md「防護類 ticket」節；執行中填寫，勿留到 complete 前。"""


# 含測試 acceptance 的 IMP 票加一行：修改產品碼前先實跑紅燈。
RED_RUN_LINE = (
    "修改產品碼前先實跑新增測試，於 Test Results 貼紅燈輸出摘要；未實跑者須標為推論。"
)
_RED_RUN_ANCHOR = "遇阻立即停下回報，禁繞過 Hook。\n"

# --isolation worktree 專用：票面 CLI 被拒的處置與多行內容傳入方式。
WORKTREE_CLI_REJECT_LINE = (
    "票面 CLI（append-log、set-acceptance 等）被拒時，不以 Edit／Write 改 worktree 內票檔；"
    "把要寫入的內容原文放進回報，由 PM 於主倉庫寫入。"
)
WORKTREE_MULTILINE_LINE = (
    "多行內容先以 Write 寫入 scratchpad 內容檔（檔名含票號，非票檔），再以 append-log --content-file <路徑> 傳入，"
    "不用 heredoc（worktree 拒收含換行的參數）；`### 自檢結果` 須獨立成行。"
)
# 測試入口對照（.claude/references/agent-dispatch-testing.md〈測試入口〉表）。
# skill 以 root 下 pyproject.toml 是否存在推導：有則以其目錄為入口；無 pyproject
# 但有 tests 目錄則借 hooks 入口；兩者皆無回 None。
WORKTREE_SIBLING_TEST_LINE = (
    "改行為前以改動物字面 grep 所有測試目錄"
    "（範圍見 agent-dispatch-testing.md〈相關測試檔怎麼找〉）；需改的測試檔不在 where.files 內即停手回報。"
)
TEST_ENTRY_LINE = "測試入口（不自拼 --with）：{commands}"
_HOOKS_ENTRY = "uv --directory <checkout>/.claude/hooks run pytest"


def _entry_for_path(path: str, root: Path):
    """單一路徑對應的測試入口命令；無對應回 None。"""
    parts = str(path).split("/")
    if len(parts) < 3 or parts[0] != ".claude" or not str(path).endswith(".py"):
        return None
    area = parts[1]
    if area in ("hooks", "lib"):
        return _HOOKS_ENTRY
    if area == "scripts":
        return "uv --directory <checkout>/.claude/scripts run pytest"
    if area != "skills" or len(parts) < 4:
        return None
    skill = parts[2]
    skill_dir = root / ".claude" / "skills" / skill
    if (skill_dir / "pyproject.toml").is_file():
        return f"uv --directory <checkout>/.claude/skills/{skill} run pytest"
    if (skill_dir / "tests").is_dir():
        return f"{_HOOKS_ENTRY} <checkout>/.claude/skills/{skill}/tests"
    return None


def entry_commands_for_files(files, root: Path) -> list:
    """由 where.files 推出所屬套件的測試入口命令（去重、保序；無對應回空）。

    root 為 checkout 根（用以判斷 skill 目錄下 pyproject.toml／tests 是否存在）。
    """
    entries = []
    for path in files or []:
        cmd = _entry_for_path(path, root)
        if cmd and cmd not in entries:
            entries.append(cmd)
    return entries


# --- 閘門逐檔檢查（merge-gate.yaml 帶 changed_files 的套件） -----------------
#
# 這類套件只對本次改動檔執行（如格式檢查），結果完全由代理人自己的改動決定，
# 提交前在本機即可重現；未轉成本機要求時，紅燈要到合併閘門才出現，多佔一輪
# 閘門名額。全套件型套件（無 changed_files）不產生命令：其命令不帶路徑即跑
# 全套件，與「代理人只跑相關測試檔」的分工衝突。
#
# 範圍判定的權威為 worktree skill 的 merge_gate.py（_parse_suite／
# _suite_scope_files）：prefixes 前綴或 files 精確路徑命中，且符合 changed_files
# 正規式。兩 skill 各有獨立環境、不互相 import，此處只複製判定所需的最小子集；
# 宣告格式驗證（欄位必填、保留名）仍以閘門為準，本函式不重複。
GATE_DECLARATION_PATH = ".claude/project-integration/merge-gate.yaml"
GATE_CHECK_CLAUSE = "提交前跑閘門逐檔檢查（結束碼須為 0）：{commands} → "


class GateDeclarationError(ValueError):
    """閘門宣告無法解析（YAML 錯誤或結構不符）。"""


def _gate_suites(declaration_text):
    import yaml  # 延遲匯入：骨架其餘部分不需 pyyaml

    if not declaration_text:
        return {}
    try:
        doc = yaml.safe_load(declaration_text)
    except yaml.YAMLError as exc:
        raise GateDeclarationError(f"YAML 無法解析：{exc}") from exc
    suites = doc.get("suites") if isinstance(doc, dict) else None
    if suites is None and isinstance(doc, dict):
        return {}
    if not isinstance(suites, dict):
        raise GateDeclarationError("suites 必須是套件名對應")
    return suites


def _suite_matches(suite: dict, files) -> list:
    import re

    pattern = suite.get("changed_files")
    command = suite.get("command")
    if not pattern or not isinstance(command, list):
        return []
    prefixes = tuple(suite.get("prefixes") or ())
    exact = tuple(suite.get("files") or ())
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise GateDeclarationError(f"changed_files 正規式無效：{exc}") from exc
    in_scope = [f for f in files if (prefixes and f.startswith(prefixes)) or f in exact]
    return [f for f in in_scope if regex.search(f)]


def gate_check_commands(files, declaration_text) -> list:
    """依 where.files 推出閘門逐檔檢查命令（每個命中的套件一條，保宣告順序）。

    declaration_text 為 merge-gate.yaml 內容；None 或空字串回空清單。
    宣告無法解析時拋 GateDeclarationError，由呼叫端決定如何回報。
    """
    import shlex

    commands = []
    for suite in _gate_suites(declaration_text).values():
        if not isinstance(suite, dict):
            continue
        matched = _suite_matches(suite, [str(f) for f in files or []])
        if matched:
            commands.append(shlex.join([str(a) for a in suite["command"]] + matched))
    return commands


_TEST_ACCEPTANCE_MARKERS = ("測試", "E1", "E2")


def requires_red_run(ticket_type, acceptance) -> bool:
    """IMP 票且 acceptance 含測試字樣或 E1／E2 時回傳 True（純函式）。"""
    if ticket_type != "IMP":
        return False
    return any(
        marker in str(item)
        for item in (acceptance or [])
        for marker in _TEST_ACCEPTANCE_MARKERS
    )


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
    isolation: str = "none",
    require_red_run: bool = False,
    test_entries=(),
    gate_checks=(),
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

    pre_commit = (
        GATE_CHECK_CLAUSE.format(commands="；".join(f"`{c}`" for c in gate_checks))
        if gate_checks else ""
    )
    skeleton = SKELETON_TEMPLATE_NORMAL.format(
        ticket_id=ticket_id,
        task_summary=task_summary,
        agent_name=agent_name,
        closing=CLOSING_BY_ISOLATION.get(isolation, CLOSING_BY_ISOLATION["none"]).format(
            ticket_id=ticket_id, agent_name=agent_name, pre_commit=pre_commit
        ),
    )

    if require_red_run:
        skeleton = skeleton.replace(
            _RED_RUN_ANCHOR, f"{RED_RUN_LINE}\n{_RED_RUN_ANCHOR}", 1
        )

    if test_entries:
        entry_line = TEST_ENTRY_LINE.format(commands="；".join(test_entries))
        skeleton = skeleton.replace(
            _RED_RUN_ANCHOR, f"{entry_line}\n{_RED_RUN_ANCHOR}", 1
        )

    if isolation == "worktree":
        skeleton = skeleton.replace(
            _RED_RUN_ANCHOR,
            f"{WORKTREE_SIBLING_TEST_LINE}\n{WORKTREE_CLI_REJECT_LINE}\n"
            f"{WORKTREE_MULTILINE_LINE}\n{_RED_RUN_ANCHOR}",
            1,
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
