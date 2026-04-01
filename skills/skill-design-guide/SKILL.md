---
name: skill-design-guide
description: "Use this skill when creating a new skill, updating an existing skill's YAML frontmatter, or reviewing skill quality. Provides the official Anthropic skill specification, frontmatter rules, description writing best practices, progressive disclosure architecture, and common pitfalls to avoid. Triggers include: creating skills, skill review, frontmatter validation, SKILL.md writing."
---

# Skill Design Guide

基於 Anthropic 官方平台文件和 Claude Code 團隊實踐經驗的 Skill 設計規範。

**官方資源**:
- Agent Skills Overview: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Skill Authoring Best Practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Claude Code Skills Docs: https://code.claude.com/docs/en/skills
- Skills Cookbook: https://platform.claude.com/cookbook/skills-notebooks-01-skills-introduction
- Engineering Blog: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Lessons from Building Claude Code: https://x.com/trq212/status/2027463795355095314

---

## 1. 核心設計原則

### Concise is Key（精簡至上）

**預設假設**：Claude 已經非常聰明。只加入 Claude 不知道的資訊。

對每條指令自問：「Claude 真的需要這個解釋嗎？」「這段文字值得它的 token 成本嗎？」

### Progressive Disclosure（漸進式揭露）

Skill 使用三層載入系統，最小化 token 使用：

| 層級 | 載入時機 | Token 成本 | 內容 |
|------|---------|-----------|------|
| **第一層：YAML frontmatter** | 常駐 system prompt | ~100 tokens/Skill | `name` + `description` |
| **第二層：SKILL.md body** | Claude 判斷相關時載入 | < 5k tokens | 完整指令和操作指引 |
| **第三層：references/ 連結檔** | Claude 按需讀取 | 無上限 | 詳細文件、腳本、範例 |

### Degrees of Freedom（自由度設計）

根據任務脆弱性和變異性，設定適當的指令精確度：

| 自由度 | 適用場景 | 方式 |
|--------|---------|------|
| **高** | 多種方法皆有效、依上下文決定 | 文字指引 |
| **中** | 有偏好模式但允許變化 | 虛擬碼或帶參數腳本 |
| **低** | 操作脆弱、一致性關鍵 | 具體腳本，禁止修改 |

### Composability（可組合性）

Claude 可同時載入多個 Skill。設計時不要假設自己是唯一的 Skill。

### Portability（可攜性）

Skill 可跨 Claude.ai、Claude Code、API 使用。但**自訂 Skill 不會跨平台同步**，需分別上傳。

| 平台 | 共享範圍 |
|------|---------|
| Claude.ai | 個人用戶 |
| Claude API | 整個 Workspace |
| Claude Code | 個人（`~/.claude/skills/`）或專案（`.claude/skills/`） |

---

## 2. 技術規範

### 檔案結構

```
your-skill-name/
├── SKILL.md           # 必要 - 主要指令檔
├── scripts/           # 選填 - 可執行腳本（Python, Bash 等）
├── references/        # 選填 - 按需載入的詳細文件
└── assets/            # 選填 - 範本、字型、圖示等
```

### 命名與檔案規則

| 規則 | 正確 | 錯誤 |
|------|------|------|
| SKILL.md 大小寫 | `SKILL.md` | `skill.md`, `SKILL.MD` |
| 資料夾 kebab-case | `notion-project-setup` | `Notion Project Setup` |
| 無底線 | `my-cool-skill` | `my_cool_skill` |
| 無大寫 | `my-cool-skill` | `MyCoolSkill` |
| 禁止 README.md | 文件放 SKILL.md 或 references/ | 不要在 Skill 資料夾內放 README.md |

**官方推薦：Gerund 命名**（動詞 + ing 形式）：

- `processing-pdfs`, `analyzing-spreadsheets`, `managing-databases`
- 也可接受名詞片語：`pdf-processing`, `spreadsheet-analysis`
- 避免模糊名稱：`helper`, `utils`, `tools`, `documents`

### 大小限制

- **SKILL.md body**: 建議低於 **500 行**。超過時拆分到 `references/`
- **description**: 最長 1,024 字元
- **compatibility**: 最長 500 字元

---

## 3. YAML Frontmatter 規格

### 3.1 Agent Skills 標準欄位

| 欄位 | 必填 | 說明 |
|------|------|------|
| `name` | **必填** | kebab-case，與資料夾名稱一致 |
| `description` | **必填** | 包含「做什麼」+「何時使用」，最長 1024 字元 |
| `license` | 選填 | 開源授權（MIT, Apache-2.0 等） |
| `compatibility` | 選填 | 環境需求（平台、系統套件、網路需求），最長 500 字元 |
| `allowed-tools` | 選填 | 限制 Skill 可使用的工具 |
| `metadata` | 選填 | 自訂 key-value pairs（author, version, mcp-server 等） |

