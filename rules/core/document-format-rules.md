# 文件格式規則

本文件定義專案中所有交接文件的格式規範。

---

## 適用範圍

**交接文件定義**：用於團隊協作和知識傳遞的文件

| 文件類型 | 存放位置 |
|---------|---------|
| 計畫文件 | `.claude/plans/` |
| 工作日誌 | `docs/work-logs/` |
| Ticket 文件 | `docs/work-logs/v{version}/tickets/` |
| 錯誤模式記錄 | `.claude/error-patterns/` |
| README 文件 | 各目錄下的 `README.md` |

---

## 強制規則

### 規則 1：禁止使用 Emoji

**所有交接文件禁止使用 emoji 符號**

| 禁止 | 替代方案 | 範例 |
|------|---------|------|
| :white_check_mark: / :heavy_check_mark: | `[x]` | `[x] 任務已完成` |
| :x: / :negative_squared_cross_mark: | `[ ]` | `[ ] 待處理項目` |
| :warning: | `[WARNING]` 或 `警告：` | `[WARNING] 注意事項` |
| :bulb: | `提示：` 或 `建議：` | `建議：考慮使用 LSP` |
| :fire: / :rocket: | 純文字描述 | `高優先級` |

**理由**：
- 確保跨平台相容性
- 維持專業性
- 避免渲染問題

### 規則 2：狀態標記

使用純文字標記狀態：

| 狀態 | 標記方式 | 範例 |
|------|---------|------|
| 完成 | `[x]` 或 `completed` | `- [x] 完成規格設計` |
| 未完成 | `[ ]` 或 `pending` | `- [ ] 待實作功能` |
| 進行中 | `in_progress` | `status: in_progress` |
| 阻塞 | `blocked` | `status: blocked` |

### 規則 3：優先級標記

使用文字而非符號標記優先級：

| 優先級 | 標記方式 | 說明 |
|-------|---------|------|
| P0 | `高` 或 `P0` | 緊急，立即處理 |
| P1 | `中` 或 `P1` | 重要，本版本處理 |
| P2 | `低` 或 `P2` | 一般，排入後續 |

### 規則 4：Markdown 格式規範

| 規範 | 說明 |
|------|------|
| 標題層級 | 使用 `#` 到 `####`，避免超過 4 層 |
| 清單縮排 | 使用 2 或 4 個空格 |
| 程式碼區塊 | 使用三個反引號並標明語言 |
| 表格對齊 | 使用 `|` 分隔，`:---` 控制對齊 |
| 連結格式 | `@path/to/file.md` 引用格式 |

### 規則 5：檔案命名規範

| 類型 | 格式 | 範例 |
|------|------|------|
| 工作日誌 | `v{版本}-{描述}.md` | `v0.29.0-ticket-system-refactor.md` |
| Ticket | `{版本}-W{波次}-{序號}.md` | `0.29.0-W1-001.md` |
| 規則檔案 | `{描述}-{類型}.md` | `language-constraints.md` |
| 方法論 | `{主題}-methodology.md` | `atomic-ticket-methodology.md` |

---

## YAML Frontmatter 規範

Ticket 和工作日誌應包含 YAML frontmatter：

```yaml
---
id: {文件 ID}
title: {標題}
type: {類型}
status: {狀態}
created: {建立日期}
updated: {更新日期}
---
```

---

## 跨檔案引用格式規範

### 規則 6：引用路徑格式

| 引用場景 | 格式 | 範例 |
|---------|------|------|
| Skill 內部引用（同 Skill 目錄） | 相對路徑 | `references/workflow-create.md` |
| 跨 Skill 引用 | 完整路徑（從 .claude/ 開始） | `.claude/skills/doc-flow/SKILL.md` |
| 引用 rules/references | 完整路徑 | `.claude/rules/core/quality-baseline.md` |
| 引用專案根目錄檔案 | 從根目錄開始 | `docs/work-logs/v{VERSION}/` |
| CLAUDE.md 中的引用 | `@` 前綴 | `@.claude/rules/core/quality-baseline.md` |

**理由**：
- 內部引用用相對路徑，搬移 Skill 目錄時只需改外部引用
- 跨 Skill 引用用完整路徑，避免閱讀者不知道要從哪個目錄起算

---

## 檢查清單

建立交接文件時，確認：

- [ ] 無 emoji 符號
- [ ] 使用純文字狀態標記
- [ ] 優先級使用「高/中/低」或「P0/P1/P2」
- [ ] Markdown 格式正確
- [ ] 檔案命名符合規範
- [ ] 有適當的 frontmatter（如適用）
- [ ] 跨 Skill 引用使用完整路徑

---

**Last Updated**: 2026-04-01
**Version**: 1.2.0 - 新增規則 6：跨檔案引用格式規範（W4-010）
