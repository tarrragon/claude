# Writing 的 multi-pass review：寫不是一輪、是 N 輪不同 frame

> **角色**：本卡是 `compositional-writing` 的支撐型原則（principle）、被 SKILL.md 第 6 原則「Multi-pass Review」直接引用為其核心展開、被 `references/writing-articles.md` / `writing-code-comments.md` / `writing-prompts.md` / `writing-documents.md` 在「自檢不是 multi-pass」段引用。
>
> **何時讀**：寫完一段文字（文章 / 註解 / doc / prompt / commit message）想直接 ship 時、用本卡判斷該跑哪幾輪 review。

---

## 結論

寫文字（文章 / 註解 / doc / prompt / commit message）的 ROI 來自 **N 輪不同 frame 的 re-read**、不是單次「寫對」。每輪 catch 上一輪 frame miss 的東西：

| 輪次 | Frame                                                                                     | 抓什麼                                                                                    |
| ---- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| 1    | 生成                                                                                      | 把 idea 變字、預期會有錯                                                                  |
| 2    | 對意圖（[ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md)） | 寫出來跟原意對齊嗎、有沒有便利驅動的偏移                                                  |
| 3    | 機會成本語氣                                                                              | 有沒有「應該」「不行」「正確」絕對主義？是不是該翻成「在 X 情境下 A 較好、Y 情境 B 較好」 |
| 4    | Grep-ability / 命名                                                                       | 關鍵字前置嗎？AI 能單次 grep 命中嗎？                                                     |
| 5    | 反例 / 邊界                                                                               | 「何時不適用」段寫了嗎？反模式列了嗎？                                                    |

每輪用「跟前一輪不同的眼睛」看同一份文字 — 才能 catch 不同層的問題。**第 1 輪的 frame 不可能同時 catch 所有層**（見 [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md) 字面 vs 行為的 ceiling）。

---

## 為什麼一輪寫不出全部維度

寫的時候 working memory 有限、必須 collapse 多個維度去專注其中之一：

- **生成 frame** 在意 idea 完整 → 顧不上語氣
- **語氣 frame** 在意「機會成本 vs 絕對主義」→ 顧不上 grep-ability
- **grep frame** 在意關鍵字前置 → 顧不上反例

要求一輪同時 catch 所有 = 認知超載。實際結果是「每個維度都做一半」。

**多輪設計接受 working memory 限制、用 N 輪解 N 維**。每輪只專注一個 frame、效率反而高。

---

## 五輪 review 的具體 checklist

### 輪 1：生成

- [ ] idea 從頭寫到尾、不停下來改
- [ ] 預期會有 typo、結構亂、語氣不對 — 不在這輪修
- [ ] 跑得到結尾比寫得漂亮重要

### 輪 2：對意圖（[ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md)）

- [ ] 開頭一句講清「這段在說什麼」嗎？
- [ ] 有沒有「便利驅動偏移」— 寫得順但其實偏題了？
- [ ] 段落順序是不是「好寫」決定的、不是「易讀」決定的？
- [ ] 有沒有「為了補滿格式」寫的廢段？

### 輪 3：機會成本語氣

- [ ] 跑 grep 抓「應該 / 必須 / 不行 / 不可以 / 正確的方式 / 唯一」這些絕對詞
- [ ] 每個絕對詞檢查：是物理 / 法律 / 安全事實嗎？不是的話翻成「在 X 情境下 A 較好、Y 情境下 B 較好」
- [ ] 反模式表的「為什麼不好」寫到「違反某個原則」、不寫「就是不對」

### 輪 4：Grep-ability / 命名

- [ ] 關鍵字在段首、不在段中
- [ ] 表格欄位用 grep 友善的分隔（`:` `|` `→`）
- [ ] 檔名 / slug 跟 title 對應、不要用流水號
- [ ] 命名能用單次 grep 命中、不需要語意推理

### 輪 5：反例 / 邊界

- [ ] 「何時不適用」段寫了嗎？
- [ ] 反模式表給「為什麼不好 + 修法」嗎、還是只給警告？
- [ ] 跨卡 cross-link 補了嗎？
- [ ] 有沒有 over-claim、把「在多數情境下」說成「總是」？

---

## 套用到不同 output 類型

每類有特化的輪次組合：

### 文章（長篇技術文章 / post-mortem）

完整跑 1-5 輪。額外加：

