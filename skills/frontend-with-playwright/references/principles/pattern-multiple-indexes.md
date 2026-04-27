# Pattern：預先建獨立 index（每種 mode 一份）

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle / pattern card）、被 reference `data-flow-and-filter-composition.md` 五策略段引用（策略 C）。
>
> **何時讀**：source 不支援該 filter 但能控 build pipeline、且 mode 數量有限時、評估是否值得 build time 多建幾份 index。

---

## Pattern 一句話

Build time 為每種 filter mode 各建一份獨立 source / index、runtime 切換 mode 等於切 source。

對應策略 C（在 [Filter × Source 合成策略總覽](./filter-source-composition-strategies.md) 中）。

---

## 何時用、何時不用

### 用

- 能控 source 的 build pipeline（自家 build、不是第三方 API）
- Filter mode 數量有限且穩定（< 5 個、不會爆炸組合）
- 兩個（含以上）mode 都重要、流量大、值得獨立 index
- Source 的 query 引擎不支援該 filter（不能用 [推進 query](./pattern-query-side-pushdown.md)）

### 不用

- Filter 維度多、組合會爆炸（5 維 × 各 5 選項 = 3125 種 index）
- Index 大小敏感（每份 index 都重複占空間）
- Build pipeline 無法控（外部 API、vendor service）
- Mode 不穩定、常常增刪

---

## 結構

### Build pipeline

```bash
# 範例：兩份 index 各自掃不同 region
search-indexer --site public --output-subdir _index-all
search-indexer --site public/title-only --output-subdir _index-title

# 或用 root selector 限定 source 範圍
search-indexer --site public --root-selector ".post-title" --output-subdir _index-title
```

### Runtime 切換

```js
const indexes = {
  all: await import('/_index-all/search.js'),
  title: await import('/_index-title/search.js'),
};

function search(query, mode) {
  return indexes[mode].search(query);
}
```

每個 mode 對應一份完整 index、search 結果直接是該 mode 的全集。**沒有 post-filter、沒有層錯位**。

---

## 多 index 的成本

| 成本面     | 影響                                           |
| ---------- | ---------------------------------------------- |
| Build 時間 | 每份 index 各建、線性增加                      |
| 儲存空間   | 每份各自占用（通常約 site 大小 2-5%）          |
| 載入頻寬   | runtime 載入哪份 = 該 mode 的 size             |
| 維護       | 改 source / schema 時、所有 index 都要重 build |

通常 build / 儲存的成本 < 在 runtime 自動續抓（B）的累積請求成本。

---

## 跟其他策略並用

C 通常跟其他策略並用：

- **C + 推進 query (A)**：在每份 index 內、再用 query filter 細分（如 `indexes.post.search('css', { filters: { tag: 'js' } })`）
- **C 切 mode + B 自動續抓**：mode 切換無感、mode 內續抓也無感

---

## 反例

### 反例 1：Mode 組合爆炸

```bash
# 5 維 × 各 5 選項 = 3125 份 index
for type in post page tutorial faq doc; do
  for tag in js css html ts py; do
    for date in 2020 2021 2022 2023 2024; do
      search-indexer --filter "type=$type tag=$tag date=$date" --output-subdir _index-$type-$tag-$date
    done
  done
done
```

組合爆炸時不能用 C — 改用 A（推進 query）讓 source 一份就好。

### 反例 2：Mode 不穩定、常常增減

每加一個 mode、build pipeline 多一份、deploy 多一份。如果 mode 半年內會大改、不適合 C。

### 反例 3：Index 沒對齊 mode

```bash
search-indexer --site public --output-subdir _index-title
# build 完後沒過濾、其實 index 了 title + content 全部
```

如果只是改 output 路徑、沒改 index 範圍 → 兩份 index 內容一樣、白做。要用 root selector 或 body 標記正確範圍。

---

## 跟其他 Pattern 的關係

選擇順序：A → C → B → D：

- A 不行（source 不支援該 filter） → 評估 C
- C 不行（mode 爆炸 / 不能控 build） → 退到 B
- B 不行（match 稀疏會爆） → 退到 D

**C 是 A 的 build-time 模擬** — 用 build 時間換 runtime 體驗、跟使用者意圖完全對齊（每份 index = 該 mode 的全集）。

---

## 判讀徵兆

| 訊號                                    | 該做的事                              |
| --------------------------------------- | ------------------------------------- |
| Source 不支援該 filter、想用 A 但做不到 | 評估能不能控 build → 是 → C           |
| Mode 數量 < 5、stable、能控 build       | 用本 pattern                          |
| Mode 組合會爆炸（多維 × 多選）          | 不要用 C、考慮 A 或重新思考 mode 設計 |
| 兩份 index 內容一樣（沒對齊 mode）      | Build pipeline 出錯、檢查 source 過濾 |
| Build 時間翻倍但 runtime 體驗沒改善     | 重評估：是否值得多份 index            |

**核心原則**：C 用 build-time 換 runtime 體驗。前提是 mode 有限、可控、值得 — 否則退到 A 或 B。
