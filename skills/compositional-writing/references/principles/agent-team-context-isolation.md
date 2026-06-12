# Agent team context 隔離設計：用不同 instance 換 frame、平行 background 保護主 context

> **角色**：本卡是 `compositional-writing` 的支撐型原則（principle）、被 SKILL.md 第 6 原則「Multi-pass Review」引用為 instance 軸（跟 frame 軸正交）的具體實作。
>
> **何時讀**：寫作 review 階段、考慮用 agent team 平行跑多 reviewer 時、想設計 reviewer prompt + context 保護策略時。

---

## 結論

Agent team context 隔離是 LLM-era review 工具設計的核心模式 — 用 N 個獨立 reviewer instance 各自跑 background、各自寫 output file、主 context 只接精煉摘要、不被 reviewer 細節污染。

| 設計選擇                                        | 解決的問題                                                     | 失敗模式                                                       |
| ----------------------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------- |
| Instance 隔離（N 個 reviewer 各自獨立 context） | 維度盲點：單一 reviewer 同時看多維度容易互相干擾               | 用單一 reviewer 處理多維度 → 每個維度都看不深                  |
| Background 平行                                 | 序列時間長：reviewer 序列跑 ~30 分鐘                           | 不平行、序列跑 → 時間 3x                                       |
| Output file 隔離                                | Context 污染：reviewer raw issue 列表佔滿主 context            | Reviewer 直接在 conversation 吐 issue → 主 context 被 raw 佔滿 |
| 主 context 只讀彙整 summary                     | Context 增量過大：直接 Read transcript 拉 raw 內容進主 context | 主 context Read reviewer transcript → 增量翻倍                 |

跟 multi-pass review 的差別：multi-pass 是 *同一 reviewer 換輪次 frame*（生成 / 對意圖 / 機會成本 / grep / 反例）；本卡是 *不同 reviewer instance 各自獨立*（規範 / 案例準確 / 跨章一致 / 文章品質等）。兩者正交、可疊加。

---

## 跟 multi-pass review 的差別

| 維度     | Multi-pass review（frame 軸）                | Agent team context 隔離（instance 軸、本卡）            |
| -------- | -------------------------------------------- | ------------------------------------------------------- |
| 軸定位   | Frame 軸（一個 reviewer N 輪不同 frame）     | Instance 軸（N 個 reviewer 各自獨立）                   |
| 解決問題 | Working memory 限制（一輪 catch 不到所有層） | Context 污染（單一 reviewer context 被 raw input 佔滿） |
| 適用對象 | Author / 單一 reviewer 跑多輪                | Agent team / 自動化平行 review                          |
| 失敗模式 | 跳輪 → 某維度永遠做一半                      | Instance 數量不足 → 維度覆蓋不全                        |

兩軸正交、可疊加 — 同一 reviewer instance 內跑 multi-pass（frame 軸）、跨 reviewer instance 各自獨立（instance 軸）。完整設計同時用兩軸：N 個 reviewer instance 各自獨立 + 每個 reviewer 內部跑多輪 frame check。

詳見 [writing-multi-pass-review](./writing-multi-pass-review.md) 的 frame 軸跟本卡 instance 軸的對照。

---

## 為什麼這層設計重要

Context 隔離要解兩個具體問題：單一 reviewer 同時處理多維度有兩個限制：

1. **維度盲點**：一個 reviewer 同時看寫作規範 + 案例準確性 + 跨章一致性、容易維度互相干擾、最後每個維度都看不深
2. **Context 污染**：reviewer 讀完整 commit + 所有案例 + 所有章節後、自身 context 被佔滿、給的建議也對應主 context 跟著沉重

Context 隔離解這兩個問題：

- 用 N 個專責 reviewer、各自只處理一個維度 → 維度深度提升
- Reviewer 各自 background、不污染主 context → 主 context 保留判讀空間
- Reviewer 寫 output file、不傳 raw 內容到主 context → 主 context 增量極少

---

## Reviewer 數量設計：依維度複雜度決定

Reviewer 數量取決於審查對象的維度複雜度：

| 審查對象                           | Reviewer 數 | 為什麼這個數                                                      |
| ---------------------------------- | ----------- | ----------------------------------------------------------------- |
| 跨章節案例驅動章節擴章             | 3 個        | 規範 / 案例準確性 / 跨章一致性的正交 axes、加更多會 overlap       |
| 方法論 / 自我審查                  | 4 個        | 規範 / 三方自一致性 / 概念邊界 / 文章品質、無 case 引用 axis 需要 |
| 一般 PR review                     | 1-2 個      | 規範 + correctness 即可、不需 case fidelity 維度                  |
| 高 stakes 內容（資安 / financial） | 4-5 個      | 額外加 epistemic rigor reviewer（claim / evidence / threats）     |

維度設計要對審查對象客製、不要固定一套維度套所有任務。

---

## 平行 background 的 abstract pattern

