# 搜尋引擎的匹配模式跟使用者預期的對齊

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 SKILL.md「相關抽象層原則」段（#73）引用、是 search feature 在 capability 維度上的對齊判準。
>
> **何時讀**：當需求涉及搜尋 / filter / lookup 功能、或使用者報「我搜 X 找不到、但是有 X」這類疑似 silent 失敗時。讀本卡跑識別三問、確認工具預設 matching mode 是否跟使用者預期對齊。

---

## 核心原則

**搜尋引擎的「匹配模式」是個經常被忽略的維度** — 工具的預設行為跟使用者的 mental model 不對齊時、產生 silent 失敗：使用者打字、看不到預期結果、誤以為「沒有」、不會 report bug。

| 匹配模式  | 例：query「pre」會匹配                  | 典型來源                     |
| --------- | --------------------------------------- | ---------------------------- |
| Exact     | `pre`（不含「pre」這個 token）          | DB `=` 比較                  |
| Prefix    | `pre`、`prefix`、`prefetch`、`presence` | 多數 static site search 預設 |
| Substring | 上面 + `backpressure`、`SuperPress`     | DB `LIKE '%pre%'`            |
| Fuzzy     | 上面 + `prv`、`pre1`（編輯距離）        | Algolia、TypeSense           |
| Semantic  | 上面 + `before`、`prior`（語意相近）    | Vector search / LLM          |

使用者被 Google / 桌面搜尋訓練、預期 **substring 或更高層級**。預設拿到 prefix 的 site search → 「pre」找不到 backpressure → 看起來像 bug 但其實是 capability 落差。

---

## 為什麼預設是 prefix

Static site search engines 多半選 prefix matching、原因：

| 因素        | Prefix     | Substring                  |
| ----------- | ---------- | -------------------------- |
| Index size  | O(N)       | O(N²)（要 index 所有後綴） |
| Query speed | 快（trie） | 慢（全掃 substring）       |
| 跨語言支援  | 容易       | 中文 / CJK 邊界不明確      |
| Build time  | 快         | 慢                         |

對 static site（沒 server）、index 是要下載到 client 的 — substring index 可能 5-10x 大、unacceptable。多數 static search 引擎選 prefix 是「對齊 size constraint」、不是「對齊使用者意圖」。

這是個典型的 [寫作便利度跟意圖對齊反相關](./ease-of-writing-vs-intent-alignment.md) — 工具預設是「實作便利位置」、不是「使用者意圖位置」。

---

## 為什麼這個 gap 是 silent

跟 Filter × Source 層錯位共用結構：使用者打字看到結果列表、結果不空、看起來「有東西」、不會懷疑 engine 沒在做完整 search。

silent 失敗的條件：

1. Prefix matching 對某些 query 仍能回到結果（排版上看起來「有用」）
2. 使用者不知道「沒看到的還有什麼」
3. 只有當 query 剛好不是任何 token 的 prefix、才會 0 結果（極少見、這時才會懷疑）

這跟 silent 失敗的通用三條件結構相同：「有部分結果掩蓋了缺口」。

---

## 多面向：跨工具的匹配模式對照

### 前端 client-side search

| 工具          | 預設匹配模式  | 可調整為                                 |
| ------------- | ------------- | ---------------------------------------- |
| Pagefind v1.5 | Word-prefix   | Exact only（`useExact`）                 |
| Lunr          | Stem + prefix | Wildcard（`q+'*'`）                      |
| MiniSearch    | Prefix        | Substring（`prefix: false, fuzzy: 0.2`） |
| FlexSearch    | Token-based   | 多種 tokenizer（含 ngram）               |
| Fuse.js       | Fuzzy         | 可關掉 fuzzy 變 substring                |

### Backend / DB

| 工具                     | 匹配模式                                       |
| ------------------------ | ---------------------------------------------- |
| SQL `=`                  | Exact                                          |
| SQL `LIKE '%X%'`         | Substring（O(n) scan）                         |
| SQL FULLTEXT             | Token + stem + (有時 prefix)                   |
| ElasticSearch            | 配置：term / match / wildcard / fuzzy / regexp |
| PostgreSQL trigram       | Substring + similarity                         |
| Vector DB（Pinecone 等） | Semantic                                       |

### 命令列 / IDE 搜尋

| 工具        | 預設                              |
| ----------- | --------------------------------- |
| `grep`      | Substring（regex）                |
| `rg`        | Substring（smart-case + regex）   |
| Vim `/`     | Regex                             |
| VSCode 搜尋 | Substring（含 fuzzy file search） |

**共通結構**：每個工具預設不同、使用者帶著舊工具的 expectation 來、不對齊時 silent 失敗。

---

## 識別三問

寫之前 / debug 時、自問：

### 1. 這個工具的預設匹配模式是什麼？

讀 docs、不要假設。許多 static search 工具 docs 會寫類似 "matches by word prefix" 的字眼。**預設不是直覺**。

