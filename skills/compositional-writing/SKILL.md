---
name: compositional-writing
description: "Composes atomic, intent-revealing, grep-friendly writing (Zettelkasten) for code comments, docs, logs, prompts, schema/ticket fields, and long-form technical articles. Use when cognitive load and token cost matter. Triggers: 寫註解, 寫文件, 寫日誌, 寫 prompt, 寫文章, 技術文章, post-mortem, 架構決策, 除錯復盤, 欄位設計, atomic, reusable."
license: MIT
metadata:
  version: 0.1.0
  category: writing-methodology
---

# Compositional Writing

以 Zettelkasten（卡片盒筆記法）為核心的寫作方法論。將每段文字視為可重複組合的原子卡片，讓人類讀者與 AI 代理人都能以最小認知負擔找到答案。

---

## Core Pillars（三大支柱）

| 支柱                         | 意義                                           |
| ---------------------------- | ---------------------------------------------- |
| **Atomization** 原子化       | 一段文字只承載一個概念，可獨立閱讀與重用       |
| **Explicit Intent** 意圖顯性 | 讀者第一眼就看懂「為什麼在這裡」與「該做什麼」 |
| **Searchability** 可查詢性   | 人和 AI 都能用關鍵字 / grep / regex 快速定位   |

---

## Six Principles（六大原則速查）

讀者能在本區塊完成快速複習；需要具體應用時，依下方「觸發路由」讀對應情境 reference。

### 1. 原子化（Atomization）

一張卡一個概念：能獨立理解、可跨情境重用。拆分依據是**認知負擔與情境匹配度**，不是行數。若讀者需要同時記住 7 個以上概念才能讀懂一張卡，必須再拆。

**拆分判準的核心問題**：「這張卡聚焦在什麼問題、有沒有議題切了一半？」— 不是「卡片之間有沒有衝突」、不是「邊界清不清晰」。兩張卡互不衝突也可能各切了一半同樣議題；一張卡邊界清晰也可能塞了兩個獨立議題。判準是 focus 完整度、不是邊界清晰度。

### 2. 索引建立（Indexing）

用 MOC（Map of Content）、tag 層級與反向索引把卡片串成可導航的網。入口文件只做路由，不承載細節；避免 A→B→C 的多層跳躍，引用最多一層深。

### 3. 意圖顯性與商業邏輯（Explicit Intent & Business Logic）

寫「為什麼」和「要達成什麼」，不寫「程式碼在做什麼」。避免 TODO / placeholder 當成說明；主詞與動詞直接，段落開頭即表達意圖。同一篇文字要貼合它在系統裡的抽象層級，不洩漏下層實作。

**機會成本語氣、不用絕對主義**：程式設計極少有絕對正確、討論的是多目標取捨。避免「正確概念是 X / 替代方案不足 / 應該這樣做」這種絕對二元語氣、改用「比較好的做法是 A、因為 [情境] / B 在 [其他情境] 合理 / D 的成本特別高、只在 [極端情境] 才划算」。絕對主義教讀者「規則」（壓力下會忘）、機會成本教讀者「思考方式」（能套用到新情境）。例外只限物理 / 法律事實（安全性、數據完整性、合規）。

**選項數由議題本身的合理選項數決定**：機會成本的精神是「教思考方式」 — 議題有幾個合理選項就寫幾個（2 個寫 A/B、3 個寫 A/B/C、4 個寫 A/B/C/D）。強湊到固定數量會產生「實務上幾乎不存在」的低品質假反模式、把「教思考」退化成「填格式」。真正的反模式直接標「D：反模式 — 違反 X 原則」、給讀者明確的「為什麼不該用」、不假裝有合理情境。

### 4. 可查詢性（Searchability）

關鍵字前置、使用可 grep 的分隔符（`:` `|` `→` `==`）、欄位名稱使用 regex 友善格式。命名讓 AI 能以單次 grep 命中，不需要語意推理。

### 5. 欄位設計（Field Design）

同一份文件的不同欄位，從不同角度觀察同一件事，不重複撰寫。`what` 描述動作、`why` 陳述動機、`acceptance` 定義可驗證條件；混淆欄位會讓讀者在多處讀到相同內容。

### 6. 多輪 Re-read Pass（Multi-pass Review）

寫完不是 done — 是進入 review 階段。一次寫對全部維度違反 working memory、實際結果是「每維度都做一半」。設計 N 輪 re-read、每輪用不同 frame：

