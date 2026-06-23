# Failure Pivot Protocol

同方向失敗 ≥ 2 次時的轉折協議 — 停下來驗證底層假設、不沿同方向加碼到第 3 次。

適用：debug 反覆失敗、CSS 規則不生效、JS 改完元素還原、layout 怎麼調都不對。
不適用：第 1 次失敗（修細節即可）；不同方向各自失敗 1 次（不算同方向累積）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋失敗計數、假設驗證、換方向決策、對外回報模板。

---

## 何時參閱本文件

| 訊號                                 | 該做的第一件事                |
| ------------------------------------ | ----------------------------- |
| 同方向第 2 次失敗                    | 停 — 用工具驗證底層假設       |
| 內心 OS：「再試一次更小心應該就過」  | 停 — 這是沉沒成本綁住的訊號   |
| 即將加 `!important` 解 specificity   | 停 — 切到 CSS layers 思路     |
| 即將加第 2 條 polyfill 補跨瀏覽器    | 停 — 先回報成本、問使用者意願 |
| 即將用 imperative JS 補宣告式 layout | 停 — 切到 CSS-first 思路      |

---

## 為什麼第 2 次是轉折點

第 1 次失敗常是執行細節（typo、cache、syntax）— 修了再試通常會過。

第 2 次失敗、用同樣的方法但更小心、還是失敗 — 訊號的重量遠大於兩次相加。它說的是：**「我以為的問題不在這層、根本問題在別處」**。

第 3 次以上、沉沒成本綁住、加碼產生的副作用會超過解決的問題：

| 嘗試次數 | 心理狀態     | 行動模式                                  | 副作用                |
| -------- | ------------ | ----------------------------------------- | --------------------- |
| 1        | 信心足       | 直接做                                    | 無                    |
| 2        | 信心動搖     | 加碼（更複雜的 selector / important）     | 可控                  |
| 3        | 焦慮         | 全面反擊（layers + important + polyfill） | 大 — 改動範圍擴張     |
| 4+       | 沉沒成本綁住 | 不肯放棄已寫的                            | 嚴重 — 為前面的錯買單 |

第 2 次是還能優雅切換方向的最後機會。

---

## 失敗計數的協議

| 失敗次數      | 行動                                                                        |
| ------------- | --------------------------------------------------------------------------- |
| 第 1 次       | 修細節（typo、cache、syntax）再試                                           |
| 第 2 次       | **停下來** — 用工具驗證底層假設（DOM tree、computed style、framework 行為） |
| 第 2 次驗證後 | 假設對 → 繼續修；假設錯 → 換方向、不為前面買單                              |

關鍵動作是第 2 次的「停」 — 把行動從「執行更努力」切換到「驗證假設」。

---

## 假設驗證的具體方法

### 方法 1：用工具讀真實狀態

| 假設類型       | 驗證工具                                           |
| -------------- | -------------------------------------------------- |
| DOM 結構       | playwright `browser_evaluate` 讀 ancestor chain    |
| Computed style | playwright + `getComputedStyle()`                  |
| 元素位置       | playwright + `getBoundingClientRect()`             |
| Framework 行為 | 讀框架 source、看 reconciliation 條件              |
| Event 觸發     | DevTools Event Listeners panel + `console.count()` |

### 方法 2：反問「如果假設錯了會怎樣」

這個反思能在沒有工具的情況下測試假設。

| 假設                      | 如果錯了會發生什麼                                    |
| ------------------------- | ----------------------------------------------------- |
| Drawer 是 form 的 sibling | 那 grid-row 完全無效（drawer 跟 form 共用 grid cell） |
| Specificity 30 是上限     | 那 layers 才是解、不是雙寫 selector                   |
| 元素永遠存在於 DOM        | 那 framework 重渲染後 querySelector 會回 null         |

「如果錯了會發生什麼」的答案 = 你正在看的失敗現象 → 假設可能錯。

### 方法 3：對外回報模板

