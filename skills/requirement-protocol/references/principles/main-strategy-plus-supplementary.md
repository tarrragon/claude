# 主策略 + 補強策略：選擇不必互斥

> **角色**：本卡是 `requirement-protocol` 的支撐型原則（principle）、被 SKILL.md「相關抽象層原則」段與 reference `decision-dialogue.md`（步驟 3「策略數」維度）引用、是「呈現決策時、不要預設五選一」的判準依據。
>
> **何時讀**：當你準備呈現多個策略選項給使用者、或寫到「五選一」「ABCDE 你選哪個」的單選表時。讀本卡判斷哪些可疊加（主 + 補強）、哪些才真正互斥。

---

## 結論

多策略選擇預設**不是單選**。能疊加的策略應該疊加、互斥的才需要選。

最常見的疊加：**root-cause 結構性修法 + 使用者感知補強**（例如修結構性層錯位 + UX hint 解感知落差）— 解不同層、互不干擾、合在一起的覆蓋面 > 單選任一。

---

## 為什麼預設單選是錯誤前提

呈現多選項時容易進「適配性比較表 → 選最高分」的單選思維。這個思維對「互斥工具選擇」（Vue / React、Postgres / MySQL）成立、對「補強型策略」不成立：

- 結構性修法（修正根因、長期穩）— 通常需要時間 + 風險
- UX 補強（解使用者感知、立即可見）— 通常 ROI 立刻、但不解根因

兩者**解的問題層不同**：根因解了、使用者立刻感受到的混亂仍在；UX 蓋過去了、根因仍在累積技術債。預設單選 = 強迫使用者在「立即解使用者痛苦」與「長期解結構問題」之間二選一、其實兩個都該做。

---

## 疊加可行的三條判準

某兩個策略 X + Y 可疊加 ⇔ 滿足以下全部：

### 1. 解不同層

X 動結構 / 資料 / 演算法、Y 動 UI / 訊息 / 預期管理。同層的兩個策略通常衝突（兩種 cache 策略、兩種 routing 策略），不同層的多半互補。

判讀：把問題分成「根因 / 訊號 / 補償」三層、每層挑 1 個策略 = 疊加組合。

### 2. 沒副作用衝突

X 加上 Y 不會放大彼此副作用、不會產生新 bug。例：multi-index（佔 build time）+ UX hint（佔畫面空間）— 兩個 cost 維度不同、不互相放大。

反例：fetch-until-quota（多次 round trip）+ aggressive prefetch（更多 round trip）— 同維度副作用會疊加、可能爆炸。

### 3. 增量成本 ≤ 預算

第二個策略的實作 + 維護成本 ≤ 它解的問題價值。如果 X 已經解掉 80% 問題、Y 解剩下 20% 但成本是 X 的兩倍 → Y 就是過度工程、不該疊加。

---

## 典型疊加模式

### 模式一：Structural fix + UX patch

| Structural              | UX                                    |
| ----------------------- | ------------------------------------- |
| Multi-index             | Honest progress UI                    |
| Query-side pushdown     | Empty state 三狀態                    |
| Build-time pre-tokenize | 匹配模式限制提示（prefix-match hint） |

Structural 解根因、UX 解使用者當下混亂。即使 structural 還沒 ship、UX patch 可以先 ship 解眼前問題。詳細搜尋匹配模式案例見 [`search-engine-matching-mode-mismatch.md`](./search-engine-matching-mode-mismatch.md)。

### 模式二：Defensive + Optimistic

| Defensive           | Optimistic                |
| ------------------- | ------------------------- |
| 輸入驗證 / 邊界檢查 | Default 值合理 / 自動修正 |
| 錯誤訊息精準        | 操作回 undo               |
| Retry with backoff  | 預測性 prefetch           |

Defensive 處理失敗、Optimistic 處理成功 — 兩個 happy path 共存、不衝突。

### 模式三：Now + Later

「先 ship X 解眼前、Y 下輪做」是一種隱式疊加 — 不是放棄 Y、是延後到風險更可承受的 release window。判準見 [`incremental-shipping-criteria.md`](./incremental-shipping-criteria.md)。

### 模式四：Selector strategy 疊加

