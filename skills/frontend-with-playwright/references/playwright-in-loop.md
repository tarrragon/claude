# Playwright in the Development Loop

Playwright 在前端開發循環的三個位置：假設驗證（寫 CSS 前）、行為驗證（規則寫完後）、互動驗證（dispatch event 後）。第 2 次同個版型 bug 出現 → 寫成測試固化。

適用：CSS / DOM debug、layout 驗收、互動行為驗證、寫 layout regression test。
不適用：純 unit test（function input/output、無 DOM）— 那用 Vitest / Jest 即可。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋三個位置的具體 query 範例、layout test 模板、最低門檻 setup。

---

## 何時參閱本文件

| 訊號                                                | 該做的第一件事                       |
| --------------------------------------------------- | ------------------------------------ |
| 即將寫 CSS 規則、想先確認 DOM 結構                  | 位置 1：假設驗證 — 量 ancestor chain |
| 規則寫完、想確認實際 layout 對                      | 位置 2：行為驗證 — 量 bounding rect  |
| 想驗證使用者互動後的狀態（filter / search / click） | 位置 3：互動驗證 — dispatch event    |
| 同個 layout bug 第 2 次出現                         | 寫 layout test、CI 防回歸            |
| 不確定 server 怎麼起 / 怎麼接 playwright            | 看下方「最低門檻 setup」             |

---

## 為什麼 playwright 是前端開發的核心驗證工具

CSS / DOM 的真實狀態 = 規則 + DOM tree + 樣式繼承 + 框架渲染的合成結果。靜態推理只能基於假設、視覺截圖只能傳達結果不傳達原因。

Playwright `browser_evaluate` 直接執行 JS 在 live page、返回 DOM tree / computed style / bounding rect — **把假設變成量測值**。寫一個 evaluate fn ≈ 30 行 JS，比反覆推理快得多。

---

## 位置 1：假設驗證（寫 CSS 規則前）

### 量 ancestor chain

```js
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

### 量子節點與 sibling

```js
async () => {
  const parent = document.querySelector('.pagefind-ui');
  return Array.from(parent.children).map(c => `${c.tagName}.${c.className}`);
}
```

### 量元素是否存在 / 數量

```js
async () => ({
  count: document.querySelectorAll('.result').length,
  first: document.querySelector('.result')?.outerHTML.slice(0, 200),
})
```

寫 CSS 規則前 30 秒能省掉後續 30 分鐘推理。

---

## 位置 2：行為驗證（規則寫完後）

### 量 bounding rect

```js
async () => ({
  form: document.querySelector('.pagefind-ui__form').getBoundingClientRect(),
  scope: document.querySelector('.scope').getBoundingClientRect(),
  results: document.querySelector('.results').getBoundingClientRect(),
})
```

返回 `{x, y, width, height, top, right, bottom, left}` 的純物件、能直接 assert 順序與位置。

### 量 computed style

```js
async () => {
  const el = document.querySelector('.target');
  const cs = getComputedStyle(el);
  return {
    display: cs.display,
    position: cs.position,
    gridRow: cs.gridRow,
    color: cs.color,
    zIndex: cs.zIndex,
  };
}
```

### 量「實際贏的 CSS rule」

```js
async () => {
  const el = document.querySelector('.target');
  // CSSOM 沒提供標準 getMatchedCSSRules；用 computed style 加 inspect
  return getComputedStyle(el).cssText;  // 全部 computed properties
}
```

或在 DevTools Computed panel 看 — 但 playwright 能寫成測試重跑。

---

## 位置 3：互動驗證（dispatch event 後讀 state）

### 模擬 input

```js
async () => {
  const input = document.querySelector('.search-input');
  input.value = 'pre';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise(r => setTimeout(r, 1000));  // 等 debounce / async render
  return Array.from(document.querySelectorAll('.result'))
    .filter(el => getComputedStyle(el).display !== 'none')
    .map(el => el.textContent.slice(0, 50));
}
```

### 模擬 click

```js
async () => {
  document.querySelector('.scope-toggle button[data-scope="title"]').click();
  await new Promise(r => setTimeout(r, 500));
  return {
    activeScope: document.querySelector('.scope-toggle [aria-pressed="true"]')?.dataset.scope,
    visibleResults: document.querySelectorAll('.result:not([hidden])').length,
  };
}
```

### 模擬 viewport resize（透過 playwright API、不在 evaluate 內）

```js
await page.setViewportSize({ width: 375, height: 667 });
const result = await page.evaluate(() => ({
  layout: document.querySelector('.layout').getBoundingClientRect(),
  sidebarVisible: getComputedStyle(document.querySelector('.sidebar')).display !== 'none',
}));
```

---

## 第 2 次同個 bug → 寫成 layout 測試固化

第 1 次 debug 完成後、bug 修好。第 2 次同個版型問題（不同 commit / viewport / 內容狀態）再出現 → **debug 完後把 query 寫成 playwright 測試**。

```js
import { test, expect } from '@playwright/test';

test('search scope is between form and results', async ({ page }) => {
  await page.goto('/search/?q=pre');
  await page.waitForSelector('.result');

  const formRect = await page.locator('.pagefind-ui__form').boundingBox();
  const scopeRect = await page.locator('.scope-toggle').boundingBox();
  const resultsRect = await page.locator('.results').boundingBox();

  expect(scopeRect.y).toBeGreaterThan(formRect.y + formRect.height);
  expect(resultsRect.y).toBeGreaterThan(scopeRect.y + scopeRect.height);
});

