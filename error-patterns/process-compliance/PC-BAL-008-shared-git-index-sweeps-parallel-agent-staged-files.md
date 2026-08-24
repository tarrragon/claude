---
id: PC-BAL-008
title: 同 repo 並行 agent 共用 git index，commit 掃入他人已 staged 檔案
severity: medium
category: process-compliance
related: [PC-BAL-007, PC-SCLK-005]
created: 2026-07-26
---

# PC-BAL-008: 同 repo 並行 agent 共用 git index，commit 掃入他人已 staged 檔案

## 症狀

- 並行派發多個 agent 到同一非 worktree repo（各自負責不同檔案，路徑零交集）
- 某方執行 `git add <自己的檔案> && git commit -m "<自己的訊息>"`，commit 卻包含他方的檔案
- commit 訊息與內容不符：標題宣稱 A 票的工作，`git show --stat` 顯示的卻是 B 票的檔案
- 內容本身無遺失也無錯誤，但 commit 歷史的可追溯性受損——後續考古會把 B 票的變更歸因到 A 票
- **工具印出的建議指令即污染源**：完成 ticket 後由 CLI 印出、供操作者複製執行的 commit 指令若未帶 pathspec，操作者照做即觸發本模式。此變體無從靠操作紀律避免——照工具建議做是合理行為

## 根因

`git commit` 提交的是**整個 index**，不是「本次 `git add` 的檔案」。同一 repo 的所有行程共用一份 `.git/index`：

- agent A 完成工作、`git add` 自己的檔案後尚未 commit（或正在寫 ticket body）
- agent B（或 PM）此時執行 `git add <B 的檔案> && git commit`，index 中 A 已 staged 的檔案一併進入該 commit
- 兩者路徑零交集也無法避免——衝突發生在 index 這個共用狀態，不在檔案內容

「檔案路徑零交集即可安全並行」這個判準只對**工作區內容衝突**成立，對 **index 競態**不成立。

## 解決方案

依適用性排序（結構性隔離優先於操作紀律；pathspec commit 已被推翻，見下方「已淘汰」說明）：

- **GIT_INDEX_FILE 隔離索引 + plumbing（首選）**：以 `GIT_INDEX_FILE=<暫存檔>` 環境變數建立與共用 index 完全隔離的臨時 index——`git read-tree <old_head>` 以舊 HEAD 初始化 -> `git add -- <路徑...>` 只在臨時 index 內 stage（範圍嚴格限指定路徑，禁 `-A`）-> `git write-tree` 產生新樹 -> `git commit-tree <tree> -p <old_head> -m "訊息"` 建立 commit 物件（純 plumbing，不呼叫 `git commit`，不需 index）-> `git diff --name-only <old_head> <new_commit>` 自我驗證差異恰為預期路徑集合，不符即放棄 -> `git update-ref HEAD <new_commit> <old_head>` 帶舊值 CAS 移動分支指標，HEAD 於期間被移動則失敗、不覆蓋他人 commit。全程不讀寫共用 index，對「他人已 staged 的其他檔案」與「他人對同一路徑的未 staged 編輯」皆結構性免疫，不存在 TOCTOU 窗口。已於本專案的 PM 端手動 commit 與 `ticket-md-auto-commit-hook.py` 自動 commit 兩條路徑落地並 live-fire 實測（見實證六）
- **git worktree 隔離**：需要各自 commit 的並行 agent 分配獨立 worktree（`git worktree add`），各自擁有獨立 index。**限制**：對受 runtime 保護而禁止在 worktree 內編輯的路徑（如 Claude Code 對 `.claude/` 的 hardcoded 保護）不適用，此時改用上一項 GIT_INDEX_FILE 方案（該方案不依賴 worktree，主 repo 內即可執行）
- **改為單一 commit 者**：並行 agent 只改檔案不 commit，由 PM 在全部完成後統一分票 commit（逐票執行，中間無並行寫入）。代價是 PM 工作量與 ticket body 長時間未 commit 的暴露窗口

### 已淘汰：pathspec commit（`git commit -- <路徑...>` / `--only` / `-o`）

