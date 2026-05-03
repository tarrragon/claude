# 決策 Trigger 綁定規則

本文件規範所有需要延後執行的決策必須綁定明確 trigger，禁止「以後再說」式的無 trigger 延後框架。

> **核心理念**：所有需求都應有明確執行計畫、階段、確認、驗收。延後不是第三種狀態——延後必須是「等 ticket X 完成後執行 Y」，且 X 必須是 ticket。

---

## 適用範圍

| 對象 | 是否適用 |
|------|---------|
| Ticket 撰寫（5W1H、Solution、Problem Analysis、acceptance） | 是 |
| 規則 / 規格 / 提案撰寫 | 是 |
| Phase 4 評估結論 | 是 |
| Code review 評論、commit message、PR description | 是 |
| 程式碼註解（業務情境陳述） | 是 |
| 對話內 prompt（PM 派發 / 代理人回報） | 是 |

---

## 強制規則

### 規則 1：兩種合法狀態，沒有第三種

任何決策只能處於以下兩種狀態之一：

| 狀態 | 含義 | 範例 |
|------|------|------|
| (a) 已決策 | 含結論的最終決定 | 「採方案 A」「無需重構」「Phase 4 評估結論：保持現狀」 |
| (b) 明確 trigger 延後 | 等 ticket X 完成後執行 | 「`<follow-up-ticket-id>` 完成後處理 X 實作」 |

**禁止**：無 trigger 延後（「Phase X 再決定」「以後再評估」「之後處理」「暫緩」「baseline 顯示需要再做」「待後續觀察」）。

**Why**：無 trigger 延後在「以後」與「永不」之間沒有可驗證邊界，必然累積為死議題（PC-093 的根源）。

**Consequence**：違反此規則的延後表述會在執行階段成為灰色地帶，驗收沒有完成定義，後人接手不知該不該補做。

**Action**：撰寫前自問「這個決策現在能不能下結論？」能 → 寫結論（狀態 a）；不能 → 建 follow-up ticket 並引用 ID（狀態 b）。

### 規則 2：合法 trigger 限 ticket ID

只有 ticket ID 是合法 trigger。其他形式（時間、量化閾值、外部事件）必須先包裝為 ticket：

| 想表達 | 錯誤 | 正確 |
|--------|------|------|
| 等 baseline > 80ms 才做 | 「baseline > 80ms 時觸發」 | 建監測 ticket（描述「監測 X 指標，> 80ms 時建 follow-up」），本決策標 `blockedBy: [<ticket-id>]` |
| 等外部版本發布 | 「外部版本 vN 發布後處理」 | 建追蹤 ticket，本決策標 `blockedBy` |
| 等指定日期重評 | 「YYYY-MM-DD 重新評估」 | 建排定 ticket，本決策標 `blockedBy` |
| 等用戶反饋累積 | 「累積 10+ 案例後評估」 | 建監測 ticket，本決策標 `blockedBy` |

**Why**：ticket 是專案唯一統一追蹤單位，含 acceptance / status / 派發機制 / scheduler runqueue。其他 trigger 形式無自動推進，會在「未綁 ticket 但說有 trigger」的灰區累積。

**Action**：想寫「等 X 條件成立時做 Y」→ 先建追蹤 X 的 ticket，再用 ticket ID 作為 trigger。

### 規則 3：寫法替換對照表

| 反模式句型 | 替代寫法 |
|-----------|---------|
| 「Phase 4 再決定觸發條件」 | 建 follow-up ticket，本 ticket frontmatter 標 `spawned_tickets: [<ticket-id>]` |
| 「之後再評估」「以後再說」 | 同上 |
| 「暫緩」 | 立刻決策（狀態 a），或建 ticket（狀態 b）。沒有第三選項 |
| 「Phase 4 評估結論：[空]」 | 必填明確結論，如「無需重構」「採方案 A」「重構範圍 = X 模組」 |
| 「baseline 顯示需要再做」 | 建量測 ticket，量測結果作為 follow-up 的 trigger |

### 規則 4：違規偵測

| 違規類型 | 偵測時機 | 行為 |
|---------|---------|------|
| Ticket / 規則 / 規格中含「之後」「再決定」「以後」「暫緩」「Phase X 再」字面，且 frontmatter 無 `spawned_tickets` / `blockedBy` 連結，內文也無有效 ticket ID 格式引用 | 寫入時驗證機制 | 警告 + 提示寫法（不阻擋；驗證機制偵測自由文字含 ticket 引用有限度） |
| Phase 4 評估結論為空或含「Phase 5 再決定」 | complete 前驗證機制 | 阻擋（quality-baseline 規則 2 已強制） |

---

## 反模式範例

**範例 1（合法 vs 違規）**：

| 違規 | 合法 |
|------|------|
| 「X 實作以後再說」 | 「X 實作待 `<follow-up-ticket-id>`（X 評估）完成後決策」+ 已建對應 ticket |
| 「這個精度問題之後再修」 | 引用既有 pending ticket ID 並附加證據（如新案例 append 進該 ticket Problem Analysis） |
| 「Phase 4 視 baseline 結果再決定」 | 「Phase 4 結論：採 cache（baseline = 84ms < 100ms AC，無需 cache）」 |

**範例 2（合法的「探索性」處理）**：

長期研究 / 等技術成熟 / 等市場訊號這類本質長期延後，仍受本規則拘束——必須建定期重評 ticket 或監測 ticket，再以 ticket ID 作為 trigger。本規則不設「探索性例外」。

---

## 與其他規則的邊界

| 規則 | 聚焦 | 與本規則差異 |
|------|------|------------|
| `quality-baseline.md` 規則 2 | Phase 4 不可跳過 | 本規則延伸：Phase 4 結論必須是狀態（a），禁止「Phase 5 再決定」 |
| `quality-baseline.md` 規則 5 | 所有發現必須追蹤 | 本規則延伸：發現後若無法立刻決策，必須綁 follow-up ticket trigger |
| `PC-093-yagni-deferred-decision-accumulation.md` | 反模式描述 | 本規則為正向 prescriptive guidance（PC-093 描述問題，本規則開藥方） |
| `document-writing-style.md` | 三明示原則 | 互補：本規則處理「決策狀態明示」，document-writing-style 處理「論述明示」 |
| `pm-rules/execution-discovery-rules.md`「遇到問題的閉環流程」 | 流程層 | 本規則是聲明（禁止無 trigger 延後），閉環流程是執行（不能立刻決策時的合法 5 step：識別 → 建 ANA/DOC → Solution 規劃 spawned 驗證/實驗 → 執行 → 釐清結案）。兩者互補形成完整閉環 |

---

## 檢查清單

撰寫 ticket / 規則 / 規格 / commit / 註解前自問：

- [ ] 內容含「之後」「再決定」「以後」「暫緩」「Phase X 再」「待後續」等表述？
- [ ] 若有，已建立對應 follow-up ticket 並標 `spawned_tickets` / `blockedBy` 連結，或內文有 `W\d+-\d+` 格式 ticket ID 引用？
- [ ] 若無 follow-up ticket，是否能立刻下結論（狀態 a）？
- [ ] Phase 4 評估結論是否為明確結論（「無需重構」「採方案 A」），而非「Phase 5 再決定」？

---

**Last Updated**: 2026-05-02
**Version**: 1.0.0 — 從用戶原則「不應該在任何時候使用延後決策」+ WRAP 完整模式分析（D + A + E 三層落地，trigger 限 ticket ID only，不設探索性例外）建立。
**Source**: PC-093 反模式描述的正向 prescriptive 替代框架；hook 精度誤判的合法 Phase 4 結論案例觸發本次反思。
