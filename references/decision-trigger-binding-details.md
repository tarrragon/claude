# 決策 Trigger 綁定規則（詳細版）

> **定位**：本檔為 `.claude/rules/core/decision-trigger-binding.md`（自動載入速查 stub）的完整 substance。stub 含規則速查表與觸發路由；本檔含規則 1.5 載體邊界、規則 3 對照表全文、規則 4 偵測、Hook 引用豁免機制全章、反模式範例、邊界表。按需讀取。

本文件規範所有需要延後執行的決策必須綁定明確 trigger，禁止「以後再說」式的無 trigger 延後框架。

> **核心理念**：所有需求都應有明確執行計畫、階段、確認、驗收。延後不是第三種狀態——延後必須是「等 ticket X 完成後執行 Y」，且 X 必須是 ticket。

---

## 適用範圍

| 對象 | 是否適用 |
|------|---------|
| Ticket 撰寫（5W1H、Solution、Problem Analysis、acceptance） | 是 |
| 規則 / 規格 / 提案撰寫 | 是（`.claude/` 框架檔案內的條件式條文另依規則 2.5 條件式操作規範處理） |
| Phase 4 評估結論 | 是 |
| Code review 評論、commit message、PR description | 是 |
| 程式碼註解（業務情境陳述） | 是 |
| 對話內 prompt（PM 派發 / 代理人回報） | 是 |

---

## 強制規則

### 規則 1：兩種合法狀態，沒有第三種

任何決策只能處於以下兩種狀態之一：

| 狀態 | 含義 | 範例 |
|------|------|------|
| (a) 已決策 | 含結論的最終決定 | 「採方案 A」「無需重構」「Phase 4 評估結論：保持現狀」 |
| (b) 明確 trigger 延後 | 等 ticket X 完成後執行 | 「`<follow-up-ticket-id>` 完成後處理 X 實作」 |

**禁止**：無 trigger 延後（「Phase X 再決定」「以後再評估」「之後處理」「將來」「暫緩」「baseline 顯示需要再做」「待後續觀察」）。

**Why**：無 trigger 延後在「以後」與「永不」之間沒有可驗證邊界，必然累積為死議題（PC-093 的根源）。

**Consequence**：違反此規則的延後表述會在執行階段成為灰色地帶，驗收沒有完成定義，後人接手不知該不該補做。

**Action**：撰寫前自問「這個決策現在能不能下結論？」能 → 寫結論（狀態 a）；不能 → 建 follow-up ticket 並引用 ID（狀態 b）。

### 規則 1.5：適用邊界——程式碼/文件 vs worklog/ticket

決策狀態的嚴格度依載體區分：

| 載體 | 可述未來考量？ | 必須綁 ticket trigger？ | 範例 |
|------|--------------|---------------------|------|
| 程式碼註解（架構討論） | 是 | 否（情境陳述） | 「未來若加入 X 模組，此處需改為 Y」（屬設計筆記，非延後決策） |
| 規則 / 方法論 / 提案 / `.claude/` 框架檔案 | 是 | 否（原則陳述）；框架檔案另**禁止**綁 ticket ID（`.claude/references/reference-stability-rules.md` 規則 8 硬擋），改依規則 2.5 條件式操作規範承載 | 擴充性說明：「未來擴展點：可加入 Z」；條件式操作規範：「本檔達 300 行時外移至 references（行數由 `file-size-guardian-hook` 偵測）」 |
| Worklog / Ticket body | 否 | 是（必須是狀態 a 或 b） | 任何「下週處理」「之後再說」「下版本再做」均違規 |
| Phase 4 評估結論 | 否 | 是 | 必填明確結論，禁止「Phase 5 再決定」 |

**Why**：程式碼/文件的「未來考量」是設計脈絡傳遞，幫助後人理解決策空間；worklog/ticket 是執行追蹤單位，「未來」若無 ticket 錨點即等於遺失。摩擦力方法論（`.claude/methodologies/friction-management-methodology.md`）核心：所有任務都有排程權重，只是輕重緩急不同；難題反而應優先（大石頭先放），時間（一週後/一個月後）不是任務權重的合法衡量單位。

**Consequence**：worklog 中以時間為延後依據（「下週處理」「下個月再做」）會在繁忙期系統性失效——時間到了沒人記得評估，且無 acceptance 可勾選；該決策在「以後」與「永不」之間沒有可驗證邊界。

**Action**：寫 worklog / ticket 時，若想表達「之後再處理」，先問「這是排程問題還是決策問題？」排程問題 → 改用 ticket 計數或版本錨點 trigger（規則 2 替代方案表新增兩列）；決策問題 → 立刻決策（狀態 a）或建 follow-up ticket（狀態 b）。

