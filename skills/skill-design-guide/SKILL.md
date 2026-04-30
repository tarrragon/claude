---
name: skill-design-guide
description: "Use this skill when creating a new skill, updating an existing skill's YAML frontmatter, or reviewing skill quality. Provides the official Anthropic skill specification, frontmatter rules, description writing best practices, progressive disclosure architecture, and common pitfalls to avoid. Triggers include: creating skills, skill review, frontmatter validation, SKILL.md writing."
---

# Skill Design Guide

依據 Anthropic 官方 `skill-creator` 與 Claude Code 平台規範整合的 Skill 設計指引。本檔聚焦「為什麼這樣設計」與「具體該怎麼做」，不重述官方文件全文。

**官方來源**：

- Skill spec: <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>
- Best practices: <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>
- Claude Code skills: <https://code.claude.com/docs/en/skills>
- 官方 `skill-creator`: 已安裝於本環境的 plugin marketplace

---

## 1. 核心心法

### 1.1 Concise is Key — context 是公共資源

**預設假設**：Claude 已經夠聰明。每段文字必須通過兩問才能保留。

| 自問 | 通過標準 |
|------|---------|
| Claude 真的不知道這個嗎？ | 通用程式知識 / 框架慣例 → 移除；專案特有 / 反直覺 → 保留 |
| 這段文字值得它的 token 成本嗎？ | 表格 / 範例優於散文，散文優於不存在 |

**Why**：description 與 SKILL.md body 都會被載入 context；冗長 skill 排擠其他 skill 的 description budget，讓自動觸發失敗。

### 1.2 Progressive Disclosure — 三層載入

| 層 | 載入時機 | 預算 | 寫什麼 |
|----|---------|------|-------|
| 1. frontmatter（name + description） | 常駐 system prompt | ~100 tokens / skill | 何時觸發 + 做什麼 |
| 2. SKILL.md body | 觸發後載入 | < 5k tokens（< 500 行） | 核心工作流 + 路由 |
| 3. references/ + scripts/ + assets/ | Claude 按需 read / exec | 無上限 | 細節、範例、模板、可執行腳本 |

**Action**：超過 500 行就外移到 references/；外移時必在 SKILL.md 留路由訊號（何時讀該檔）。

### 1.3 Degrees of Freedom — 自由度匹配脆弱性

| 自由度 | 任務特徵 | 表達方式 | 範例 |
|--------|---------|---------|------|
| 高 | 多種解法皆可、依情境決定 | 文字指引 + 啟發式 | 「分析使用者需求並建議方向」 |
| 中 | 有偏好模式、容許變化 | 虛擬碼 / 帶參數腳本 | 「依照範本但可調整章節順序」 |
| 低 | 操作脆弱、一致性關鍵 | 具體腳本、固定步驟 | 「執行 `scripts/validate.py`，不可改寫」 |

**判準**：「Claude 走錯一步會壞掉嗎？」會 → 低自由度；不會 → 高自由度。

---

## 2. Anatomy — Skill 該長什麼樣

### 2.1 檔案結構

```
your-skill-name/
├── SKILL.md              # 必要：YAML frontmatter + 主指令
├── scripts/              # 選填：可執行程式碼（可不載入 context 直接跑）
├── references/           # 選填：按需載入到 context 的文件
└── assets/               # 選填：產出時使用的範本 / 圖示 / 字型
```

### 2.2 三類 bundled resource 的分工

| 類型 | 載入方式 | 何時用 | 範例 |
|------|---------|-------|------|
| `scripts/` | 可不讀直接執行（subprocess） | 同樣程式碼會被反覆寫；需要決定性結果 | `validate.py`、`init_skill.py`、`rotate_pdf.py` |
| `references/` | Claude `Read` 載入 context | 工作時需查的文件 / schema / 詳細範例 | `api-schema.md`、`patterns.md` |
| `assets/` | 不載入 context，被複製到輸出 | 產出物的素材 | `logo.png`、`template.pptx`、樣板專案目錄 |

**Why 區分這三類**：scripts 的價值是「跳過 context」，references 的價值是「按需載入」，assets 的價值是「不污染 context」。誤放會抵消設計。

