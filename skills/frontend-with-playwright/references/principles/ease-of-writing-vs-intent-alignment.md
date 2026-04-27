# 寫作便利度跟意圖對齊反相關

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 SKILL.md「相關抽象層原則」段與 `references/data-flow-and-filter-composition.md` 引用、是 [`verification-timeline-checkpoints.md`](./verification-timeline-checkpoints.md) / [`test-first-red-before-green.md`](./test-first-red-before-green.md) / [`url-as-state-container.md`](./url-as-state-container.md) 等多份 principle 共同參照的 meta-principle。
>
> **何時讀**：寫程式當下感覺「這樣寫最快」「直接用現成 API 就好」「之後再 refactor」時、用本卡判斷自己是否掉進「容易寫的陷阱」。

---

## 核心原則

**寫程式時最容易寫出的版本、通常是離意圖最遠的版本。**

| 變數        | 寫作便利度高的特徵     | 意圖對齊高的特徵        |
| ----------- | ---------------------- | ----------------------- |
| 起點        | 用現成的 context / API | 找到正確的層            |
| 範圍        | 寬（捕魚式撈一遍）     | 窄（精準命中）          |
| 操作位置    | 下游（已 materialize） | 上游（stream / source） |
| 認知負擔    | 低（就地能解）         | 中-高（要回到上層分析） |
| Silent 風險 | 高（看起來能用）       | 低（強制處理邊界）      |

兩個方向反相關 — **越容易寫、越容易錯位**。識別這個反相關 = 識別自己正在掉進「容易寫的陷阱」、不是寫出對的東西。

---

## 為什麼便利度跟正確性反向

### 便利度的來源

寫程式當下、能「快速寫出」的條件是：

- 手邊已經有需要的資料（已 fetch、已 render、已 materialize）
- 現成的 API 能直接呼叫（`document.querySelectorAll`、`Array.from`、`results.filter`）
- 不需要跨抽象層（不用回到 source / framework 邊界 / build pipeline）

這些條件都建立在「**已是 subset / 已展開 / 已下游**」的位置 — 因為下游才有「現成上下文」。

### 意圖對齊的代價

「跟使用者意圖對齊」的條件相反：

- 操作 stream 全集（不是 subset）
- 在 source 層處理（不是 view 層）
- 處理 build-time 抽象（不是 runtime 取巧）

這些條件要求**回到上游 / 跨抽象層 / 處理沒被 materialize 的東西** — 而上游沒有「現成上下文」、需要刻意建立。

### 反相關的本質

便利度 = 用已有資訊；意圖對齊 = 處理還沒有的資訊。**資訊狀態相反 → 兩個目標反相關**。

「容易寫」這件事本身就是「在錯位的層」的徵兆。不是「容易寫的有時候錯」、是「容易寫的多半錯」。

---

## 多面向：跨領域的同個結構

### 面向 1：Filter 在 view 層

容易寫：`document.querySelectorAll('.result').forEach(el => el.hidden = !matches(el))` — 5 行、用現成 DOM。

意圖對齊：把 filter 推到 source 層 — 改 SDK 呼叫、可能改 build。

相關概念：Filter 與 Source 的層錯位（在 source 層做 filter、不在 view 層 post-filter）。

### 面向 2：Selector 用過寬範圍

容易寫：`document.querySelectorAll('.title')` — 一行命中所有 `.title`。

意圖對齊：`document.querySelector('.scope-root').querySelectorAll(':scope > .results > .result > .title')` — 起點 + 範圍 + 過濾顯式設計。

過寬 selector 的代價是「命中無關元素 → 副作用未知」 — 但寫的時候不會看到。

### 面向 3：Inline style + !important

容易寫：`el.style.setProperty('display', 'none', 'important')` — 立刻生效。

意圖對齊：`el.classList.toggle('is-hidden')` + CSS class — 樣式留 CSS、JS 只 toggle state。

Important 是「立刻生效」的便利、代價是「DevTools 看不出為什麼」、改視覺要 grep 多處。

### 面向 4：Middleware filter（後端 case）

容易寫：在 API response 後加 filter middleware — 對 response array 做 `.filter()`。

意圖對齊：把 filter 推進 ORM query / SQL `WHERE` — 改 query、可能加 index。

Middleware 在 pagination 之後、漏掉沒在這頁的符合項。

### 面向 5：Cached subset 上算統計

容易寫：`stats.average = cache.values().reduce(...) / cache.size` — 直接用 cache。

意圖對齊：先 revalidate、再算；或標明「statistic on cached subset」。

Cache subset 算出的統計跟 fresh dataset 算出的不同、但寫的時候看不到差異。

**五個面向共用結構**：用「已存在的東西」5 行解決、產出對「沒處理到的東西」silent 失敗的版本。

---

## 便利度的時間維度：當下便利 vs 未來便利反向

便利度有兩個尺度、方向相反：

| 尺度     | 什麼是便利                           | 對誰便利           |
| -------- | ------------------------------------ | ------------------ |
| 當下便利 | 用現成 context、5 行解決、不跨層     | 寫的當下的我       |
| 未來便利 | 清楚的層次、明確的契約、可預測的行為 | 五年後讀 code 的人 |

「五年後讀 code 的人」包括五年後的自己 — 那時候不會記得當下為什麼選 view 層 filter、只會看到「為什麼這個 filter 漏掉了沒載入的東西」。

### 為什麼兩個尺度反向

當下便利的條件是「**用已存在的東西**」：

- 已 materialize 的資料（不用追上游）
- 已存在的 API（不用設計介面）
- 已有的命名（不用想新名字）

未來便利的條件是「**留下可預測的結構**」：

