#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Bare Commit Guard Hook - PreToolUse Hook

功能: 並行派發期間偵測裸 git commit 與 index-discarding commit
      （-- pathspec / --only / -o），依 staged 範圍安全性判斷 DENY 或放行，
      阻擋跨 ticket 汙染共用 git index；非並行期僅 WARN 提醒（見下方
      「修正」段，index-discarding form 已不再是無條件豁免）。

Hook Event: PreToolUse
Matcher: Bash
Decision: DENY（exit 2，stderr 訊息）| WARN（exit 0，stderr 訊息）| allow（無輸出）

============================================================
背景（0.2.1-W3-276 ANA 裁決，完整回測數據見 ticket Solution）
============================================================
path-limited commit 文字條款（parallel-dispatch / dispatch-template 逐字範例）
四次失效後的機制層防線。8/1-8/4 570 筆 commit 回測：91 筆手動 commit 中
5 筆（agent commit 的 8.6%）為裸 commit 掃入他人 staged 檔案的跨 ticket 汙染，
5 筆事故全部發生在並行派發期間；非並行期裸 commit（PM 單線 bookkeeping）
27.3% 為刻意多 ticket 操作，無害。

三設計題裁決：
1. 觸發條件：並行條件觸發（.claude/dispatch-active.json 有活躍派發才啟用）。
   一律啟用會打斷 PM 33 筆合法裸 commit 中的多數（誤擋成本過高）。
2. 處置等級：並行期 DENY（exit 2）+ 非並行期 WARN（exit 0 + stderr）。
   WARN 對 AI agent 無約束力已四次實證，並行期改 DENY 才有效防護；
   非並行期維持 WARN 不打斷 PM 但仍提供提醒。
3. 豁免通道：三種自然豁免（-- pathspec / --amend / -a｜--all），不設顯式
   marker（marker 有同樣的記憶依賴問題）。【此項第一種豁免已由下方
   「修正」段取代，pathspec 不再無條件豁免，僅保留此段作歷史決策紀錄】

============================================================
探針結論（0.2.1-W3-277 前提驗證）
============================================================
1. dispatch-active.json 時效性：本 session（0.2.1-W3 wave）並行派發下，
   dispatches 陣列在無活躍派發時穩定為 []，未觀察到超時清理（housekeeping
   `cleanup_expired` 90+ 筆日誌中僅 2 筆命中，且皆非本 wave）的異常累積。
   次要觀察：SubagentStop 精準清理（clear_dispatch_by_id）在本 session 樣本
   中命中率偏低，改由 FIFO fallback 或更早的清理路徑處理——此為既有
   dispatch_tracker 機制的已知行為（非本票新增），效果是條目「提早消失」
   而非「殘留過久」，方向上不會導致非並行期被誤 DENY（本票風險項），
   僅可能在極端時序下低估真並行度而降級為 WARN（安全方向，符合 ANA
   本已接受的 ~20% 精確率設計）。
2. CLI auto-commit 不可見性：PreToolUse Bash hook 僅檢視 Bash 工具收到的
   **字面命令字串**（tool_input.command），不追蹤該命令執行時內部產生的
   子行程呼叫。`ticket track complete <id>` 等 CLI 命令字面文字不含
   "git commit"，其內部以 Python subprocess 呼叫 git commit 對本 hook
   結構性不可見（與 bash-git-protected-branch-guard-hook.py 等既有同類
   hook 的偵測模型一致）。本 session 執行歷程本身即為實證：多次
   `ticket track append-log` / `ticket track complete` 呼叫觸發了真實
   auto-commit（git log 可見對應 commit），但從未觸發任何以命令字面文字
   比對為基礎的 Bash git guard。

============================================================
範疇邊界（刻意不做，非遺漏）
============================================================
- 僅偵測 cwd 隱含形式的 `git commit`（含 `git -C <path> commit`），不解析
  子 shell `cd` 形式的目標 repo（與本 hook 的目的無關——本 hook 檢查的是
  「是否夾帶他人 staged 檔案」，非跨 repo 保護分支，無需解析目標 repo）。
