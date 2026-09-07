# 檔案結構 / 建立流程 / 類型速查 / 安全考量

> 何時讀：從零建一個新 skill、決定它屬哪一類型、或引入他人寫的 skill 前做安全審查時。**亦由此進入**——`skill-creation-flow`（pm-rules）第 1 步把讀者送到入口檔之後的下一跳；`frontmatter-and-description.md` 與 `writing-the-body.md` 回跳「這一步在整體流程的哪裡」。
>
> 同目錄：frontmatter 與 description 在 `frontmatter-and-description.md`，正文寫法在 `writing-the-body.md`，拆分程序在 `splitting-an-existing-skill.md`，工作流範本與問題排除在 `patterns-and-troubleshooting.md`，設計哲學在 `seeing-like-an-agent.md`；〈核心心法〉〈三類 bundled resource 的分工〉〈發布前檢查清單〉留在 `SKILL.md`。
>
> 溯源：自 SKILL.md 搬移（v1.6.0，因兩個官方門檻皆超標）。

本檔章節：〈檔案結構〉〈Skill 建立流程〉〈Skill 類型速查〉〈安全考量〉。



## 檔案結構

```
your-skill-name/
├── SKILL.md              # 必要：YAML frontmatter + 主指令
├── scripts/              # 選填：可執行程式碼（可不載入 context 直接跑）
├── references/           # 選填：按需載入到 context 的文件
└── assets/               # 選填：產出時使用的範本 / 圖示 / 字型
```

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
| 4d | 量兩個門檻（門檻值、量測指令與語言換算表見 `SKILL.md`〈Progressive Disclosure — 三層載入〉）；超標即依 `splitting-an-existing-skill.md` 外移 |
| 4e | 測試 scripts 實際可跑 |
| 4f | 走一遍 `SKILL.md`〈發布前檢查清單〉四組 |

**寫作風格**：用祈使句 / 不定式（imperative / infinitive），不用「我」「你」。

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

## 安全考量

> **強烈建議只使用信任來源的 skill**（自建或 Anthropic 提供）。

| 風險 | 說明 |
|------|------|
| 工具誤用 | 惡意 skill 可指示 Claude 執行非預期 bash / 檔案操作 |
| 資料外洩 | 有敏感資料存取權的 skill 可能洩漏到外部 |
| 注入攻擊 | 從 URL / 外部來源取內容的 skill 可能被注入 |

**審查時檢查**：所有 SKILL.md、scripts/、assets/ 異常的網路呼叫、檔案存取模式。
