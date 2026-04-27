# Pattern：把 filter 推進 query 引擎

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle / pattern card）、被 reference `data-flow-and-filter-composition.md` 五策略段引用（策略 A）、SKILL.md description 提到「推進 query」觸發詞。
>
> **何時讀**：寫 client-side filter / post-filter 前、決定能不能直接讓 source 端回符合的；或寫了 filter 還補 client-side post-filter 時、判斷是否「半推進」反模式。

---

## Pattern 一句話

把 filter 變成 source 的 query 參數、source 端就回符合的、client 不 post-filter。

對應策略 A（在 [Filter × Source 合成策略總覽](./filter-source-composition-strategies.md) 中）。

---

## 何時用、何時不用

### 用

- Source 支援該 filter 條件（已索引、能在 query 表達）
- 想避免任何 client-side post-filter
- 想避免層錯位（見 [view-layer-filter-vs-source-layer](./view-layer-filter-vs-source-layer.md)）

### 不用

- Source 不支援（如某搜尋 SDK 對 title-only 沒 native 支援）
- 條件需要 client-side 計算（依 viewport / 隨機抽樣）
- 推進 query 後 cardinality 仍大、還是要 paginate（這時 A + B 並用）

---

## 推進的層次

| 層次        | 範例                                                 | 成本            |
| ----------- | ---------------------------------------------------- | --------------- |
| Query 參數  | `?type=post&tag=js`                                  | 最低、改 URL    |
| Filter API  | `searchSDK.search(q, { filters: { type: 'post' } })` | 低、用 SDK      |
| Re-query    | 重新呼叫 search、不是同個 result 集再過濾            | 低              |
| Index 重建  | Build 時加新欄位 / 新 index                          | 中-高、要 build |
| Schema 修改 | 改 DB schema、加欄位、reindex                        | 高              |

選哪一層 = source 的 capabilities 決定。

---

## 評估 Source Capabilities

寫之前讀 source docs / API spec、列出：

| 問題                                   | 答案範例                               |
| -------------------------------------- | -------------------------------------- |
| Source 接受哪些 filter 條件？          | `=`, `IN`, `BETWEEN`, full-text, ...   |
| 哪些欄位已索引？                       | `type`, `tag`, `date` (not `title`)    |
| 哪些 filter 不支援、需要重 index？     | `title contains`（需 full-text title） |
| Filter 有沒有 cost cap（rate limit）？ | 100 query / sec                        |

不評估就寫 = 寫到一半發現 source 不支援、回頭走策略 B 或 C。

---

## 範例：靜態站搜尋 SDK

### 支援的 filter

```js
// 該搜尋 SDK 支援 filter（透過預先建好的 filter 索引）
const r = await searchSDK.search('keyword', {
  filters: {
    type: 'post',           // 支援
    tag: { any: ['js', 'css'] }, // 支援多選
  },
});
```

### 不支援的 filter

```js
// 該搜尋 SDK 不支援「只搜 title」
// 因為 SDK 的 search 對 full-text、不分區
const r = await searchSDK.search('keyword', {
  scope: 'title-only',  // ❌ 不存在
});
```

要解決：

- 方案 1：build 時把 title 標成獨立 region、用 region filter（如果 SDK 支援）
- 方案 2：建兩個獨立 index（一個只 index title、一個只 index content） — 走 [策略 C](./pattern-multiple-indexes.md)
- 方案 3：放棄推進 query、用 [策略 B 自動續抓](./pattern-fetch-until-quota.md) + post-filter

---

## 跟原本 query 邏輯的並用

推進 filter 通常不取代原本 query、是「補上條件」：

```js
// 使用者輸入 query "css"、選 type=post
const r = await searchSDK.search('css', {  // query
  filters: { type: 'post' },               // filter
});
// 兩個都進 source、source 算交集
```

Filter 跟 query 是不同維度：query 是「找什麼」、filter 是「在哪些範圍找」。

---

## 反例

### 反例 1：推進不完全、留 client-side post-filter 補

```js
const r = await searchSDK.search(q, { filters: { type: 'post' } });
const filtered = r.results.filter(x => x.title.includes(q));
// ↑ 這行還是層錯位
```

如果 source 不支援 title-filter、不要用「半推進」 — 直接走策略 C 或 B。

### 反例 2：忽略 cost cap

```js
input.addEventListener('input', async () => {
  // 每個鍵盤事件 fire 一個 search query
  const r = await searchSDK.search(input.value, { filters: ... });
});
// → query rate 100+/秒、撞 rate limit
```

加 debounce：

```js
let timer;
input.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(() => searchSDK.search(input.value, ...), 200);
});
```

### 反例 3：客製欄位沒進 index、寫了 query 失效

```js
// 期望 filter 「閱讀時間 > 5 分鐘」
const r = await searchSDK.search(q, { filters: { readingTime: { gt: 5 } } });
// → 但 build 時沒把 readingTime 進 filter index → filter 被忽略
```

預期 source 不支援 → 評估「是否值得加進 index」（成本 vs 使用率）。

---

## 跟其他 Pattern 的關係

- A 是最優 — 在 source capabilities 範圍內優先選
- A 不可行 → 評估 [C 建獨立 index](./pattern-multiple-indexes.md)
- C 也不可行 → 退到 [B 自動續抓](./pattern-fetch-until-quota.md)
- 都不可行 → [D 誠實 UX](./pattern-honest-progress-ui.md)

**選擇順序：A → C → B → D**。

---

## 判讀徵兆

| 訊號                                     | 該做的事                                    |
| ---------------------------------------- | ------------------------------------------- |
| Filter 條件能在 source 端表達            | 用本 pattern                                |
| Source 不支援、考慮要不要重 index        | 評估 C 的成本                               |
| 用了 filter 還寫 client-side post-filter | 半推進是反模式、要嘛全推進、要嘛換策略      |
| Filter 觸發 query rate 高                | 加 debounce / throttle                      |
| Query 跟 filter 概念混淆                 | 區分：query = 「找什麼」、filter = 「範圍」 |

**核心原則**：能推進 query 就推 — 沒層錯位、沒 silent 失敗、跟使用者意圖最近。但前提是 source 支援；不支援就要退到 B / C / D、不要做半推進。