- staged 檔案清單一律讀取專案根目錄（get_project_root()）的 git index，
  不解析 `-C <path>` 指向的其他 repo（回測樣本 91 筆手動 commit 皆為
  cwd 隱含形式，此範疇涵蓋實際發現的事故模式）。
- `-a`/`--all` 豁免偵測為全命令字串層級的 token 掃描，非嚴格綁定 commit
  呼叫本身的參數位置。已知殘留：commit message 內容恰好含獨立 ` -a `
  子字串時可能被誤判為豁免（如 `git commit -m "fix -a bug"`）。方向安全
  （誤判方向是「該擋的沒擋」而非「不該擋的被擋」），符合 ANA 對此類邊界
  情境的容忍設計，未進一步處理。同一設計限制延伸至 `_ONLY_FLAG_RE`：
  commit message 內容恰好含獨立 ` -o ` 或 `--only` 子字串（例如訊息中
  提及這兩個 flag 本身）會被誤判為 index-discarding form，觸發時機為
  改動本 hook 這次 commit 本身實際命中（訊息描述 `--only`/`-o` 而觸發
  非並行期 WARN，見 hook-logs 20260819-104331）。方向同樣安全（誤判方向
  是「多一則無害 WARN」而非「該擋的沒擋」），不進一步處理。

============================================================
修正：pathspec / --only / -o 不再是無條件豁免（後續實測回饋）
============================================================
上方「三種自然豁免」的第一種（`-- pathspec`）原始設計把它視為「已限縮
提交範圍」的安全訊號，無條件放行、不留下任何訊息。實測發現此判斷錯誤：
`git commit -- <pathspec>` 與 `--only`/`-o` 語意相同，皆會**丟棄既有
git index**、改以這些路徑當下的 working tree 內容重建臨時 index 後提交，
不是「從 index 中挑選子集」。並行環境下，這會吸入同路徑上其他派發代理人
尚未 stage 的編輯——本 hook 原本要防的是「他人已 staged 的內容被誤吸」，
舊版豁免邏輯卻把語意更危險的「他人未 staged 的內容也被誤吸」整條路徑
排除在防護之外，且不留提醒。已有實際誤吸事故（正確暫存 hunk 後改用
pathspec 提交，誤吸另一並行派發的未 stage 編輯）。

現行邏輯改為：pathspec / `--only` / `-o` 三者視為「index-discarding
form」，與純粹的裸 commit（未帶任何 flag，只提交既有 index 內容）分開
判斷——裸 commit 可用 staged 快照驗證安全性（見
`_staged_scope_is_safe_for_bare_commit`），index-discarding form 無法
如此驗證（提交當下才讀 working tree，staged 快照不代表其實際提交內容），
故並行期間一律 DENY，非並行期間改為 WARN 提醒改用「精確 add + 核對 +
裸 commit」流程。正確寫法詳見
`.claude/rules/core/bash-tool-usage-rules.md` 規則七。

`--amend` 與 `-a`/`--all` 兩種豁免維持不變（防護標的與 pathspec 不同：
前者是修訂既有 commit，後者是明確表態「提交全部 tracked 變更」，皆非
「以為限縮範圍實則丟棄 index」的認知落差來源）。

============================================================
再修正：命令字串誤判——payload 內文被當成真實命令與旗標（後續實測回饋）
============================================================
上方所有偵測函式原本直接對 PreToolUse 收到的**完整原始命令字串**做子字串
／正則比對，無法區分「這是要執行的命令與旗標」與「這只是傳給某個命令的
文字內容（commit message、heredoc 本體、其他命令的引號參數）」。

至少三種真實觸發樣態已重現：