### 規則 2：合法 trigger 限 ticket ID

只有 ticket ID 是合法 trigger。其他形式（時間、量化閾值、外部事件）必須先包裝為 ticket：

> **適用範圍**：本規則約束的是**延後決策**（此刻仍有未回答的問題）。決策已下完、只等條件成立的**條件式操作規範**不在本規則範圍內，其合法承載形式見規則 2.5。此區分在 `.claude/` 框架檔案上是必要的——該處禁引專案 ticket ID，若不區分則兩條規則不可同時滿足。

| 想表達 | 錯誤 | 正確 |
|--------|------|------|
| 等 baseline > 80ms 才做 | 「baseline > 80ms 時觸發」 | 建監測 ticket（描述「監測 X 指標，> 80ms 時建 follow-up」），本決策標 `blockedBy: [<ticket-id>]` |
| 等外部版本發布 | 「外部版本 vN 發布後處理」 | 建追蹤 ticket，本決策標 `blockedBy` |
| 等指定日期重評 | 「YYYY-MM-DD 重新評估」 | 建排定 ticket，本決策標 `blockedBy` |
| 等用戶反饋累積 | 「累積 10+ 案例後評估」 | 建監測 ticket，本決策標 `blockedBy` |
| 等執行 N 個 ticket 後重評 | 「跑一週看看再說」 | 「執行 N 個同類 ticket 後重評」+ 建監測 ticket 計數 |
| 下一版本再處理 | 「下個月再做」 | 「v0.X+1 開版時新增重評 ticket」+ 建版本錨點 ticket |

**Why**：ticket 是專案唯一統一追蹤單位，含 acceptance / status / 派發機制 / scheduler runqueue。其他 trigger 形式無自動推進，會在「未綁 ticket 但說有 trigger」的灰區累積。

**Action**：想寫「等 X 條件成立時做 Y」→ 先建追蹤 X 的 ticket，再用 ticket ID 作為 trigger。

### 規則 2.5：條件式操作規範不綁 ticket trigger

條件式操作規範是「決策已下完、只等條件成立」的條文，不受規則 2 約束——它需要的是**偵測承擔者與當場執行者**，不是 trigger。適用載體為 `.claude/` 框架檔案；`docs/` 與 ticket 可合法引 ticket ID，不需本規則。

判別只看句子本身，不看有沒有偵測機制：**此刻是否還有「做不做 / 做 A 還是 B」未回答？** 有 → 延後決策（規則 2）；無 → 條件式操作規範（本規則）。定位所在格，照該格處置：

| | 有偵測承擔者 | 無偵測承擔者 |
|---|---|---|
| **決策已下完** | 寫規範，條文內指名偵測承擔者 | 補偵測手段，或拿掉條件改寫為無條件規範 |
| **決策未下完** | 框架檔案不是合法載體——改寫入專案 ticket；需跨 consumer 追蹤時另以 framework issue（`claude#NN`）為錨點，依規則 8 provenance 慣例置於 frontmatter 或 commit trailer | 同左 |

**Why**：規則 2 的實質關切是「無人執行」而非「無 ticket」。ticket 被指定為唯一合法 trigger，理由是它是專案內唯一能被 scheduler 推進的單位；這個理由只在「條件成立時還需要有人重新判斷」時成立。

**Consequence**：不區分兩者，框架檔案內的條件式條文會與 `.claude/references/reference-stability-rules.md` 規則 8 相撞——規則 2 要求綁 ticket ID，規則 8 硬擋。兩側守衛的觸發路徑不同：規則 8 的守衛掛在 `.claude/` 檔案編輯上、當場阻擋；PC-093 側的 hook 掛在 ticket 生命週期命令上、不掃框架檔案編輯（見規則 4）。結果是合規嘗試被擋、規避寫法零阻力，撞牆後最省力的出路變成刪掉 trigger 了事。

**Action**：在 `.claude/` 框架檔案寫「當條件成立時該做 X」前先問上述判別問題，再依表格定位處置。屬自指維護閾值者另受下節約束。

#### 自指維護閾值：必須指名偵測承擔者且粒度相符

「本區 / 本檔 / 本清單達 N 時外移或改寫」這類**自指的文件維護閾值**，必須在條文內指名偵測承擔者，並確認該承擔者的量測單位與條件單位相符——區塊級條件對整檔級守衛不算相符。指不出承擔者、或粒度不符，該條文即為「靠維護者記得」，須改為無條件規範或改走延後決策路徑。

