# 篩選類指令的澄清時機

> **角色**：本卡是 `requirement-protocol` 的支撐型原則（principle）、被 reference `clarifying-ambiguous-instructions.md`（類型 5：篩選三問）引用。
>
> **何時讀**：收到「依 X 篩選」「只看 X」「過濾 Y」這類指令、寫第一行 code 之前。

---

## 核心原則

**「依 X 篩選」這類指令、寫之前必須澄清三件事**：

1. 篩選的**定義域**是「已載入的子集」還是「全部結果」？
2. 資料源是**一次性給完整 dataset** 還是**分批 / 限額**？
3. 「沒命中」與「還沒抓到」要不要在 UI 上**區分**？

三問沒跑完就直接寫、必然寫成視覺層 post-filter（最容易實作的版本）、撞上「Filter 與 Source 的層錯位」反模式。

這是模糊指令澄清協議的第 5 類：篩選類指令。

跟前四類的差別：

- 空間 / 位置 / 隔離類 — 缺的是**幾何資訊**（數字、layout、邊界）
- 決定權類 — 缺的是**誰拍板**（visible 三問）
- 篩選類（本卡）— 缺的是**操作的層級**（filter 的 stream 範圍 = 哪一層的「一筆」）

前四類的澄清能避免實作走錯方向、第 5 類能避免架構上錯層。

---

## 為什麼篩選指令需要獨立的澄清協議

「依 X 篩選」的指令在使用者口中是一個簡單訴求、在實作上有兩個獨立決策：

- **語意決策**：filter 的定義域是哪一層？
- **UX 決策**：邊界 state（loading / empty / partial）怎麼呈現？

兩個決策不澄清、執行者預設選最簡單版本（view 層 + silent fail）— 但這版本對應的使用者意圖通常不是使用者真的要的。

---

## 三問模板

### 問 1：定義域

```text
「依 X 篩選」是指：

(a) 在已載入的結果裡找 X 符合的（filter 範圍 = 已抓的子集）
(b) 在所有結果裡找 X 符合的（filter 範圍 = 完整 dataset）
(c) 重新搜尋、把 X 當成 query 條件（filter ≡ 改 query）

通常 (b) 是使用者預期、但實作成本看 (c) 是不是 source 支援的。哪一個？
```

回答決定 filter 該寫在哪一層。

### 問 2：資料源型態

```text
資料源是：

(a) 一次性給完整 dataset（靜態陣列、一次 fetch 到底）
(b) 分批 / 限額（paginated API、infinite scroll、indexed search）
(c) Streaming（SSE / WebSocket、來多少看多少）
(d) Cached + revalidate（先 cache 後 fresh）

(a) 沒有層錯位風險、直接寫 view 層 filter；
(b)(c)(d) 必須跟 source 對齊或加自動續抓 / 誠實 UX。
```

問 1 跟問 2 的組合決定實作模式：

|            | Source (a) 一次性 | Source (b)(c)(d) 分批      |
| ---------- | ----------------- | -------------------------- |
| 定義域 (a) | view filter OK    | view filter + 誠實 UX      |
| 定義域 (b) | view filter OK    | 自動續抓、或 push 到 query |
| 定義域 (c) | 改 query          | 改 query                   |

### 問 3：空狀態區分

```text
當 filter 後 0 筆顯示、要不要區分：

(a) 「沒命中」（已抓完、確定 0）
(b) 「還沒抓到」（已載入子集裡 0、source 還有）
(c) 「載入中」（fetch 還在跑）
(d) 「載入失敗」

通常 (a)(b)(c)(d) 都該區分（loading / empty / end 三狀態）、但實作上能忍受多少混為一談？
```

回答決定 UX 要做到多細。

---

## 多面向：篩選指令的不同形式

### 形式 1：Boolean 篩選

「只看標記為 favorite 的」「只看 type = post」 — 屬性匹配、二元。

通常推到 query 層（formula: `type = post`）、不在 view 層 hide。

### 形式 2：Substring / regex 篩選

「title 含 X」「內文匹配某 pattern」 — 字串搜尋、可能跨欄位。

如果 source 有 full-text index、推到 query；沒有 → 自動續抓 + 應用 regex。

### 形式 3：範圍篩選

「日期在 X-Y 之間」「分數 > 80」 — 連續值區間。

通常 source 支援（SQL `BETWEEN`、API 的 ?from=&to=）、推到 query。

### 形式 4：Facet（多選交集）

「type=post AND tag=js AND date>2024」 — 多條件組合。

實作通常是 source 支援多 filter 參數、UI 提供 facet 介面。每個 facet 獨立澄清三問。

### 形式 5：客製計算後篩選

「閱讀時間 > 5 分鐘」「distance < 1 km」 — 需要計算、source 通常不會直接支援。

要嘛預先計算後存到 source（推到 query）、要嘛接受「在已載入子集裡計算」的語意縮小。

---

## 設計取捨：澄清的時機與形式

### A：寫第一行 code 前澄清三問

- **機制**：使用者下指令、執行者立刻列三問、給三問的選項、讓使用者選
- **選 A 的理由**：避免錯實作、避免層錯位
- **代價**：對話成本中（三問 + 選項）

### B：邊寫邊發現邊問

- **機制**：先寫 view 層、發現邊界 case 不對再回問
- **跟 A 的取捨**：B 對話成本看起來低、但累積的重做成本高（架構已選錯方向）
- **B 才合理的情境**：原型 / 探索期、選錯架構成本低

### C：執行者自己選一個版本、commit、看使用者驗收

- **跟 A 的取捨**：C 把分析丟給使用者驗收、把使用者意圖跟實作不匹配的成本後置
- **C 才合理的情境**：執行者跟使用者是同一人、或預期會多輪迭代

### D：忽略澄清、直接寫 view 層 silent post-filter（反模式）

- **為什麼是反模式**：寫出的版本對應的不是使用者意圖、撞上「Filter 與 Source 層錯位」、ship 後 silent 失敗
- **看起來吸引人的原因**：對話成本看起來最低（不用問三問）、5 行 forEach 解決
- **實際發生的代價**：使用者誤以為「沒命中」、放棄使用、得不到回報（silent 失敗最隱蔽）

---

## 判讀徵兆

| 訊號                                                               | 該做的行動                  |
| ------------------------------------------------------------------ | --------------------------- |
| 收到「依 X 篩選」「只看 X」「過濾 Y」這類指令                      | 跑三問、列選項              |
| 即將寫 `elements.forEach(el => el.hidden = !matches(el))`          | 三問先跑                    |
| Source 是分批的、且使用者沒明示「filter 範圍」                     | 必問問 1 — 定義域           |
| Filter 後可能 0 筆、且使用者沒明示「沒命中 vs 還沒抓到」要不要區分 | 必問問 3 — 空狀態           |
| 內心 OS：「先做 view 層、晚點補資料層」                            | 停 — 跑完三問、確認方向再寫 |

**核心原則**：篩選指令的「簡單表面」掩蓋了三個獨立決策。澄清三問是必要、不是過度溝通 — 跳過任一問就會寫成「能用但跟意圖有縫」的版本。

---

## 與其他原則的串連

- 解法策略五選一見 [`filter-source-composition-strategies.md`](./filter-source-composition-strategies.md) — 三問跑完後、按 source capabilities / match 密度 / UX 容忍度三變數選策略 A-E。