1. 非 git 命令的 heredoc 本體中提及 `git` 與 `commit` 相鄰字樣（例如
   ticket CLI 的 append-log 內文描述本 hook 的攔截對象），使
   `_contains_git_commit` 誤判整條命令為 git commit。
2. 非 git 命令的引號參數內文含相同字樣，同上誤判來源，形式不同（引號
   而非 heredoc）。
3. 真實的 `git commit -m "..."` 呼叫，其 `-m` 訊息內容透過 heredoc 帶入
   且描述本次修正時提及 `--only`/`-o` 字面，使 `_is_index_discarding_form`
   誤判該次真實 commit 為 index-discarding form（本 hook 修正
   pathspec/--only/-o 豁免的那次 commit 本身即實際命中，非 mock，
   hook-logs 有存證）。

修法（初版）：新增 `_strip_command_payload`，在所有偵測函式之前先移除
命令字串中的 heredoc 本體與引號字串內容，只留下骨架文字供偵測。

============================================================
三修正：改採 argv 結構解析，取代自維護的 payload 消除（收斂至共用 lib）
============================================================
上一段「修法（初版）」的 `_strip_command_payload` 是本 hook 自行維護的
字串前處理，與另兩個 Bash git 守衛（bash-git-add-broad-guard-hook.py、
bash-git-protected-branch-guard-hook.py）各自維護的解析邏輯屬於同一類
問題——三處對「什麼算一次 git 呼叫」的定義互不相同，各自留下不同破口。
已收斂至 `.claude/lib/git_command_parse.py` 的 `find_git_invocations()`：
heredoc 剝離（含保底）在該共用函式內部處理；引號內容的問題則由「不再
對原始字串做子字串比對，改為 shlex tokenize 後逐 token 精確比對」從
根本解決——被 shlex 判定為單一引號內 token 的內容，天生不會被拆成獨立
token 誤判為旗標，`_strip_command_payload` 的引號剝離半段因此變得多餘，
一併移除。三個偵測函式改為對 `GitInvocation.args`（token 清單）做精確
比對，機制說明見共用模組 docstring。

============================================================
四修正：不相交放行路徑不再被單筆空 files 派發記錄整體癱瘓
============================================================
`_staged_scope_is_safe_for_bare_commit` 的不相交路徑原本要求「所有」
活躍派發的 `files` 皆非空才驗證（任一派發 files 為空即整條路徑失效、
一律落到不安全）。實測發現此設計會誤擋：一筆 code-review 型派發因
prompt/description 無法解析出 ticket_id，其 dispatch-active.json 記錄
的 files 為空陣列；此時即使 staged 內容與所有其他有效派發宣告完全
不相交（例如提交 ticket metadata），也會被整體判定為不安全並 DENY，
且 DENY 訊息宣稱的放行路徑（二）實際不可達，執行者依訊息指引清理
staged 範圍後仍反覆失敗。

空 files 宣告本身不構成任何人的領地（未聲明範圍即無從主張範圍），故
改為計算聯集時排除空宣告，只用有宣告範圍的派發驗證不相交條件；讀取端
不過濾 dispatch-active.json 本身（該記錄仍供 dispatch_count／orphan
偵測等其他用途使用），僅本函式的範圍判定將其排除，並在存在空宣告時
發出 warning（可觀測性，見 `_staged_scope_is_safe_for_bare_commit` 的
`logger` 參數）。詳細判斷理由見該函式 docstring。

============================================================
五修正：SubagentStop 不再提早清除記錄，dispatch_count 存活語意明確化
============================================================
上方「探針結論」段記錄的「SubagentStop 精準清理（clear_dispatch_by_id）
命中率偏低……效果是條目提早消失」，根因已查明並修復：SubagentStop 的
觸發前提被誤假設為「代理人真正停止才觸發」，實測代理人回合結束後轉入
idle 仍存活、仍可接受訊息並繼續工作。刪除式清理已改為標記式（entry
保留、寫入 `turn_ended_at`），詳見 `.claude/lib/dispatch_tracker.py`
模組 docstring「turn_ended_at 欄位」段。

