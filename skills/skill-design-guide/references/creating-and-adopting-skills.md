# 檔案結構 / 建立流程 / 類型速查 / 安全考量

> 何時讀：從零建一個新 skill、決定它屬哪一類型、決定某份內容該放 `scripts/`／`references/`／`assets/`、或引入他人寫的 skill 前做安全審查時。**亦由此進入**——`skill-creation-flow`（pm-rules）第 1 步把讀者送到入口檔之後的下一跳；`frontmatter-and-description.md` 與 `writing-the-body.md` 回跳「這一步在整體流程的哪裡」。
>
> 同目錄：frontmatter 與 description 在 `frontmatter-and-description.md`，正文寫法在 `writing-the-body.md`，拆分程序在 `splitting-an-existing-skill.md`，工作流範本、自由度與預設值、問題排除在 `patterns-and-troubleshooting.md`，設計哲學在 `seeing-like-an-agent.md`；〈核心心法〉的前兩則與〈發布前檢查清單〉留在 `SKILL.md`。
>
> 溯源：自 SKILL.md 搬移（v1.6.0，因兩個官方門檻皆超標）；〈三類 bundled resource 的分工〉於 v1.9.0 再自 `SKILL.md` 搬入。

本檔章節：〈檔案結構〉〈三類 bundled resource 的分工〉〈Skill 建立流程〉〈Skill 類型速查〉〈廢止與遷移〉〈安全考量〉。



## 檔案結構

```
your-skill-name/
├── SKILL.md              # 必要：YAML frontmatter + 主指令
├── scripts/              # 選填：可執行程式碼（可不載入 context 直接跑）
├── references/           # 選填：按需載入到 context 的文件
└── assets/               # 選填：產出時使用的範本 / 圖示 / 字型
```

`SKILL.md` 存在且 frontmatter 可解析由 `skill-registration-check-hook.py`（SessionStart）自動掃描全庫，WARNING 不阻擋；本清單仍需自查，因為該 hook 只驗證結構完整性，不驗證內容品質。

## 三類 bundled resource 的分工

| 類型 | 載入方式 | 何時用 | 範例 |
|------|---------|-------|------|
| `scripts/` | 可不讀直接執行（subprocess） | 同樣程式碼會被反覆寫；需要決定性結果 | `validate.py`、`init_skill.py`、`rotate_pdf.py` |
| `references/` | Claude `Read` 載入 context | 工作時需查的文件 / schema / 詳細範例 | `api-schema.md`、`patterns.md` |
| `assets/` | 不載入 context，被複製到輸出 | 產出物的素材 | `logo.png`、`template.pptx`、樣板專案目錄 |

**Why 區分這三類**：scripts 的價值是「跳過 context」，references 的價值是「按需載入」，assets 的價值是「不污染 context」。誤放會抵消設計。

### 本庫實況：四個官方分類外的目錄

官方三分類回答的是「內容如何被消費」，但本庫實際的 bundled resource 目錄不只三種。全深度掃描排除 `.venv`（`find .claude/skills -mindepth 2 -type d -name <型別> | grep -v '/\.venv/' | wc -l`；只掃第一層子目錄會漏掉巢狀在套件內的同名目錄，得出不同數字）：`references/` 38、`scripts/` 15、`tests/` 12、`hooks/` 8、`templates/` 7、`examples/` 5、`assets/` **0**——三分類裡官方唯一給的 `assets/` 在本庫從未被使用，另外四種目錄合計 32 處，全部不在官方分類、也不在本檔原表格內。

