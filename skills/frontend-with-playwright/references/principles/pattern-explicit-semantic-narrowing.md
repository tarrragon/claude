# Pattern：明示語意縮小（不承諾全集）

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle / pattern card）、被 reference `data-flow-and-filter-composition.md` 五策略段引用（策略 E）。
>
> **何時讀**：當 filter 必然只能在 subset 上做、又無法用推進 query / 多 index / 自動續抓 / 誠實 UX 任一策略時、決定怎麼明示「範圍 = 已載入」給使用者 / 呼叫者。

---

## Pattern 一句話

當 filter 必然只在已載入子集上運作、用 UI 文字 / API contract / docstring 明確告訴呼叫者「範圍 = 已載入、不承諾全集」 — 不假裝是全集 filter。

對應策略 E（在 [Filter × Source 合成策略總覽](./filter-source-composition-strategies.md) 中）。

---

## 何時用、何時不用

### 用

- Source 不支援推進 query (A 不可行)
- 不能控 build pipeline (C 不可行)
- Match 稀疏、自動續抓會拉爆 (B 不可行)
- 工程量限制、做不了誠實 UX 的三數字
- 能接受「filter 範圍 = subset」這個語意縮小、但要使用者知道

### 不用

- Source 一次給完整 dataset（沒有 subset、不需要縮小）
- 使用者預期 filter 是「全集」、無法接受縮小
- 應用情境影響重大決策（finance、medical 等不能接受 silent 範圍縮小）

---

## 跟策略 D（誠實 UX）的差別

D 跟 E 都是「在 subset 上 filter」、差別在「怎麼告訴使用者」：

| 面向       | D（誠實 UX）                | E（明示語意縮小）                |
| ---------- | --------------------------- | -------------------------------- |
| 範圍訊號   | 即時數字（已掃 N / 命中 K） | 文字描述（一次性告知）           |
| UI 顯眼度  | 高 — 每次都看得到           | 低 — 看一次就過                  |
| 工程量     | 中 — 要實作三數字           | 低 — 改文字 / 加 docstring       |
| 使用者參與 | 點「再掃一批」續抓          | 不續抓、自己判斷要不要 load more |
| 適合       | filter 是主要互動模式       | filter 是次要功能、原型期        |

簡言之：D 是「持續顯示掃描範圍」、E 是「告訴一次、之後不再提」。

---

## 「明示」的具體做法

### UI 明示

```html
<input type="search" placeholder="Filter loaded results...">
<small class="hint">只在已載入的結果裡篩選。要看更多請先載入更多。</small>
```

「Filter loaded results」、「已載入的結果裡」、「載入更多」 — 三個 cue 讓使用者知道範圍。

### API contract 明示

```ts
/**
 * Filter loaded results by predicate.
 *
 * NOTE: Operates on currently loaded subset only.
 * Does NOT trigger fetch of un-loaded items. To filter the full
 * dataset, use {@link searchAll} instead.
 */
function filterLoaded(predicate: (item: Item) => boolean): Item[];
```

JSDoc / TSDoc 把語意寫進 API、IDE 提示能看到。

### Docstring / README 明示

```markdown
## Filter behavior

`filter()` only operates on results currently loaded in client.
If the source uses pagination, items not yet loaded are NOT included.
For full-dataset filtering, the source must support server-side filter.
```

文件級的明示、給開發者讀。

---

## 反例

### 反例 1：Silent 縮小（不告訴）

```html
<input type="search" placeholder="Filter results...">
```

「Filter results」沒指明「only loaded」 — 使用者預設是全集 filter、實際是 subset → 撞回 [層錯位](./view-layer-filter-vs-source-layer.md) 的語意縫。

### 反例 2：明示位置使用者看不到

```ts
/**
 * Filter results.
 * Note: subset only.
 */
```

使用者只看 UI、不讀 docstring — 「明示」要在使用者會看到的位置（UI hint、tooltip、行為描述）。

### 反例 3：明示但不清楚

```html
<small>限定範圍篩選</small>
```

「限定範圍」太抽象、沒說明是什麼範圍。要寫具體：「已載入的 N 筆內」「不包含尚未載入的」。

---

## 何時 E 升級到 D

當以下任一觸發、把 E 升級到 D（誠實 UX 三數字）：

| 訊號                                    | 行動                         |
| --------------------------------------- | ---------------------------- |
| 使用者依然誤以為是全集 filter           | 升 D — 文字明示不夠          |
| Filter 後 0 筆的情境變常見              | 升 D — 三數字能 disambiguate |
| Filter 變主要互動模式（不再是次要功能） | 升 D — 顯眼度需要拉高        |
| Match 密度高、續抓 ROI 變正             | 升 B（自動續抓）             |

E 是「成本低的退路」、不是長期解。當需求成熟、應該升級到 D / A / C。

---

## 跟其他 Pattern 的關係

- E 是策略順序 A → C → B → D 之外的「最後退路」
- E 跟 D 都是「在 subset 上做」、差別在告知方式
- E 跟 silent 反模式的差別：**E 是 explicit 縮小、silent 是 implicit 縮小**

選擇順序（重申）：**A 推進 → C 多 index → B 自動續抓 → D 誠實 UX → E 明示縮小 → silent（反模式）**

對應 pattern 卡片：[推進 query](./pattern-query-side-pushdown.md) / [多 index](./pattern-multiple-indexes.md) / [自動續抓](./pattern-fetch-until-quota.md) / [誠實進度 UX](./pattern-honest-progress-ui.md)

---

## 判讀徵兆

| 訊號                                               | 該做的事                       |
| -------------------------------------------------- | ------------------------------ |
| Source 不支援、工程量做不了 D                      | 用本 pattern                   |
| Filter 行為已決定是 subset、但 UI 沒寫             | 補 UI hint                     |
| API 沒 docstring 說明 filter 範圍                  | 補 docstring                   |
| 使用者反映「filter 結果跟我想的不一樣」            | E 沒成功、升級到 D 或 A        |
| 內心 OS：「反正 subset 就是 subset、寫了也沒人看」 | 停 — silent 縮小是層錯位反模式 |

**核心原則**：能接受語意縮小是可以、但必須明示。Silent 縮小（沒告知就 subset）等於層錯位、是反模式。E 的價值在「明示」這個動作、不在「subset」這個事實。
