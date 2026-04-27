# Pattern：誠實進度 UX（已掃 N / 命中 K / 共 M）

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle / pattern card）、被 reference `data-flow-and-filter-composition.md` 五策略段引用（策略 D）、SKILL.md description 提到「誠實進度 UX」觸發詞。
>
> **何時讀**：當 filter 必然有層錯位、決定怎麼用「三數字 + 再掃一批」UX 把掃描範圍攤給使用者；或 UI 上只顯示「找到 K 筆」沒顯示「已掃 N」時。

---

## Pattern 一句話

當 filter 必然有層錯位、用「已掃 N / 命中 K / 共 M」三數字 + 「再掃一批」按鈕讓使用者看見掃描範圍、自己決定要不要續抓。

對應策略 D（在 [Filter × Source 合成策略總覽](./filter-source-composition-strategies.md) 中）。

---

## 何時用、何時不用

### 用

- Source 不支援 server-side filter（A 不可行）
- 不能或不值得重 index（C 不可行）
- Match 稀疏或不可預期、自動續抓（B）會拉爆
- 工程量限制、原型期 / MVP

### 不用

- Filter 是主要互動模式（使用者預期「自動全找完」）
- 三數字會讓 UI 太複雜
- 使用者完全不在意「掃描範圍」

---

## 三數字的語意

| 數字   | 意思                               | 來源                |
| ------ | ---------------------------------- | ------------------- |
| 已掃 N | 已從 source 載入並 filter 過的筆數 | client 累計         |
| 命中 K | 已掃 N 筆中、符合 filter 的筆數    | client 累計         |
| 共 M   | Source 總筆數（如果 source 知道）  | source meta（可選） |

最少要顯示「已掃 N / 命中 K」 — 沒有 N 使用者不知道掃描範圍、沒有 K 使用者不知道有沒有命中。

「共 M」可選 — 有的 source 會給 total count、有的（streaming）不會。

---

## UI 模板

### 基本版

```html
<div class="filter-status">
  已掃 <strong>24</strong> 筆 / 命中 <strong>3</strong> 筆
  <button>再掃一批</button>
</div>
```

### 含總數

```html
<div class="filter-status">
  已掃 <strong>24</strong> / <strong>~150</strong> 筆 — 命中 <strong>3</strong>
  <button>再掃一批</button>
</div>
```

### 含結束狀態（呼應三狀態）

```html
<!-- Loading -->
<div class="filter-status">掃描中... 已掃 <strong>24</strong> / 命中 <strong>3</strong></div>

<!-- Partial（還可續） -->
<div class="filter-status">已掃 <strong>24</strong> / 命中 <strong>3</strong>
  <button>再掃一批</button>
</div>

<!-- End（掃完） -->
<div class="filter-status">已全部掃完、共命中 <strong>12</strong> 筆</div>

<!-- Empty (filter) -->
<div class="filter-status">已掃 <strong>24</strong>、沒有命中
  <button>再掃一批</button> 或 <a>清除 filter</a>
</div>
```

---

## 進度更新時機

### 即時更新（每筆）

```js
for (const item of stream) {
  scanned++;
  if (matches(item)) {
    matched++;
    appendResult(item);
  }
  updateUI(scanned, matched);  // 每筆更新
}
```

UX 順、但 DOM 操作頻繁、可能 jank。

### 批次更新（每批）

```js
const batch = await fetchNext();
scanned += batch.length;
const m = batch.filter(matches);
matched += m.length;
appendResults(m);
updateUI(scanned, matched);  // 每批一次
```

DOM 操作少、但 UX 不夠順（一段時間沒動）。

### 推薦：每批 + 載入中 spinner

批次後更新數字、批次間顯示 spinner。最平衡。

---

## 跟自動續抓（B）的混合

可以做成「初始自動續抓 N 批、之後切誠實 UX」：

```js
async function searchWithFilter(query) {
  // 初始自動續抓 3 批（湊一些結果）
  await fetchUntilQuota(3, autoBatches: 3);

  // 之後使用者手動點「再掃一批」
  showHonestProgressUI();
}
```

混合的好處：使用者一進來就有結果（不是空畫面）、之後續抓由使用者決定。

---

## 反例

### 反例 1：只顯示「命中 K」、不顯示「已掃 N」

```html
<div>找到 3 筆結果</div>
```

使用者不知道是從多少筆裡找的、不知道「再掃會不會有」。

### 反例 2：只顯示「共 M / N」進度條、沒分「已掃」「命中」

```html
<progress value="24" max="150"></progress>
```

進度條告訴使用者「load 進度」、但「load 進度 ≠ filter 進度」。沒命中時使用者不知道為什麼進度走了 24% 但畫面沒結果。

### 反例 3：「再掃一批」沒做

只顯示三數字、沒提供續抓 button — 使用者看到「已掃 24 沒命中」、不知道下一步。

---

## 跟三狀態的關係

誠實進度 UX 是 [Loading / Empty / End 三狀態的區分](./loading-empty-end-state-distinction.md) 在「filter + 分批」情境下的具體實作。三數字提供區分三狀態的訊號：

| 三狀態         | 對應的三數字組合                     |
| -------------- | ------------------------------------ |
| Loading        | 已掃增加中、N 還在跑                 |
| Empty (filter) | 已掃 = 24、命中 = 0、還有 → 「再掃」 |
| End            | 已掃 = M、命中 = K（K 可能 0）       |
| Partial        | 已掃 < M、命中 ≥ 1、還有 → 「再掃」  |

---

## 判讀徵兆

| 訊號                                   | 該做的事                  |
| -------------------------------------- | ------------------------- |
| Filter 後可能 0 筆、source 還有未載入  | 用本 pattern              |
| UI 上只有「找到 K 筆」、沒有「已掃 N」 | 補 N — 否則使用者無法判斷 |
| 沒有「再掃一批」按鈕                   | 補 — 給使用者下一步行動   |
| 工程量允許做策略 A / C                 | 用 A / C、誠實 UX 是退路  |
| Match 密集、自動續抓不會爆             | 用策略 B、誠實 UX 太顯眼  |

**核心原則**：誠實 UX 不是「lazy 解法」、是「sourcing 限制下的合理透明度」。給使用者三數字 + 行動選項、比假裝完美但 silent 失敗好。

相關概念：覆寫深度的成本告知 — 兩者都是「把實作的限制 / 代價攤給使用者、讓使用者參與決策」。差別在一個是「實作前告知工程成本」、本卡是「runtime 持續顯示掃描成本」 — 攤出來的位置不同、原則一致：silent 累積負擔是反模式。
