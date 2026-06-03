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

**禁止**：無 trigger 延後（「Phase X 再決定」「以後再評估」「之後處理」「將來」「暫緩」「baseline 顯示需要再做」「待後續觀察」）。

**Why**：無 trigger 延後在「以後」與「永不」之間沒有可驗證邊界，必然累積為死議題（PC-093 的根源）。

**Consequence**：違反此規則的延後表述會在執行階段成為灰色地帶，驗收沒有完成定義，後人接手不知該不該補做。

**Action**：撰寫前自問「這個決策現在能不能下結論？」能 → 寫結論（狀態 a）；不能 → 建 follow-up ticket 並引用 ID（狀態 b）。

### 規則 1.5：適用邊界——程式碼/文件 vs worklog/ticket

決策狀態的嚴格度依載體區分：

| 載體 | 可述未來考量？ | 必須綁 ticket trigger？ | 範例 |
|------|--------------|---------------------|------|
| 程式碼註解（架構討論） | 是 | 否（情境陳述） | 「未來若加入 X 模組，此處需改為 Y」（屬設計筆記，非延後決策） |
| 規則 / 方法論 / 提案 | 是 | 否（原則陳述） | 「未來擴展點：可加入 Z」（屬擴充性說明） |
| Worklog / Ticket body | 否 | 是（必須是狀態 a 或 b） | 任何「下週處理」「之後再說」「下版本再做」均違規 |
| Phase 4 評估結論 | 否 | 是 | 必填明確結論，禁止「Phase 5 再決定」 |

**Why**：程式碼/文件的「未來考量」是設計脈絡傳遞，幫助後人理解決策空間；worklog/ticket 是執行追蹤單位，「未來」若無 ticket 錨點即等於遺失。摩擦力方法論（`.claude/methodologies/friction-management-methodology.md`）核心：所有任務都有排程權重，只是輕重緩急不同；難題反而應優先（大石頭先放），時間（一週後/一個月後）不是任務權重的合法衡量單位。

**Consequence**：worklog 中以時間為延後依據（「下週處理」「下個月再做」）會在繁忙期系統性失效——時間到了沒人記得評估，且無 acceptance 可勾選；該決策在「以後」與「永不」之間沒有可驗證邊界。

**Action**：寫 worklog / ticket 時，若想表達「之後再處理」，先問「這是排程問題還是決策問題？」排程問題 → 改用 ticket 計數或版本錨點 trigger（規則 2 替代方案表新增兩列）；決策問題 → 立刻決策（狀態 a）或建 follow-up ticket（狀態 b）。

### 規則 2：合法 trigger 限 ticket ID

只有 ticket ID 是合法 trigger。其他形式（時間、量化閾值、外部事件）必須先包裝為 ticket：

| 想表達 | 錯誤 | 正確 |
|--------|------|------|
| 等 baseline > 80ms 才做 | 「baseline > 80ms 時觸發」 | 建監測 ticket（描述「監測 X 指標，> 80ms 時建 follow-up」），本決策標 `blockedBy: [<ticket-id>]` |
| 等外部版本發布 | 「外部版本 vN 發布後處理」 | 建追蹤 ticket，本決策標 `blockedBy` |
| 等指定日期重評 | 「YYYY-MM-DD 重新評估」 | 建排定 ticket，本決策標 `blockedBy` |
| 等用戶反饋累積 | 「累積 10+ 案例後評估」 | 建監測 ticket，本決策標 `blockedBy` |
| 等執行 N 個 ticket 後重評 | 「跑一週看看再說」 | 「執行 N 個同類 ticket 後重評」+ 建監測 ticket 計數 |
| 下一版本再處理 | 「下個月再做」 | 「v0.X+1 開版時新增重評 ticket」+ 建版本錨點 ticket |

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
| Ticket / 規則 / 規格中含「之後」「再決定」「以後」「將來」「暫緩」「Phase X 再」「下週」「下個月」字面，且 frontmatter 無 `spawned_tickets` / `blockedBy` 連結，內文也無有效 ticket ID 格式引用 | 寫入時驗證機制 | 警告 + 提示寫法（不阻擋；驗證機制偵測自由文字含 ticket 引用有限度） |
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