| 目錄 | 官方三分類最接近者 | 為何不直接歸入 | 本庫實例 |
|------|------|------|------|
| `tests/` | `scripts/`（皆屬執行時、非載入 context） | 官方分類未區分「主流程腳本」與「驗證主流程腳本的測試」，消費方式相同（subprocess 執行）但角色不同 | `ticket/tests`、`doc/tests` 等 12 處，多數為 pytest 套件 |
| `hooks/` | 三者皆不合 | 它掛的是 Claude Code 生命週期事件（`PreToolUse`／`Stop`），由 `settings.json` 註冊後由平台在事件時機呼叫；三分類假設 bundled resource 由 skill 自身工作流呼叫，這裡反過來是平台呼叫 skill | `ticket/hooks`、`tdd/hooks` 等 8 處 |
| `templates/` | `assets/`（官方原文舉例正是 "template.pptx"） | 語意相同、命名不同——本庫用獨立 `templates/` 而非 `assets/templates/`，是既成命名慣例而非刻意分工 | `doc/templates` 的 9 份 `.md` 模板，供建立新提案／規格／用例時複製結構 |
| `examples/` | `references/`（皆被 `Read` 載入 context） | 官方分類未區分「抽象規則」與「具體案例走查」，兩者都讀進 context 但性質不同 | `doc/examples/proposal-to-spec-walkthrough.md`、`version-bootstrap/examples/v02-walkthrough.md` |

**Action**：規劃新 skill 的 bundled resources 時，這四種不是額外選項而是官方三分類在本庫的既有延伸——「反覆被驗證的主流程」拆 `tests/`；「掛在平台事件上的程式碼」拆 `hooks/`；「複製後修改的文件骨架」用 `templates/`（不必另開 `assets/`）；「完整案例走查」拆 `examples/`（不必塞進 `references/` 的抽象規則裡）。

### 安裝式套件主體（pyproject.toml skills）

本庫至少 8 支 skill（`doc`、`ticket`、`worktree`、`mermaid-ascii`、`project-init`、`skill-sync`、`version-release`、`branch-worktree-guardian`）帶 `pyproject.toml`，是可安裝的 Python 套件而非單純 bundled resource 的集合。這類 skill 的主體程式碼（`ticket_system/`、`doc_system/`、`mermaid_ascii/` 等）本身就是整個套件，其下再嵌套自己的 `scripts/`／`tests/`／`templates/`。三分類問的是「這份內容怎麼被消費」，套件主體問的是「skill 的實作放哪裡」——兩個維度不衝突，也不互相取代，但三分類無法回答後者，這正是它「無處可放」的根源。

**Action**：套件主體以 skill 名稱的 snake_case 形式放在 skill 根目錄（如 `ticket/ticket_system/`），不要嘗試把它塞進 `scripts/`／`references/`／`assets/` 三選一——它是 skill 本身，不是 skill 攜帶的資源。

### 維護本檔：本庫實務對照程序（定期執行）

逐項補完當下的缺口只解決今天的落差；官方文件與本庫的 hook／慣例都會持續變動，需要一個可重複跑的程序，讓下一次的落差自己浮出來。

**Action**（雙方向都要跑，單向必漏——理由同 `SKILL.md`〈按需讀取〉的死名／孤兒節雙向檢查）：

1. **正向**（官方 → 本庫）：對照官方 skill spec／best practices 的主題清單，逐項確認 `SKILL.md`〈按需讀取〉路由表是否有對應章節；沒有即為缺口。
2. **反向**（本庫 → 官方文件／本檔）：本庫既有的 skill 相關 hook 是否已被本檔六份 reference 任一份提及；未提及是候選缺口，仍須逐一判斷它是否真屬「設計 skill 本身的規範」，或屬另一支 skill（如 `skill-sync`）自己的操作機制——後者不算缺口。

```bash
# 反向檢查：本庫 skill 相關 hook 是否被 skill-design-guide 任一檔提及
for h in $(ls .claude/hooks/ | grep -i skill); do
  n=$(grep -rl "$h" .claude/skills/skill-design-guide/ | wc -l)
  echo "$h -> $n"
done
```

**當下跑出的落差（示範，已個別判定）**：本次修訂後執行上述指令，`skill-shadowing-check-hook.py`（見〈載入優先序與同名遮蔽〉）、`skill-description-length-check-hook.py`、`skill-residue-check-hook.py` 已有歸屬；`skill-registration-check-hook.py`（SessionStart 檢查 SKILL.md 是否存在且 frontmatter 可解析）與 `skill-banned-term-scan-hook.py`（掃描 skill 正文誤用禁用詞）屬本檔規範範圍但尚無歸屬，判定為真缺口；`framework-rule-edit-skill-trigger-hook.py`（觸發的是 `compositional-writing` skill 而非本檔）與 `skill-sync-push-residue-gate-hook.py`（`skill-sync` 自身的 push 機制）判定為誤判，不屬本檔範圍。真缺口的落地見〈發布前檢查清單〉「結構」組與 `writing-the-body.md`〈內容品質規則〉。

