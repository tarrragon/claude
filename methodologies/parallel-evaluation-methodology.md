# 並行評估方法論

## 核心理念

### 最小充分行動原則（Minimum Sufficient Action）

> 只做剛好夠用的事，不要大砲打小鳥。

並行評估的核心不是「找出所有問題」，而是「快速識別值得行動的問題」。每一個改善建議都有成本（變更風險、review 時間、認知負擔），只有當改善幅度明確大於成本時，才值得執行。

### 並行掃描 → 彙整 → 值得改才改

這是一個三步驟的品質掃描模式：

1. **收集標的** — 確定要掃描什麼
2. **多視角同時掃描** — 每個視角從不同角度檢查同一個標的
3. **過濾後行動** — 只保留值得改的項目，其餘跳過

### 與既有工具的定位差異

| 工具 | 定位 | 產出 |
|------|------|------|
| multi-perspective-analysis | 理解問題（分析型） | 多角度理解 |
| /design-decision-framework | 方案比較（評估型） | 方案排名 |
| **並行評估** | **品質掃描（決策型）** | **做/不做清單** |
| /bulk-evaluate | 批量處理（卸載型） | N 個子 Ticket 結論 |

關鍵差異：並行評估不比較方案，而是從多個視角同時掃描一個標的，產出的是經過過濾的「值得行動」清單。

### 常駐委員制度

每次並行評估除了情境特定視角外，**必須**包含 linux（品質把關）作為常駐委員：

```
每次 parallel-evaluation 執行:
  情境特定視角 (2-3 個) + 常駐委員 linux (1 個) = 3-4 個 Agent
```

**linux 常駐視角**（所有情境通用）：

| 檢查焦點 | 核心問題 |
|---------|---------|
| 設計簡潔性 | 能用更簡單的方式嗎？ |
| 問題真實性 | 是在解決真實問題還是假想問題？ |
| 特例消除 | 有不必要的特例嗎？能透過重新設計消除嗎？ |
| 向後相容性 | 會破壞任何現有行為嗎？ |

**品質評分**：Good taste / Acceptable / Garbage

**與 Worth-It Filter 的整合**：linux 評分直接對應 Worth-It Filter 的改善幅度（Garbage = 高、Acceptable = 中、Good taste = 無發現），走同一套規則，無特例。

---

## 通用三階段流程

### Phase 1: 收集標的（Gather Target）

確定掃描範圍和標的物。

| 標的類型 | 範例 |
|---------|------|
| 程式碼變更 | git diff 的檔案清單 |
| 架構設計 | 設計文件或程式碼模組 |
| 分析報告 | incident-responder 產出的結論 |
| 功能規格 | Phase 1 產出的 API 定義 |

**收集原則**：

- 標的範圍越精確，視角掃描越有效
- 過大的標的應先拆分再評估
- 明確列出「不在範圍內」的項目

### Phase 2: 並行視角掃描（Parallel Lens Scan）

啟動 2-4 個 Agent，每個 Agent 負責一個視角（Lens），同時掃描標的。

**視角設計原則**：

1. **獨立性** — 每個視角有明確且不重疊的檢查焦點
2. **可操作性** — 視角的發現必須能轉化為具體行動
3. **數量控制** — 2-4 個視角為佳；超過 4 個則噪音大於訊號
4. **Agent 匹配** — 每個視角應匹配最適合的 Agent 類型

**並行執行**：

- 所有視角同時啟動，互不依賴
- 每個 Agent 獨立產出發現清單
- Agent 之間不需要溝通

### Phase 3: 彙整與行動過濾（Aggregate & Filter）

收集所有視角的發現，通過 Worth-It Filter 決定執行方式。所有發現都必須追蹤（Ticket 或 todolist），Filter 只決定「立即執行」或「延後追蹤」。

**彙整流程**：

1. 合併所有視角的發現清單
2. 去重（多個視角發現同一問題時合併，可信度提升）
3. 對每個發現套用 Worth-It Filter
4. 產出最終的行動清單

---

## Worth-It Filter（執行決策規則）

> **核心原則**：發現技術債和決定修復成本是兩個獨立決策。Worth-It Filter 只回答「現在修還是之後修」，不回答「要不要追蹤」— 答案永遠是「要」。

### 核心公式

```
行動價值 = 改善幅度 / (變更風險 + 實施成本)
```

當行動價值 > 門檻時，該項目值得立即執行。低於門檻時延後，但仍必須建 Ticket 追蹤。

### 量化門檻表

| 改善幅度 | 變更風險 | 執行決策 | 追蹤方式 |
|---------|---------|---------|---------|
| 高（消除 bug/安全漏洞） | 任何 | 立即執行 | 建 Ticket（P0/P1） |
| 高（顯著簡化） | 低 | 立即執行 | 建 Ticket（P1） |
| 高（顯著簡化） | 高 | 延後執行 | 建 Ticket（P1） |
| 中（可讀性/維護性） | 低 | 立即執行 | 建 Ticket（P2） |
| 中（可讀性/維護性） | 高 | 延後執行 | 建 Ticket（P2） |
| 低（風格偏好） | 任何 | 延後執行 | 建 Ticket（P2） |

