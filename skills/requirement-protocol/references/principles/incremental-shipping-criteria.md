# 分批 ship：低風險可見價值先行、結構性下輪

> **角色**：本卡是 `requirement-protocol` 的支撐型原則（principle）、被 SKILL.md「相關抽象層原則」段與 reference `decision-dialogue.md`（步驟 4「批次邊界」維度）引用、是「決定 ship 順序時不要把『重要程度』誤當『ship 順序』」的判準依據。
>
> **何時讀**：當你準備規劃 release / PR 順序、或寫到「等所有東西都做完一起 ship」「下次再優化」時。讀本卡用三軸（可見性 / 風險 / 驗證）切分什麼先 ship、什麼下輪。

---

## 結論

寫到「該 ship 哪些」時、預設**分批**：把 changes 沿三軸切 — **使用者可見性高 + 風險低 + 驗證簡單** 的先 ship、**結構性 + 風險高 + 需驗證** 的下輪。對抗「都做完才能 ship」的整體性衝動。

分批的真正價值：**降低每次 review 的 cognitive load + 加速使用者拿到價值 + 讓回退單位更小**。整批 ship 的代價是 review 變慢、bug 排查面變大、出問題回退要拖整批。

---

## 三軸切分

切「現在 ship vs 下輪 ship」用三個維度：

### 軸 1：使用者可見性

- **高**：使用者立刻能感受到差異（UI 改變、訊息精準、互動更順）
- **低**：純內部結構（refactor、index 重建、protocol 升級）

可見性高 → 早 ship 拿價值；可見性低 → 早晚 ship 差別不大、可以等更多 confidence。

### 軸 2：風險暴露面

- **低**：純加法（新檔案、新欄位、新 endpoint）— 不影響既有 path
- **中**：修改既有 code path 但有 fallback / 開關
- **高**：替換、刪除、結構重組 — 沒退路或退路成本高

低風險 → 早 ship、出問題範圍小；高風險 → 等 confidence、配 staged rollout / feature flag。

### 軸 3：驗證需求

- **低**：邏輯簡單、unit test 夠、可肉眼驗收
- **中**：需要 E2E、多瀏覽器 / 多裝置驗證
- **高**：需要長時觀測、production 流量壓測、A/B 比較

低驗證需求 → 早 ship；高驗證需求 → 等驗證流程跑完、不為趕時間跳過驗收。

---

## 切分矩陣

| 可見性 | 風險 | 驗證  | 建議                               |
| ------ | ---- | ----- | ---------------------------------- |
| 高     | 低   | 低    | **立刻 ship**（最高 ROI / 風險比） |
| 高     | 低   | 中    | 跑完 E2E 就 ship                   |
| 高     | 高   | 中-高 | 配 feature flag、staged rollout    |
| 低     | 低   | 低    | 順便 ship、合併進其他 PR           |
| 低     | 高   | 高    | **下輪**（沒急、值得等驗證）       |
| 低     | 中   | 中    | 看 batch 是否方便、不單獨 ship     |

關鍵 row：**「高可見 + 低風險 + 低驗證」就是先 ship 的甜蜜點** — 例：UX hint、empty state 訊息、明顯的 UI 修正。

---

## 為什麼「全做完才 ship」是反模式

幾個常見藉口 + 為什麼站不住：

| 藉口                            | 為什麼站不住                                                                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| 「分批 ship 不完整」            | 完整是工程師視角、使用者只看自己當下能不能用上                                                                                       |
| 「PR 越大越好 review」          | 反、PR 越大 review 越粗、bug 越多漏                                                                                                  |
| 「下輪我會做完」                | 違反高 ROI 無觸發原則 — 沒 trigger 會跳過（詳見 [`external-trigger-for-high-roi-work.md`](./external-trigger-for-high-roi-work.md)） |
| 「測試一起 ship 比較好驗」      | 反、批次測試會放大 noise、各個獨立驗證更乾淨                                                                                         |
| 「regression 一起爆比較好排查」 | 反、regression 範圍越大越難 bisect                                                                                                   |

實際上「全做完才 ship」最常見的真實原因是：**沒花時間想分批**。預設分批就會自然分。