**Why**：其餘條件式規範（「當 X 需求出現時做 Y」）由提出需求的人當場觸發，需求本身即宣告條件成立，不需外部量測。自指維護閾值沒有這樣的觸發者——沒有人會為了核對行數而回頭讀這條，寫下就沒人再回看。

**Consequence**：缺此約束時，任何延後決策都能改寫成「當條件成立時該做 X」的句型規避建票，而規則 2.5 本身還提供了合乎規範的句型模板；規避手法因此更難辨識。

**邊界：指名不等於會被執行。** 機械檢查的優勢是偵測不會漏，不是行動一定發生——本框架的體量守衛每次 session 都報，超標檔案仍長期維持在閾值數倍。指名承擔者解決「沒人知道條件成立」，不解決「知道了沒人動手」。把兩者當同一件事，會高估這條防護的強度。

**存量**：本規則對新寫內容生效，既有條文屬應然目標，不回溯逐條改寫（與規則 8 對存量的處置一致）。

**與 `baseline-gated` 豁免的邊界**：`baseline-gated`（見下「Hook 引用豁免機制」）處理 ticket body 內量化條件的 hook 命中豁免；本規則處理框架檔案內條件式條文的承載形式選擇。對象不同，不互相取代。

**不採「規則 8 增列框架層追蹤項目豁免類別」**：開豁免等於把 sync 後死連結重新引入規則 8 正要根除的位置，且該規則的全禁原則已以五類分類收斂；新增語意型豁免會使守衛退回逐句判斷「這是不是 trigger」，其漂移形態與豁免清單逐案追加、最終無人能判定成員邊界的形態同型。

### 規則 2.6：協作射程——被操作 repo 無本框架 ticket 系統時的追蹤載體

規則 2 把 ticket ID 指定為唯一合法 trigger。該條文成文時，「專案」與「裝有本框架 ticket 系統的專案」是同一件事，無須區分。協作或接手他人專案時這兩者分開：被操作的 repo 沒有本框架的票庫與 CLI，分析發現的落點是外接資料夾內的一份**盤點工作項表**（逐列登記待辦的主檔），其項目編號不是 ticket ID。

本規則承認**通過下節全部閘門的工作項編號**為合法 trigger，射程限於該情境。規則 2 的原條文一字不改——射程內的判準不變，新射程有自己的機械判準，兩個射程各自可查。

**Why**：規則 2 的實質關切是「無人執行」而非「無 ticket」（見規則 2.5 的 Why）。ticket 只是這個性質在裝有票庫的專案內的唯一實例，不是第一原則。框架自身也已承認過一個非 ticket-ID 的追蹤錨點——規則 2.5 四格表的 framework issue（`claude#NN`）——判準是該錨點具備穩定識別與可查狀態，不是它叫什麼名字。本規則把同一判準擴到第二種情境，不是開新原則。

**Consequence**：不設此射程，協作情境的每一則發現在規則層都沒有合法落點——建在分析者端的票指向對方 repo 的檔案，對方看不到也推不動；寫進工作項表的則被規則 2 判為無 trigger 延後。兩條路都不通時最省力的出路是把發現留在敘事裡，而那正是 PC-093 要根除的形態。

**Action**：先以閘門 G5（收件方歸屬）與 G1 確認情境確實落在本射程，再逐道核對其餘閘門。任一道不通過，該編號等同無 trigger 延後，規則 2 與 `quality-baseline.md` 規則 5 的原條文照常適用。

#### 與規則 2.5 的差異：不是同一類豁免

兩者管轄的對象不同：規則 2.5 管 `.claude/` 框架檔案內條件式條文的**承載形式**（寫成規範還是寫成 ticket），本規則管延後決策的 **trigger 載體身分**（什麼東西可以當 trigger）。規則 2.5 的射程自陳限於框架檔案，外接資料夾的工作項表不是框架檔案，本案因此不進入其兩軸四格表。

附帶一提，即便把規則 2.5 的判別問題硬套到本案，結論也相反而非相同：工作項表的一列是尚未執行、有前置項、待排序的待辦，決策未下完，該格處置指向「改寫入專案 ticket」。這條路之所以不通，是對象錯配（拿管條文承載形式的表去判 trigger 載體身分），不是判別問題答錯。

**Why**：兩者都在處理「規則 2 的字面在某處不適用」，形狀相近；不寫明差異，讀者會以規則 2.5 的判別問題套本案，得到「決策未下完，不適用」的相反結論。**Consequence**：套錯後的行為是把工作項表整份改寫為分析者端的逐項票，即下文閘門 G3 排除的第二份追蹤主檔。**Action**：判別時先問對象是條文承載形式還是 trigger 載體身分，再選規則。