| 輪  | Frame                                                                         | 抓什麼                                                  |
| --- | ----------------------------------------------------------------------------- | ------------------------------------------------------- |
| 1   | 生成                                                                          | idea → 字、預期會有錯                                   |
| 2   | 對意圖（[#67](references/principles/ease-of-writing-vs-intent-alignment.md)） | 跟原意對齊嗎、便利寫法偏移                              |
| 3   | 機會成本語氣                                                                  | 絕對主義詞翻成 trade-off（grep「應該/必須/不行/正確」） |
| 4   | Grep-ability / 命名                                                           | 關鍵字前置、AI 能單次 grep 命中                         |
| 5   | 反例 / 邊界                                                                   | 「何時不適用」段、反模式列表                            |

**核心**：「再仔細一次」≠ multi-pass — 同 frame 重看 catch 不到新問題。每輪換 frame、才能 catch 不同層。各 reference（writing-articles / writing-code-comments / writing-documents / writing-prompts）依 output 類型有特化的輪次組合。

Naming 是這條原則最容易跳的子場景 — 第一版命名幾乎不對、四輪 review（第一版 / grep / cross-call-site / impl 洩漏）才收斂、見 [#84](references/principles/naming-as-iterated-artifact.md) 跟 writing-code-comments 的 naming review 段。

詳見 [#83 Writing 的 multi-pass review](references/principles/writing-multi-pass-review.md)、[#85 Methodology 的 multi-pass 該 embed 在 pillar](references/principles/methodology-multi-pass-embedding.md)。

---

## When to Consult This Skill（觸發路由）

| 觸發情境                                                                                   | 讀哪份 reference                                                                                                   |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| 要寫或改一段程式碼註解 / doc comment                                                       | `references/writing-code-comments.md`                                                                              |
| 要起草 / 改寫一份文件（worklog、spec、README）                                             | `references/writing-documents.md`                                                                                  |
| 要設計 log / 錯誤訊息 / 結構化輸出                                                         | `references/writing-logs.md`                                                                                       |
| 要撰寫給 AI 的 prompt / instruction / Agent 派發 / Ticket Context Bundle                   | `references/writing-prompts.md`（為 `.claude/rules/core/ai-communication-rules.md` 的詳細版庫，portability-allow） |
| 要撰寫完整長篇技術文章（blog post / post-mortem / 架構決策 / 除錯復盤 / 技術評估）         | `references/writing-articles.md`                                                                                   |
| 要管理多篇相關文章的結構（系列、文集、知識庫、MOC、跨篇引用、何時抽抽象層 / Pattern 卡片） | `references/managing-article-collections.md`                                                                       |
| 要設計 ticket 欄位 / schema frontmatter / 表單欄位                                         | `references/designing-fields.md`                                                                                   |
| 想驗證寫作品質（認知負擔、獨立理解率）                                                     | `references/meta-metrics.md`                                                                                       |
| 要新增或修改一份 Skill reference（撰寫品質規範、結構標準）                                 | `references/reference-authoring-standards.md`                                                                      |
| 要驗收 Skill 發布品質（語意層驗收、Phase 2 dry-run）                                       | `references/dry-run-guide.md`                                                                                      |

每份 reference 自包含：以該情境為核心，把五大原則翻譯成可直接套用的檢查項與範例。閱讀任一 reference 不需要回來看其他 reference。

---

## Success Criteria（M1-M2 認知負擔類）

| Metric                        | 定義                                                  | 目標 |
| ----------------------------- | ----------------------------------------------------- | ---- |
| **M1 — 找到答案路徑**         | 讀者從 SKILL.md 出發，需要開啟幾個檔案才能解決問題    | ≤ 2  |
| **M2 — reference 獨立理解率** | 隨機挑一份 reference，不讀其他 reference 能否獨立套用 | 100% |

詳細量測方式與自評表見 `references/meta-metrics.md`。M3-M5（token 類）保留未定，待實際範例累積後補足。

---

## Directory Index

```text
compositional-writing/
├── SKILL.md                              # 本檔：五大原則速查 + 觸發路由
└── references/
    ├── writing-code-comments.md          # 情境 1：程式碼註解
    ├── writing-documents.md              # 情境 2：文件撰寫
    ├── writing-logs.md                   # 情境 3：log 輸出
    ├── writing-prompts.md                # 情境 4：prompt 撰寫
    ├── writing-articles.md               # 情境 5：完整長篇技術文章
    ├── managing-article-collections.md   # 情境 5b：跨多篇文章的結構（三層、MOC、Pattern 卡片）
    ├── designing-fields.md               # 情境 6：欄位設計（含六欄位角度總表）
    ├── designing-fields-ticket-6w.md     # 六欄位詳細範例：正確 + 混淆共 12 項（按需讀取）
    ├── meta-metrics.md                   # 品質量化驗收（M1-M5）
    ├── reference-authoring-standards.md  # Skill reference 撰寫品質規範
    └── dry-run-guide.md                  # Skill 發布前語意層驗收（Phase 2 dry-run 流程）
```

---

## Reading Order（建議閱讀順序）

1. 第一次接觸 → 從本 SKILL.md 的「三大支柱 + 五大原則」讀起
2. 進入實際寫作情境 → 依觸發路由讀對應 reference（只讀一份）
3. 想驗證成果 → 讀 `meta-metrics.md` 做自評

---

**Last Updated**: 2026-04-25
**Version**: 0.7.0 — Phase B1 結構升級：加第 6 原則「多輪 Re-read Pass」（明示 5 輪 frame）、引用 #83 / #84 / #85 multi-pass 系列。後續 Phase B2 會把各 reference 結尾加「第 2 輪 review checklist」段
**Version**: 0.6.0 — 從 references 過載的反思：writing-articles.md 從 780 行瘦身到 ~530 行（拆分判準 / 三類 structure 模板搬到 managing-article-collections.md、focus 集中在「單篇文章內部」）；新增規則八「自我應用 (dogfooding)」（教某條規則的段落本身遵守該規則）；managing-article-collections.md 整合「拆分判準」+「三層 structure 詳細對照 + 模板」；meta-metrics.md M2 加 dogfooding 失敗訊號
**Version**: 0.5.0 — 從批量改寫 35 篇的經驗回流：原則 3 補「選項數由議題決定、不強湊」（避免 A/B/C/D 強迫症與「實務上幾乎不存在」的假反模式）；writing-articles.md 新增規則九（三類文章 structure 模板）；managing-article-collections.md 新增「跨篇引用 idiom 庫」與「三層 structure 對照」
**Version**: 0.4.0 — 新增 `managing-article-collections.md`（跨多篇文章結構：三層、MOC、Pattern 卡片）；強化原則 1「原子化」（focus 是議題完整度、不是邊界清晰）；強化原則 3「意圖顯性」（機會成本語氣、不用絕對主義）
**Version**: 0.3.0 — 新增 `dry-run-guide.md` 於 Directory Index 與觸發路由（Skill 發布前語意層驗收 Phase 2 dry-run）