本 hook 的 `dispatch_count = len(dispatches)` 刻意不檢視 `turn_ended_at`
欄位——並行安全防護採保守存活語意，entry 存在本身即代表「該代理人未被
確認終止」，回合是否結束不改變此判斷（代理人 idle 期間仍可能繼續寫檔）。
不得因保留 entry 使並行判定漂移為「只計入尚在執行回合中的 entry」，那
會讓已轉 idle 但仍存活的代理人重新暴露在本 hook 原本要防的並行汙染
風險下。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
from lib.dispatch_tracker import get_active_dispatches
from lib.git_command_parse import GitInvocation, contains_git_word, find_git_invocations
from lib.git_utils import get_project_root, run_git_command


def _has_amend_or_all_exemption(args: List[str]) -> bool:
    """`--amend` / `-a`｜`--all` 維持無條件豁免，不受本次修正影響。

    短選項組合含 'a' 字元（如 `-am`）比照既有設計視為命中 `-a`；已知
    殘留：訊息本文若恰好含獨立 `-a` 短選項形態的 token（極罕見，通常
    出現在引號內而不會被 tokenize 成獨立 token），方向安全（見模組
    docstring「範疇邊界」段）。
    """
    for tok in args:
        if tok == "--amend" or tok == "--all":
            return True
        if tok.startswith("-") and not tok.startswith("--") and len(tok) > 1:
            if "a" in tok[1:]:
                return True
    return False


def _is_index_discarding_form(args: List[str]) -> bool:
    """偵測 `-- pathspec` / `--only` / `-o`：三者皆丟棄既有 index、改以
    working tree 內容重建臨時 index 後提交，staged 快照無法代表其實際
    提交範圍，故與純 index 的裸 commit 分開判斷（不適用
    `_staged_scope_is_safe_for_bare_commit` 的驗證邏輯）。
    """
    return any(tok in ("--", "--only", "-o") for tok in args)


def _get_active_dispatches_safe(project_root: Path) -> List[Dict]:
    """取得目前活躍派發完整記錄，讀取失敗時保守回傳空清單（fail-open，降級為 WARN）。"""
    try:
        return get_active_dispatches(project_root)
    except Exception:
        return []