Selector 起點 pattern（document query / 元件根 / 函式參數 / closest lookup）乍看互斥（每個元件只能選一個起點）、實際在同一個 handler 內可疊加：

| 元件位置                           | 適合 pattern |
| ---------------------------------- | ------------ |
| Modal / dialog 內定位元素          | 元件根變數   |
| 跨 modal 邊界元素（toast、portal） | 全文件 query |
| Event target → 找最近容器          | closest      |
| Test / 多實例                      | 函式參數     |

同一份 component code 可同時用多種起點（外部 portal 用 document、內部用 closest）— 解不同 selector context、不衝突、增量成本低 = 滿足三條判準。

判讀：「這幾個 pattern 是同層次（互斥）還是不同 context（互補）？」不同 context = 疊加。

---

## 反模式：強迫單選的代價

| 反模式                          | 後果                                                                                                                       |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| 「五選一」當預設                | 放掉 80% 互補可能                                                                                                          |
| 用「最佳策略」當銀彈            | 漏掉解不同層的問題                                                                                                         |
| 「先做 X、Y 永遠延後」          | Y 變成高 ROI 無觸發的結構性跳過（詳見 [`external-trigger-for-high-roi-work.md`](./external-trigger-for-high-roi-work.md)） |
| 「Y 才是真正的 fix、X 是 hack」 | 道德判斷阻止 X 的價值、使用者多受苦一段時間                                                                                |
| 把 UX 補強當「掩蓋問題」        | 忽略掉「使用者預期管理」也是真實價值                                                                                       |

---

## 何時該堅持單選

| 情境                           | 為什麼                                             |
| ------------------------------ | -------------------------------------------------- |
| 真正互斥（同 slot 只能放一個） | 例：UI framework、DB engine、protocol — 選了就排他 |
| 維護成本不可接受               | 兩條 path 並存的 cognitive load > 收益             |
| 一致性比覆蓋面重要             | 例：UI 設計語言、API 慣例 — 多選會稀釋             |
| 探索期、還沒驗證               | 多選 = 多戰線、超過驗證能力                        |

四類共通：**疊加的代價 > 疊加的收益**。其他情境都該先檢查「能不能疊加」。

---

## 判讀徵兆

| 訊號                                     | 該做的事                                  |
| ---------------------------------------- | ----------------------------------------- |
| 「五策略選一」當預設                     | 檢查能不能疊加、列出組合                  |
| 推薦時只給一個策略、沒講「也可以加 X」   | 補上「再加 Y 風險不大」的選項             |
| 使用者問「那 Y 還做嗎」                  | 你已經把 Y 隱式排除、講清楚 Y 的位置      |
| 「真正的 fix 是 Z、其他是 hack」道德判斷 | 退一步檢查：在 Z 完成前、有沒有便宜的減痛 |
| 兩個策略放一起就互相打架                 | 違反判準 1 或 2、退回單選                 |
| 第二個策略 ROI 邊際                      | 違反判準 3、不疊加                        |

**核心**：策略選擇問「能不能疊加」優先於「選哪個」 — 多數工程問題的最佳解是「多層次組合」、不是「找出唯一答案」。

---

## 與其他原則的串連

- Filter × Source 五策略選擇矩陣：列了五策略、本卡點出「不必選一個、常配對使用」 — 詳見 [`filter-source-composition-strategies.md`](./filter-source-composition-strategies.md)
- 搜尋匹配模式不對齊：五個策略中 D（UX hint）+ B/C（結構修法）就是疊加典型 — 詳見 [`search-engine-matching-mode-mismatch.md`](./search-engine-matching-mode-mismatch.md)
- 分批 ship 準則：「先 X 後 Y」是疊加在時間軸上的展開 — 詳見 [`incremental-shipping-criteria.md`](./incremental-shipping-criteria.md)
- 高 ROI 無觸發：「下輪做 Y」需要結構性 trigger、不靠紀律 — 詳見 [`external-trigger-for-high-roi-work.md`](./external-trigger-for-high-roi-work.md)
- 決策對話的五維度：本卡是「策略數」維度的展開 — 單選 vs 主+補強疊加 — 詳見 [`decision-dialogue-dimensions.md`](./decision-dialogue-dimensions.md)