### 3.2 Claude Code 擴展欄位

以下欄位為 Claude Code 特有，在 Claude.ai/API 上不一定支援：

| 欄位 | 說明 | 範例 |
|------|------|------|
| `argument-hint` | 自動補全時的參數提示 | `"[issue-number]"` |
| `disable-model-invocation` | 設 `true` 防止 Claude 自動觸發 | `true` |
| `user-invocable` | 設 `false` 隱藏在 `/` 選單 | `false` |
| `model` | 指定使用的模型 | `haiku` |
| `context` | 設 `fork` 在隔離子代理中執行 | `fork` |
| `agent` | `context: fork` 時的子代理類型 | `Explore` |
| `hooks` | Skill 生命週期 Hook | 見官方文件 |

### 3.3 allowed-tools 語法

```yaml
# Agent Skills 標準格式
allowed-tools: "Bash(python:*) Bash(npm:*) WebFetch"

# Claude Code 格式（也可接受）
allowed-tools: Bash(ticket *), Read, Grep, Glob

# 安全建議：使用命令模式限制，優於裸 Bash
allowed-tools: Bash(gh *)  # 只允許 gh 命令
```

### 3.4 metadata 範例

```yaml
metadata:
  author: Company Name
  version: 1.0.0
  mcp-server: server-name
  category: productivity
  tags: [project-management, automation]
```

### 3.5 安全限制

| 限制 | 原因 |
|------|------|
| 禁止 XML 角括號（`<` `>`） | frontmatter 出現在 system prompt，可能注入指令 |
| 禁止 name 含 "claude" 或 "anthropic" | 保留名稱 |
| 禁止 YAML 多行語法（`\|` `>`） | 後續行被誤判為屬性名稱 |
| 禁止自訂屬性（triggers, type, category） | 導致解析錯誤 |

---

## 4. Description 寫作規範（最重要）

description 是 Skill 觸發的**唯一機制**（除手動 `/name`）。寫好 description 是 Skill 成敗的關鍵。

### 強制：長度限制（最重要的規則）

> **description 超過 250 字會被截斷，導致自動觸發完全失敗。**

| 長度 | 評估 | 說明 |
|------|------|------|
| < 100 字 | 推薦 | Claude 能完整看到所有觸發詞 |
| 100-250 字 | 可接受 | 接近上限，注意關鍵詞位置 |
| > 250 字 | 禁止 | **被截斷，後半段觸發詞不可見** |

**關鍵詞位置策略**：最重要的觸發詞放在 description 最前面。截斷時後面的先丟失。

**實際案例**：`/parallel-evaluation` 的 description 超過 250 字，「多視角審核」「code review」等觸發詞在 Use for: 段落中被截斷，Claude 完全無法自動觸發，PM 被迫手動派發 Agent 繞過標準流程。

### 強制：第三人稱

description 注入 system prompt，人稱不一致會導致觸發問題。

- **正確**：`"Processes Excel files and generates reports"`
- **錯誤**：`"I can help you process Excel files"`
- **錯誤**：`"You can use this to process Excel files"`

### 結構公式

```
[做什麼] + [何時使用（觸發條件）] + [關鍵能力]
```

### Undertrigger 防護（官方建議）

Claude 傾向 **undertrigger**（有用時不觸發）。Description 應稍微積極，主動列出觸發情境，包括用戶沒有明說但明顯需要的場景。

**對比**：

```yaml
# 太被動（undertrigger 風險）
description: "Processes PDF files to extract text and tables."

# 積極版（防止 undertrigger）
description: "Processes PDF files to extract text and tables. Use whenever the user mentions PDFs, wants to read a document, asks to summarize a file, or uploads any document — even if they don't explicitly say 'PDF'."
```

**加強觸發的技巧**：
- 列出用戶可能說的**同義詞和近似詞**（e.g., "document", "file", "report" 不只是 "PDF"）
- 加上 "even if they don't explicitly ask for..." 涵蓋隱性需求
- 加上 "Make sure to use this skill whenever..." 作為明確的觸發指引

### 正確範例

```yaml
# 具體且可操作
description: "Analyzes Figma design files and generates developer handoff documentation. Use when user uploads .fig files, asks for 'design specs', 'component documentation', or 'design-to-code handoff'."

# 包含觸發短語
description: "Manages Linear project workflows including sprint planning, task creation, and status tracking. Use when user mentions 'sprint', 'Linear tasks', 'project planning', or asks to 'create tickets'."

# 明確的價值主張
description: "End-to-end customer onboarding workflow for PayFlow. Handles account creation, payment setup, and subscription management. Use when user says 'onboard new customer', 'set up subscription', or 'create PayFlow account'."

# 包含負面觸發（防止過度觸發）
description: "Advanced data analysis for CSV files. Use for statistical modeling, regression, clustering. Do NOT use for simple data exploration (use data-viz skill instead)."
```

