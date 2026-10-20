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

============================================================
六修正：-a／--all 豁免並行期收窄為同等內容驗證，DENY 訊息新增派發範圍
        映射與分次提交指令
============================================================
`-a`／`--all` 豁免原為無條件放行、不檢查內容、不分並行期。實測發現：
代理人的 commit 被 `_staged_scope_is_safe_for_bare_commit` 正確 DENY
（staged 跨兩個活躍派發宣告範圍）後，改用「暫存無關檔案 → 帶 -a 的
commit → 還原暫存」繞道完成提交——結果內容雖然無害，但路徑正是守衛
文件明寫的無條件豁免，且與該代理人自身派發骨架（`STAGING_PHRASE_AGENT`）
明文禁止的「DENY 後改用 -a 繞過」直接矛盾：規則文字已收緊到「連 -a
繞過 DENY 都禁止」，守衛判準卻停在「-a 一律無條件放行」，兩者不同步。

現行邏輯：`--amend` 維持無條件豁免（修訂既有 commit，非提交全部
tracked 變更，與本次收窄的風險模型無關）。`-a`／`--all` 在並行期改
套用與裸 commit 相同的兩條放行路徑驗證
（`_staged_scope_is_safe_for_bare_commit`），驗證對象改為 `-a` 實際會
提交的完整集合——staged ∪ unstaged-tracked（`git diff --cached
--name-only` 聯集 `git diff --name-only`，後者不含 untracked 新檔，
因 `-a` 本身也不提交 untracked 檔案）；非並行期維持無條件豁免（既有
裁決精神：一律啟用會打斷合法裸 commit，實測非並行期正常用途存在）。
已知邊界：`--amend` 與 `-a` 同時出現時（`git commit --amend -a`）因
`--amend` 分支判斷順序在前而優先放行，不套用本次收窄——維持既有
`--amend` 無條件豁免語意，非本次引入的新繞道（範圍外，未涵蓋此組合）。

DENY 訊息（裸 commit 與 -a／--all 兩種皆適用）新增「檔案 → 派發
ticket_id」映射表（未落在任何宣告範圍者標「未宣告範圍」）與依映射表
拆分的具體分次提交指令序列，取代原本僅描述抽象放行路徑、不提供可執行
步驟的版本——原版本的放行路徑（二）雖已可達（見「四修正」），但執行者
從訊息本身看不出如何拆分，仍會選擇已知的豁免繞道。

============================================================
七修正：DENY 訊息的代理人數與判定依據脫節、補救指令可能被整段複製誤導
============================================================
兩處獨立缺陷，皆來自後續實測回饋（非本 hook 主修法範疇，與派發記錄殘留
清除無依賴，可獨立先落地）：

1. 裸 commit 與 -a／--all 兩則 DENY 訊息原本印的代理人數取自
   `len(dispatches)`（計入全部活躍派發記錄），但同一次判定實際依據的是
   `_staged_scope_is_safe_for_bare_commit` 內濾掉 `files` 為空者後的
   `known_scope_sets`——訊息宣稱的集合與判定依據的集合不是同一個。實測
   樣本：一批活躍記錄中相當比例 `files` 為空（範圍未知），判定只用了
   有宣告範圍的子集，訊息卻把全部記錄數當成代理人數宣稱。修法：兩則
   訊息改印有宣告範圍的派發數，範圍未知者另行標示於括號內，不併入主要
   數字。`pathspec`/`--only`/`-o` 的 DENY 訊息（`_build_index_discarding_
   deny_message`）不受影響——其決策路徑本身就是「`dispatch_count > 0`
   即一律阻擋」，未經 `known_scope_sets` 過濾即已與訊息數字一致，此為
   刻意不做（見「範疇邊界」段一律阻擋設計），非遺漏。

