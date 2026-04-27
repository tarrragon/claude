# Data Flow and Filter Composition

設計 filter / sort / count / transform 等 stream 操作時、確保操作位置跟資料源同層、避免層錯位產生 silent 缺口。原則跨 UI / 後端 / 演算法管線通用 — 不只是前端問題。

適用：前端 paginated UI 加 filter、後端 API + middleware filter、演算法 pipeline 加 transform、map-reduce 加 post-filter、資料庫 materialized view 加 query。
不適用：純運算演算法（沒有 stream / 沒有 materialization 概念）、純 React state 管理（沒有外部 source）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。本文件涵蓋層錯位識別、五策略選擇、跨領域範例、playwright 驗證方法。

---

## 何時參閱本文件

| 訊號                                                             | 該做的第一件事                                  |
| ---------------------------------------------------------------- | ----------------------------------------------- |
| 即將寫 `forEach(el => el.hidden = !matches(el))`                 | 停 — 確認 source 是不是分批 / streaming         |
| Source 是 `pagefind.search()` / `paginatedFetch()` / `for await` | filter 必須跟 source 同層、不能在 view 層後處理 |
| 「filter 後 0 筆但 source 還有未載入」可能發生                   | 必須補自動續抓 / 推進 query / 誠實 UX           |
| Backend middleware / response wrapper 加 filter                  | 推進 ORM query / SQL `WHERE`、不在 response 後  |
| 演算法 pipeline 末端 filter                                      | 推進 pipeline stage 內、stream-aware            |
| Map-reduce 完成後加 post-filter                                  | 推進 map / reduce 階段                          |
| 「畫面 / 結果對了但邊界 case 怪」                                | 識別這是層錯位、不是 bug 修補能解               |

---

## 為什麼 filter × source 是個結構性議題

Filter 操作的定義是「從 stream 中過濾出符合條件的元素」 — **stream** 是隱含的對象。當 stream 被分層 materialize 時、filter 套在哪一層、決定它能「看見」的元素範圍：

| 層                      | 能看到的範圍                                     | filter 結果的語意          |
| ----------------------- | ------------------------------------------------ | -------------------------- |
| Source 層               | 完整 stream                                      | 「stream 中所有符合的」    |
| Materialization 中      | 已 materialize 的部分                            | 「目前載入的符合的」       |
| 下游（view / response） | Materialized 之後 + downstream filter 之前的子集 | 「下游可見的子集中符合的」 |

使用者 / 呼叫者意圖的「filter」通常是第一層（stream 全集）— 但寫程式當下手邊的對象通常是第三層（已 materialize 的 subset）。**寫起來最便利的位置 ≠ 對齊意圖的位置**。

