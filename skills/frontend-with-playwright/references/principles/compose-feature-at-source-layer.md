# Feature 操作要跟 Source 同層合成

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 reference `data-flow-and-filter-composition.md` 與 SKILL.md「相關抽象層原則」段引用。
>
> **何時讀**：寫 filter / sort / count / transform / search 等 stream 操作前、判斷該套在哪一層；或發現「能用、但邊界 case 怪」的 silent 缺口、找根因時。

---

## 核心原則

**Stream 操作（filter / sort / count / transform / search）必須跟 stream 的 materialization 同層或更上游合成。** 在下游合成 = 操作的對象是 subset、不是 stream。

這是 [Filter 與 Source 的層錯位](./view-layer-filter-vs-source-layer.md) 的抽象升級 — 不限於「視覺層 vs 資料層」、適用任何分層系統（前端 / 後端 / 演算法管線 / 資料庫）。

---

## 抽象結構

```text
[Stream Source]
   ↓ (materialize 部分)
[Subset L1]
   ↓ (再 materialize)
[Subset L2]
   ↓ ...
```

Stream 操作要套在哪一層、決定它「過濾的範圍」是什麼：

| 套在哪一層    | 操作範圍        |
| ------------- | --------------- |
| Stream Source | 完整 stream     |
| Subset L1     | L1 子集         |
| Subset L2     | L1 的子集的子集 |

使用者 / 呼叫者通常想要的是「完整 stream 的操作結果」、不是「下游 subset 的結果」。在下游做 = 跟意圖不對齊。

---

## 多面向：跨領域的同個結構

### 領域 1：前端 UI

- Stream：完整搜尋結果集
- Materialize：搜尋元件分批 fetch
- Subset：已載入的 result
- 錯誤合成：在 view 層 filter（subset 上做）

### 領域 2：後端 API + middleware

```text
[Database query result]  ← stream source
  ↓
[ORM materialize as objects]  ← L1 subset (lazy load 部分欄位)
  ↓
[API response]  ← L2 subset (pagination 後)
  ↓
[Middleware filter]  ← 錯誤位置 — 已是 subset 了
```

Middleware 過濾「pagination 後的回應」 — 漏掉沒在這頁的符合項。應該推進 ORM query。

### 領域 3：演算法管線

```python
def pipeline():
    for chunk in load_chunks():       # stream source
        for item in chunk:             # L1
            processed = transform(item) # L2
            yield processed             # L3

# 錯誤合成
results = list(pipeline())
filtered = [x for x in results if matches(x)]
# ↑ 如果上游有 take(N) 或 break、filtered 對的是 subset
```

對例：filter 推到 transform 之前 / 之內。

### 領域 4：資料庫 + materialized view

```sql
-- 錯誤：在 view 上 filter
SELECT * FROM materialized_view WHERE x = 1;
-- ↑ materialized_view 可能是 partial / stale

-- 對例：filter 推進原表
SELECT * FROM source_table WHERE x = 1;
-- 或 view 重建時 filter 已加進去
```

### 領域 5：Map / Reduce

```text
[shards] → [map output partial] → [reduce]
                                       ↓
                                  [post-reduce filter]  ← 錯位
```

Filter 應該在 map 階段（per-shard）或 reduce 內、不是 reduce 後。

**五個領域共用結構**：在 materialization 下游做 stream 操作 → silent 缺口。

---

## 同層合成的具體做法

### 做法 1：把操作推進 source query

最直接 — source 端就回符合的、根本沒 subset。

對應 [Pattern：推進 query](./pattern-query-side-pushdown.md)。

### 做法 2：在 materialization 過程中合成

如果 source 是 lazy stream、操作放進 stream 而不是事後：

```python
# 對例：filter 放進 stream
def filtered_pipeline(predicate):
    for chunk in load_chunks():
        for item in chunk:
            if predicate(item):
                yield item
```

每筆 materialize 時就 filter、不累積到 subset 後再做。

### 做法 3：自動續抓直到湊滿

當 source 不能改、且 materialization 是分批 — 用 loop 把分批變透明。

對應 [Pattern：自動續抓](./pattern-fetch-until-quota.md)。

### 做法 4：明示降級到 subset 操作

不能同層合成 → 顯式告訴呼叫者「我只在 subset 上做」、而不是假裝在 stream 上做。

對應 [Pattern：誠實進度 UX](./pattern-honest-progress-ui.md)。

---

## 為什麼這個原則跨領域通用：資訊可見範圍

五個領域共用結構不是巧合。底層命題是**資訊論的問題、不是工程問題**：

> 一個操作能「看見」的範圍、就是它能正確套用的範圍。把操作放在看不見完整 stream 的位置 = 操作對部分資訊運算 = 結果不能宣稱對完整資訊。

「合成位置」就是「資訊可見範圍」的代名詞。同層或上游的位置看得到完整 stream、下游位置只看得到 subset。這跟「stream 是什麼樣的資料」「系統是哪個語言寫的」「框架是 React 還是 Vue」都無關 — 只跟「看得到什麼」有關。

所以這個原則：

- 不是「前端 bug」 — 後端、演算法、DB、map-reduce、分散式系統都會遇到
- 不是「特定技術 stack 問題」 — 任何分層架構都適用
- 不是「特定 library 問題」 — 任何「分批 materialize」的 source 都會引發

把它當「資訊可見範圍」原則來理解、能應用到任何「stream 操作 + 分層 materialization」的情境。

---

## 上推（push down）在不同領域的代價

把操作從下游推到上游 = 改變誰負責執行操作。每個領域的「上推」代價不同：

