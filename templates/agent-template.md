# 代理人範本 (Agent Template)

本文件為建立新代理人的標準範本，確保所有代理人具有一致的結構和完整的資訊。

---

## 範本使用說明

1. 複製「完整範本」部分到新檔案
2. 將 `{placeholder}` 替換為實際內容
3. 根據代理人類型選擇適當的章節
4. 刪除不適用的章節
5. 確保通過「範本檢查清單」

---

## 完整範本

```markdown
---
name: {agent-name-kebab-case}
description: {一句話描述核心職責和觸發條件，50-100 字}
tools: {工具列表，逗號分隔}
color: {顏色名稱}
model: {haiku|sonnet|opus}
---

# {代理人中文名稱} ({Agent English Name})

You are a {role description in English}. Your core mission is {mission statement}.

**定位**：{一句話中文定位}

---

## 觸發條件

{代理人名稱} 在以下情況下**應該被觸發**：

| 觸發情境 | 說明 | 強制性 |
|---------|------|--------|
| {情境1} | {說明} | 強制/建議 |
| {情境2} | {說明} | 強制/建議 |
| {情境3} | {說明} | 強制/建議 |

---

## 核心職責

### 1. {職責1名稱}

**目標**：{目標描述}

**執行步驟**：
1. {步驟1}
2. {步驟2}
3. {步驟3}

### 2. {職責2名稱}

**目標**：{目標描述}

**執行步驟**：
1. {步驟1}
2. {步驟2}
3. {步驟3}

### 3. {職責3名稱}（如適用）

**目標**：{目標描述}

---

## 禁止行為

### 絕對禁止

1. **禁止 {行為1}**：{說明}
2. **禁止 {行為2}**：{說明}
3. **禁止 {行為3}**：{說明}

---

## 輸出格式

### {報告/輸出名稱} 模板

```markdown
# {報告標題}

## 摘要
- **{欄位1}**: [{值}]
- **{欄位2}**: [{值}]

## {章節1}
[內容]

## {章節2}
[內容]

## 建議
[建議內容]
```

---

## 與其他代理人的邊界

| 代理人 | {本代理人} 負責 | 其他代理人負責 |
|--------|----------------|---------------|
| {代理人1} | {本代理人職責} | {其他代理人職責} |
| {代理人2} | {本代理人職責} | {其他代理人職責} |
| {代理人3} | {本代理人職責} | {其他代理人職責} |

### 明確邊界

| 負責 | 不負責 |
|------|-------|
| {職責1} | {排除1} |
| {職責2} | {排除2} |
| {職責3} | {排除3} |

---

## 升級機制

### 升級觸發條件

- {條件1}
- {條件2}
- {條件3}

### 升級流程

1. 記錄當前進度到輸出文件
2. 標記為「需要升級」
3. 向 rosemary-project-manager 提供：
   - 已完成的工作
   - 遇到的問題
   - 需要的協助

---

## 工作流程整合

### 在整體流程中的位置

```
{前一步驟}
    |
    v
[{本代理人}] <-- 你的位置
    |
    +-- {結果1} --> {下一步1}
    +-- {結果2} --> {下一步2}
```

### 與相關代理人的協作

{描述與其他代理人的協作方式}

---

## 成功指標

### 品質指標
- {指標1} > {目標值}
- {指標2} > {目標值}

### 流程遵循
- {遵循項目1}
- {遵循項目2}

---

**Last Updated**: {日期}
**Version**: 1.0.0
**Specialization**: {專業領域}
```

---

## 必要章節說明

### Frontmatter（必要）

| 欄位 | 說明 | 範例 |
|------|------|------|
| name | 代理人識別名稱（kebab-case） | `incident-responder` |
| description | 核心職責描述（50-100 字） | 見下方說明 |
| tools | 允許使用的工具 | `Read, Grep, Glob, LS, Bash` |
| color | 代理人顏色標記 | `orange`, `gold`, `green` |
| model | 使用的模型 | `haiku`, `sonnet`, `opus` |

### Description 撰寫指南

**格式**：`{角色名稱}。{核心職責}。{觸發條件或特殊說明}。`

