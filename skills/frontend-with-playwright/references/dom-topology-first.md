# DOM Topology First

寫 CSS 規則之前、先讀真實 DOM tree — class name 是約定、不是結構保證。Selector 設計從最精準起步、有證據再放寬。

適用：寫 / 改 CSS 規則、設計 JS query selector、判斷是否該改 layout 結構。
不適用：純邏輯演算法（沒有 DOM）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋 DOM 量測方法、selector 三維度設計、四種起點的取捨。

---

## 何時參閱本文件

| 訊號                                                     | 該做的第一件事                           |
| -------------------------------------------------------- | ---------------------------------------- |
| 即將寫 CSS 規則但只看過 class name、沒看過真實 DOM       | playwright 量 ancestor chain             |
| Selector 命中超出預期的元素                              | 把 selector 加上起點 + 範圍 + 過濾三維度 |
| 規則寫了但不生效                                         | DevTools Computed → 看誰實際贏了         |
| Class name 含 `__inner` `__wrapper` 但不確定是直接子節點 | playwright 讀 parent / child 關係        |
| 想用 `document.querySelectorAll('.target')`              | 先評估「起點要不要從元件根」             |

---

## 為什麼 DOM topology 要先確認

CSS 行為由「規則 + DOM tree + 樣式繼承 + 框架渲染」四個變數共同決定。**靜態推理只能基於假設的 DOM tree** — 假設錯了、推理就錯。

Class name 是命名約定 — `pagefind-ui__drawer` 看起來像 `.pagefind-ui` 的 child，但實際可能是 `pagefind-ui__form` 的 child。命名告訴你「這是 drawer」、不告訴你「在哪一層」。

跳過 DOM 確認的代價：寫了 N 條 CSS 規則、推理為什麼不生效、加 specificity / `!important` / `display: contents` — 全部基於錯假設。

---

## 量 DOM 的最小 query

```js
// ancestor chain
async () => {
  const el = document.querySelector('.target');
  let chain = []; let n = el;
  while (n && n !== document.body) {
    chain.push(`${n.tagName}.${n.className}`);
    n = n.parentElement;
  }
  return chain;
}
```

返回值告訴你目標元素在 DOM tree 哪個位置、parent / sibling 是誰。寫 CSS 規則前 30 秒能省掉後續 30 分鐘推理。

---

## Selector 設計三維度

精準的 selector = **起點 + 範圍 + 過濾** 三維度顯式設計、不是「能命中就好」。

| 維度 | 問題                      | 答案類型                                     |
| ---- | ------------------------- | -------------------------------------------- |
| 起點 | 從哪個 DOM 節點開始 query | document / 元件根 / 函式參數 / closest()     |
| 範圍 | 要找直接子節點還是子孫    | `>` 直接子 / `> ... > ...` 多層 / 空格 子孫  |
| 過濾 | 要排除哪些元素 / 已處理的 | `:not()` / `[data-processed]` / WeakMap 檢查 |

---

## 起點四選一（依情境）

### 起點 A：Document 全文件 query

```js
document.querySelector('.target');
```

**用**：原型期、單例（整頁只一個）、跨元件邊界元素。
**不用**：production 客製、可能多實例、效能敏感（大頁面）。

### 起點 B：元件根變數 query

```js
const root = document.querySelector('.pagefind-ui');
root.querySelector('.target');  // 從 root 起
```

**用**：production 客製、客製只該影響該元件、避免命中其他頁面同名元素。
**不用**：跨多元件邊界的 query。

### 起點 C：起點當函式參數

```js
function decorate(root) {
  return root.querySelector('.target');
}
```

**用**：library / utility function、需要支援多實例、純函式設計。
**不用**：一次性腳本（多餘的抽象）。

### 起點 D：closest() 反向找根

```js
button.addEventListener('click', e => {
  const card = e.target.closest('.result-card');
  card.classList.add('expanded');
});
```

**用**：動態 / 多實例元件、event delegation、不知道事件源在哪一層。
**不用**：靜態起點已知（用 B 或 C 更直接）。

---