### False Positive 處理原則

> 執行有疑慮就延後，但追蹤不可省略。

- 如果需要超過 30 秒解釋「為什麼這值得**現在**改」，就延後
- 多個視角同時發現的問題，可信度更高
- 只有一個視角發現且改善幅度為「中」的項目，降級為延後

> 量化標準和案例：.claude/skills/parallel-evaluation/references/worth-it-filter-details.md

---

## 情境速查與 Worth-It Filter 特化

> 情境快速選擇表和視角表格：.claude/skills/parallel-evaluation/SKILL.md
> 各視角完整檢查項目：references/lens-configurations.md
> Agent 提示模板：references/lens-prompts.md

各情境的 Worth-It Filter 特化規則：

| 情境 | Worth-It Filter 特化 |
|------|---------------------|
| A: 程式碼審查 | 風格偏好延後追蹤；只立即行動於有具體改善的項目 |
| B: 重構評估 | 重構成本必須低於維護成本的 3 倍 |
| C: 架構評估 | 不一致性必須是實際問題（非美學偏好） |
| D: 功能評估 | 功能重疊超過 50% 時必須合併或重新定義 |
| E: 冗餘偵測 | 只處理跨模組的重複（同模組內由 Phase 4 處理） |
| F: 結論審查 | 閾值更嚴格 — 任一視角發現問題必須回到分析階段 |
| G: 系統設計 | 術語不一致必須修正；交叉引用缺失必須補齊；風格偏好延後追蹤 |

### 情境 G 與情境 A 的區別

| 維度 | 情境 A（程式碼審查） | 情境 G（系統設計評估） |
|------|-------------------|---------------------|
| 標的 | `*.dart`, `*.py` 程式碼 | `*.md` 規則/Skill/方法論 |
| 視角 | Reuse, Quality, Efficiency | Consistency, Completeness, Cognitive Load |
| 關注點 | 執行效率、重複程式碼 | 設計一致性、覆蓋完整性 |

### 情境 F 與 incident-response 流程的整合

```
錯誤發生 → /pre-fix-eval → incident-responder 分析
→ 情境 F 並行審查分析結論
→ 審查通過 → 建立 Ticket → 派發修復
→ 審查不通過 → 回到分析，補充遺漏的視角
```

---

## 與決策樹的整合點

| 決策樹層級 | 整合方式 |
|-----------|---------|
| 第負一層（並行化評估） | 並行評估本身就是並行派發的應用 |
| 第五層（TDD Phase 4） | 情境 B 可用於重構決策 |
| 第六層（事件回應） | 情境 F 用於審查 incident 分析結論 |

### 觸發建議

| 場景 | 建議情境 |
|------|---------|
| Phase 3b 完成後 | 情境 A（程式碼審查） |
| Phase 4 開始前 | 情境 B（重構評估） |
| SA 前置審查 | 情境 C（架構評估） |
| Phase 1 完成後 | 情境 D（功能評估） |
| 版本規劃時 | 情境 E（冗餘偵測） |
| incident 分析後 | 情境 F（結論審查） |
| 規則/Skill/方法論變更後 | 情境 G（系統設計評估） |

---

## 報告輸出格式

```markdown
## 並行評估報告

**標的**: [掃描範圍描述]
**情境**: [A-G]
**視角數**: [N]

### 值得行動的發現

| # | 視角 | 發現 | 改善幅度 | 變更風險 | 決策 |
|---|------|------|---------|---------|------|
| 1 | [視角名] | [描述] | 高/中/低 | 高/中/低 | 執行/延後 |

### 延後追蹤（建 Ticket，不立即執行）

| # | 視角 | 發現 | 延後原因 | Ticket |
|---|------|------|---------|--------|
| 1 | [視角名] | [描述] | [原因] | [Ticket ID] |

### 結論

[總結和建議]
```

---

## 相關文件

- .claude/skills/parallel-evaluation/SKILL.md - 操作指南
- .claude/skills/parallel-evaluation/references/lens-configurations.md - 視角配置詳細
- .claude/skills/parallel-evaluation/references/lens-prompts.md - Agent 提示模板
- .claude/skills/parallel-evaluation/references/worth-it-filter-details.md - 過濾標準詳細
- .claude/skills/parallel-evaluation/references/integration-guide.md - 整合指南
- .claude/rules/core/decision-tree.md - 主線程決策樹
- .claude/rules/guides/parallel-dispatch.md - 並行派發指南

---

**Last Updated**: 2026-03-02
**Version**: 1.1.0 - 情境模組精簡 + Agent 提示模板提取