## Hook 引用豁免機制（W10-126 補強）

phase4-decision-enforcement-hook 對「Phase X 再決定」「延後評估」等字面強制偵測，但合法情境（規則引用、source ticket 歷史 context 引用）需用 `<!-- PC-093-exempt: <category>:<reason> -->` 標記豁免。

### 合法豁免類別

| Category | 適用情境 | reason 要求 |
|---------|---------|------------|
| `rule-quote` | 引用 `.claude/rules/` 或 `.claude/pm-rules/` 規則名稱 | reason 須含 `.claude/rules/` 或 `.claude/pm-rules/` 路徑 |
| `ticket-tracked` | 引用既有 ticket ID（如 source ticket why 含歷史延後話術描述） | reason 須含 `W\d+-\d+` 格式 ticket ID |
| `baseline-gated` | 量化基線觸發條件（如「baseline > 100ms 則重啟」） | reason 須含數字 |
| `tdd-transition` | TDD phase 轉換的合法延後 | 一般說明 ≥ 10 字 |
| `user-override` | 用戶明確授權的延後 | 一般說明 ≥ 10 字 |
| `history` | 引用已完成歷史 / 動機脈絡（如 IMP ticket 開頭引用 parent ANA 多視角審查發現作 Problem Analysis 背景） | reason 須含 `W\d+-\d+` 格式 ticket ID 作歷史錨點 |

**`history` vs `ticket-tracked` 語意區分**：

| Category | 語意 | 典型情境 |
|---------|------|---------|
| `ticket-tracked` | 「等待該 ticket 完成後處理」（延後決策有 trigger） | source ticket why 含歷史延後話術描述、引用尚未 complete 的 follow-up ticket |
| `history` | 「引用已完成歷史 / 動機脈絡」（非延後，是事實陳述） | IMP Problem Analysis 開頭引用 parent ANA 審查發現、回顧已 complete ticket 的決策歷程 |

### 標記位置規則（PC-146 / EXEMPT_PROXIMITY_LINES=1）

marker 必須**緊鄰命中行**：同一行行尾，或命中行上方一行（中間不可有空行 / 標題等元素）。

正確：

```markdown
<!-- PC-093-exempt: ticket-tracked:本段為 W10-118 source ticket why 引用 -->
- 0.18.0-W10-118 why: ...「Phase 5 再決定」...
```

或：

```markdown
- 0.18.0-W10-118 why: ...「Phase 5 再決定」... <!-- PC-093-exempt: ticket-tracked:W10-118 引用 -->
```

錯誤（marker 與命中行物理分離）：

```markdown
- 0.18.0-W10-118 why: ...「Phase 5 再決定」...

### Hook 引用豁免章節                                ← marker 與命中行隔了空行 + 標題
<!-- PC-093-exempt: ... -->
```

### 多命中行情境

每個命中行各加一個 marker，不可共用一個（hook 行級獨立判定）。

詳見 PC-146（exempt marker 位置誤用 + 三層防護）。

### Frontmatter 場景：不需 exempt marker（W1-092 起）

ticket frontmatter（YAML 區塊，`when` / `why` / `strategy` 等欄位）內出現「Phase 4 評估」「Phase 5 再決定」等歷史字面時，**不需要**加 `PC-093-exempt` marker。

**Why**：phase4-decision-enforcement-hook 自 W1-092（PC-142 case 5 修復）起，透過 `compute_frontmatter_lines` 將整個 frontmatter 區塊（含起訖 `---`）排除於 phrase 掃描與 marker 蒐集範圍之外。frontmatter 為結構化元資料，其欄位常含 source ticket history 引用字面，本質與 Context Bundle auto-extracted、Schema placeholder、fenced code block 同類——非人類撰寫的當下延後決策論述，故整段跳過。

