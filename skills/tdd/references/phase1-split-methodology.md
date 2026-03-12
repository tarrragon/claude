# Phase 1 SOLID 拆分方法論

本文件整合自 `tdd-phase1-split` SKILL，包含版本號分配規則、CLI 工具使用、拆分報告範本等 `/tdd split` 的補充指引。

> 核心 SOLID 檢查清單和拆分流程見 SKILL.md 的 `/tdd split` 命令。本文件提供進階工具和範本。

---

## CLI 工具

`/tdd` 提供 Python CLI 腳本輔助 SOLID 分析，位於 `scripts/tdd-phase1-split.py`。

### 可用命令

| 命令 | 用途 | 範例 |
|------|------|------|
| `analyze` | 互動式 SOLID 分析 | `uv run scripts/tdd-phase1-split.py analyze -d "實作書籍搜尋功能"` |
| `suggest` | 產出拆分建議 | `uv run scripts/tdd-phase1-split.py suggest -d "實作書籍搜尋功能" -v 0.29.0` |
| `create-tickets` | 建立拆分 Tickets | `uv run scripts/tdd-phase1-split.py create-tickets -d "實作書籍搜尋功能" -v 0.29.0 -w 3` |
| `validate` | 驗證拆分合規性 | `uv run scripts/tdd-phase1-split.py validate -t 0.29.0-W3-001` |
| `report` | 產出拆分報告 | `uv run scripts/tdd-phase1-split.py report -d "實作書籍搜尋功能" -v 0.29.0` |

> **執行方式**：在 `.claude/skills/tdd/` 目錄下執行 `uv run scripts/tdd-phase1-split.py <command>`。

### analyze（互動式分析）

逐一引導檢查 SRP、OCP、LSP、ISP、DIP，輸出分析報告。適用於初次接觸 SOLID 原則的場景，提供結構化問答。

### suggest（拆分建議）

根據功能描述和目標版本，自動產出拆分建議，包含：
- 子功能識別（按架構層分類）
- 版本號分配（依依賴關係）
- 並行/序列判斷

### validate（驗證拆分）

讀取已建立的 Ticket，驗證子 Ticket 是否符合 SRP（標題不含「和」、描述聚焦單一目標）。

---

## 版本號分配規則

拆分後的子任務需要合理的版本/批次分配，確保依賴關係正確。

### 分配原則

| 情況 | 版本/批次分配 | 範例 |
|------|-------------|------|
| 無依賴任務 | 同一批次（可並行） | Domain Entities -> 第一批 |
| 依賴前一批 | 下一個批次 | UseCases -> 第二批 |
| 依賴多批次 | 最後依賴的下一批 | Widget -> 第三批 |

### 並行判斷

| 條件 | 可並行 |
|------|--------|
| 同一批次 | 是 |
| 無 blockedBy | 是 |
| 不同架構層但無依賴 | 是 |
| 有 blockedBy | 否 |

### 架構層級執行順序

| 架構層 | 執行順序 | 說明 |
|--------|---------|------|
| Domain | 第一批 | Entity、Value Object、介面定義（無依賴） |
| Application | 第二批 | UseCase（依賴 Domain） |
| Infrastructure | 第二批 | Repository 實作（依賴 Domain 介面） |
| Presentation | 第三批 | Widget、Controller（依賴 Application） |

> **框架整合**：本專案使用 Patch 版本號（如 v0.29.1 -> v0.29.2）對應批次，由 `/ticket create` 管理。

---

## 拆分報告範本

Phase 1 拆分分析完成後，使用以下範本產出報告：

```markdown
## Phase 1 拆分報告

### 原始需求
- **描述**: {需求描述}
- **預估複雜度**: 高 / 中 / 低

### SOLID 分析

| 原則 | 分析結果 | 拆分建議 |
|------|---------|---------|
| SRP | {結果} | {建議} |
| OCP | {結果} | {建議} |
| LSP | {結果} | {建議} |
| ISP | {結果} | {建議} |
| DIP | {結果} | {建議} |

### 拆分清單

| 編號 | 描述 | 架構層 | 執行批次 | 依賴 |
|------|------|--------|---------|------|
| A | {描述} | Domain | 第一批 | 無 |
| B | {描述} | Application | 第二批 | A |

### 執行計畫
1. 第一批（可並行）：A、B、C
2. 第二批（序列）：D（依賴 A、B）
3. 第三批（序列）：E（依賴 D）
```

---

## 拆分範例（書籍搜尋功能）

**原始需求**：「實作書籍搜尋功能」

**SOLID 分析摘要**：

| 原則 | 結果 |
|------|------|
| SRP | 識別 3 個職責：查詢建立、搜尋執行、結果呈現 |
| OCP | 搜尋來源可能多樣（本地、API），需要抽象 |
| DIP | UseCase 不應依賴具體 Repository |

**拆分結果**：

```
父任務：書籍搜尋功能
├── A: SearchQuery 值物件       [Domain]         第一批  無依賴
├── B: SearchResult Entity     [Domain]         第一批  無依賴
├── C: ISearchRepository 介面   [Domain]         第一批  無依賴
├── D: SearchBooksUseCase      [Application]    第二批  依賴 A, B, C
├── E: SearchRepository 實作    [Infrastructure] 第二批  依賴 C
└── F: SearchWidget            [Presentation]   第三批  依賴 D
```

**執行順序**：
1. 第一批（A + B + C 可並行）
2. 第二批（D + E，D 依賴 A/B/C，E 依賴 C）
3. 第三批（F 依賴 D）

---

## 相關資源

- `/tdd split` 命令：`../SKILL.md`（SOLID 檢查清單和拆分流程）
- Phase 1 設計指引：`phase1-design.md`（功能規格、API 設計、GWT 場景）
- 可攜式設計邊界：`portable-design-boundary.md`
- 任務拆分指南：`.claude/rules/guides/task-splitting.md`

---

**Last Updated**: 2026-03-12
**Version**: 1.0.0 - 從 tdd-phase1-split SKILL 遷移整合
**Source**: .claude/skills/tdd-phase1-split/SKILL.md