- 操作位置跟意圖對齊（不用 debug 為什麼結果怪）
- 抽象層清楚（不用穿三層才理解一行）
- 命名反映意圖（不用讀 commit history 才懂）

兩個條件方向相反 — 用已存在的東西 = 順著當下慣性；留下可預測結構 = 抵抗當下慣性、為未來付出。

### 「我等下會 refactor」是個謊言

寫便利版時內心 OS 常常是「先這樣、晚點 refactor 補回來」 — 但補回來這件事在實務上幾乎不發生：

- Refactor 沒有功能訊號驅動（壞掉才修、能用不修）
- 重新理解當時為什麼這樣寫、需要把整個 context 重建一次（成本反而高）
- 寫的時候的決策已經影響了周邊代碼（要 refactor 一處要連帶改五處）

所以「現在便利、未來再對齊」這個 plan 實際上是「現在便利、未來繼承這個錯位」。**當下的選擇就是長期的選擇**、沒有「之後補」這個選項。

要嘛當下對齊、要嘛接受 explicit 縮小（把限制攤開）。沒有第三條路。

---

## 識別訊號：什麼時候你正掉進這個陷阱

### 訊號 1：「這樣寫最快」

內心 OS「直接 forEach + filter 就好」「就用現成的 API 啊」 — 「最快 / 現成」這兩個詞通常標記下游 / subset 位置。

### 訊號 2：跨層的成本看起來高、但本層解看起來夠

「為了一個 filter 改 build pipeline 太誇張了吧」「直接前端 filter 不就好了」 — 這個內心 OS 在錯估、因為下游解的 silent 風險不在當下顯露。

### 訊號 3：寫完手動測一次就過

第 1 次 happy path 過了、覺得對。但 happy path 過 = 子集裡有命中、不證明 stream 全集對齊。同 [`two-occurrence-threshold.md`](./two-occurrence-threshold.md)：第 1 次成功是低資訊量訊號。

### 訊號 4：「先這樣、晚點補資料層」

這個想法本身就是「我知道這寫法不對齊意圖、但便利度太高」 — 補不回來、會 ship 進 production silent 失敗。

---

## 不該套用本原則的情境

「便利度跟意圖對齊反相關」這條原則在絕大多數開發情境成立、但有合理例外：

| 情境                      | 為什麼不該套用                                         |
| ------------------------- | ------------------------------------------------------ |
| 純原型 / hackathon        | 預期幾天後丟掉、未來便利根本沒有未來、便利優先合理     |
| 一次性 throw-away script  | 跑完就刪、不維護、寫完馬上產生價值、對齊成本沒回報     |
| 探索性 spike              | 目的是驗證可行性、不是建立可維護結構、便利對齊不是議題 |
| Code review 之前的 sketch | 寫出來是為了討論、不是 ship、之後會重寫                |

這四類共同特徵：**「未來便利」這個變數的權重 ≈ 0** — 因為沒有未來（不會被讀、不會被改、不會被擴）。本原則的反相關建立在「未來便利有權重」上、權重 0 時自然不適用。

判讀：寫之前自問「這代碼三個月後會不會有人讀」 — 否 → 本原則可放寬；是 → 本原則嚴格適用。

---

## 跟其他抽象層原則的關係

| 原則                                                                                             | 跟本卡的關係                                       |
| ------------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| [`two-occurrence-threshold.md`](./two-occurrence-threshold.md)                                   | 「容易寫」是低資訊量訊號、跟「第 1 次成功」同類    |
| [`minimum-necessary-scope-is-sanity-defense.md`](./minimum-necessary-scope-is-sanity-defense.md) | 寬範圍是便利、窄範圍是對齊 — 同個反相關            |
| [`single-source-of-truth.md`](./single-source-of-truth.md)                                       | 多源是便利（就地寫個值）、單源是對齊(找 fact 位置) |
| [`external-component-collaboration-layers.md`](./external-component-collaboration-layers.md)     | 內部結構層便利、公共介面層對齊                     |

本卡是這幾條的共同上位原則 — 它們都是「**便利 vs 正確性的取捨**」在不同情境的具體展現。

---

## 判讀徵兆

| 訊號                                       | 該做的行動                                   |
| ------------------------------------------ | -------------------------------------------- |
| 內心 OS：「這樣寫最快」「直接用現成 API」  | 停 — 評估「快」是不是「在錯層」的徵兆        |
| 5 行解決一個原本應該跨層的問題             | 是 — 跨層通常 50+ 行、5 行是訊號             |
| 跨層解的工程量看起來「不值得」             | 注意 — 你可能在錯估 silent 風險的代價        |
| 「先做、晚點補上游」                       | 補不回來、要嘛當下做、要嘛接受 explicit 縮小 |
| 寫完 happy path 一次就過                   | 補規模 / 稀疏 / 跨情境驗證                   |
| 程式跑得通、但你說不出為什麼這個位置是對的 | 這是「便利驅動」而不是「意圖驅動」的訊號     |

**核心原則**：寫程式當下的便利度跟正確性反相關、是因為兩者用的資訊狀態相反。識別「我現在在容易的位置」 = 識別「我可能在錯的層」。**便利度本身是個診斷訊號**、不是好東西。

延伸到測試驗證：跳過 RED 階段（不切 branch / 不重 build / 不在 buggy code 上跑測試）是便利、走 RED-GREEN 是對齊。詳見 [`test-first-red-before-green.md`](./test-first-red-before-green.md)。

更上位的解釋：相關概念「高 ROI 無外部觸發的工作會被結構性跳過」 — 本卡是該 meta-原則在「寫程式當下選哪條路」面向的展現。
