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

| 支柱 | 意義 |
|------|------|
| **Atomization** 原子化 | 一段文字只承載一個概念，可獨立閱讀與重用 |
| **Explicit Intent** 意圖顯性 | 讀者第一眼就看懂「為什麼在這裡」與「該做什麼」 |
| **Searchability** 可查詢性 | 人和 AI 都能用關鍵字 / grep / regex 快速定位 |

---

## Five Principles（五大原則速查）

讀者能在本區塊完成快速複習；需要具體應用時，依下方「觸發路由」讀對應情境 reference。

### 1. 原子化（Atomization）

一張卡一個概念：能獨立理解、可跨情境重用。拆分依據是**認知負擔與情境匹配度**，不是行數。若讀者需要同時記住 7 個以上概念才能讀懂一張卡，必須再拆。

### 2. 索引建立（Indexing）

用 MOC（Map of Content）、tag 層級與反向索引把卡片串成可導航的網。入口文件只做路由，不承載細節；避免 A→B→C 的多層跳躍，引用最多一層深。

### 3. 意圖顯性與商業邏輯（Explicit Intent & Business Logic）

寫「為什麼」和「要達成什麼」，不寫「程式碼在做什麼」。避免 TODO / placeholder 當成說明；主詞與動詞直接，段落開頭即表達意圖。同一篇文字要貼合它在系統裡的抽象層級，不洩漏下層實作。

### 4. 可查詢性（Searchability）

關鍵字前置、使用可 grep 的分隔符（`:` `|` `→` `==`）、欄位名稱使用 regex 友善格式。命名讓 AI 能以單次 grep 命中，不需要語意推理。

### 5. 欄位設計（Field Design）

同一份文件的不同欄位，從不同角度觀察同一件事，不重複撰寫。`what` 描述動作、`why` 陳述動機、`acceptance` 定義可驗證條件；混淆欄位會讓讀者在多處讀到相同內容。

---

## When to Consult This Skill（觸發路由）

| 觸發情境 | 讀哪份 reference |
|---------|----------------|
| 要寫或改一段程式碼註解 / doc comment | `references/writing-code-comments.md` |
| 要起草 / 改寫一份文件（worklog、spec、README） | `references/writing-documents.md` |
| 要設計 log / 錯誤訊息 / 結構化輸出 | `references/writing-logs.md` |
| 要撰寫給 AI 的 prompt / instruction / Agent 派發 / Ticket Context Bundle | `references/writing-prompts.md`（為 `.claude/rules/core/ai-communication-rules.md` 的詳細版庫，portability-allow） |
| 要撰寫完整長篇技術文章（blog post / post-mortem / 架構決策 / 除錯復盤 / 技術評估） | `references/writing-articles.md` |
| 要設計 ticket 欄位 / schema frontmatter / 表單欄位 | `references/designing-fields.md` |
| 想驗證寫作品質（認知負擔、獨立理解率） | `references/meta-metrics.md` |
| 要新增或修改一份 Skill reference（撰寫品質規範、結構標準） | `references/reference-authoring-standards.md` |
| 要驗收 Skill 發布品質（語意層驗收、Phase 2 dry-run） | `references/dry-run-guide.md` |

每份 reference 自包含：以該情境為核心，把五大原則翻譯成可直接套用的檢查項與範例。閱讀任一 reference 不需要回來看其他 reference。

---

## Success Criteria（M1-M2 認知負擔類）

| Metric | 定義 | 目標 |
|--------|------|------|
| **M1 — 找到答案路徑** | 讀者從 SKILL.md 出發，需要開啟幾個檔案才能解決問題 | ≤ 2 |
| **M2 — reference 獨立理解率** | 隨機挑一份 reference，不讀其他 reference 能否獨立套用 | 100% |

詳細量測方式與自評表見 `references/meta-metrics.md`。M3-M5（token 類）保留未定，待實際範例累積後補足。

---

## Directory Index

```
compositional-writing/
├── SKILL.md                              # 本檔：五大原則速查 + 觸發路由
└── references/
    ├── writing-code-comments.md          # 情境 1：程式碼註解
    ├── writing-documents.md              # 情境 2：文件撰寫
    ├── writing-logs.md                   # 情境 3：log 輸出
    ├── writing-prompts.md                # 情境 4：prompt 撰寫
    ├── writing-articles.md               # 情境 5：完整長篇技術文章
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

**Last Updated**: 2026-04-18
**Version**: 0.3.0 — 新增 `dry-run-guide.md` 於 Directory Index 與觸發路由（Skill 發布前語意層驗收 Phase 2 dry-run）
