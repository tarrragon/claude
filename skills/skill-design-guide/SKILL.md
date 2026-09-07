---
name: skill-design-guide
description: "Anthropic skill spec plus this project's conventions: frontmatter, descriptions, loading budgets, and splitting an oversized skill. Use when creating a skill, editing SKILL.md, reviewing skill quality, or moving content into references/."
metadata:
  version: 1.7.3
---

# Skill Design Guide

依據 Anthropic 官方 `skill-creator` 與 Claude Code 平台規範整合的 Skill 設計指引。本檔聚焦「為什麼這樣設計」與「具體該怎麼做」，不重述官方文件全文。

**官方來源**：

- Skill spec: <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>
- Best practices: <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices>
- Claude Code skills: <https://code.claude.com/docs/en/skills>
- 官方 `skill-creator`: 已安裝於本環境的 plugin marketplace

---

## 核心心法

### Concise is Key — context 是公共資源

**預設假設**：Claude 已經夠聰明。每段文字必須通過兩問才能保留。

| 自問 | 通過標準 |
|------|---------|
| Claude 真的不知道這個嗎？ | 通用程式知識 / 框架慣例 → 移除；專案特有 / 反直覺 → 保留 |
| 這段文字值得它的 token 成本嗎？ | 表格 / 範例優於散文，散文優於不存在 |

**Why**：兩層各有各的成本，機制不同，不可混談。**第 1 層**（description）常駐 system prompt，冗長會排擠其他 skill 的 description budget，讓自動觸發失敗——這是唯一會傷到別人的一層。**第 2 層**（body）只在本 skill 被觸發後載入，不影響他人；但它一旦載入就與對話歷史及其餘 context 競爭，冗長會壓縮讀者當下真正需要的空間。官方原文：「once Claude loads it, every token competes with conversation history and other context」。

### Progressive Disclosure — 三層載入

| 層 | 載入時機 | 預算 | 寫什麼 |
|----|---------|------|-------|
| 1. frontmatter（name + description） | 常駐 system prompt | ~100 tokens / skill | 何時觸發 + 做什麼 |
| 2. SKILL.md body | 觸發後載入 | < 5k tokens **且** < 500 行 | 核心工作流 + 路由 |
| 3. references/ + scripts/ + assets/ | Claude 按需 read / exec | 無上限 | 細節、範例、模板、可執行腳本 |

**兩個門檻都是官方值，且來自不同頁**：`< 5k tokens` 出自 spec overview 的 Level 2 表格（逐字 "Under 5k tokens"）；`< 500 行` 出自 best-practices，該頁三處重述（Progressive disclosure patterns、Token budgets、Checklist，皆為 "Keep SKILL.md body under 500 lines for optimal performance"）。兩者互補而非互相取代——tokens 是真正的成本，行數是它在英文內容下的可靠代理。

**Action**：兩個門檻都量，任一超標即須外移。

```bash
wc -l .claude/skills/<name>/SKILL.md   # > 500 即須外移（官方值，直接可判）
wc -m .claude/skills/<name>/SKILL.md   # 字元數，需依語言換算，見下
```

**字元數要換算才能判**，因為 chars/token 隨語言差四倍：

| 內容 | chars/token | 5k tokens 約當 | 依據 |
|------|------------|---------------|------|
| 繁中為主 | 1.3 | 6,500 字元 | `file-size-guardian-hook.py` 的 `CHARS_PER_TOKEN`，2026-06-12 以 `/context` 實測校準（該註解逐字寫「繁中為主集合」） |
| 英文為主 | 約 4 | 約 20,000 字元 | 一般 BPE 分詞的常見比值 |

混合內容取兩者之間，或直接以行數門檻判。**不可把 6,500 無條件套用於 ASCII 為主的 skill**——實測本庫一份 100% ASCII、7,584 字元的 skill 依 6,500 判超標，而它約 1,896 tokens，僅官方預算的 38%。

超標時外移「一次只用其中一段」的內容——互斥的模式分支、填表問句、句型範本、Examples、Troubleshooting；SKILL.md 留路由與判準。外移時必在 SKILL.md 留路由訊號（何時讀該檔）。**拆分既有 skill 另有程序**，見 `references/splitting-an-existing-skill.md`：搬移正確不等於拆分後可用，兩者要用不同方法驗。

**Why 兩個都要量**：行數對繁中失效——每行字元數沒有上界，兩者在長行處脫鉤。一份實測案例（該 skill 已於此後拆分，以下為拆分前的量測值）：245 行（**通過** 500 行門檻）但 15,015 字元 ≈ 11.5k tokens，超標 2.3 倍，最長單行 548 字。反向地，字元數對英文失效（見上表）。單量一個必有一類漏網。

