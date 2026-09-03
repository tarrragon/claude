---
id: PC-BAL-045
title: 產出未落地被記載為 process 已結束，殭屍代理人無人回收
severity: 中
category: process-compliance
related: [PC-BAL-013, PC-BAL-015, PC-166]
created: 2026-08-18
---

# PC-BAL-045: 產出未落地被記載為 process 已結束，殭屍代理人無人回收

## 基本資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-BAL-045 |
| 類別 | process-compliance |
| 風險等級 | 中 |
| 首發時間 | 2026-08-17（錯誤記述隨終態票凍結當日；2026-08-18 才被發現，落差 19 小時） |
| 姊妹模式 | PC-BAL-013、PC-BAL-015、PC-166（逐項分界見「與既有模式的分界」） |

## 症狀

ticket 收尾時，把「某代理人的報告未落地」這個產出面觀察，寫成「process 已結束」這個狀態面宣告，而該狀態從未查證。

實例：一張多視角審查 ANA 票於 2026-08-17 完成，其審查結果表格記載「架構與技術判斷視角｜否｜報告未落地，process 已結束」。19 小時後（2026-08-18），該代理人仍以 idle 狀態存活於原 session，經 `TaskStop` 才實際終止。

本檔一律以「代理人」指稱執行體本身，以「process 已結束」指稱被誤寫的那句狀態宣告；「in-process teammate」專指同一 session 內建立、不列於 `ListAgents` peer session 清單的代理人。

典型表徵：

- 派發或審查紀錄出現「process 已結束」「代理人已終止」等狀態詞，但同段落唯一支撐證據是「沒有收到產出」
- 以 `ListAgents` 清點閒置代理人時該代理人不在清單（in-process teammate 不列於 peer session 列），需另一觀測面才可見
- 票已終態，錯誤記述隨票凍結，後續讀者無從察覺

## 根因

**產出未交付與 process 已終止分屬兩個平面：前者可從自己的 context 直接觀察，後者必須查 session 外部狀態。** 收尾當下書寫者手上只有前者，順手把它補成後者。

`.claude/rules/core/tool-output-trust-rules.md` 規則 5（記錄平面與世界平面不對稱）已同時覆蓋讀與寫——其 Action 表禁止欄首列即「憑記憶斷言 commit 成功」，斷言就是書寫。本模式相對規則 5 的增量在另外兩處：

1. **推論結構不同。** 規則 5 三列 Action 全屬「記憶中有事件，因而斷言事件為真」的正向記憶；本模式是「觀察到缺席，因而斷言狀態」的缺席推論。缺席推論在規則 5 沒有對應樣態，這是真缺口。查證這一點請讀該規則 Action 表三列的共同句式。
2. **平面屬性被賦予載體而非陳述。** 規則 5 把 ticket 整體列入世界平面（原文為「filesystem / git / ticket 的世界平面」），下游因此信任票面；但票面內容的平面歸屬取決於書寫時是否查證。未查證的推定寫進 ticket，就把記錄平面的推定洗成世界平面的事實。平面屬性應賦予陳述而非載體。

三個放大因素：

1. **清單覆蓋缺口。** 只信 `ListAgents` 會得到「無閒置代理人」的假結論；本例是用戶另從代理人樹狀清單指認才發現兩個 idle 代理人。

   **缺口所在的軸已於 2026-09-03 複測更正。** 原記述為「`ListAgents` 回傳 peer session 但不含 in-process teammate」，該描述現已不成立：複測於三個時點觀測，本 session 自有的 in-process teammate 皆列於獨立的 `Teammates` 區塊並帶 status 欄位（同一代理人先後顯示 `running` 與 `idle`）。

   實際缺口在另一軸——**自有與他有**：`ListAgents` 列本 session 自有的 teammate，不列他 session 所屬的 teammate。複測期間收到兩個他 session 所屬 teammate 的 idle 通知（存活由通知送達證明），同一時刻該清單的任何區塊皆未出現它們。

   此更正改變本節處方的適用性：依原記述補查 teams config 的 in-process 那一面，仍完全看不到跨 session 殘留，而後者是實務上的主要殘留來源（一次實測清出 25 個閒置 4 至 17 小時者，全數來自前一 session）。指向錯誤位置的防護比缺少防護更難發現失效，因為執行者會認為自己已經查過。
2. **idle 與 terminated 在產出面同形。** 兩者都表現為「不再有東西送過來」，不查外部狀態無從區分。
3. **記述凍結於終態票。** ticket 完成後不再有人複查其歷史記述，錯誤不會被自動修正，且該段落有機會被下游當事實引用。

## 影響

殭屍代理人長期佔用資源而無人負責回收——票面既已宣告結束，就不存在觸發回收的訊號，本例存活 19 小時。

