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

Multi-pass review 還需要 surface inventory。Frame 定義每輪看什麼品質；surface inventory 定義每輪掃哪些文字位置。當產物包含 title、description、heading、link label、MOC / index entry 時，這些 metadata / navigation surface 要跟正文跑同一輪 review。細節見 [metadata-surface-in-writing-review](./metadata-surface-in-writing-review.md)。

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

**Production 教學文章再追加（catch 字句層問題、跑 N 輪後仍漏同類問題時觸發）**：

- **輪 8**：keyword bank 比對（換工具）— 跑 grep 比對固定 keyword list（口語修辭 / 廢話前綴 / 地區漂移 / 依賴 code）、不靠 reviewer 記憶
- **輪 9**：reader simulation（換視角）— 拿掉所有 code block 重讀、跳到段落中間直接讀、catch reviewer 的「fill in 上下文」盲點
- **輪 10**：self-criticism（換層次）— 跑「我這份規則本身在這個情境是否夠細、有沒有 miss 的 frame」、反向審視 framework 本身覆蓋度

跳輪規則：短文 / 即時 note 跳 4-7 + 8-10、production 教學文章在輪 5 後仍系統性漏同類問題時 opt-in 8-10。詳見 [multi-pass-review-frame-granularity](./multi-pass-review-frame-granularity.md)。

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

## Stakes-conditional 追加輪：Epistemic Rigor

5 輪基本 frame 是 frame 軸（生成 / 意圖 / 語氣 / grep / 反例）；**高 stakes 內容**（reader 照做後錯誤不可逆 / 系統層 / 不可分批 ship 修正）追加 stakes 軸的 **輪 E：epistemic rigor**——比照學術 peer review 的 claim / evidence / method / threats / citation 五個 sub-check、確認論述強度足以承擔 reader 直接 implement 的下游風險。

### 啟動條件（opt-in、不污染預設）

| 內容類型                                       | 是否跑輪 E     |
| ---------------------------------------------- | -------------- |
| 一般技術文章（layout / refactor / debug 教學） | 不跑（5 輪夠） |
| 資安 / cryptography / 防護 mitigation 教學     | **跑**         |
| Concurrency 正確性 / memory model claims       | **跑**         |
| Distributed consistency / consensus 演算法     | **跑**         |
| Financial 計算 / accounting / settlement       | **跑**         |
| Medical / safety-critical 計算                 | **跑**         |
| 任何「reader 照做後錯誤不可逆 / 系統層」的內容 | **跑**         |

判別啟動的核心問題：「**reader 照這段實作會不會在生產系統留 silent gap、且不能靠後續 ship 修補**？」——會 → 跑輪 E、不會 → 5 輪即可。

### 輪 E：Epistemic Rigor 的 5 個 sub-check

```text
E.1 Claim：每個結論可拆 falsifiable 子句嗎？
    - reader 讀完能說「在 X 條件下 Y 成立、Z 條件失效」嗎？
    - 不能拆 = false sense of security 產地、補 boundary

E.2 Evidence：claim → evidence 推論鏈完整嗎？
    - 跳步驟的地方在哪？
    - 「業界常用」「最佳實踐」當論證 = appeal to convention、不是 evidence
    - 補 mechanism / 前提鏈

E.3 Method：reader 照 method 做能反向驗證嗎？
    - 「使用 X」單一 control 名稱 = 字面層 mitigation
    - 補 mechanism + deployment 條件 + 失效訊號

E.4 Threats（含 context-dependence）：什麼前提失效會 invalidate？
    - 哪些 deployment 條件改變方法有效性？
    - 在 5 輪輪 5（反例）的基礎上、specific 化到「條件變數」維度

E.5 Citation：版本 / 句意 / current best practice 都對嗎？
    - 引用標準有無標版本 / 年份？
    - 原文 quote 跟轉述是否語意一致（conditional → unconditional drift）？
    - 引用內容仍是 current best practice、還是已 deprecated？
```

### 輪 E 的產出格式

跑完輪 E、每個 weakness 對應到一個 dimension + tier（accept / minor revise / major revise / **withdraw**）：

- **Accept**：該段沒 weakness 或在容忍範圍
- **Minor revise**：補 boundary / contrast / 版本標記類小改、不阻擋 ship
- **Major revise**：結構性 false sense、需重寫、ship 前必須修
- **Withdraw**：教錯主動誤導 reader（過時 crypto 沒標 deprecated / 扭曲 citation 反向違反現行標準 / defense theater 當示範），保留 = 增加生產系統 risk、必須移除或全換

