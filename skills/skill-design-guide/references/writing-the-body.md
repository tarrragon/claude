# 嚴禁清單 / Body 寫作 / Claude Code 特有功能 / 一則完整走查

> 何時讀：寫或修 SKILL.md 正文時——骨架、內容品質、什麼不該放進去、引用形式（skill 內用相對路徑、指向外部用指名身分）、字串替換與動態 context 注入。**亦由此進入**——`SKILL.md`〈發布前檢查清單〉的「結構」與「Body」兩組（尤其外部引用的機械檢查）；`creating-and-adopting-skills.md`〈Step 4：撰寫內容〉的 4c（寫 body）；`splitting-an-existing-skill.md` 的結構約定（拆完要照本檔的引用規則重寫指標）。
>
> 同目錄：frontmatter 與 description 在 `frontmatter-and-description.md`，新建流程與三類 bundled resource 的分工在 `creating-and-adopting-skills.md`，拆分程序在 `splitting-an-existing-skill.md`，工作流範本、自由度與預設值、問題排除在 `patterns-and-troubleshooting.md`，設計哲學在 `seeing-like-an-agent.md`；〈核心心法〉的前兩則與〈發布前檢查清單〉留在 `SKILL.md`。
>
> 溯源：自 SKILL.md 搬移（v1.6.0，因兩個官方門檻皆超標）。

本檔章節：〈嚴禁清單 — 什麼不該放進 Skill〉〈Body 寫作〉（內含〈外部引用：指名身分，不用檔案路徑〉）〈Claude Code 特有功能〉〈一則完整走查：兩個判準只有一個附了可執行動作〉。

## 嚴禁清單 — 什麼不該放進 Skill

> **核心原則**：Skill 只放 AI agent 執行任務需要的東西，不放給人看的後設資訊。

### 禁止的檔案

| 禁止檔案 | 為何禁止 | 替代方案 |
|---------|---------|---------|
| `README.md`（任何層級，含 `references/` 子目錄） | 給人看的入口；AI 經 SKILL.md 進入，README 只是冗餘 | 資料夾用途透過檔名自說明，或在 SKILL.md「參考文件」段落索引 |
| `INSTALLATION_GUIDE.md` | 安裝是平台職責，非 skill 工作 | 放專案根目錄文件 |
| `QUICK_REFERENCE.md` | 與 SKILL.md 必有重複 | 直接寫進 SKILL.md 或 reference 檔 |
| `CHANGELOG.md` | **本專案不禁止**——見下方查證段 | 保留；版號協定見專案的 skill 同步規範 |
| 設計過程紀錄 / 測試報告 | 開發 artifact，非 runtime 需要 | 放專案 worklog 系統 |

**Why**：SKILL.md 是 Claude 進入 skill 的唯一入口，與它平行的檔案若無路由訊號就不會被讀到，卻仍佔目錄的辨識成本；給人看而 AI 不會讀的文件屬此類。

**本表的官方依據到哪為止（2026-09-04 查證）**：官方 best-practices **未禁止**任何額外檔案，且明文相反——「Reference files, data, or documentation don't consume context tokens until actually read」「Bundle comprehensive resources: include complete API docs, extensive examples, large datasets; no context penalty until accessed」；其示範目錄即為 `SKILL.md` 與 `FORMS.md`／`reference.md`／`examples.md` 平鋪。故本表是**本地判斷**，理由是目錄辨識成本而非 context 成本，且僅對「AI 不會讀到的檔案」成立。

`CHANGELOG.md` 因此不在禁止之列：本專案的 skill 走 git 同步、有跨 consumer 版號協定（版號有兩個住址——CHANGELOG 首條與 frontmatter 的 `metadata.version`），它是該協定的載體而非給人看的附錄。本庫的 skill 一律帶著它，缺漏由 `skill-residue-check-hook.py` 在 SessionStart 掃出。

### 禁止的內容

| 禁止內容 | 為何禁止 |
|---------|---------|
| SKILL.md 內「When to Use This Skill」段落 | 觸發判斷靠 description（已在 system prompt），body 寫一次無效 |
| 時間敏感資訊（「2025 年 8 月前用舊 API」） | 改成「old patterns」段落。**禁的是效力有期限的內容，不是內容有時間戳**——標記查證時點的括號註（「（YYYY-MM-DD 查證）」）、檔尾 `Last Updated`、以及年份本身就是所指之一部分者（「2023-era kicker」）皆不在此列 |
| 同一資訊同時放 SKILL.md 與 reference | 重複會稀釋 grep 命中率；資訊只放一處 |

