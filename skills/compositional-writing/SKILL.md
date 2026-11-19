---
name: compositional-writing
description: "Composes atomic, intent-revealing, grep-friendly writing (Zettelkasten) for code comments, docs, logs, prompts, schema/ticket fields, external-analysis transformation, and long-form technical articles. Also supplies the keyword bank for multi-round review / batch review / 寫作 audit (〈字句層 keyword bank（完整清單）〉). Triggers: 寫註解, 寫文件, 寫日誌, 寫 prompt, 寫文章, 技術文章, post-mortem, 欄位設計, 多輪審查, multi-round review, 寫作 audit, 字句層 grep, 示範指令, 解法比較, 文章拆分."
license: MIT
metadata:
  portable: true
  version: 1.65.1
  category: writing-methodology
---

# Compositional Writing

以 Zettelkasten（卡片盒筆記法）為核心的寫作方法論：每段文字是可重複組合的原子卡片，人類讀者與 AI 代理人以最小認知負擔找到答案。

---

## 這份檔案是綱領層

本檔給原則的主張、判別線與路由；可執行的操作在 `references/` 各情境的 reference（步驟與範例）與 `references/keyword-bank.md`（可直接跑的 rg 指令）。讀完主張後的第一個動作是到〈When to Consult This Skill〉找自己的情境、打開對應檔。各原則的論證、實證與邊界在 `references/core-principles.md`。

## 動手之前先定這一份的定位

**定位決定體例，所以它在所有規則之前。** 寫下一句話：誰讀、讀完要做什麼。這一句是後面每條規則的過濾器，也是選 reference 的依據。判別軸是動作落在哪裡：在世界上動手，還是在腦中重新歸類。

| 定位             | 讀者               | 體例                                         | Reference                          |
| ---------------- | ------------------ | -------------------------------------------- | ---------------------------------- |
| Agent 指令、規範 | 照著執行的執行者   | 操作手冊：步驟編號、判錯代價                 | `reference-authoring-standards.md` |
| 人類教材         | 來理解一件事的人   | 引導與脈絡：講清楚為什麼是這個順序           | `writing-articles.md`              |
| 程式碼註解       | 正在讀那段程式的人 | 只解釋商業邏輯，原理讀程式碼就有             | `writing-code-comments.md`         |

會讓稿件被讀成手冊的裝置（表徵對映清單、檢查順序、配比數字、順序加顛倒後果、可執行判斷標準、具體器具、序列連接詞（「首先」「接著」「最後」這類標出步驟順序的詞））改的是框架、不是刪資訊。裝置清單與處置見 `references/core-principles.md`〈動手之前先定這一份的定位〉與 [positioning-decides-form-before-any-rule-applies](references/principles/positioning-decides-form-before-any-rule-applies.md)。

## 每一句先填槽位再成句（生成端規格）

寫的當下用，不等審查。描述操作的句子有四個槽位：**動作者、動詞、受詞、結果**，每格填這個領域裡實際存在的東西，量詞計數的是領域裡的單位。判斷問句是受詞是不是動詞在這個領域裡能作用的對象（「執行」作用於指令，「一個字都沒有執行」的受詞在領域外）；範圍要在句內具名；判定者不代填槽位。

**每一個子句的主詞都要做得了它的動詞**，描述句、論斷句、標題與段標都一樣；兼語句（「讓音樂整體流過」）看被使役的那一方，省略的主詞先補出來再問；受事當主詞的句子（「這首曲子演奏得很快」）與活動名詞當主詞的句子（「審查找到三處」「實測顯示」）照省略主詞處理，補出施事再問。**主詞是物**指主詞不是人、也不是由人組成的團體（錄音、作品的段落、身體部位、文件、抽象概念、程式、指標）；主詞是物時，每一個子句都問一次：**這個主詞本身，或它在這個領域裡慣用來指的人，做得了這個動詞嗎？** 「慣用來指的人」是這個詞在領域裡的固定用法（樂器指演奏者、書指作者），不是判定者從這一篇的上下文推出來的動作者；從上下文才推得出的，照「判定者不代填槽位」改寫。「這個動詞」取它在這個領域裡有定義的意思（樂理的回到主調、進行、解決、應答，程式的回傳、掛載、資料流過）；領域裡沒有這個定義、只是借來說明的意思時，照它平常字面的動作問，要把動詞換成另一個詞（「給」說成「提供」）才做得了的，算做不了。做不了，就改寫成實際做這件事的一方，或改用描述這個物的狀態或屬性的動詞。這是要靠判斷的一問，答案沒有機械條件，不拿詞表或慣用說法的出現次數當門檻；下面的例子分屬兩個方向，括號裡是它依的屬性：

