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

依適用性排序（首選 pathspec commit，取代原先以 worktree 為首選的排序，理由見各項）：

- **pathspec commit（首選）**：`git commit -m "訊息" -- <路徑...>` 只提交指定路徑，繞過 index 全量提交。對已 staged 的他人檔案**有效隔離**——該形式的提交集合由參數決定，index 中的其他項目不參與，屬結構保證而非操作紀律。原文「仍需注意」的保守表述已由實測推翻（見關聯段實證二）
- **git worktree 隔離**：需要各自 commit 的並行 agent 分配獨立 worktree（`git worktree add`），各自擁有獨立 index。**限制**：對受 runtime 保護而禁止在 worktree 內編輯的路徑（如 Claude Code 對 `.claude/` 的 hardcoded 保護）不適用，該類路徑的並行只能在主 repo 進行，故不能作為通用首選
- **改為單一 commit 者**：並行 agent 只改檔案不 commit，由 PM 在全部完成後統一分票 commit（逐票執行，中間無並行寫入）。代價是 PM 工作量與 ticket body 長時間未 commit 的暴露窗口

### 工具層修法（優於前三項操作層方案）

前三項皆屬操作層，依賴每個執行者記得照做。當污染源是工具印出的建議指令時，正解是修工具：CLI 印出的 commit 建議指令應自帶 pathspec，且其路徑與該次實際 staged 範圍一致。**Why**：預設行為優於文件規範，執行者照工具建議操作是合理行為，把責任推給「應該記得加 pathspec」等於要求所有人抵抗工具的引導。

## 預防措施

- 派發前判斷：本批 agent 是否各自需要 commit？需要且路徑允許 worktree → 用 worktree；需要但路徑受 runtime 保護 → prompt 明示 pathspec commit 形式；不需要 → prompt 要求「只改檔案不 commit，由 PM 收尾」
- 派發 prompt 的 commit policy 須同時涵蓋 `git add` 與 `git commit` 兩階段。**只寫 `git add` 精確路徑不足**——精確 add 之後的裸 commit 仍提交整個 index，而「add 精確」看起來已是完整防護，容易讓條款停在此處
- 已發生時不改寫歷史：內容正確的前提下，rebase 重寫會破壞 ticket body 已引用的 commit SHA；改為在兩票的 Solution 各記一筆「commit 落地備註」交叉指認
- **不要用 `git reset --soft` 事後修正**：在持續有並發 commit 的 repo 上，reset 後到重新 commit 之間存在新的競態窗口，實測出現過「撤銷後變更反而落入他人 commit」的二次事故（見關聯段實證二）。事後修正比事前預防難得多，發現已發生時記錄即可
- Commit 後驗證須錨定在剛完成的那次 commit 本身，不可用 `HEAD` 代稱：並行環境下 `HEAD` 是可變引用，自己 commit 完成後到執行驗證指令之間，若有其他代理人插入新 commit，`HEAD` 已前移，此時驗證看到的是他人 commit 的檔案清單——形態與「自己誤提交了不該提交的檔案」完全相同，容易誘發錯誤的補救動作（reset / amend / revert 他人成果）。正確做法：`git commit` 執行後 stdout 首行印出的短 SHA 直接拿來驗證（`git show --stat <該短SHA>`）。**擷取 SHA 這一步也必須與 commit 同一次呼叫內完成**（如 `git commit -m "..." && git rev-parse HEAD` 一次呼叫取得 SHA 供後續驗證），不可拆成「先 commit，之後另開一次呼叫再 `git rev-parse HEAD`」——後者兩次呼叫之間仍是競態窗口，`rev-parse` 當下的 `HEAD` 可能已被他人 commit 推走，驗證錯了 commit 而不自知（此陷阱已在本次修正過程中實測復現，見「實證三」附註）。實證見「實證三」
- 稽核缺口自覺：本模式為**零錯誤訊息的靜默 race**——commit 成功、exit 0、訊息正常，只有事後比對 diff 才看得出範圍不對。相對地 `index.lock` 競爭有明確錯誤訊息可攔。防護條款通常跟隨「曾被觀察到的失敗」而生，靜默失敗不產生觀察事件，故此類缺口不會自己浮現，需主動稽核

## 變體：檔案級共用（兩票 where.files 指向同一檔案）

### 症狀

- 並行派發 W3-295 與 W3-296 兩票，規格皆指向同一檔案 `.claude/skills/framework-issue/tests/test_framework_issue.py`
- 兩位代理人均遵守本文件「明確路徑 git add」規範
- W3-296 進行中對該檔案新增 33 行測試（`fix_version`/`close_issue` 相關）尚未 commit
- W3-295 較晚對同一路徑執行 `git add tests/test_framework_issue.py && git commit`，commit `0f6e6678` 卻同時包含 W3-296 進行中的 33 行內容
- 內容本身無損（兩者的測試新增都保留在檔案中），但 commit 訊息宣稱 W3-295 的工作，diff 卻含 W3-296 尚未收尾的變更

### 根因

本文件既有解決方案（pathspec commit / 明確路徑 `git add`）處理的是**路徑級隔離**——防止 commit 誤把**其他路徑**的已 staged 內容一併提交。本變體發生在路徑重疊本身：兩票的 `where.files` 指向同一實體檔案，該檔案在共享的 working tree 中被兩位代理人的 Edit 操作依序疊寫。無論哪一方對這個路徑執行 `git add`，add 進 index 的都是「當下磁碟內容」，而磁碟內容此刻已同時含有兩方的編輯——這與原案例（index 誤留他人已 add 但未 commit 的**其他**檔案）機制不同：原案例的解方（precise `git add` + pathspec commit）在此無效，因為問題不在 index 累積範圍之外的檔案，而在**目標檔案本身已是兩方共筆**。

