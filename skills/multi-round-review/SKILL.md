---
name: multi-round-review
description: "寫多篇章節後做多輪 agent reviewer audit 的標準流程：每輪換 frame、跨輪 finding 不重疊、停止看多軸涵蓋而非 finding 遞減；Round 1-A 同步 invoke compositional-writing 的字句層 keyword bank。觸發：多輪審查、Round 1/2/3、frame 切換、reviewer 規劃、何時停止 review、寫作 audit、batch review、術語探針、self-application sweep。"
license: MIT
metadata:
  portable: true
  version: 2.3.0
  category: writing-methodology
---

# Multi-Round Review

寫多篇章節後做多輪 agent reviewer audit 的標準操作流程。每輪用不同 frame、跨輪 finding 互不重疊、至少三輪是硬底線、停止判讀從 Round 3 結束後才開始。已在 backend 5 章（3 輪 9 reviewer 38 finding）和 dotfile 31 篇（3 輪 8 reviewer 43 finding）兩次驗證，Round 3 每次都找出前兩輪結構上看不到的一類問題（數字見 [多輪審查至少三輪](references/principles/minimum-three-rounds.md)）。

## 適用情境

- **多篇相關章節**：3+ 章一起寫完、需要跨稿件 audit
- **品質高於速度**：每輪 30-60 分鐘 reviewer + 30-120 分鐘 fix、3 輪約 4-8 小時
- **章節品質敏感**：教學模組、規範文件、長期累積的內容
- **主 context 容量敏感**：reviewer 平行 background 是節省 context 的關鍵設計

不適用：

- **單篇短文**：固定成本（規劃 frame + 跑 reviewer + 整合 finding）對短文 ROI 低
- **快速迭代原型**：流程偏向「寫一次寫好」、不是「快速修改」
- **低風險文件**：個人筆記、草稿、不需要外部 review

## 基本原則

1. **每輪用不同 frame**（per [multi-pass frame 顆粒度盲點](references/principles/multi-pass-frame-granularity.md)）：同 reviewer / 同 frame 跑多輪 catch 高度相同。多輪價值在 frame 切換、不在重複加深。
2. **跨輪 finding 互不重疊**：若新一輪 finding 跟上一輪重疊、代表 frame 沒換、再跑無增益。
3. **停止訊號是 frame 涵蓋、不是 finding 遞減**（per [跨輪 review 停止訊號](references/principles/cross-round-stopping-signal.md)）：多輪 review 通常 finding 不遞減、Round 3 可能比 Round 1 / 2 多。停止判讀看七軸有沒有都動過，程序在 `references/planning-and-stopping.md`〈Round N 規劃判讀〉；「想不出新 frame」量的是判斷者、不作必要條件。
4. **至少三輪是硬底線**（per [多輪審查至少三輪](references/principles/minimum-three-rounds.md)）：Round 3 的 steelman / outbound frame 覆蓋 Round 1-2 結構性盲區（漏選項、反向引用、搜尋落點、知識卡缺口），歷次實測每輪都找出 10+ 項。Round 1-2 從「已寫的內容」裡找錯，Round 3 從「沒寫的東西」出發——這類問題在前兩輪的 frame 下結構性不可見。「要不要跑 Round 3」不是判讀問題、是執行紀律。停止判讀從 Round 3 結束後才開始。
5. **規模與來源是兩件事**（per [規模買不到異源視角](references/principles/review-scale-does-not-buy-independent-origin.md)）：一個 session 派出的所有 reviewer 與探針構成單一來源——同一份稿、同一個人寫的 prompt、同一個 context 的框架。增加數量提高的是覆蓋的面，不是視角的來源數。register 與用詞搭配這一類的偵測依賴的正是來源，所以「已經派了幾十個 reviewer」不構成異源已經覆蓋的證據。一次實測：兩個併行執行者各自跑完四輪、各自掃描回報乾淨，交換檢視時各自一眼看到對方一處違規，其中一處的判斷標準可機械執行而寫的人套在自己的小節標題上判定通過。併行的另一個執行者是最便宜的異源視角，交換的單位是掃描而不是評價。