---

## Body 寫作

### SKILL.md 推薦骨架

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

### 內容品質規則

| 規則 | 反例 → 正例 |
|------|------------|
| 具體可操作 | `Validate the data before proceeding.` → `Run python scripts/validate.py --input {filename}. If exit code != 0, see references/errors.md` |  <!-- skill-residue-exempt: 範例情境的示意路徑，非本專案實際檔案 -->
| 包含錯誤處理 | （只寫成功路徑） → 額外加 `## Common Issues` 段 |
| 重要指令前置 | 散落在中段 → 用 `## Important` / `## Critical` 標題 + 必要時重複 |
| 一致術語 | 混用「endpoint / URL / route」 → 全 skill 統一一個詞 |
| MCP 工具完整名稱 | `tool_name` → `ServerName:tool_name` |
| 避免模糊語言 | `Make sure to validate things properly` → `CRITICAL: Before X, verify A, B, C` |
| **不涵蓋的告示用固定前綴** | 五種寫法散落各處 → 一律以 `**不涵蓋**：` 起手 |
| 禁用詞（language-constraints.md 規則 2） | 「文檔」「數據」「默認」等 → 「文件」「資料」「預設」；`skill-banned-term-scan-hook.py` 對 `skill-sync` pull 後的用語回歸做掃描 |

**「不涵蓋」的告示要能被清點。** 一份檢查清單或一道機械檢查有射程之外的東西時，必須明寫，否則讀者會把「走完全綠」讀成「已驗證」。而這類告示是修法過程中新增最多的一類內容——實測一份 skill 的四批修法共新增 5 處，**用了五種不同形式**（checkbox 內粗體、checkbox 內句尾、組層級獨立段、粗體標籤加表格新欄、表前單行），沒有共同字串，因此**既無法 grep 清點、讀者也建立不起辨識模式**，其中藏在八項清單第八項句尾的那則最容易漏讀。固定前綴讓 `grep -rn '不涵蓋'` 一次列出全部射程缺口。

### references/ 引用規則

| 規則 | 說明 |
|------|------|
| 一跳可達 | 每份 reference 在 SKILL.md 路由表都有自己的一列，讀者從入口一跳即到。**禁止的是「只能經由另一份 reference 才被發現的內容」，不是 reference 之間互相指路** |
| 路由訊號 | SKILL.md 必說明「什麼情境讀此檔」，否則 reference 形同孤兒 |
| 100+ 行且**被選段查閱**者加 TOC | 讓 Claude preview 時看到完整範圍。**被整份執行的 reference 不適用**——SKILL.md 明令「讀這一份再繼續」的那種，反正從頭讀到尾，目錄省不下東西。行數只是成本，決定要不要 TOC 的是讀取方式（實測同一條判準在兩支 skill 上判出相反結果：一支 25 份誤報、一支 8 份真違規，差別只在這個維度） |
| 不重複 | 內容只放 SKILL.md 或 reference 之一，不兩處皆有 |

**為何是「一跳可達」而不是「禁止 A → B」。** 後者對本 skill 的六份 reference 全數判違規——每一份的檔頭都列了同目錄的其他五份，而那正是 `splitting-an-existing-skill.md`〈結構約定〉要求的產物。一條被自己的規範強制違反的規則不會被遵守，它只是讓真正的違規藏在六個偽陽性裡。

一跳可達把判準移到**讀者的最短路徑**上，於是檔頭的「同目錄」與「亦由此進入」不再是違規：它們是橫向索引，指向的目標同樣在入口路由表裡，讀者要到那裡不必經過這一份。而某份 reference 若指到一個路由表沒有的檔案，那個檔案就只有經由它才會被發現，判違規——這才是原規則想擋的東西。機械檢查與判定方式見 `SKILL.md`〈發布前檢查清單〉的 Body 組。

