# 用前端測試把排版問題自動化

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 reference `playwright-in-loop.md` 與 `data-flow-and-filter-composition.md`（layout test 寫死合成策略）引用。
>
> **何時讀**：同一個版型 bug 出現第 2 次、想把規範固定下來防回歸；或要決定哪些 layout 契約值得寫成自動化測試、哪些用手動 / visual regression 更合適。

---

## 核心原則

**當一個版型被 debug 兩次以上、就值得寫成 playwright 測試。** 測試替代「手動檢查 + 截圖」的循環、讓版型回歸可被機器發現。下次有人改 CSS 時、測試會立刻指出哪個假設被破壞。

---

## 為什麼版型問題適合自動化

### 商業邏輯

排版問題的特徵：

| 特徵                                   | 對手動檢查的不利             |
| -------------------------------------- | ---------------------------- |
| 邊界條件多（viewport、字型、互動狀態） | 人眼難以涵蓋全部組合         |
| 變動觸發點不明顯（改 token、改 theme） | 改一處不知道哪裡會壞         |
| 視覺問題往往來自相對關係               | 截圖只看絕對位置、看不出關係 |

人腦適合「驚訝時注意」、不適合「重複檢查 100 個 case 是否如預期」。後者是機器擅長的。

### 兩種測試層次

| 層次     | 測什麼                       | 工具                                     |
| -------- | ---------------------------- | ---------------------------------------- |
| 視覺迴歸 | 整頁與基準截圖比對           | Percy / Chromatic / Playwright snapshot  |
| 結構斷言 | 特定元素的位置 / 尺寸 / 順序 | Playwright `browser_evaluate` + `expect` |

兩種互補。視覺迴歸抓「整頁有沒有變」、結構斷言抓「特定關係有沒有保持」。

---

## 結構斷言測試的形狀

```js
// tests/page-layout.spec.js
import { test, expect } from '@playwright/test';

test.describe('page layout', () => {
  test('desktop ≥ 1400 顯示左側 filter sidebar', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/path/to/page/');
    await page.fill('.search-input', 'pre');
    await page.waitForSelector('.filter-panel');

    const slot = await page.$('.filter-slot');
    const isVisible = await slot.isVisible();
    expect(isVisible).toBe(true);

    const filterParent = await page.evaluate(() =>
      document.querySelector('.filter-panel').parentElement.className
    );
    expect(filterParent).toContain('filter-slot');
  });

  test('viewport < 1400 filter 留在 drawer', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 900 });
    await page.goto('/path/to/page/');
    await page.fill('.search-input', 'pre');
    await page.waitForSelector('.filter-panel');

    const filterParent = await page.evaluate(() =>
      document.querySelector('.filter-panel').parentElement.className
    );
    expect(filterParent).toContain('drawer');
  });

  test('scope UI 在三互動狀態下都在 input 與 results 之間', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/path/to/page/');

    async function getY(selector) {
      return page.evaluate(s => document.querySelector(s).getBoundingClientRect().y, selector);
    }

    // 狀態 1：初始載入
    let scopeY = await getY('.scope');
    let inputY = await getY('.search-input');
    expect(scopeY).toBeGreaterThan(inputY);

    // 狀態 2：點 input
    await page.click('.search-input');
    scopeY = await getY('.scope');
    inputY = await getY('.search-input');
    expect(scopeY).toBeGreaterThan(inputY);

    // 狀態 3：輸入字
    await page.fill('.search-input', 'pre');
    await page.waitForSelector('.results .result');
    scopeY = await getY('.scope');
    inputY = await getY('.search-input');
    const resultsY = await getY('.results');
    expect(scopeY).toBeGreaterThan(inputY);
    expect(scopeY).toBeLessThan(resultsY);
  });
});
```

每個 `expect` 對應一條版型契約 — 這條被破壞時測試紅、改 CSS 的人立刻知道。

---

## 測試的維護成本與收益

### 內在屬性比較

| 屬性     | 手動檢查                | Playwright 測試        |
| -------- | ----------------------- | ---------------------- |
| 首次成本 | 低 — 開頁面看           | 中 — 寫測試            |
| 重複成本 | 高 — 每次回歸都要全部看 | 低 — 自動跑            |
| 涵蓋率   | 低 — 受人記憶限制       | 高 — 跑所有 case       |
| 規範化   | 否 — 知識在腦中         | 是 — 寫成可讀的 expect |
| 教學價值 | 低 — 新人需要被告知     | 高 — 測試本身是文件    |

