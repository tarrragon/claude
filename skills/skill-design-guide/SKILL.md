---
name: skill-design-guide
description: "Anthropic skill spec plus this project's conventions: frontmatter, descriptions, loading budgets, and splitting an oversized skill. Use when creating a skill, editing SKILL.md, reviewing skill quality, or moving content into references/."
metadata:
  version: 1.9.0
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
| 刪掉這段，Claude 的預設輸出會變嗎？ | 會變 → 保留；不會 → 移除 |
| 這段文字值得它的 token 成本嗎？ | 表格 / 範例優於散文，散文優於不存在 |

**第一問問的是行為差異，不是知識空缺。** 「Claude 知不知道」與「Claude 預設會不會這樣做」是兩個獨立維度，四種組合都存在；把它們寫成一條線的兩端（通用知識 → 移除、專案特有 → 保留），「知道但預設不會做」那一格會被判成移除。本檔的 `wc -l` 與分段估算指令正落在該格——量測工具是通用程式知識，而 Claude 預設不會在寫 skill 前去量體量，它會憑印象判斷；刪掉那兩行，輸出會變。

**Action**：判不準時做刪除測試——把該段拿掉，在乾淨 session 對同一任務重跑，比對兩次產出。這一問可外部驗證，「Claude 知不知道」不能。

**Why**：兩層各有各的成本，機制不同，不可混談。**第 1 層**（description）常駐 system prompt，冗長會排擠其他 skill 的 description budget，讓自動觸發失敗——這是唯一會傷到別人的一層。**第 2 層**（body）只在本 skill 被觸發後載入，不影響他人；但它一旦載入就與對話歷史及其餘 context 競爭，冗長會壓縮讀者當下真正需要的空間。官方原文：「once Claude loads it, every token competes with conversation history and other context」。

### Progressive Disclosure — 三層載入

| 層 | 載入時機 | 預算 | 寫什麼 |
|----|---------|------|-------|
| 1. frontmatter（name + description） | 常駐 system prompt | 250 字元（唯一閘門，另兩個口徑不換算，見 `references/frontmatter-and-description.md` 的〈Description 寫作（最重要的一節）〉） | 何時觸發 + 做什麼 |
| 2. SKILL.md body | 觸發後載入 | < 5k tokens；另須符合官方 < 500 行 | 核心工作流 + 路由 |
| 3. references/ + scripts/ + assets/ | Claude 按需 read / exec | 目錄總量無上限；單檔判準見〈第 3 層的單檔判準是讀取方式〉 | 細節、範例、模板、可執行腳本 |

**這三個預算的適用對象各不相同，先認對象再量。** 第 2 層的兩個數字只管 `SKILL.md` body 這一個檔，因為它是觸發即載入、成本無條件支付的那一份；第 3 層的「無上限」講的是**目錄總量**——bundle 幾份 reference 都不預先付費，官方逐字寫 "no context penalty until accessed"——不是說單檔可以無限大。把「無上限」讀成單檔沒有判準，reference 會長成沒人讀得完的一份。

**Action**：第 2 層的主判準是分段 token 估算，直接與 5k 比較。

```bash
python3 -c "import sys;t=open(sys.argv[1],encoding='utf-8').read();a=sum(1 for c in t if ord(c)<128);print(round(a/4+(len(t)-a)/1.3),'tokens (est)')" .claude/skills/<name>/SKILL.md
wc -l .claude/skills/<name>/SKILL.md   # 官方 500 行，超標即須外移
```

**估算要分段加總，不是全檔比例內插。** token 數是各段落的和；把它算成全檔比例的內插判不出結論——落在兩個換算值之間即無答案，區間本身就是不判。

| 字元類別 | chars/token | 依據 |
|---------|------------|------|
| 非 ASCII（繁中） | 1.3 | `file-size-guardian-hook.py` 的 `CHARS_PER_TOKEN`，2026-06-12 以 `/context` 實測校準 |
| ASCII | 取 4 | **無實測**，一般 BPE 分詞落在 3–4；取寬鬆側的 4 會低估 token 數，誤差方向是放行而非誤擋。要收緊改填 3，並在此註明改動 |