- **輪 6**：跨卡 cross-link 健康度（單向引用 vs 雙向）
- **輪 7**：放回索引條描述對應到內容嗎

### 程式註解（doc comment / inline）

跑 1-3 輪 + 額外：

- **輪 4'**：grep-ability 改成「介面 vs 實作分層」— doc comment 不洩漏 impl、inline comment 講 why 不講 what
- **輪 5'**：反例改成「這個註解 5 個月後讀還看得懂嗎」（時間軸 robust）

### Naming（變數 / 函式 / 檔名 / slug）

→ 見 [naming-as-iterated-artifact](./naming-as-iterated-artifact.md)、有特化的 4 輪設計。

### Prompt（給 LLM 的指令）

跑 1-3 輪 + 額外：

- **輪 4''**：模糊指令 — 「對齊」「靠近」這類詞翻成具體數字 / 條件
- **輪 5''**：「邊界 case 預期行為」明示了嗎

---

## 反模式：跳輪的代價

| 反模式                               | 後果                                        |
| ------------------------------------ | ------------------------------------------- |
| 寫完直接 ship、跳過所有 review 輪    | 第 1 輪生成 frame 沒抓到的全部漏            |
| 每輪用同個 frame review              | 角度沒換、重複 catch 同類錯、新類錯不會浮現 |
| 「我邊寫邊改」融合多輪               | working memory 超載、每維都做一半           |
| 跳過輪 3 機會成本語氣                | 絕對主義教讀者規則、不教思考                |
| 跳過輪 4 grep                        | AI 找不到、文字變孤兒                       |
| 跳過輪 5 反例                        | 看起來是教條、不是 trade-off                |
| 「下次寫的時候多注意」當 review 取代 | 高 ROI 無觸發、紀律失效                     |

---

## 何時可以跳某些輪

| 情境                          | 可跳的輪                            |
| ----------------------------- | ----------------------------------- |
| 內部 quick note、不會有人看   | 跳 4 + 5（grep + 反例）             |
| Commit message                | 跳 4 + 5、留 1-3                    |
| Slack / chat 即時對話         | 只跑輪 1                            |
| 引言 / 標題                   | 1-4 都跑、5 可省                    |
| 摘要 / TL;DR                  | 1-3 + 5（反例不適用、但語氣很重要） |
| 純資料填寫（schema / config） | 跳 3、其他都跑                      |

四類共通：**ROI 不同、輪次組合不同**。Production 文件 / 卡片 / 註解 全跑、即時通訊只跑核心。

---

## 跟其他抽象層原則的關係

| 原則                                                                                                | 關係                                                                                 |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md)                     | 輪 2 的核心判準 — 為什麼便利寫法 ≠ 對齊意圖                                          |
| [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md) | 本卡是該卡在「寫」這個動作的具體實例 — review 是 multi-pass、不是 hook               |
| [naming-as-iterated-artifact](./naming-as-iterated-artifact.md)                                     | 本卡的輪 4 在 naming 場景的特化                                                      |
| [methodology-multi-pass-embedding](./methodology-multi-pass-embedding.md)                           | 本卡的 5 輪設計就是 compositional-writing 該 embed 為核心原則的內容、不該塞 appendix |

---

## 判讀徵兆

| 訊號                               | 該做的事                                                 |
| ---------------------------------- | -------------------------------------------------------- |
| 寫完直接 commit、覺得「OK 應該夠」 | 跑五輪、每輪都會抓到東西                                 |
| 每次 review 都「看不出哪裡可改」   | Frame 沒換、改用下一輪的 frame 看                        |
| 「這次先這樣、下次寫好一點」       | 是結構性跳過、補 trigger（pre-commit / template / pair） |
| 反模式段空白                       | 跳了輪 5、補                                             |
| 找不到自己寫過的卡                 | 輪 4 沒做、grep-ability 漏掉                             |
| 文字看起來像教條                   | 輪 3 的絕對主義詞沒翻、補                                |
| 段落開頭看不出在說什麼             | 輪 2 的意圖顯性沒做                                      |

**核心**：Writing 的 ROI 來自**多輪不同 frame**、不是單次「寫得仔細」。要寫得仔細的部分太多、超過 working memory、必須分輪。**跳輪的代價是某維度永遠做一半、累積成「看起來都對但其實有漏」的低品質文字**。
