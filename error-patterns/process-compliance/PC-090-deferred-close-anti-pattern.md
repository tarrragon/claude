# PC-090: 推延性 close 反模式

## 基本資訊

- **Pattern ID**: PC-090
- **分類**: 流程合規（process-compliance）
- **來源版本**: v0.18.0
- **發現日期**: 2026-04-18
- **風險等級**: 中

---

## 問題描述

### 症狀

PM 在 ticket 尚未完成目標的情況下，以「暫緩」「等 data」「條件尚未觸發」「之後再判斷」等理由提議 close。

常見表現形式：

| 表現 | 說明 |
|------|------|
| 「閘門未達，先 close」 | 把「執行條件未觸發」當作「任務已完成」 |
| 「W15-XXX 已處理，可以 close」 | 把 follow-up ticket 產出當作本 ticket 目標達成 |
| 「先 close，之後再判斷要不要執行」 | 把決策延後偽裝成合法 close |
| 「session 快結束了先收掉」 | 因決策疲勞誤判完成狀態 |
| 「成本太高，不值得執行」 | 成本評估應轉 cancel 或 migrate，不是 close |

### 四層動機分析

W15-024 ANA 透過 WRAP Reality Test 識別推延性 close 的深層動機：

| 動機類型 | 表面說法 | 深層動機 |
|---------|---------|---------|
| A 成本迴避 | 「E2 實驗 40 session 成本高」 | 想省推理 token / 估算成本後迴避 |
| B 閘門混淆（主因） | 「E3 > 0.3 未觸發，任務已完成」 | 把「ANA 成本閘門未達」當「目標完成」 |
| C 決策疲勞 | 「W15 已有 11 個 ticket 收尾」 | 想快速結束 session，誤判收狀時機 |
| D 責任轉移錯誤 | 「W15-016 已處理此事」 | 誤把 follow-up 建立標記當本 ticket 完成 |

**真根因**：動機 B（閘門混淆）為主，A 和 C 加乘。閘門未達只代表「本 ticket 定義的條件未發生」，不代表「目標已達成或任務不再需要」。

---

## W15-015 案例對照

### 案例背景

W15-015 是一個條件型 ticket，設計為「E3 實驗結果 > 0.3 才投入 E2 深度實驗」。

### 事件序列

| 時間點 | 事件 | 問題 |
|--------|------|------|
| W15 末期 | E3 結果 < 0.3，閘門未觸發 | 正常，非問題 |
| session 準備收尾 | PM 提議：「閘門未達，W15-015 可以 close」 | 把閘門未觸發等同於目標達成 |
| 用戶指正 | ticket 只能做或收狀，「等之後判斷」不是合法 close | PM 動機為推延性 close 反模式 |
| 校正後 | W15-015 重新設計為 find_files 子實驗，不 close | 閘門未達 → 應 rescope 或 migrate，不是 close |

### 正確處理路徑

```
條件型 ticket 閘門未達
        |
        +-- 知識已轉移 error-pattern → close (not_executable_knowledge_captured)
        |
        +-- 仍有未來價值 → rescope 或 migrate 到下版本
        |
        +-- 需求消失（上游取消）→ close (requirement_vanished)
        |
        +-- 成本/效益評估為不值得 → close (cancelled_by_user) + 決策日誌
```

---

## 合法 close 條件（C1-C4 規則）

### C1. close 合法理由枚舉

ticket close 必須填寫 `close_reason`，且理由必須符合以下六種枚舉之一：

| close_reason | 語意 | 必填附件 |
|-------------|------|---------|
| goal_achieved | 目標已達成 | 無 |
| requirement_vanished | 需求消失（環境變更使 ticket 無意義） | 說明消失原因 |
| superseded_by | 被上游 ticket 取代 | 附上游 ticket ID |
| not_executable_knowledge_captured | 無法執行且知識已轉移 error-pattern | 附 error-pattern 檔案路徑 |
| duplicate | 與既有 ticket 重複 | 附重複 ticket ID |
| cancelled_by_user | 用戶明示取消 | 附取消理由 |

### C2. 禁止的假 close

以下理由不屬於合法 close，必須轉換為正確操作：

| 偽 close 理由 | 正確操作 |
|--------------|---------|
| 「等 data / 等觀察 / 之後再說」 | migrate 至下版本或 rescope |
| 「暫緩 / 算了不重要」 | cancel（需附決策日誌）或 migrate |
| 「閘門未達，跳過」 | 依條件型 ticket 三後果流程處理（見 C3） |
| 「follow-up 已建立」 | 僅建立 follow-up ≠ 本 ticket 完成 |

### C3. 條件型 ticket 建立時預定義三後果

建立條件觸發型 ticket 時必須在 ticket 說明中預定義：

- 觸發 → 執行動作（明確描述要做什麼）
- 未觸發且知識可轉移 → close with `not_executable_knowledge_captured` + error-pattern 路徑
- 未觸發但仍有價值 → rescope 或 migrate，更新觸發條件

### C4. 回顧式 close 允許 unknown

既有 closed ticket 若需補填 `close_reason`，允許填 `unknown` 但需標記 audit flag，以供後續統計分析。

---

## 防護措施

### 自我檢查清單（close 前確認）

在執行 close 操作前，PM 必須確認以下問題全部為「是」：

- [ ] close_reason 符合 C1 六種枚舉之一？
- [ ] 不是「等之後判斷」的推延偽裝？
- [ ] 若為條件型 ticket：三後果中至少一個已確認？
- [ ] 若引用 follow-up ticket：本 ticket 的原始目標已達成（非只是「建立了追蹤」）？
- [ ] 若因成本評估不執行：已轉 cancelled_by_user + 決策理由？

### 觸發訊號識別

PM 出現以下思路時，應立即停止並重新評估：

| 觸發訊號 | 正確回應 |
|---------|---------|
| 「session 快結束了，先 close 再說」 | 停止。執行 C1 檢查，不因 session 壓力 close |
| 「這個 ticket 的條件沒發生，可以 close」 | 停止。執行 C3 三後果流程 |
| 「XXX 已處理了，所以這個也算完成」 | 停止。確認本 ticket 原始目標是否達成 |
| 「成本太高，先 close 等之後決定」 | 停止。成本評估 → cancel 或 migrate，不是 close |

---

## 解決方案

### 正確做法

- 執行 C1 枚舉確認 close 理由合法
- 條件型 ticket 閘門未達 → 執行 C3 三後果流程
- 認為「之後再判斷」→ 選擇 migrate 或 rescope
- 成本/效益評估不執行 → cancel + 決策日誌

### 錯誤做法（避免）

- 用「閘門未達」當「任務完成」
- 把「建立 follow-up ticket」等同於「本 ticket 完成」
- 因 session 疲勞或決策疲勞推延 close
- 不填 close_reason 直接 close

---

## 相關資源

- `.claude/error-patterns/process-compliance/PC-090-deferred-close-anti-pattern.md`（本檔）
- `.claude/pm-rules/ticket-lifecycle.md` — close 條件規則 C1-C4 落地位置（W15-025 IMP）
- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W15-024.md` — 原始 ANA WRAP 分析
- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W15-025.md` — ticket-lifecycle.md 規則落地
- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W15-026.md` — 本 error-pattern 建立任務

---

## 標籤

`#ticket-lifecycle` `#close-condition` `#deferred-close` `#anti-pattern` `#process-compliance` `#decision-fatigue` `#gate-confusion`

---

**Last Updated**: 2026-04-18
**Version**: 1.0.0 — 初建，從 W15-024 ANA WRAP 分析轉化（W15-026 DOC）