### 錯誤範例

```yaml
# 太籠統
description: "Helps with projects."

# 缺少觸發條件
description: "Creates sophisticated multi-page documentation systems."

# 太技術，無使用者觸發
description: "Implements the Project entity model with hierarchical relationships."

# 描述內部架構而非使用場景
description: "統一 Ticket 系統 v1.0 - 整合 create/track/handoff/resume/migrate/generate 六大功能。"
```

### 專案內格式（也可接受）

```yaml
# 中文 + "Use for:" 列舉式
description: "認知負擔評估工具。Use for: (1) 任務複雜度評估, (2) 代理人升級判斷, (3) 任務拆分建議"
```

### 觸發問題診斷

**Skill 未觸發**：description 太籠統或缺少使用者常用詞彙。加入更多關鍵字和觸發短語。

**Skill 過度觸發**：加入負面觸發（"Do NOT use for..."）或限縮描述範圍。

**驗證方法**：問 Claude「When would you use the [skill name] skill?」。Claude 會引用 description，根據回答調整。

---

## 5. 指令撰寫最佳實踐

### 建議的 SKILL.md 結構

```markdown
---
name: your-skill
description: [...]
---

# Your Skill Name

## Instructions

### Step 1: [First Major Step]
Clear explanation of what happens.

### Step 2: [Next Step]
...

## Examples

### Example 1: [common scenario]
User says: "..."
Actions:
1. ...
2. ...
Result: ...

## Troubleshooting

### Error: [Common error message]
**Cause:** [Why it happens]
**Solution:** [How to fix]
```

### 指令品質原則

**具體且可操作**：

```markdown
# 好
Run `python scripts/validate.py --input {filename}` to check data format.
If validation fails, common issues include:
- Missing required fields (add them to the CSV)
- Invalid date formats (use YYYY-MM-DD)

# 壞
Validate the data before proceeding.
```

**包含錯誤處理**：

```markdown
## Common Issues

### MCP Connection Failed
If you see "Connection refused":
1. Verify MCP server is running
2. Confirm API key is valid
3. Try reconnecting
```

**清楚引用 references/ 中的資源**：

```markdown
Before writing queries, consult `references/api-patterns.md` for:
- Rate limiting guidance
- Pagination patterns
- Error codes and handling
```

**引用只能一層深**（官方強制）：所有 reference 檔案從 SKILL.md 直接連結，禁止 A→B→C 巢狀引用。

**長 reference 檔（100+ 行）加 TOC**：確保 Claude preview 時能看到完整範圍。

**重要指令放最上面**：使用 `## Important` 或 `## Critical` 標題。關鍵指令需要時可重複。

**避免時間敏感資訊**：不要寫「2025 年 8 月前用舊 API」。用 "old patterns" 區段處理。

**一致性術語**：選定一個詞彙，全 Skill 統一使用（不要混用 "endpoint"/"URL"/"route"）。

**MCP 工具用完整限定名稱**：`ServerName:tool_name` 格式，避免 "tool not found"。

**避免模糊語言**：

```markdown
# 壞
Make sure to validate things properly

# 好
CRITICAL: Before calling create_project, verify:
- Project name is non-empty
- At least one team member assigned
- Start date is not in the past
```

---

## 6. Claude Code 特有功能

### 字串替換

Skill 內容支援動態變數替換：

| 變數 | 說明 | 範例 |
|------|------|------|
| `$ARGUMENTS` | 所有傳入參數 | `/fix-issue 123` -> `$ARGUMENTS` = `123` |
| `$ARGUMENTS[N]` | 第 N 個參數（0-based） | `$ARGUMENTS[0]` = 第一個參數 |
| `$N` | `$ARGUMENTS[N]` 的簡寫 | `$0` = 第一個參數 |

若 SKILL.md 內容中沒有 `$ARGUMENTS`，參數會自動附加為 `ARGUMENTS: <value>`。

### 動態 Context 注入

`` !`command` `` 語法在 Skill 內容送出前執行 shell 命令：

```markdown
## Pull request context
- PR diff: !`gh pr diff`
- Changed files: !`gh pr diff --name-only`
```

這是**預處理**，Claude 只看到展開後的結果。

### 觸發控制矩陣

