# YAML Frontmatter / Description 寫作 / 命名規則 / 觸發控制

> 何時讀：寫或修一個 skill 的 frontmatter 時——name、description、標準與 Claude Code 擴展欄位、觸發控制矩陣、資料夾命名。**亦由此進入**——`SKILL.md`〈發布前檢查清單〉的「YAML」與「觸發測試」兩組；`creating-and-adopting-skills.md` 的 〈Step 4：撰寫內容〉的 4b（寫 frontmatter）與〈Step 6：迭代〉（該觸發沒觸發時修 description）。
>
> 同目錄：正文寫法在 `writing-the-body.md`，新建流程與類型速查在 `creating-and-adopting-skills.md`，拆分程序在 `splitting-an-existing-skill.md`，工作流範本與問題排除在 `patterns-and-troubleshooting.md`，設計哲學在 `seeing-like-an-agent.md`；〈核心心法〉〈三類 bundled resource 的分工〉〈發布前檢查清單〉留在 `SKILL.md`。
>
> 溯源：自 SKILL.md 搬移（v1.6.0，因兩個官方門檻皆超標）。

本檔章節：〈YAML Frontmatter〉〈Description 寫作（最重要的一節）〉〈命名規則〉〈觸發控制矩陣〉。

## YAML Frontmatter

### 標準欄位（Anthropic Agent Skills）

| 欄位 | 必填 | 說明 |
|------|------|------|
| `name` | 是 | kebab-case，與資料夾名稱一致 |
| `description` | 是 | 做什麼 + 何時用，最長 1024 字元（官方上限）；本框架另有更嚴的 250 字元閘門，見〈Description 寫作〉 |
| `license` | 否 | 開源授權字串 |
| `compatibility` | 否 | 環境需求，最長 500 字元 |
| `allowed-tools` | 否 | 限制 skill 可用工具 |
| `metadata` | 否 | 自訂 key-value（author、version、tags 等） |

### Claude Code 擴展欄位

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

### 安全與格式禁令

| 禁止 | 原因 | 修正 |
|------|------|------|
| 角括號 `< >` | frontmatter 進 system prompt，可能被解讀為指令 | 用「lt」「gt」或全形字 |
| `name` 含 "claude" / "anthropic" | 保留名稱 | 換名 |
| YAML 多行語法（`\|` `>`） | 後續行被誤判為新屬性 | 改單行雙引號字串 |
| 自訂屬性（`triggers` / `type` / `category` 等） | 解析器拒絕 | 全部塞進 `metadata` |
| 缺 `---` 分隔符 | 整段被當 markdown body | 補分隔符 |
| 未閉合引號 | 解析失敗整支 skill 不可用 | 補引號 |

---

## Description 寫作（最重要的一節）

description 是 Claude 自動觸發 skill 的**唯一機制**。寫不好等於 skill 不存在。

### 強制：長度 < 250 字元（最重要規則）

| 長度 | 評估 | 後果 |
|------|------|------|
| < 100 字元 | 推薦 | 觸發詞完整可見 |
| 100-250 字元 | 可接受 | 接近上限，關鍵詞放前面 |
| > 250 字元 | 禁止 | **被截斷，後段觸發詞丟失，自動觸發失敗** |

**Why**：Claude Code 對單一 description 有截斷行為（context budget 約 2% / 16k 字元）。實證案例：`/parallel-evaluation` 因 description 過長，「多視角審核」「code review」等詞在 Use for: 段落被截斷，無法自動觸發。

**Action**：把最重要的觸發詞放最前面；截斷時前段不會丟。量測用：

```bash
python3 -c "import re,sys;t=open(sys.argv[1],encoding='utf-8').read();m=re.search(r'^description: \"(.*?)\"\s*\$',t,re.M|re.S);print(len(m.group(1)))" SKILL.md
```

執法層為 `skill-description-length-check-hook.py`（SessionStart 掃全庫，`WARNING_THRESHOLD = 250`，以字元計）。它是 warning 不阻擋，故仍須自查。