**Consequence**：本層目前**無 hook 執法**——`file-size-guardian-hook.py` 的 `SCAN_CONFIG` 涵蓋 pm-rules / rules / references 三處，不含 `.claude/skills/`；`skill-description-length-check-hook.py` 只查第 1 層的 description（250 字元）。第 2 層判準完全依賴撰寫者自查，寫錯代理指標即等同無判準。

### Degrees of Freedom — 自由度匹配脆弱性

| 自由度 | 任務特徵 | 表達方式 | 範例 |
|--------|---------|---------|------|
| 高 | 多種解法皆可、依情境決定 | 文字指引 + 啟發式 | 「分析使用者需求並建議方向」 |
| 中 | 有偏好模式、容許變化 | 虛擬碼 / 帶參數腳本 | 「依照範本但可調整章節順序」 |
| 低 | 操作脆弱、一致性關鍵 | 具體腳本、固定步驟 | 「執行 `scripts/validate.py`，不可改寫」 |

**判準**：「Claude 走錯一步會壞掉嗎？」會 → 低自由度；不會 → 高自由度。中自由度是這兩者的中間帶——**有一條偏好路徑，但偏離它不會壞**。

**同一個任務寫成三種自由度**（任務：讓 skill 產出一份審查報告）：

```markdown
高：整理審查發現，依嚴重度分組，附位置與建議修法。

中：用下列骨架，欄位可增減：
    | 位置 | 問題 | 嚴重度 | 建議修法 |
    嚴重度用「嚴重必修／建議可改」兩級；需要第三級時說明理由。

低：逐項填滿下表，欄位不可增減、不可留空：
    | 位置 | 問題 | 嚴重度 | 全部命中位置 | 建議修法 |
    嚴重度只能填「嚴重必修」或「建議可改」。
    「全部命中位置」不可寫「多處」，須逐一列出或註明抽樣方式。
```

差別不在字數，在**偏離的空間**：高只給目標，中給骨架並明示可調，低把每個欄位的合法值也定死。選錯的代價是不對稱的——該低而給高，產物形態每次都不同；該高而給低，執行者會在不適用的情境硬填。

### Opinionated Defaults — 預設路徑引導正確做法

**預設假設**：使用者（尤其 AI agent）走預設路徑。如果預設路徑不引導正確做法，文件規範再完整也無效。

| 設計問題 | 判準 | 行動 |
|---------|------|------|
| Skill 工作流有分支選擇？ | 有「多數情況下正確」的路徑嗎？ | 有 → 預設走該路徑，允許覆蓋 |
| 需要使用者提供參數？ | 有合理預設值嗎？ | 有 → 設預設值，使用者可覆蓋 |
| 前置條件可能不滿足？ | 能自動修正嗎？ | 能 → 自動修正 + 通知；不能 → 明確報錯，不靜默跳過 |
| 需寫「請先做 X」提醒？ | 能改成自動檢查？ | 能 → 改 Hook / pre-flight check；每個「請先」都是設計改善信號 |

**Why**：AI agent 沒有跨 session 記憶，工具即時引導是唯一可靠防線。文件說的和工具做的不一致時，工具會贏。

## 三類 bundled resource 的分工

| 類型 | 載入方式 | 何時用 | 範例 |
|------|---------|-------|------|
| `scripts/` | 可不讀直接執行（subprocess） | 同樣程式碼會被反覆寫；需要決定性結果 | `validate.py`、`init_skill.py`、`rotate_pdf.py` |
| `references/` | Claude `Read` 載入 context | 工作時需查的文件 / schema / 詳細範例 | `api-schema.md`、`patterns.md` |
| `assets/` | 不載入 context，被複製到輸出 | 產出物的素材 | `logo.png`、`template.pptx`、樣板專案目錄 |

**Why 區分這三類**：scripts 的價值是「跳過 context」，references 的價值是「按需載入」，assets 的價值是「不污染 context」。誤放會抵消設計。

---

## 按需讀取

本檔留下的是路由與判準——三層載入的預算、核心心法、三類 bundled resource 的分工、發布前的檢查清單。細節依你當下在做什麼取一份讀。

**涵蓋章節欄的字串與目標檔的 `##` 標題逐字相同，且雙向齊全**——每個名字都在目標檔存在（無死名），且目標檔的每個 `##` 都在這一欄出現（無孤兒節）。改任一目標檔的標題或新增節時，這一欄要同步。**兩個方向要各驗一次**：死名檢查抓的是指向虛無的指標，抓不到沒有指標的內容，單驗一邊必漏一類（實測：一次修法新增了一個 `##` 而只跑了死名檢查，該節無人指向而檢查全綠）。

