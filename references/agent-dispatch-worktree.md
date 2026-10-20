# Agent Dispatch Template（worktree 派發政策）

> **用途**：派發 prompt 情境與政策詳解之一：worktree 派發政策（唯讀豁免、base 同步、快照過舊防護）。
>
> **同族檔**：`agent-dispatch-closeout.md`、`agent-dispatch-testing.md`、`agent-dispatch-worktree.md`、`agent-dispatch-pm-edit.md`、`agent-dispatch-variants.md`。原檔 `agent-dispatch-template.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
## 唯讀派發豁免 worktree 強制（0.2.1-W3-269，框架 issue 36）

> **用途**：派發實作代理人執行**唯讀規劃/分析階段**（如 TDD Phase 3a 只讀不寫）時，prompt 首行宣告 `Dispatch-Mode: readonly` 可豁免 worktree 強制，不需先建立/切換 worktree 即可派發。
>
> **權威來源**：完整判準（聲明方式三條件 AND、反例、關鍵字豁免已移除、與 Agent 工具 `dispatch_mode` 參數失效的實測結論）見 `.claude/pm-rules/worktree-operations.md`「唯讀派發豁免 worktree 強制」節；本節僅提供派發 prompt 骨架速查。

**聲明方式**：prompt **首行**（strip 後第一行，非文中任意位置）逐字寫 `Dispatch-Mode: readonly`：

```markdown
Dispatch-Mode: readonly

Ticket: {ticket_id}

## 任務

{一句話動作描述，僅唯讀規劃/分析內容}