## 誰做哪一段

這份文件同時被兩種角色讀，而它們該做的事完全不同。讀之前先確定自己是哪一種。

|                                      | **主 session**（規劃並派發的那個）                  | **reviewer**（被派出去的那個） |
| ------------------------------------ | --------------------------------------------------- | ------------------------------ |
| 讀哪些段                             | 全部                                                | 只讀自己被指派的那一個 frame   |
| 決定輪數與 frame 組合                | 是                                                  | 否                             |
| 派 agent                             | 是                                                  | **否——reviewer 不再往下派**    |
| 執行檢查、產出報告                   | 只做不外包的那幾項（見〈主 session 不外包的四項〉） | 是，且只做被指派的那一個       |
| 判斷可不可以停                       | 是                                                  | 否                             |
| 整合跨 reviewer 的 finding、決定修法 | 是                                                  | 否                             |

**如果你拿到的指示沒有指名 frame**：不要自己挑一個，也不要整份跑一遍。回去問派你來的人要哪一個——這種情況代表派發時漏了東西，而你猜一個跑完的成本比問一句高得多，猜錯的那份報告還會被當成該維度已經覆蓋。

**主 session 不外包的四項**：整體通讀（reviewer 各看一角、合成缺陷只有通讀看得到）、停止判讀、跨 reviewer finding 的去重與修法決策、以及需要窮盡列舉的維度——列舉在主 context 很便宜，派出去的 reviewer 只回報它抽樣到的位置，而窮盡要的是全部。

## 派發之前先列這一批用的工具

**一行的成本，擋掉整批審查建立在過期規則上的可能。** 列出這次要用的方法論、規範檔與檢查腳本，逐個寫下版本與取得時間；有發佈端的順手比一次。理由是每個 frame 都對著審查對象設計，工具從來不在任何一個 frame 的射程裡——實測一次四輪、二十餘個 reviewer 的審查全程沒有一步會發現所用的方法論落後十一個 minor 版，而那些版本差裡有一版正好改掉了該次停止判定所依據的規則。見 [審查的射程只涵蓋被審查的對象](references/principles/review-scope-never-includes-the-instrument.md)

## 派發之前先定這一批的定位

**定位決定哪些 frame 適用，所以它在 frame 表之前，不在 frame 表裡面。** 寫下一句話：誰讀、讀完要做什麼。這一句是後面每一個 frame 的過濾器。

判別定位的軸不是「內容裡有沒有可執行的東西」——教材也給辨識訊號與可以改的東西——而是**那個動作落在哪裡：在世界上動手，還是在腦中重新歸類**。

三種常見定位與它們對應的體例：

| 定位             | 讀者               | 體例                                                                         |
| ---------------- | ------------------ | ---------------------------------------------------------------------------- |
| Agent 指令、規範 | 照著執行的執行者   | 操作手冊：步驟編號是執行的位置，判錯代價要寫，因為執行者需要知道哪一步不能錯 |
| 人類教材         | 來理解一件事的人   | 引導與脈絡：講清楚為什麼是這個順序，順序自己就出來；讀者要的是判讀的依據     |
| 程式碼註解       | 正在讀那段程式的人 | 只解釋商業邏輯，不解釋原理也不冗長，因為原理讀程式碼就有                     |

**同一個內容集合底下可能兩種定位並存**——一個分類裡的文章是教材而它的目錄頁是操作手冊，歸納層（記問題與解法的卡）兩邊都不是。2-D 掃體例時要把這些位置排除，否則會把正確的形式報成違規；判別與例子見下方連結的 principle。

定位判定為人類教材時，下列 frame 的觸發條件要重新過一次，因為它們的預設來自 agent 指令或工程決策內容：2-B‴ 的微案例要求（後果直觀時補了是冗餘）、2-B″ 的可執行走查（教材的讀者不照著執行）、1-D 的下游任務（下游任務是理解而不是產出）。判定為不跑的照樣要寫理由。

詳見 [定位決定體例](references/principles/positioning-decides-form-before-any-rule-applies.md)。