withdraw tier 是高 stakes 內容跟一般內容的關鍵差異——一般內容 review 沒有「保留 = 增加 risk」的硬決策、高 stakes 必須有。

### 跟 5 輪基本 frame 的分工

| 軸       | 5 輪基本 frame                         | 輪 E（高 stakes 追加）                                                   |
| -------- | -------------------------------------- | ------------------------------------------------------------------------ |
| 軸定位   | Frame 軸：每輪換一個寫作品質視角       | Stakes 軸：論述強度檢查                                                  |
| 觸發     | 預設全跑（依 output 類型可跳少數輪）   | 高 stakes 內容才 opt-in                                                  |
| 找的問題 | typo / 偏題 / 絕對主義 / grep / 邊界缺 | claim 空降 / 對位失效 / context 缺 / citation 過時 / withdraw-level 教錯 |
| 失敗後果 | 文字品質低、reader 用力讀              | reader 照做後實作出生產破口、silent failure                              |

兩軸正交、不取代——高 stakes 內容兩軸都跑（5 輪 frame + 輪 E stakes）、一般內容只跑 5 輪。輪 E 不在 5 輪裡是因為：把 epistemic rigor 設為預設會讓一般文章 over-audit、稀釋 review 紀律；設為 conditional opt-in 才能讓高 stakes 場景拉到學術級而不污染日常寫作。

→ 詳細的維度展開（threat model 對稱 / mitigation 對位 mechanism / context-dependence / citation 時效）跟 audit recommendation tier 判斷標準、見 [auditing-articles](../auditing-articles.md) reference。

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

| 原則                                                                                                  | 關係                                                                                                                  |
| ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| [ease-of-writing-vs-intent-alignment](./ease-of-writing-vs-intent-alignment.md)                       | 輪 2 的核心判斷標準 — 為什麼便利寫法 ≠ 對齊意圖                                                                           |
| [literal-interception-vs-behavioral-refinement](./literal-interception-vs-behavioral-refinement.md)   | 本卡是該卡在「寫」這個動作的具體實例 — review 是 multi-pass、不是 hook                                                |
| [naming-as-iterated-artifact](./naming-as-iterated-artifact.md)                                       | 本卡的輪 4 在 naming 場景的特化                                                                                       |
| [methodology-multi-pass-embedding](./methodology-multi-pass-embedding.md)                             | 本卡的 5 輪設計就是 compositional-writing 該 embed 為核心原則的內容、不該塞 appendix                                  |
| [metadata-surface-in-writing-review](./metadata-surface-in-writing-review.md)                         | 本卡定義 frame 軸，該卡補 surface 軸                                                                                  |
| [multi-pass-review-frame-granularity](./multi-pass-review-frame-granularity.md)                       | 本卡的延伸—frame 顆粒度盲點、補 keyword bank / reader simulation / self-criticism 三機制處理「跑 N 輪仍漏」字句層問題 |
| [colloquial-rhetoric-erodes-technical-precision](./colloquial-rhetoric-erodes-technical-precision.md) | 輪 8 keyword bank 的具體展開—口語修辭 keyword 清單                                                                    |
| [prose-self-contained-without-code-reference](./prose-self-contained-without-code-reference.md)       | 輪 9 reader simulation 的具體展開—拿掉 code 重讀的自測                                                                |
| [regional-terminology-alignment](./regional-terminology-alignment.md)                                 | 輪 8 keyword bank 的另一具體展開—地區漂移 keyword                                                                     |
| [design-flaw-by-current-axes-not-hindsight](./design-flaw-by-current-axes-not-hindsight.md)           | 輪 5 反例 / 邊界的進階—設計檢討類文章避免 hindsight 論述汙染                                                          |
| [agent-team-context-isolation](./agent-team-context-isolation.md)                                     | 本卡定義 frame 軸（一個 reviewer N 輪不同 frame）、該卡定義 instance 軸（N 個 reviewer 各自獨立）、兩軸正交可疊加     |
| [case-citation-three-part-structure](./case-citation-three-part-structure.md)                         | 寫作當下段落順序紀律（段首給概念定義、case 引用居中、通用展開）、是輪 2 對意圖 + 輪 5 反例的具體實作                  |

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

---

## 原則 6：多輪 Re-read Pass（Multi-pass Review）全文（自 SKILL.md 移入）