> **skill 自身目錄內的 reference 用相對路徑**（`references/foo.md`），這是本表的適用範圍。**指向 skill 外部的東西見〈外部引用：指名身分，不用檔案路徑〉。**

### 外部引用：指名身分，不用檔案路徑

**要讀的資料一律以身分指名，不寫檔案路徑。**

| 引用對象 | 寫法 | 讀者如何取得 |
|---------|------|------------|
| 另一個 skill | `` `tdd` skill ``、`` `compositional-writing` skill 的字句層 keyword bank `` | Skill 工具以名字載入。指到某一節時，該節須在對方 SKILL.md 的路由中可被找到——否則讀者只能掃目錄，正是本節要取代的行為 |
| 方法論 | 元件庫雙向約束方法論 | 以標題檢索 |
| 規則 | 可觀測性規則、決策 trigger 綁定規則 | 以標題檢索 |

**Why**：路徑是「它現在放在哪」，名字是「它是什麼」。路徑會因框架改版而失效——實證：某次改版把 hook 自 `.claude/hooks/` 移入 `.claude/skills/<name>/hooks/`，所有以舊路徑註冊者全數失效。更根本的是機制錯配：skill 在本系統以名字載入，寫路徑等於叫讀者 cat 檔案，繞過既有載入機制。

**Consequence**：除了改版即斷，還會觸發 `skill-sync` 的可攜性閘門——宣告 `metadata.portable: true` 的 skill 若指名 `.claude/...` 路徑，push 會被中止並列出全部命中處（實證：兩份 skill 累計 25 處，被判為「指名他專案的檔案」）。

**Action**：寫外部引用前先問這一句，**它是主判準，底下的例外只是它的舉例**——

> **這個路徑指向的是「它要操作的東西」，還是「讀者要去讀的東西」？** 前者合規，後者違規。

| 答案 | 形式 | 例 |
|------|------|-----|
| 它要操作的東西 | 保留檔名與欄位名（**介面規格**） | 「依賴回填至 `docs/proposals-tracking.yaml` 的 `depends_on`，下游檢查器讀該欄位」 |
| 讀者要去讀的東西 | 指名身分 | 「判準見 `tdd` skill 的分層測試策略」 |

**先用這一問判，判不了才查下列例外。** 實測一支 skill 的 24 個 `.claude/` 命中裡，**這一問一次判定了 23 個**；而把例外清單放在問句之前，會讓判定者先去比對四個類別、比對不上才回頭想問句。

**以下例外，路徑是正當的**（同時命中多類時取義務較嚴者）：

1. **框架綁定工具講自己的主題**：`.claude/` 路徑就是該 skill 的操作對象而非閱讀材料時。判準是**它對那個路徑做什麼**——讀寫該路徑下的檔案是它的功能本身，而不是叫讀者去讀那個檔。不列具名清單：成員資格會與成員自述脫節（實測有一份 skill 的 SKILL.md 自稱 `zero framework dependencies and works in any project`，而它同時是任何一份具名清單都會收的成員）。
2. **介面規格**：下游程式讀特定檔案的特定欄位時，泛稱會使契約不可驗證。此類須在鄰近處標明它是本框架的位置慣例、不是契約本身。
3. **路徑本身即被討論的對象**：如本節引述「hook 自 `.claude/hooks/` 移入⋯⋯」作為失效實證。此時路徑是舉例的內容，不是指向要讀的東西。
4. **hook 與 script 的溯源引用**：這類東西無法以名字載入（沒有 Skill 工具可用、也沒有標題可檢索），路徑是唯一可行的指名方式。寫路徑時給檔名即可，不必寫全路徑——`file-size-guardian-hook.py` 比 `.claude/hooks/file-size-guardian-hook.py` 更耐搬移。

5. **skill 內相對路徑補足前綴後的結果**：依下一段的規則把 `` `references/foo.md` `` 補成完整路徑時，產生的 `.claude/…` 寫法屬本類，不必再歸入前四類。**這一條是為了讓遵守下一段規則的產物不會被〈發布前檢查清單〉的機械檢查判為「說不出屬於哪一類」。**

