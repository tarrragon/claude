# 代理人前置載入規範 (Agent Preload Standards)

本文件定義**所有代理人**在開始執行任務前**必須**遵守的核心規則。

> **重要**：本文件透過 `@` 引用機制被載入到每個代理人的上下文中。

---

## 強制規則

### 1. 語言規範（最高優先）

**所有輸出必須使用繁體中文 (zh-TW)**

#### 禁用詞彙對照表

| 禁用詞彙 | 正確用語 |
|---------|---------|
| 文檔 | 文件 |
| 數據 | 資料 |
| 默認 | 預設 |
| 代碼 | 程式碼 |
| 視頻 | 影片 |
| 軟件 | 軟體 |
| 硬件 | 硬體 |
| 信息 | 資訊 |
| 智能 | Hook 系統、規則比對 |

#### 技術術語保留英文

程式碼識別符、技術專有名詞（Flutter, Dart, TDD 等）、指令（`/ticket`）保留英文。

> 完整規範：@.claude/rules/core/language-constraints.md

---

### 2. Ticket 操作規範

**讀取 Ticket 必須使用 `ticket` 指令，禁止直接使用 Read 工具**

#### 正確方式

```bash
# 查詢特定 Ticket
ticket track query 0.31.0-W8-003

# 查詢 Ticket 列表
ticket track list

# 查詢摘要
ticket track summary
```

#### 禁止方式

```bash
# 禁止直接讀取 Ticket 檔案
Read(docs/work-logs/v0.31.0/tickets/0.31.0-W8-003.md)  # 禁止
```

#### 原因

1. `ticket` 指令會自動解析 frontmatter 和結構
2. 確保 Ticket 追蹤系統的一致性
3. 指令會驗證 Ticket 狀態和格式

> 完整規範：@.claude/skills/ticket/SKILL.md

---

### 3. 文件格式規範

- 所有交接文件禁止使用 emoji
- 使用純文字狀態標記（`[x]` / `[ ]`）
- 優先級使用「P0/P1/P2」或「高/中/低」

> 完整規範：@.claude/rules/core/document-format-rules.md

---

### 4. 5W1H 回應格式

代理人的報告和輸出應遵循結構化格式，包含：
- Who（執行者）
- What（任務內容）
- When（觸發時機）
- Where（執行位置）
- Why（執行理由）
- How（實作方式）

---

## 執行檢查清單

代理人在開始任務前，自我確認：

- [ ] 所有輸出使用繁體中文
- [ ] 無禁用詞彙（文檔→文件、數據→資料...）
- [ ] 讀取 Ticket 使用 `ticket track query`
- [ ] 文件無 emoji
- [ ] 報告結構清晰（5W1H）

---

## 違規處理

| 違規類型 | 處理方式 |
|---------|---------|
| 使用禁用詞彙 | 立即修正輸出 |
| 直接 Read Ticket 檔案 | 改用 `ticket` 指令重新讀取 |
| 使用簡體中文 | 重新輸出繁體中文版本 |

---

**Last Updated**: 2026-02-05
**Version**: 1.0.0
**Purpose**: 確保所有代理人遵守核心規則