**範例**：
- `事件回應專家。測試失敗或問題發生時的第一線評估者，分析錯誤狀況和上下文，判斷是設計問題還是實作問題，開錯誤處理 Ticket，避免衝動決策。Skip-gate 核心解決方案。`
- `TDD 前置審查專家。在 TDD 開始前審查系統一致性、檢視/撰寫需求文件、防止重複造輪子、確保 ticket 與大系統設計一致。負責系統級審查，不負責單一功能設計。`

### 觸發條件（必要）

明確列出代理人的觸發條件，包含：
- 強制觸發情境
- 建議觸發情境
- 觸發關鍵字（如適用）

### 核心職責（必要）

描述代理人的主要職責，每個職責包含：
- 目標說明
- 執行步驟或流程
- 產出物（如適用）

### 禁止行為（必要）

明確列出代理人不應該做的事情，防止越權。

### 輸出格式（建議）

如果代理人需要產出特定格式的報告或文件，提供模板。

### 與其他代理人的邊界（必要）

明確定義職責邊界，避免職責重疊或遺漏。

### 升級機制（必要）

定義何時需要升級到 rosemary-project-manager，以及升級流程。

---

## 範本檢查清單

建立新代理人時，確保通過以下檢查：

### Frontmatter 檢查
- [ ] name 使用 kebab-case
- [ ] description 在 50-100 字之間
- [ ] tools 列表完整
- [ ] model 選擇適當（haiku/sonnet/opus）

### 內容檢查
- [ ] 有英文角色定義
- [ ] 有中文定位說明
- [ ] 觸發條件表格完整
- [ ] 核心職責有明確步驟
- [ ] 禁止行為有列出
- [ ] 與其他代理人邊界明確

### 流程檢查
- [ ] 升級機制有定義
- [ ] 工作流程位置清楚
- [ ] 成功指標可量化

### 格式檢查
- [ ] 使用繁體中文
- [ ] 無 emoji
- [ ] 表格格式正確
- [ ] 程式碼區塊使用正確語法標記

---

## 代理人類型參考

### 系統級代理人
- incident-responder（事件回應）
- saffron-system-analyst（系統分析）
- star-anise-system-designer（系統設計）
- sumac-system-engineer（系統工程）
- sassafras-data-administrator（資料管理）

### TDD 階段代理人
- lavender-interface-designer（Phase 1）
- sage-test-architect（Phase 2）
- pepper-test-implementer（Phase 3a）
- parsley-flutter-developer（Phase 3b）
- cinnamon-refactor-owl（Phase 4）

### 專業任務代理人
- clove-security-reviewer（安全審查）
- basil-hook-architect（Hook 開發）
- thyme-documentation-integrator（文件整合）
- mint-format-specialist（格式化）
- ginger-performance-tuner（效能優化）

---

## 命名規範

### 代理人命名
- 使用香料/植物名稱 + 職責描述
- 範例：`saffron-system-analyst`, `basil-hook-architect`

### 檔案命名
- 使用與 name 相同的 kebab-case
- 範例：`saffron-system-analyst.md`

### 觸發條件規則檔案
- 位置：`.claude/rules/dispatch-rules/`
- 命名：`{agent-name}.md`
- 範例：`system-analyst.md`

---

## 關聯文件

建立新代理人時，**必須**同步建立以下文件：

| 文件 | 說明 | 位置 |
|------|------|------|
| Task 工具版本 | 完整的代理人定義（詳細指令） | `.claude/agents/` |
| 派發規則版本 | 精簡的派發規則摘要 | `.claude/rules/dispatch-rules/` |
| 職責矩陣 | 更新職責邊界 | `.claude/rules/dispatch-rules/overview.md` |
| CLAUDE.md | 更新代理人列表（如適用） | `CLAUDE.md` |
| 決策流程 | 更新派發規則（如適用） | `.claude/rules/core/decision-tree.md` |

### 雙目錄建立檢查

- [ ] `.claude/agents/{name}.md` 已建立（Task 工具版本）
- [ ] `.claude/rules/dispatch-rules/{name}.md` 已建立（派發規則版本）
- [ ] `.claude/rules/dispatch-rules/overview.md` 已更新

---

**Last Updated**: 2026-01-28
**Version**: 1.1.0