test('sidebar visible at 1400px+', async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 800 });
  await page.goto('/search/?q=pre');
  await expect(page.locator('.sidebar')).toBeVisible();
});

test('sidebar hidden at < 1400px', async ({ page }) => {
  await page.setViewportSize({ width: 1399, height: 800 });
  await page.goto('/search/?q=pre');
  await expect(page.locator('.sidebar')).toBeHidden();
});
```

未來 layout 改動觸發 regression、CI 立刻發現。

---

## 寫 layout test 的優先順序

不要每個 layout 都寫測試 — 寫測試的 ROI 條件：

| 條件                                    | 該寫測試嗎               |
| --------------------------------------- | ------------------------ |
| Bug 第 1 次出現                         | 否（修了就好）           |
| Bug 第 2 次出現                         | **是**（防回歸）         |
| Layout 跟 viewport 強相關（breakpoint） | 是（容易壞）             |
| Layout 跟 framework 重渲染相關          | 是（升級時需要驗證）     |
| 純視覺風格（顏色 / 字型）               | 否（用視覺 review 即可） |

---

## 最低門檻 setup

### Server

```bash
# 任何方式起本地 server
hugo server                                       # Hugo
python3 -m http.server 8000 --directory public    # 純靜態
npm run dev                                        # framework dev server
```

### Playwright MCP（給 Claude 用）

Claude 透過 MCP 提供的 tool：

- `browser_navigate(url)` — 開頁
- `browser_evaluate(fn)` — 執行 JS 拿結果
- `browser_take_screenshot()` — 截圖
- `browser_snapshot()` — accessibility tree
- `browser_click(selector)` / `browser_type(selector, text)` — 互動

### Playwright 測試（給 CI 用）

```bash
npm i -D @playwright/test
npx playwright install
npx playwright test
```

`playwright.config.ts` 設 baseURL 指向 `http://localhost:1313`（Hugo 預設）或自訂 port。

---

## Wrong vs Right 對照

### 範例 1：CSS 不生效

**錯**：靜態推理 + 截圖溝通 4 次失敗。

**對**：第 2 次失敗 → 切 playwright：

```js
// 1. 確認 ancestor chain
async () => {
  const el = document.querySelector('.target');
  let chain = []; let n = el;
  while (n) { chain.push(`${n.tagName}.${n.className}`); n = n.parentElement; }
  return chain;
}
// → 看到目標元素是 form 的 child、不是 .pagefind-ui 的直接 child

// 2. 確認 computed style 誰贏
async () => getComputedStyle(document.querySelector('.target')).color
// → "rgb(0,0,255)" — vendor 的藍色贏了

// 3. 換方向：用 @layer 把 vendor 包起來
```

### 範例 2：Layout 第 2 次出現一樣的 bug

**錯**：手動在不同 viewport 下視覺驗證、commit、過幾週又壞、又手動驗證。

**對**：第 2 次出現後寫成測試：

```js
test('layout golden path: form → scope → results', async ({ page }) => {
  for (const width of [375, 768, 1024, 1400, 1920]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto('/search/?q=pre');
    const form = await page.locator('.pagefind-ui__form').boundingBox();
    const scope = await page.locator('.scope-toggle').boundingBox();
    expect(scope.y, `at width=${width}`).toBeGreaterThanOrEqual(form.y + form.height);
  }
});
```

未來改 CSS、CI 直接告訴你哪個 viewport 壞了。

---

## RED-GREEN 順序：先看到 RED 才相信 GREEN

寫完 playwright test 後、必須先在「buggy code」跑出 RED 才能相信「fixed code」的 GREEN。詳見 [#69 Test-First：先看到 RED 才相信 GREEN](principles/test-first-red-before-green.md)。

修 bug 的順序：

1. **先寫測試 + 跑 → RED**（在 buggy code 上 fail、證明測試會 catch + bug 真的存在）
2. **修 code**
3. **跑測試 → GREEN**（證明修對了 + 測試會抓回歸）

跳過 step 1 的 retrospective 補救（修完才補測試）：

```bash
# Stash 修復、checkout 修前 commit
git stash && git checkout <pre-fix-commit>

# Cherry-pick 測試 commit、build、跑
git cherry-pick <test-commit>
make site && npm test
# 預期：RED ✓

# 切回修後版本
git checkout main && git stash pop
npm test
# 預期：GREEN ✓
```

兩個訊號都看到 + 順序對、測試才被驗證。

---

## 自檢清單（dogfooding）

debug / 驗證 layout 時：

- [ ] 寫 CSS 規則前、有沒有用 playwright 量過 ancestor chain？
- [ ] 規則寫完後、有沒有用 playwright 量過 bounding rect / computed style 確認？
- [ ] 互動行為（filter / click）有沒有用 playwright 模擬 + 量化驗證？
- [ ] 同個 layout bug 第 2 次出現時、有沒有寫成測試？
- [ ] 推理失敗 ≥ 2 次時、有沒有主動切換到 playwright（不等到第 5 次）？

---


**Last Updated**: 2026-04-26
**Version**: 0.1.0