寫入風險存在但路徑窄：idle 代理人不會自發寫入，需有其他持有其名稱的執行體對它 `SendMessage` 才會起跑。而票面既已宣告它已死，原派發方通常不會再送訊；實際成立的路徑是名稱被後續派發重用而路由到它。若該代理人具寫入權限並在此路徑下起跑，它寫進工作區的變更會被歸類為來源不明（本例為唯讀審查，未發生此後果）。

維持「中」等級的實質支撐是第三項損害：終態票的歷史記述失準本身即為損害——下游若引用該段作為「該代理人已死」的依據，其重派或不重派的判斷建立在假前提上。該項與根因第 2 點（推定洗成事實）同源。

## 解決方案

**收尾記述只寫產出面事實，process 狀態一律不寫；需要確定狀態時直接執行 `TaskStop` 回收，用動作取代陳述。**

之所以不採「先查證再寫」，是因為現有觀測面不存在「已終止」的正向證據（2026-08-18 實測）：

| 觀測面 | 實測內容 | 能否證明已終止 |
|--------|---------|--------------|
| `~/.claude/teams/<session>/config.json` 的 `members[]` | 欄位為 `agentId` / `agentType` / `backendType` / `cwd` / `joinedAt` / `name` / `subscriptions` / `tmuxPaneId`，無 `status`、無 `exitedAt` | 否，只證明曾派發 |
| 該 session 的 inbox JSON | 訊息消費後為空陣列，不帶狀態 | 否 |
| subagent prompt 內的 active 代理人清單 | 為「可定址」清單，與 config `members[]` 高度重疊但不完全一致 | 否 |

查證條件既然永不成立，二分支的「查得到就寫、查不到就換句話」會恆定落到後者，等於空操作。收斂為單一寫法後特例消失，讀者也不需判斷「這次查得到嗎」。

`TaskStop` 屬狀態改變操作而非觀測，因此列為回收手段而非查證手段：用它「查證」等於用終止動作製造被查證的事實，且對已終止代理人的回傳無法區分「本來就死了」與「名稱寫錯」。

其餘兩類狀態宣告仍適用查證後書寫：

| 要寫的話 | 需要的查證 | 查不到時的替代寫法 |
|---------|-----------|------------------|
| 代理人執行失敗 | `TaskOutput` 回傳 `status=error` | 「未收到回報」 |
| 無閒置代理人可回收 | 本 session 自有者查 `ListAgents` 的 `Teammates` 區塊即可（2026-09-03 複測確認涵蓋）。他 session 所屬者該清單看不到，且現行三個持久化資料源皆無法列舉（見下），故此結論目前無可靠觀測面支撐——不得宣告，只能宣告「本 session 自有代理人已無閒置者」 | 「ListAgents 未列出」（該清單不涵蓋他 session 所屬者，未列出不構成證據） |

**他 session 所屬代理人的可列舉性（2026-09-03 實測）**：三個持久化資料源皆無法列舉，故上表該列的「無可靠觀測面」為現況判定而非推測。

| 資料源 | 失效原因 |
|--------|---------|
| `pm-registry.json` | 粒度為 PM session；三支 registry hook 一致排除 subagent，故其中結構性不存在 agent 維度 |
| `dispatch-active.json` | 欄位齊備（含 ticket_id 與 session_id），但記錄在代理人尚未終止時即被刪除——清理掛在 SubagentStop，而該事件標示回合結束非執行體終止。實測：代理人轉入 idle 後記錄已清空，同時該代理人仍列於清單、仍可接受訊息並繼續工作 |
| `agent-dispatch.jsonl` | 記錄完整且 ticket 歸屬正確，但為 append-only 日誌，無存活狀態欄位，只能列舉曾派發過什麼 |

`claude agents --json` 亦不適用：其粒度為 session 級，明載不列 subagent。

回收前先界定寫入範圍：確認殭屍代理人存活後，先以 `git status` 對照該代理人的任務範圍，判定工作區既有變更中哪些出自它，再執行 `TaskStop`。跳過這一步會把它已落地的合法變更誤判為來源不明而回退。

`TaskStop` 接受 teammate 名稱作為 `taskId`，不需先取得 agentId——本例即以名稱終止成功。`.claude/references/claude-code-tools-reference.md` 現行描述 `taskId` 由 `Monitor` 回傳，未載明名稱亦可用；該檔待補此項。因此即使 context 已 `/clear`，只要能讀到代理人名稱即可回收。

## 預防措施