---

## 3. 嚴禁清單 — 什麼不該放進 Skill

> **核心原則**：Skill 只放 AI agent 執行任務需要的東西，不放給人看的後設資訊。

### 3.1 禁止的檔案

| 禁止檔案 | 為何禁止 | 替代方案 |
|---------|---------|---------|
| `README.md`（任何層級，含 `references/` 子目錄） | 給人看的入口；AI 經 SKILL.md 進入，README 只是冗餘 | 資料夾用途透過檔名自說明，或在 SKILL.md「參考文件」段落索引 |
| `INSTALLATION_GUIDE.md` | 安裝是平台職責，非 skill 工作 | 放專案根目錄文件 |
| `QUICK_REFERENCE.md` | 與 SKILL.md 必有重複 | 直接寫進 SKILL.md 或 reference 檔 |
| `CHANGELOG.md` | 給人看的版本紀錄 | 放專案根目錄或 git log |
| 設計過程紀錄 / 測試報告 | 開發 artifact，非 runtime 需要 | 放專案 worklog 系統 |

**Why**：每多一個檔案就增加 Claude 讀檔判斷成本；給人看的文件對 AI 是雜訊。

### 3.2 禁止的內容

| 禁止內容 | 為何禁止 |
|---------|---------|
| SKILL.md 內「When to Use This Skill」段落 | 觸發判斷靠 description（已在 system prompt），body 寫一次無效 |
| 時間敏感資訊（「2025 年 8 月前用舊 API」） | 改成「old patterns」段落，不寫具體日期 |
| 同一資訊同時放 SKILL.md 與 reference | 重複會稀釋 grep 命中率；資訊只放一處 |

---

## 4. YAML Frontmatter

### 4.1 標準欄位（Anthropic Agent Skills）

| 欄位 | 必填 | 說明 |
|------|------|------|
| `name` | 是 | kebab-case，與資料夾名稱一致 |
| `description` | 是 | 做什麼 + 何時用，最長 1024 字元（但實務 < 250 字，見 §5） |
| `license` | 否 | 開源授權字串 |
| `compatibility` | 否 | 環境需求，最長 500 字元 |
| `allowed-tools` | 否 | 限制 skill 可用工具 |
| `metadata` | 否 | 自訂 key-value（author、version、tags 等） |

### 4.2 Claude Code 擴展欄位

> 僅在 Claude Code 可用，跨平台（Claude.ai / API）會被忽略或報錯。

| 欄位 | 用途 | 範例 |
|------|------|------|
| `argument-hint` | `/<name>` 自動補全提示 | `"[issue-number]"` |
| `disable-model-invocation` | 防止 Claude 自動觸發 | `true` |
| `user-invocable` | 從 `/` 選單隱藏 | `false` |
| `model` | 指定模型 | `haiku` |
| `context` | 隔離子代理執行 | `fork` |
| `agent` | `context: fork` 時的代理類型 | `Explore` |
| `hooks` | Skill 生命週期 hook | 見官方文件 |

### 4.3 安全與格式禁令

| 禁止 | 原因 | 修正 |
|------|------|------|
| 角括號 `< >` | frontmatter 進 system prompt，可能被解讀為指令 | 用「lt」「gt」或全形字 |
| `name` 含 "claude" / "anthropic" | 保留名稱 | 換名 |
| YAML 多行語法（`\|` `>`） | 後續行被誤判為新屬性 | 改單行雙引號字串 |
| 自訂屬性（`triggers` / `type` / `category` 等） | 解析器拒絕 | 全部塞進 `metadata` |
| 缺 `---` 分隔符 | 整段被當 markdown body | 補分隔符 |
| 未閉合引號 | 解析失敗整支 skill 不可用 | 補引號 |

---

## 5. Description 寫作（最重要的一節）

description 是 Claude 自動觸發 skill 的**唯一機制**。寫不好等於 skill 不存在。

### 5.1 強制：長度 < 250 字（最重要規則）

