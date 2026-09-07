# YAML Frontmatter / Description 寫作 / 命名規則 / 觸發控制

> 何時讀：寫或修一個 skill 的 frontmatter 時——name、description、標準與 Claude Code 擴展欄位、觸發控制矩陣、資料夾命名。**亦由此進入**——`SKILL.md`〈發布前檢查清單〉的「YAML」與「觸發測試」兩組；`creating-and-adopting-skills.md` 的 〈Step 4：撰寫內容〉的 4b（寫 frontmatter）與〈Step 6：迭代〉（該觸發沒觸發時修 description）。
>
> 同目錄：正文寫法在 `writing-the-body.md`，新建流程、類型速查與三類 bundled resource 的分工在 `creating-and-adopting-skills.md`，拆分程序在 `splitting-an-existing-skill.md`，工作流範本、自由度與預設值、問題排除在 `patterns-and-troubleshooting.md`，設計哲學在 `seeing-like-an-agent.md`；〈核心心法〉的前兩則與〈發布前檢查清單〉留在 `SKILL.md`。
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

### 擴展欄位的選擇判準

七列裡只有 `disable-model-invocation`／`user-invocable` 兩列在〈觸發控制矩陣〉給了選擇時機；其餘五列在建立時沒有依據可查，寫的人只能照抄範例值。

| 欄位 | 何時用 | 何時不用 |
|------|-------|---------|
| `argument-hint` | skill 走 `/name <arg>` 手動呼叫且參數是必要輸入（如 issue 編號、檔名） | 全自動觸發、無需補全提示的 skill；沒有 `/` 手動介面時本欄位不生效 |
| `model` | skill 的工作機械、可預期、不需要主對話的模型能力（如固定格式轉換），指定較小模型可省成本 | 未驗證過在指定模型上行為一致——本庫零使用，指定前先跑一輪〈觸發測試〉的模型一致性檢查 |
| `context: fork` | skill 需要大量探索性讀取（搜尋、掃描），過程雜訊不該留在主對話歷史 | skill 的產出需要主對話立即接續使用（fork 出去的結果需要額外一步才能帶回） |
| `agent` | 與 `context: fork` 搭配，依隔離出去的工作性質選代理人（純搜尋用 `Explore`） | 未設 `context: fork` 時本欄位不生效 |
| `hooks` | 見下方〈`hooks` 欄位是死路由〉 | 同上 |

### `hooks` 欄位是死路由

本庫 59 支 skill 對 `hooks:` frontmatter 欄位的使用數為零，本檔對它的說明只有「見官方文件」四字、不含連結。這與 skill 目錄下常見的 `hooks/` 資料夾是兩件不相干的事——後者裝的是本庫既有的 Claude Code 生命週期 hook（`PreToolUse`／`Stop` 等，經 `settings.json` 註冊，`ticket`、`tdd`、`worktree` 等 skill 皆有此目錄，見 `creating-and-adopting-skills.md`〈本庫實況：四個官方分類外的目錄〉），前者是 skill 自身宣告、目前無任何 skill 使用的生命週期掛勾欄位。名稱相同、機制不同，未查證前容易誤把 `hooks/` 目錄的既有先例當成 `hooks:` 欄位已被驗證過。

**Action**：需要用 `hooks:` 欄位時，先讀官方文件 <https://code.claude.com/docs/en/skills> 取得目前語法（本庫無可對照的本地實例）；需要的是「skill 自帶的可執行／可查閱檔案」走 `scripts/`／`references/`，需要的是「Claude Code 生命週期 hook」走 `.claude/hooks/` 或 skill 目錄下的 `hooks/`。

### `metadata.portable`：建立時要下的決定，不是事後的副作用

`metadata.portable: true` 目前只在 `writing-the-body.md`〈外部引用：指名身分，不用檔案路徑〉的 Consequence 段落以一句話出現——宣告 `portable: true` 的 skill 若指名 `.claude/...` 路徑，`skill-sync` push 會被中止。這是它唯一的出處，且是以「違反後會怎樣」的副作用形式帶出，不是建立 skill 當下要下的判斷。

**Action（Step 4b 撰寫 frontmatter 時判斷，不要等 push 被擋才回頭改）**：

| 問題 | 答案 | 決定 |
|------|------|------|
| 這個 skill 的判準／流程／範本是否綁定特定專案的目錄結構或檔案路徑？ | 否——邏輯可原樣搬到任何專案 | `portable: true`；正文與 reference 一律以身分指名而非路徑（見 `writing-the-body.md`〈外部引用〉），專案專屬的實際路徑另放 `references/project-integration/`（依命名慣例排除於 `skill-sync` push，`component-contract-design` skill 已有此實例） |
| 是 | 不宣告 `portable` | 可自由使用 `.claude/...` 路徑 |

**Consequence**：宣告 `portable: true` 後才發現正文寫死了路徑，要嘛違反可攜性承諾被 push 擋下，要嘛回頭把已寫好的內容全部改成身分指名並搬移到 `project-integration/`——晚判斷的成本是重寫，不是重新標記一個欄位。

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

### 三個長度口徑，只有一個是閘門

description 的長度在本 skill 有三個數字，單位不同、互不換算。判定一律用 250 字元那一個，另外兩個不作閘門。

| 口徑 | 值 | 出處與角色 | 換算 |
|------|----|-----------|------|
| 官方欄位上限 | 1,024 字元 | Anthropic spec 的欄位硬上限，超過即不合規 | 是字元，與本框架閘門同單位 |
| 本框架閘門 | 250 字元 | `skill-description-length-check-hook.py` 的 `WARNING_THRESHOLD`，SessionStart 掃全庫 | 全 ASCII 約 62 tokens、全繁中約 192 tokens |
| 三層表的量級參考 | 約 100 tokens | 官方 overview 對 Level 1 的描述，**非閘門** | 全 ASCII 約 400 字元、全繁中約 130 字元 |