讀取 ticket：`ticket track full {ticket_id}`
認領：`ticket track claim {ticket_id} --as {agent_name}`
```

**禁止**：本次派發若涉及任何 Edit/Write（即使小改），不得使用本宣告——宣告後 hook 判定放行、不建 worktree，若代理人實際寫入檔案，寫入會直接落在派發當下的 cwd，可能污染主 repo 或既有 worktree。

**適用情境速查**：

| 情境 | 是否可用 |
|------|---------|
| TDD Phase 3a（實作策略規劃，產出虛擬碼/流程圖，不動實際程式碼） | 可用 |
| 唯讀審查、純分析報告 | 可用 |
| 任何會 Edit/Write 檔案的派發 | 不可用 |
| 外部（非本專案）`.claude/` 路徑 | 不可用（不受本豁免影響，判斷序列中先於本豁免被阻擋） |
| Agent 工具 `dispatch_mode: "readonly"` 結構化參數 | 無效——CC runtime 剝離 Agent tool_input 自訂欄位，唯一有效聲明方式是本節的 prompt 首行文字 |

**與既有審查模式豁免（W10-084）的關係**：關鍵字豁免已移除，審查派發唯一路徑為首行宣告。理由：實作票收尾標準用語「Phase 4 評估」必然命中子字串，守衛失效方向為放行；改為未宣告即阻擋。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

---

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
## worktree 派發 base 同步指引（W1-035）

> **用途**：派發 `isolation: "worktree"` agent 時，在 prompt 加入 base 同步指引，使 agent 開始工作前先將 worktree merge 至最新 main。
>
> **設計依據**：cc runtime `isolation:worktree` 以派發瞬間 main HEAD 為快照、不後續同步；worktree 共享 git object store，可在 worktree 內直接 merge main 取得最新內容。
>
> **前提**：本指引假設 agent 在 auto-worktree 內完成所有工作（file ops + ticket CLI）。禁止 `isolation: worktree` + prompt 導向另一個外部 worktree 的組合派發——該模式導致 ticket CLI 寫入與 code changes 分裂到不同分支（ghost commits）。替代方案見 `.claude/pm-rules/parallel-dispatch.md`「Redirect 派發反模式禁令（W1-016）」。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

### cc runtime worktree base 選擇邏輯（實證歸納）

> **說明**：以下為實證觀察歸納，非 harness 原始碼分析。cc runtime 為閉源，此段反映多次派發觀察的行為模式，非官方文件保證。
>
> **Consequence**：base 建立後主 repo 新增的 commit 不反映到 worktree，agent 以過時檔案為基礎工作，產出與 main 新增 commit 不相容的變更，需手動整合。
>
> **Action**：每次 worktree 派發在 prompt 加入 `git merge main` 指引（見下方「prompt 插入範本」）。

| 行為 | 實證描述 |
|------|---------|
| base 選取時機 | cc runtime 在 **PM 觸發派發的瞬間**，以當時 main HEAD commit 為 worktree base |
| 後續同步 | base 建立後**不後續同步** main；main 新增 commit 不會自動反映到 worktree |
| 觸發案例（W1-048.4.1） | PM 派發 thyme（isolation=worktree）時，main HEAD 為 W4-002；W1-047.1 / W1-048.x 的新增 commit 不在 worktree，agent 以舊檔案為基礎工作 | <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
| git object store | worktree 與主 repo **共享** git object store（bare repository 設計），可在 worktree 內直接執行 `git merge main` 取得主 repo 已 commit 的內容 |
| 何時會落差最大 | 高 commit 頻率的 Wave（PM 或其他 agent 持續 commit main）；base 初始時間越早落差越大 |

**結論**：stale base 是 cc runtime worktree 的系統性行為，**每次** isolation:worktree 派發都可能遇到，落差大小取決於派發前主 repo 的 commit 活躍度。**Action**：方案 B（prompt 加 base-stale 處理 step）可覆蓋全部落差，見下方「三方案評估與選定理由」。

### 三方案評估與選定理由

| 方案 | 說明 | 優點 | 缺點 |
|------|------|------|------|
| A：PM 派發前 commit gate | PM 派發前確認 main HEAD 已 commit（無 uncommitted 變更） | 縮小初始落差 | 無法防止「派發後 main 新增 commit」的後半段落差；PM 多一步操作但 agent 不受保護 |
| B：prompt 中加 base-stale 處理 step | prompt 開頭加 `git merge main` 指引，agent 執行後對齊 | 覆蓋全部落差（包含派發前與派發後）；agent 端自律；prompt snippet 可複製；不依賴 PM 手動判斷 | 需要每次 worktree 派發的 prompt 都加入，若漏加則失保護 |
| C：hook 在 worktree 建立後自動 merge main | PostToolUse hook 偵測 worktree 建立，自動執行 merge | 無需修改每個 prompt；全自動 | hook 無法可靠偵測 cc runtime 建 worktree 的時機（cc runtime 建 worktree 屬內部機制，非本地 shell command）；hook 與 cc runtime 時序競爭難以保證 merge 在 agent 工作前完成 |

**選定方案：B（prompt 中加 base-stale 處理 step）**

理由：B 覆蓋範圍最完整（初始落差 + 派發後 main 新增 commit 的落差均覆蓋），agent 端可自律執行，成本為每次 prompt 多一行 git merge 指引。對比：A 只縮小初始落差，無法防止派發後主 repo 新增 commit；C 在 cc runtime 閉源環境難以可靠偵測 worktree 建立時機，hook 與 cc runtime 時序競爭難以保證。A1（PM 派發前 commit gate）作為輔助防護與 B 並用（見「與派發前 commit gate 的關係」）。

### 觸發條件

| 情境 | 是否插入指引 |
|------|------------|
| `isolation: "worktree"` 背景派發 | 強制 |
| 非 worktree 派發（主 repo cwd） | 不需要（無 base 落差問題） |
| 純查詢類 agent（無 ticket create、無檔案寫入） | 可省略（stale base 不影響唯讀操作） |

### prompt 插入範本

**Why worktree 可直接 merge main**：worktree 與主 repo 共享 git object store（bare repository 設計），主 repo 已 commit 的內容可直接透過 `git merge` 取得，無需額外 fetch 或網路操作。

在 worktree 派發 prompt 的「## 任務」或「## 執行」段開頭，加入：

```markdown
開始工作前先同步 worktree base：執行 git merge main（worktree 共享 git
object store，可直接 merge），確認本地檔案為最新 main 後再開始工作。
```

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
### 環境前置欄位（0.2.1-W3-274，框架 issue 46）

> **用途**：worktree 派發 prompt 補「環境前置」選填欄位，載明 worktree 是 git 層隔離、非 git 狀態不隨之而來的事實，並指引該狀態的具體補齊命令應寫在哪裡。

**Why**：worktree 只複製 git 追蹤的內容；`.gitignore` 排除的建置產物、依賴目錄等執行測試/建置所需的狀態不會隨 worktree 建立出現，需另外執行專案特定的補齊命令才能還原。這類命令屬於 consumer 專案知識（依語言/框架/套件管理器而異），**框架層不寫任何具體命令字面**——寫了就只對當下這個 consumer 準確，對其他 consumer 反而失準；框架層能提供的是「標準載明位置」這個機制本身。

**Consequence**：派發模板缺這個欄位時，consumer 沒有標準位置放置這類知識，代理人各自摸索補齊方式，成功與否取決於個別代理人是否碰巧試出正確命令，同一問題在不同代理人間重複發生而無人留下可複用記錄（框架 issue 46 症狀一實證：四個代理人三個撞牆且回報各異）。

**Action**：worktree 派發 prompt 視需要補以下欄位：

```markdown
## 環境前置（如適用）

