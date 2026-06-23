# Progressive Verification & Minimum Necessary Scope

從最小可驗證單位起步、加變數一次只加一個、範圍從窄到寬擴張。

適用：UI layout debug、對齊問題、selector / MutationObserver root / JS 操作邊界的設計。
不適用：純內部演算法（沒有視覺、沒有範圍選擇）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋 placeholder 漸進、measurement 完整性、最小必要範圍三個共生原則。

---

> **Test-First 補充**：當「漸進」的方式是「寫測試固化」時、必須走 RED → GREEN 兩個訊號才算驗證 — 詳見 [#69 Test-First：先看到 RED 才相信 GREEN](principles/test-first-red-before-green.md)。沒看過 RED 的測試 = 未驗證的訊號、不能信任。

## 何時參閱本文件

| 訊號                                                     | 該做的第一件事                  |
| -------------------------------------------------------- | ------------------------------- |
| 開始 UI layout debug、不知道從哪一步起                   | 從色塊 placeholder 起步         |
| 對齊規則寫了結果歪掉、不知道哪裡錯                       | 列方程組、確認每個變數有來源    |
| 設計 selector / observer / JS 操作的範圍                 | 從最小起、有證據再擴張          |
| 想用 `document.querySelectorAll('*')` 或 `subtree: true` | 停 — 範圍可能過寬、補上限制條件 |
| Layout debug 一次改了 5 個變數、改完不知道哪個生效       | 退回去、一次只動一個            |

---

## 為什麼這三個原則合併在一份 reference

三個原則服務同一個讀者群體（**正在開始一個新工作、還沒卡關**）、回答同一類問題（**該從多大的範圍 / 多少變數起步**）。

- Placeholder 漸進 = 視覺面的「一次一個變數」
- Measurement 完整性 = 對齊問題的「方程組必須完整」
- Minimum scope = JS / CSS 範圍的「窄起來再放寬」

共同精神：**先窄後寬、有證據再擴張**。「先寬後縮」的問題是分不出哪個寬度是刻意的；「先窄後寬」每次擴張都有原因可追。

---

## 原則 1：Placeholder 漸進除錯

UI debug 從色塊起步、加東西一次加一個。

### 起步：純色塊

```html
<div style="width: 200px; height: 100px; background: red; border: 2px solid black;"></div>
```

沒文字、沒樣式、沒互動。**唯一目的**：確認位置、尺寸、grid / flex / absolute 的定位邏輯對。

### 階段順序

| 階段 | 加入                             | 驗證                           |
| ---- | -------------------------------- | ------------------------------ |
| 1    | 純色塊（固定尺寸 + 顯眼邊框）    | 位置、grid cell、stacking 對   |
| 2    | 占位文字（單行、無樣式）         | 文字基線對、line-height 沒影響 |
| 3    | 真實內容（多行、含長字串）       | 換行、溢出、文字裁切對         |
| 4    | 視覺樣式（color、font、padding） | 視覺層次對                     |
| 5    | 互動行為（hover、click、focus）  | 互動狀態對、focus 不跑掉       |

每階段只引入一個變數、發現問題能立刻定位。**跳階段** = 失敗時不知道是哪個變數錯。

### 典型反例

```html
<!-- 第 1 步直接寫真實內容 + 完整樣式 -->
<div class="card">
  <h3>Search results</h3>
  <p>Showing {{count}} matches for "{{query}}"</p>
  <ul>...</ul>
</div>
```

CSS 寫了 30 條、結果 `.card` 沒在預期位置。是 grid 錯？font-size 影響？margin-collapse？line-height？無法定位。

---

## 原則 2：Measurement 完整性

對齊問題的本質是線性方程組：

```text
target_y = anchor_y + offset
total_height = h1_height + form_height + gap + scope_height + ...
```

每個變數都要有明確來源 — 任一個未知 → 整組無解。

### 變數來源的三種類型

| 類型             | 說明                                   | 範例                                  |
| ---------------- | -------------------------------------- | ------------------------------------- |
| Hardcoded        | 寫死在 design token / config           | `--gap: 16px`、`--h1-height: 48px`    |
| Component hook   | 框架 / vendor 提供的 API               | `pagefind.options.height`、CSS var    |
| Runtime measured | JS 執行時量測（getBoundingClientRect） | `form.getBoundingClientRect().height` |

### 反例：靠估值補方程式

```css
/* 假設 form 大概 60px、加 gap 20px、總共 80px */
.scope { top: 80px; }
```

實際 form 高度是 72px（隨字型 / line-height 變動）→ scope 跑位 8px。

### 對例：每個變數有來源

```js
const formHeight = form.getBoundingClientRect().height;  // measured
const gap = parseFloat(getComputedStyle(form).marginBottom);  // measured
scope.style.top = `${formHeight + gap}px`;
```

或全部用 design token：

```css
.scope { top: calc(var(--form-height) + var(--gap)); }
/* var 在某處有單一定義、不是分散估值 */
```

混搭策略要全選同一邊：對齊基準上要嘛全寫死、要嘛全量測、不要 hardcoded + 估值混用。

---

## 原則 3：Minimum Necessary Scope

Selector / MutationObserver / JS 操作的範圍從最小起、擴張要有證據。

### Selector 範圍

| 寬度         | 範例                               | 風險                        |
| ------------ | ---------------------------------- | --------------------------- |
| 最小（精準） | `#search-form .scope-toggle`       | 安全、變化時要更新 selector |
| 中等         | `.scope-toggle`                    | 可能命中其他頁面的同名元素  |
| 過寬         | `[class*="scope"]` / `* > .toggle` | 命中無關元素、副作用未知    |

預設用最小、有證據（多個地方確實要 match）再擴張。

### MutationObserver 範圍

三個維度：root、options、頻率。

```js
// 過寬
observer.observe(document.body, { childList: true, subtree: true, attributes: true });
// → 監聽整個 page、每個 attribute 變動都觸發、CPU 100%

// 最小
observer.observe(searchForm, { childList: true });
// → 只監聽 form 直接子節點變動
```

### JS 操作邊界

改一個元素的範圍從小到大：

| 範圍            | 風險                                          |
| --------------- | --------------------------------------------- |
| 改 inline style | 安全、僅自家管的元素                          |
| 改 attribute    | 中 — framework 可能 reconcile 清掉            |
| 改 textContent  | 中 — 同上                                     |
| 改 innerHTML    | 高 — 子節點全重建、event listener 失效        |
| reparent 整節點 | 高但可控 — 整節點搬遷、framework 通常不會還原 |

從「改 inline style」起步、不行才升級。

---

## 三個原則的共同精神

**從最小可驗證單位起步、有證據再擴張**：

- Placeholder：色塊 → 文字 → 樣式（一次加一層）
- Measurement：每個變數先確認來源、再寫對齊規則
- Scope：最窄的 selector / observer / JS 邊界、要擴張要有具體 case

「先寬後縮」的反模式：寫一個包山包海的 selector、之後試著加 `:not(...)` 排除 → 永遠不知道哪些 match 是刻意的。

---

## Wrong vs Right 對照

### 範例 1：UI debug 起步

> 任務：把搜尋結果卡片做成兩欄 grid

**錯**：

```html
<!-- 直接寫完整版本 -->
<div class="results-grid">
  <article class="result-card">
    <h3><a href="...">Title</a></h3>
    <p class="excerpt">{{excerpt}}</p>
    <div class="meta"><span class="tag">tag</span> · <time>date</time></div>
  </article>
</div>

<style>
.results-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.result-card { padding: 16px; border: 1px solid; }
.result-card h3 { font-size: 18px; margin-bottom: 8px; }
/* ... */
</style>
```

跑出來、卡片高度不一致、`grid-auto-rows` 沒設、第二欄擠到第一欄底下。debug 困難 — 是 grid 設定錯？卡片內容差異？margin-collapse？

**對**：

```html
<!-- 階段 1：純色塊驗證 grid -->
<div class="results-grid">
  <div style="height: 100px; background: red;"></div>
  <div style="height: 100px; background: blue;"></div>
  <div style="height: 100px; background: green;"></div>
  <div style="height: 100px; background: yellow;"></div>
</div>
```

確認 grid 兩欄正常後、再進階段 2（加占位文字）。

### 範例 2：MutationObserver root

> 任務：當 search results 出現時、注入客製 UI

**錯**：

```js
new MutationObserver(...).observe(document.body, { subtree: true, childList: true });
// 整個 page 任何變動都觸發、callback 跑 1000+ 次/秒
```

**對**：

```js
const container = document.querySelector('.pagefind-ui__results-area');
new MutationObserver(...).observe(container, { childList: true });
// 只監聽 results area 的直接子節點變動
```

如果之後發現 `.pagefind-ui__results-area` 內部 nested 變動也要監聽 → 那時再加 `subtree: true`、加之前能說出「為什麼需要」。

---

## 自檢清單（dogfooding）

開始一個新工作前：

- [ ] UI debug：第 1 階段是不是純色塊（沒文字、沒樣式）？
- [ ] 對齊規則寫之前：是不是每個變數都列出來源（hardcoded / hook / measured）？
- [ ] Selector：起步是不是最精準的版本？
- [ ] MutationObserver：root / options 是不是最窄的？
- [ ] JS 改元素：是不是從「改 inline style」起、不行才升級？

任一項打勾失敗 → 退回最小、重新起步。

---

## 相關原則

- [`principles/minimum-necessary-scope-is-sanity-defense.md`](principles/minimum-necessary-scope-is-sanity-defense.md) — 最小必要範圍是 sanity 防線

---

**Last Updated**: 2026-04-26
**Version**: 0.1.0