| 長度 | 評估 | 後果 |
|------|------|------|
| < 100 字 | 推薦 | 觸發詞完整可見 |
| 100-250 字 | 可接受 | 接近上限，關鍵詞放前面 |
| > 250 字 | 禁止 | **被截斷，後段觸發詞丟失，自動觸發失敗** |

**Why**：Claude Code 對單一 description 有截斷行為（context budget 約 2% / 16k 字元）。實證案例：`/parallel-evaluation` 因 description 過長，「多視角審核」「code review」等詞在 Use for: 段落被截斷，無法自動觸發。

**Action**：把最重要的觸發詞放最前面；截斷時前段不會丟。

### 5.2 強制：第三人稱

description 進 system prompt，「I」「you」會破壞語境。

| 正確 | 錯誤 |
|------|------|
| `Processes Excel files and generates reports` | `I can help you process Excel files` |
| `Use when user uploads .xlsx files` | `You can use this to process Excel files` |

### 5.3 結構公式

```
[做什麼] + [何時使用 / 觸發詞清單] + [可選：負面觸發]
```

### 5.4 防 undertrigger（官方建議）

Claude 預設保守、傾向不觸發。description 應**主動列同義詞與隱性需求**。

| 對比 | 範例 |
|------|------|
| 太被動 | `Processes PDF files to extract text and tables.` |
| 積極版 | `Processes PDF files to extract text and tables. Use whenever the user mentions PDFs, documents, files, or asks to summarize a report — even if they don't explicitly say 'PDF'.` |

**技巧**：

- 列同義詞 / 近似詞（「document」「file」「report」不只「PDF」）
- 加 "even if they don't explicitly ask..." 涵蓋隱性需求
- 加 "Make sure to use this skill whenever..." 作明確指引

### 5.5 防 overtrigger — 負面觸發

```yaml
description: "Advanced statistical modeling for CSV files. Use for regression, clustering, hypothesis testing. Do NOT use for simple data exploration (use data-viz skill instead)."
```

### 5.6 範例對照

| 評估 | description |
|------|------------|
| 好（具體 + 觸發詞 + 同義詞） | `Analyzes Figma design files and generates developer handoff docs. Use when user uploads .fig files, asks for 'design specs', 'component documentation', or 'design-to-code handoff'.` |
| 好（負面觸發） | `Statistical modeling for CSV. Use for regression / clustering. Do NOT use for visualization (use data-viz skill).` |
| 壞（太籠統） | `Helps with projects.` |
| 壞（缺觸發） | `Creates sophisticated multi-page documentation systems.` |
| 壞（描述內部架構） | `統一 Ticket 系統 v1.0 — 整合 create / track / handoff / resume / migrate / generate 六大功能。` |

### 5.7 觸發品質診斷

| 症狀 | 修正 |
|------|------|
| Skill 該觸發卻沒觸發 | description 太籠統 → 加同義詞、加 "whenever..." |
| Skill 不該觸發卻觸發 | 加負面觸發 "Do NOT use for X" |
| 不確定 | 直接問 Claude「When would you use the [skill name] skill?」，看回答對不對 |

---

## 6. Body 寫作

### 6.1 SKILL.md 推薦骨架

```markdown
---
name: your-skill
description: [...]
---

# Your Skill Name

[一句話說明目的，不重述 description]

## Core Concepts / Workflow（必要）

[關鍵概念表 或 步驟清單。少用 prose、多用表格 / 列表]

## When to Read Which Reference（必要）

[路由表：什麼情境讀哪份 reference]

## Examples（建議）

[輸入 → 動作 → 輸出 的具體案例 1-3 則]

## Troubleshooting（建議）

[常見錯誤 → 原因 → 解法]
```

### 6.2 內容品質規則

| 規則 | 反例 → 正例 |
|------|------------|
| 具體可操作 | `Validate the data before proceeding.` → `Run python scripts/validate.py --input {filename}. If exit code != 0, see references/errors.md` |
| 包含錯誤處理 | （只寫成功路徑） → 額外加 `## Common Issues` 段 |
| 重要指令前置 | 散落在中段 → 用 `## Important` / `## Critical` 標題 + 必要時重複 |
| 一致術語 | 混用「endpoint / URL / route」 → 全 skill 統一一個詞 |
| MCP 工具完整名稱 | `tool_name` → `ServerName:tool_name` |
| 避免模糊語言 | `Make sure to validate things properly` → `CRITICAL: Before X, verify A, B, C` |