## 這一批要跑哪些 frame

Round 1-3 是硬底線，但每一輪裡的 frame 不是全部都跑。主 session 在派發前先過這張表，把結果寫下來——**判定為不跑的也要寫，並寫出理由——理由要指出該篇哪一段構成或不構成觸發條件；只寫類型標籤（「非操作型」「本批無可疑詞」）是關機鍵、不算理由（per [判定型規則要規定判定的痕跡](references/principles/judgment-rules-must-specify-their-trace.md)）**，否則「沒跑」與「判定不需要」在產物裡分不開。

| frame                                  | 什麼時候跑                                           | 判定依據                                                                                                                                    |
| -------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 1-A 寫作規範 / 1-B 案例 / 1-C 跨章一致 | 一律跑                                               | 無條件                                                                                                                                      |
| 1-D Downstream-task                    | 讀者讀完有明確的下一個動作（提案、估時程、選型）時   | 看文章的收尾段有沒有指向一個外部動作；定位為教材時照〈派發之前先定這一批的定位〉的例外                                                      |
| 1-E 斷言支撐                           | 素材來源是經驗談 / 訪談 / 口述的批次；或判斷標準密集 | 高風險批次此 frame 排第一輪，知識類型錯位的修法是重寫                                                                                       |
| 1-F 商業分析                           | 內容含財報判讀、產業比較、估值                       | 逐篇看有沒有財務數字或估值段                                                                                                                |
| 2-A Cadence                            | 一批三篇以上                                         | 單篇不適用（同骨化是跨篇現象）                                                                                                              |
| 2-B 讀者旅程                           | 有跨篇路線                                           | 單篇不適用                                                                                                                                  |
| 2-B′ 冷讀                              | 一律跑                                               | 任何可被搜尋或直連抵達的內容都適用                                                                                                          |
| 2-B″ Executable walkthrough            | 操作型（有步驟、有指令）                             | 非操作型不跑                                                                                                                                |
| 2-B‴ 情境可想像性                      | 判讀 / 選型型（給判斷標準、要讀者做決定）            | 非判讀型不跑                                                                                                                                |
| 2-B⁗ 低階 model 讀者探針               | 一律跑；審查對象是規則類文件時加「第一個具體動作」欄 | 無條件；報告的自評欄與比對欄分開讀（見 `references/reviewer-prompt.md` 的〈每個 frame 的產出契約〉）；定義在 `references/round-2-probes.md` |
| 2-B⁵ 翻譯探針                          | 中文稿件、且已通過 2-B⁗                              | 非中文稿件不跑；命題層未收斂時先跑 2-B⁗；定義在 `references/round-2-probes.md`                                                              |
| 2-B⁶ 術語探針                          | 有可疑的高頻用詞或口語譬喻                           | 沒有可疑詞不跑；同批沒有控制詞的結果不採用；定義在 `references/round-2-probes.md`                                                           |
| 2-B⁷ 類型探針                          | 定位是人類教材、而內容帶操作性材料時                 | 同批沒有兩份控制文件的結果不採用；定義在 `references/round-2-probes.md`                                                                     |
| 2-C 題目範圍 + 跨 surface              | 一律跑                                               | 無條件；標題是寬泛傘狀詞時範圍分不開、先收窄標題                                                                                            |
| 2-D 體例與定位一致                     | 一律跑                                               | 無條件；派發前的定位宣告是它的輸入，缺宣告就跑不了                                                                                          |
| 3-A 自審 / 3-B Steelman / 3-C Outbound | 一律跑                                               | 無條件                                                                                                                                      |
| 3-D Persona / 3-E Search landing       | 對象是教材或模組                                     | 單篇不適用                                                                                                                                  |
| 3-F 誤用梯度                           | 審查對象是規則 / 協議 / 規範 / 流程                  | 對象本身要被別人照著執行就跑                                                                                                                |
| 3-G 共同前提                           | 一批三篇以上                                         | 單篇不適用                                                                                                                                  |
| 3-H 個案實跑                           | 內容含判斷標準（判定序、分類法、選型三問）           | 判斷標準型必跑                                                                                                                              |


