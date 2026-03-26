---
name: parallel-evaluation
description: "並行評估決策工具。啟動多個 Agent 從不同視角並行掃描，所有發現必須追蹤（Ticket 或 todolist），Worth-It Filter 只決定執行時機。Use for: 重構前掃描冗餘/重複, 架構方案快速評估, 系統設計品質掃描, 結論/報告審查, 任何需要多角度快速評估的決策"
---

# 並行評估工具

> 方法論: .claude/methodologies/parallel-evaluation-methodology.md

## 核心流程

**Phase 1** → 收集標的（確定掃描範圍）
**Phase 2** → 並行視角掃描（2-4 Agent 同時掃描）
> Phase 2 預算檢查: `reference_tokens + (N x avg_target_tokens) + (N x output_tokens) < 100,000`。超過則減少 N 或拆分標的。

**Phase 3** → 彙整 + Worth-It Filter（決定執行方式，所有發現必須追蹤）
> Phase 3 衝突處理：視角間有衝突時，依衝突分類策略處理（加法vs減法預設減法，linux 品味否決權）。詳見 multi-perspective-analysis-methodology.md「衝突處理策略」。

## 情境快速選擇

| 情境 | 適用時機 | 視角 | Agent 數 |
|------|---------|------|---------|
| A: 程式碼審查 | Phase 3b 後、PR 前 | Reuse + Quality + Efficiency | 3 |
| B: 重構評估 | Phase 4 前、TD 清理 | Redundancy + Coupling + Complexity | 3 |
| C: 架構評估 | SA 審查、新架構決策 | Consistency + Impact + Simplicity | 3 |
| D: 功能評估 | Phase 1 後、需求確認 | Overlap + Fit + Scope | 3 |
| E: 冗餘偵測 | 版本規劃、系統清理 | Duplication + State + Interface | 3 |
| F: 結論審查 | 任何分析報告產出後 | Evidence + Alternatives + Scope | 3 |
| G: 系統設計 | 規則/Skill/方法論變更後 | Consistency + Completeness + CogLoad | 3 |

> 各視角詳細檢查項目: references/lens-configurations.md

**常駐委員**：所有情境自動加入 linux（Good Taste 品質把關），總計 3-4 個 Agent。linux 評分對應 Worth-It Filter：Garbage = 高幅度、Acceptable = 中幅度、Good taste = 無發現。Wave 完成審查時，除了標準的多視角代理人外，必須額外派發 linux 代理人作為常駐審查委員，與 code-reviewer（Bug/安全）和 code-explorer（架構/設計）組成固定三人組（見 parallel-dispatch.md 多視角審查固定三人組章節）。

## Worth-It Filter 快速判斷

> **核心原則**：Worth-It Filter 只決定「是否立即執行」，不決定「是否追蹤」。所有發現都必須建 Ticket 或寫入 todolist。發現技術債是一個問題，修復成本是否值得是另一個問題 — 兩者不在同一時刻決策。

| 改善幅度 | 風險低 | 風險高 | 追蹤方式 |
|---------|--------|--------|---------|
| 高（bug/安全） | 立即執行 | 立即執行 | 建 Ticket（P0/P1） |
| 高（簡化） | 立即執行 | 延後執行 | 建 Ticket（P1） |
| 中（維護性） | 立即執行 | 延後執行 | 建 Ticket（P2） |
| 低（風格） | 延後執行 | 延後執行 | 建 Ticket（P2） |

**原則**: 執行有疑慮就延後，但追蹤不可省略。

> 量化標準和案例: references/worth-it-filter-details.md

## 執行範例

### 情境 A: 程式碼變更審查

```
Phase 1: git diff --name-only 取得變更檔案
Phase 2: 並行派發 3 Agent
  - Explore: 掃描是否有可重用的既有 utility
  - code-reviewer #1: 掃描冗餘狀態和 copy-paste
  - code-reviewer #2: 掃描不必要的工作和效能問題
Phase 3: 彙整發現 → Worth-It Filter → 行動清單
```

### 情境 F: 結論審查

```
Phase 1: 收集分析報告/結論
Phase 2: 並行派發 3 Agent
  - Explore #1: 驗證結論是否有程式碼佐證
  - Plan: 檢查是否遺漏替代方案
  - Explore #2: 評估影響範圍估計是否合理
Phase 3: 任一視角發現問題 → 回到分析階段補充
```

## 報告格式

```markdown
## 並行評估報告

**標的**: [範圍]  **情境**: [A-G]

### 值得行動

| # | 視角 | 發現 | 幅度 | 風險 | 決策 |
|---|------|------|------|------|------|

### 延後追蹤（建 Ticket，不立即執行）

| # | 視角 | 發現 | 延後原因 | Ticket |
|---|------|------|---------|--------|

### 結論
[總結]
```

## 與 `/bulk-evaluate` 的區別

| 維度 | `/parallel-evaluation` | `/bulk-evaluate` |
|------|----------------------|--------------------|
| 並行軸 | N 個視角 x 1 組標的 | 1 個標準 x N 個單位 |
| 產出物 | 彙整報告（回到主線程） | N 個子 Ticket（不回主線程） |
| 適用 | 多角度快速評估 | 批量處理 + context 卸載 |

**選擇原則**：需要多角度掃描同一標的 → 本工具；需要用同一標準掃描 N 個獨立目標 → `/bulk-evaluate`

## 相關文件

- .claude/methodologies/parallel-evaluation-methodology.md - 完整方法論
- .claude/skills/bulk-evaluate/SKILL.md - 批量評估（正交工具）
- references/lens-configurations.md - 視角配置
- references/worth-it-filter-details.md - 過濾標準
- references/integration-guide.md - 整合指南
