# PC-097: 同一資料於同一請求中被兩處 I/O 重複呼叫

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-097 |
| 類別 | process-compliance |
| 風險等級 | 中（效能損耗 + 兩次取值間資料漂移風險，破壞單次請求內資料一致性） |
| 首發時間 | 2026-04-19（W10-017.1 Phase 1 多視角審查 Plan 視角揭露） |
| 姊妹模式 | PC-006（過早抽象統一）、PC-068（Phase 3a 規劃新工具未掃描既有） |

---

## 症狀

同一筆 I/O 結果（檔案讀取、git status、HTTP 請求、DB 查詢）在單次請求生命週期內被**兩個或多個位置各自獨立呼叫**，導致：

1. **效能浪費**：相同 I/O 執行 N 次（git status 在大 repo 數百 ms / 次）
2. **資料漂移**：兩次呼叫間實際狀態若有變動，呼叫方拿到不一致的快照（race window）
3. **時間欄位不一致**：第一次取得 `computed_at_T1` 寫入 state；第二次取得時實際已是 `T2`，但仍標 `T1` → 時間戳謊報
4. **責任分裂**：兩處呼叫各自擁有「我自己的 git status」心智模型，難以追蹤該以哪份為準

---

## 實際案例

### 案例 1（W10-017.1 handoff-ready 規格，2026-04-19）

**任務**：實作 `ticket track snapshot` 增強「當前建議」+「/clear Ready Check」區塊

**問題結構**：

```
PM 呼叫 ticket track snapshot
  ├─ commands/track_snapshot.py
  │    └─ 直接呼叫 git status → 取得 dirty files 顯示在「Ready Check」區塊
  │       computed_at_1 = 14:30:00
  └─ lib/checkpoint_state.py::checkpoint_state()
       └─ 也呼叫 git status → 寫入 CheckpointState.uncommitted_files
          computed_at_2 = 14:30:00.450
```

**Plan 視角揭露**（多視角審查第 2 條發現）：

> snapshot 命令對 `git status` 重複呼叫兩次（command layer 一次、lib layer 一次），且 CheckpointState.computed_at 寫入的是 lib 層呼叫時間，而 command 層 Ready Check 顯示的是更早呼叫時的快照——兩者在競態下會錯位，且 PM 看到的「未提交檔案數」與 state 記錄的可能不同。

**修正方向**：

| 方案 | 做法 |
|------|------|
| 修正 A | command 層只透過 `state.uncommitted_files` 取資料，禁止自行呼叫 git status |
| 修正 B | lib 層 `checkpoint_state()` 接受預先採集的 git_status 參數，由 command 層採集後注入 |

選擇 A：以 lib 層為唯一 I/O 源，command 層只渲染（單一資料源原則）。

---

## 根本原因

### 真根因

1. **層級設計時 I/O 責任未明確指定**：command layer 與 lib layer 各自被視為「需要 git status」的合法消費者，未明確規定「誰負責採集」
2. **抽象封裝的副作用**：`checkpoint_state()` 將 git 操作封裝在 lib 內看似乾淨，但 command 層因「想顯示更詳細欄位」自行再次呼叫，繞過封裝
3. **快取/單例缺位**：未設計請求級的 I/O 快取機制，相同呼叫在同一請求中無法共享結果
4. **時間戳設計疏忽**：`computed_at` 欄位語意未規範「這代表哪次 I/O 的時刻」，導致 command 層渲染時不知道應信任哪個時間

### 為什麼容易發生

- 兩處呼叫各自看似合理，code review 時難以發現重複（檔案不同、上下文不同）
- 開發階段資料量小、I/O 快，效能與漂移問題不顯
- TDD 測試多 mock 掉 git status，重複呼叫不會在測試層被偵測
- 「lib 提供 API、command 也能直接用底層工具」的彈性反而促成重複

---

## 常見陷阱模式

| 陷阱表述 | 為何仍是重複 I/O |
|---------|---------------|
| 「lib 跟 command 需要的欄位不同，所以各自呼叫合理」 | 解法應是「lib 提供更完整的回傳結構」，不是兩處重複呼叫 |
| 「git status 很快，不會有效能問題」 | 重點不只效能，而是**時間漂移**與**資料一致性** |
| 「兩次呼叫結果應該幾乎一樣」 | 「幾乎一樣」就是 race condition 的徵兆，正式系統不接受「幾乎」 |
| 「lib 層回傳資料不夠用，command 自己補一下」 | 應修 lib 層介面，不應 command 層繞過 |
| 「請求等級快取太重」 | 通常一個 dataclass 傳遞即可解決，不需快取機制 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 設計 | 同一請求內的同一筆 I/O 必須**單一採集點**，其他消費者透過參數/state 接收 | 行為準則（本 PC 後立） |
| Phase 1 review | 規格設計時列出所有 I/O 操作及其呼叫位置，檢查是否有同一資料兩處採集 | 行為準則 |
| 命名 | 採集點命名清楚（例如 `state.git_status`），消費端禁止自行呼叫底層 | 行為準則 |
| 時間戳 | 任何 `computed_at` / `fetched_at` 欄位必須註明「這個時間代表哪次 I/O」 | 行為準則 |

---

## 檢查清單（Phase 1 規格設計與 Phase 4 重構評估時）

- [ ] 列出本請求的所有 I/O 操作，是否有任兩處採集相同資料？
- [ ] 若存在重複，是否能由其中一處採集後傳遞給另一處？
- [ ] state/snapshot dataclass 是否包含足夠欄位讓消費端不需另呼叫底層？
- [ ] 時間戳欄位是否明確指向唯一一次 I/O 的時刻？
- [ ] 測試是否能偵測「同一請求內 git status 呼叫超過 1 次」？（mock call count assertion）

---

## 教訓

1. **I/O 採集點應在請求生命週期中唯一**：不是「禁止重複呼叫」這麼簡單，而是「明確指定誰負責採集」
2. **lib 層介面要包含消費者真正需要的所有欄位**：command 層繞過封裝的根因往往是 lib 介面回傳不全
3. **時間戳是請求一致性的試金石**：兩處 I/O 各自取時間，立刻暴露重複呼叫問題
4. **Phase 1 規格 review 要列 I/O 清單**：不要等到 Phase 3b 實作或 Phase 4 重構才發現

---

## 相關文件

- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W10-017.1.md` — 案例 1 來源（Phase 1 多視角審查 Plan 視角第 2 條發現）
- `.claude/skills/ticket/ticket_system/lib/checkpoint_state.py` — 案例 1 涉及的 lib 層
- `.claude/error-patterns/process-compliance/PC-006-premature-unification-abstraction.md` — 姊妹模式（過早統一抽象）
- `.claude/error-patterns/process-compliance/PC-068-phase3a-planning-new-utility-without-scan.md` — 姊妹模式（規劃新工具未掃描既有）

---

**Last Updated**: 2026-04-19
**Version**: 1.0.0
**Source**: W10-017.1 Phase 1 多視角審查 Plan 視角第 2 條結構性發現