分段法解掉單一字元門檻的兩類誤判：純 ASCII 檔在 6,500 字元門檻下判超標，分段法算出僅預算的 38%；混合內容套 6,500 判超標、套「取兩者之間」落在區間內判不出來。**任何寫在文件裡的量測值都是當時的**——執行 **Action** 的量測指令即得當下值。

超標時該外移什麼，判準見 `references/splitting-an-existing-skill.md` 的〈外移什麼、留什麼〉。它以「這段用在讀者選路之前還是之後」定位，**不以「一次只用其中一段」定位**——互斥性對本檔每一張判準表都成立，當不了外移訊號。同檔另有拆分程序：搬移正確不等於拆分後可用，兩者要用不同方法驗。

**行數是官方合規項，不是體量判準。** 官方 best-practices 三處重述 "Keep SKILL.md body under 500 lines"，故仍須量、仍須符合；但它不攜帶 token 資訊——每行字元數沒有上界，兩者在長行處脫鉤（一份實測：245 行通過門檻，卻是 ≈ 11.5k tokens、最長單行 548 字）。**兩個都量、取較嚴者；行數通過不代表體量合格，只代表官方那一項沒違反。**

**第 3 層的單檔判準是讀取方式，不是行數。** 判別依據是〈按需讀取〉路由表那一列的措辭：明令「讀這一份再繼續」者為整份執行，其餘為選段查閱（本 skill 六份現況皆為後者）。

| 讀取方式 | 量什麼 | 門檻 |
|---------|-------|------|
| 整份執行 | 全檔分段估算 | 5k tokens——它與 SKILL.md 一樣是整份進 context |
| 選段查閱 | 最大單節的分段估算 | 5k tokens |

這與 `references/writing-the-body.md`〈Body 寫作〉裡「決定要不要 TOC 的是讀取方式、行數只是成本」是同一個維度，不是新增判準：要不要 TOC 與該量什麼，答案由同一件事決定。

**Consequence**：本層目前**無 hook 執法**——`file-size-guardian-hook.py` 的 `SCAN_CONFIG` 涵蓋 pm-rules / rules / references 三處，不含 `.claude/skills/`；`skill-description-length-check-hook.py` 只查第 1 層的 description（250 字元）。第 2 層判準完全依賴撰寫者自查，寫錯代理指標即等同無判準。

### 表達方式與預設值：兩則心法住在 reference

自由度三級（高／中／低，判準為「有無機械消費者、產物要不要彙總」）與 opinionated default（預設路徑要引導正確做法）都只在**設計工作流的表達方式時**用得到，見 `references/patterns-and-troubleshooting.md` 的〈Degrees of Freedom — 自由度匹配脆弱性〉〈Opinionated Defaults — 預設路徑引導正確做法〉。

---

## 按需讀取

本檔留下的是路由與判準——三層載入的預算、判斷內容去留的兩問、發布前的檢查清單。細節依你當下在做什麼取一份讀。

**涵蓋章節欄的字串與目標檔的 `##` 標題逐字相同，且雙向齊全**——每個名字都在目標檔存在（無死名），且目標檔的每個 `##` 都在這一欄出現（無孤兒節）。改任一目標檔的標題或新增節時，這一欄要同步。**兩個方向要各驗一次**：死名檢查抓的是指向虛無的指標，抓不到沒有指標的內容，單驗一邊必漏一類（實測：一次修法新增了一個 `##` 而只跑了死名檢查，該節無人指向而檢查全綠）。