- 做得了，這一問可以留（其他槽位照常判）：「法國號在舞台外演奏」（法國號慣用來指吹法國號的人，那個人做得了演奏）；「這本書討論……」（書慣用來指作者，作者在書裡做得了討論）；「伺服器回應 404」「函式接受兩個參數」（回應、接受是程式依設計產生的行為，程式本身做得了）；「第三樂章最後回到主調」（回到主調是樂理定義的調性變化，樂章本身做得了）；「這份報告建議……」（報告慣用來指作者，作者在報告裡做得了建議）；「探針補錯了主詞」（探針是模型，模型本身做得了讀與補）；「這個設定影響快取命中率」（影響是因果關係，設定本身做得了）。
- 做不了，要改：「錄音給不了現場的音量」→「錄音記錄下來的動態範圍比現場窄」（「給」是把東西交到對方手上；現場的音量不是錄音交出的東西，動態範圍窄是錄音的屬性）；「結尾往哪裡走」→ 寫出結尾實際怎麼變，原句指的是音量、配器還是調性就寫那一項（結尾是作品的段落，不會移動；「往哪裡走」不是樂理有定義的說法）；「小提琴唱出旋律」→「小提琴拉出如歌的旋律」（「唱」要用嗓子，樂理沒有定義這個說法）；「佇列給不了順序保證」→「這個佇列不保證訊息照送出的順序送達」（「給」要說成「提供」才做得了；保證或不保證才是佇列依設計的行為）；「HDD 給不了 SSD 的隨機讀取速度」→「HDD 的隨機讀取速度比 SSD 慢」（讀取速度是 HDD 的屬性，不是它交出的東西）；「這本書給不出那個粒度」→「作者在書裡沒有寫到那個粒度」（書慣用來指作者，作者在書裡做的是寫；「給」是交出東西，書寫到的內容不是作者交出的東西）；「這個案例告訴我們……」→「讀者從這個案例看得到……」（案例不慣用來指任何人，做不了「告訴」）。

判斷不出來時，照要改的那一邊改寫成實際的動作者或屬性：改寫可以撤回，留下擬人則要等審查才找得到。

改寫出來的句子再問一次同一個問題；用到承重類動詞或內容集合的結構譬喻時，另外照 [keyword-bank](references/keyword-bank.md) 的〈物理化錯配〉與〈結構譬喻頂替主詞與動詞〉檢查，這一問照樣問。

寫完一段就當場問，不等全篇寫完再審；改寫被點名的詞之後，拿改後的句子再問一次。逐句列主謂的做法、候選與痕跡寫在 [keyword-bank](references/keyword-bank.md)〈用詞搭配錯位〉擬人那一項。

論斷句、總結句、段標與過渡句在四個槽位之外另有兩格：

- **名詞的所屬**：來源、輸出、結果、原因、代價、差別、位置、範圍、邊界、訊號、層、線、情形這類名詞，把「誰的、什麼的」寫在這一句或緊接的前一句；形容詞與動詞不直接當名詞用。知識卡的段標例外與它的條件在 [keyword-bank](references/keyword-bank.md)〈名詞缺所屬〉。
- **動作者與時機**：主詞要做得了這個動作（主詞是物時照上面那一問）；順序是誰 → 在什麼時機 → 做了什麼 → 為什麼會觸發。指標、數字與清單配上動作動詞（決定要不要做某件事、告訴、要求）時不當主詞，改成受詞或依據，並寫出依它做事的一方（「CI 綠燈不會告訴你部署成功了沒」→「部署的人從 CI 綠燈看不出部署成功了沒」；「這個 metric 決定要不要擴容」→ 寫出是 autoscaler 還是值班的人依這個 metric 擴容）；配上描述狀態、比較或指涉的謂語（超過、比……慢、顯示、代表）時，句子裡沒有被藏起來的動作者，只照上面那一問判（「HDD 的隨機讀取速度比 SSD 慢」可以留）。這一條管每一種句子，不只論斷句。

組織全篇的框架詞（「X 回答的問題是」）把「回答」換成元件實際的動作、把「問題」換成它指的那一種（問句、故障、事項、主題或需求）。三種變體、實測與逐項判讀的全文在 [noun-without-its-owner-passes-the-slot-check](references/principles/noun-without-its-owner-passes-the-slot-check.md)〈每一句先填槽位再成句（生成端規格）全文〉。

## 示範指令的引數另有一條檢查（程式碼區塊適用）

句子層檢查走到程式碼區塊會停下。判斷問句：讀者要把這條指令用在自己的環境上，得改哪幾個位置，文章有沒有說過每個位置填的是什麼；掃描入口是區塊裡的字面值、不是佔位符；引數的有無改變行為時，兩條指令並列在同一個區塊。區塊怎麼排、註解裝什麼、何時改用參數表，全文在 `references/demonstrating-commands.md`〈示範指令的引數另有一條檢查（程式碼區塊適用）〉。

## Core Pillars（核心支柱）

