# 測試命名規範

## 核心原則

測試是少數會自我驗證的文件——名稱說的事如果跟實際行為不符，CI 會擋下 commit。測試名稱跟實際行為的一致性被 CI 強制執行，doc comment 沒有這個保證。

**設計目標**：讀者不看 test body，只掃 test name 就能讀懂模組的行為規格。寫測試名時想像讀者只會看到名字，他要能推得三件事：在驗哪個操作、在哪個情境下、期待什麼結果。三件事缺一不可。

**Why**：source code 的 doc comment 有結構性缺陷——code 改了 doc 沒改，doc 就在說謊。測試名不會說謊，因為 CI 強制同步。**Consequence**：不利用這個性質，測試只是 regression 工具；有意識利用，測試同時是可執行的 API 規格。

---

## 三種命名模式

被測單元的契約分三類——回傳什麼、操作做什麼、何時失敗——對應三種命名模式。

### 模式 1：state-based（狀態描述）

「在某狀態下，呼叫 X 會回傳 / 變成什麼」。適合 query / read-only 操作。

```text
returns_null_when_user_not_found
returns_empty_list_when_no_items_match
```

### 模式 2：scenario-based（情境描述）

「當某條件成立時，操作會做什麼」。適合 command / mutation 操作。negative assertion 也該寫進名字（`does_not_X`）——這是契約的一部分。

```text
removes_item_when_quantity_reaches_zero
does_not_update_last_changed_on_remove
```

### 模式 3：failure-mode（失敗模式描述）

「在某輸入 / 狀態下，會 throw / error / 失敗」。適合 error path、edge case。失敗模式是 doc 最容易漏寫的部分，但對 caller 最關鍵。

```text
throws_not_found_when_id_does_not_exist
returns_error_when_network_unavailable
```

---

## Group 結構作為命名空間

巢狀 group 提供「主題→操作→情境」的階層命名空間。讀者掃過 group 結構，立刻知道模組對外提供哪些操作、每個操作有哪些行為承諾。

```text
EventCollector
  validateEvent
    rejects_when_missing_required_field
    accepts_when_all_required_fields_present
    strips_unknown_fields_silently
  queryEvents
    returns_empty_list_when_no_match
    filters_by_type_when_type_param_provided
    respects_limit_param
```

好的 IDE / test runner 會把 group 結構顯示為樹狀——把這個視覺結構利用好，測試 console 本身就是 doc 瀏覽器。

---

## 名稱承載意圖：紅燈時刻的讀者

三種模式描述的是「驗什麼」；名稱還承擔一個失敗訊息給不了的東西——「**為什麼這個行為是刻意的**」。失敗輸出只有症狀（Expected X、Actual Y），拿到紅燈的人下一個問題是：這是一條刻意的規則、還是漏網的 bug？答案的位置就是名稱。例：一個批次合併操作有兩種收尾（回到編輯流程、或直接進入下一階段），`finishes_immediately_without_editing_teardown`（直接進入下一階段：不做編輯流程的收尾）讓紅燈的人知道自己撞到刻意規則；名稱只寫症狀時，他查不出這條規則為誰存在，deadline 前最合理的動作是把斷言改成新行為讓測試回綠——防護在發聲的那一刻被解除，而那次 diff 在 review 裡讀起來只是一次正常的測試更新。

名稱說不出這件事為什麼成立，先改名稱；改完仍說不出來（理由在 repo 之外：法規、外部契約），才在測試旁留註解記出處。

---

## 名稱之外的測試文字

名稱之外，測試還有三類文字，各有落點；同一資訊只放一處：

| 文字                          | 該寫什麼                                                                                                                    | 反例 → 正例                                                                                         |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| assertion 的 reason / message | 失敗的後果與處置（這代表什麼、接下來做什麼），把實際變數值內插進訊息、紅燈時不必重跑加 log                                  | `'狀態應該是 1'` → `'後端未釋放資源（實際=X）——刪除編排依「同步釋放」設計、需與後端確認並同步修正'` |
| skip 訊息                     | 可行動：這代表什麼、怎麼讓它跑起來                                                                                          | `'未提供憑證'` → `'未提供憑證、跳過真實後端驗證——帶 <參數> 執行（見檔頭）'`                         |
| 測試內註解                    | 只寫操作性約束（違反會壞、且原因看不出來）與非顯而易見的 setup 原因；「本測試驗證什麼」的敘述性註解不寫——該修的是名稱和斷言 | 檔頭彙整清單（「已模擬的行為：…」）不寫——沒有機制守著它與 handler 同步、終將過期                    |

