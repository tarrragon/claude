# 各步驟為什麼存在

> **什麼時候讀本檔**：想跳過某一步、或要判斷某一步在本專案是否適用時。SKILL.md 的九步表給的是做什麼與時機，本檔給的是跳過的後果。
>
> 同目錄另有 `version-shift-sop.md`（提案移版時的契約殘留盤點）、`reactive-work.md`（不納入 bootstrap 的反應式工作）、`adjacent-assets-boundary.md`（與相鄰資產的交界）。

每一節的 Why 說明該步驟填補的是哪一種空隙，Consequence 是跳過它的實測後果——括號標「實證」者為已發生過的案例，非推想。

## Step 1：跨提案依賴檢查腳本

**背景**：`check_proposal_dependencies.py` 讀 `docs/proposals-tracking.yaml` 各提案的 `depends_on` 欄位（選填，list of str，元素為本提案依賴的前置提案 id）比對 `target_version` 排序；若專案已採用 `doc` skill，該欄位格式定義的權威來源見 doc skill 的 `tracking_schema.py`（`PROPOSALS_TRACKING_SCHEMA["proposal_entry_optional"]`），非本 yaml 檔案本身的頭部註解。若未採用 doc skill，本腳本仍可正常運作（腳本本身不 import 該檔，以執行期讀取的 list 格式驗證取代靜態 import），只是欄位格式需自行依上方括號說明推斷，無法查閱該權威定義檔案。

**Why**：本版提案依賴的提案若排在更晚版本，屬排序矛盾，本檢查在提案確認階段就攔截，不留到規劃波中段。**Consequence（動機案例，實證）**：曾有版本以雙提案啟動，其中一提案依賴另一個排在更晚版本的提案，卻仍排入本版，矛盾拖到規劃波中段才由用戶手動發現，最終將該提案移至依賴對象所在的版本節點。若此檢查在 Step 1 就位，矛盾可在提案確認階段被攔截。**Action**：見 SKILL.md Step 1 的依賴檢查腳本指令與輸出 `[WARNING]` 時的二擇一處理（移入本版或更早版本一起排入／移至依賴提案完成之後的版本）。

## Step 2.5：Domain 規劃

**Why**：spec 定義 FR（系統做什麼）、UC 定義使用者場景（誰怎麼用），兩者皆為垂直視角，不界定 domain 的水平聚合邊界——aggregate / kernel / read-model 分類、依賴方向、層測試策略。**Consequence**：跳過本步驟，domain 邊界會在實作階段臨場拍板（退化為「哪個檔案太大就拆」），依賴方向底線無文件可依，易出現 read-model 互相耦合、持久化細節混入 domain；測試設計（Step 5）也無 per-bundle 依據。需事後補 domain map（實證：某個移動應用實作案例中於實作前補建）。**Action**：spec FR 填完後、測試設計前，為每個 domain 產出或更新 domain map。

## Step 2.6：資料契約產出

**Why**：spec FR 定義欄位存在，不定義欄位的值域、狀態責任分層、不變式、交易邊界、錯誤語意與恢復模型；domain map §3 Bundle 界定表的 data/infrastructure 列只標「持久化細節屬 data 層」，未展開細節。**Consequence**：跳過本步驟，資料層設計意圖（為何選這個約束、哪些不變式由 DB 保證）無專屬載體，散落於 DDL 註解與 repository 程式碼各處；Step 5 測試設計對資料層契約條目無盤點依據，覆蓋缺口不可審計（見 `.claude/methodologies/data-layer-contract-methodology.md` 第 6 節）。**Action**：spec FR 與 domain map 完成後、紅燈測試設計前，依兩旗標判準決定是否產出資料契約文件。

## Step 4.5：地基波

**Why**：測試設計（Step 5）需驗 zh/en overflow 與元件互動反應，這些依賴 i18n 系統與元件實體先存在；若 Step 4 後直接進 Step 5，UI 版本會在 i18n / design-system / 元件庫尚未 build 時進測試設計，無可驗對象。**Consequence**：跳過本步驟，測試票會假設不存在的 i18n key 與元件，Phase 3b 才暴露缺地基，需回頭補甚至推翻測試設計（實證：地基波經指正後手動插入）。**Action**：對含 UI 提案的版本，於測試設計前編排地基波實作波。

