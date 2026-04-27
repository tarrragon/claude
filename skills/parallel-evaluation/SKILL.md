---
name: parallel-evaluation
description: "多視角審核/code review 工具。派發三人組（含常駐委員 linux）並行掃描程式碼品質、架構設計、重構評估。Use for: 程式碼審查, 架構評估, 重構掃描, 結論審查, 系統設計變更審查, 功能規劃審查。Use when: Phase 3b 完成後 PR 前, Phase 4 重構評估前, 重大架構決策前, ANA Ticket 結論審查, 任何分析報告產出後, 規則/Skill/方法論變更後, Wave 完成審查, 規格設計完成後"
---

# 並行評估工具

> 方法論: .claude/methodologies/parallel-evaluation-methodology.md

## 核心流程

**Phase 1** → 收集標的（確定掃描範圍）
**Phase 2** → 並行視角掃描（2-4 Agent 同時掃描）
> Phase 2 預算檢查: `reference_tokens + (N x avg_target_tokens) + (N x output_tokens) < 100,000`。超過則減少 N 或拆分標的。

**Phase 3** → 彙整 + Worth-It Filter + **建立 Ticket** + **錯誤模式記錄**（決定執行方式，所有發現必須追蹤）
> Phase 3 強制步驟：(1) 彙整發現 → (2) Worth-It Filter 分類 → (3) **對每個「延後執行」項目執行 `ticket create`** → (4) 將 Ticket ID 填入報告表格 → (5) **結構性發現→錯誤模式記錄**（見下方判斷標準）→ (6) 輸出報告。步驟 3-5 不可省略，報告中不可出現沒有 Ticket ID 的「延後追蹤」行。
> Phase 3 步驟 5 判斷標準：發現是否為**結構性模式**（跨專案可重現的錯誤類型，而非單次的專案 bug）？若是，執行 `/error-pattern add` 記錄到 `.claude/error-patterns/`。判斷方式：將發現中的專案名稱和檔案路徑替換為通用描述，如果仍然有意義 → 是結構性模式。
> Phase 3 衝突處理：視角間有衝突時，依衝突分類策略處理（加法vs減法預設減法，linux 品味否決權）。詳見 multi-perspective-analysis-methodology.md「衝突處理策略」。

## 常駐委員機制

parallel-evaluation 的常駐委員分兩類，加入規則與 opt-out 條件不同：

| 類型 | 代理人 | 加入情境 | 可 opt-out |
|------|--------|---------|-----------|
| `universal_lens` | linux | 所有情境（A-G）無條件加入（Good Taste / 架構複雜度為所有產出的元維度） | 否 |
| `default_lens_per_scenario` | basil-writing-critic | 情境 C / D / F / G 預設加入（書面文字產出量最高的場景）；情境 A / B / E 不加入 | 是（`--skip-basil`） |

**linux 常駐說明**：linux 評分對應 Worth-It Filter：Garbage = 高幅度、Acceptable = 中幅度、Good taste = 無發現。Wave 完成審查時，除了標準的多視角代理人外，必須額外派發 linux 代理人作為常駐審查委員，與 code-reviewer（Bug/安全）和 code-explorer（架構/設計）組成固定三人組（見 parallel-dispatch.md 多視角審查固定三人組章節）。

**basil opt-out 機制（`--skip-basil`）**：PM 在以下任一條件成立時可宣告 `--skip-basil`，略過本次 basil 加入：

| 條件 | 判斷依據 |
|------|---------|
| Context 使用率 > 70% 或 session 後段 | 剩餘 token 預算不足以同時承載 basil 審查輸出 |
| 審查標的為已知非文字密集產出 | 例如：schema 定義、YAML 設定、程式碼變更（僅情境 C/D/F/G 意外含大量程式碼） |
| 本 session 已完成一次 basil 審查且標的無重大變更 | 同一文件短期內重複審查，邊際收益低 |

**Why**：basil 在 C/D/F/G 預設加入是保護書面文字品質的必要機制；但強制無 opt-out 會在 token 緊張的 session 後段單方面增加 +33% 派發成本，違反「Never break userspace」（W17-066 linux L-W1 共識）。opt-out 讓 PM 在資源受限時能主動降低摩擦，同時保留預設強制的保護效果。

**Consequence**：未宣告 `--skip-basil` 即代表 basil 必然加入情境 C/D/F/G；濫用 `--skip-basil`（在非緊急條件下略過）會使文字品質防護缺失，後期需要更高成本的人工修正。

