# Reactive Performance

前端 reactive 效能的盤點與優化：MutationObserver 三維度（root / options / debounce）、polling → observer、iteration / regex / reflow / lazy load 四個成本面。

適用：使用者反映卡頓、CPU 100%、scroll lag、resize jank、首次互動延遲。
不適用：純後端效能、純伺服器渲染（SSR 的成本另一套）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋四個效能風險面向、observer 設計準則、量測方法。

---

## 何時參閱本文件

| 訊號                                                        | 該做的第一件事                                   |
| ----------------------------------------------------------- | ------------------------------------------------ |
| 使用者打字時搜尋頁卡頓                                      | 量 input listener / observer 觸發頻率            |
| Scroll 時掉幀                                               | 量 scroll listener 觸發頻率 + reflow 成本        |
| Resize 視窗時 layout 跳動                                   | 量 ResizeObserver 觸發 + 重新計算成本            |
| CPU 100%、即使頁面靜止                                      | 找 setInterval / setTimeout polling、換 observer |
| 結果規模大（> 500 筆）時慢                                  | 量 iteration cost、看是否每筆都跑 regex          |
| 首次互動延遲（搜尋頁 200ms+ 才能輸入）                      | 量 critical path、看 lazy chunk 是否要 preload   |
| 即將寫 `observer.observe(document.body, { subtree: true })` | 停 — 範圍過寬、補上限制                          |

---

## 為什麼 reactive 效能要主動盤點

Reactive 系統的成本不是線性 — 一個觸發頻率失控的 listener 會放大整個系統的負擔：

- 一個 observer 觸發 → callback 執行 → DOM 變動 → 再觸發 observer → 無限迴圈
- 一個 input listener 沒 debounce → 每個鍵盤事件跑一次重 query → CPU 飆高
- 一個 setInterval polling 50ms → 永遠不停、即使頁面背景

主動盤點 = 寫之前先估觸發頻率、寫之後用 `console.count` 驗證。事後 debug 比事前設計貴 10 倍。

---

## 風險面向 1：Listener 觸發頻率

### MutationObserver 三維度

| 維度     | 預設                  | 過寬訊號                                                   |
| -------- | --------------------- | ---------------------------------------------------------- |
| Root     | 最窄（具體 element）  | `document.body` / `document.documentElement`               |
| Options  | `{ childList: true }` | `{ subtree: true, attributes: true, characterData: true }` |
| Debounce | 0ms 或微 microtask    | 沒寫 debounce、callback 執行 > 5ms                         |

### 過寬範例

```js
// 監聽整個 page 任何變動
new MutationObserver(cb).observe(document.body, {
  childList: true,
  subtree: true,
  attributes: true,
  characterData: true,
});
// 一次 react state 變動 → 100+ 個 callback
```

### 對例

```js
const root = document.querySelector('.pagefind-ui__results-area');
let timer;
new MutationObserver(() => {
  clearTimeout(timer);
  timer = setTimeout(callback, 100);  // debounce 100ms
}).observe(root, { childList: true });
// 只監聽 results 直接子節點變動、debounce 100ms
```

### 量觸發頻率

```js
let count = 0;
new MutationObserver(() => {
  count++;
  console.log('mutation', count);
}).observe(...);

// 預期：使用者打字 1 秒、觸發 10 次以下
// 觀察：100+ 次 → 範圍過寬、加 debounce 或縮 root
```

或用 `console.count('decorate')` 計數、看每秒觸發幾次。

---

## 風險面向 2：Polling 換 Observer

### 反例：setInterval polling

```js
const timer = setInterval(() => {
  const el = document.querySelector('.target');
  if (el) {
    decorate(el);
    clearInterval(timer);
  }
}, 50);
```

問題：CPU 50% busy waiting、即使元素永遠不出現、interval 永遠跑。

### 對例：MutationObserver + fast-path

```js
function waitForElement(selector, root = document.body) {
  return new Promise(resolve => {
    const existing = root.querySelector(selector);
    if (existing) return resolve(existing);

    const obs = new MutationObserver(() => {
      const el = root.querySelector(selector);
      if (el) {
        obs.disconnect();
        resolve(el);
      }
    });
    obs.observe(root, { childList: true, subtree: true });
  });
}
```

Fast-path 先檢查（如果已經在 DOM 立即返回）、否則 observer 等元素出現。0 latency、0 idle CPU、元素出現立刻觸發。

---

## 風險面向 3：Iteration / Regex 成本

### 反例：每筆結果跑重 regex

```js
const results = await pagefind.search(query);
const filtered = results.results.filter(r => /complex|regex|here/i.test(r.excerpt));
// 500 筆 × regex test = 500 次 regex 編譯與執行
```

### 對例：regex compile 一次、用 cached version

```js
const re = /complex|regex|here/i;
const filtered = results.results.filter(r => re.test(r.excerpt));
// regex 只編譯一次、test 每次便宜
```

### 量 iteration 成本

```js
console.time('filter');
const filtered = results.filter(...);
console.timeEnd('filter');
// 觀察：> 16ms → 影響 60fps、要優化
```

### 大資料量的常用優化