#### 防架空閘門

承認的是通過全部閘門的編號，不是任何自訂編號。閘門全數通過才承認。

| 閘門 | 內容 | 判準性質 |
|------|------|---------|
| **G1 射程閘門** | 僅在**被操作 repo 無本框架 ticket 系統**時適用。判準是客觀事實（該 repo 有無本框架票庫且 ticket CLI 可用），不是便利性宣稱。同一專案內 ticket 系統可用而改用工作項編號，視為違反規則 2 | 可執行查核 |
| **G2 載體閘門** | 編號必須來自工作項表主檔，該表須同時具備下列與可驗證性直接相關的全部必留欄位：項目編號、狀態、驗收條件、前置項（含順序層）。缺任一欄，該編號不是合法載體 | 查欄位，非判語意 |
| **G3 唯一主檔閘門** | 一個交付案只有一份工作項表主檔。**追蹤主檔**指逐項登記待辦、且被當作狀態來源的清單——分析者端逐項對應的影子票是其典型形態，一次性的交接摘要與涵蓋多項的單張分析票則不是。存在第二份追蹤主檔時，兩份的編號皆不合法 | 數主檔份數 |
| **G4 推進閘門** | 分析者端必須有**一張本框架 ticket** 作為該交付案的對帳載體，其 acceptance 記載對帳觸發條件與承擔者，工作項表為其產出。產出該表的分析票本身即可擔任此載體，不需另開空票。缺此票時，工作項編號退回不合法 | 查票是否存在 |
| **G5 收件方閘門** | 射程由**發現的收件方**決定，不由手邊有無 ticket 系統決定。本框架自身的發現（框架缺陷、分析者端專案的技術債）不適用射程切換，仍須建 ticket 或走 framework issue | **分類判斷**（唯一一道），依 `.claude/skills/framework-issue/references/escalation-flow.md`〈介入判斷：框架問題 vs 專案問題〉的兩條 AND 判準逐條套，不憑印象 |

項目編號的格式本規則不規定，只要求在該表內唯一且不重用；形如 `INV-001` 的連號即可。 <!-- rule8-exempt: illustration:工作項編號格式舉例，非任何專案的識別符 -->

**Why**：沒有一道閘門要求判斷「這個載體夠不夠等效」——G1 至 G4 是查事實、查欄位、查份數、查票，全部機械可查。這是刻意的設計約束，規則 2 的價值在判準機械化。**唯一的例外是 G5**：收件方歸屬是分類判斷，本規則不自行定義判準，改指名既有 SOP（見上表）；它同時是決定射程是否啟動的那一道，誤判 G5 則其餘全通過也無意義，故須先行且逐條套。**Consequence**：若把判準改寫成「限 ticket ID 或等效追蹤載體」，守衛即退回逐句判斷，其漂移形態與豁免清單逐案追加、最終無人能判定成員邊界的形態同型（規則 2.5 末段拒絕語意型豁免同理）。**Action**：核對結果逐道寫入 G4 那張對帳票的 acceptance（該 repo 有無票庫與 CLI、表內必留欄位是否齊備、主檔幾份、收件方歸屬的判準套用結果），不留在執行者的推理裡，也不以「情況特殊」跳過任一道。

**Why（為何要求寫入對帳票）**：五道閘門若只在執行者腦中跑完，產出端看不出差別——復核者讀到的只有一句落地宣告，無從分辨背後核對過幾道。**Consequence**：缺殘留物時，五道閘門的實際強度等同自我宣告，與本節開頭拒絕的語意型豁免無異。**Action**：沿用 G4 已經要求存在的那張票承載核對結果，不新增任何機制。

閘門 G4 對應的是工作項表相對 ticket 的唯一實質缺口：ticket 由 scheduler runqueue 與派發機制推進，工作項表的對帳紀錄欄是人工對帳。G4 把「相信有人記得對帳」升級為「查一張票是否存在」，故它不是附加要求，而是承認結論的成立條件。

#### 指涉穩定與狀態權威分離

工作項編號的「不漂移」保證須拆成兩件被混談的事：

| 保證 | 交付前 | 交付後 |
|------|-------|-------|
| 指涉穩定（編號不重用、不重編） | 分析者。工作項表是唯一主檔（G3） | 分析者。編號在全時段是穩定識別 |
| 狀態權威（哪一份說了算） | 工作項表 | **轉移至對方系統**。工作項表降為對照表，狀態由對帳回抄，並新增一列對帳紀錄 |