原文（實證二前）曾將此形式列為首選，理由是「只提交指定路徑，繞過 index 全量提交，對已 staged 的他人檔案有效隔離」。`.claude/rules/core/bash-tool-usage-rules.md` 規則七已推翻此結論並明文禁用：`git commit -- <path>` 與 `--only`/`-o` 語意相同，皆以 HEAD 建臨時 index、填入指定路徑的**working tree 內容**、據此 commit，等同丟棄既有 index——不只不隔離他人已 staged 的其他檔案，還會吸入該路徑上他人**未 staged** 的編輯（`--include`/`-i` 則是相反問題：連同 index 中他人已 staged 的檔案一起送出）。

實證二觀察到「同批次全數乾淨」，只覆蓋「他人變更落在不同路徑」的情境；本文件下方「變體：檔案級共用」章節已實證「同一路徑被兩方疊寫」時 pathspec 無效，這是規則七 categorical 禁令所涵蓋根因的其中一種顯現（他人在同一路徑的未 staged 編輯），並非獨立特例。**Action**：pathspec commit 一律禁用，改用上方 GIT_INDEX_FILE 隔離索引方案；本文件「工具層修法」「預防措施」「變體」三節原引用 pathspec 為有效防護之處已同步改寫（見下方）。

### 工具層修法（優於操作層方案）

操作層方案依賴每個執行者記得照做。當污染源是工具印出的建議指令時，正解是修工具：CLI 印出的 commit 建議指令應改採 GIT_INDEX_FILE 隔離索引 + plumbing 形式（見上方「首選」項與實證六），而非僅在裸 commit 後補 pathspec——後者已被規則七禁用。**Why**：預設行為優於文件規範，執行者照工具建議操作是合理行為，把責任推給「應該記得改用隔離索引」等於要求所有人抵抗工具的引導。

## 預防措施

- 派發前判斷：本批 agent 是否各自需要 commit？需要且路徑允許 worktree → 用 worktree；需要但路徑受 runtime 保護（worktree 不適用）→ prompt 明示 GIT_INDEX_FILE 隔離索引 + plumbing 形式；不需要 → prompt 要求「只改檔案不 commit，由 PM 收尾」
- 派發 prompt 的 commit policy 須同時涵蓋 `git add` 與 `git commit` 兩階段。**只寫 `git add` 精確路徑不足**——精確 add 之後的裸 commit 仍提交整個 index，而「add 精確」看起來已是完整防護，容易讓條款停在此處
- 已發生時不改寫歷史：內容正確的前提下，rebase 重寫會破壞 ticket body 已引用的 commit SHA；改為在兩票的 Solution 各記一筆「commit 落地備註」交叉指認
- **不要用 `git reset --soft` 事後修正**：在持續有並發 commit 的 repo 上，reset 後到重新 commit 之間存在新的競態窗口，實測出現過「撤銷後變更反而落入他人 commit」的二次事故（見關聯段實證二）。事後修正比事前預防難得多，發現已發生時記錄即可
- Commit 後驗證須錨定在剛完成的那次 commit 本身，不可用 `HEAD` 代稱：並行環境下 `HEAD` 是可變引用，自己 commit 完成後到執行驗證指令之間，若有其他代理人插入新 commit，`HEAD` 已前移，此時驗證看到的是他人 commit 的檔案清單——形態與「自己誤提交了不該提交的檔案」完全相同，容易誘發錯誤的補救動作（reset / amend / revert 他人成果）。正確做法：`git commit` 執行後 stdout 首行印出的短 SHA 直接拿來驗證（`git show --stat <該短SHA>`）。**擷取 SHA 這一步也必須與 commit 同一次呼叫內完成**（如 `git commit -m "..." && git rev-parse HEAD` 一次呼叫取得 SHA 供後續驗證），不可拆成「先 commit，之後另開一次呼叫再 `git rev-parse HEAD`」——後者兩次呼叫之間仍是競態窗口，`rev-parse` 當下的 `HEAD` 可能已被他人 commit 推走，驗證錯了 commit 而不自知（此陷阱已在本次修正過程中實測復現，見「實證三」附註）。實證見「實證三」
- **不要用反向套用 commit 還原被掃進的內容**：與 `git reset --soft` 同屬事後修正——被掃進的內容與他人同窗口的合法寫入在 diff 上不可區分，還原必然連帶撤銷後者（見關聯段實證六）。發現已發生時只記錄歸屬錯誤；若仍需從共用 index 提交，改用 `GIT_INDEX_FILE` 隔離索引 + plumbing 從源頭避免，而非事後還原
- **核對只驗範圍，不驗版本**：`git diff --cached --name-only` 的輸出正確不代表那些路徑上的內容是最新版——共用 index 的項可能是任意時點的舊暫存狀態（見實證八）。核對通過後若 commit 的 insertions/deletions 量級與預期不符，先查證再繼續，不可因為清單正確就採信結果
- **staged 狀態不可假定跨呼叫存活**：並行代理人依制式句執行 `git restore --staged <非本票檔案>` 時，會一併清掉 PM 或其他 session 已 stage 未 commit 的內容。stage 與 commit 必須在同一次呼叫內完成，或直接改用隔離索引（見實證六）
- 稽核缺口自覺：本模式為**零錯誤訊息的靜默 race**——commit 成功、exit 0、訊息正常，只有事後比對 diff 才看得出範圍不對。相對地 `index.lock` 競爭有明確錯誤訊息可攔。防護條款通常跟隨「曾被觀察到的失敗」而生，靜默失敗不產生觀察事件，故此類缺口不會自己浮現，需主動稽核

