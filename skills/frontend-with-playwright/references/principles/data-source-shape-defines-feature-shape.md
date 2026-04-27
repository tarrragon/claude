# 資料源的形狀決定 feature 的形狀

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 reference `data-flow-and-filter-composition.md` 的 checklist 引用。
>
> **何時讀**：拿到一個 source（API、SDK、library）開始設計 feature 前、用來判斷哪些 UI 設計受資料形狀硬約束、避免憑 UI 倒推資料層。

---

## 核心原則

**Feature 的設計受資料源的形狀約束、不能憑 UI 想要的形狀去倒推**。

| 資料源形狀                      | 對 feature 的硬約束                      |
| ------------------------------- | ---------------------------------------- |
| 一次性 fetch（靜態 / API 全集） | Filter / sort / count 都安全可在任意層做 |
| 分批 fetch（pagination）        | Filter / sort 必須跟 source 同層         |
| Streaming（SSE / iterator）     | 結果可能無上限、count 是不確定值         |
| Cached + revalidate             | 兩個 dataset 並存、要決定哪個 winning    |

憑 UI 倒推資料層 =「我希望畫面這樣呈現、所以資料層應該這樣」 → 多半會在錯誤的層做錯誤的操作（見 [層錯位](./view-layer-filter-vs-source-layer.md)）。

---

## 為什麼會憑 UI 倒推

### UI 設計通常先動

設計師畫 wireframe、PM 描述體驗、執行者看到的是「畫面該長什麼樣」 — 資料層的限制不在 wireframe 裡。

### UI 形狀對資料層假設過強

UI 上「filter 拉桿」這個元件、隱含假設「資料能立即過濾」 — 但如果資料是分批 fetch、立即過濾在資料層不成立。執行者按 UI 寫 → view 層 post-filter → 撞上層錯位。

### 「能用」訊號早於「對齊資料形狀」

寫完 view 層 filter、手動測一次能用、覺得對 — 但能用的範圍是「已載入子集」、不是「完整 dataset」。資料形狀的限制要刻意對照才看得到。

---

## 多面向：資料源形狀的不同類型

### 形狀 1：一次性給完整 dataset

範例：靜態 JSON、SSR 完整渲染、API 一次回全集（< 1MB）。

| Feature 設計  | 安全與否 |
| ------------- | -------- |
| 任意層 filter | 安全     |
| 任意層 sort   | 安全     |
| Count         | 安全     |
| Pagination    | 不需要   |

這類 source 是「最寬容」的、UI 想怎麼設計都行。

### 形狀 2：分批 fetch（pagination）

範例：靜態站搜尋 index、infinite scroll、cursor-based API。

| Feature 設計     | 限制                                      |
| ---------------- | ----------------------------------------- |
| Filter           | 必須跟 source 同層（A）或自動續抓（B）    |
| Sort             | 必須是 server-side sort、不能 client 重排 |
| Count            | 通常需要 source 提供 total                |
| 「跳到最後一頁」 | 需要 cursor / offset 支援                 |

UI 設計時要避開：「立即 filter」「立即 sort」「Show all」 — 這些假設 dataset 已 materialize。

### 形狀 3：Streaming / async iterator

範例：SSE、WebSocket push、async iterator from generator、log tail。

| Feature 設計 | 限制                                   |
| ------------ | -------------------------------------- |
| Filter       | 可在 stream 裡做（透明）               |
| Sort         | 不能 — stream 沒終點、無法 sort        |
| Count        | 「目前累計」、不是「總數」             |
| 進度條       | 只能顯示「已收 N 筆」、不能 % progress |

UI 設計時要避開：「sort by 任意欄位」「總共 X 筆」「進度條 50%」 — 這些假設有限終點。

### 形狀 4：Cached + revalidate

範例：service worker cache、SWR、HTTP cache、IndexedDB cache。

| Feature 設計     | 限制                                       |
| ---------------- | ------------------------------------------ |
| Filter           | 哪個 dataset 在 filter？cache 還是 fresh？ |
| 「最新狀態」訊號 | 需要 UI 區分 stale vs fresh                |
| 衝突處理         | Cache 跟 fresh 結果不同時、誰 winning？    |

UI 設計時要決定：cache-first（快但 stale）還是 fresh-first（慢但新）。Filter 跟其他操作要對齊這個選擇。

---

## 形狀識別的 protocol

拿到一個 source（API、SDK、library）、用以下兩問判斷它是哪個形狀：

### 問 1：是否一次給完整 dataset？

| 答案 | 形狀                    |
| ---- | ----------------------- |
| 是   | 形狀 1（一次性）— 安全  |
| 否   | 形狀 2 / 3 / 4 — 進問 2 |

判讀依據：API 是否有 `pagination` / `cursor` / `nextPage` / `loadMore` / `for await` / `subscribe` 等概念？有就是「不一次給完」。

### 問 2：分批的觸發機制是什麼？

| 機制                                   | 形狀                          |
| -------------------------------------- | ----------------------------- |
| 客戶端要求下一頁（pull）               | 形狀 2（paginated）           |
| 伺服端推（push）、可能無終點           | 形狀 3（streaming）           |
| 預先給一份（cache）+ 之後重抓（fresh） | 形狀 4（cached + revalidate） |

判讀依據：SDK doc / API spec 的「資料更新方式」段落。讀不到就跑 spike：手動觸發、看是 pull 還是 push、有沒有 cache。

兩問跑完、形狀已知 → 寫 feature 之前能評估「資料形狀對 feature 設計的硬約束」。

---

## 形狀混合（疊加）

實務上、source 常常是多個形狀疊加。常見組合：

### 組合 1：Cached + Paginated

