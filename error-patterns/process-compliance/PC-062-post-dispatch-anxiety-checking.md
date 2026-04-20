# PC-062: 派發後焦慮性檢查違規

## 錯誤症狀

PM 派發代理人（background）後，task-notification 未到達前主動執行 git status / grep / find / cat dispatch-active.json 等 Bash 查詢，**動作本身合法但動機是焦慮性監控**，違反非同步派發原則。

典型表現：
- 同一派發週期內重複執行 `git status`，每次間隔數秒至數十秒
- 通知未到達時主動 `grep -l` 代理人可能產出的檔案
- 反覆 `cat .claude/dispatch-active.json` 確認剩餘數量（即使剛才已看過）
- 讀取 agent transcript output 檔案的 `<output>` body 推論執行狀態（與 PC-050 模式 D 重疊但更常發生）

**核心區分**：動作本身中性，但如果 PM 無法明確回答「執行這個命令要驗證什麼具體問題」，即屬焦慮性。

## 根因分析

### 表層原因：Hook 訊息正向強化

`active-dispatch-tracker-hook.py` 在 PostToolUse 附加訊息「[OK] 所有代理人已完成，可開始驗收」到 context。當 dispatch-active.json 為空（可能因為 hook 過早清理、或尚未派發、或通知已處理完），此訊息仍出現，**形成正向強化**：PM 每做一次 Bash 都看到「已完成」暗示可以驗收，誘發繼續查詢。

### 深層原因：async-mindset 規則結構缺陷（根本問題）

> 關鍵洞察：W10-023 WRAP 分析 Consider the Opposite 揭示。

`async-mindset.md` 原版只有 don't（禁止等待、禁止同步），沒有 do（派發後應做什麼）。規則層面的注意力空缺會自動由焦慮填補，不是執行者意志問題。

類比：告訴司機「不要踩煞車」而不告訴要踩油門或方向盤，車子不會停在原地，會失控。

### 次要原因：代理人完成訊號不可區分

Hook 觸發「已清理派發記錄」訊息與 task-notification 到達的形式相似，PM 容易將前者誤解為後者，進而進入驗收心態卻發現代理人仍在跑，形成心理不一致，催生進一步查詢確認。

## 防護措施

### 規則層（已落地）

- **async-mindset.md v1.2.0**（W10-025）：新增「派發後注意力出口」章節，包含合法 vs 焦慮檢查對照表、注意力切換範本（5 層優先級）、代理人完成訊號可信度表、4 個邊界案例
- **pm-rules/behavior-loop-details.md**：派發後行為表已規範應做事項（Context Bundle / 下個 Ticket 分析 / worklog 整理）

### CLI 層（已落地）

- **ticket CLI claim 簡化 WRAP 三問**（W10-028）：每次 claim 強制 PM 回答 W/A/P 三問，其中 A（機會成本）直接對抗「閒著就查代理人」的傾向——迫使 PM 意識到此刻應投入的下件事

### Hook 層（待落地 W10-024）

- `active-dispatch-tracker-hook.py` 訊息調整：dispatch-active.json 為空且無近期通知時不輸出「[OK] 已完成」，避免誤導正向強化

### 行為層自檢

每次派發後想執行 Bash 查詢前，PM 必須能回答：「**我執行這個命令要驗證什麼具體問題**？」
- 可以 → 合法檢查，執行
- 不能 → 焦慮檢查，禁止，切換注意力出口

## 合法 vs 焦慮情境（快速對照）

| 命令 | 合法情境 | 焦慮情境 |
|------|---------|---------|
| `git status` | commit 前驗證範圍；派發前清點；通知後驗收 | 派發後短時重複；無目的「看看」 |
| `cat dispatch-active.json` | 派發後首次清點；通知到達後確認剩餘 | 通知未到達前重複 polling |
| `grep / find` 代理人產出 | 通知到達後驗收具體檔案 | 通知未到達前「偵察」進度 |
| 讀 agent transcript `<output>` body | **永遠禁止**（PC-050 模式 D） | **永遠禁止** |

## 邊界案例

### 案例 A：派發後立刻發現另一個必須處理的 bug
- 分類：外部中斷，**非焦慮**
- 處理：建 Ticket 記錄，評估是否影響代理人，可獨立處理

### 案例 B：派發後超過合理時間無通知
- 分類：合法懷疑，**可查詢**
- 處理：用 `TaskOutput(task_id=X, block=false)` 查 `<status>` 標籤（非阻塞），禁止讀 `<output>` body
- 合理時間參考：代理人歷史完成時間分佈（通常 2-5 分鐘，複雜任務 10+ 分鐘）

### 案例 C：派發後疑慮自己的 prompt 品質
- 分類：焦慮變種，**禁止查詢代理人**
- 處理：信任代理人或派發前 review prompt；已派發則 SendMessage 補充不要 polling

### 案例 D：派發後想看代理人有沒有在動
- 分類：純焦慮，**禁止**
- 處理：立刻切換到「注意力出口」範本的 5 層優先級

## 相關錯誤模式

- **PC-050**：PM 在代理人仍在工作時誤判完成/失敗（本錯誤模式的下游症狀——焦慮性檢查常導致 PC-050 模式 D 讀 transcript 誤判失敗）
- **PC-009**：Handoff first 預設（context 擁擠時焦慮性檢查更常見，應優先 handoff）

## 驗證方式

每 session 結束前 PM 自省：
- 本 session 派發後的 Bash 查詢是否都能說出「要驗證什麼」？
- 有幾次在 task-notification 未到達前讀取 transcript body？（應為 0）
- 派發後到通知到達之間，是否做了注意力出口範本中的任一項？

## 觸發日期

- 2026-04-13 新增：W10-023 WRAP 分析揭示，W10-026 建立

## 防護措施實作追蹤

| 層次 | Ticket | 狀態 |
|------|--------|------|
| 規則層：async-mindset 注意力出口 | 0.18.0-W10-025 | 完成（v1.2.0） |
| CLI 層：claim 簡化 WRAP 三問 | 0.18.0-W10-028 | 完成 |
| Hook 層：active-dispatch-tracker 訊息調整 | 0.18.0-W10-024 | 待執行 |
| 錯誤模式：本檔案 | 0.18.0-W10-026 | 完成 |