## Step 2 的 UI 前置檢查

**UI 類提案元件庫前置檢查（強制，元件庫雙向約束方法論落地）**：Why——UI 類提案若跳過 design token 層與元件庫規劃直接進入實作，設計端與工程端會各自決定元件形狀，產生重複造輪與樣式漂移，已上線元件難以回溯套用 token 體系。三項前置檢查的產物（design token 層、L3 元件庫章節、design-system spec）本身就是圖形介面的組成，判準因此鎖定「FR 產物是否為圖形介面」這個呈現通道，不以字面關鍵字判定——同一個彈窗換一種寫法就會漏掉字面比對，但呈現通道不會變。Consequence——未在本步驟攔截，UI 實作票會在 Step 6 匯總建票時直接開出，等到 Phase 3b 實作階段才發現缺 token 層或元件庫章節，需回頭補規劃甚至推翻已完成的實作。Action——UI 類判別依 SKILL.md Step 2〈UI 類判別〉的呈現通道表，本檔不逐字複寫判準本文（避免兩處各自演化、逐字不同步）；判為 UI 類提案者須先確認 SKILL.md Step 2〈UI 類提案元件庫前置檢查（強制）〉表列各檢查項存在，缺則先補齊才可繼續本提案的 UI 實作票規劃（檢查項清單以該表為準，本檔不重複列舉以免計數隨表格增減而過期）。

**三項檢查的「存在」判準**：檢查的是內容是否符合 SKILL.md 表格「對應載體」欄的定義，不是檔案或章節是否存在——標題存在但內容為空殼（如僅一句「待補」）不算通過。存在性檢查對有效性零鑑別力的通用原則見 `.claude/skills/foundation-design/SKILL.md`〈判準的通用形式：問作用，不問存在〉：「文件存在不代表它回答得了問題」。

**L3 元件庫章節的範圍收斂**：舊表述用「本步驟得先只到此」界定範圍，「得」是允許語氣、不是定義句，曾使讀者把括號內「逐元件契約欄位表與容器條目」也算進本步驟的存在判準，判為不通過（實證：讀者探針對此條文的判定歧義）。SKILL.md 表格已改為明訂句——L3 元件庫章節本步驟僅檢查「元件清單 + 原生元件禁用對照表 + 豁免清單」三項是否存在；契約欄位表與容器條目不算本步驟範圍，於 Step 4.5 第 3 塊（元件契約銜接）補齊，缺這兩項不影響本步驟通過判定。

**呈現通道表兩列的優先序**：圖形介面（第一列）與非圖形的人讀呈現（第二列）在「應用程式產出、版面固定的匯出檔」（如本應用程式產生的固定版面 PDF）上字面重疊——版面固定容易被誤讀為第一列的「含唯讀畫面」。判準依查看／操作當下的呈現位置，不依版面豐不豐富：使用者查看或操作時若已離開本應用程式視窗、改由外部程式（PDF 閱讀器、試算表軟體等）另開檔案呈現，一律歸第二列，即使該檔案版面固定或排版複雜；只有仍在本應用程式視窗內即時繪製、可操作或查看者才歸第一列。SKILL.md 表格第二列已加註「（優先本列）」標示此交界。

## Step 2 為什麼多一項 design-system spec

**Why 加 design-system spec 檢查**：doc skill 已提供 `design-system-spec-template`，但 `batch-init` 只產一般功能 spec，UI 版本易漏產 design system 專屬 spec。**Consequence**：漏產則 Step 4.5 地基波的 design-system 實作無契約可依（實證：PM 用 batch-init 產一般功能 spec 卻未產 design-system spec，經指正後才補）。**Action**：UI 版本填 spec 時一併用 design-system-spec-template 產出 design system spec，作為 Step 4.5 design-system 實作的契約。

## 元件契約遞移依賴