> SKILL.md 1.49.0 的〈6. 多輪 Re-read Pass（Multi-pass Review）〉原文，逐字保留，1.50.0 因入口檔 token 預算外移；SKILL.md 只留主張與本節路由。

完稿即進入 review 階段。一次寫對全部維度違反 working memory、實際結果是「每維度都做一半」。設計 N 輪 re-read、每輪用不同 frame：

| 輪  | Frame                                                                                                         | 抓什麼                                                                            |
| --- | ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 1   | 生成                                                                                                          | idea → 字、預期會有錯                                                             |
| 2   | 對意圖（[ease-of-writing-vs-intent-alignment](ease-of-writing-vs-intent-alignment.md)） | 正文、title、description、MOC hook 都跟原意對齊                                   |
| 3   | 機會成本語氣                                                                                                  | 全 surface 的絕對詞翻成 trade-off                                                 |
| 4   | Grep-ability / 命名 / 術語                                                                                    | title、slug、link label、段首關鍵字可單次 grep 命中；術語保留原文錨點與完整名詞頭 |
| 5   | 反例 / 邊界                                                                                                   | 「何時不適用」段、反模式列表                                                      |

Surface enumeration 是 multi-pass 的固定前置步驟。寫作產物包含 body surface 與 metadata / navigation surface：`title`、`description`、`tags`、heading、link label、MOC / index entry、slug / filename。每輪 frame 都掃這份 surface 清單，讓正文與讀者入口共用同一個概念錨點。description / hook 對規則做壓縮時、**可以丟細節、不可以改模態** — 把本體的「條件允許（可延後但要記錄）」壓成「絕對禁止（不可跳過）」、讀者依摘要行動就會偏離本體；摘要讀起來比本體「更有力、更乾脆」就是失真訊號、模態詞跟主詞動詞同級、最後砍。實測一批七份文件有四份的 description 出現模態漂移 — 這個檢查每批都要跑。

**核心**：「再仔細一次」≠ multi-pass — 同 frame 重看 catch 不到新問題。每輪換 frame、才能 catch 不同層。各 reference（writing-articles / writing-code-comments / writing-documents / writing-prompts）依 output 類型有特化的輪次組合。

Naming 是這條原則最容易跳的子場景 — 第一版命名幾乎不對、四輪 review（第一版 / grep / cross-call-site / impl 洩漏）才收斂、見 [naming-as-iterated-artifact](naming-as-iterated-artifact.md) 跟 writing-code-comments 的 naming review 段。術語是 naming 的高歧義子場景：翻譯術語第一次出現保留原文錨點，中文壓縮術語保留完整名詞頭，中文名詞頭要保留來源中的概念角色，轉換他人材料時強度詞停在原文量級（保真轉換鎖定量級、原創文案與宣告過的再創作以訴求效果為準），見 [terminology-keeps-original-anchor](terminology-keeps-original-anchor.md)、[compressed-chinese-terms-need-head-noun](compressed-chinese-terms-need-head-noun.md)、[translation-must-preserve-concept-role](translation-must-preserve-concept-role.md) 與 [rewrite-preserves-claim-intensity](rewrite-preserves-claim-intensity.md)。