## 變體：檔案級共用（兩票 where.files 指向同一檔案）

### 症狀

- 並行派發 W3-295 與 W3-296 兩票，規格皆指向同一檔案 `.claude/skills/framework-issue/tests/test_framework_issue.py`
- 兩位代理人均遵守本文件「明確路徑 git add」規範
- W3-296 進行中對該檔案新增 33 行測試（`fix_version`/`close_issue` 相關）尚未 commit
- W3-295 較晚對同一路徑執行 `git add tests/test_framework_issue.py && git commit`，commit `0f6e6678` 卻同時包含 W3-296 進行中的 33 行內容
- 內容本身無損（兩者的測試新增都保留在檔案中），但 commit 訊息宣稱 W3-295 的工作，diff 卻含 W3-296 尚未收尾的變更

### 根因

本文件既有解決方案（GIT_INDEX_FILE 隔離索引 / 明確路徑 `git add`；pathspec commit 已淘汰，見上方說明）處理的是**路徑級隔離**——防止 commit 誤把**其他路徑**的已 staged 內容一併提交。本變體發生在路徑重疊本身：兩票的 `where.files` 指向同一實體檔案，該檔案在共享的 working tree 中被兩位代理人的 Edit 操作依序疊寫。無論哪一方對這個路徑執行 `git add`，add 進 index 的都是「當下磁碟內容」，而磁碟內容此刻已同時含有兩方的編輯——這與原案例（index 誤留他人已 add 但未 commit 的**其他**檔案）機制不同：原案例的解方（precise `git add` + 隔離索引）在此無效，因為問題不在 index 累積範圍之外的檔案，而在**目標檔案本身已是兩方共筆**。GIT_INDEX_FILE 隔離索引解決的是「共用 index 被他人寫入其他路徑」，對「working tree 上同一路徑已被疊寫」同樣無效——臨時 index 的 `git add` 讀的仍是磁碟上已疊寫的內容。

「明確路徑 git add（含隔離索引形式）只提供路徑級隔離」這個判準，對「兩票各自檔案互斥」的並行安全成立，對「兩票共用同一檔案」不成立。

### 解決方案

防護無法在 staging/commit 階段補救（介入時內容已疊寫），必須前移到**派發設計**：

| 方案 | 適用情境 | 代價 |
|------|---------|------|
| 拆分檔案落點 | 兩票內容可切分為互斥的測試檔（如各自獨立檔案，事後視需要合併） | 需額外設計檔案邊界，事後可能需整併 |
| 序列派發 | 兩票對同一檔案的修改各自獨立、不可拆分 | 等待前票 commit 完成後才派後票，喪失並行度 |

能拆分檔案邊界則優先拆分以保留並行度；規格上不可拆（如同一檔案的同一函式集合）則改序列派發。

### 影響邊界

