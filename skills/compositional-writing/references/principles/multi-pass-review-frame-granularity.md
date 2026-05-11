# Multi-pass review 的 frame 顆粒度盲點：抽象規則 → 具體訊號的轉譯

> **角色**：本卡是 `compositional-writing` 的支撐型原則（principle）、是 [writing-multi-pass-review](writing-multi-pass-review.md) 的延伸——補上 frame 顆粒度議題、被 SKILL.md 第 6 原則「Multi-pass Review」直接引用。
>
> **何時讀**：跑 multi-pass review 時、用本卡判斷 framework 本身是否夠細到 catch 字句層問題；尤其在「跑了 N 輪、相同類型問題仍漏」的徵兆出現時。

---

## 論述基礎與限制

本卡的論述基於 **1 個 case** 的 review 失誤觀察抽出。具體限制：

- **樣本量極小**：「multi-pass review framework 顆粒度盲點」這個結論基於 1 次 review、不是多次跨主題 review 觀察到的 systematic pattern。可能是個別 reviewer 的特定盲點、不是 framework 本身的問題
- **三機制有效性未驗證**：keyword bank / reader simulation / self-criticism 三機制是 proposed mechanisms、未實際跑後續文章驗證
- **「reader simulation 由同 reviewer 執行」是 partial fix**：同一 reviewer 拿掉 code block 重讀、記憶仍在、無法完全模擬「沒看過 code 的讀者視角」。本卡提的修法不是 root cause solution
- **「同一 reviewer 跑多輪 catch 高度相同」是直覺論述**：未做受控實驗、是基於 multi-pass 設計動機（「換 frame」）的推論

讀者使用本卡時、把它當「**從一次 review 失誤抽出的盲點假說**」、不當「驗證過的 review framework 升級方案」。三機制是 starting point、有效性需要後續案例累積驗證。

---

## 核心原則

Multi-pass review 用「規則 frame」掃描、有效抓「結構性違反」（規則順序、論述結構、邊界段缺失）、但**抓不到「字句層的具體訊號」**——同個規則有大量具體訊號、reviewer 用記憶 sweep 會 systematic miss 一部分。

| 缺口類型     | Multi-pass 用「規則 frame」能抓       | Multi-pass 用「規則 frame」抓不到                    |
| ------------ | ------------------------------------- | ---------------------------------------------------- |
| 結構性違反   | 段落順序、論述結構、邊界段缺失        | —                                                    |
| 規則對齊     | 「應該 / 必須」絕對主義（明顯）       | 「碰巧 / 撞牆 / 一輩子」口語修辭（同樣違反但不明顯） |
| 用詞精度     | 術語原文錨點（contract / 關鍵抽象詞） | 地區漂移（屏 / 螢幕、默認 / 預設）                   |
| 論述自包含性 | H2 後加商業邏輯導引                   | 段落內依賴 code（「payload 第二段」）                |
| 句型結構     | 反例段落補正向錨點（明顯）            | 「不是 A 而是 B」結構（隱性違反）+ 廢話前綴 wrapper  |

關鍵差異是「規則理解」vs「具體訊號比對」：

- **規則理解**：reviewer 知道規則
- **具體訊號比對**：reviewer 要逐句檢查所有可能違反該規則的具體句型

抽象規則 → 具體訊號的轉譯沒做完整、就會 systematic miss 一整類字句層問題。

---

## 為什麼「規則 frame」抓不到字句層問題

### 問題 1：抽象規則沒展開成具體訊號清單

每條規則有大量可能的違反句型——例如「最重要的話優先說」可能違反句型：

| 違反句型           | 具體案例                        | 在哪裡常見           |
| ------------------ | ------------------------------- | -------------------- |
| 廢話前綴 / wrapper | 「下次看到 X 時、做 Y」         | 結尾段、heuristic 段 |
| 觀察先 / 定義後    | 「實務上常看到：[code]」        | 起點段               |
| 否定先 / 肯定後    | 「不要先想 A、先想 B」          | 除錯思維、check list |
| 條件先 / 結論後    | 「在 X、Y、Z 條件下、結論是 W」 | 推導段               |

reviewer 用「規則」這個 frame 掃描、靠記憶找——多半只 catch 明顯 case、漏 catch 隱性違反。

### 問題 2：缺乏 grep keyword bank

字句層問題有大量可 grep 的具體詞——但 reviewer 沒有 keyword bank、靠肉眼掃。每輪 review 用 grep 比對固定 keyword list、能消除「靠記憶找違規」的 systematic miss。