精確說法是：**工作項編號在全時段是合法的 trigger 識別，但狀態判定權威隨交付切換**。

**Why**：trigger 需要的是「能被指名且不漂移」，這由指涉穩定提供；「做完了沒」則是狀態問題，交付後對方系統才是事實來源。**Consequence**：不分離兩者，會出現「工作項表寫完成、對方系統還沒做」的雙主檔，而那正是閘門 G3 排除影子票所要避免的形態。**Action**：交付後首次對帳前未回填外部編號的列，計為「未對應」，不得據以宣告終態。

#### `quality-baseline.md` 規則 5 落地終態的對應

規則 5 的實質是「發現不得只停在敘事」。其落地終態在工作項表上逐一有對應：

| 規則 5 的落地形式 | 工作項表對應 |
|------------------|------------|
| 建票並記入 `spawned_tickets` / `children` | 工作項表新增一列，來源欄記出處 |
| spawn request resolve 為 `processed` 附 ticket ID | 新增一列並於交付後回填外部編號 |
| resolve 為 `dismissed` 附理由 | 狀態填「不做」，詳情寫理由 |
| 逐項標註「無需建 ticket：[理由]」 | 同上 |

**強制層零改動接法**：`acceptance-gate-hook` 的 spawn 落地計數只認 `spawned_tickets` + `children` + 已判定的 spawn request，工作項表列不計數。其豁免標記以字面字串逐行扣抵一項 spawn 規劃，故在本框架 ANA 票的 Solution 內逐項寫「無需建 ticket：已落為工作項表 <工作項編號>（主檔：<外接資料夾路徑>）」即可扣抵。

**Why**：該句同時滿足兩件事——含豁免標記字面而被強制層扣抵，且寫出了落點使人工復核可追。**Consequence**：不用此寫法而改動 hook 計數邏輯，等於為一個零樣本的情境改強制層，風險落在所有既有 ANA 票的 complete 路徑上。**Action**：協作案的 ANA 票逐項用上述句型；主檔路徑寫到可定位該表的層級，只寫編號不寫主檔者，復核時無從查證。該句型只用於逐項宣告，**同一份 Solution 內不另行引述本節條文原文**——豁免標記以字面逐行扣抵、不區分宣告與引述，多一行引述即靜默多扣抵一項真實 spawn 規劃且無警告；確需引述時把引述放進**非 spawn 規劃表格行**的表格行（一般表格行走另一條計數路徑而不計入；放進真實的 spawn 規劃行則會把該項規劃本身一併豁免，與本段要避免的失效同型）。

### 規則 3：寫法替換對照表

| 反模式句型 | 替代寫法 |
|-----------|---------|
| 「Phase 4 再決定觸發條件」 | 建 follow-up ticket，本 ticket frontmatter 標 `spawned_tickets: [<ticket-id>]` |
| 「之後再評估」「以後再說」 | 同上 |
| 「暫緩」 | 立刻決策（狀態 a），或建 ticket（狀態 b）。沒有第三選項 |
| 「Phase 4 評估結論：[空]」 | 必填明確結論，如「無需重構」「採方案 A」「重構範圍 = X 模組」 |
| 「baseline 顯示需要再做」 | 建量測 ticket，量測結果作為 follow-up 的 trigger |
| 框架檔案內「本區超過 N 行時外移」綁 ticket ID | 判為條件式操作規範（規則 2.5）：條文明訂動作 + 指名偵測承擔者且粒度相符，不綁 ticket ID |

### 規則 4：違規偵測

| 違規類型 | 偵測時機 | 行為 |
|---------|---------|------|
| Ticket / 規則 / 規格中含「之後」「再決定」「以後」「將來」「暫緩」「Phase X 再」「下週」「下個月」字面，且 frontmatter 無 `spawned_tickets` / `blockedBy` 連結，內文也無有效 ticket ID 格式引用 | 寫入時驗證機制 | 警告 + 提示寫法（不阻擋；驗證機制偵測自由文字含 ticket 引用有限度） |
| Phase 4 評估結論為空或含「Phase 5 再決定」 | complete 前驗證機制 | 阻擋（quality-baseline 規則 2 已強制） |

---

## 反模式範例

**範例 1（合法 vs 違規）**：

| 違規 | 合法 |
|------|------|
| 「X 實作以後再說」 | 「X 實作待 `<follow-up-ticket-id>`（X 評估）完成後決策」+ 已建對應 ticket |
| 「這個精度問題之後再修」 | 引用既有 pending ticket ID 並附加證據（如新案例 append 進該 ticket Problem Analysis） |
| 「Phase 4 視 baseline 結果再決定」 | 「Phase 4 結論：採 cache（baseline = 84ms < 100ms AC，無需 cache）」 |