| Frontmatter 設定 | 用戶可呼叫 | Claude 可呼叫 | 何時載入 |
|------------------|-----------|--------------|---------|
| （預設） | Yes | Yes | description 常駐 context |
| `disable-model-invocation: true` | Yes | No | 用戶呼叫時才載入 |
| `user-invocable: false` | No | Yes | description 常駐 context |

### Description 預算

- **預算**: context window 的 2%（fallback: 16,000 字元）
- **超出時**: 部分 Skill 會被排除
- **單一 description 上限**: 250 字（超過被截斷，觸發詞丟失）
- **建議**: description 保持 1-3 句（< 100 字），focus on 觸發條件

---

## 7. YAML 格式陷阱

### 禁止：多行語法

```yaml
# 錯誤：| 和 > block scalar 會導致解析失敗
description: |
  第一行會被解析為 description
  第二行會被誤判為獨立屬性名稱

# 正確：雙引號單行字串
description: "第一行內容。第二行內容。第三行內容。"
```

### 禁止：缺少分隔符

```yaml
# 錯誤：缺少 --- 分隔符
name: my-skill
description: Does things

# 正確
---
name: my-skill
description: Does things
---
```

### 禁止：未閉合引號

```yaml
# 錯誤
description: "Does things

# 正確
description: "Does things"
```

---

## 8. 快速檢查清單

### 開始前

- [ ] 已確定 2-3 個具體使用案例
- [ ] 已識別需要的工具（內建或 MCP）
- [ ] 已規劃資料夾結構

### 開發中

- [ ] 資料夾使用 kebab-case 命名（推薦 gerund 形式）
- [ ] `SKILL.md` 檔名完全正確（大小寫敏感）
- [ ] YAML frontmatter 有 `---` 分隔符
- [ ] `name` 欄位：kebab-case，無空格，無大寫
- [ ] `description` 使用第三人稱，包含「做什麼」和「何時使用」
- [ ] 無 XML 角括號（`<` `>`）
- [ ] 無自訂屬性（triggers, type, category 等）
- [ ] 無 YAML 多行語法（`|` `>`）
- [ ] 指令具體可操作
- [ ] 包含錯誤處理
- [ ] 包含範例
- [ ] references/ 連結只有一層深
- [ ] 長 reference 檔（100+ 行）有 TOC
- [ ] 資料夾內無 README.md
- [ ] SKILL.md body 低於 500 行
- [ ] 無時間敏感資訊
- [ ] 術語一致

### 上線後

- [ ] 測試觸發：相關查詢能觸發
- [ ] 測試觸發：改述查詢也能觸發
- [ ] 測試觸發：無關主題不會觸發
- [ ] 功能測試通過
- [ ] 多模型測試（Haiku/Sonnet/Opus 行為可能不同）
- [ ] 收集回饋並迭代

---

## 9. 常見 Skill 類型

| 類型 | 用途 | 觸發方式 | 範例 |
|------|------|---------|------|
| **Document & Asset Creation** | 建立一致、高品質的輸出 | Claude 自動 | frontend-design, docx, pptx |
| **Workflow Automation** | 多步驟流程自動化 | 用戶觸發 | skill-creator, deploy |
| **MCP Enhancement** | 增強 MCP 工具的工作流指引 | Claude 自動 | sentry-code-review |
| **Reference** | 知識/規範/風格指南 | Claude 自動 | coding-standards, api-conventions |
| **Task** | 步驟式操作指令 | 用戶手動 `/name` | commit, fix-issue |

**設計建議**：
- Reference 型 Skill 保持預設（Claude 自動載入）
- Task 型 Skill 設 `disable-model-invocation: true`，防止 Claude 擅自執行副作用操作

---

## 10. 安全考量

**強烈建議只使用來自信任來源的 Skill**（自己建立或 Anthropic 提供）。

| 風險 | 說明 |
|------|------|
| 工具誤用 | 惡意 Skill 可指示 Claude 執行非預期的 bash/檔案操作 |
| 資料外洩 | 有敏感資料存取權的 Skill 可能洩漏到外部系統 |
| 外部來源風險 | 從 URL 取得內容的 Skill 可能被注入惡意指令 |

**審查清單**：檢查所有 SKILL.md、腳本、資源檔案。留意異常的網路呼叫、檔案存取模式。

---

## 11. 延伸閱讀

- 詳細的 Patterns、Troubleshooting 和 Testing 指引：`references/patterns-and-troubleshooting.md`
- 工具設計哲學和演進洞見：`references/seeing-like-an-agent.md`

---

**Last Updated**: 2026-03-08
**Version**: 1.0.0
**Source**: Anthropic Official Platform Docs + "Lessons from Building Claude Code" + anthropics/skills skill-creator + Project Experience