- 收尾記錄審查缺席時，產出面與狀態面分開陳述：「報告未落地」是觀察，「process 已結束」是推定，後者無查證則不寫。
- 清點活躍代理人時先界定觀測面涵蓋哪個族群。單一來源的空清單不構成「沒有」的證據；`PC-166` 防護 E 同樣要求以第二個觀測面交叉驗證。**且交叉驗證的前提是各觀測面的涵蓋範圍已知**——本檔原記述誤判了 `ListAgents` 的缺口所在，補查另一觀測面仍看不到目標族群，因為兩個觀測面在同一軸上而缺口在另一軸。觀測面數量不能替代涵蓋範圍的確認。
- 已終態票發現此類記述失準時不追改票面（`.claude/rules/core/quality-baseline.md` 規則 6：流程瑕疵不回退既成工作），改為記錄本模式，並在後續同型書寫時避免。

上述三條屬自律層，另有三個機械判定點可承擔一部分，依優先序：

| 優先序 | 機械點 | 說明 |
|-------|-------|------|
| 1（直擊實際損害） | ticket complete 或 session Stop hook 讀 teams config `members[]`，比對已完工／已 shutdown 名單，提示尚未回收的代理人 | 殭屍存活的損害來自無人回收。回收提示不依賴書寫是否正確，比掃狀態詞更根本 |
| 2（源頭 opinionated default） | 多視角審查表格由 ticket CLI 產生時，缺席理由欄限定枚舉（未落地／未回報／逾時／不適用），不開放自由文字寫狀態詞 | 符合 `.claude/rules/core/structured-content-generation.md`「結構由工具生成」，特例從源頭消失 |
| 3（第 3 層保險） | commit 或 complete 時掃 ticket body 變更行的狀態詞，命中且同段無查證紀錄則 WARNING | 誤攔可再以 `subprocess`、`不存在於` 等詞收窄 |

第 3 點的誤攔量級已實測（2026-08-18，掃描該專案工作日誌目錄下 857 份 markdown）：

| pattern | 命中 | 真陽性 | 誤攔 |
|---------|------|-------|------|
| 寬版 `(process\|進程\|代理人\|agent\|teammate)[^。\n\|]{0,12}(已結束\|已終止\|已死\|終止\|已退出)` | 11 | 1 | 10（subprocess 技術描述、error-pattern 引用文） |
| 限定表格列（行首 `\|`） | 2 | 1 | 1（分析表列） |

絕對量為 1 至 11 條對 857 檔，WARNING 級可承受。此量級不適用「誤攔率高故全採自律」的推論——後者的成立前提是千條級命中量，與本例差兩個數量級。

## 與既有模式的分界

分界軸為**失效端**：規則 5 的同一條不對稱可以在讀端失效，也可以在寫端失效。讀端失效是以自身 context 當 ground truth 後行動，寫端失效是把未查證的推定寫成記述供下游繼承。行動方向相反（過度行動 vs 缺席回收）是這條軸的推導結果，不是分界依據——後果發生時該讀哪一檔已無意義，故不以後果選檔。

| 模式 | 失效端 | 觸發時機 | 待決動作 |
|------|-------|---------|---------|
| `.claude/error-patterns/process-compliance/PC-BAL-013-cleared-context-mistaken-for-terminated-background-agent.md` | 讀端 | context 中斷後，看到 assigned ticket 或未提交變更 | 是否重派 |
| PC-BAL-045（本檔） | 寫端 | ticket 收尾，書寫審查缺席理由 | 如何記述、是否回收 |

因此 PC-BAL-013 的錯誤即刻兌現為重派與雙寫入者，本模式的錯誤凍結於票面延後兌現。兩檔不合併：本檔有 013 沒有的實質內容（in-process teammate 的觀測面缺口、終態票記述凍結、處置為回收而非重派），而 013 的存活查證表（mtime、diff、`started_at`）本檔不重複。想確認代理人是否還活著時讀 013，想確認該怎麼把「沒收到報告」寫進票面時讀本檔。

最近的鄰居是 `.claude/error-patterns/process-compliance/PC-BAL-015-idle-notification-and-uncommitted-work-read-as-agent-inaction.md`，其標題為「idle 通知加上尚未落地的寫入被當成代理人未執行」。它與本檔對同一個 idle 訊號做了反向超譯——015 是 idle 被讀成未執行，低估已完成的工作，處置為前台重做；本檔是 idle 被寫成已終止，高估已結束的狀態，處置缺席。本檔根因因素 2（idle 與 terminated 在產出面同形）與 015 的根因同構，兩檔的差別在超譯方向，讀 015 可取得同一訊號另一側的誤判樣態。

`.claude/rules/core/tool-output-trust-rules.md` 規則 5 是三者共用的上位總則（記錄平面與世界平面不對稱）；`.claude/error-patterns/process-compliance/PC-166-confabulated-tool-result-and-git-working-tree-ground-truth.md` 防護 E 提供本檔預防措施第 2 條所依據的交叉驗證要求。