```text
我嘗試了 [方向 X]：
- 第 1 次：[做法 A] → [現象]
- 第 2 次：[做法 B] → [一樣的現象]

我的底層假設是「[假設 Z]」、但 [方法 1 / 方法 2 的驗證] 顯示 Z 似乎不成立。

要不要換 [方向 W]、或您看到我沒看到的訊息嗎？
```

對外回報 = 把卡關放到使用者視野、避免繼續單方面加碼。

---

## 假設錯了之後：換方向 ≠ 全部重寫

換方向不是「之前的全部丟掉」、是「對抗錯假設的部分丟掉、其他保留」。

**範例**：search scope UI 放在「form 與 results 之間」。

- 嘗試 1-4：基於假設「drawer 是 form 的 sibling」、用 grid + display:contents + grid-row 排序 → 全失敗
- 第 5 次（用 playwright 驗證）：drawer 是 form 的 child、跟 form 共用 grid cell
- 換方向：不用 grid-row 控制位置（被假設綁住的部分）、改用 absolute + drawer margin-top（不被假設綁住）→ 一次成功

換方向後保留：CSS variable 命名、scope 命名、HTML 結構。丟掉：grid-row 規則。**只丟跟錯假設綁定的代碼、不丟所有東西**。

---

## Wrong vs Right 對照

### 範例 1：specificity 戰

**錯**：

```css
/* 第 1 次：規則沒生效 */
.target { color: red; }
/* 第 2 次：加 specificity */
.parent .target { color: red; }
/* 第 3 次：再加 */
.parent .container .target { color: red; }
/* 第 4 次：放大絕招 */
.parent .container .target { color: red !important; }
```

四次同方向加碼、根本問題（vendor CSS 用了更高 specificity 或更晚 cascade）沒解。

**對**：

```css
/* 第 1 次：規則沒生效 */
.target { color: red; }

/* 第 2 次失敗 → 停下來驗證假設 */
/* DevTools Computed → 看到 vendor 的 .pagefind .target { color: blue } 贏了 */
/* 假設「我的規則該贏」錯 → 換方向：CSS layers */

@layer vendor { /* @import vendor css here */ }
/* 我的規則 unlayered → 自動贏所有 layered 規則 */
.target { color: red; }
```

### 範例 2：JS 改完元素被還原

**錯**：

```js
// 第 1 次：改完被還原
el.textContent = 'custom';
// 第 2 次：加保護
setTimeout(() => { el.textContent = 'custom'; }, 100);
// 第 3 次：再加
setInterval(() => { el.textContent = 'custom'; }, 50);  // CPU 100%
```

**對**：

```js
// 第 1 次：改完被還原
el.textContent = 'custom';

// 第 2 次失敗 → 停、驗證假設
// playwright: 看到 framework 每次 state change 重渲染整個子樹
// 假設「我的修改會 stick」錯 → 換方向：把客製 UI 放到 framework 邊界外

const customEl = document.createElement('div');
customEl.textContent = 'custom';
container.appendChild(customEl);  // 不在 framework 子樹內、不會被 reconcile
```

---

## 自檢清單（dogfooding）

第 2 次失敗時、用這份清單檢查：

- [ ] 我有沒有列出「底層假設是什麼」？
- [ ] 我有沒有用工具或反問驗證假設？
- [ ] 如果假設錯了、有沒有列出替代方向？
- [ ] 對外回報訊息有沒有寫「驗證 X、似乎不成立、要不要換 W」這種句式？
- [ ] 我有沒有避免「再試一次更小心」這種同方向加碼的衝動？

任一項打勾失敗 → 停下來補上、再決定下一步。

---

## 相關原則

- [`principles/two-occurrence-threshold.md`](principles/two-occurrence-threshold.md) — 2 次門檻的抽象原則（跨工具 / 測試 / 思路 / 溝通四面向）

---

**Last Updated**: 2026-04-26
**Version**: 0.1.0