worktree 建立後、執行測試/建置前，先依 {專案層文件路徑，如 CLAUDE.md
對應章節或 scripts/<script-name>} 執行前置命令，補齊 gitignore 排除的
建置狀態。
```

填寫指引：

| 項目 | 要求 |
|------|------|
| 命令來源 | 指向專案層文件（`CLAUDE.md` 對應章節或專案 `scripts/`），不在 prompt 或本模板寫死具體命令字面 |
| 何時填 | 該專案存在 worktree 不含但測試/建置依賴的非 git 狀態時（如依賴安裝、建置快取還原） |
| 何時可省略 | 專案無此類前置需求，或本次派發不涉及測試/建置執行 |

**consumer 落地位置**：具體命令記錄於專案層（`CLAUDE.md` 或 `scripts/`）；框架層對「worktree 不含哪些狀態」的概念說明見 `.claude/skills/worktree/SKILL.md`「worktree 不含的狀態」節。

**與 base 同步指引的邊界**：本節與上方「cc runtime worktree base 選擇邏輯」處理不同層面的落差——base 同步是「git 追蹤內容落後 main 多少個 commit」（`git merge main` 可解），環境前置是「git 完全不追蹤的內容從未存在於任何 worktree」（merge 無法解，需另外執行安裝/還原命令）。兩者可能同時發生，prompt 需分別涵蓋。

### 與派發前 commit gate 的關係

A1（PM 派發前 commit gate，見 `.claude/pm-rules/behavior-loop-details.md`「派發前檢查：worktree base 同步」）與本指引（B1）為互補防護：A1 在派發前縮小 base 初始落差，B1 在 agent 端補平派發後新增的落差。A1 是一次 `git status`、B1 是 prompt 內一行 `git merge` 指引，相對於 base 落差累積後的手動整合成本，兩者投入都小；並用可覆蓋派發前與執行中兩個時間窗。

### 派發前 origin 同步驗證（PC-154 前置 1 延伸）

> **Why**：A1 只檢查本機有無 uncommitted 變更，未驗證本機 main 是否已 push 到 origin。PC-154 前置 1 已記錄 worktree base 在部分觀測中反映「較早的 checkpoint 或 origin/main」而非本機 main HEAD；PM 本 session 新建/修改的 ticket commit 若尚未 push，origin 落後，agent 進入 worktree 讀到舊票況會誠實回報「Ticket 不存在」——此訊息易誤診為打錯票號，實為 record-plane（agent 所見 origin 舊態）與 world-plane（本機 HEAD 有票）漂移（`tool-output-trust-rules` 規則 5）。
>
> **Action**：派發任何 `isolation: "worktree"` 實作 agent 前，除 A1 `git status --porcelain` 外，再執行 `git push origin main`（確認 `git rev-list --left-right --count origin/main...main` 為 `0 0`）。收到 agent 回報「Ticket 不存在」時，先查 `git log origin/main..main` 是否有未 push 的票 commit，而非直接懷疑票號打錯。完整前置條件表見 `.claude/error-patterns/process-compliance/PC-154-worktree-dispatch-prerequisites-not-verified.md`「前置 1：worktree base 含所需檔案」。

### worktree 派發收尾指引：complete 由 PM 於合併後執行

> **用途**：worktree 隔離派發（`isolation: "worktree"`）的收尾段，代理人止於 worktree commit 並回報 PM；`ticket track complete` 由 PM 於合併並驗證後在主 checkout 執行（用戶裁決，2026-10-14）。
>
> **設計依據**：平台對隔離代理人的 `complete` 條件性阻擋（argv 逐元素 basename 比對撞上 bash builtin `complete`）；曾以別名 `ticket track finish` 避開（finish 同樣經 acceptance-gate 驗收），但隔離代理人在合併前收尾，會讓票面在程式碼未進 main 時即為完成。`finish` 別名仍存在於 CLI，但不再是隔離代理人的收尾路徑。

**Why**：complete 發生在 PM 合併與測試之後，票面完成狀態才與 main 上的程式碼一致；自檢仍由執行期的代理人經 `append-log` 撰寫（寫入主 repo 票面），PM 收尾只執行 complete，證據來源不變。

**Consequence**：派發 prompt 若仍指示隔離代理人執行 `complete` 或 `finish`，`complete` 會被平台擋下而阻塞，`finish` 能通過但讓票面在合併前即為完成；PM 代填自檢則破壞「執行期的代理人才是自檢正確供給側」的設計原則（見上方「收尾義務標準段」章節 Why）。

**Action**：

| 派發位置 | 代理人收尾段 | complete 執行者 |
|---------|------------|----------------|
| `isolation: "worktree"` | `set-acceptance` 勾選 → `append-log` 填 Solution（含 `### 自檢結果與 Phase 4 評估`）與 Test Results → `ticket track commit <id> -m "..." --worktree <路徑> -- <檔案>` → 回報 PM；不執行 complete 與 finish | PM，合併並驗證後於主 checkout 執行 |
| 主 repo cwd（`isolation: "none"`） | 沿用 `agent-dispatch-closeout.md`〈收尾義務標準段〉的既有收尾段，末步 `ticket track complete <id> --as <自身 agent 名稱>` | 代理人 |