第 1 次寫成本中、第 2 次以後成本碾壓手動。**門檻在「會 debug 第 2 次嗎」**。

---

## 測試什麼、不測什麼

### 適合測試的版型場景

- 跨 viewport 的元件顯示 / 隱藏切換
- 元件相對位置（A 在 B 上方 / 下方 / 左右）
- 元件順序（type 在 tag 前）
- 互動狀態下的位置不變（scope 在三狀態下都在 input 與 results 之間）

### 不適合用 playwright 測

- 純視覺差異（顏色微差、圓角 1px 差） — 用 visual regression 工具
- 動畫過程 — 不穩定、容易 flaky
- 字型 rendering 細節 — 跨 OS / 瀏覽器差異大

選擇原則：**測「結構性契約」、不測「畫素」**。畫素級檢查交給 visual regression。

---

## 設計取捨：版型驗證機制的選擇

四種做法、各自機會成本不同。版型 debug ≥ 2 次後選 A（結構斷言測試）當預設、其他做法在特定情境合理。

本原則是 [2 次門檻](./two-occurrence-threshold.md) 抽象原則在「驗證機制升級」這個面向的應用。

### A：Playwright 結構斷言測試（預設）

- **機制**：寫 `expect(scopeY > inputY)` 這類斷言、自動跑、跨字型 / 主題都對
- **選 A 的理由**：規範化（測試本身是文件）、跨環境穩定、回歸自動偵測
- **適合**：debug ≥ 2 次的版型場景、需要長期保護的 layout 契約
- **代價**：寫測試的初始成本、需要 playwright runtime

### B：手動截圖檢查

- **機制**：開頁面、看截圖、人眼確認
- **跟 A 的取捨**：B 起步成本 0、A 起步成本中；但 B 重複成本高（每次回歸都要看）
- **B 比 A 好的情境**：第 1 次驗證（debug 過 1 次、不確定值不值得寫測試）、純探索期

### C：Visual regression snapshot

- **機制**：截整頁圖跟 baseline 比對、像素級差異
- **跟 A 的取捨**：C 涵蓋率廣（整頁所有變動都偵測）、A 只測指定契約；但 C false positive 多（字型微調 / theme 換色都觸發）
- **C 比 A 好的情境**：純視覺驗證（marketing page）、設計穩定不常改

### D：不寫測試

- **機制**：純信任手動驗證
- **跟 A 的取捨**：D 0 維護成本、A 有測試維護；但 D 在版型反覆壞時累積「腦中知識」、新人接手不知道
- **D 才合理的情境**：純探索期 / prototype、確定不上 production

---

## 判讀徵兆

| 訊號                                  | 應該寫測試的時機            | 第一個該寫的 expect        |
| ------------------------------------- | --------------------------- | -------------------------- |
| 同一個版型 bug 出現第 2 次            | 立刻寫                      | 把當時的 fix 寫成 expect   |
| 改 token / theme 時不確定哪些頁面會壞 | 把對 token 敏感的頁面寫測試 | 元件相對位置、寬度比例     |
| 跨 viewport 的響應式邏輯複雜          | 寫 viewport 切換測試        | 不同寬度下元件顯示 / 位置  |
| 互動狀態下版型不穩定                  | 寫狀態切換測試              | 各狀態下關鍵元素的位置關係 |

**核心原則**：版型契約用測試固定 — 測試紅了表示契約被打破、不是測試壞了。每個紅色測試都是有人改了不該改的東西的訊號。

---

## 與其他原則的串連

- [two-occurrence-threshold](./two-occurrence-threshold.md) — 「debug 兩次」就是 2 次門檻在驗證機制升級的應用
- [verification-timeline-checkpoints](./verification-timeline-checkpoints.md) — layout test 是 Checkpoint 3「Ship 前」的具體做法 — 跨 viewport / 跨狀態 / 跨資料規模驗收、catch 開發中 checkpoint 看不到的整合錯
- [test-first-red-before-green](./test-first-red-before-green.md) — 寫完 layout test 必須在「未修版型」跑 RED 確認測試會抓到該抓的、再在「修後版型」跑 GREEN 確認修對了、兩個訊號都看到測試才被驗證