2. 三則 DENY 訊息（裸 commit、-a／--all、pathspec/--only/-o）的補救
   指令皆以多行區塊呈現，版面暗示可整段複製後串成一個命令（`&&` 或
   分號）執行。本 hook 為 PreToolUse，在整個命令執行前依「當下」的
   git index 狀態判斷；串接執行時，同一命令內尚未發生的 `git add` /
   `git restore` 效果對本次判斷不可見，故串接命令會被同一則訊息再次
   阻擋整串——包括其中的 `git restore` / `git add` 部分，因為 Bash 工具
   本身就沒有執行任何一段。使用者因此不是「少做一步」，而是對自己已
   執行過什麼的認知與事實相反（實測：多次獨立撞到此問題，皆誤以為前面
   步驟已經執行過）。修法：三則訊息的補救指令區塊前皆加一句明示語句，
   說明須逐條分開送出執行、不可用 `&&` 或分號串接。

============================================================
九修正：擁有者 session 已結束（orphan_confirmed）的派發條目不計入佔用（見
_exclude_orphan_confirmed；僅排除確定孤兒，registry 讀取失敗 fail-closed）

八修正：宣告範圍改讀票面現行 where.files，不再以派發快照為準
============================================================
派發記錄的 `files` 是派發當下由 dispatch_tracker 記錄的 where.files 快照。
派發後 `ticket track set-where`（例如檔案改名）不會同步回記錄，新路徑被
判為「未宣告範圍」，只能拆成兩次提交。

修法選擇「hook 改讀票面」，不選「set-where 同步寫 dispatch-active」：
where.files 的寫入路徑不只 set-where（create、`ticket track commit` 對未
宣告檔案的補入、手改票面皆會寫），同步寫入只能補住其中一條，其餘路徑仍
產生同型過期；改讀票面以票面為單一權威，任何寫入路徑自動生效。

做法：`_with_live_declared_files` 在 `main()` 取得派發記錄後，依各筆
ticket_id 讀票面現行 where.files 並取代該筆的 `files`，下游判定與 DENY
訊息不需改動。ticket_id 為空、票檔找不到或 frontmatter 解析失敗時退回
快照並寫 warning，行為與修前相同（不新增 fail-open／fail-closed 路徑）。
不處理：記錄提前被清除（記錄生命週期問題，見「五修正」）；路徑字串解析
（CJK／quotepath）。

============================================================
辨識範疇：commit 呼叫的辨識模型與已知未涵蓋（路由說明）
============================================================
本 hook 以任意位置掃描（scan=True）辨識 commit 呼叫：位置判定之外，另掃
每個語句中的每個 git token。只有掃描命中、沒有位置命中時，辨識不確定，
比照「命令無法解析」處理（見 main() 對 via_scan 的處置）。

掃描仍漏判的封閉類別、各類的偵測承擔者或不承擔的理由、掃描的誤判情境
與改寫方式，統一記於 `.claude/references/bash-tool-usage-details.md`
〈守衛如何辨識 commit：位置判定、任意位置掃描與殘留範圍〉，本 docstring
不重複全文，以免兩處漂移。守衛沒有反應不等於命令符合規則七。

============================================================
模組分工（依職責拆分，本檔保留豁免判定與 main 流程）
============================================================
- `.claude/lib/dispatch_scope.py`：派發登記讀取、宣告範圍以票面為準、
  orphan 排除、commit 目標 checkout 推導與派發條目過濾。
- `.claude/lib/git_operation_state.py`：進行中操作偵測（MERGE_HEAD、
  CHERRY_PICK_HEAD、REVERT_HEAD、rebase 衝突與 edit 停點）與偵測目錄推導。
- `.claude/hooks/bare_commit_guard/staged_scope.py`：staged／unstaged 清單
  讀取與範圍安全性判定。
- `.claude/hooks/bare_commit_guard/messages.py`：全部 DENY／WARN 訊息。
上述模組內的函式於本檔 re-export 原頂層名稱。