### 6.3 references/ 引用規則

| 規則 | 說明 |
|------|------|
| 一層深 | 所有 reference 從 SKILL.md 直接連結，禁止 A → B → C 巢狀 |
| 路由訊號 | SKILL.md 必說明「什麼情境讀此檔」，否則 reference 形同孤兒 |
| 100+ 行加 TOC | 讓 Claude preview 時看到完整範圍 |
| 不重複 | 內容只放 SKILL.md 或 reference 之一，不兩處皆有 |

---

## 7. 命名規則

### 7.1 強制

| 規則 | 正確 | 錯誤 |
|------|------|------|
| `SKILL.md` 大小寫 | `SKILL.md` | `skill.md`、`SKILL.MD` |
| 資料夾 kebab-case | `notion-project-setup` | `Notion Project Setup`、`my_skill` |
| 無底線 | `my-cool-skill` | `my_cool_skill` |
| 無大寫 | `my-cool-skill` | `MyCoolSkill` |

### 7.2 推薦：Gerund 命名

| 類型 | 範例 | 評估 |
|------|------|------|
| Gerund（動詞 + ing，官方推薦） | `processing-pdfs`、`analyzing-spreadsheets`、`managing-databases` | 最佳，意圖明確 |
| 名詞片語 | `pdf-processing`、`spreadsheet-analysis` | 可接受 |
| 模糊名稱 | `helper`、`utils`、`tools`、`documents` | 避免，無法判斷觸發場景 |

---

## 8. Skill 建立流程（官方 6 步）

> 來源：Anthropic `skill-creator` 官方流程。新建或大改 skill 時依序執行，已知不適用才跳過。

### Step 1：用具體案例釐清 skill

列出 2-3 個使用者會說的話，作為 skill 觸發的代表情境。問題範例：

- 「使用者會用什麼詞描述這個需求？」
- 「同一需求有幾種說法？」
- 「哪些情境**不該**觸發？」

**Why**：description 設計、reference 拆分、scripts 規劃都從這些案例反推。

### Step 2：規劃 bundled resources

對每個案例分析：

| 觀察 | 行動 |
|------|------|
| 同樣程式碼會被反覆寫 | 建 `scripts/X.py` |
| 同樣文件 / schema 會被反覆查 | 建 `references/X.md` |
| 同樣模板 / 素材會被輸出 | 建 `assets/X` |

### Step 3：初始化 skill

官方 `skill-creator` 提供 `scripts/init_skill.py`。手動建立時依 §2.1 結構。

### Step 4：撰寫內容

| 順序 | 動作 |
|------|------|
| 1 | 先寫 bundled resources（scripts / references / assets） |
| 2 | 寫 SKILL.md frontmatter（依 §4 規範） |
| 3 | 寫 SKILL.md body（依 §6 骨架） |
| 4 | 測試 scripts 實際可跑 |

**寫作風格**：用祈使句 / 不定式（imperative / infinitive），不用「我」「你」。

### Step 5：打包

官方 `skill-creator` 提供 `scripts/package_skill.py`，自動驗證 frontmatter + 命名 + 結構，產出 `.skill` 檔。

### Step 6：迭代

| 訊號 | 動作 |
|------|------|
| Skill 該觸發沒觸發 | 修 description（§5.4） |
| Skill 觸發但用錯方向 | 修 SKILL.md body 路由 |
| Skill 反覆需要相同細節 | 拆出 reference 或寫腳本 |

---

## 9. Claude Code 特有功能

### 9.1 字串替換

| 變數 | 說明 | 範例 |
|------|------|------|
| `$ARGUMENTS` | 全部傳入參數 | `/fix-issue 123` → `$ARGUMENTS = "123"` |
| `$ARGUMENTS[N]` | 第 N 個（0-based） | `$ARGUMENTS[0]` 第一個 |
| `$N` | `$ARGUMENTS[N]` 簡寫 | `$0` 第一個 |