與原案例一致：內容無遺失，遺失的是追溯性。本變體額外確認：即使兩位代理人都完全遵守「明確路徑 git add」的既有防護條款，路徑重疊本身即是防護盲區，非操作紀律可彌補；防護須前移至派發前的 `where.files` 交集檢查（見 `.claude/pm-rules/parallel-dispatch.md`「派發前 where.files 交集檢查」章節）。

### 實證七（PM 前台在途 vs 派發代理人跨執行體型）

2026-08-18，PM 於前台改寫 `.claude/pm-rules/parallel-dispatch.md` 尚未 commit 期間，另一 session 派發的代理人以同一檔案為標的執行 commit，將前台在途的章節改寫（4 處內容命中）一併吸收，commit 訊息與 ticket 歸屬皆歸於派發側的票，前台已寫入但未 commit 的版本記錄編號亦因此被佔用，需回頭順延。內容未遺失，但變更歸屬錯票。

值得注意的是，該次派發側任務的目的正是收斂「精準 staging 制式句」以防本模式，仍發生同型事件——顯示既有防護對「同一檔案同時被兩個執行體編輯」的場景不足。本條補上與實證四（兩位派發代理人）不同的執行體型態組合：PM 前台在途工作與派發代理人的疊寫，同屬本變體根因（同一檔案在共享 working tree 被兩個執行體依序疊寫），顯示範圍不僅限「兩票皆為派發代理人」的組合，PM 前台自身編輯框架檔案時同樣暴露於此風險。

既有「派發前 `where.files` 交集檢查」條款原僅比對本輪待派發各票、採人工逐項比對，未涵蓋 PM 前台自身在途工作，故未攔截本次事件。該條款已修訂：比對改為強制執行 `ticket track conflicts` CLI（取代人工比對），範圍由「本輪待派發各票」擴大為「當前所有 `pending`/`in_progress` 票」，並要求 PM 前台編輯框架檔案前同樣以 ticket 登記 `where.files` 使其可被涵蓋（見 `.claude/pm-rules/parallel-dispatch.md`「派發前 where.files 交集檢查」章節）。

### 實證八（掃入的是 index 中的歷史殘留，而非他人的最新工作）

2026-08-21，PM 依三要件執行 metadata commit——精準 `git add` 兩個檔、`git diff --cached --name-only` 核對（輸出確認恰為那兩個）、裸 commit。commit `8db456783` 實含 5 檔，其中一張他方票的 md 被寫成 **148 行 / `status: pending` / `priority: P2`**，而該票當時的工作區版本為 **1053 行 / `in_progress` / `P0`**（另一 session 的 P0 票，其代理人正在執行中）。

**本條與實證一至七的分別在於錯的東西不同**：前七條的失效是「commit 含了不該含的路徑」，內容本身是他人當下正確的版本，後果為歸屬錯置、資料不損。本條的失效是「commit 含了該路徑的**過期版本**」——`ticket track complete` 的 auto-stage 在核對之後動作，且它 stage 的是**當時共用 index 中已存在的項**，該項可能是任意時點的舊暫存狀態，而非工作區最新內容。

**三要件對此無效**，因為三者檢查的都是範圍而非版本：清單來源獨立解決「撈到別人的路徑」，`GIT_INDEX_FILE` 解決「寫入共用 index」，`commit-tree` 後的 tree 自檢解決「組出的樹超出預期路徑集」。當錯的是同一路徑上的內容版本時，三者皆通過。

**後果的嚴重性高於前七條**：HEAD 上的內容是錯的而非僅歸屬錯。此時任何以 HEAD 為基準的操作——`git checkout -- <path>`、`git stash`、以 HEAD 為基底的 rebase 或 worktree 建立——都會使工作區的 900 行新內容消失，且該消失不會有任何錯誤訊息。本次未造成損失僅因發現及時（commit 輸出的 `943 deletions` 與預期的兩個 metadata 檔量級不符，觸發查證），並由檔案所有者以隔離索引從工作區前向提交覆蓋修復，未 revert。

同一 session 內另一方回報同型的過期 index 項出現 5 次，前 4 次在 `git restore --staged` 階段被攔下，僅本次進入 HEAD——顯示這不是偶發，而是共用 index 在高並行下的常態狀況，只是多數時候被下游步驟意外攔截。