PM 收尾步驟與身份：

```bash
# 合併 worktree 分支並確認測試通過後，於主 checkout 執行
ticket track set-who <ticket-id> --current rosemary-project-manager
ticket track complete <ticket-id> --as rosemary-project-manager
```

`set-who` 使 who.history 保留實作者與交接時間、Executing Agent 欄保留實作者，who.current 記錄收尾者。PM 只執行 complete，不代填自檢。身份做法的比較與依據見 `.claude/references/agent-definition-standard-details.md`〈隔離派發的收尾界線〉。上方「收尾義務標準段」與「收尾 --as 全覆蓋」章節的範例套用於隔離派發時，刪去末步 complete 即可。

---

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
## worktree 快照過舊防護（W2-007）

> **用途**：session 中途新建 ticket / 檔案後才派發 `isolation: "worktree"` agent 時，prompt 第 0 步強制驗證與同步，並在阻塞回報後正確判斷是重派新 agent 還是 SendMessage 恢復舊 agent。
>
> **與「worktree 派發 base 同步指引（W1-035）」的差異**：W1-035 提供通用的 `git merge main` 指引；本節針對 W2-007 兩次獨立觀測補兩項更精確的防護——(1) merge 後另加 ls/grep 驗證目標檔案確實存在，不只信任 merge 指令本身成功；(2) 阻塞回報後的恢復方式判準（重派 vs SendMessage），W1-035 未涵蓋此決策點。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
### 機制定性（W2-007 實證）

isolation worktree 以**session 起始快照**建立，非派發當下的 main HEAD。W2-006 首派與二派兩個 worktree 皆停在 session 起始 commit，落後 main 5 個以上 commit；三派在 prompt 第 0 步加 `git merge main --no-edit` 後成功完成（13/13 測試綠）。快照過舊在該次觀測中 2/2 重現，merge main 防護 2/2 有效（含 W2-005 代理人自主採用）。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