| 何時讀 | 檔案 | 涵蓋章節 |
|--------|------|---------|
| 寫或修 frontmatter：name、description、擴展欄位、觸發控制、命名 | `references/frontmatter-and-description.md` | 〈YAML Frontmatter〉〈Description 寫作（最重要的一節）〉〈命名規則〉〈觸發控制矩陣〉 |
| 寫或修 SKILL.md 正文：骨架、內容品質、引用形式、什麼不該放 | `references/writing-the-body.md` | 〈嚴禁清單 — 什麼不該放進 Skill〉〈Body 寫作〉（含〈外部引用：指名身分，不用檔案路徑〉）〈Claude Code 特有功能〉〈一則完整走查：兩個判準只有一個附了可執行動作〉 |
| 從零建一個新 skill、判斷它屬哪一類型、決定內容該放 `scripts/`／`references/`／`assets/`、要廢止或遷移既有 skill、或引入他人的 skill | `references/creating-and-adopting-skills.md` | 〈檔案結構〉〈三類 bundled resource 的分工〉〈Skill 建立流程〉〈Skill 類型速查〉〈廢止與遷移〉〈安全考量〉 |
| 既有 skill 超出第 2 層預算、要外移內容 | `references/splitting-an-existing-skill.md` | 〈為什麼需要專屬程序〉〈外移什麼、留什麼〉〈拆分特有的必查項〉〈兩種驗證，方法不同〉〈拆分特有的高頻缺陷〉〈結構約定〉〈收尾〉〈一則最小走查〉〈相關〉 |
| 決定工作流該給多少自由度或要不要設預設值、設計多步驟工作流、要進階範本、規劃測試方法、或 skill 行為不如預期 | `references/patterns-and-troubleshooting.md` | 〈Degrees of Freedom — 自由度匹配脆弱性〉〈Opinionated Defaults — 預設路徑引導正確做法〉〈Skill 設計模式〉〈選擇方法：Problem-first vs Tool-first〉〈測試方法〉〈迭代回饋指引〉〈常見問題排除〉 |
| 想理解工具設計哲學與 agent 視角的演進 | `references/seeing-like-an-agent.md` | 〈核心哲學〉〈Claude Code 團隊的演進教訓〉〈進階 Skill 設計模式〉〈觀察 Claude 如何使用 Skill〉〈反模式〉 |

**兩個近同名章節的消歧義**：〈Skill 設計模式〉（`patterns-and-troubleshooting.md`，五個可貼用的工作流範本）與〈進階 Skill 設計模式〉（`seeing-like-an-agent.md`，設計哲學層的六則模式）不是同一節。要範本去前者，要設計理由去後者。

## 發布前檢查清單

### 結構

- [ ] 資料夾 kebab-case（推薦 gerund）
- [ ] `SKILL.md` 大小寫正確
- [ ] 無 `README.md`（任何層級，含子目錄）
- [ ] 無 `INSTALLATION_GUIDE.md` / `QUICK_REFERENCE.md`（`CHANGELOG.md` 不在此列，見 `references/writing-the-body.md` 的〈嚴禁清單〉）
- [ ] SKILL.md body 通過兩個門檻（5k tokens 與 500 行）；各 reference 通過第 3 層的單檔判準。門檻的適用對象、量測指令與分段估算表見〈Progressive Disclosure — 三層載入〉
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
- [ ] 每份 reference 一跳可達（判準與例外見 `references/writing-the-body.md` 的〈Body 寫作〉）。機械檢查：下列指令列出「在 reference 裡出現、但入口路由表沒有」的檔名，每個命中須逐一判定——說明用的示意路徑與被討論的對象不算違規，其餘即是（本 skill 現況命中 3 個，皆為示意路徑）

```bash
# 在該 skill 的目錄下執行
LC_ALL=C comm -13 <(grep -o 'references/[a-z-]*\.md' SKILL.md | LC_ALL=C sort -u) \
                  <(grep -rho 'references/[a-z-]*\.md' references/ | LC_ALL=C sort -u)
```

- [ ] 100+ 行**且被選段查閱**的 reference 有 TOC（整份執行者不適用，理由見 `references/writing-the-body.md` 的〈Body 寫作〉；同一個讀取方式維度也決定第 3 層量什麼）
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