## 範圍：`>` 還是空格

| 寫法                 | 意思           | 風險                                  |
| -------------------- | -------------- | ------------------------------------- |
| `.parent > .child`   | 直接子節點     | 安全、嚴格                            |
| `.parent .child`     | 任意深度子孫   | 命中 nested 結構的同類元素            |
| `.parent > * > .x`   | 確切兩層       | 嚴格、結構變動時要更新                |
| `.parent .x:not(.y)` | 子孫中排除某類 | 還是子孫範圍、:not 是過濾不是限制範圍 |

預設 `>`、有證據（多層 nested 結構都該 match）才放寬到空格。

---

## 過濾：idempotency 標記

JS 處理元素時、避免重複處理。兩種做法：

### A：DOM attribute 標記

```js
function decorate(root) {
  const targets = root.querySelectorAll('.target:not([data-decorated])');
  targets.forEach(el => {
    // ... 處理
    el.setAttribute('data-decorated', '');
  });
}
```

**用**：production 預設、devtools 可見、跨 page reload 也保留（如果元素持久）。
**不用**：library 設計（不該污染使用者 DOM）。

### B：WeakMap 紀錄

```js
const decorated = new WeakMap();
function decorate(root) {
  root.querySelectorAll('.target').forEach(el => {
    if (decorated.has(el)) return;
    // ... 處理
    decorated.set(el, true);
  });
}
```

**用**：library 設計、不污染 DOM、元素 GC 後紀錄自動清。
**不用**：跨頁面、需要 devtools debug、需要 CSS selector 過濾（CSS 看不到 WeakMap）。

---

## Wrong vs Right 對照

### 範例 1：寫 CSS 前沒看 DOM

> 任務：把 `pagefind-ui__drawer` 排到 `pagefind-ui__form` 下方

**錯**（基於 class 命名假設）：

```css
.pagefind-ui {
  display: grid;
  grid-template-rows: auto auto;
}
.pagefind-ui__form { grid-row: 1; }
.pagefind-ui__drawer { grid-row: 2; }
```

跑出來 drawer 跑到頁尾、grid-row 完全沒生效。

**對**（先量 DOM）：

```js
async () => {
  const drawer = document.querySelector('.pagefind-ui__drawer');
  let chain = []; let n = drawer;
  while (n && n !== document.body) { chain.push(`${n.tagName}.${n.className}`); n = n.parentElement; }
  return chain;
}
// 返回：[DIV.pagefind-ui__drawer, FORM.pagefind-ui__form, DIV.pagefind-ui]
// → drawer 是 form 的 child、不是 sibling
// → grid-row 在 .pagefind-ui 上設、無法控制 form 的 child
```

→ 換方向：drawer 改 absolute、form 加 margin-bottom 留 spacer。

### 範例 2：selector 過寬命中無關元素

**錯**：

```js
document.querySelectorAll('.title').forEach(el => el.classList.add('search-title'));
// 命中 page header 的 .title、navbar 的 .title、結果卡的 .title — 全變色
```

**對**：

```js
const root = document.querySelector('.pagefind-ui');
root.querySelectorAll(':scope > .results > .result > .title').forEach(el => el.classList.add('search-title'));
// 起點 = .pagefind-ui、範圍 = 確切三層、過濾 = 不需要（已精準）
```

---

## 自檢清單（dogfooding）

寫 CSS 規則或 JS query 前：

- [ ] 我有沒有量過真實 DOM tree（playwright `browser_evaluate` 或 DevTools）？
- [ ] Selector 的「起點」明確嗎？是 document / 元件根 / 函式參數 / closest 哪一個？
- [ ] Selector 的「範圍」明確嗎？是 `>` 直接子還是空格子孫？
- [ ] Selector 的「過濾」明確嗎？需要 idempotency 標記嗎？
- [ ] 過寬的 selector（`document.querySelectorAll('*')`、`[class*="x"]`）能不能換成更精準的？

任一項打勾失敗 → 補上、再寫規則。

---


**Last Updated**: 2026-04-26
**Version**: 0.1.0