| 支柱                                   | 意義                                                       |
| -------------------------------------- | ---------------------------------------------------------- |
| **Atomization** 原子化                 | 一段文字只承載一個概念，可獨立閱讀與重用                   |
| **Explicit Intent** 意圖顯性與層級貼合 | 讀者第一眼就看懂「為什麼在這裡、屬哪個抽象層級、該做什麼」 |
| **Searchability** 可查詢性             | 人和 AI 都能用關鍵字 / grep / regex 快速定位               |

---

## Core Principles（核心原則速查）

每條只留主張與路由；論證、實證與邊界在 `references/core-principles.md` 同名原則（原則 6 在 writing-multi-pass-review）。

### 1. 原子化（Atomization）

一張卡一個概念，能獨立理解、跨情境重用。拆分依據是讀者要同時 hold 的概念數（超過 7 就拆）與情境匹配度，行數不是依據。內容壓力的出口是擴充結構（就地展開、外部化成卡、換成連結），不是壓縮內容；壓縮論證的下界是一句話的理由，因為沒有理由的禁令讀者記不住、也判不出邊界。拆成多檔後另查交界，職責數從修改紀錄讀。

### 2. 索引建立（Indexing）

入口文件只做路由，引用深度最多一層。引用錨點用語意標題、不用位置編號或相對位置；同一個結構單位只有一個 canonical 名字（全篇指稱它時都用同一個名字，不換同義詞）；集合命名用角色、不內嵌數量；正文對象用內容名、不用序數或字母代號；切開集合時先寫依據再命名；摘要另一份內容時寫出成員、不寫計數；被多處逐字引用的標籤自帶限定語。

### 3. 意圖顯性與層級貼合（Explicit Intent & Layer Alignment）

寫作前先標記本文所在的抽象層級（實作 / 工具 / 協作 / 認知 / 架構），論述停在該層；寫「為什麼」與「要達成什麼」，把「程式碼在做什麼」留給程式碼。預設用機會成本語氣（情境化取捨）、不用絕對二元語氣，物理 / 法律 / 數學事實除外。讀者是缺經驗的專業人士；標題與段標寫主旨；判斷標準寫到條件層。這一原則的二十餘條款（讀者定位、敘事姿態、標題寫法、連貫、判斷標準、深度分配等）全部在 `references/core-principles.md`〈3. 意圖顯性與層級貼合〉。

### 4. 可查詢性（Searchability）

關鍵字前置、使用可 grep 的分隔符（`:` `|` `→` `==`）、欄位名稱用 regex 友善格式。行自足（一句話被單獨拿出來讀仍然看得懂）是配套義務：單句消費位（checklist 項、表格格、判斷標準句、章節首句這類常被單獨讀的位置）要命題完整、指涉閉合、實詞可反推、一句一命題，全文在 [sentence-self-sufficiency-by-consumption-unit](references/principles/sentence-self-sufficiency-by-consumption-unit.md)。句子層文法標準見上方〈每一句先填槽位再成句〉。

### 5. 欄位設計（Field Design）

同一份文件的不同欄位從不同角度觀察同一件事，不重複撰寫。欄位集合宣稱了「會有哪些結果」：值域沒有涵蓋的真實情形會逼填表者失真，修法是補值、不是補說明。

### 6. 多輪 Re-read Pass（Multi-pass Review）

完稿即進入 review。每輪換 frame（生成 → 對意圖 → 機會成本語氣 → grep-ability / 命名 / 術語 → 反例 / 邊界），同 frame 重看 catch 不到新問題；每輪先枚舉 surface（正文加 title、description、heading、link label、MOC entry、slug）；壓縮 description 可丟細節、不可改模態。字句層仍漏時追加輪 8-10、高 stakes 內容追加輪 E、批量 sibling 寫作要做生成端輪替、跨 reviewer instance 隔離為 Instance 軸。譯名不用讀者會先想到別的東西的詞。完整內容在 [writing-multi-pass-review](references/principles/writing-multi-pass-review.md)〈原則 6：多輪 Re-read Pass（Multi-pass Review）全文〉。

---

## When to Consult This Skill（觸發路由）

審查一份剛寫好的稿件時，第一步是依體裁開下表對應的 reference，逐項跑它的檢查項；接著開 `references/keyword-bank.md` 逐類跑字句層 grep；最後依原則 6 換 frame 重讀。

