---
id: PC-BAL-044
title: 並行建票下依連號推定衍生票 ID，引用與 staging 同步指向他人票
severity: medium
category: process-compliance
related: [PC-BAL-008, PC-166]
created: 2026-08-18
---

# PC-BAL-044: 並行建票下依連號推定衍生票 ID，引用與 staging 同步指向他人票

## 症狀

- 同一 repo 有另一 session 並行建票，雙方交錯取號
- 建票 CLI 輸出被 `tail` 截斷或未回讀，操作者依前一張票的號碼加一推定新票 ID
- 該推定 ID 同時流入兩處：ticket body 的衍生票引用，以及 commit 前的 `git add` 路徑清單
- commit 使用了 pathspec、路徑精確，仍納入他人票的檔案——**pathspec 正確但輸入的檔名本身就錯**
- 自己真正建立的那張票反而未進版本控制，直到 `complete` 的 spawned 檢查列出實際 ID 才暴露落差

## 根因

「ID 由誰決定」的認知錯位。建票 ID 由 CLI 在鎖保護下原子分配，屬**世界平面**事實；操作者的連號推定屬**記錄平面**推論（「我上一張是 N，所以這張是 N+1」）。並行建票下兩者必然漂移——他人在你兩次建票之間取走了中間號碼。

放大機制有兩層：

1. **輸出被截斷**：建票命令常以 `| tail -N` 收斂輸出，實際 ID 出現在被截掉的區段，操作者從未看見真值卻不自知。
2. **單點錯誤雙路徑擴散**：同一個推定 ID 既寫進文件引用、又進 staging 清單。防護 commit 污染的既有紀律（pathspec）只保證「提交參數指定的路徑」，不驗證「這些路徑是不是你的票」，因此對本錯誤完全無效。

`tool-output-trust-rules` 規則 5 的世界平面查證要求涵蓋 commit / complete / spawn 等狀態轉換，但「新建物件的識別碼」未被列為需查證項目——建立成功的回饋被當成 ID 已知。

## 解決方案

- **建票後立即回讀實際 ID**，不從輸出推定也不從連號推定：
  ```bash
  ticket track deps <source-ticket-id>   # 列出實際 spawned_tickets
  ```
  `deps` 讀 frontmatter 的 `spawned_tickets`，是 CLI 寫入的世界平面值。以此清單作為文件引用與 staging 的唯一來源。
- **建票命令不要截斷到看不見 ID**：`| tail -N` 的 N 需大到涵蓋 CLI 回報的建立結果，或改以 `deps` 回讀取代看輸出。
- **staging 清單由回讀結果產生**，而非由記憶或推定拼出檔名。
- 已污染的 commit 依 `quality-baseline` 規則 6 不回退——吸收的內容是對方的真實產出，無資料損失；補一次 commit 修正 ID 引用並補進自己漏掉的檔案，並在 ticket 自檢欄如實記為未通過。

## 預防措施

- 收尾前對照：ticket body 引用的衍生票 ID 集合，與 `deps` 輸出的集合逐一相符才 commit。
- 自檢清單中「並行 session 檔案未被吸收」不可只檢查「有沒有用 pathspec」，須連帶檢查「pathspec 裡的每個檔名是否來自回讀而非推定」。
- 工具層改善方向：建票 CLI 於輸出末段（不易被 `tail` 截掉的位置）固定印出新票完整 ID，使正確資訊落在操作者實際會看到的區段。

## 關聯

- `PC-BAL-008`：同屬並行 repo 的 commit 污染家族，但根因不同——該模式是 index 全量提交掃入他人已 staged 檔案，pathspec 即可根治；本模式的 pathspec 本身輸入錯誤，pathspec 紀律無效。兩者需並列檢查。
- `PC-166` 與 `tool-output-trust-rules` 規則 5：本模式是「記錄平面推論取代世界平面查證」在新建物件識別碼上的具體形態。