**skill 內相對路徑與外部路徑同形時，一律補足前綴。** `` `references/foo.md` `` 這種寫法在本 skill 目錄內指自己的 reference（合規），指到別的地方時則是斷掉的路徑——而**兩者字面完全相同**，讀者與機械檢查都分不出來（實測一份 skill 的 SKILL.md 寫 `` `references/agent-dispatch-template.md` ``，該檔實住 `.claude/references/`，而檢查清單的 grep 因為它不帶 `.claude/` 前綴也抓不到）。規則：**指自己目錄內的 reference 才可用裸相對路徑，其餘一律寫完整路徑或改指名**。

> 本節條文寫成後隨即套回本文件自身，抓到三處違規（Opinionated Defaults 的詳細版路由、延伸閱讀表兩列），已改為指名。**寫完條文與用條文掃過自己是兩個動作**，`SKILL.md`〈發布前檢查清單〉的機械檢查即為此而設。
>
> **但這一次的自我套用只跑了本節這一條規則。** 後續審查在同一份文件裡另抓到多處違反**其他**條文的地方（本節起手句原寫「三類例外」而底下實列四項、本檔 100+ 行卻無 TOC）。自我套用的單位不是「我剛寫的那一條」，是**這份文件的全部條文 × 這份文件的全部內容**；留下一句自我套用的宣告，會讓後續審查不再查這一節，其餘條文對它的違規因此拿到永久豁免。

## Claude Code 特有功能

### 字串替換

| 變數 | 說明 | 範例 |
|------|------|------|
| `$ARGUMENTS` | 全部傳入參數 | `/fix-issue 123` → `$ARGUMENTS = "123"` |
| `$ARGUMENTS[N]` | 第 N 個（0-based） | `$ARGUMENTS[0]` 第一個 |
| `$N` | `$ARGUMENTS[N]` 簡寫 | `$0` 第一個 |

若 SKILL.md 沒寫 `$ARGUMENTS`，參數自動附加為 `ARGUMENTS: <value>`。

### 動態 context 注入（pre-process）

`` !`command` `` 在 skill 載入前執行 shell，Claude 只看到結果：

```markdown
## Pull request context

- PR diff: !`gh pr diff`
- Changed files: !`gh pr diff --name-only`
```

## 一則完整走查：兩個判準只有一個附了可執行動作

本節與〈Claude Code 特有功能〉無關，示範的是把 `patterns-and-troubleshooting.md`〈Opinionated Defaults — 預設路徑引導正確做法〉那張判準表套到一段既有條文上。對象是本 skill 自己的體量門檻。

| 階段 | 內容 |
|------|------|
| 原設計 | 表列兩個判準「< 5k tokens（< 500 行）」，Action 寫「超過 500 行就外移」 |
| 套「有沒有多數情況下正確的路徑」這一問 | 有——多數 skill 是繁中，行數對它失效 |
| 套「能不能改成自動檢查」這一問 | 部分——`wc` 可量，但語言比例要人判 |
| 實際發生 | Action 只綁了行數，於是**只有行數生效**；一份 245 行、15,015 字元的 skill 全程通過 |
| 改後設計（第一次） | 兩個門檻都量、都給指令；字元門檻附語言換算表；並在條文中載明「本層無 hook 執法，依賴自查」 |
| 補完動作之後才暴露的問題 | 兩個門檻以「任一超標即外移」合併，於是**較嚴的那個永遠是實際生效的閘門**。對英文內容而言較嚴的是行數，而行數不量測任何體量——沉默的判準補上動作後，反而變成主導的 |
| 改後設計（第二次） | 主判準改為分段 token 估算直接比 5k，行數降為官方合規項；第 3 層補上單檔判準 |

這一則的教訓可一般化：**當兩個判準只有一個附了可執行動作，實際生效的永遠是有動作的那個**——而寫的人會以為兩個都在跑。

**而補上動作不是終點，還要回頭問合併規則。** 上表第一次修法只做了前半：兩個判準都有動作之後，沒有人問過「兩個都在跑時，誰說了算」。合併規則若是 OR（任一超標即外移），生效的就永遠是較嚴的那個，另一個等於沒有；失效的判準從沉默變成主導，而外觀上兩個都在跑。**修法清單裡凡是「補上缺的那一半」，都要接著問補完之後兩半怎麼合。**

> 完整論證、案例、反模式對照表見 Opinionated Default 設計原則的詳細版；通用設計原則見同名的速查規則。
