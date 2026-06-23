# Methodology 的 multi-pass 該 embed 在 pillar、不是 appendix

> **角色**：本卡是 `requirement-protocol` 的支撐型原則（principle）、被支柱 4「Multi-pass Refinement」與第 7 原則明示引用、是「為什麼把 multi-pass refinement 升成 pillar、不放在 appendix」的根據。
>
> **何時讀**：設計 / 維護 SKILL / playbook / methodology 文件時、判斷 multi-pass 該放在哪一層；或察覺 reference 結尾的 self-check 沒人用、想理解結構性原因。

---

## 結論

凡是教做事方法的東西（SKILL、playbook、methodology document、checklist）— 如果你認為 multi-pass refinement 是必要的、就要把它放在**核心結構層**（pillar、principle、step）、不是放在**附帶段**（appendix、tips、reminder、see also）。

放在 appendix = 結構暗示「optional、看心情選擇」 = 在 [external-trigger-for-high-roi-work](./external-trigger-for-high-roi-work.md) 的結構壓力下、永遠被跳過。**Pillar 層 = 結構性必跑、用結構強制行為、不靠紀律**。

---

## 為什麼 pillar / appendix 的位置決定執行率

讀者看 SKILL / methodology 時、認知資源分配：

- **Pillar / Core Principles**：必讀、會內化、實作中會回想
- **Steps / Reference**：實作中翻
- **Tips / Appendix / "See also"**：第一次讀掃過、之後忘記

把 multi-pass review 放 appendix = 結構暗示「這是進階、可選」。即使內容寫得很詳細、結構訊號蓋過內容。

對比放 pillar：每次接觸 SKILL、第一眼看到 4-5 個 pillar 中包含 "Multi-pass Refinement" — 結構性提示「這跟其他 pillar 同樣重要」。

---

## 各 methodology 的 pillar / appendix 切分

實際 methodology 文件的 pillar 應該包含 multi-pass、appendix 應該避免：

| Methodology        | 適合的 pillar                                              | 不適合放 appendix              |
| ------------------ | ---------------------------------------------------------- | ------------------------------ |
| 寫作方法論         | 「Re-read Pass」原則明示輪次                               | 「最後 review 一下」三字附帶   |
| 需求協議           | Pillar「Multi-pass Refinement」明示「第 1 輪實作預期不對」 | 「失敗多次再回頭看」零散提示   |
| 前端 + 測試協議    | 「漸進驗證」原則中、再加「Multi-pass Review」串成系列      | TODO 註解講「之後 review」     |
| TDD（test-driven） | RED-GREEN-REFACTOR 三步本身就是 multi-pass                 | 「重構是 optional」當 appendix |
| Agile（process）   | Sprint review / retrospective 是 pillar                    | 「有空回顧一下」當 appendix    |

每個 methodology 的設計都該檢查：**multi-pass 是 pillar 還是 appendix？**

---

## 如何識別「該升 pillar 但被當 appendix」

訊號：

| 訊號                                                   | 該做的事                                           |
| ------------------------------------------------------ | -------------------------------------------------- |
| 「最後再 review 一下」「有空再 polish」這類 disclaimer | 升成獨立 pillar / 原則                             |
| Multi-pass 內容散在多個 reference 角落、沒有單一定位   | 抽出 pillar、各 reference 引用                     |
| Pillar 列表只 3 條（看似簡潔）、但實作中常忘 review    | 缺 pillar、補上 multi-pass                         |
| 「第 1 輪原則」+「第 2 輪原則」分開兩個 SKILL          | 合併、multi-pass 是同 SKILL 的多輪、不是兩個 SKILL |
| 文件結尾「最後注意事項」常被使用者引用為「我忘了」     | 結構問題、移到 pillar                              |

每個訊號都是 **multi-pass 的位置太低**、結構壓力把它當作 optional。

---

## 升 pillar 後的設計：四個必要元素

把 multi-pass 升成 pillar、需要含這四個元素才完整：

### 1. 明示「第 1 輪不追求完美」

寫在 pillar 內容、第一句就講：「第 1 輪不要追求 perfect、預期會有未發現問題、設計第 2 輪去 catch」。

去掉「第 1 輪該寫對」的隱含預設、釋放認知資源。

### 2. 列出 N 輪的 frame 清單

每輪用什麼 frame、catch 什麼。例：

```text
輪 1：生成 — idea → 字
輪 2：對意圖 — 跟原意對齊嗎
輪 3：機會成本語氣 — 絕對主義詞翻成 trade-off
輪 4：grep-ability — 關鍵字前置嗎
輪 5：反例 / 邊界 — 何時不適用寫了嗎
```

### 3. 何時可跳輪

不是所有情境都跑全輪。寫清楚「跳輪的合理情境」、避免「跑全輪 = 過度工程」的反彈。

### 4. 跨 frame 的不可替代性

明示：**輪 N 不能用「再跑一次輪 N-1」取代** — 不同 frame 才能 catch 不同層。重複同 frame = 同類錯一直 miss。

---

## 反模式：「我自己會 review」當 pillar 替代

```text
不該寫：「請務必在送出前自行 review。」
應該寫：「此 methodology 的第 N 個 pillar 是 Multi-pass Review、含 1-5 輪 frame：⋯⋯」
```

「自行 review」= L1 紀律（[external-trigger-for-high-roi-work](./external-trigger-for-high-roi-work.md)）= 預期失敗。

「列入 pillar + 列輪次 + 列 checklist」= L3-L5 結構性對策 = 結構強制執行。

---

## 跟其他抽象層原則的關係

| 原則                                                                                                | 關係                                                                                                     |
| --------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| [external-trigger-for-high-roi-work](./external-trigger-for-high-roi-work.md)                       | 本卡是該卡在 methodology 設計層的展現 — appendix-level 是 L1 紀律、pillar-level 是 L3-L5 結構            |
| [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md) | Methodology 設計這個動作本身就是 multi-pass 的對象 — 第一版 pillar 不對、要 review                       |
| [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md)                     | 寫 methodology 時、便利的寫法是「核心 3 條 + 細節塞 appendix」、跟「使用者實際需要 multi-pass 跑」不對齊 |
| [minimum-necessary-scope-is-sanity-defense](./minimum-necessary-scope-is-sanity-defense.md)         | Pillar 不該過度膨脹、但「該升的內容沒升」是反向偏差、本卡是補該原則的另一邊                              |

---

## 判讀徵兆

| 訊號                                                  | 該做的事                                        |
| ----------------------------------------------------- | ----------------------------------------------- |
| Methodology 文件結尾有「最後 review 一下」            | 升 pillar                                       |
| Pillar 列表只 3 條、但 reference 多次提到「再過一次」 | 缺 multi-pass pillar                            |
| Multi-pass 內容散在 ≥ 3 個地方                        | 抽 pillar、各 reference 引用                    |
| 「進階使用者再 review」這類分級                       | 結構訊號錯位 — multi-pass 不是進階、是 baseline |
| 使用者反饋「我忘了 review」                           | 結構問題、不是紀律問題、升 pillar               |
| Reference 結尾 self-check 沒人用                      | 位置太尾、提升結構地位                          |
| 新 methodology 文件第一版                             | 預設加 multi-pass pillar、不是寫完才補          |

**核心**：Methodology 設計的 pillar / appendix 切分**不是內容深淺問題、是執行率問題**。Pillar 層必跑、appendix 層不跑。把 multi-pass 視為「附帶」= 結構性確保它不被執行。**真正必要的東西要升結構、不能藏在末尾**。