失敗語意：hook 以 `run_hook_safely(main, ...)` 包裝，未預期例外為 fail-open
（記錄 traceback、非零非阻擋退出碼，不 fail_closed）；個別偵測失敗的放行或
阻擋方向見各模組 docstring。
"""

import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, resolve_session_id
from lib.dispatch_scope import (  # noqa: F401  re-export 原頂層名稱
    _commit_target_checkout,
    _commit_target_checkouts,
    _exclude_orphan_confirmed,
    _filter_dispatches_for_targets,
    _get_active_dispatches_safe,
    _overrides_git_dir,
    _read_registry_sessions,
    _read_ticket_where_files,
    _with_live_declared_files,
)
from lib.git_command_parse import (
    GitInvocation,
    classify_parse_cause,
    contains_git_word,
    find_git_invocations,
)
from lib.git_operation_state import (  # noqa: F401  re-export 原頂層名稱
    _BLOCKING_OPS,
    _OP_CHERRY_PICK,
    _OP_MERGE,
    _OP_REBASE,
    _OP_REBASE_EDIT,
    _OP_REVERT,
    _OP_UNRESOLVABLE,
    _TARGET_MERGE,
    _TARGET_OTHER,
    _base_dir,
    _merge_in_progress,
    _note_detect_failure,
    _other_operation_state,
    _pending_operation,
    _pending_operation_in_dirs,
    _report_detect_failure,
    _resolve_detect_dirs,
    _resolve_detect_dirs_multi,
)
from lib.git_utils import get_project_root

from bare_commit_guard.messages import (  # noqa: F401  re-export 原頂層名稱
    _build_all_flag_deny_message,
    _build_deny_message,
    _build_dispatch_mapping_block,
    _build_index_discarding_deny_message,
    _build_index_discarding_warn_message,
    _build_merge_in_progress_deny_message,
    _build_parse_failure_deny_message,
    _build_parse_failure_warn_message,
    _build_pending_operation_deny_message,
    _build_rebase_edit_warn_message,
    _build_split_commit_instructions,
    _build_warn_message,
    _commit_instruction_line,
    _dispatch_count_clause,
    _known_scope_dispatch_counts,
    _map_files_to_dispatches,
    _CONTINUE_HINTS,
    _SEQUENTIAL_EXECUTION_NOTICE,
    _UNASSIGNED_LABEL,
)
from bare_commit_guard.staged_scope import (  # noqa: F401  re-export 原頂層名稱
    _get_staged_files,
    _get_unstaged_tracked_files,
    _staged_scope_is_safe_for_bare_commit,
)


def _has_amend_exemption(args: List[str]) -> bool:
    """`--amend` 維持無條件豁免：修訂既有 commit，非提交全部 tracked
    變更，與 `-a`／`--all` 的內容驗證收窄風險模型無關（見模組 docstring
    「六修正」段）。
    """
    return "--amend" in args


def _has_all_exemption(args: List[str]) -> bool:
    """偵測 `-a`／`--all`（含短選項組合，如 `-am`）。

    並行期不再無條件豁免，改由呼叫端（`main()`）套用與裸 commit 相同的
    內容安全性驗證（見模組 docstring「六修正」段）；非並行期維持無條件
    豁免。本函式僅負責偵測旗標是否出現，不含並行期判斷。

    短選項組合含 'a' 字元（如 `-am`）比照既有設計視為命中；已知殘留：
    訊息本文若恰好含獨立 `-a` 短選項形態的 token（極罕見，通常出現在
    引號內而不會被 tokenize 成獨立 token），方向安全（見模組 docstring
    「範疇邊界」段）。
    """
    for tok in args:
        if tok == "--all":
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

    project_root = get_project_root()
    base_dir = _base_dir(input_data.get("cwd"), project_root)
    invocations = find_git_invocations(command, {"commit"}, base_dir, scan=True)
    parse_cause = classify_parse_cause(invocations)
    if invocations and all(inv.via_scan for inv in invocations):
        # 僅任意位置掃描命中（無位置命中）：辨識不確定，比照無法解析處置
        logger.info("commit 呼叫僅掃描命中，比照無法解析")
        invocations = None
    elif invocations:
        invocations = [inv for inv in invocations if not inv.via_scan]

    # 並行期只計入工作位置與本 checkout 相同的條目；舊條目（無 work_checkout）保守計入。
    # 過濾基準是 commit 實際作用的 checkout（-C／cd 後的 effective_dir），非 hook cwd。
    dispatches = _exclude_orphan_confirmed(
        _filter_dispatches_for_targets(
            _get_active_dispatches_safe(project_root),
            _commit_target_checkouts(invocations, logger),
        ),
        project_root,
        resolve_session_id(input_data),
        logger,
    )
    dispatches = _with_live_declared_files(dispatches, project_root, logger)
    dispatch_count = len(dispatches)

    if invocations is None:
        # 無法安全 tokenize（未閉合引號等）：命令含 git 字樣但結構不明，
        # 並行期保守阻擋、非並行期僅提醒（見兩則 _build_parse_failure_*
        # 訊息函式 docstring）。例外：有他方可能待收尾的進行中操作時，
        # 不論並行期與否一律擋（無 -C 資訊，偵測目錄為 payload cwd > root）。
        pending = _pending_operation_in_dirs(
            _resolve_detect_dirs(input_data.get("cwd"), None, project_root), logger
        )
        if pending in _BLOCKING_OPS:
            logger.warning("命令無法安全解析且 %s 進行中，一律阻擋", pending)
            print(_build_pending_operation_deny_message(pending), file=sys.stderr)
            return 2
        if dispatch_count > 0:
            logger.warning("命令含 git 字樣但無法安全解析，並行期保守阻擋")
            print(_build_parse_failure_deny_message(dispatch_count, parse_cause), file=sys.stderr)
            return 2
        logger.info("命令含 git 字樣但無法安全解析，非並行期 WARN 放行")
        print(_build_parse_failure_warn_message(parse_cause), file=sys.stderr)
        return 0

    if not invocations:
        logger.debug("命令不含 git commit 呼叫，放行")
        return 0

    # 進行中操作偵測取「全部目標聯集」，在任何單筆豁免之前完成；
    # 之後逐筆判定，任一筆回 2 即擋（--amend 只豁免該筆）。
    pending = _pending_operation_in_dirs(
        _resolve_detect_dirs_multi(input_data.get("cwd"), invocations, project_root),
        logger,
    )
    rebase_warned = False
    for invocation in invocations:
        if _has_amend_exemption(invocation.args):
            logger.debug("該筆 commit 含 --amend，豁免該筆")
            continue
        if pending == _OP_REBASE_EDIT and not rebase_warned:
            logger.info("rebase edit 停下，WARN 後續行正常判定")
            print(_build_rebase_edit_warn_message(), file=sys.stderr)
            rebase_warned = True
        rc = _judge_invocation(invocation, pending, dispatches, project_root, logger)
        if rc != 0:
            return rc
    return 0


def _judge_invocation(
    invocation: GitInvocation,
    pending: Optional[str],
    dispatches: list,
    project_root: Path,
    logger,
) -> int:
    """單筆 commit 判定鏈（非 --amend）：回 2 阻擋、0 放行（可能附 WARN）。"""
    dispatch_count = len(dispatches)
    if pending in _BLOCKING_OPS:
        if pending == _OP_UNRESOLVABLE:
            logger.warning("覆寫目標無法靜態解析，保守阻擋")
        else:
            logger.warning("%s 進行中，裸 commit 會收尾他方操作，阻擋", pending)
        print(_build_pending_operation_deny_message(pending), file=sys.stderr)
        return 2

    if _has_all_exemption(invocation.args):
        if dispatch_count == 0:
            logger.debug("命令含 -a｜--all，非並行期無條件放行")
            return 0
        staged_files = _get_staged_files(project_root)
        unstaged_files = _get_unstaged_tracked_files(project_root)
        content_files = sorted(set(staged_files) | set(unstaged_files))
        if _staged_scope_is_safe_for_bare_commit(content_files, dispatches, logger=logger):
            logger.info(
                "並行期 -a｜--all commit，staged∪unstaged-tracked 範圍落在"
                "單一派發宣告內，放行（內容檔案數=%d）",
                len(content_files),
            )
            return 0
        logger.warning(
            "並行期 -a｜--all commit 被阻擋（活躍派發數=%d，內容檔案數=%d）",
            dispatch_count, len(content_files),
        )
        print(_build_all_flag_deny_message(content_files, dispatches), file=sys.stderr)
        return 2

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
        print(_build_deny_message(staged_files, dispatches), file=sys.stderr)
        return 2

    logger.info("非並行期裸 commit，WARN 放行")
    print(_build_warn_message(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "bare-commit-guard"))
