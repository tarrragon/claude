# Tool Switching Timing

何時從靜態推理切換到量測工具、何時從 DevTools 升級到 Playwright、何時把 debug 過程寫成測試。

適用：CSS / DOM debug、layout 卡關、不確定該用哪個工具。
不適用：純邏輯 bug（這時 logging / debugger 比 layout 工具有用）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋四種工具的 ROI 對照、切換時機、最低門檻入口。

---

## 何時參閱本文件

| 訊號                                           | 該做的第一件事                              |
| ---------------------------------------------- | ------------------------------------------- |
| 推理 ≥ 2 次失敗                                | 切到 playwright `browser_evaluate`          |
| 視覺截圖溝通迴圈卡住、雙方對「哪裡不對」沒共識 | 切到 playwright + 量化資料（rect / style）  |
| Layout 在某些狀態下錯、其他狀態下對            | 切到 playwright、量不同狀態的 bounding rect |
| 改 CSS 不生效、specificity 看起來對            | 切到 playwright、量 computed style          |
| 同一個版型 bug 第 2 次出現                     | 切到「寫成 playwright 測試」固化            |
| 一次性確認 DOM 結構、不會重複查                | 用 DevTools 即可、不需要起 server           |

---

## 為什麼工具切換要早、不該等到推理徹底失敗

CSS 行為由「規則 + DOM tree + 樣式繼承 + 框架渲染」四個變數共同決定。**靜態推理只能基於假設的 DOM tree** — 假設錯了、推理就錯。視覺截圖只能傳達「結果是什麼」、無法傳達「為什麼」。

Playwright 的 `browser_evaluate` 直接執行 JS 在 live page、返回真實的 DOM tree、computed style、bounding rect — **把四個變數全部變成已知**。

**門檻在第 2 次**：第 1 次推理快（假設正確時一次到位）；第 2 次推理失敗 → 假設可能錯 → 繼續推理會在錯誤假設上累積。Playwright 起步成本中、但後續穩定。

---

## 四種工具的 ROI 對照

| 方法                          | 取得資訊量            | 起步成本 | 重複成本 | 可寫成測試               |
| ----------------------------- | --------------------- | -------- | -------- | ------------------------ |
| 靜態 CSS 推理                 | 低 — 全是假設         | 0        | 高       | 否                       |
| 視覺截圖溝通                  | 中 — 只有結果         | 低       | 中       | 否                       |
| 瀏覽器 DevTools               | 高 — DOM + computed   | 低       | 中       | 否                       |
| Playwright `browser_evaluate` | 最高 — 程式化任意查詢 | 中       | 低       | 是 — 同樣 query 可寫測試 |

**選擇順序**：

| 情境                                    | 工具                          |
| --------------------------------------- | ----------------------------- |
| 第 1 次推理（簡單修改、假設正確機率高） | 靜態推理 + 截圖               |
| 一次性確認、不重複查                    | DevTools                      |
| 推理 ≥ 2 次失敗 / 反覆 debug            | Playwright `browser_evaluate` |
| 同個版型 bug 第 2 次以上                | Playwright 測試固化           |

---

## Playwright 在開發循環的三個位置

### 位置 1：假設驗證（寫 CSS 規則前）

確認 DOM 結構符合假設。

```js
async () => {
  const drawer = document.querySelector('.pagefind-ui__drawer');
  let chain = []; let n = drawer;
  while (n && n !== document.body) {
    chain.push(`${n.tagName}.${n.className}`);
    n = n.parentElement;
  }
  return chain;
}
```

返回值對照假設、發現 `drawer` 是 `form` 的 child（不是 sibling）→ grid-row 控制無效、改方向。

### 位置 2：行為驗證（layout 規則寫完後）

驗證實際 layout 結果。

```js
async () => ({
  rect: document.querySelector('.target').getBoundingClientRect(),
  computedTop: getComputedStyle(document.querySelector('.target')).top,
  computedDisplay: getComputedStyle(document.querySelector('.target')).display,
})
```

### 位置 3：互動驗證（使用者操作後的狀態）

```js
async () => {
  const input = document.querySelector('.search-input');
  input.value = 'pre';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise(r => setTimeout(r, 1000));
  return Array.from(document.querySelectorAll('.result'))
    .filter(el => getComputedStyle(el).display !== 'none')
    .map(el => el.textContent.slice(0, 50));
}
```

---

## 第 2 次同個 bug → 寫成測試固化