### 問題 3：reviewer 自我審查的視角盲點

reviewer 讀自己寫的東西、會自動 fill in 上下文、感受不到讀者的真實閱讀體驗。同一個 reviewer 跑多輪、視角始終是寫作者視角、不是讀者視角。

### 問題 4：Multi-pass 缺 self-criticism 輪

每輪 review 都是 forward checking（這篇對齊規則嗎？）、沒做 backward critique（規則本身在這個情境是否夠細？有沒有 miss 的 frame？）。framework 不夠細、跑再多輪都掃不到 frame 之外的問題。

---

## 三個 proposed 補強機制

基於這次 review 失誤的觀察、提出三個補強機制各自處理「同一 reviewer 跑多輪仍 miss」的不同來源。**三機制是 proposed、有效性待後續案例驗證**。

### 機制 1：Keyword bank（換工具）

每條規則展開成可 grep 的 keyword list、每輪 review 用 grep 比對、不靠 reviewer 記憶。

範例 keyword bank：

```text
口語修辭：
  一輩子 / 永遠 / 碰巧 / 剛好 / 撞牆 / 炸 / 鎖死 / 啊原來 / 沒事 / 乾淨

廢話前綴 + 否定先行：
  下次看到 / 下次寫 / 下次面對 / 下次遇到 / 不要先 / 不是 X 而是 Y

地區漂移（繁中讀者）：
  屏 / 默認 / 質量 / 視頻 / 文件（當 file 用）/ 函數 / 接口 / 內存

依賴 code 訊號：
  那個 / 這個 / 剛才的 / 上面的 / 第 X 段 / 就好 / 就能 / 就行
```

具體 keyword bank 詳見：

- [colloquial-rhetoric-erodes-technical-precision](colloquial-rhetoric-erodes-technical-precision.md)（口語修辭 + 廢話前綴）
- [prose-self-contained-without-code-reference](prose-self-contained-without-code-reference.md)（依賴 code）

新 keyword 的觸發條件：發現新的字句層違反模式 → 加進 keyword bank、下次 review 自動 catch。

### 機制 2：Reader simulation 輪（換視角）

加一輪「假設讀者沒有上下文、能不能讀懂這段論述」、強迫換視角。具體做法：

- **拿掉所有 code block 後重讀**：論述是否 self-contained？
- **跳到段落中間直接讀**：不依賴前文、能不能 parse？
- **隨機抽段給陌生讀者讀**：cold-read 能不能拿到關鍵資訊？

這個 frame 的價值在於 catch reviewer 的「fill in 上下文」盲點。

### 機制 3：Self-criticism 輪（換層次）

加一輪「我這份規則本身在這個情境是否夠細、有沒有 miss 的 frame？」、強迫 reviewer 反向審視框架本身。具體 prompt：

- 「我跑的 N 輪、catch 的問題類型有哪些？」
- 「同個規則底下、還有哪些可能違反句型沒被掃到？」
- 「如果讀者報告 X 類問題、是哪輪該 catch 但沒 catch？」
- 「framework 本身是否有 known blind spot？」

self-criticism 輪不是「再跑一次規則 frame」、是「**檢視 frame 本身的覆蓋度**」。

---

## 為什麼「再仔細一輪」不能取代這三個機制

reviewer 跑同一個 frame 兩次、catch 的東西高度相同——因為視角、知識、注意力分配相同。Multi-pass review 的核心是「每輪換 frame」、不是「同 frame 多跑幾次」。

但**換 frame ≠ 換規則**——reviewer 可能換規則但用同樣的視角、同樣的記憶 sweep、catch 的東西相同。要真正換 frame、需要：

- **換工具**：keyword bank 取代肉眼掃（機制 1）
- **換視角**：模擬讀者取代 reviewer 視角（機制 2）
- **換層次**：審視 framework 取代套用 framework（機制 3）

三個機制各自處理「同一 reviewer 跑多輪仍 miss」的不同來源。

### Hindsight 視角的反向印證

[design-flaw-by-current-axes-not-hindsight](design-flaw-by-current-axes-not-hindsight.md) 的核心議題是「事後諸葛論述」會混淆「設計缺陷 vs 需求演化」。同樣的 hindsight 風險也存在於 review 流程：

- **Hindsight 視角**：「讀者反饋了 → 補進規則」——把規則當成「事故後補的 patch」
- **當下三軸視角**：「framework 本身是否夠細到 catch 這類問題？」——把 framework 當成預設工具、用 self-criticism 反向審視