**Why 只用 250**：它是唯一以可直接量測的單位表達、又有執法層的線。另外兩個都給不出行動——1,024 遠寬於實際可用量；約 100 tokens 換算後在兩種語言下都對不上 250，且方向相反（英文的 250 字元只有約 62 tokens，看起來還有四成餘裕；繁中的 250 字元已約 192 tokens，看起來將滿）。同一份 description 依口徑不同會得到相反的行動建議。

**Consequence**：本 skill 自己的 description 是 237 字元、全 ASCII、約 59 tokens。用約 100 tokens 那一個口徑判，結論是「還可以再寫四成」；用 250 字元閘門判，只剩 13 字元。照前者行動會直接撞上 hook。

**Action**：只量字元數（指令見下一節），不換算 token。三層表的量級參考只用來理解第 1 層為何要短，不進入判定。

> **16k 那個數字管的是全庫合計，不是單支。** 它是 description 區塊的 context budget 量級，本庫全部 skill 的 description 共用。實測本庫 58 支 skill 的 description 合計已達 17,929 字元（量法：逐檔取 frontmatter 的 `description:` 首行、含引號）；把 16k 讀成單支的允許長度，會得出「250 還有六十幾倍餘裕」這種錯誤結論。

### 強制：長度 < 250 字元（最重要規則）

| 長度 | 評估 | 後果 |
|------|------|------|
| < 100 字元 | 推薦 | 觸發詞完整可見 |
| 100-250 字元 | 可接受 | 接近上限，關鍵詞放前面 |
| > 250 字元 | 禁止 | **被截斷，後段觸發詞丟失，自動觸發失敗** |

**Why**：description 區塊有 context budget（約 2% / 16k 字元，全庫 skill 共用，見上一節），超出後個別 description 被截斷。實證案例：`/parallel-evaluation` 因 description 過長，「多視角審核」「code review」等詞在 Use for: 段落被截斷，無法自動觸發。

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

### 跨 Skill 觸發競爭（建立前必查）

上一節處理單一 skill 該不該觸發；本節處理**兩個 skill 都可能被同一句話觸發**時如何取捨——這是「Skill 創建流程」pm-rules 文件前置條件「確認無既有 Skill 覆蓋相同場景」列出的檢查項，但該文件未給做法。

**Why**：description 是自動觸發的唯一依據（見上文），兩份 description 共用觸發詞時 Claude 選中哪一個不可預測，新 skill 的觸發詞會與既有 skill 爭奪同一批使用者措辭，不會因為「後寫的更完整」而自動勝出。

**Action**：

1. 列出候選 description 中最具體的 2-3 個觸發詞
2. 逐一查是否已被其他 skill 使用：`grep -l "<觸發詞>" .claude/skills/*/SKILL.md`
3. 有命中 → 判斷場景是否真重疊：不重疊則不需處理；重疊則依〈防 overtrigger — 負面觸發〉的句式，在**兩份** description 互相加註「Do NOT use for X（use Y instead）」——只改新寫的那份防不住舊 skill 持續吸走使用者措辭

**Consequence**：只在新 description 單方加負面觸發，防不住舊 skill 的正面觸發詞持續與新 skill 爭奪同一批措辭；兩份都要動才成立。

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

### 載入優先序與同名遮蔽（建立前必查）

Skill 名稱衝突不是「兩者都載入、依 context 選用」，而是靜默覆蓋——同名 skill 在四層間依固定優先序合併去重，**先出現者保留、後出現者被捨棄**，且失效對後者的作者不可見。

| 優先序（高到低） | 層級 | 對本庫的意涵 |
|----|------|------|
| 1 | managed（policy-scope） | 與 project 同名時，project 版本被完全遮蔽 |
| 2 | personal（`~/.claude/skills/`） | 本庫政策為此層恆空；一旦非空即覆蓋全部專案的同名 project skill |
| 3 | project（`.claude/skills/`） | 本庫寫入的位置 |
| 4 | plugin marketplace | 優先序最低，與 project 同名時被遮蔽的是 marketplace 版本 |

**Why**：`skill-shadowing-check-hook.py`（SessionStart）的存在本身即是實證——它掃描 project／personal 兩層全部同名 skill、逐檔比對差異，這件事發生過才需要 hook。

**Consequence**：新建 skill 撞名於更高優先序層，新內容永遠不會被載入，宣告層（規則寫了）與執行層（規則送不到執行點）就此脫節，且對撰寫者不可見。

**Action**：建立新 skill 前，除了確認本庫內無同名（`ls .claude/skills/`），也確認 `~/.claude/skills/` 無同名（該層應恆空，非空本身即是待處理的違規）。**Coverage gap**：`skill-shadowing-check-hook.py` 不掃描 managed 與 plugin marketplace 兩層，兩者的碰撞需自行查（plugin marketplace 可用 `find ~/.claude/plugins/marketplaces -mindepth 3 -maxdepth 3 -type d -path '*/skills/*'` 列出）。

## 觸發控制矩陣

| frontmatter 設定 | 用戶可呼叫 | Claude 可呼叫 | 載入時機 |
|----|----|----|----|
| 預設 | 是 | 是 | description 常駐 context |
| `disable-model-invocation: true` | 是 | 否 | 用戶呼叫時才載入 |
| `user-invocable: false` | 否 | 是 | description 常駐 context |

**設計建議**：

- Reference 型（知識 / 規範） → 預設（自動觸發）
- Task 型（執行副作用，如 deploy / commit） → `disable-model-invocation: true`，防 Claude 擅自執行