**Consequence**：若仍在 frontmatter 欄位內加 `PC-093-exempt` marker，會造成兩層問題：(1) marker 對 hook 無作用（該區塊不被掃描，marker 也不被蒐集），屬冗餘標記；(2) ticket CLI complete 後的 metadata sync 會以 PyYAML round-trip 重新序列化 frontmatter，行內 markdown 註解形式的 marker 不被當 YAML 註解而是 scalar 值的一部分，序列化後可能位置漂移或被移除，產生「marker 一加就消失」的錯覺。W1-048.3（2026-05-23）即為此模式：sage 在 hook 修復前加 marker 才能 complete，complete 後 metadata sync 移除 marker——但因 W1-092 已讓 hook 不掃 frontmatter，marker 的存廢不再影響 complete。

**Action**：

| 字面所在位置 | 是否需 marker | 理由 |
|------------|-------------|------|
| frontmatter（`---` 區塊內的 YAML 欄位） | 否 | hook 整段跳過（W1-092），加 marker 冗餘且會被 metadata sync 移除 |
| body 一般論述（`## Solution` 等章節文字） | 是 | hook 行級掃描，命中需 marker 豁免 |
| body 內 fenced code block / Schema placeholder / Context Bundle auto-extracted | 否 | hook 各自整段跳過（W11-018 / W10-130 / W1-120） |

**判別準則**：marker 只在「hook 會掃描且會命中」的 body 論述行才有意義。frontmatter 與上述三類整段豁免區塊內，移除 marker 不會造成 hook 阻擋，無需保留。

## 與其他規則的邊界

| 規則 | 聚焦 | 與本規則差異 |
|------|------|------------|
| `quality-baseline.md` 規則 2 | Phase 4 不可跳過 | 本規則延伸：Phase 4 結論必須是狀態（a），禁止「Phase 5 再決定」 |
| `quality-baseline.md` 規則 5 | 所有發現必須追蹤 | 本規則延伸：發現後若無法立刻決策，必須綁 follow-up ticket trigger |
| `PC-093-yagni-deferred-decision-accumulation.md` | 反模式描述 | 本規則為正向 prescriptive guidance（PC-093 描述問題，本規則開藥方） |
| `document-writing-style.md` | 三明示原則 | 互補：本規則處理「決策狀態明示」，document-writing-style 處理「論述明示」 |
| `pm-rules/execution-discovery-rules.md`「遇到問題的閉環流程」 | 流程層 | 本規則是聲明（禁止無 trigger 延後），閉環流程是執行（不能立刻決策時的合法 5 step：識別 → 建 ANA/DOC → Solution 規劃 spawned 驗證/實驗 → 執行 → 釐清結案）。兩者互補形成完整閉環 |
| `methodologies/friction-management-methodology.md` | 摩擦力 / 排程權重理論 | 本規則延伸：所有任務都有排程權重，時間（週 / 月）不是合法權重單位；難題優先排（大石頭先放）；改用 ticket 計數或版本錨點作 trigger |

---

## 檢查清單

撰寫 ticket / 規則 / 規格 / commit / 註解前自問：

- [ ] 內容含「之後」「再決定」「以後」「將來」「暫緩」「Phase X 再」「待後續」「下週」「下個月」等表述？
- [ ] 載體屬 worklog / ticket / Phase 4 結論？若是，必須為狀態 (a) 或狀態 (b)，不可述「未來考量」（規則 1.5）
- [ ] 若有，已建立對應 follow-up ticket 並標 `spawned_tickets` / `blockedBy` 連結，或內文有 `W\d+-\d+` 格式 ticket ID 引用？
- [ ] 若無 follow-up ticket，是否能立刻下結論（狀態 a）？
- [ ] Phase 4 評估結論是否為明確結論（「無需重構」「採方案 A」），而非「Phase 5 再決定」？

---

**Last Updated**: 2026-06-02 | **Version**: 1.4.0 — 新增「Frontmatter 場景：不需 exempt marker」章節，釐清 phase4-hook 自 W1-092 起整段跳過 frontmatter，marker 在 frontmatter 內冗餘且會被 metadata sync 移除（W1-052）。歷史 1.0–1.3 版見 git log。**Source**: PC-093 / PC-146 / W11-023 / W1-092。