這是 [#67 寫作便利度跟意圖對齊反相關](principles/ease-of-writing-vs-intent-alignment.md) 在 stream 操作上的具體展現。

---

## 跨領域：同個結構、五個情境

### 情境 1：前端 UI + Pagefind paginated search

```js
// 反例：post-filter on view layer
const all = await pagefind.search(query);
all.results.slice(start, start + 10).forEach(render);
document.querySelectorAll('.result').forEach(el => {
  el.hidden = !matches(el);  // view 層 filter
});
// 第二批全 hidden、使用者看到「load more 沒效果」
```

### 情境 2：後端 API + ORM middleware

```python
# 反例：middleware 在 pagination 之後 filter
@app.route("/posts")
def posts():
    page = Post.objects.paginate(page=1, per_page=10)
    return [p for p in page.items if p.author == "author_x"]
    # 漏掉沒在這頁的符合項
```

### 情境 3：Async iterator + take(N)

```python
# 反例：先 take 後 filter
items = list(itertools.islice(stream(), 100))
filtered = [x for x in items if matches(x)]
# stream 後面可能還有符合的、但被 take 100 切斷了
```

### 情境 4：Map-reduce + post-reduce filter

```text
[shards] → [map output] → [reduce]
                              ↓
                         [filter]  ← 已是 reduce 後的結果
```

Filter 應該在 map 階段（per-shard）或 reduce 內、不是 reduce 後。

### 情境 5：Materialized view + SELECT

```sql
-- 反例：在 stale view 上 filter
SELECT * FROM posts_summary WHERE author_id = 42;
-- view 可能是某個時點的 snapshot、漏掉之後寫入的 posts

-- 對例：filter 推進原表
SELECT * FROM posts WHERE author_id = 42;
```

**五個情境共用結構**：source 是分層 materialize 的、filter 套在下游 → silent 缺口。

---

## 五種解法策略

詳細展開見 [#59 Filter × Source 合成策略五選一](principles/filter-source-composition-strategies.md)。本卡只列總覽：

| 策略 | 一句話                               | 對 source 的需求              | 工程量 | UX 影響        |
| ---- | ------------------------------------ | ----------------------------- | ------ | -------------- |
| A    | 把 filter 推進 source 的 query       | 必須支援該 filter 條件        | 中-高  | 透明（無感）   |
| B    | 自動續抓直到湊滿 N 個 match          | 任何分批 source               | 中     | 透明（稍慢）   |
| C    | 預先建獨立 index（每種 mode 一份）   | 能控 source 的 build pipeline | 高     | 透明（最快）   |
| D    | 誠實 UX 顯示「已掃 N / 命中 K」      | 任何 source                   | 低     | 顯眼（多按鈕） |
| E    | 明示語意縮小（filter 範圍 = 已載入） | 任何 source                   | 最低   | 隱性語意縮小   |

選擇順序：**A → C → B → D → E**（不寫不告知的 silent 縮小、那是反模式）。

對應的 pattern 卡片：[#60 自動續抓](principles/pattern-fetch-until-quota.md) / [#61 推進 query](principles/pattern-query-side-pushdown.md) / [#62 誠實進度 UX](principles/pattern-honest-progress-ui.md) / [#65 多 index](principles/pattern-multiple-indexes.md) / [#66 明示語意縮小](principles/pattern-explicit-semantic-narrowing.md)

---

## 三變數決定策略選擇

選 A / B / C / D / E 看三個變數：

### 變數 1：Source capabilities

Source 支援哪些 server-side filter？

- 支援該 filter 條件 → A 最優
- 不支援、能控 build → 評估 C
- 都不行 → B / D / E

### 變數 2：Match 密度

每抓一批、預期多少筆 match？

- 高密度（每批 ≥ 1 個 match）→ B 自動續抓 OK
- 稀疏（要抓很多批才湊到一個）→ B 會拉爆、用 D / E
- 不可預期 → 加上限保護的 B + fallback 到 D

### 變數 3：UX 容忍度

使用者能接受多顯眼的「掃描範圍」UX？

- 完全不行（filter 是核心互動）→ A / C
- 可以顯示三數字 → D
- 一次性文字告知就行 → E

---

## Playwright 驗證 filter × source 行為

寫完 filter 後、用 playwright 驗證是否有層錯位 silent 缺口。

### 驗證 1：「Load more 後 filter 後是否該有結果」

```js
async ({ page }) => {
  await page.goto('/search/?q=pre');
  await page.click('[data-scope="title"]');  // 選 title-only

  // 載入第一批、量已掃 / 命中
  const before = {
    loaded: await page.$$eval('.result', els => els.length),
    visible: await page.$$eval('.result:not([hidden])', els => els.length),
  };

  await page.click('button.load-more');
  await page.waitForTimeout(500);

  const after = {
    loaded: await page.$$eval('.result', els => els.length),
    visible: await page.$$eval('.result:not([hidden])', els => els.length),
  };

  // 層錯位徵兆：loaded 增加、visible 沒增加
  return {
    deltaLoaded: after.loaded - before.loaded,
    deltaVisible: after.visible - before.visible,
    isSilentGap: after.loaded > before.loaded && after.visible === before.visible,
  };
}
```

### 驗證 2：「稀疏 case 是否拉爆」

```js
// 用一個極少 match 的 query 觸發 B 策略
await page.goto('/search/?q=very_rare_keyword');
await page.click('[data-scope="title"]');
const startTime = Date.now();
await page.waitForSelector('.scan-status', { timeout: 10000 });
// 應該在 5s 內顯示「已掃完、共命中 K 個」、不該無限續抓
```

### 驗證 3：「使用者能否區分四狀態」

```js
const statusVisible = await page.locator('.filter-status').textContent();
// 應該明示 loading / partial / end / empty 之一、不只是 spinner
```

寫成 playwright test 固化 — 未來架構改動時 CI 立刻發現 regression（[#15 layout-tests-with-playwright](principles/layout-tests-with-playwright.md)）。

---

## 設計決策的 checklist

寫 filter 之前、跑這份 checklist：

- [ ] Source 是不是分批 / streaming / cached / lazy？（[#63 資料源形狀](principles/data-source-shape-defines-feature-shape.md)）
- [ ] Filter 的定義域是已載入子集還是 source 全集？（使用者意圖三問、見 [#58](principles/filter-instruction-clarification.md)）
- [ ] Source 是否支援 server-side filter？（決定能不能用 A）
- [ ] Match 密度可預期嗎？（決定 B 是否可行）
- [ ] 三狀態（loading / empty / end）UX 怎麼區分？（[#57](principles/loading-empty-end-state-distinction.md)）
- [ ] 對於「filter 後 0 筆」的情境、使用者能否區分「沒命中」vs「還沒抓到」？

---

## Wrong vs Right 對照

### 範例 1：搜尋頁 title-only filter

**錯**：

```js
// pagefind 分批載入、view 層 post-filter
input.addEventListener('input', async () => {
  const results = await pagefind.search(input.value);
  results.results.slice(0, 10).forEach(render);
});

document.querySelector('.scope-title').addEventListener('click', () => {
  document.querySelectorAll('.result').forEach(el => {
    const title = el.querySelector('.title').textContent;
    el.hidden = !title.includes(query);
  });
});
```

第二批 8 筆 title 不含 query → 全 hidden、使用者看到「load more 沒效果」。

**對**（策略 C：多 index + 切換）：

```bash
# Build 階段
pagefind --site public --output-subdir _pagefind-all
pagefind --site public --root-selector "article h1, article h2" --output-subdir _pagefind-title
```

```js
const indexes = {
  all: await import('/_pagefind-all/pagefind.js'),
  title: await import('/_pagefind-title/pagefind.js'),
};

input.addEventListener('input', async () => {
  const pf = currentScope === 'title' ? indexes.title : indexes.all;
  const results = await pf.search(input.value);
  // results 已是「該 scope 的全集」、無層錯位
  results.results.slice(0, 10).forEach(render);
});
```

**對**（策略 D：誠實進度 UX、保留 view 層 filter）：

```html
<div class="filter-status">
  已掃 <strong>24</strong> / <strong>~150</strong> 筆 — 命中 <strong>3</strong>
  <button>再掃一批</button>
</div>
```

```js
// view 層 filter 保留、但 UI 顯示掃描範圍 + 提供續抓
function updateStatus() {
  const all = document.querySelectorAll('.result');
  const visible = document.querySelectorAll('.result:not([hidden])');
  document.querySelector('.scanned').textContent = all.length;
  document.querySelector('.matched').textContent = visible.length;
}
```

### 範例 2：後端 API filter

**錯**：

```python
@app.route("/posts")
def list_posts():
    page = request.args.get('page', 1)
    posts = Post.objects.paginate(page=page, per_page=10)
    if author := request.args.get('author'):
        return [p for p in posts.items if p.author == author]
    return posts.items
```

中間的 list comprehension 在 pagination 之後 filter — 漏掉沒在這頁的符合項。

**對**：

```python
@app.route("/posts")
def list_posts():
    query = Post.objects
    if author := request.args.get('author'):
        query = query.filter_by(author=author)  # 推進 ORM
    page = request.args.get('page', 1)
    return query.paginate(page=page, per_page=10).items
```

Filter 在 query 層、pagination 在 filter 之後、無層錯位。

---

## 自檢清單（dogfooding）

寫 filter / sort / count / transform 前：

- [ ] 我有沒有問「這個操作的對象是哪一層的 stream」？
- [ ] Source 是分批的嗎？是 → filter 必須同層或推進上游
- [ ] 寫了 view 層 filter？檢查：稀疏 case 會不會 silent 失敗？
- [ ] 用了 B（自動續抓）？有沒有 MAX_BATCHES + MAX_TIME_MS 上限保護？
- [ ] UX 能否區分「載入中 / 沒命中 / 還沒抓到 / 抓完了」四狀態？
- [ ] Playwright 驗證有沒有覆蓋「稀疏 case」「load more 後 visible 是否變」？

---

## 延伸閱讀

問題分析：

- [#55 Filter 與 Source 的抽象層錯位](principles/view-layer-filter-vs-source-layer.md) — 根因
- [#56 視覺完成 ≠ 功能完成](principles/visual-completion-vs-functional-completion.md) — 「畫面對」是低資訊量訊號
- [#57 Loading / Empty / End 三狀態的區分](principles/loading-empty-end-state-distinction.md) — UX 落地

指令澄清（在 requirement-protocol skill）：

- [#58 篩選類指令的澄清時機](principles/filter-instruction-clarification.md) — 三問模板

解法策略：

- [#59 Filter × Source 合成策略五選一](principles/filter-source-composition-strategies.md) — 總覽
- [#60-#62, #65-#66 五張 Pattern 卡片](principles/pattern-fetch-until-quota.md) — 各策略具體實作

抽象原則：

- [#63 資料源的形狀決定 feature 的形狀](principles/data-source-shape-defines-feature-shape.md) — 形狀是硬約束
- [#64 Feature 操作要跟 Source 同層合成](principles/compose-feature-at-source-layer.md) — 跨領域通用原則
- [#67 寫作便利度跟意圖對齊反相關](principles/ease-of-writing-vs-intent-alignment.md) — meta-principle
- [#68 驗收的時間軸：四個 checkpoint](principles/verification-timeline-checkpoints.md) — 驗收策略

---

**Last Updated**: 2026-04-26
**Version**: 0.1.0