| 領域            | 上推 = 在哪裡做              | 代價                                      |
| --------------- | ---------------------------- | ----------------------------------------- |
| 前端 UI         | 推到 fetch 層 / source query | 重設計 fetcher、可能改 API contract       |
| 後端 middleware | 推到 ORM query / SQL WHERE   | 改 query、可能要加 index                  |
| 演算法管線      | 推到 stream stage 內         | 重排 pipeline、可能影響其他 stage         |
| 資料庫          | 推到原表 query / 重建 view   | 重 build view、影響其他依賴 view 的 query |
| Map-reduce      | 推到 map 階段或 reduce 內    | 改 mapper / reducer 邏輯                  |

代價評估決定「能不能上推」：

- 代價 < 缺口的維護成本 → 上推
- 代價 > 缺口的維護成本 → 退到 explicit 縮小（[明示語意縮小](./pattern-explicit-semantic-narrowing.md)）+ 接受
- 代價 ≈ 缺口的維護成本 → 看其他因素（短期 vs 長期、團隊熟悉度）

---

## 常見誤判：以為自己在 source 層、實際在 subset 層

每個領域都有「看起來是 source 但實際是 subset」的陷阱：

| 領域         | 看起來是 source、實際是 subset                                                                |
| ------------ | --------------------------------------------------------------------------------------------- |
| 前端         | `Array.from(document.querySelectorAll(...))` 看起來是「全部元素」、實際是「已 render 的元素」 |
| 後端 ORM     | `User.all()` 看起來是「所有 user」、實際是 lazy load + memory 限制                            |
| 演算法       | `list(generator)` 看起來是「materialize 全部」、實際 generator 上游可能 lazy / take(N)        |
| 資料庫       | `SELECT * FROM materialized_view` 看起來是查表、實際 view 可能 stale / partial                |
| 分散式 cache | `cache.get_all()` 看起來是「cache 全集」、實際是 single-node subset                           |

這些誤判共用結構：**API 命名暗示「全集」、實際是 subset**。寫之前要看「這個 API 的真實 cardinality 是什麼」、不是看名字。

---

## 跟形狀原則的關係

[資料源的形狀決定 feature 的形狀](./data-source-shape-defines-feature-shape.md) 講「形狀是硬約束」 — 本文講「在硬約束下、操作該放哪一層」。

| 維度 | 形狀原則                  | 本文                   |
| ---- | ------------------------- | ---------------------- |
| 焦點 | 形狀如何約束 feature 設計 | 操作如何跟 stream 合成 |
| 階段 | 設計 / 規劃               | 實作 / 架構            |
| 結論 | 不要憑 UI 倒推資料層      | 操作要同層或更上游     |

兩者互補：形狀原則是 high-level 設計原則、本文是 implementation 指引。

---

## 設計取捨：操作合成的位置

四種、跟「策略五選一」對應但更抽象。

### A：合成在 source

最近 stream、無 silent 缺口。對應推進 query。

### B：合成在 materialization 過程中

Stream 處理時就做、不累積到 subset 後。對應自動續抓 + 在 loop 內 filter。

### C：合成在 subset、但顯式

明示語意縮小、用誠實 UX 告訴呼叫者範圍。

### D：合成在 subset、隱式（反模式）

- **為什麼是反模式**：silent 失敗、跟意圖有縫、違反「資訊可見範圍 = 操作正確套用範圍」的本質
- **看起來吸引人的原因**：寫起來最快、用現成 subset、不用追上游、5 行解決
- **實際發生的代價**：跨情境 silent bug、使用者基於錯結果決策、debug 時定位困難（因為錯位的位置不會報錯）

選擇順序：**A → B → C → 不要 D**。

---

## 判讀徵兆

| 訊號                                                                  | 該做的事                                        |
| --------------------------------------------------------------------- | ----------------------------------------------- |
| 寫 `.filter()` / `.sort()` / `.count()` 在已 materialize 的 subset 上 | 確認 source 是不是 stream / 分批；是 → 推到上游 |
| 跨多層的系統、操作出現在最下游                                        | 評估能不能上推                                  |
| 「能用、但沒覆蓋邊界 case」的功能                                     | 多半是合成位置錯了                              |
| Map-reduce / pipeline / middleware 鏈路裡、filter 在最後一層          | 推進到 stage 內                                 |
| 內心 OS：「在最後 filter 比較容易寫」                                 | 是訊號 — 容易寫的位置通常是錯位的位置           |

**核心原則**：Stream 操作的合成位置決定它的語意。同層或更上游 = 操作 stream、跟意圖對齊。下游 = 操作 subset、跟意圖有縫。這個原則跨前端 / 後端 / 演算法 / 資料庫 / 分散式系統通用 — 不是「前端 vs 後端」的問題、是「合成位置 vs materialization 位置」的問題。

---

## 與其他原則的串連

- 跟 [最小必要範圍是 sanity 防線](./minimum-necessary-scope-is-sanity-defense.md)：兩者共用「邊界選對 vs 選錯」的精神 — 一個講範圍從窄到寬、本卡講合成從上游到下游；錯方向都是 silent 失敗
- 跟 [Single Source of Truth](./single-source-of-truth.md)：兩者共用「值的住址唯一」精神 — SSOT 是「定義位置唯一」、本卡是「操作位置正確」；操作不在 source 層 = 等於建了個第二定義（subset 上的「filter 結果」）跟 stream 全集競爭
- 跟 [2 次門檻](./two-occurrence-threshold.md)：發現合成位置錯時、不要試「同層補丁」三次以上、第 2 次失敗就退一層找根因