若 SKILL.md 沒寫 `$ARGUMENTS`，參數自動附加為 `ARGUMENTS: <value>`。

### 9.2 動態 context 注入（pre-process）

`` !`command` `` 在 skill 載入前執行 shell，Claude 只看到結果：

```markdown
## Pull request context

- PR diff: !`gh pr diff`
- Changed files: !`gh pr diff --name-only`
```

### 9.3 觸發控制矩陣

| frontmatter 設定 | 用戶可呼叫 | Claude 可呼叫 | 載入時機 |
|----|----|----|----|
| 預設 | 是 | 是 | description 常駐 context |
| `disable-model-invocation: true` | 是 | 否 | 用戶呼叫時才載入 |
| `user-invocable: false` | 否 | 是 | description 常駐 context |

**設計建議**：

- Reference 型（知識 / 規範） → 預設（自動觸發）
- Task 型（執行副作用，如 deploy / commit） → `disable-model-invocation: true`，防 Claude 擅自執行

---

## 10. Skill 類型速查

| 類型 | 觸發方式 | 範例 | 設計重點 |
|------|---------|------|---------|
| Document & Asset Creation | Claude 自動 | frontend-design、docx、pptx | assets/ 放模板 |
| Workflow Automation | 用戶觸發 | skill-creator、deploy | scripts/ 放主流程 |
| MCP Enhancement | Claude 自動 | sentry-code-review | references/ 放 MCP schema |
| Reference / Knowledge | Claude 自動 | coding-standards、api-conventions | references/ 主導 |
| Task / Slash Command | 用戶手動 `/name` | commit、fix-issue | `disable-model-invocation` |

---

## 11. 安全考量

> **強烈建議只使用信任來源的 skill**（自建或 Anthropic 提供）。

| 風險 | 說明 |
|------|------|
| 工具誤用 | 惡意 skill 可指示 Claude 執行非預期 bash / 檔案操作 |
| 資料外洩 | 有敏感資料存取權的 skill 可能洩漏到外部 |
| 注入攻擊 | 從 URL / 外部來源取內容的 skill 可能被注入 |

**審查時檢查**：所有 SKILL.md、scripts/、assets/ 異常的網路呼叫、檔案存取模式。

---

## 12. 發布前檢查清單

### 結構

- [ ] 資料夾 kebab-case（推薦 gerund）
- [ ] `SKILL.md` 大小寫正確
- [ ] 無 `README.md`（任何層級，含子目錄）
- [ ] 無 `INSTALLATION_GUIDE.md` / `QUICK_REFERENCE.md` / `CHANGELOG.md`
- [ ] SKILL.md body < 500 行

### YAML

- [ ] `---` 分隔符存在
- [ ] `name` kebab-case 且與資料夾同名
- [ ] `description` 第三人稱、< 250 字、含觸發詞
- [ ] 無角括號、無多行語法、無自訂屬性
- [ ] 引號閉合

### Body

- [ ] 無「When to Use This Skill」段（觸發資訊只放 description）
- [ ] 指令具體可操作、含錯誤處理
- [ ] 含至少 1 個範例
- [ ] 引用只一層深
- [ ] 100+ 行的 reference 有 TOC
- [ ] 術語一致
- [ ] 無時間敏感字串

### 觸發測試

- [ ] 主關鍵字觸發成功
- [ ] 改述查詢仍觸發
- [ ] 無關主題不觸發
- [ ] Haiku / Sonnet / Opus 行為一致

---

## 13. 延伸閱讀

| 文件 | 何時讀 |
|------|-------|
| `references/patterns-and-troubleshooting.md` | 設計多步驟 / 條件式工作流、需要進階範本模式 |
| `references/seeing-like-an-agent.md` | 想理解工具設計哲學與 agent 視角的演進 |

---

**Last Updated**: 2026-04-30
**Source**: Anthropic 官方 skill-creator（`/Users/mac-eric/.claude/plugins/marketplaces/anthropic-agent-skills/skills/skill-creator/`）+ 官方平台文件 + Claude Code 擴展規範 + 本專案實踐