---

## 分批時要避免的反模式

| 反模式                                         | 為什麼不好                         | 修法                                    |
| ---------------------------------------------- | ---------------------------------- | --------------------------------------- |
| 把高風險砍進「先 ship」 batch 為了趕 demo      | 風險爆炸時所有先 ship 的內容跟著退 | 用 feature flag、不要硬塞               |
| 「下輪做 X」沒寫進系統                         | X 變成結構性跳過                   | 寫成 issue / TODO with deadline         |
| 第一批漏掉 telemetry                           | 下輪沒資料判斷 X 該怎麼設計        | 第一批就埋觀測                          |
| 分太細、每個 PR 都太小、整體 review 成本反而高 | 分批本身有 overhead                | 每批 ≥ 一個完整使用者 user-story 的價值 |
| 第一批 ship 後就鬆懈、忘了下輪                 | 結構性陷阱                         | 把下輪寫進 calendar / sprint plan       |

---

## 何時該堅持「一次完整 ship」

| 情境                                                | 為什麼                                   |
| --------------------------------------------------- | ---------------------------------------- |
| Feature 拆了不能用（atomic from user view）         | 強制 atomic、用 feature flag 控制可見性  |
| Migration / Schema change                           | 半 ship 會破壞既有資料 / 流程一致性      |
| 安全修補                                            | 不能 leak 知道一半                       |
| 跨服務 protocol upgrade（client + server 必須對齊） | 半邊改另一半就破                         |
| 第一次設定 baseline                                 | 沒 baseline 可比較、下輪改才有 reference |

四類共通：**ship 一半比都不 ship 更壞**。其他情境分批優先。

---

## 判讀徵兆

| 訊號                                         | 該做的事                                                                                                                         |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| PR diff > 800 行、含多個 feature             | 拆批、各自走 review                                                                                                              |
| 「等 X 做完一起 ship」                       | 用三軸檢查 X 是否該獨立 ship                                                                                                     |
| Feature flag 名稱長期堆積、沒清掉            | 「下輪清掉」沒 trigger、補 L3-L5 對策（詳見 [`external-trigger-for-high-roi-work.md`](./external-trigger-for-high-roi-work.md)） |
| 「這次先這樣、下次再優化」每次都不發生       | 下輪沒 trigger、把它寫進系統                                                                                                     |
| 第一批 ship 後 production 出問題、回退範圍大 | 第一批塞太多、檢查為什麼沒分更細                                                                                                 |
| 使用者抱怨「等很久才有 X」                   | 可能 X 早就可分批 ship、檢查阻塞點                                                                                               |
| 推薦「等 B/C 都做完再 ship」                 | 違反三軸、應該先 ship 高可見低風險的部分                                                                                         |

**核心**：「ship 順序 ≠ 重要程度」。使用者可見性高 + 風險低 + 驗證需求低 = 先 ship 甜蜜點、即使在重要程度上不是 top。等所有結構性修法都做完才 ship、是把重要程度誤當成 ship 順序的常見錯誤。

---

## 與其他原則的串連

- 驗收的時間軸：分批 ship 對應「Ship 前 / Ship 後」分散 — 每批各自走完四 checkpoint — 詳見 [`verification-timeline-checkpoints.md`](./verification-timeline-checkpoints.md)
- 主策略 + 補強：補強策略通常先 ship、主策略下輪 — 兩卡互補 — 詳見 [`main-strategy-plus-supplementary.md`](./main-strategy-plus-supplementary.md)
- 高 ROI 無觸發：「下輪做」需要結構性 trigger（issue + deadline）、不靠紀律 — 詳見 [`external-trigger-for-high-roi-work.md`](./external-trigger-for-high-roi-work.md)
- 最小必要範圍：每批的範圍從窄起、有證據再擴張 — 詳見 [`minimum-necessary-scope-is-sanity-defense.md`](./minimum-necessary-scope-is-sanity-defense.md)
- 決策對話的五維度：本卡是「批次邊界」維度的展開 — 一次 vs 分批 — 詳見 [`decision-dialogue-dimensions.md`](./decision-dialogue-dimensions.md)