**譯名不用讀者會先想到別的東西的詞（嚴重寫作錯誤）。** 管的是正文裡由外文概念翻來的術語；產品名、協定名、程式識別字與業界通用的縮寫（HTTP、JSON）不在此列，知識卡的標題格式另依專案規範。寫下每一個譯名時問一句：**除了要譯的這個概念，軟體或介面裡還有沒有另一個讀者常碰到的東西也叫這個名字？** 有的話，讀者在技術文件裡讀到它會先想到那一個，照那個意思學錯而且不會停下來問，因為那個詞他認得——cursor 譯成「游標」，讀者想到畫面上的游標；file handle 譯成「把手」，讀者想到介面上的拖曳把手；pagination bookmark 譯成「書籤」，讀者想到瀏覽器書籤；short-circuit evaluation 譯成「捷徑」，讀者想到桌面捷徑。軟體以外的日常意思本身不構成違規：「旗標」的日常意思是旗子、「交易」是買賣，而軟體與介面裡沒有另一個東西叫這兩個名字，讀者在技術文件裡讀到它們只會想到 flag 與 transaction，合規；「鉤子」「管線」「記憶體」同理。比對的是中文名稱：看台灣的軟體介面上那個東西實際顯示的中文字，英文同名不算——例如英文 header 另指文書軟體的頁首，但那個東西在台灣介面上顯示的是「頁首」，不能拿來判定「標頭」違規；兩份探針曾這樣從英文反推。日常功能相似不能拿來當合規的理由：「游標」也是「標記目前位置」，讀者照樣先想到畫面上的游標。問句排除要譯的那個概念本身（「鉤子」在軟體裡指的正是 hook，不算另一個東西）；先前的版本問「讀者第一個想到的是不是要譯的這個概念」，判斷者因此把旗子、買賣這類軟體以外的意思也算進去，兩批探針實測各有兩份誤判；現在的問句把比較範圍限定在軟體或介面裡的另一個東西。自己拿不準時，用術語探針量（問「在技術文件裡讀到這個詞，第一個想到什麼；它在軟體或介面裡是什麼」）。這一問只能在寫的當下做：作者與同源審查者都知道那個詞在這裡指什麼，所以讀起來通順，看不出問題。修法依序是：先查承載這個概念的知識卡或術語表有沒有已定案的寫法，有就照用；沒有就把英文詞在這個情境裡指的東西寫成一句話（英文詞有多個意思就每個意思各自處理）、再找讓詞面直接說出功能的譯名（讀字面就知道它做什麼），找不到就自組描述功能的短語（分頁的 cursor 寫「接續標記（cursor）」、資料庫的寫「查詢結果的讀取物件（cursor）」），短語說不清就改寫成完整的一句話，再附英文原詞；**替代譯名同樣要過這一問**——一次探針實測裡，替「書籤」找替代時提出的候選之一是「分頁遊標」，又回到同一個錯誤。定案的譯名寫回知識卡，讓下一位作者照用，同一個概念才不會有兩個名字。量過之後各份探針給的定義仍收斂不到同一個所指的詞（test oracle），第一次出現寫一句中文描述再附英文原詞，之後同一篇可以只寫英文詞。第一次出現寫「中文（original term）」，之後以中文為主，程式識別字與討論英文詞本身時用英文；**沒有任何中文說明、只寫英文，是把翻譯工作交給讀者**，也不算修好。既有譯名在其他中文資料裡流通時，附一句「其他中文資料常寫作 X」，讓讀者拿舊譯名也對得上。沿用查得到的既有譯名之前，先看那份文件裡用法一不一致、是不是機器翻譯；某個譯名「很常見」要先問常見在哪一種中文的語料（繁中或簡中）。詳見 [borrowed-everyday-word-as-translated-term](borrowed-everyday-word-as-translated-term.md)。

**高 stakes 內容追加輪 E（epistemic rigor、conditional opt-in）**：reader 照做後錯誤不可逆的內容（資安 / concurrency 正確性 / distributed consistency / financial / medical）在 5 輪基本 frame 之外、追加 stakes 軸的 epistemic rigor pass——比照學術 peer review 跑 claim / evidence / method / threats / citation 五個 sub-check、加上 audit recommendation tier（accept / minor / major / withdraw）。一般內容 5 輪夠、不跑輪 E；高 stakes 內容兩軸都跑。詳見 `references/auditing-articles.md` 跟 `references/principles/writing-multi-pass-review.md` 的「stakes-conditional 追加輪」段。

**Production 教學文章追加輪 8-10（字句層 catch、跑 N 輪仍漏時觸發）**：跑了 5 輪基本 frame 仍系統性漏 catch 字句層問題（口語修辭 / 廢話前綴 / 地區漂移 / 依賴 code / **裝飾符號 emoji** / 對讀者喊話 / 自評誇飾 / 必然性框架 / 恐嚇式語氣 / 歸因語氣）時、追加三個換軸機制——輪 8 keyword bank（換工具、含 emoji / 裝飾 unicode 掃描）、輪 9 reader simulation（換視角、四 lens：自包含性 + register/stance + meta 殘留 + AI 歸因過度）、輪 10 self-criticism（換層次、審視 framework 本身覆蓋度）。短文 / 即時 note 不需要、production 教學文章在跑 5 輪後仍漏同類問題時 opt-in。**keyword bank 命中是候選、不是判決**——grep 命中後仍要一個語意判定步驟（這個命中是建立概念的違規、還是合規的反例對照 / hook），reviewer 容易把違規合理化放行；偵測（bank）跟判定（語意）是兩個認知步驟。**register/stance 類（喊話 / 誇飾 / 必然）無穩定關鍵詞、keyword bank 抓不到、輪 9 reader-sim 是主 keyword bank 是輔、且最依賴 external cold-read**。漏抓後補機制前先分 **design gap**（框架缺 frame、改框架）vs **execution gap**（框架有 frame 但只跑了臨時子集、改執行不是改框架）——「加 keyword」對 execution gap 跟無關鍵詞的類都無效。詳見 [multi-pass-review-frame-granularity](multi-pass-review-frame-granularity.md)、[decorative-symbols-keyword-bank](decorative-symbols-keyword-bank.md)、[teaching-prose-neutral-register](teaching-prose-neutral-register.md) 跟 `references/writing-articles.md` 輪 8-10 段。