**候選處置**（尚未定案，由該次事件的三要件收斂票追蹤）：CLI 的 auto-stage 改 stage 工作區當前版本而非沿用 index 既有項；或 CLI 自身改以隔離索引提交、完全不留 staged 狀態；或執行者收到 `[Auto-stage]` 提示時一律先 `git restore --staged` 再依三要件重新提交。第二條從源頭消除 staged 狀態，不依賴執行者記得，與本檔「工具層修法優於操作層」的既有判準一致。

## 關聯

- 實證四（檔案級共用變體）：2026-08-05 實驗，詳見上方「變體：檔案級共用」章節
- 實證七（PM 前台在途 vs 派發代理人跨執行體型）：2026-08-18 案例，詳見上方「變體：檔案級共用」章節
- 實證八（過期 index 項進入 HEAD）：2026-08-21 案例，詳見上方同名章節——與前七條的分別在於錯的是內容版本而非路徑範圍，三要件對此無效
- PC-BAL-007（並行文件票未交叉驗證的事實漂移）：同屬並行派發的副作用家族；該模式風險在**內容**，本模式風險在**版控狀態**
- **姊妹模式（跨 consumer）**：PC-SCLK-005——screen_clock 專案獨立捕獲的同家族模式，兩者互不知情各自命中。PC-SCLK-005 曾聚焦路徑級隔離的「commit 帶精準 pathspec」結論，該結論與本文件原文同源，已被 `.claude/rules/core/bash-tool-usage-rules.md` 規則七推翻（見上方「已淘汰」說明：pathspec commit 會吸入指定路徑上他人未 staged 的編輯，非有效防護）；本文件上方「變體：檔案級共用」章節額外實證，當兩票 `where.files` 指向同一實體檔案時，即使雙方都用精準 pathspec commit 仍會吸收對方尚未收尾的變更，是規則七禁令根因的具體顯現之一。讀 PC-SCLK-005 時應一併參照本文件「已淘汰」與「變體：檔案級共用」兩章節，避免誤判 pathspec 為有效或充分防護
- 實證一：flutter_balance 0.2.1-W3-003 / W3-005（2026-07-26），commit `73e4ea3` 標題為 W3-005 收尾、內容全為 W3-003 檔案；W3-005 的原始碼變更早已由其 agent 自行 commit。內容無遺失，僅訊息與內容不符，兩票已交叉記錄
- 實證二：flutter_balance 0.2.1-W3 並行度 11 的批次（2026-08-04），同一批次內三名 agent 各自獨立命中，全數已依當時條款使用精確路徑 `git add`。此批次提供三項新資訊：
  - **污染源定位到工具建議指令**：`ticket track complete` 印出的 metadata sync 建議指令未帶 pathspec，commit `e19664a1` 的訊息逐字符合該建議格式，`git show --stat` 顯示夾帶 12 個檔案（5 張無關 ticket 的 md、4 個框架檔的刪除或改名、1 個 script 修改）。執行者確認即照該建議操作
  - **`git reset --soft` 二次事故**：一名 agent 發現污染後以 `reset --soft` 撤銷，但撤銷到重新 commit 之間與他人的並發 commit 撞期，自己的兩檔變更最終落入對方的 commit。該 agent 判斷「repo 持續有並發 commit，改寫歷史風險大於保留現狀」而未進一步 rebase，此判斷正確
  - **pathspec commit 實測有效（後續被規則七推翻）**：同批次後續改用 `git commit -m "..." -- <路徑...>` 的 commit 全數乾淨，`git show --stat` 涵蓋範圍與參數一致，無夾帶。原文對 pathspec commit 的保守表述據此修正為「首選」；此結論只驗證了「他人變更落在不同路徑」的情境，未觸及「他人在同一路徑的未 staged 編輯」，`.claude/rules/core/bash-tool-usage-rules.md` 規則七已就後者將 pathspec commit 列為禁令（見上方「已淘汰」章節），本條實證的歷史敘述保留，「首選」結論不再適用