**範例 2（合法的「探索性」處理）**：

長期研究 / 等技術成熟 / 等市場訊號這類本質長期延後，仍受本規則拘束——必須建定期重評 ticket 或監測 ticket，再以 ticket ID 作為 trigger。本規則不設「探索性例外」。

---

## Hook 引用豁免機制（W10-126 補強）

phase4-decision-enforcement-hook 對「Phase X 再決定」「延後評估」等字面強制偵測，但合法情境（規則引用、source ticket 歷史 context 引用）需用 `<!-- PC-093-exempt: <category>:<reason> -->` 標記豁免。

### 合法豁免類別

| Category | 適用情境 | reason 要求 |
|---------|---------|------------|
| `rule-quote` | 引用 `.claude/rules/` 或 `.claude/pm-rules/` 規則名稱 | reason 須含 `.claude/rules/` 或 `.claude/pm-rules/` 路徑 |
| `ticket-tracked` | 引用既有 ticket ID（如 source ticket why 含歷史延後話術描述） | reason 須含 `W\d+-\d+` 格式 ticket ID |
| `baseline-gated` | 量化基線觸發條件（如「baseline > 100ms 則重啟」） | reason 須含數字 |
| `tdd-transition` | TDD phase 轉換的合法延後 | 一般說明 ≥ 10 字 |
| `user-override` | 用戶明確授權的延後 | 一般說明 ≥ 10 字 |
| `history` | 引用已完成歷史 / 動機脈絡（如 IMP ticket 開頭引用 parent ANA 多視角審查發現作 Problem Analysis 背景） | reason 須含 `W\d+-\d+` 格式 ticket ID 作歷史錨點 |

**`history` vs `ticket-tracked` 語意區分**：

| Category | 語意 | 典型情境 |
|---------|------|---------|
| `ticket-tracked` | 「等待該 ticket 完成後處理」（延後決策有 trigger） | source ticket why 含歷史延後話術描述、引用尚未 complete 的 follow-up ticket |
| `history` | 「引用已完成歷史 / 動機脈絡」（非延後，是事實陳述） | IMP Problem Analysis 開頭引用 parent ANA 審查發現、回顧已 complete ticket 的決策歷程 |

### 標記位置規則（PC-146 / EXEMPT_PROXIMITY_LINES=1）

marker 必須**緊鄰命中行**：同一行行尾，或命中行上方一行（中間不可有空行 / 標題等元素）。

正確：

```markdown
<!-- PC-093-exempt: ticket-tracked:本段為 W10-118 source ticket why 引用 -->
- 0.18.0-W10-118 why: ...「Phase 5 再決定」...
```

或：

```markdown
- 0.18.0-W10-118 why: ...「Phase 5 再決定」... <!-- PC-093-exempt: ticket-tracked:W10-118 引用 -->
```

錯誤（marker 與命中行物理分離）：

```markdown
- 0.18.0-W10-118 why: ...「Phase 5 再決定」...

### Hook 引用豁免章節                                ← marker 與命中行隔了空行 + 標題
<!-- PC-093-exempt: ... -->
```

### 多命中行情境

每個命中行各加一個 marker，不可共用一個（hook 行級獨立判定）。

詳見 PC-146（exempt marker 位置誤用 + 三層防護）。

### Frontmatter 場景：不需 exempt marker（W1-092 起）

ticket frontmatter（YAML 區塊，`when` / `why` / `strategy` 等欄位）內出現「Phase 4 評估」「Phase 5 再決定」等歷史字面時，**不需要**加 `PC-093-exempt` marker。

**Why**：phase4-decision-enforcement-hook 自 W1-092（PC-142 case 5 修復）起，透過 `compute_frontmatter_lines` 將整個 frontmatter 區塊（含起訖 `---`）排除於 phrase 掃描與 marker 蒐集範圍之外。frontmatter 為結構化元資料，其欄位常含 source ticket history 引用字面，本質與 Context Bundle auto-extracted、Schema placeholder、fenced code block 同類——非人類撰寫的當下延後決策論述，故整段跳過。