分析用的後設詞彙（「語意」「契約」「漂移」）與開發過程（取證日期、「曾以相反順序抓到」）不入測試文字——前者屬於對話、後者屬於 commit 訊息與知識庫。判斷法：這個詞刪掉之後、句子有沒有變得更直接。

---

## 反模式

| 反模式                                             | 問題                                                  | 正向替代                                                       |
| -------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------- |
| `test_` 前綴 + 模糊主題（`test_user_2`）           | 讀者必須跳進 body 才能分辨在驗什麼，命名 doc 價值消失 | 寫具體行為：`creates_user_with_default_role_when_role_omitted` |
| 實作洩漏（`uses_hashmap_for_lookup`）              | 重構換實作會逼測試改名，但對外行為沒變                | 描述可觀察行為：`returns_value_in_O1_for_existing_key`         |
| 描述過程（`mocks_db_and_calls_find_then_asserts`） | 讀者拿到的是測試怎麼寫，不是被測單元承諾什麼          | 描述契約：`returns_null_when_user_not_found`                   |
| assertion 動詞（`isFalse_when_disabled`）          | 讀者不知道 false 對應什麼業務語意                     | 寫業務語意：`returns_false_when_feature_disabled`              |
| 用編號取代命名（`addItem_case_1`）                 | CI 報告只看到編號，無法判斷哪個情境壞了               | 加情境描述：`addItem_appends_when_cart_empty`                  |

---

## 邊界

測試名不適合獨自承擔 doc 責任的四種情境：

| 情境                             | 原因                                                         | 命名角色                    |
| -------------------------------- | ------------------------------------------------------------ | --------------------------- |
| 大量參數化 / property-based test | invariant 命名只能寫概念名，具體 input 範圍靠 generator 描述 | 定位錨點                    |
| 整合 / e2e test                  | 跨多系統的行為壓不下完整流程                                 | 定位錨點，搭配 scenario doc |
| 業務動機的二次表達（如合規規則） | 詳細條款在 spec 文件，命名只負責驗證點                       | 驗證點索引                  |
| 內部 helper / private worker     | 不是公開契約，可直接用實作詞彙                               | regression 防護             |

判斷標準：讀者只看名字能拿到他要的資訊嗎？能→命名當 spec；不能→命名當定位錨點，詳細上下文寫 doc。

---

## 檢查清單

寫測試前確認：

- [ ] 名字能讓讀者不看 body 就知道驗證什麼？
- [ ] 名字描述的是被測單元的契約（非測試過程）？
- [ ] 名字有業務面詞彙（非 assertion 動詞）？
- [ ] 同 group 下與其他 test 有足夠區辨度？
- [ ] 這個行為契約是 doc 沒寫但 test 在驗的？（補了 doc 漏洞）
- [ ] 是否在驗實作細節？（是→改成驗對外可觀察行為）

---

## 相關文件

- `references/phase2-test-design.md` — Phase 2 測試設計指引（測試命名基本要求）
- `references/bdd-behavior-testing.md` — BDD 行為測試（行為 vs 實作判別法）

---

**Last Updated**: 2026-08-08
**Version**: 1.1.0 — 兩節新增：「名稱承載意圖」（失敗輸出只給症狀、名稱回答「為什麼這是刻意的」；名稱失職時防護會被紅燈的人親手解除——改斷言遷就新行為、diff 讀起來像正常測試更新）與「名稱之外的測試文字」（reason 寫失敗後果與處置並內插變數值、skip 訊息可行動、註解只寫操作性約束、分析詞彙與開發史不入測試文字）。來源是測試文字紀律的實際 review 案例集、同步上游 testing 教材的測試註解與命名紀律。
**Version**: 1.0.0 — 從 blog `record/test-naming-as-documentation.md` 提煉，語言無關化
**Source**: ~/Projects/blog/content/record/test-naming-as-documentation.md