```text
[Server paginated API]
   ↓
[Client cache layer (e.g. SWR)]
   ↓
[UI 拿 cache + 分批 fetch fresh]
```

- 形狀 4（cached）+ 形狀 2（paginated）疊加
- Filter 要決定：在 cache 上還是 fresh 上？fresh 是分批的、又有層錯位？

### 組合 2：Streaming + Buffered

```text
[Server SSE push]
   ↓
[Client buffer N events]
   ↓
[UI 從 buffer 取]
```

- 形狀 3（streaming）+ 內部 buffer 限額
- Filter 要看：在 stream 入口還是 buffer 出口？buffer 滿了怎麼處理舊事件？

### 組合 3：Lazy iterator + take(N)

```python
def stream():
    for chunk in remote_paginated():
        yield from chunk

list(itertools.islice(stream(), 100))  # 限額 100
```

- 形狀 2（paginated）+ 用 take 限額 → 行為像形狀 1（一次給完）但只給前 100
- Filter 全集還是 100 個 subset？

混合形狀的 filter 要分別處理每一層的層錯位、不是當成單一形狀。

---

## 形狀的可改造性

形狀不只決定 feature 設計、還決定「策略可選範圍」。可改造性分三類：

| 類別           | 例子                               | 對策略選擇的影響                                   |
| -------------- | ---------------------------------- | -------------------------------------------------- |
| 你控的 source  | 自家 build pipeline、自家 API      | 全部策略可選（重 index、多 index、改 schema 都行） |
| 你不控但能要求 | 同公司其他團隊、open source vendor | 部分可選（提 issue / PR、等回覆）                  |
| 完全不可控     | 第三方 API、legacy black box       | 只剩 client-side 解（自動續抓、誠實 UX、明示縮小） |

評估可改造性、跟策略選擇配套：

- 全可控 → 推進 query 或多 index 通常最優
- 半可控 → 自動續抓短期解 + 長期等可改造
- 不可控 → 接受誠實 UX / 明示縮小、不要硬撞推進 query

---

## 寫 feature 前的形狀對照表

寫第一行之前、先填這張表：

| 維度                          | 答案                    |
| ----------------------------- | ----------------------- |
| Source 是什麼形狀（1-4）      | ?                       |
| Total cardinality 是多少      | ?（10? 1萬? 10萬?）     |
| 是否分批 / 限額 / streaming   | ?                       |
| Source 支援哪些 filter / sort | ?                       |
| Cache 策略（如果有）          | ?                       |
| Match 密度預期                | ?（密集 / 中等 / 稀疏） |

填完後評估：UI 設計需求跟資料形狀有沒有衝突？衝突就重設計 UI、或調整資料層、或退到誠實 UX。

---

## 設計取捨：UI 還是 Source 先服從

### A：UI 服從 source 形狀（推薦）

- **機制**：先看 source 給什麼形狀、UI 設計成「這個形狀能呈現的」
- **適合**：source 已存在（vendor library、legacy API、無法改）
- **代價**：UI 可能比設計理想中簡單

### B：Source 服從 UI 需求（重設計 source）

- **機制**：UI 設計理想化、為了支援 UI、改 source（重 index、加欄位、換 SDK）
- **跟 A 的取捨**：B 工程量大、但 UX 上限高
- **B 才合理的情境**：source 能控、改 source 的成本 < 長期 UX 收益

### C：兩邊妥協、用誠實 UX 補縫

- **機制**：UI 設計理想、source 不重做、用 [誠實進度 UX](./pattern-honest-progress-ui.md) 把資料形狀的限制告訴使用者
- **跟 A 的取捨**：C 比 A 顯眼、比 B 工程量小、是常見的中間方案
- **C 才合理的情境**：使用者能接受顯眼的「掃描範圍」UX

### D：UI 假裝 source 形狀符合（反模式）

- **為什麼是反模式**：UI 暗示的能力跟資料層實際能力不符、使用者基於錯誤訊號決策
- **看起來吸引人的原因**：UI 設計可以理想化、不用看資料層限制、設計師跟工程師都輕鬆
- **實際發生的代價**：撞上 [層錯位](./view-layer-filter-vs-source-layer.md)、長期維護負擔大（每次 source 升級都要重 patch）、使用者信任損失

---

## 判讀徵兆

| 訊號                                                       | 該做的行動                         |
| ---------------------------------------------------------- | ---------------------------------- |
| 拿到 wireframe 開始實作前、沒看過資料源 API doc            | 先看 — 確認資料形狀                |
| UI 含「立即 filter」「sort by 任意欄位」但 source 是分批的 | 衝突 — 重設計 UI 或重 index source |
| UI 顯示 progress bar 但 source 是 streaming                | 衝突 — 改成「已收 N 筆」、不寫 %   |
| Cache 策略沒設定就開始寫 feature                           | 先設定 — cache-first / fresh-first |
| 內心 OS：「資料層之後處理、先把 UI 寫出來」                | 停 — 形狀對照表先填                |

**核心原則**：資料源的形狀是 feature 的硬約束。UI 設計可以理想化、但實作要看 source 給什麼。憑 UI 倒推資料層的實作 = 在錯誤的層解錯誤的問題、最終產生層錯位類 bug。

---

## 與其他原則的串連

- 跟 [外部組件合作四層](./external-component-collaboration-layers.md)：兩者共用「先看你能改什麼、再決定怎麼客製」 — 一個講 UI 客製、本卡講資料層客製、共同精神是「客製從邊界往中心做、不要倒推」
- 跟 [Feature 操作要跟 Source 同層合成](./compose-feature-at-source-layer.md)：本卡講「形狀是硬約束」、同層合成講「在硬約束下、操作該放哪一層」