| 觸發情境                                                                 | 讀哪份                                                                      | 涵蓋章節                                                         |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| 寫或改程式碼註解 / doc comment                                           | `references/writing-code-comments.md`                                       |                                                                  |
| 起草 / 改寫文件（worklog、spec、README）                                 | `references/writing-documents.md`                                           |                                                                  |
| 設計 log / 錯誤訊息 / 結構化輸出                                         | `references/writing-logs.md`                                                |                                                                  |
| 撰寫給 AI 的 prompt / Agent 派發 / Ticket Context Bundle                 | `references/writing-prompts.md`（`ai-communication-rules.md` 的詳細版庫）   |                                                                  |
| 撰寫長篇技術文章（blog、post-mortem、架構決策、除錯復盤）                | `references/writing-articles.md`                                            |                                                                  |
| 外部分析 / 經驗談（含使用者貼來的論壇說法、問答、AI 回答）轉成教學型分析文章 | `references/source-to-teaching-analysis.md`                                 |                                                                  |
| 文章引用樂評、評測、使用心得、量測、考證或鑑定的結論、排名這類相對比較，或引用同時帶著評語的來源（任何體裁；不論引用的目的是佐證現況、佐證紀錄還是滿足收錄條件） | `references/source-to-teaching-analysis.md`                                 | 引用評價時留意它評的時間點                                       |
| 翻譯 / 轉譯、檢查譯名與超譯                                              | `references/translation-review.md`                                          |                                                                  |
| 句子與用詞層的受控寫作：一事一名、一詞一義、情態詞只用可以／會／必須、句長門檻 | `asd-ste100` skill（正體中文讀它的 zh-TW pack：句子規則與詞庫）                 | 本 skill 不重寫這組規則；篇章結構仍由本 skill 負責               |
| 管理多篇文章的結構（系列、MOC、跨篇引用、同一對象在兩個集合各有一頁）    | `references/managing-article-collections.md`                                |                                                                  |
| 結構決策（拆篇、擴充點、依賴方向、讀者分流）、拆成多檔後查交界           | `references/structuring-with-solid.md`                                      |                                                                  |
| 對高 stakes 內容做 reviewer-style audit                                  | `references/auditing-articles.md`                                           |                                                                  |
| 寫或檢查判讀 / 選型 / 決策類內容                                         | `references/judgment-content-needs-scenarios.md`                            |                                                                  |
| 並排比較幾種做法（比較表的欄、跨篇零件並排）                             | `references/principles/comparison-axis-comes-from-the-readers-decision.md`  |                                                                  |
| 示範指令（區塊內容、註解分工、並列兩條、參數表）                         | `references/demonstrating-commands.md`                                      | 示範指令的引數另有一條檢查（程式碼區塊適用）                     |
| 設計 ticket 欄位 / schema frontmatter / 表單欄位                         | `references/designing-fields.md`                                            |                                                                  |
| 驗證寫作品質（認知負擔、獨立理解率）                                     | `references/meta-metrics.md`                                                |                                                                  |
| 新增或修改 Skill reference                                               | `references/reference-authoring-standards.md`                               |                                                                  |
| 驗收 Skill 發布品質（Phase 2 dry-run）                                   | `references/dry-run-guide.md`                                               |                                                                  |
| 字句層審查、多輪審查的 Round 1-A、batch review、寫作 audit               | `references/keyword-bank.md`（本站字句層檢查的唯一權威清單）                | 字句層 keyword bank（完整清單）                                  |
| 多輪 re-read 的輪次設計、譯名檢查、批量 sibling 寫作                     | `references/principles/writing-multi-pass-review.md`                        | 原則 6；批量 sibling 寫作的生成端輪替；譯名不用讀者會先想到別的東西的詞 |
| 查原則 1 至 5 的論證與實證、定位的裝置清單、與跨章節教學模組流程的分工   | `references/core-principles.md`                                             | 原則 1-5 全文；動手之前先定這一份的定位；跟特化寫作流程的分工    |
| 查生成端規格的三種變體與名詞所屬的探針                                   | `references/principles/noun-without-its-owner-passes-the-slot-check.md`     | 每一句先填槽位再成句（生成端規格）全文                           |

每份 reference 自包含：以該情境為核心，把核心原則翻譯成可直接套用的檢查項與範例。`references/` 底下另有 `principles/` 支撐型原則卡與 `designing-fields-ticket-6w.md`（六欄位詳細範例，按需讀取）。

---

## Success Criteria（M1-M2 認知負擔類）

M1：讀者從 SKILL.md 出發，解決問題需開啟的檔案數 ≤ 2。M2：隨機挑一份 reference，不讀其他 reference 能否獨立套用，目標 100%。量測方式與自評表見 `references/meta-metrics.md`。

## 跟特化寫作流程的分工

本 skill 管單篇寫作（articles / comments / logs / prompts / fields）。跨 5 章以上、有案例庫支撐的教學模組另有跨章節生產流程（案例 audit、agent team 平行 review、跨檔修正、polish pass），每章內部仍套本 skill 的六條原則。分工表與疊加方式在 `references/core-principles.md`〈跟特化寫作流程的分工〉。

---

**Last Updated**: 2026-10-30

版本紀錄在同目錄的 `CHANGELOG.md`。
