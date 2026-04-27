# Filter 與 Source 的抽象層錯位

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 reference `data-flow-and-filter-composition.md`（根因）引用、是 filter / sort / count 跟分批 source 合成時的層錯位反模式根源卡。
>
> **何時讀**：要寫 filter / sort / count / transform 操作之前、source 是 paginated / streaming / cached / lazy 的；或 bug report 是「Load more 後畫面閃但內容沒變」「我搜了但漏東西」這類疑似 silent 缺口時。

---

## 核心原則

**Filter 必須跟它過濾的資料源在同一層運作。** 把 filter 寫在視覺層（querySelector + show/hide）、把 source 留在資料層分批產出（paginated fetch / streaming / lazy iterator）— 兩層的「一筆」定義不一致、filter 看不到 source 還沒產出的東西、結果跟使用者意圖之間有語意縫。

更廣義的說法：**stream 操作（filter / sort / count / transform / search）必須跟 stream 的 materialization 同層或更上游**。在下游做 stream 操作、操作的對象是已經 materialize 的 subset、不是完整的 stream。

---

## 為什麼層錯位產生語意縫

### 「一筆」在不同層有不同定義

| 層     | 「一筆」是什麼           | 邊界                            |
| ------ | ------------------------ | ------------------------------- |
| 資料層 | Source 產出的一筆 record | 全部、或還沒產出的下一批        |
| 渲染層 | 已 render 進 DOM 的一筆  | = 已 fetch 並 render 過的子集   |
| 視覺層 | 螢幕上看得見的一筆       | = render 層之中沒被 hide 的子集 |

Filter 寫在視覺層、它的「過濾全部」≡「過濾螢幕上看得見的全部」≡「過濾已 fetch 已 render 的子集」。**離資料層的真實全集差兩層**。使用者意圖（「給我所有 title 含 X 的結果」）對應的是資料層的全集、不是視覺層的子集。

### Silent 失敗的條件

層錯位不會在「filter 子集裡有命中」的情境下被發現。它只在以下條件下顯露：

1. 已 materialize 的子集裡剛好沒命中
2. 但完整 stream 裡有命中、只是還沒 materialize
3. 使用者沒有訊號知道「還有沒抓的」

三個條件同時滿足、使用者看到「filter 後是空的」、誤以為是「沒有命中」、放棄。

### 為什麼這個 bug 容易寫出來

視覺層 filter 是寫起來最簡單的版本：

```js
items.forEach(el => {
  el.style.display = el.dataset.title.includes(query) ? '' : 'none';
});
```

5 行解決、看起來能用、第一輪測試（手動輸入 query → 看到 filter 生效）會通過。**「能用」的訊號出現太早、掩蓋了語意缺口**。

這是 [寫作便利度跟意圖對齊反相關](./ease-of-writing-vs-intent-alignment.md) 在「filter × source」情境的具體展現 — 容易寫的位置（已 materialize 的 view 層）跟對齊意圖的位置（source 層）方向相反。

---

## 哪些 source 形狀有層錯位風險

| Source 型態                           | 是否有層錯位風險                |
| ------------------------------------- | ------------------------------- |
| 一次性 fetch、靜態陣列                | 否（沒有 subset）               |
| Paginated fetch（load more / cursor） | 是                              |
| Streaming（SSE / WebSocket）          | 視 server 是否限額              |
| Lazy iterator + take(N) / break       | 是                              |
| Cached + revalidate                   | 是（cache vs fresh 兩 dataset） |

四類 source 共用同個結構：**source 分批 / 限額 / 延遲 materialize、filter 在下游 → silent 缺口**。詳細形狀分析見 [data-source-shape-defines-feature-shape](./data-source-shape-defines-feature-shape.md)。

---

## 內在屬性比較：filter 該放哪一層

| 層            | 看到的範圍       | 跟使用者意圖的距離 | 寫作成本           |
| ------------- | ---------------- | ------------------ | ------------------ |
| 視覺層        | 已 render 的子集 | 最遠（差兩層）     | 最低               |
| 渲染層        | 已 fetch 的子集  | 中（差一層）       | 低                 |
| 資料層 (源頭) | 完整 dataset     | 最近               | 中-高              |
| Source 之外   | 重 query         | 最近 + 最新        | 高（query 重設計） |

「寫作成本最低」跟「跟意圖最近」是反相關 — 這個反相關本身是 [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md) 的核心命題、本卡是它在 filter × source 情境的展開。

---

## 識別層錯位的三問

寫 filter / sort / count / transform 之前自問：

### 1. 這個操作的「對象」是什麼層的「一筆」？

如果寫在 view 層、對象是「螢幕上的元素」 — 那源頭如果分批、就有缺口。

### 2. Source 是「一次給完整 dataset」還是「分批 / 限額」？

對照前面「哪些 source 形狀有層錯位風險」表 — 任何分批 / 限額 / streaming / cached source 都有風險。一次性 fetch 或靜態陣列才安全。

### 3. 「沒命中」與「還沒 materialize」對使用者要不要區分？

要區分 → filter 必須在 source 層或自動續抓、否則使用者無法判斷。
不區分（可接受「在已載入範圍內找」這個語意） → view 層 filter 加誠實 UX。

三問跑完才寫 filter — 跳過任一問就可能掉進層錯位。

---

## 判讀徵兆

| 訊號                                                               | 該做的行動                                       |
| ------------------------------------------------------------------ | ------------------------------------------------ |
| 即將寫 `elements.forEach(el => el.hidden = !matches(el))`          | 停 — 確認 source 是不是分批的；是 → 推到資料層   |
| Source 是 paginated / `for await` / streaming 但 filter 在 forEach | 是 — 重看「filter 該放哪一層」                   |
| 不確定 source 真實 cardinality 跟分批機制                          | 用 playwright 量 live source 的回傳數量          |
| Filter 後可能 0 筆但 source 還有未載入                             | 必須補「自動續抓」或「誠實掃描範圍 UX」          |
| 「Load more」「Show next」按鈕存在、且有 filter                    | 評估：filter 跟 load more 的 quota 是否同層      |
| 內心 OS：「先做出來、晚點補資料層」                                | 停 — 補不回來、會 ship 進 production silent 失敗 |

**核心原則**：filter / sort / count / transform 是 stream operation、必須跟 stream 的 materialization 同層或更上游。寫在下游 = 操作 subset 而不是 stream、語意縫是必然、不是偶發 bug。

---

## 與其他原則的串連

- [filter-source-composition-strategies](./filter-source-composition-strategies.md) — 解法策略五選一（A 推進 query / B 自動續抓 / C 預先 index / D 誠實 UX / E 明示縮小）
- [filter-instruction-clarification](./filter-instruction-clarification.md) — 寫 filter 之前的三問澄清模板
- [visual-completion-vs-functional-completion](./visual-completion-vs-functional-completion.md) — 「畫面對但功能漏」、本卡是該命題在 filter × source 情境的具體展現
- [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md) — 容易寫的位置（view 層）跟對齊意圖的位置（source 層）方向相反、本卡是該原則的具體展開
- [data-source-shape-defines-feature-shape](./data-source-shape-defines-feature-shape.md) — source 形狀（分批 / streaming / cached）決定 feature 形狀