「明確路徑 git add 只提供路徑級隔離」這個判準，對「兩票各自檔案互斥」的並行安全成立，對「兩票共用同一檔案」不成立。

### 解決方案

防護無法在 staging/commit 階段補救（介入時內容已疊寫），必須前移到**派發設計**：

| 方案 | 適用情境 | 代價 |
|------|---------|------|
| 拆分檔案落點 | 兩票內容可切分為互斥的測試檔（如各自獨立檔案，事後視需要合併） | 需額外設計檔案邊界，事後可能需整併 |
| 序列派發 | 兩票對同一檔案的修改各自獨立、不可拆分 | 等待前票 commit 完成後才派後票，喪失並行度 |

能拆分檔案邊界則優先拆分以保留並行度；規格上不可拆（如同一檔案的同一函式集合）則改序列派發。

### 影響邊界

與原案例一致：內容無遺失，遺失的是追溯性。本變體額外確認：即使兩位代理人都完全遵守「明確路徑 git add」的既有防護條款，路徑重疊本身即是防護盲區，非操作紀律可彌補；防護須前移至派發前的 `where.files` 交集檢查（見 `.claude/pm-rules/parallel-dispatch.md`「派發前 where.files 交集檢查」章節）。

## 關聯

- 實證四（檔案級共用變體）：2026-08-05 實驗，詳見上方「變體：檔案級共用」章節
- PC-BAL-007（並行文件票未交叉驗證的事實漂移）：同屬並行派發的副作用家族；該模式風險在**內容**，本模式風險在**版控狀態**
- **姊妹模式（跨 consumer）**：PC-SCLK-005——screen_clock 專案獨立捕獲的同家族模式，兩者互不知情各自命中。PC-SCLK-005 聚焦路徑級隔離的「有效防護：commit 帶精準 pathspec」結論；本文件上方「變體：檔案級共用」章節額外實證，當兩票 `where.files` 指向同一實體檔案時，即使雙方都用精準 pathspec commit 仍會吸收對方尚未收尾的變更——pathspec 只隔離「其他路徑」，對「同一路徑被兩方疊寫」無效。讀 PC-SCLK-005 時應一併參照本文件「變體：檔案級共用」章節，避免誤判 pathspec 為充分防護
- 實證一：flutter_balance 0.2.1-W3-003 / W3-005（2026-07-26），commit `73e4ea3` 標題為 W3-005 收尾、內容全為 W3-003 檔案；W3-005 的原始碼變更早已由其 agent 自行 commit。內容無遺失，僅訊息與內容不符，兩票已交叉記錄
- 實證二：flutter_balance 0.2.1-W3 並行度 11 的批次（2026-08-04），同一批次內三名 agent 各自獨立命中，全數已依當時條款使用精確路徑 `git add`。此批次提供三項新資訊：
  - **污染源定位到工具建議指令**：`ticket track complete` 印出的 metadata sync 建議指令未帶 pathspec，commit `e19664a1` 的訊息逐字符合該建議格式，`git show --stat` 顯示夾帶 12 個檔案（5 張無關 ticket 的 md、4 個框架檔的刪除或改名、1 個 script 修改）。執行者確認即照該建議操作
  - **`git reset --soft` 二次事故**：一名 agent 發現污染後以 `reset --soft` 撤銷，但撤銷到重新 commit 之間與他人的並發 commit 撞期，自己的兩檔變更最終落入對方的 commit。該 agent 判斷「repo 持續有並發 commit，改寫歷史風險大於保留現狀」而未進一步 rebase，此判斷正確
  - **pathspec commit 實測有效**：同批次後續改用 `git commit -m "..." -- <路徑...>` 的 commit 全數乾淨，`git show --stat` 涵蓋範圍與參數一致，無夾帶。原文對 pathspec commit 的保守表述據此修正
- 實證三（驗證步驟本身失效，非 commit 內容污染）：flutter_balance 0.2.1-W3（2026-07-28），PM 提交 worklog（commit `56dbe0e`，1 檔，內容正確無夾帶）後立即執行 `git show --stat HEAD` 驗證，因並行執行的另一位代理人在 PM 的 commit 與驗證之間插入 commit `02811ac`，`HEAD` 已前移，驗證輸出顯示的是該代理人 ticket md 的變更（13 insertions）而非 PM 自己提交的內容；改以 commit 自身印出的短 SHA 查證後才確認 `56dbe0e` 內容正確。與實證一/二不同——此處 commit 內容本身無誤，出錯的是**驗證步驟自己選錯了要檢查的 commit**，且此失效恰好發生在驗證步驟意圖防護的並行情境中，形態上與真正的污染無法區分，靠人工複查才辨明。**同批修正過程中即時復現**（2026-08-04）：撰寫本條修正時，commit 完成後另開一次呼叫執行 `SHA=$(git rev-parse HEAD)`，兩次呼叫之間已有另一代理人插入新 commit，`rev-parse` 取到的是他人 commit 的 SHA；改用 commit 當下 stdout 已印出的短 SHA 直接驗證才正確——證實「擷取 SHA 這一步也必須與 commit 同一次呼叫內完成」並非理論推演，是同一失效模式的變體
- 影響邊界（實證一、二一致）：**不遺失資料，遺失的是追溯性**。內容完整落在 git 歷史中，但 `git log --grep <票號>` 找不到，需 `git log -S` 或逐 commit 比對才能還原歸屬