| 何時讀 | 檔案 | 涵蓋章節 |
|--------|------|---------|
| 寫或修 frontmatter：name、description、擴展欄位、觸發控制、命名 | `references/frontmatter-and-description.md` | 〈YAML Frontmatter〉〈Description 寫作（最重要的一節）〉〈命名規則〉〈觸發控制矩陣〉 |
| 寫或修 SKILL.md 正文：骨架、內容品質、引用形式、什麼不該放 | `references/writing-the-body.md` | 〈嚴禁清單 — 什麼不該放進 Skill〉〈Body 寫作〉（含〈外部引用：指名身分，不用檔案路徑〉）〈Claude Code 特有功能〉〈一則完整走查：兩個判準只有一個附了可執行動作〉 |
| 從零建一個新 skill、判斷它屬哪一類型、或引入他人的 skill | `references/creating-and-adopting-skills.md` | 〈檔案結構〉〈Skill 建立流程〉〈Skill 類型速查〉〈安全考量〉 |
| 既有 skill 超出第 2 層預算、要外移內容 | `references/splitting-an-existing-skill.md` | 〈為什麼需要專屬程序〉〈拆分特有的必查項〉〈兩種驗證，方法不同〉〈拆分特有的高頻缺陷〉〈結構約定〉〈收尾〉〈一則最小走查〉〈相關〉 |
| 設計多步驟工作流、要進階範本、規劃測試方法、或 skill 行為不如預期 | `references/patterns-and-troubleshooting.md` | 〈Skill 設計模式〉〈選擇方法：Problem-first vs Tool-first〉〈測試方法〉〈迭代回饋指引〉〈常見問題排除〉 |
| 想理解工具設計哲學與 agent 視角的演進 | `references/seeing-like-an-agent.md` | 〈核心哲學〉〈Claude Code 團隊的演進教訓〉〈進階 Skill 設計模式〉〈觀察 Claude 如何使用 Skill〉〈反模式〉 |

**兩個近同名章節的消歧義**：〈Skill 設計模式〉（`patterns-and-troubleshooting.md`，五個可貼用的工作流範本）與〈進階 Skill 設計模式〉（`seeing-like-an-agent.md`，設計哲學層的六則模式）不是同一節。要範本去前者，要設計理由去後者。

## 發布前檢查清單

### 結構

- [ ] 資料夾 kebab-case（推薦 gerund）
- [ ] `SKILL.md` 大小寫正確
- [ ] 無 `README.md`（任何層級，含子目錄）
- [ ] 無 `INSTALLATION_GUIDE.md` / `QUICK_REFERENCE.md`（`CHANGELOG.md` 不在此列，見 `references/writing-the-body.md` 的〈嚴禁清單〉）
- [ ] SKILL.md body 通過兩個門檻（門檻值、量測指令與語言換算表見〈Progressive Disclosure — 三層載入〉）
- [ ] skill 帶 CLI 入口點時，另走 `skill-cli-sync-check` 規則。**不涵蓋**：本清單不問「CLI 行為變更後 SKILL.md 與 pm-rules 是否同步」，走完本清單全綠不代表那件事被問過

### YAML

- [ ] `---` 分隔符存在
- [ ] `name` kebab-case 且與資料夾同名
- [ ] `description` 第三人稱、< 250 **字元**、含觸發詞（量測指令見 `references/frontmatter-and-description.md`）
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
- [ ] **外部引用以身分指名，不寫檔案路徑**（見 `references/writing-the-body.md` 的〈外部引用：指名身分，不用檔案路徑〉）。機械檢查：`grep -nE '\`\.claude/[^\`]*\`' SKILL.md`，每個命中須屬該節列出的例外之一，逐一說明；說不出屬於哪一類就是該改。**不涵蓋**：裸檔名（`file-size-guardian-hook.py` 這種寫法不帶 `.claude/` 前綴，零命中），以及反引號後不是緊接 `.claude/` 的片段（`` `node .claude/…` `` 這種寫法同樣零命中）——兩類皆須人工核

### 觸發測試

**不涵蓋**：本組四項對走 git 同步的專案全部無可執行程序。前三項的做法落在 `references/patterns-and-troubleshooting.md`〈測試方法〉的 Manual 層，而該節載明 Manual 與 Programmatic 兩層在無上傳環節的專案裡沒有管道、Scripted 是唯一可用的一層而本檔未給程序；第四項的做法不在本 skill 任何一份檔案內。**勾選本組任一項目前只代表「已知有這件事」，不代表已驗證**——在補上程序之前，這一組不是閘門。

查詢的具體形態與判準仍可參考〈測試方法〉的觸發測試段（Should trigger / Should NOT trigger 範例）與〈迭代回饋指引〉（未觸發、過度觸發各自的修法）；description 側的診斷見 `references/frontmatter-and-description.md` 的〈觸發品質診斷〉。

- [ ] 主關鍵字觸發成功
- [ ] 改述查詢仍觸發
- [ ] 無關主題不觸發
- [ ] Haiku / Sonnet / Opus 行為一致 —— 跨模型比對的做法不在本 skill 任何一份檔案內，也未見於官方文件

---

版本紀錄在同目錄的 `CHANGELOG.md`。