def _get_staged_files(project_root: Path) -> List[str]:
    """取得目前 staged 檔案清單，讀取失敗時回傳空清單。"""
    success, output = run_git_command(
        ["diff", "--cached", "--name-only"], cwd=str(project_root)
    )
    if not success or not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _staged_scope_is_safe_for_bare_commit(
    staged_files: List[str], dispatches: List[Dict], logger=None
) -> bool:
    """裸 commit（純 index 提交）的安全性驗證，兩條放行路徑擇一命中即安全：

    1. 子集路徑：staged 內容完整落在某一活躍派發宣告的 `files` 範圍內。
       命中即代表這次提交不可能夾帶「其他」活躍派發的宣告檔案。
    2. 不相交路徑：staged 內容與所有「已宣告範圍」活躍派發（`files` 非空）
       的聯集完全不相交（例如 PM 提交 ticket metadata，內容從不出現在
       任何派發宣告中）。

    files 為空的派發記錄（修正舊版設計，見下方「範圍修正」段）：空宣告
    代表該派發未聲明任何檔案範圍，邏輯上不構成任何人的領地，計算聯集時
    予以排除（不計入 `all()` 判定、不參與 union）。這不會降低對「有宣告
    範圍」派發的保護——子集路徑與不相交路徑檢查的仍是這些派發的完整
    宣告；差異只在於不再讓單一筆空宣告使整個不相交放行路徑對所有人失效
    （實測案例：一筆 code-review 型派發因 ticket_id 無法從 prompt/
    description 解析而 files 為空，導致與其他有效宣告完全不相交的正常
    提交被誤擋）。若排除空宣告後已無任何已宣告範圍（例如所有活躍派發的
    files 皆為空），聯集為空集合，staged 內容對空集合恆為不相交，同樣
    視為安全——這是同一原則（空宣告不構成領地）的自然延伸，非另立特例。

    範圍修正：舊版設計要求「dispatches 非空、且每個派發的 files 皆非空」
    才驗證不相交路徑，任一派發 files 為空即整條路徑失效、必須落到不
    安全。此舉把「無法驗證安全」等同於「必須阻擋」，但空宣告本身不構成
    領地，阻擋的是與空宣告完全無關的內容——防護對象錯置。

    兩條路徑皆不依賴呼叫者身份比對（並行環境下 PreToolUse 拿不到可靠的
    呼叫者身份），只驗證「內容」是否安全。

    staged_files 為空時視為安全（無內容可構成汙染，`git commit` 本身
    亦會因空提交拒絕，不需本 hook 額外處理）。

    已知邊界：兩條路徑驗的都是「宣告的」派發檔案範圍，非「實際」staged
    範圍。若 agent stage 了自己未宣告的檔案，該檔不在任何派發的宣告清單
    內，不相交路徑會誤判為安全。子集路徑本就有相同暴露面，此非本次引入
    的回歸，留待後續處理。

    Args:
        logger: 選填，非 None 時對「存在 files 為空的派發記錄」發出
            warning（可觀測性；記錄本身仍保留在 dispatch-active.json，
            供 dispatch_count／orphan 偵測等其他用途，僅本函式的範圍
            判定將其排除）。
    """
    if not staged_files:
        return True
    staged_set = set(staged_files)

    declared_sets = [set(d.get("files") or []) for d in dispatches]
    known_scope_sets = [declared for declared in declared_sets if declared]

    for declared in known_scope_sets:
        if staged_set <= declared:
            return True

    empty_count = len(declared_sets) - len(known_scope_sets)
    if empty_count > 0 and logger is not None:
        logger.warning(
            "%d 筆活躍派發記錄 files 為空（範圍未知，ticket_id 可能無法"
            "解析），計算不相交聯集時已排除",
            empty_count,
        )

    if declared_sets:
        all_declared = set().union(*known_scope_sets) if known_scope_sets else set()
        if staged_set.isdisjoint(all_declared):
            return True

    return False


def _build_deny_message(staged_files: List[str], dispatch_count: int) -> str:
    """組出裸 commit 的 DENY 訊息：staged 清單未落在任一活躍派發宣告範圍內、
    也與所有活躍派發宣告範圍相交（見 `_staged_scope_is_safe_for_bare_commit`
    兩條放行路徑），指引正確的核對與清理步驟。
    """
    if staged_files:
        staged_block = "\n".join(f"  - {f}" for f in staged_files)
    else:
        staged_block = "  （無法讀取，可能不在 git repo 或無 staged 變更）"

    return (
        "[並行派發期間裸 commit 被阻擋]\n\n"
        f"理由：目前有 {dispatch_count} 個實作代理人正在派發中"
        "（.claude/dispatch-active.json 有活躍記錄），且目前 staged 內容"
        "既非任一活躍派發宣告檔案範圍的子集，也與所有活躍派發宣告範圍的"
        "聯集相交，裸 git commit 會把共用 git index 中可能屬於其他人的"
        "staged 檔案一併提交，造成跨 ticket 汙染。\n\n"
        "當前 staged 檔案：\n"
        f"{staged_block}\n\n"
        "有兩條合法放行路徑：(1) staged 內容完整落在你的派發宣告範圍內；"
        "(2) staged 內容與所有活躍派發宣告範圍完全不相交（例如提交"
        "ticket metadata，內容從不出現在任何派發宣告中）。請先核對並清理"
        "staged 範圍使其命中其中一條，再重新裸 commit（不要改用"
        "`-- <pathspec>` / `--only` / `-o`——那會丟棄 index、改讀"
        "working tree 全文，同樣會吸入他人未 stage 的編輯，危害更大）：\n"
        "  git diff --cached --name-only            # 核對 index 實際範圍\n"
        "  git restore --staged <非本票檔案>          # 逐一移除非本票內容\n"
        '  git commit -m "你的訊息"                   # 核對乾淨後裸 commit\n\n'
        "確需一次提交全部 staged 內容（刻意行為）時，改用：\n"
        '  git commit -a -m "你的訊息"     # 提交所有 tracked 變更\n'
        "  git commit --amend             # 修訂上一筆 commit\n"
    )