**Consequence**：若仍在 frontmatter 欄位內加 `PC-093-exempt` marker，會造成兩層問題：(1) marker 對 hook 無作用（該區塊不被掃描，marker 也不被蒐集），屬冗餘標記；(2) ticket CLI complete 後的 metadata sync 會以 PyYAML round-trip 重新序列化 frontmatter，行內 markdown 註解形式的 marker 不被當 YAML 註解而是 scalar 值的一部分，序列化後可能位置漂移或被移除，產生「marker 一加就消失」的錯覺。W1-048.3（2026-05-23）即為此模式：sage 在 hook 修復前加 marker 才能 complete，complete 後 metadata sync 移除 marker——但因 W1-092 已讓 hook 不掃 frontmatter，marker 的存廢不再影響 complete。

**Action**：

| 字面所在位置 | 是否需 marker | 理由 |
|------------|-------------|------|
| frontmatter（`---` 區塊內的 YAML 欄位） | 否 | hook 整段跳過（W1-092），加 marker 冗餘且會被 metadata sync 移除 |
| body 一般論述（`## Solution` 等章節文字） | 是 | hook 行級掃描，命中需 marker 豁免 |
| body 內 fenced code block / Schema placeholder / Context Bundle auto-extracted | 否 | hook 各自整段跳過（W11-018 / W10-130 / W1-120） |

**判別準則**：marker 只在「hook 會掃描且會命中」的 body 論述行才有意義。frontmatter 與上述三類整段豁免區塊內，移除 marker 不會造成 hook 阻擋，無需保留。

### Code fence 豁免途徑（與六類 marker 並列的第二種豁免手段）

除上述六類 `PC-093-exempt` marker 外，hook 對整段 fenced code block（``` 或 ```` ``` ```` 包夾的區塊）**整段跳過掃描**，不需逐行補 marker。這是與 frontmatter、Schema placeholder、Context Bundle auto-extracted 同類的「非人類撰寫當下延後決策論述」整段豁免機制（見上表），但適用觸發條件不同——marker 是逐行標記，fence 是整段包裹，兩者解決不同形狀的問題。

**適用時機差異**：

| 途徑 | 適用場景 | 典型情境 |
|------|---------|---------|
| Code fence | **引用或示範**延後話術的句型本身——內容是「展示規則要攔什麼」，不是撰寫者當下真實要延後的決策 | 撰寫規則/方法論舉例說明 PC-093 攔截哪些句型、撰寫測試案例的輸入字串、逐字引用他人 ticket 的延後語作說明 |
| Marker | 延後語彙**不得不出現在實質論述**中，無法抽離成獨立引用區塊 | Problem Analysis 段落中夾雜對歷史延後決策的分析評論、source ticket why 欄位的延後話術描述需要與周圍論述連續 |

**判別問句**：這段文字若整段抽掉不影響論述完整性（純粹是「附帶展示的例句」）→ 用 code fence。這段文字若抽掉會讓論述斷裂（延後語彙本身就是被分析/引用的論述主體一部分）→ 用 marker。

**Why**：code fence 途徑成本遠低於 marker——不需要為每個示範句逐行補 `<!-- PC-093-exempt -->`，也不需要判斷該用哪個 category；只需把示範內容整段包進 fence。此途徑早已存在於 hook 實作（fenced code block 屬既有整段豁免機制之一），但補強前 DENY 訊息完全未提及，撞牆者只看得到六類 marker 說明，找不到成本最低的出路——實證見同一工作階段內，三次獨立任務皆因「須引用/示範延後話術以說明規則或撰寫測試」而觸發自我阻擋，其中一次因所在章節無法補 marker 而完全卡死。

**Consequence**：不知道 fence 途徑時，撞牆者要嘛逐句改寫示範內容繞過偵測（PC-093 同精神反模式：改寫文字消音而非正確豁免），要嘛在自由撰寫章節（無法補 marker 的情境）完全卡死。