## Skill 建立流程

> 來源：Anthropic `skill-creator` 官方流程，**本節已就本專案調整**。新建或大改 skill 時依序執行。
>
> **不涵蓋**：本節不是純官方流程。〈Step 5：打包〉本專案不執行（走 git 同步、不產出 `.skill` 檔）；Step 4 的六個子項中 4d（量兩個門檻）與 4f（走發布前檢查清單）是本地約定，不在官方流程內。要對照官方原文時以 `skill-creator` 為準，不以本節為準。

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

官方 `skill-creator` 提供 `scripts/init_skill.py`。手動建立時依〈檔案結構〉。

### Step 4：撰寫內容

本節內部用 **4a–4f** 編號，不用裸數字——本檔的 `## Step 1..6` 已佔用 1–6 這個命名空間，節內表格若也用 1–6，「Step 5」會同時指〈Step 5：打包〉與本表第五列，而**跨檔指涉一律只寫「Step N」**（實測有三處外部引用落在這個歧義區）。

| 順序 | 動作 |
|------|------|
| 4a | 先寫 bundled resources（scripts / references / assets） |
| 4b | 寫 SKILL.md frontmatter（依 `frontmatter-and-description.md`〈YAML Frontmatter〉） |
| 4c | 寫 SKILL.md body（依 `writing-the-body.md`〈Body 寫作〉的骨架） |
| 4d | 量兩個門檻（門檻值、量測指令與分段估算表見 `SKILL.md`〈Progressive Disclosure — 三層載入〉）；超標即依 `splitting-an-existing-skill.md` 外移 |
| 4e | 測試 scripts 實際可跑 |
| 4f | 走一遍 `SKILL.md`〈發布前檢查清單〉四組 |

**寫作風格**：用祈使句 / 不定式（imperative / infinitive），不用「我」「你」。

### 測試慣例與執行環境（Step 4e 展開）

Step 4 表格的 4e 只有六字「測試 scripts 實際可跑」，沒有給測試放哪裡、用什麼指令跑。本庫依 skill 是否帶 `pyproject.toml` 分兩種慣例：

| 形態 | 判斷依據 | 測試放哪裡 | 執行環境 |
|------|---------|-----------|---------|
| 單檔 script | skill 根目錄無 `pyproject.toml` | 多數目前無測試；需要時放 `scripts/tests/` | 腳本自帶 PEP 723 inline header（`#!/usr/bin/env -S uv run --quiet --script` + `# /// script ... ///`），`uv run --script <file>` 或 `uv run <file>` 直接執行，無需另外安裝依賴——同框架 hook 腳本（如 `file-size-guardian-hook.py`）的既有慣例 |
| 安裝式套件 | skill 根目錄有 `pyproject.toml` | 套件內 `tests/`（可能同時有根層 `tests/` 與巢狀 `<package>/tests/` 兩處，見 `ticket` skill） | `pyproject.toml` 的 `[tool.pytest.ini_options]` 宣告 `testpaths`，一次 `pytest` 涵蓋所有宣告目錄；裸指令跑，**不要**帶顯式路徑參數 |

**Why**：兩種慣例對應本庫兩種 skill 形態，混用會出錯——對單檔 script 找 `pyproject.toml` 會找不到；對安裝式套件的 `tests/` 用 `uv run --script` 執行整包會因缺依賴宣告而失敗。

**Consequence**：套件型 skill 的測試若帶顯式路徑執行（如 `pytest tests/`），會覆蓋 `testpaths` 只收集單一目錄，巢狀 `<package>/tests/` 靜默漏跑而不觸發任何錯誤或警告——覆核者可能因此在只驗了一半測試的情況下宣稱「測試通過率 100%」。

**Action**：安裝式套件一律用裸指令跑（範例：`(cd .claude/skills/ticket && uv run --with pytest --with pyyaml --with filelock python -m pytest -q)`），單檔 script 一律用 `uv run --script` 或 `uv run` 直接執行驗證輸出。