def _build_warn_message() -> str:
    """組出非並行期裸 commit 的 WARN 提醒訊息（exit 0，不阻擋）。"""
    return (
        "[提醒] 偵測到裸 git commit。目前無並行派發活躍記錄，本次放行；"
        "建議養成「commit 前先核對 staged 範圍」的習慣，以防未來並行期"
        "誤觸跨 ticket 汙染（不要用 `-- <pathspec>` / `--only` / `-o` 限縮"
        "範圍，那會丟棄 index 改讀 working tree 全文，風險更高）：\n"
        "  git diff --cached --name-only   # 核對 index 只含你的檔案\n"
    )


def _build_index_discarding_deny_message(dispatch_count: int) -> str:
    """組出 index-discarding form（pathspec / --only / -o）的 DENY 訊息。"""
    return (
        "[並行派發期間 pathspec/--only/-o commit 被阻擋]\n\n"
        f"理由：目前有 {dispatch_count} 個實作代理人正在派發中"
        "（.claude/dispatch-active.json 有活躍記錄）。`git commit -- "
        "<pathspec>` 與 `--only`/`-o` 會丟棄既有 index，改以指定路徑當下的"
        "working tree 內容重建臨時 index 後提交——不是從 index 挑選子集，"
        "而是完全繞過 index。並行環境下這會吸入同路徑上其他派發代理人"
        "尚未 stage 的編輯，且無法像裸 commit 一樣用 staged 快照驗證安全性"
        "（提交當下才讀 working tree），故一律阻擋，不提供例外。\n\n"
        "請改用精確 add + 核對 + 裸 commit：\n"
        "  git add <你的確切檔案>\n"
        "  git diff --cached --name-only   # 核對 index 只含你的檔案\n"
        '  git commit -m "你的訊息"        # 裸 commit（不帶 pathspec）\n\n'
        "若裸 commit 仍被本 hook 阻擋，代表 index 混入非本票內容，先用"
        "`git restore --staged <path>` 移除後再重試。\n"
    )


def _build_parse_failure_deny_message(dispatch_count: int) -> str:
    """組出「命令含 git 字樣但無法安全解析」的 DENY 訊息（並行期）。

    無法安全解析時（`find_git_invocations` 回傳 None，見共用模組「失敗
    語意」段），本 hook 無從確認該命令是否為裸 commit 或其安全性，並行
    期間保守阻擋，非並行期改 WARN（見 `_build_parse_failure_warn_message`）。
    """
    return (
        "[並行派發期間裸 commit 被阻擋（命令無法安全解析）]\n\n"
        f"理由：目前有 {dispatch_count} 個實作代理人正在派發中"
        "（.claude/dispatch-active.json 有活躍記錄），且本次命令含 git"
        "字樣，但因未閉合引號等原因無法安全解析其結構，無法確認是否為"
        "裸 commit 或其安全性，故保守阻擋。\n\n"
        "請檢查命令引號是否配對，修正後重試。\n"
    )


def _build_parse_failure_warn_message() -> str:
    """組出「命令含 git 字樣但無法安全解析」的 WARN 訊息（非並行期）。"""
    return (
        "[提醒] 本次命令含 git 字樣，但因未閉合引號等原因無法安全解析其"
        "結構。目前無並行派發活躍記錄，本次放行；請檢查命令引號是否配對，"
        "以防未來並行期無法確認安全性而被阻擋。\n"
    )