第 1 次 debug 完、bug 修好。第 2 次同個版型問題（不同 commit / 不同 viewport）再出現 → **debug 完後把 query 寫成 playwright 測試**。

```js
test('search scope is between form and results', async ({ page }) => {
  await page.goto('/search/?q=pre');
  const formRect = await page.locator('.pagefind-ui__form').boundingBox();
  const scopeRect = await page.locator('.scope-toggle').boundingBox();
  const resultsRect = await page.locator('.results').boundingBox();
  expect(scopeRect.y).toBeGreaterThan(formRect.y + formRect.height);
  expect(resultsRect.y).toBeGreaterThan(scopeRect.y + scopeRect.height);
});
```

未來 layout 改動觸發 regression、CI 立刻發現、不需要再人工 debug。

---

## Playwright 引入的最低門檻

```bash
# 起本地 server（任何方式）
python3 -m http.server 8000 --directory public
# 或 hugo server
hugo server
```

Playwright MCP 提供的核心工具：

- `browser_navigate(url)` — 開頁
- `browser_evaluate(fn)` — 執行 JS 拿結果
- `browser_take_screenshot()` — 截圖
- `browser_snapshot()` — accessibility tree

寫一個 evaluate fn ≈ 30 行 JS。比反覆推理快得多。

---

## 主動切換訊號（不要等使用者打斷）

當以下任一觸發、執行者要主動提：「我推理 2 次失敗了、我們起 server、用 playwright 量 live DOM 確認假設」。**不要等到第 5 次才切**。

| 訊號                                          | 對外回報句式                                            |
| --------------------------------------------- | ------------------------------------------------------- |
| 同方向 CSS 規則改了 2 次都不生效              | 「我假設 X 是 Y、playwright 一查就知道、要起 server？」 |
| 截圖看起來對 / 不對、但雙方對「為什麼」沒共識 | 「用 playwright 量 bounding rect、量化比較好？」        |
| 改完 JS 後元素被還原                          | 「playwright 量 framework 重渲染週期、確認時機」        |
| Layout 在某些 state 下錯、其他對              | 「我用 playwright 各 state 量一次 rect、做對照」        |

---

## Wrong vs Right 對照

### 範例 1：CSS 不生效

**錯**：

```css
/* 改了 3 次 specificity、還是沒生效 */
.target { color: red; }                    /* 失敗 */
.parent .target { color: red; }            /* 失敗 */
.parent .container .target { color: red; } /* 失敗 */
.parent .container .target { color: red !important; } /* 失敗 */
```

**對**：

```css
.target { color: red; }
```

第 2 次失敗 → 切 playwright：

```js
async () => getComputedStyle(document.querySelector('.target')).color
// 返回 "rgb(0, 0, 255)" — 不是我寫的紅色
```

```js
async () => {
  const el = document.querySelector('.target');
  return Array.from(getMatchedCSSRules?.(el) || [])
    .map(r => r.cssText);
}
// 看到 vendor 的 .pagefind .target { color: blue !important } 在贏
```

→ 換方向：用 CSS Layers 把 vendor CSS 包進 layer、自家 unlayered 自動贏。

### 範例 2：Layout 在 mobile viewport 錯

**錯**：

反覆推理 + 在 DevTools 切 viewport 視覺確認 → 改 → 失敗 → 改 → 失敗。

**對**：

第 2 次推理失敗、切 playwright：

```js
async () => {
  await page.setViewportSize({ width: 375, height: 667 });
  return {
    h1: document.querySelector('h1').getBoundingClientRect(),
    form: document.querySelector('form').getBoundingClientRect(),
    scope: document.querySelector('.scope').getBoundingClientRect(),
  };
}
```

量化資料 → 立刻看到「scope 的 top 比 form 的 bottom 小 12px」→ overlap → 改 form margin-bottom。

---

## 自檢清單（dogfooding）

debug 卡關時：

- [ ] 我推理失敗幾次了？≥ 2 次 → 該切換工具
- [ ] 我能說出「假設是什麼、用什麼工具能驗證」嗎？
- [ ] 切到 playwright 之前、有沒有試圖用更努力的推理多撐一次？（如果有 → 停）
- [ ] 第 2 次同個版型 bug 出現時、有沒有寫成測試固化？
- [ ] 對外回報切換工具的提案、有沒有寫得具體（要起哪個 server、量什麼）？

---

**Last Updated**: 2026-04-26
**Version**: 0.1.0