## 每個 reviewer 的 prompt 都要指定的事

沒有產出契約的 frame 等於沒跑過——認真跑完與完全沒跑在自由格式的報告裡同形。每個 prompt 缺一不可：

- **產出形態**：表或清單，欄位是什麼
- **窮盡還是抽樣**：抽樣要寫抽了幾處、怎麼選
- **每個 finding 註明它那一類的全部命中位置**，或註明是抽樣
- **產出排在報告最前面，材料與推導附在後面**——截斷從尾端切
- **零 finding 分三格**：掃過有候選判合規／判準對此對象結構上不適用／沒掃
- **自評欄與比對欄分開**：自報「我掃了」與比對「掃到了什麼」是兩欄
- **結案後的改判登記進下一輪輸入**，不回頭補進已結案的清單

推導、實測數字與 prompt 模板在 `references/reviewer-prompt.md`。

## 標準流程：按輪讀對應的檔

Round 1-3 是硬底線、直接跑不問；每一輪的 frame 定義、reviewer 指令與預期 finding 類型各住一份 reference。**派某一輪之前打開那一份不是載入預算的建議**——產出契約與各 frame 的表格形態都住在那裡，沒打開就派出去的 reviewer 等於沒跑過；各節標題以 frame 編號起頭（`## 1-E …`），拿編號進檔 grep 就到。

| 何時讀                                                                | 檔                                       | 涵蓋章節                                                                                                                |
| --------------------------------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| 派 Round 1（compliance / 基線）的 reviewer 之前                       | `references/round-1-compliance.md`       | 1-A 到 1-F 各一節、〈預期 finding 類型〉                                                                                |
| 派 Round 2（cadence / 讀者旅程）的 reviewer 之前                      | `references/round-2-cadence.md`          | 2-A、2-B、2-B′、2-B″、2-B‴、2-C、2-D 各一節、〈預期 finding 類型〉                                                      |
| 派 Round 2 的探針（理解 / 翻譯 / 術語 / 類型）之前——探針不是 reviewer | `references/round-2-probes.md`           | 2-B⁗、2-B⁵、2-B⁶、2-B⁷ 各一節、〈探針的派發契約〉、〈預期 finding 類型〉                                                |
| 派 Round 3 之前；拆章 / 併章 / 大幅改寫之後                           | `references/round-3-self-application.md` | 3-A 到 3-H 各一節、〈預期 finding 類型〉、〈重組後遺症 frame（拆章 / 併章 / 大幅改寫之後專用）〉                        |
| 規劃任何一輪之前對照〈反模式〉；Round 3 跑完、判定要不要 Round 4 時   | `references/planning-and-stopping.md`    | 〈Round N 規劃判讀〉、〈收尾清單〉、〈反模式〉                                                                          |
| 寫 reviewer 的 prompt 時                                              | `references/reviewer-prompt.md`          | 〈每個 frame 的產出契約〉、〈Reviewer prompt 結構〉                                                                     |
| 拿到 finding 清單準備修時；修完要驗證時                               | `references/integrating-findings.md`     | 〈整合 finding 跟 fix 工作流〉、〈修法的反模式〉、〈register 違規的異源複核操作〉、〈判斷兩個維度該不該合併：隔離實驗〉 |


## 跟既有 skill 的關係

- `compositional-writing` 提供寫作原則與字句層 grep keyword bank（完整清單在該 skill 的「字句層 keyword bank（完整清單）」節，本 skill 各處列的類別都是摘要）。**本 skill 啟動時應同步 invoke compositional-writing**——Round 1-A 寫作規範 reviewer 必須跑那一節的字句 grep（摘要在 `references/round-1-compliance.md` 的 1-A）、Round 2-A cadence reviewer 引用其〈多輪 Re-read Pass〉原則。
- `case-first-module-workflow`：本 skill 是它第三階段（agent team review）的展開。
- `business-analysis`：1-F 的 checklist 來源，見 `references/round-1-compliance.md`。

---

版本紀錄在同目錄的 `CHANGELOG.md`。