**Why**：Step 4.5 地基波順序表把元件契約（3.5）排在 UX 審查（3）之後、元件庫（4）之前，PM 工作句只寫「元件契約依賴 UX 審查」，沒有交代是否也依賴 i18n（1）與 design-system（2）；`component-contract-design` skill 自身的前置檢查表另外把 design token 層列為該規格票的直接前置，兩處對「元件契約是否依賴 design-system」各自表述，容易讓讀者誤以為 i18n 完全不在元件契約的依賴範圍內。**Consequence**：若誤判元件契約不依賴 i18n，可能在 i18n 尚未 build 完成時開放元件契約票；填元件契約欄位表的內容政策時（`component-contract-design` skill 的 step-3〈內容政策〉要求填「最長測試文案」，來源為 i18n 資源檔既有譯文）無資源可查，需回頭等待或用臆測值頂替，事後還要重測。**Action**：UX 審查的 `blockedBy` 已含 i18n 與 design-system（見 SKILL.md Step 4.5 PM 工作句），元件契約的 `blockedBy` 只需列 UX 審查一項——UX 審查完成即代表 i18n 與 design-system 皆已完成，元件契約經此鏈已遞移取得兩者，不必重複列出；重複列出反而製造兩條可能不同步的依賴宣告。

**去重原則的射程**：上段「不必重複列出」僅限元件契約自身的 `blockedBy` 列舉，因為元件契約對 i18n／design-system 只是經 UX 審查遞移取得完成訊號，並未直接消費兩者產出。此原則不適用於 Step 4.5 元件庫的 `blockedBy`：元件庫「套 token + i18n + UX 反應，依契約實作」（SKILL.md Step 4.5 產出欄；方法論〈地基波 build 順序〉第 4 塊「文字經 i18n key 傳入、樣式取 design token」），直接消費 design token、i18n key 與 UX 反應三項產出，非僅取得完成訊號，故元件庫的 `blockedBy` 仍需並列前三塊與元件契約四項，不受本節去重原則約束。

## GREEN 票分組依據

Step 6「每個 spec FR 或功能模組 1 張」的「或」由三條依據共同決定，各管不同判準對象：

1. `.claude/pm-rules/task-splitting.md`〈拆分後檢查清單〉B——`where.files` 有交集者合併到同一票。
2. `.claude/rules/core/cognitive-load.md`〈速查三閾值〉——合併後功能職責數 > 2 須再拆分。
3. 同檔〈策略 7〉——「不以依賴為由合併」：兩個 FR 僅共用狀態、`where.files` 無交集時不合併，改依 `blockedBy` 序列派發。

**Why**：依據 1 判準對象是「檔案是否重疊」，依據 3 判準對象是「僅有邏輯依賴、檔案不重疊」——兩者結論相反（前者合併、後者不合併）但不衝突，因為判準對象本就不同；SKILL.md 原僅路由依據 1、2，未路由依據 3，讀者遇到僅共用狀態、無檔案交集的 FR 組合時無條文可查。**Consequence**：未路由依據 3，讀者可能誤把依據 1 的「合併」結論套到「僅共用狀態」情境，將不該合併的 FR 併成一票；或反過來每次重新判斷，判斷標準因人而異。**Action**：SKILL.md Step 6 三條依據並列，本節列出各自管轄的判準對象；三者是否構成同一套一致的「拆分單位」定義（尤其依據 3 的「GWT scenario group」與 Step 6 的「spec FR 或功能模組」是否為同一粒度）屬另案裁決範圍，本節僅路由三條依據各自的條文，不代為判定何者為權威。

**依據 1 與依據 2 同時命中時，交界尚未裁決**：先依依據 1 合併之後，若合併後的功能職責數依依據 2 超過閾值須再拆分，拆開後的子票可能重新持有原本因檔案交集而合併的那些檔案，方向與依據 1「共用檔案的問題已合併到同一 ticket」相反。**Consequence**：這條交界目前沒有裁決依據，若逕自選邊（一律優先合併或一律優先拆分），會與另一條依據的字面要求牴觸，且牴觸不會在當下顯露，要到下一次同型情境才會被發現處理不一致。**Action**：遇到依據 1 與依據 2 同時命中，本檔不代為判定合併優先或拆分優先，停手交 PM 判斷，不自行選邊。