**批量 sibling 寫作的生成端輪替**：一次寫多份同類文件時、cadence 同質化會在六個層發生（title 形式 / 開場句式 / 章節標題 / 敘事骨架 / 條目形態 / 跨檔引用句）、單份 review 全部抓不到、且 review 端抓過的同骨會在下一批復發 — 同類 finding 第二次出現、就把規則升到生成端：寫之前排好開場 frame 輪替（規則先行 / 後果先行 / 動作先行 / 反差先行）、條目形態輪替、敘事視角輪替、引用句去重。詳見 [cadence-homogenization](cadence-homogenization.md)。**以集合裡的舊文章當範本寫新稿時，範本的句型缺陷可能跟著進來**：一次實測裡，舊文章用來組織集合的譬喻（「這條線」「各接一個面」「由 X 承接」「X 的決定落在 Y」）在七份新稿初稿裡每一份都出現，連「把讀者做的決定寫成分類的屬性」這個錯誤也一樣；而同一組詞在同一網站沒有這批範本的其他集合也常見，所以範本與生成端自己的用詞習慣都可能是成因。寫新稿之前用 bank〈結構譬喻頂替主詞與動詞〉那一條掃範本，寫完之後用同一條掃自己的初稿，新稿與範本一起修；bank 的其他類別照原本的完稿掃描跑。詳見 [structural-metaphor-replaces-actor-and-verb](structural-metaphor-replaces-actor-and-verb.md)。

**驗證手段要對齊錯誤的層次**：字面攔截（掃得到的固定字串）與行為精煉（要看行為才判得出的）是兩種錯誤層次，用錯層的手段驗不出東西而報告看起來正常。詳見 [literal-interception-vs-behavioral-refinement](literal-interception-vs-behavioral-refinement.md)，那裡給兩層的分界與各自該用的驗證手段。

**Instance 軸：跨 reviewer instance 隔離**：Instance 軸是 multi-pass review 的另一條擴展軸 — N 個獨立 reviewer instance 各自獨立 context、各自跑 background、解「單一 reviewer 同時看多維度容易維度盲點 + context 污染」的問題。Instance 指獨立 reviewer 程式實體（如 agent tool spawn 出的 subagent）、跟同一 reviewer 換輪次 frame（frame 軸）正交可疊加。適用 production 教學文章 / 高 stakes 內容 / 跨章節教學模組這類維度複雜度高的審查場景。詳見 [agent-team-context-isolation](agent-team-context-isolation.md)。

詳見 [Writing 的 multi-pass review](writing-multi-pass-review.md)、[Methodology 的 multi-pass 該 embed 在 pillar](methodology-multi-pass-embedding.md)、[Metadata surface 要納入寫作 review 範圍](metadata-surface-in-writing-review.md)、[False sense of security 是高 stakes 寫作的主要失敗模式](false-sense-of-security-as-primary-failure.md)、[Risk-asymmetric audit standard](risk-asymmetric-audit-standard.md)、[colloquial-rhetoric-erodes-technical-precision](colloquial-rhetoric-erodes-technical-precision.md)、[prose-self-contained-without-code-reference](prose-self-contained-without-code-reference.md)、[regional-terminology-alignment](regional-terminology-alignment.md)、[multi-pass-review-frame-granularity](multi-pass-review-frame-granularity.md)、[design-flaw-by-current-axes-not-hindsight](design-flaw-by-current-axes-not-hindsight.md)、[agent-team-context-isolation](agent-team-context-isolation.md)、[decorative-symbols-keyword-bank](decorative-symbols-keyword-bank.md)、[teaching-prose-neutral-register](teaching-prose-neutral-register.md)。
