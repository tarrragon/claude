---
id: PC-165
title: AUQ 派發類選項未先驗 blockedBy readiness（假選項）
category: process-compliance
severity: medium
status: active
created: 2026-06-02
---

# PC-165: AUQ 派發類選項未先驗 blockedBy readiness（假選項）

## 症狀

PM 在 AskUserQuestion 中把某 ticket 列為「下一步派發」選項，但**未在呈現選項前**驗證該 ticket 的 `blockedBy` 是否已滿足。readiness 查證發生在**用戶選擇之後**，而非之前。

典型訊號：

- commit 後「下一步」AUQ（askuserquestion-rules 場景 #2 / #11）選項含某 ticket，PM 憑「主題連貫」直覺列入，未過 `ticket track runqueue`。
- 用戶選定後，PM 才 `grep blockedBy` 或查 helper/前置狀態，發現該 ticket 被前置阻擋。
- 選項文字無「（blocked by X）」標註，呈現為可直接執行的假象（false affordance）。

## 根因

1. **readiness 驗證時序倒置**：AUQ 派發選項應只列 runqueue-ready（`blockedBy=[]` 或全 terminal）的 ticket；本案在「呈現前」省略此檢查，「選擇後」才補。
2. **runqueue/dashboard 過濾未套用於手動 AUQ**：`/ticket` 裸命令的 dashboard `[Ready Top N]` 已自動過濾 ready，但「commit 後下一步」AUQ 的選項由 PM **手動列**，未走同一 readiness 過濾 → 缺口在手動路徑。
3. **連貫性偏誤（對象為 blockedBy）**：剛完成 export 線（W1-035），自然聯想「下一個 export 工作 = W8-001.2」，主題連貫蓋過依賴檢查。與 PC-107 連貫性偏誤同源，但 PC-107 對象是「拆分」，本 pattern 對象是「blockedBy readiness」。
4. **權力不對等放大**：PM 是資訊強勢方，用戶傾向相信列出的選項已驗證可行（ai-communication-rules 規則 5 §5.6 前提查驗缺失）。

## 實際案例

**0.31.1 W8-001.2 派發（2026-06-02）**：

- W1-035（export l10n）完成後，PM 在 AUQ 列「派 W8-001.2 繼續」為選項，未先查 W8-001.2 的 blockedBy。
- 用戶選擇後，PM 才查證：`W8-001.2 blockedBy [W8-001.1]`，而 W8-001.1（為 `createFullTestApp` 加 overrides 參數）仍 pending。`createFullTestApp` 不支援 overrides，export 測試無法注入 mock provider。
- PM 自我修正：改派前置 W8-001.1（未真的派出 W8-001.2，未造成 agent 越界）。

**未自我修正時的後果**（此次已避免）：

派發 W8-001.2 → parsley 認領後發現 helper 無 overrides → 兩種壞路徑：(a) NeedsContext 中斷，浪費一次 worktree 派發 + 復原成本；(b) parsley 自行改 helper（越界 W8-001.1 範疇）。

## 防護

### 1. PM 規則層：派發類 AUQ 選項先過 readiness 過濾（人工）

AUQ 列「下一步派發某 ticket」前，對每個候選 ticket：

| 步驟 | 動作 |
|------|------|
| 1 | `ticket track runqueue --wave N`（回傳 blockedBy 滿足的可執行清單）|
| 2 | 候選 ticket 不在 runqueue → 不列為「直接派發」選項 |
| 3 | 仍要呈現 blocked ticket → 選項文字標「（blocked by X，需先做 X）」，且首選改為其前置 |

### 2. 對照既有 dashboard 機制

`/ticket` 裸命令 dashboard `[Ready Top N]` 已自動過濾 ready（blockedBy 滿足）。缺口在**手動列選項的 AUQ 路徑**（場景 #2 commit 後、場景 #11 接手）。修復方向：這些場景的選項生成改引用 runqueue 輸出，不靠 PM 記憶。

### 3. Hook 層（未來）

commit 後路由 hook 可在偵測 PM 將 ticket ID 放入 AUQ 選項時，回填其 blockedBy 狀態提示（類比 dispatch-readiness 的 pre-check 思路）。

## 與既有規則的關係

| 規則 / pattern | 關係 |
|------|------|
| `askuserquestion-rules.md` 場景 #2 / #11 | 缺「派發類選項須先過 runqueue readiness」條款 → 防護 #2 落地點 |
| PC-107（派發前未走拆分檢查）| 同為「派發前 pre-check 缺失」家族；PC-107 查 cognitive-load 拆分，本 pattern 查 blockedBy readiness |
| `ticket track runqueue` / dashboard | 機制已存在（自動過濾 ready），但未套用於手動 AUQ 選項生成 |
| ai-communication-rules 規則 5（權力不對等前提查驗）| 假選項是「未查驗前提即呈現」的具體案例 |
| quality-baseline 規則 6（失敗案例學習）| 本案自我修正未回退，提煉為本 pattern |

## 修復方向

- **本案個案**：已自我修正（改派 W8-001.1 前置）。
- **框架層**：在 `askuserquestion-rules.md` 場景 #2 / #11 加條款「派發類選項生成前須過 `runqueue` readiness 過濾，blocked ticket 須標前置」（已建 follow-up ticket 追蹤）。

## 相關 Ticket

- 0.31.1-W8-001.2 / W8-001.1（本 pattern 動機案例）

## 相關 error-patterns

- PC-107（派發前未走拆分檢查）
- PC-064（PM 純文字選項未用 AUQ）
- PC-020（plan execution dispatch mismatch）