**Action**：撰寫規則/方法論/測試需要示範或引用延後話術句型時，優先把該段整段包進 markdown code fence；若示範內容需要與外層引用（例如把整份 hook 訊息一起貼進 ticket）巢狀，內外層須用不同 fence 字元（``` vs ~~~），避免同字元巢狀導致外層提前視為收尾（見 phase4-decision-enforcement-hook.py 的 `format_block_message` 內建範例，即採此作法）。

---

## 與其他規則的邊界

| 規則 | 聚焦 | 與本規則差異 |
|------|------|------------|
| `quality-baseline.md` 規則 2 | Phase 4 不可跳過 | 本規則延伸：Phase 4 結論必須是狀態（a），禁止「Phase 5 再決定」 |
| `quality-baseline.md` 規則 5 | 所有發現必須追蹤 | 本規則延伸：發現後若無法立刻決策，必須綁 follow-up ticket trigger；收件方 repo 無本框架 ticket 系統時的射程例外見規則 2.6 |
| `PC-093-yagni-deferred-decision-accumulation.md` | 反模式描述 | 本規則為正向 prescriptive guidance（PC-093 描述問題，本規則開藥方） |
| `document-writing-style.md` | 三明示原則 | 互補：本規則處理「決策狀態明示」，document-writing-style 處理「論述明示」 |
| `pm-rules/execution-discovery-rules.md`「遇到問題的閉環流程」 | 流程層 | 本規則是聲明（禁止無 trigger 延後），閉環流程是執行（不能立刻決策時的合法 5 step：識別 → 建 ANA/DOC → Solution 規劃 spawned 驗證/實驗 → 執行 → 釐清結案）。兩者互補形成完整閉環 |
| `references/reference-stability-rules.md` 規則 8 | 框架檔案禁引專案層級識別符 | 交集為「`.claude/` 內的條件式延後」。規則 2.5 以「延後決策 vs 條件式操作規範」收窄規則 2 的適用範圍解消衝突，規則 8 不開豁免 |
| `methodologies/friction-management-methodology.md` | 摩擦力 / 排程權重理論 | 本規則延伸：所有任務都有排程權重，時間（週 / 月）不是合法權重單位；難題優先排（大石頭先放）；改用 ticket 計數或版本錨點作 trigger |

---

## 檢查清單

撰寫 ticket / 規則 / 規格 / commit / 註解前自問：

- [ ] 內容含「之後」「再決定」「以後」「將來」「暫緩」「Phase X 再」「待後續」「下週」「下個月」等表述？
- [ ] 載體為 `.claude/` 框架檔案且內容為「當條件成立時該做 X」？先問「此刻是否還有未回答的問題」定位規則 2.5 表格所在格；若屬自指維護閾值（本區 / 本檔 / 本清單達 N），是否已指名偵測承擔者且粒度相符？
- [ ] 載體屬 worklog / ticket / Phase 4 結論？若是，必須為狀態 (a) 或狀態 (b)，不可述「未來考量」（規則 1.5）
- [ ] 若有，已建立對應 follow-up ticket 並標 `spawned_tickets` / `blockedBy` 連結，或內文有 `W\d+-\d+` 格式 ticket ID 引用？
- [ ] 若無 follow-up ticket，是否能立刻下結論（狀態 a）？
- [ ] Phase 4 評估結論是否為明確結論（「無需重構」「採方案 A」），而非「Phase 5 再決定」？
- [ ] 發現的收件方是另一個 repo 且該 repo 無本框架 ticket 系統？若是，已依規則 2.6 逐道核對閘門（G1 射程、G2 必留欄位、G3 唯一主檔、G4 對帳票、G5 收件方），並確認交付後的狀態權威已切換？

---

**Last Updated**: 2026-09-16 | **Version**: 1.7.0 — 新增規則 2.6（協作射程：被操作 repo 無本框架 ticket 系統時，通過閘門的盤點工作項表編號為合法 trigger）：射程分離不改規則 2 原條文；含與規則 2.5 的差異（本案落在「決策未下完」列，非同類豁免，且管轄對象不同）、防架空閘門（射程／載體必留欄位／唯一主檔／對帳票／收件方；除收件方歸屬為分類判斷並指名既有 SOP 外皆機械可查，核對結果須寫入對帳票 acceptance）、指涉穩定與狀態權威的交付前後切換表、`quality-baseline.md` 規則 5 三種終態對應與強制層零改動接法。檢查清單增一列。**Version**: 1.6.0 — 新增規則 2.5（條件式操作規範不綁 ticket trigger）：以「決策是否已下完」單一判別問題收窄規則 2 適用範圍，解消其與 reference-stability 規則 8 在 `.claude/` 框架檔案上不可同時滿足的衝突；處置改為「決策狀態 x 有無偵測承擔者」兩軸四格表；指名偵測承擔者的要求收窄至自指維護閾值一類並加粒度相符判準；明示存量不回溯、與 `baseline-gated` 豁免的分工、以及「指名不等於會被執行」的強度邊界。規則 1.5 既有「規則 / 方法論 / 提案」列擴含 `.claude/` 框架檔案（避免同一檔案命中兩列）；規則 2 加適用範圍註；規則 3 表與檔頭適用範圍表同步；邊界表增列規則 8。**Version**: 1.5.0 — 主文 substance 自 `.claude/rules/core/decision-trigger-binding.md` 外移至本檔（W7-004.2 auto-load token 收斂）；core/ 原檔降為速查 stub。歷史 1.0–1.4 版見 git log。**Source**: PC-093 / PC-146 / W11-023 / W1-092。
