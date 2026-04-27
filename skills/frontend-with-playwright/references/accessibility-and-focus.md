# Accessibility and Focus

A11y 三道防線：靜態（鍵盤可達性三要素）、動態（focus 跟 aria-live）、優先 Native HTML > ARIA。鍵盤 / 視覺 / motor / 認知都納入。

適用：寫互動 UI、JS reparent / hide 元素、自製 component（modal / dropdown / tabs）、客製外部組件後檢查 a11y。
不適用：純後端 / 純資料流（沒有使用者直接互動）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋鍵盤可達性三要素、focus management 模板、aria-live 設計、native HTML 優先原則。

---

## 何時參閱本文件

| 訊號                                                | 該做的第一件事                           |
| --------------------------------------------------- | ---------------------------------------- |
| 自製 modal / dropdown / tabs / accordion            | 先看有沒有 `<dialog>` / `<details>` 能用 |
| JS reparent 或 hide 元素                            | 保存 focus、操作後還原                   |
| 動態變動內容（搜尋結果、filter 切換、status 訊息）  | 加 `aria-live` region                    |
| 使用者反映「鍵盤跑掉」「Tab 順序怪」                | 檢查 visible focus indicator + tab order |
| 即將寫 `role="button"` `role="dialog"` 等 ARIA role | 停 — 看 native HTML 能不能用             |
| 行動裝置誤點                                        | 檢查 hit target 大小（最小 44×44 px）    |

---

## 為什麼 a11y 是預設不是補丁

A11y 不是「完整功能後再加上」、是**設計時就決定的結構**：

- 用 `<button>` vs `<div onclick>` → 鍵盤 / focus / a11y tree 自帶 vs 全部要自己補
- modal 用 `<dialog>` vs 自己組 → focus trap / escape / scrollable / inert 自帶 vs 全部要自己補
- 動態內容變動有 aria-live vs 沒 → screen reader 知道 vs 不知道

**事後補 a11y 比事前設計貴 5-10 倍**。寫之前先選對結構、後續成本低。

---

## 防線 1：靜態鍵盤可達性三要素

鍵盤使用者要能用、三個元素缺一不可：

### 要素 1：Visible focus indicator

```css
/* 反例：去掉預設 focus outline */
button:focus { outline: none; }

/* 對例：可見的 focus indicator */
button:focus-visible {
  outline: 2px solid var(--focus-color);
  outline-offset: 2px;
}
```

`:focus-visible`（鍵盤 focus）跟 `:focus`（含滑鼠 click 後）區分 — 滑鼠使用者不需要看到 outline、鍵盤使用者必須看到。

### 要素 2：邏輯 Tab 順序

Tab 順序預設由 DOM tree 決定。如果視覺順序跟 DOM 順序不同（例如用 CSS grid 重排），考慮：

- 重排 DOM 順序對齊視覺
- 用 `tabindex="0"` 讓元素可 focus（不要用 > 0）
- 不要用 `tabindex="-1"` 跳過該 focus 的元素

### 要素 3：Modal / drawer 有 escape 路徑

```js
dialog.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') dialog.close();
});
```

或用 `<dialog>` native — `Escape` 自帶。

---

## 防線 2：動態 a11y

### Focus management on DOM move

JS reparent / hide 元素時、focus 會跑掉（落到 body）。需要保存與還原：

```js
function moveFilter(targetSlot) {
  const filter = document.querySelector('.filter');
  const focused = document.activeElement;
  const wasFilterFocused = filter.contains(focused);

  targetSlot.appendChild(filter);  // reparent

  if (wasFilterFocused) {
    focused.focus();  // 還原 focus
  }
}
```

### aria-live 廣播動態變動

Screen reader 預設不會朗讀「DOM 變動」、要明確告訴它：

```html
<!-- polite：等使用者操作完才朗讀（搜尋結果數量、filter 切換） -->
<div aria-live="polite" aria-atomic="true">
  顯示 12 筆結果
</div>

<!-- assertive：立刻打斷朗讀（錯誤訊息、緊急狀態） -->
<div aria-live="assertive" role="alert">
  搜尋失敗、請重試
</div>
```

`aria-atomic="true"` 整段重讀（不只朗讀變動的部分）。

### 範例：搜尋結果區

```html
<div class="results" aria-live="polite" aria-atomic="false">
  <p class="status">顯示 <span id="count">12</span> 筆結果</p>
  <ul>...</ul>
</div>
```

JS 更新 `#count` 的 textContent 時、screen reader 朗讀「顯示 12 筆結果」。

---

## 防線 3：Native HTML > ARIA

### 為什麼優先 Native

| 元素                  | Native 自帶                                               | ARIA 補強需要                                                                    |
| --------------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `<button>`            | Tab focus、Enter/Space 觸發、a11y role、disabled 狀態     | `role="button"` + tabindex + keydown listener + aria-disabled                    |
| `<dialog>`            | Modal focus trap、Escape 關閉、`::backdrop`、`inert` 外層 | `role="dialog"` + aria-modal + 自寫 focus trap + Escape handler + inert polyfill |
| `<details>`           | Toggle 展開、鍵盤、a11y                                   | `role="region"` + aria-expanded + 自寫 click handler + keyboard support          |
| `<fieldset>+<legend>` | 群組 a11y、screen reader 讀 legend                        | `role="radiogroup"` + aria-labelledby                                            |
| `<input type="...">`  | 各種 input 的 native UX、validation、a11y                 | 全部自寫                                                                         |