**Action**：PM 在 parallel-evaluation 情境判斷時，先確認情境屬 C/D/F/G，若是則 basil 預設加入；若任一 opt-out 條件成立，可宣告 `--skip-basil` 並在 Ticket append-log 記錄原因。

## 情境快速選擇

| 情境 | 適用時機 | 視角 | Agent 數 | basil 預設 |
|------|---------|------|---------|-----------|
| A: 程式碼審查 | Phase 3b 後、PR 前 | Reuse + Quality + Efficiency | 3 | 否 |
| B: 重構評估 | Phase 4 前、TD 清理 | Redundancy + Coupling + Complexity | 3 | 否 |
| C: 架構評估 | SA 審查、新架構決策 | Consistency + Impact + Simplicity | 3+1 | 是（`--skip-basil` 可 opt-out）|
| D: 功能評估 | Phase 1 後、需求確認 | Overlap + Fit + Scope | 3+1 | 是（`--skip-basil` 可 opt-out）|
| E: 冗餘偵測 | 版本規劃、系統清理 | Duplication + State + Interface | 3 | 否 |
| F: 結論審查 | 任何分析報告產出後 | Evidence + Alternatives + Scope | 3+1 | 是（`--skip-basil` 可 opt-out）|
| G: 系統設計 | 規則/Skill/方法論變更後 | Consistency + Completeness + CogLoad | 3+1 | 是（`--skip-basil` 可 opt-out）|

> 各視角詳細檢查項目: references/lens-configurations.md

**語言代理人加入規則**：當審查標的涉及語言/框架專屬的基礎設施或開發流程時，將對應語言代理人作為額外審查委員加入標準三人組：

| 審查標的涉及 | 加入代理人 | 常見場景 |
|-------------|-----------|---------|
| Flutter/Dart | parsley-flutter-developer | Widget 架構、Riverpod 設計、Dart 慣例 |
| Python | thyme-python-developer | Hook 系統、腳本設計、Python 慣例 |
| Go | fennel-go-developer | 後端服務、Go 慣例 |

此規則對情境 C（架構評估）和 D（功能評估）尤為重要，因為規劃階段的決策深受語言/框架限制影響。語言代理人可提供框架專業知識，避免產出不符合實際開發慣例的方案。

## Worth-It Filter 快速判斷

> **核心原則**：Worth-It Filter 只決定「是否立即執行」，不決定「是否追蹤」。所有發現都必須建 Ticket 或寫入 todolist。發現技術債是一個問題，修復成本是否值得是另一個問題 — 兩者不在同一時刻決策。

| 改善幅度 | 風險低 | 風險高 | 追蹤方式 |
|---------|--------|--------|---------|
| 高（bug/安全） | 立即執行 | 立即執行 | 建 Ticket（P0/P1） |
| 高（簡化） | 立即執行 | 延後執行 | 建 Ticket（P1） |
| 中（維護性） | 立即執行 | 延後執行 | 建 Ticket（P2） |
| 低（風格） | 延後執行 | 延後執行 | 建 Ticket（P2） |

**原則**: 執行有疑慮就延後，但追蹤不可省略。

**強制規則**：「延後執行」不等於「不建 Ticket」。Phase 3 產出報告前，必須對所有延後項目執行 `ticket create`，並在報告表格的 Ticket 欄填入實際 ID。**禁止行為**：報告中出現「延後」但 Ticket 欄為空。

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

> **強制**：此表格每一行的 Ticket 欄必須填入實際 Ticket ID（格式如 `{version}-W{wave}-{seq}`）。空白 Ticket 欄 = 未追蹤 = 違反 quality-baseline 規則 5。

| # | 視角 | 發現 | 延後原因 | Ticket |
|---|------|------|---------|--------|

### 結構性錯誤模式（已記錄到 error-patterns/）

> 此區段僅在有結構性發現時出現。判斷標準：將發現中的專案名稱和檔案路徑替換為通用描述，如果仍然有意義 → 記錄。

| # | Pattern ID | 標題 | 來源發現 |
|---|-----------|------|---------|

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

---

**Last Updated**: 2026-04-24
**Version**: 1.1.0 - 新增 basil-writing-critic 常駐委員機制（情境 C/D/F/G 預設加入）+ `--skip-basil` opt-out 機制 + 常駐委員概念拆分（universal_lens / default_lens_per_scenario）（W17-069 / W17-066 R-3）