**Why**：session 起始快照機制是 cc runtime 行為，PM 無法從外部改變；session 中途建立的 ticket / 檔案對此後派發的 worktree agent 不可見，agent 會誤判「ticket 不存在」。

**Consequence**：不加防護時，agent 依落後快照工作會回報找不到 ticket（實際 main 已有），造成誤判阻塞並浪費一次派發回合；若 agent 未停手而是憑舊快照猜測繼續，則產出會建立在過時檔案上，需事後整合。

**Action**：

1. session 中有新增 commit（新建票、新檔案）之後才發起的 `isolation: "worktree"` 派發，prompt 第 0 步強制：

```markdown
第 0 步：執行 git merge main --no-edit（worktree 共享 git object store，可直接取得最新 main）。
merge 後執行 ls <目標檔案路徑> 或 grep 確認本 ticket 相關檔案已存在，
確認無誤後再開始執行任務；若檔案仍不存在，停手回報而非猜測繼續。
```

2. 此步驟疊加在既有「worktree 派發 base 同步指引（W1-035）」的 `git merge main` 指引之上，補的是 merge 之後的**顯性驗證**（ls / grep），不是取代 merge 本身。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

### 阻塞回報後：重派新 agent 優先於 SendMessage 恢復

**原則**：worktree 不在就重新派發新 agent，不以 SendMessage 恢復。

**射程**：標題沿用初版情境名，射程以本段為準。本段是所有「對已回報過的 `isolation: "worktree"` 代理人再送工作」路徑的共同前置判準，不限快照過舊。涵蓋：阻塞回報後恢復、審查退回後請同一代理人修正、NeedsContext 補料後恢復、idle 代理人續用於另一張票、超時後 SendMessage 催促。各路徑的段落只路由到此處，不各自重述判準。

**前提事實**（實測）：以 `isolation: "worktree"` 派發的代理人，若第一輪沒有任何變更，其 worktree 與分支在完成通知送達時被 runtime 自動清除；此後以 SendMessage 恢復，代理人的工作目錄落回主 repo 的 main，不報錯。對照組：第一輪已有 commit 的代理人，worktree 保留，恢復後仍在原 worktree。

**Why**：恢復後的代理人仍持有原 prompt 脈絡，自認身處隔離環境；實際上 Edit、`git mv`、`git add` 直接進入共用 working tree 與共用 index，無明顯錯誤訊息。

**Consequence**：branch-verify-hook 只在 commit 時攔下，攔下之前的寫入與暫存已生效，任何 session 的裸 commit 都可能吸入；此偏差不易從代理人回報文字察覺。

**Action**：恢復或續用之前，先以下列兩個判斷訊號確認 worktree 仍在；訊號指出不在，或兩個訊號都取不到，直接重新派發新 agent（前一輪脈絡先寫回 ticket），不恢復。

| 判斷訊號 | 讀法 |
|---------|------|
| 上一輪完成通知是否帶 `worktreePath`（及 `worktreeBranch`）欄位 | 有欄位：worktree 保留。無欄位：該輪無變更，worktree 已清除（實測：有 commit 的代理人通知帶此欄位，無變更者不帶） |
| `git worktree list` 是否列出含該 agent id 的 worktree | 有列出：仍在。未列出：已清除 |

兩個訊號結論不一致時（例如通知帶 `worktreePath`，但 `git worktree list` 未列出），以 `git worktree list` 為準：它反映當下現況，完成通知只是當時的快照。

| 情境 | 判準 |
|------|------|
| 任一恢復或續用路徑，兩個訊號顯示 worktree 仍在 | 可用 SendMessage 恢復或續用 |
| 任一恢復或續用路徑，worktree 不在 | 重派新 agent（新 worktree 會以較新快照建立），不用 SendMessage |
| agent 因快照過舊回報阻塞（未產生變更） | 屬上一列的特例：worktree 已清除，重派 |
| 兩個訊號都取不到（例如完成通知已不在 context，且 `git worktree list` 執行失敗） | 直接重派，不恢復 |

**Source**：0.3.6-W2-007（ANA，兩次獨立觀測 + W2-006 三次派發自然對照組）。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

---