兩種視角的差別跟設計檢討的 hindsight 議題同骨：前者依賴結局、後者用當下框架審視。

---

## 識別訊號：什麼時候你的 review framework 不夠細

### 訊號 1：讀者反饋的問題類型在 framework 裡找不到對應 frame

讀者指出某類問題、reviewer 翻 framework 找對應 frame——找到了高層 frame 但沒展開到具體子場景。

修法：把問題類型加進 framework 的 keyword bank、下次同類問題能被 grep catch。

### 訊號 2：跑了 N 輪、相同類型的問題仍重複出現

字句層問題（口語修辭、地區漂移）跑了多輪 review 仍漏——表示 framework 沒 catch 這個層次。

修法：加 keyword bank（機制 1）、不靠 reviewer 記憶。

### 訊號 3：reviewer 自我審查感覺通順、讀者反映卡住

依賴上下文的論述對 reviewer 通順、對讀者卡住——視角差異。

修法：加 reader simulation 輪（機制 2）。

### 訊號 4：相同 framework 跑不同主題、catch 的問題類型差異不大

framework 不會自我批判——跑 N 篇文章、catch 的都是 framework 內的 frame、framework 外的問題永遠看不見。

修法：加 self-criticism 輪（機制 3）、定期審視 framework 本身的覆蓋度。

---

## 何時不需要這些補強機制

| 情境                              | 為什麼不需要                                                      |
| --------------------------------- | ----------------------------------------------------------------- |
| 短篇 note / 即時更新              | 預期讀者群小、不擴散、字句層問題影響有限                          |
| 個人筆記                          | reviewer = reader、視角差異不存在                                 |
| Review framework 已成熟、團隊內化 | keyword bank 已經內化成 reviewer 的反射、不需要 explicit 工具     |
| Framework 規模太小                | framework 只有 3-5 條規則時、self-criticism 容易出 false positive |

判讀：寫之前自問「這篇文章的讀者群有多大？字句層問題擴散的代價有多高？」——大 / 高 → 嚴格用三機制；小 / 低 → 可放寬。

---

## 跟其他原則的關係

| 原則                                                                                                | 跟本卡的關係                                                                                    |
| --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [writing-multi-pass-review](writing-multi-pass-review.md)                                           | 本卡是 multi-pass review 的延伸——補上「frame 本身要夠細、且需要工具 / 視角 / 層次三軸補強」     |
| [colloquial-rhetoric-erodes-technical-precision](colloquial-rhetoric-erodes-technical-precision.md) | 是字句層的「具體訊號」之一、本卡是「為什麼字句層訊號被 framework 漏 catch」的 meta 層           |
| [prose-self-contained-without-code-reference](prose-self-contained-without-code-reference.md)       | 是字句層的另一類具體訊號、本卡 cover meta 層的修法                                              |
| [design-flaw-by-current-axes-not-hindsight](design-flaw-by-current-axes-not-hindsight.md)           | hindsight 視角會把 review framework 當「補丁」、self-criticism 用當下框架審視、跟它同骨         |
| [ease-of-writing-vs-intent-alignment](ease-of-writing-vs-intent-alignment.md)                       | 用「規則 frame 掃描」是 reviewer 的寫作便利、用「keyword bank + reader simulation」是費力但精準 |

---

## 判讀徵兆

| 訊號                                    | 該做的行動                                                         |
| --------------------------------------- | ------------------------------------------------------------------ |
| 讀者反饋了 framework 裡找不到對應 frame | 加進 keyword bank、補進 framework 的 frame 列表                    |
| 跑 N 輪後同類問題仍出現                 | framework 不夠細、加機制 1（keyword bank）                         |
| reviewer 通順 / 讀者卡住                | 加機制 2（reader simulation 輪）                                   |
| framework 從來沒被質疑過                | 加機制 3（self-criticism 輪）、定期審視 framework 本身             |
| 多輪 review 跑完還是同 reviewer         | 引入外部讀者反饋、或刻意換視角（不同 IDE / 不同字體 / 跳段順序讀） |

**核心原則**：multi-pass review 用「規則 frame」掃描有效抓結構性違反、抓不到字句層具體訊號。要 catch 字句層、需要把規則展開成 keyword bank、加 reader simulation 視角、加 self-criticism 反向審視 framework 本身——三個機制各自處理同 reviewer 跑多輪仍 miss 的不同來源。