實作 pattern（4 個關鍵設計選擇）：

1. **N 個 reviewer 各自 spawn background instance**：平行跑、不阻塞主 context
2. **每個 reviewer 寫 output file**：報告寫到外部檔（如 `/tmp/reviewer-{id}-report.md`）、不污染主 conversation
3. **主 context 不讀 reviewer transcript**：只讀通知 summary + 最後讀 output file 彙整
4. **Reviewer prompt 含主 context 保護指令**：「報告寫進檔即可、不要在 conversation 吐 raw issue」

具體 spawn / API 用法依 agent tool 平台而異、屬實作層細節、不在本卡 scope。

---

## Reviewer 維度設計：跟著任務客製化

Reviewer 維度不該固定 — 跨章節案例驅動章節用「規範 / 案例 / 跨章一致」三維度、方法論審查用「規範 / 三方自一致 / 概念邊界 / 文章品質」四維度。

設計原則：

- **拆 axis 不重疊**：每個 reviewer 的維度跟其他 reviewer 互斥（如「規範」vs「案例準確性」是不同 axis）
- **覆蓋審查對象的關鍵風險**：審查案例驅動章節要 case fidelity reviewer、審查方法論要三方自一致性 reviewer
- **預期 issue baseline 設好**：每 reviewer 給 prompt 預期數量、reviewer 不要過度抓 / 漏抓
- **prompt 含主 context 保護指令**：「報告寫到外部檔、不要在主 conversation 吐 raw issue」

---

## 反模式

| 反模式                                                      | 後果                                             |
| ----------------------------------------------------------- | ------------------------------------------------ |
| 單一 reviewer 處理所有維度                                  | 維度盲點 + context 污染、品質下降                |
| Reviewer 不寫 output file、直接在 conversation 吐 raw issue | 主 context 被 issue 列表佔滿、修正循環沒空間     |
| Reviewer 維度固定不變、套所有任務                           | 維度跟審查對象不對齊、漏抓關鍵風險               |
| Reviewer 不平行、序列跑                                     | 時間成本高、序列 30 分鐘 vs 平行 10 分鐘         |
| Reviewer prompt 沒明示 baseline                             | Reviewer 抓 5 個或 50 個都「完成」、無法判讀品質 |
| 主 context 直接讀 reviewer transcript                       | 把 raw conversation 拉進主 context、context 污染 |

---

## 何時不適用本紀律

單篇短文 / 無多維度審查需求 / 快速 prototype / 主 context 不敏感的場景不需 agent team — 單一 reviewer 跑 multi-pass（frame 軸）就夠、加 instance 軸是過度設計。Instance 軸適用 production 教學文章 / 高 stakes 內容 / 跨章節教學模組這類維度複雜度高的審查場景。

---

## 跟其他抽象層原則的關係

| 原則                                                                            | 關係                                                                                                                                       |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| [Writing 的 multi-pass review](./writing-multi-pass-review.md)                  | 互補 — multi-pass 是 frame 軸（一個 reviewer N 輪）、本卡是 instance 軸（N 個 reviewer 各自獨立）、兩軸正交可疊加                          |
| [multi-pass-review-frame-granularity](./multi-pass-review-frame-granularity.md) | 解同類問題的不同手法 — frame 顆粒度盲點用「keyword bank / reader simulation / self-criticism」三機制擴大覆蓋、本卡用 instance 隔離擴大覆蓋 |
| [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md) | 同骨 pattern — 單一 reviewer 處理多維度最便利（不用 spawn / coordinate）、但意圖（深度 review）失準                                        |
| [methodology-multi-pass-embedding](./methodology-multi-pass-embedding.md)       | 互補 — methodology 把 multi-pass embed 為 pillar、本卡把 multi-pass 從 frame 軸延伸到 instance 軸                                          |

---

## 判讀徵兆

| 訊號                                           | 該做的事                                                  |
| ---------------------------------------------- | --------------------------------------------------------- |
| Reviewer 給的建議「對應主 context 也沉重」     | Reviewer context 被污染、改 background instance 隔離      |
| 主 context 修正循環時、不知道從哪個 issue 開始 | Reviewer 報告沒精煉、補 reviewer prompt 要求 summary 開頭 |
| 多個 reviewer 抓到同類 issue                   | 維度設計重疊、調整 reviewer 維度分配                      |
| Reviewer 序列跑、單次 review 30 分鐘以上       | 改平行 background、預期縮到 10 分鐘                       |
| 主 context tokens 在 review 階段增長過快       | Reviewer 沒用 output file、改 prompt 明示「報告寫進檔」   |
| 想複用 reviewer prompt 到不同任務              | 維度該重新設計、不是固定一套                              |

**核心**：Agent team context 隔離是 LLM-era review 工具的設計模式 — 用 instance 隔離換維度深度跟 context 保護。維度設計要對任務客製化、不要固定不變。
