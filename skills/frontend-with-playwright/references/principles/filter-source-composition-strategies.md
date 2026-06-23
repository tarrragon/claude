# Filter × Source 的合成策略五選一

> **角色**：本卡是 `frontend-with-playwright` 的支撐型原則（principle）、被 reference `data-flow-and-filter-composition.md`（總覽 + 五策略展開）引用、跟 [`filter-instruction-clarification.md`](./filter-instruction-clarification.md)（三問澄清）配對使用。
>
> **何時讀**：篩選三問跑完、確定要解 Filter × paginated source 的層錯位、要選五策略中的哪一個。

---

## 核心原則

**Filter 跟分批 source 的合成有五種策略、各自機會成本不同**。沒有絕對最佳 — 選哪個取決於三個變數：

1. Source 是否支援 server-side filter（capabilities）
2. Match 密度（稀疏 vs 密集）
3. UX 容忍度（要不要誠實顯示「掃描範圍」）

本文是「Filter 與 Source 的層錯位」反模式的解法展開、列出五個合理選項與適用情境。

---

## 五策略對照表

| 策略 | 一句話                                           | 對 source 的需求              | 對 UX 的影響   | 工程量 |
| ---- | ------------------------------------------------ | ----------------------------- | -------------- | ------ |
| A    | 把 filter 推進 source 的 query                   | 必須支援該 filter 條件        | 透明（無感）   | 中-高  |
| B    | 自動續抓直到湊滿 N 個 match                      | 任何分批 source               | 透明（稍慢）   | 中     |
| C    | 預先建獨立 index（每種 mode 一份）               | 能控 source 的 build pipeline | 透明（最快）   | 高     |
| D    | 誠實 UX 顯示「已掃 N / 命中 K」                  | 任何 source                   | 顯眼（多按鈕） | 低     |
| E    | 接受「filter 範圍 = 已載入」、不承諾 source 全集 | 任何 source                   | 隱性語意縮小   | 最低   |

---

## 五策略一句話總覽

### 策略 A：推進 query

把 filter 條件變成 source 的 query 參數、source 端就回符合的。最優、無層錯位 — 但要 source 支援。

### 策略 B：自動續抓直到湊滿

抓一批 → filter → 不夠再抓 → 湊滿 N 個或 source 結束。需要上限保護避免拉爆。

### 策略 C：預先建獨立 index

Build time 為每種 filter mode 各建一份 source、runtime 切 mode = 切 source。前提是能控 build、mode 有限。

### 策略 D：誠實進度 UX

保留 view 層 filter、UI 顯示「已掃 N / 命中 K / 共 M」三數字 + 「再掃一批」、使用者手動觸發續抓。

### 策略 E：明示語意縮小

明示告訴使用者「filter 範圍 = 已載入、不承諾全集」、不假裝是全集 filter。比 D 顯眼度低、但成本最低。

> **D 跟 E 都是 subset 上做、差別**：D 用三數字持續顯示掃描範圍、E 用文字一次性告知。silent 縮小（既不三數字、也不告知）= 反模式、撞回層錯位。

---

## 選擇規則：決定矩陣

| 條件                                  | 建議策略              |
| ------------------------------------- | --------------------- |
| Source 支援 server-side filter        | A（最優）             |
| Source 不支援、match 密度高、自動較好 | B                     |
| Source 不支援、能控 build、mode 有限  | C                     |
| Source 不支援、稀疏、要避免拉爆       | D                     |
| 原型期、不解決完美                    | E（明示語意縮小）     |
| Source 一次性給完、無分批             | view 層 filter 直接寫 |

---

## 多策略並用

實務上常見組合：

- **A + D fallback**：query 推進失敗（如使用者用 source 不支援的條件）→ fallback 到 D
- **B + 上限 → D**：自動續抓到上限後切 D（顯示「已掃 N 筆、再掃？」）
- **C + B 補強**：預先 index 解一般 case、B 解 index 沒覆蓋的組合

並用通常比單選有效、但複雜度也最高。詳細的疊加判準（解不同層 / 沒副作用衝突 / 增量成本可接受）見 [`main-strategy-plus-supplementary.md`](./main-strategy-plus-supplementary.md) — 本表的「並用」就是該原則的具體展現。

「先 ship 哪個策略、哪個下輪」見 [`incremental-shipping-criteria.md`](./incremental-shipping-criteria.md) — 例如 D（UX）通常先 ship、A/C（結構）下輪。

---

## 判讀徵兆

| 訊號                                                      | 該選的策略起點                  |
| --------------------------------------------------------- | ------------------------------- |
| Source 是 SQL / ES / indexed search 且 filter 條件已索引  | A                               |
| Source 是 indexed search 且 filter 是「title vs content」 | C（重 index 兩份）              |
| Source 不支援、預期 match 密集、要無感                    | B                               |
| 工程量限制、能接受顯眼 UX                                 | D                               |
| 原型 / MVP、能接受語意縮小但要明示                        | E（含語意聲明）                 |
| 使用者意圖明確要「全部命中」、source 不支援、match 稀疏   | A 或 C 重設計、不要 B（會拉爆） |

**核心原則**：Filter × Source 沒有最佳解、只有「對齊三變數（capabilities / 密度 / UX）的取捨」。識別三變數、選對策略 → 比寫漂亮的程式重要。

---

## 與其他原則的串連

跟 [`external-component-collaboration-layers.md`](./external-component-collaboration-layers.md) 同構：A 推進 query ≈ 公共介面層（最穩定）、C 多 index ≈ 邊界層（build pipeline 控制）、B 自動續抓 ≈ 邊界 DOM 層（client 補足）、D / E 誠實或縮小 ≈ 內部結構層（接受限制）。兩個原則的選擇順序都是「離 source 公共介面越近、合作越穩」。