| 問題           | 優化                           |
| -------------- | ------------------------------ |
| 每筆都跑 regex | regex 編譯一次、test 重用      |
| 每筆 query DOM | DOM query 一次、緩存結果       |
| 排序 N²        | 用 `Array.sort()` (N log N)    |
| 全量過濾後分頁 | 分頁邊界提前 break、不跑完全部 |

---

## 風險面向 4：Layout Reflow 成本

Reflow（重新計算 layout） > Repaint（重繪） > Composite（合成）— 三者成本遞減。

### Reflow 觸發訊號

| 操作                             | 成本                                  |
| -------------------------------- | ------------------------------------- |
| 改 width / height / top / margin | Reflow（layout 變動）                 |
| 改 color / background            | Repaint（不影響 layout）              |
| 改 transform / opacity           | Composite（GPU、最便宜）              |
| 讀 `getBoundingClientRect()`     | 強制 sync reflow（如果 pending 變動） |

### 反例：read-write-read-write 觸發 layout thrashing

```js
elements.forEach(el => {
  const w = el.offsetWidth;       // read
  el.style.width = `${w * 2}px`;  // write
  const h = el.offsetHeight;      // read（強制 reflow）
  el.style.height = `${h * 2}px`; // write
});
// 每次 read 觸發一次 reflow、N 個元素 = N 次 reflow
```

### 對例：批量 read、批量 write

```js
const sizes = elements.map(el => ({
  el, w: el.offsetWidth, h: el.offsetHeight,
}));
sizes.forEach(({ el, w, h }) => {
  el.style.width = `${w * 2}px`;
  el.style.height = `${h * 2}px`;
});
// 1 次 reflow、性能提升 N 倍
```

### 量 reflow 成本

Chrome DevTools Performance panel → 找 "Layout" 紫色塊。> 16ms 要優化。

---

## 風險面向 5：資源載入時序

### Critical path vs lazy chunk

| 資源                  | 該不該 lazy                       |
| --------------------- | --------------------------------- |
| 首屏需要的 CSS / JS   | 否（critical path、preload）      |
| 搜尋頁的 search index | 是（使用者進搜尋頁前不需要）      |
| Footer 圖片           | 是（lazy load on scroll）         |
| 跟首屏互動相關的 JS   | 否（input listener 要立刻 ready） |

### 範例：搜尋頁的 lazy chunk

```html
<!-- 搜尋頁進來時、preload 第一個 chunk -->
<link rel="preload" href="/_pagefind/pagefind-entry.json" as="fetch" crossorigin>
<link rel="preload" href="/_pagefind/pagefind.js" as="script">

<script type="module">
  import('/_pagefind/pagefind.js').then(p => p.init());
</script>
```

不 preload 的代價：使用者進搜尋頁 → 點 input → 等 200-500ms 才能搜尋。

### 量 critical path

Chrome DevTools Network panel → 看每個資源的 timing。Slow 3G throttle 模擬真實使用者環境。

---

## 盤點 reactive listener 的協議

對複雜頁面（搜尋頁、dashboard）做一次性盤點：

```js
// 1. 列出所有 observer / listener
console.log({
  mutationObservers: window.observers,  // 自家紀錄
  resizeObservers: window.resizeObservers,
  inputListeners: '...',
});

// 2. 加 console.count 在每個 callback
const decorateCount = (() => { let c = 0; return () => { console.count(`decorate ${++c}`); }; })();

// 3. 操作頁面 1 分鐘、看 console
// 4. 任何 callback 執行 > 100 次/分鐘 → 評估是否需要 debounce / 縮範圍
```

定期盤點（每加新 observer 後）= 主動發現觸發頻率失控、不等使用者抱怨。

---

## Wrong vs Right 對照

### 範例 1：搜尋頁打字卡頓

**錯**：

```js
input.addEventListener('input', () => {
  // 每個鍵盤事件都重 query 整個 results、重排版
  const results = expensiveQuery(input.value);
  renderResults(results);
});
```

**對**：

```js
let timer;
input.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    const results = expensiveQuery(input.value);
    renderResults(results);
  }, 200);  // debounce 200ms
});
```

### 範例 2：等元素出現

**錯**：

```js
const timer = setInterval(() => {
  if (document.querySelector('.target')) {
    decorate();
    clearInterval(timer);
  }
}, 100);
```

**對**：

```js
new MutationObserver((mutations, obs) => {
  if (document.querySelector('.target')) {
    obs.disconnect();
    decorate();
  }
}).observe(document.body, { childList: true, subtree: true });
// 注意：subtree 只在「等元素出現」場景可接受、決完後 disconnect
```

---

## 自檢清單（dogfooding）

寫 reactive code 或 perf debug 時：

- [ ] MutationObserver root 是不是最窄能達成目標的 element？
- [ ] options 是不是只開必要的（`childList` 預設、`subtree` 要有理由、`attributes` 不是預設）？
- [ ] 重 callback 有沒有 debounce / throttle？
- [ ] setInterval / setTimeout polling 能不能換成 MutationObserver？
- [ ] iteration / regex 在大資料量下測過嗎？> 16ms 要優化
- [ ] 改 layout 屬性有沒有 batch read-write、避免 layout thrashing？
- [ ] Lazy chunk 是 critical path 還是真的 lazy？

---


**Last Updated**: 2026-04-26
**Version**: 0.1.0