- 實證三（驗證步驟本身失效，非 commit 內容污染）：flutter_balance 0.2.1-W3（2026-07-28），PM 提交 worklog（commit `56dbe0e`，1 檔，內容正確無夾帶）後立即執行 `git show --stat HEAD` 驗證，因並行執行的另一位代理人在 PM 的 commit 與驗證之間插入 commit `02811ac`，`HEAD` 已前移，驗證輸出顯示的是該代理人 ticket md 的變更（13 insertions）而非 PM 自己提交的內容；改以 commit 自身印出的短 SHA 查證後才確認 `56dbe0e` 內容正確。與實證一/二不同——此處 commit 內容本身無誤，出錯的是**驗證步驟自己選錯了要檢查的 commit**，且此失效恰好發生在驗證步驟意圖防護的並行情境中，形態上與真正的污染無法區分，靠人工複查才辨明。**同批修正過程中即時復現**（2026-08-04）：撰寫本條修正時，commit 完成後另開一次呼叫執行 `SHA=$(git rev-parse HEAD)`，兩次呼叫之間已有另一代理人插入新 commit，`rev-parse` 取到的是他人 commit 的 SHA；改用 commit 當下 stdout 已印出的短 SHA 直接驗證才正確——證實「擷取 SHA 這一步也必須與 commit 同一次呼叫內完成」並非理論推演，是同一失效模式的變體
- 實證五（核對步驟與 commit 之間的殘留競態）：flutter_balance 0.2.1-W3（2026-08-21），PM 依 `agent-dispatch-template.md`「精準 staging 制式句」執行——`git add` 兩個 ticket metadata 檔後，以 `git diff --cached --name-only` 核對 index，輸出確認只含該兩檔；隨即裸 `git commit`，stdout 卻回報 `3 files changed`。`git show --stat 377bbc59a` 確認第三檔為並行代理人的測試檔，該代理人在 PM 核對通過之後、`git commit` 之前完成自己的 `git add`。此條補上前四項實證未涵蓋的一環：**制式句的第二道防線（核對 index 範圍）本身有 TOCTOU 窗口**——核對通過不代表 commit 當下範圍仍相同，兩個動作之間 index 是全域共用且可被他人寫入的。前四項實證處理的是「精確 add 不足」與「驗證選錯 commit」，皆未觸及核對與提交之間的時間差。內容正確且測試通過，依 quality-baseline 規則 6 未回退；結構性處置（每個代理人以 `GIT_INDEX_FILE` 取得獨立 index，或改用 worktree 隔離）另由 ticket 追蹤
- 實證六（反向套用還原撤銷他人合法寫入）：flutter_balance 0.2.1-W3 並行批次（2026-08-21），代理人 commit `260c12a30` 被掃進同儕 session 代理人在同一窗口內執行 `ticket track complete` 寫入的 frontmatter 終態（status / completed_at），代理人以 `f28792c33`、`2b910fade` 兩個「反向套用」commit 將非本票內容原樣反轉，淨效果是**同儕的完成狀態被撤銷**（同儕重新 complete，`3d7ed58a5`）。此條補上與實證二同型的另一面：實證二是「撤銷後變更落入他人 commit」，本條是「撤銷把他人合法變更一併撤掉」。機制：被掃進的「誤吸髒資料」與「他人在同一窗口的合法寫入」在 diff 上不可區分，任何事後還原都必然波及後者。同批次另觀察到：制式句「`git restore --staged <非本票檔案>`」對 PM 自己已 stage 未 commit 的內容同樣生效，PM 的 staged 狀態在有並行代理人時不可假定存活到下一次呼叫。PM 端改以 `GIT_INDEX_FILE=$(mktemp)` + `read-tree HEAD` + `update-index --add <exact>` + `write-tree` + `commit-tree -p HEAD` + `update-ref refs/heads/main <new> <old>` 提交（`36d18cb48`、`3c665717e`、`e614fa1bf`），全程不觸碰共用 index，三次皆正確；匯流 ticket 見該專案 W3-774
- 影響邊界（實證一、二一致）：**不遺失資料，遺失的是追溯性**。內容完整落在 git 歷史中，但 `git log --grep <票號>` 找不到，需 `git log -S` 或逐 commit 比對才能還原歸屬