### 2. 使用者預期哪種匹配模式？

使用者被別的工具訓練。使用者基數越大、越接近 Google substring + fuzzy 預期。

| 使用者類型                   | 預期匹配模式                 |
| ---------------------------- | ---------------------------- |
| 一般使用者（被 Google 訓練） | Substring + fuzzy + semantic |
| 開發者（用 grep / IDE）      | Substring + regex            |
| 資料庫使用者（寫 SQL）       | 看你給的 hint                |
| 命令列重度使用者             | 預設 regex                   |

### 3. Gap 多大？是否 silent？

工具預設 vs 使用者預期不一致時、評估「使用者會在多少 case 中遇到不一致」。

- Prefix vs Substring：使用者只要打詞中間部分就 silent 失敗、頻率高
- Prefix vs Fuzzy：使用者打錯字才會發現、頻率低
- Substring vs Semantic：使用者用同義詞才會發現、頻率中

頻率高的 gap 必須有對策。

---

## 五種對策（跟 [Filter × Source 五策略](./filter-source-composition-strategies.md) 同構）

### A：選用支援目標匹配模式的引擎

不支援 substring 的引擎 → 換支援的（如 MiniSearch / FlexSearch）。不支援 fuzzy 的 → 換 FlexSearch / Fuse.js。

- **適合**：早期決策、index size 不是 bottleneck、能接受工程量
- **代價**：換引擎成本（API 不同、index 重建、UI 重整合）

### B：在 build time pre-tokenize、增加替代 token

在 build pipeline 拆字、把 `backpressure` 加進 search index 的多個 token：`back` + `pressure` + `backpressure` + `back-pressure`。可透過引擎提供的 metadata 機制或多份 hidden text 注入。

- **適合**：少量已知關鍵詞 / 跨語言邊界（中文）/ 能控 build pipeline
- **代價**：手動標記、index 變大、新詞要加進清單

### C：Client-side fallback substring search

主引擎找不到時、fetch 一份頁面 metadata（title + slug）、做 client-side substring filter。

- **適合**：頁面數量 < 10000、可接受第二層延遲
- **代價**：需要額外 fetch + 客戶端 substring scan、兩種 result UI 整合

### D：UX hint 明示匹配模式

把限制告訴使用者：「搜尋為前綴匹配、想找 X 請打 Y」。對應「明示語意縮小」概念。

- **適合**：成本最低、只需文字 hint
- **代價**：使用者要學新規則、不對齊 Google expectation

### E：接受限制（不告知）

不做任何處理、silent 接受。這是反模式 — 使用者誤以為「沒有相關內容」、放棄。

---

## 判讀徵兆

| 訊號                                                  | 該做的事                                            |
| ----------------------------------------------------- | --------------------------------------------------- |
| 寫 search feature、沒讀工具的 matching mode docs      | 跑識別三問、確認預設                                |
| 使用者報「我搜 X 找不到、但是有 X」                   | 多半是 matching mode gap、不是 bug                  |
| 使用者打字、結果列表 0 筆、但確實有相關內容           | 不對齊的訊號明顯、需要對策                          |
| Search 跨多種使用者（Google trained / dev / DB user） | Mental model 異質、選擇性高（A/B + C 組合通常需要） |
| 工具 docs 寫「matches by word prefix」這類字眼        | 警訊 — 預設不是 substring                           |
| 任何 static site search                               | 預設多半是 prefix、要主動評估是否符合需求           |

**核心原則**：搜尋引擎的匹配模式是個容易被忽略的 capability 維度。工具預設多半是 prefix（為了 index size）、使用者預期多半是 substring 或更高（被 Google 訓練）。沒對齊 = silent 失敗：使用者誤以為內容不存在、不會 report bug。Checkpoint 1 列「使用者意圖完整集」要包含「使用者打字行為的預期」。

---

## 與其他原則的串連

- Filter × Source 層錯位：都是「使用者意圖跟工具實際行為的 silent gap」、本卡是 matching 維度的展現 — 詳見 [`filter-source-composition-strategies.md`](./filter-source-composition-strategies.md)
- 寫作便利度跟意圖對齊反相關：工具預設是實作便利、使用者預期是 mental model 對齊、反相關 — 詳見 [`ease-of-writing-vs-intent-alignment.md`](./ease-of-writing-vs-intent-alignment.md)
- 驗收的時間軸：Checkpoint 1「source capabilities 是否對齊使用者預期」屬意圖完整集 — 容易跳過 — 詳見 [`verification-timeline-checkpoints.md`](./verification-timeline-checkpoints.md)
- 高 ROI 無外部觸發：「讀 search engine docs 確認 matching mode」沒便利路徑、容易跳過 — 詳見 [`external-trigger-for-high-roi-work.md`](./external-trigger-for-high-roi-work.md)