### 何時用 ARIA

ARIA 是補強、不是替代：

- 用 native 但 a11y tree 還不夠（標 aria-label / aria-describedby 補語意）
- 真的沒有 native 元素（complex composite widget、tabs、tree）
- 動態變動需要廣播（aria-live）

### 範例：自製 toggle 還是 native checkbox

**錯**：

```html
<div class="toggle" role="switch" tabindex="0" aria-checked="false">
  <span class="track"></span>
</div>
<script>
  toggle.addEventListener('click', ...);
  toggle.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') ...;
  });
</script>
```

**對**：

```html
<label class="toggle">
  <input type="checkbox">
  <span class="track" aria-hidden="true"></span>
  <span class="visually-hidden">啟用 dark mode</span>
</label>
```

```css
.toggle input { position: absolute; opacity: 0; }
.toggle input:checked + .track { background: var(--brand); }
```

Native checkbox 自帶 keyboard / focus / state、CSS 把它隱藏、視覺用 `.track` 呈現。

---

## 視覺 / Motor a11y

### 視覺輔助

```css
/* 對比度 */
:root { --text: #1a202c; --bg: #fff; }
/* WCAG AA: 普通文字 4.5:1、大文字 3:1 */

/* 字型放大時不破版 */
.container { max-width: 60ch; }  /* ch 跟字型同步 */
.text { font-size: 1rem; line-height: 1.6; }  /* rem 跟使用者設定同步 */

/* prefers-reduced-motion */
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

### Motor / Hit target

```css
/* 觸控 hit target 最小 44×44 px (WCAG AAA) */
button, a, [role="button"] {
  min-height: 44px;
  min-width: 44px;
}

/* 兩個 hit target 之間留 8px+ 間距、避免誤點 */
.toolbar > * + * { margin-left: 8px; }
```

---

## Wrong vs Right 對照

### 範例 1：自製 dropdown

**錯**：

```html
<div class="dropdown" tabindex="0">
  <span>選單</span>
  <div class="menu">
    <div class="item">選項 1</div>
    <div class="item">選項 2</div>
  </div>
</div>
```

問題：no native focus、no keyboard、no a11y role、screen reader 不知道是 menu。

**對**：

```html
<button aria-haspopup="menu" aria-expanded="false" aria-controls="menu1">
  選單
</button>
<ul id="menu1" role="menu" hidden>
  <li role="menuitem"><button>選項 1</button></li>
  <li role="menuitem"><button>選項 2</button></li>
</ul>
```

或如果是「選擇一個」 → `<select>` native。

### 範例 2：filter 切換沒 a11y broadcast

**錯**：

```js
button.addEventListener('click', () => {
  document.querySelectorAll('.result').forEach(r => {
    r.style.display = r.dataset.tag === currentFilter ? 'block' : 'none';
  });
});
// screen reader 不知道結果變了
```

**對**：

```html
<div class="results" aria-live="polite">
  <p class="status">顯示 <span id="count">12</span> 筆結果（filter: <span id="filter">全部</span>）</p>
</div>
```

```js
button.addEventListener('click', () => {
  // ... filter logic
  document.getElementById('count').textContent = visibleCount;
  document.getElementById('filter').textContent = currentFilter;
  // aria-live 自動朗讀
});
```

### 範例 3：JS 移動元素 focus 跑掉

**錯**：

```js
// resize 時把 filter 從 mobile drawer 移到 desktop sidebar
mediaQuery.addEventListener('change', () => {
  if (mediaQuery.matches) {
    sidebar.appendChild(filter);
  } else {
    drawer.appendChild(filter);
  }
});
// 如果 filter 內的某個 input 有 focus、reparent 後 focus 落到 body
```

**對**：

```js
mediaQuery.addEventListener('change', () => {
  const focused = document.activeElement;
  const wasInFilter = filter.contains(focused);

  if (mediaQuery.matches) {
    sidebar.appendChild(filter);
  } else {
    drawer.appendChild(filter);
  }

  if (wasInFilter) focused.focus();  // 還原 focus
});
```

---

## 自檢清單（dogfooding）

寫互動 UI 時：

- [ ] 用 `<button>` `<dialog>` `<details>` `<fieldset>` 取代自製 ARIA 結構？
- [ ] visible focus indicator 沒被 `outline: none` 拿掉？
- [ ] Tab 順序符合視覺順序（沒用 `tabindex > 0`）？
- [ ] Modal / drawer 有 Escape 關閉路徑？
- [ ] JS reparent / hide 時保存與還原 focus？
- [ ] 動態變動內容用 `aria-live` 廣播？
- [ ] 對比度 ≥ 4.5:1（普通文字）？
- [ ] Hit target ≥ 44×44 px？
- [ ] `prefers-reduced-motion` 時關掉動畫？

---


**Last Updated**: 2026-04-26
**Version**: 0.1.0