def _build_index_discarding_warn_message() -> str:
    """組出非並行期 index-discarding form 的 WARN 訊息（exit 0，不阻擋）。"""
    return (
        "[提醒] 偵測到 `git commit -- <pathspec>` / `--only` / `-o`。"
        "此語法會丟棄既有 index、改讀指定路徑當下的 working tree 內容"
        "提交，不是「從 index 挑選子集」；目前無並行派發活躍記錄，本次"
        "放行，但不建議養成此習慣（未來並行期會吸入他人未 stage 的編輯，"
        "且並行期間本 hook 會直接阻擋此語法）。建議改用：\n"
        "  git add <你的確切檔案>\n"
        "  git diff --cached --name-only   # 核對 index 只含你的檔案\n"
        '  git commit -m "你的訊息"        # 裸 commit\n'
    )


def main() -> int:
    """Hook 主邏輯：並行期 DENY 裸 commit，非並行期 WARN。"""
    logger = setup_hook_logging("bare-commit-guard")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON，放行")
        return 0

    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return 0

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "") or ""

    if not contains_git_word(command):
        logger.debug("命令不含 git 字樣，放行")
        return 0

    invocations = find_git_invocations(command, {"commit"})

    project_root = get_project_root()
    dispatches = _get_active_dispatches_safe(project_root)
    dispatch_count = len(dispatches)

    if invocations is None:
        # 無法安全 tokenize（未閉合引號等）：命令含 git 字樣但結構不明，
        # 並行期保守阻擋、非並行期僅提醒（見兩則 _build_parse_failure_*
        # 訊息函式 docstring）。
        if dispatch_count > 0:
            logger.warning("命令含 git 字樣但無法安全解析，並行期保守阻擋")
            print(_build_parse_failure_deny_message(dispatch_count), file=sys.stderr)
            return 2
        logger.info("命令含 git 字樣但無法安全解析，非並行期 WARN 放行")
        print(_build_parse_failure_warn_message(), file=sys.stderr)
        return 0

    if not invocations:
        logger.debug("命令不含 git commit 呼叫，放行")
        return 0

    # 多語句內含多筆 git commit 呼叫時，僅處理第一筆——沿用本 hook 原始
    # regex 設計的隱含假設（單一命令對應單一相關 commit），無測試涵蓋
    # 多筆呼叫各自獨立判定的情境，範疇邊界非本次收斂目標。
    invocation: GitInvocation = invocations[0]

    if _has_amend_or_all_exemption(invocation.args):
        logger.debug("命令含 --amend / -a｜--all，放行")
        return 0

    if _is_index_discarding_form(invocation.args):
        if dispatch_count > 0:
            logger.warning(
                "並行期 index-discarding commit（pathspec/--only/-o）被阻擋"
                "（活躍派發數=%d）",
                dispatch_count,
            )
            print(_build_index_discarding_deny_message(dispatch_count), file=sys.stderr)
            return 2
        logger.info("非並行期 index-discarding commit，WARN 放行")
        print(_build_index_discarding_warn_message(), file=sys.stderr)
        return 0

    if dispatch_count > 0:
        staged_files = _get_staged_files(project_root)
        if _staged_scope_is_safe_for_bare_commit(staged_files, dispatches, logger=logger):
            logger.info(
                "並行期裸 commit，staged 範圍落在單一派發宣告內，放行"
                "（staged 檔案數=%d）",
                len(staged_files),
            )
            return 0
        logger.warning(
            "並行期裸 commit 被阻擋（活躍派發數=%d，staged 檔案數=%d）",
            dispatch_count, len(staged_files),
        )
        print(_build_deny_message(staged_files, dispatch_count), file=sys.stderr)
        return 2

    logger.info("非並行期裸 commit，WARN 放行")
    print(_build_warn_message(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "bare-commit-guard"))