### 強制：第三人稱

description 進 system prompt，「I」「you」會破壞語境。

| 正確 | 錯誤 |
|------|------|
| `Processes Excel files and generates reports` | `I can help you process Excel files` |
| `Use when user uploads .xlsx files` | `You can use this to process Excel files` |

### 結構公式

```
[做什麼] + [何時使用 / 觸發詞清單] + [可選：負面觸發]
```

### 防 undertrigger（官方建議）

Claude 預設保守、傾向不觸發。description 應**主動列同義詞與隱性需求**。

| 對比 | 範例 |
|------|------|
| 太被動 | `Processes PDF files to extract text and tables.` |
| 積極版 | `Processes PDF files to extract text and tables. Use whenever the user mentions PDFs, documents, files, or asks to summarize a report — even if they don't explicitly say 'PDF'.` |

**技巧**：

- 列同義詞 / 近似詞（「document」「file」「report」不只「PDF」）
- 加 "even if they don't explicitly ask..." 涵蓋隱性需求
- 加 "Make sure to use this skill whenever..." 作明確指引

### 防 overtrigger — 負面觸發

```yaml
description: "Advanced statistical modeling for CSV files. Use for regression, clustering, hypothesis testing. Do NOT use for simple data exploration (use data-viz skill instead)."
```

### 範例對照

| 評估 | description |
|------|------------|
| 好（具體 + 觸發詞 + 同義詞） | `Analyzes Figma design files and generates developer handoff docs. Use when user uploads .fig files, asks for 'design specs', 'component documentation', or 'design-to-code handoff'.` |
| 好（負面觸發） | `Statistical modeling for CSV. Use for regression / clustering. Do NOT use for visualization (use data-viz skill).` |
| 壞（太籠統） | `Helps with projects.` |
| 壞（缺觸發） | `Creates sophisticated multi-page documentation systems.` |
| 壞（描述內部架構） | `統一 Ticket 系統 v1.0 — 整合 create / track / handoff / resume / migrate / generate 六大功能。` |

### 觸發品質診斷

| 症狀 | 修正 |
|------|------|
| Skill 該觸發卻沒觸發 | description 太籠統 → 加同義詞、加 "whenever..." |
| Skill 不該觸發卻觸發 | 加負面觸發 "Do NOT use for X" |
| 不確定 | 直接問 Claude「When would you use the [skill name] skill?」，看回答對不對 |

---

## 命名規則

### 強制

| 規則 | 正確 | 錯誤 |
|------|------|------|
| `SKILL.md` 大小寫 | `SKILL.md` | `skill.md`、`SKILL.MD` |
| 資料夾 kebab-case | `notion-project-setup` | `Notion Project Setup`、`my_skill` |
| 無底線 | `my-cool-skill` | `my_cool_skill` |
| 無大寫 | `my-cool-skill` | `MyCoolSkill` |

### 推薦：Gerund 命名

| 類型 | 範例 | 評估 |
|------|------|------|
| Gerund（動詞 + ing，官方推薦） | `processing-pdfs`、`analyzing-spreadsheets`、`managing-databases` | 最佳，意圖明確 |
| 名詞片語 | `pdf-processing`、`spreadsheet-analysis` | 可接受 |
| 模糊名稱 | `helper`、`utils`、`tools`、`documents` | 避免，無法判斷觸發場景 |

## 觸發控制矩陣

| frontmatter 設定 | 用戶可呼叫 | Claude 可呼叫 | 載入時機 |
|----|----|----|----|
| 預設 | 是 | 是 | description 常駐 context |
| `disable-model-invocation: true` | 是 | 否 | 用戶呼叫時才載入 |
| `user-invocable: false` | 否 | 是 | description 常駐 context |

**設計建議**：

- Reference 型（知識 / 規範） → 預設（自動觸發）
- Task 型（執行副作用，如 deploy / commit） → `disable-model-invocation: true`，防 Claude 擅自執行