### Step 5：打包

**本專案不執行這一步**：本庫的 skill 走 git 同步、不產出 `.skill` 檔。只有要把 skill 散布到本庫以外時才走官方打包。

官方 `skill-creator`（Anthropic 提供的 skill，安裝於 plugin marketplace，非本庫資產）提供 `scripts/package_skill.py`，自動驗證 frontmatter + 命名 + 結構，產出 `.skill` 檔。實測該腳本以 `from scripts.quick_validate import ...` 匯入，直接執行會 `ModuleNotFoundError`，須以 `PYTHONPATH=<skill-creator 目錄>` 呼叫。

### Step 6：迭代

| 訊號 | 動作 |
|------|------|
| Skill 該觸發沒觸發 | 修 description（見 `frontmatter-and-description.md`〈防 undertrigger（官方建議）〉） |
| Skill 觸發但用錯方向 | 修 SKILL.md body 路由 |
| Skill 反覆需要相同細節 | 拆出 reference 或寫腳本 |

---

## Skill 類型速查

| 類型 | 觸發方式 | 範例 | 設計重點 |
|------|---------|------|---------|
| Document & Asset Creation | Claude 自動 | frontend-design、docx、pptx | assets/ 放模板 |
| Workflow Automation | 用戶觸發 | skill-creator、deploy | scripts/ 放主流程 |
| MCP Enhancement | Claude 自動 | sentry-code-review | references/ 放 MCP schema |
| Reference / Knowledge | Claude 自動 | coding-standards、api-conventions | references/ 主導 |
| Task / Slash Command | 用戶手動 `/name` | commit、fix-issue | `disable-model-invocation` |

---

## 廢止與遷移

本檔的 Skill 生命週期止於〈Step 6：迭代〉，沒有終點——skill 該怎麼廢止、遷移到別的 skill，這六份 reference 檔零字。這比 agent 的廢止更急迫：agent 的完整定義只在被派發時載入；skill 的 `description` 常駐 system prompt（見〈Concise is Key〉），廢止前每一回合都在佔用觸發預算，留著不處理是持續成本，不是零成本的擱置。

本庫已有的 agent 廢止慣例可直接借用（`john-carmack`、`memory-network-builder` 兩份已廢棄的 agent 定義）：

| 步驟 | 動作 |
|------|------|
| 1 | `description` 開頭加 `[DEPRECATED]`，接一句合併去向（如「已合併至 X skill」） |
| 2 | body 第一段列：狀態（已廢棄）、合併日期、合併目標、合併原因 |
| 3 | 保留檔案，不刪除——既有機制（如 `skill-shadowing-check-hook.py`）以檔案存在為前提，且刪除會讓仍引用舊名的文件變成死連結 |
| 4 | 全庫查引用舊名的位置並改指向新 skill：`grep -rl "<舊 skill 名>" .claude/ docs/` |

**與 agent 廢止的差異**：agent 定義只在派發時載入，廢止後遺留檔案不佔常駐成本；skill 的 `description` 無論廢止與否都常駐 system prompt。**加 `[DEPRECATED]` 前綴不解除這個常駐成本，只是防止誤觸發**——它仍計入本庫全部 skill 共用的 description context budget（見 `frontmatter-and-description.md`〈三個長度口徑，只有一個是閘門〉）。徹底解除常駐成本需要真正移除該 skill 目錄，這是加前綴之外的下一步，不是同一步。

**Action**：確認遷移目標穩定運作至少一個版本週期後，才移除舊 skill 目錄；移除前執行第 4 步的引用查詢確保無遺留死連結。

---

## 安全考量

> **強烈建議只使用信任來源的 skill**（自建或 Anthropic 提供）。

| 風險 | 說明 |
|------|------|
| 工具誤用 | 惡意 skill 可指示 Claude 執行非預期 bash / 檔案操作 |
| 資料外洩 | 有敏感資料存取權的 skill 可能洩漏到外部 |
| 注入攻擊 | 從 URL / 外部來源取內容的 skill 可能被注入 |

**審查時檢查**：所有 SKILL.md、scripts/、assets/ 異常的網路呼叫、檔案存取模式。
