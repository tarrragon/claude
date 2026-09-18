# Clean Architecture 實作方法論

## 核心概念

Clean Architecture 是分層架構模式，核心原則：**依賴只能由外向內**。

### 四層架構

| 層級 | 責任 | 依賴方向 |
|-----|------|---------|
| **Entities** | 核心業務規則、Value Objects | 最內層（無依賴） |
| **Use Cases** | 應用業務邏輯、定義 Ports | 依賴 Entities |
| **Interface Adapters** | Controller、Presenter、Repository 介面 | 依賴 Use Cases |
| **Frameworks & Drivers** | DB、Web、UI 具體實作 | 依賴 Interface Adapters |

### 依賴反轉原則（DIP）

- Use Case 依賴 Repository **介面**（在 Use Cases 層定義）
- Repository **實作**（在 Frameworks 層）依賴該介面
- 組裝階段（Composition Root）注入具體實作

## 執行步驟

### 設計階段（Inner → Outer）

1. **Entities 設計** - 識別業務實體、定義 Value Objects、驗證業務不變量
2. **Use Cases 設計** - 定義 Input/Output Ports、定義 Repository Ports
3. **Interface Adapters 設計** - Controller 轉換請求、Presenter 格式化輸出
4. **Frameworks 設計** - 選擇技術框架、實作 Repository

### 實作階段（Outer → Inner）

1. **定義 Ports** - 先定義 Use Case 和 Repository 介面
2. **外層依賴介面開發** - Controller 使用 Mock Use Case 開發測試
3. **內層補完實作** - Interactor 實作業務邏輯、Repository 實作資料存取
4. **組裝依賴注入** - Composition Root 連接所有元件

## 檢查清單

### 依賴方向

- [ ] Entities 不依賴任何外層
- [ ] Use Cases 只依賴 Entities 和自己定義的 Ports
- [ ] Interface Adapters 依賴 Use Cases 介面
- [ ] Frameworks 實作 Interface Adapters 定義的介面

### 介面契約

- [ ] Repository Port 在 Use Cases 層定義
- [ ] Repository 回傳 Entity（不是 DTO）
- [ ] Input/Output Ports 不洩漏技術細節
- [ ] Port 介面定義完成後，已依〈Port 回饋契約〉補齊呼叫的可觀測時刻（回傳型別能否區分成功與降級、是否有 progress callback、是否有受理狀態）

### 業務邏輯位置

- [ ] 業務不變量在 Entity 建構子驗證
- [ ] 應用邏輯在 Use Case Interactor
- [ ] Controller 只負責轉換和呼叫

### Interface-Driven Development

- [ ] Ports 在設計階段定義完成
- [ ] 外層使用 Mock 介面開發測試
- [ ] 內層實作後組裝注入

## Port 回饋契約

Port 契約不只定義方法簽章與依賴方向，還必須定義呼叫的可觀測性——這個 port 的呼叫有沒有清楚的回饋時刻。本節補齊此空缺，原則對輸入端與輸出端 port 通用；UI 層（輸入端 port）的特化見 [元件庫回饋契約掛載點](./component-library-bidirectional-constraint-methodology.md)。

### 輸出端回饋層級與判準

Driven port（應用層／領域層往外呼叫外部系統，例如開檔案、存取資料庫、呼叫 API）的呼叫要通過幾個可觀測時刻，結構平行於輸入端的回饋層級，但消費者不同——輸入端的消費者是使用者，輸出端的消費者是呼叫端程式碼、日誌與監控追蹤。

| 時刻 | 定義 | 承擔者 |
|------|------|--------|
| 呼叫發出 | 呼叫端調用 port 方法的那一刻即為事件；不依賴外部系統是否回應、是否可達、是否逾時 | 呼叫端程式碼 |
| 外部系統受理 | 連線建立、檔案控制碼取得、請求被接收（acknowledged 狀態或 progress callback） | adapter 實作 |
| 結果 | 外部操作的結局：成功、失敗、逾時、不可達 | adapter 實作的回傳值或例外 |

判準問句（平行於輸入端「拔掉服務還看得到反應嗎」）：**把外部系統整個拔掉，呼叫端能否得知「呼叫已發出但無回應」？日誌能否記錄「何時發出、對誰發出、至今無回應」？** 答案為否，即呼叫發出這個時刻缺失。

### 不變式：INV-PORT-OBSERVE-001

**每一次 driven port 呼叫都必須產生「呼叫已發出」這個可觀測事件，即使呼叫最終失敗、被防抖丟棄或立即拋出例外。**

此事件不依賴外部系統是否回應——它是呼叫端主動發出的，不是外部系統回覆才產生的。若此事件不存在，外部系統無回應時的記錄只能出現在結果時刻；逾時之前沒有任何記錄，形成可觀測性空窗，正如輸入端缺互動回饋時使用者「按了沒反應」。

### 回饋消費者與投影關係

輸出端的回饋消費者不是單一對象，而是幾個獨立實體，各自消費同一組事件的不同投影：

| 消費者 | 消費形式 | 消費目的 |
|--------|---------|---------|
| 呼叫端程式碼 | 回傳值、例外、非同步狀態、progress callback | 程式決策：重試、降級、傳播錯誤、更新狀態 |
| 日誌 | 結構化記錄（時間戳 + context + 層級） | 事後診斷、稽核軌跡、根因分析 |
| 監控追蹤 | 追蹤區段起訖、延遲分佈、錯誤率 | 長期健康度、告警觸發 |

三種投影各自不可替代：日誌記了不代表呼叫端知道，呼叫端處理了不代表日誌有留紀錄，兩者都有不代表監控追蹤有記下延遲分佈。

**不互相抵扣規則**：日誌不抵扣呼叫端回饋，呼叫端回饋不抵扣日誌——兩者是獨立義務，審查時分別確認。此規則與 UI 層「日誌不抵扣使用者回饋」同構（見 `ARCH-GPD-001`）。典型違反：adapter 的例外處理只記日誌並回傳預設值，呼叫端因此拿到一個無法區分「成功且值恰為預設值」與「失敗被降級」的結果——日誌完整但呼叫端已被誤導。

**反向路由**：port 呼叫進入稀缺通道（連線池、佇列、isolate 事件迴圈等）之前，還有一個仲裁決策事件決定是否放行、卸載或降級，見 `.claude/methodologies/event-flow-load-arbitration-methodology.md`〈可觀測性〉；兩者不互相涵蓋——本節管單次外部呼叫的可觀測時刻，該方法論管仲裁決策事件。

### 時序約束

日誌與監控追蹤不是事後可補的能力，它們消費的是設計期就決定好的回饋點：

- Port 介面的簽章決定呼叫端能拿到什麼——回傳型別是否能區分成功與失敗、是否有 progress callback、是否有受理狀態。這些決定外部系統受理這個時刻是否可被消費。
- Adapter 實作中記錄呼叫的位置決定各個時刻是否被記下——呼叫前一行（呼叫發出）、收到受理回應時（外部系統受理）、操作完成時（結果）。
- 設計期沒有把回饋點寫進 port 契約，事後補記錄只能拿到例外堆疊（結果時刻的失敗分支），拿不到前面的時刻——因為那些時刻的記錄需要程式碼在那個位置主動發出記錄呼叫，那些位置不在例外路徑上。

### 測試義務

| 時刻 | 驗證目標 | 是否需要外部系統替身 |
|------|---------|---------------------|
| 呼叫發出 | port 方法確實被呼叫、呼叫事件被記錄 | 不需要——用記錄器（spy）確認方法被呼叫、參數為何即可，不模擬任何行為 |
| 外部系統受理 | adapter 正確處理受理狀態或 progress callback | 需要——注入模擬外部系統受理行為的替身 |
| 結果 | adapter 正確處理各種結局（成功、失敗、逾時、不可達） | 需要——注入模擬各種結局的替身 |

呼叫發出這個時刻不需要外部系統替身，精神同輸入端互動回饋（不需要服務依賴，只驗元件自身的即時反應）——差異在載體：輸入端的載體是元件本身（建構即有），輸出端的載體是 port 介面（依賴注入），需要一個記錄器來捕捉呼叫事實。這個記錄器不是行為替身，不屬於模擬外部系統結局的替身角色分類，只單純記錄「方法被呼叫了、參數是什麼」。

## Reference

### 整合方法論

- [TDD 協作開發流程](./tdd-collaboration-flow.md) - TDD 四階段與 Clean Architecture 整合
- [敏捷重構方法論](./agile-refactor-methodology.md) - Agent 分派與架構層級對應
- [Domain Bundle 邊界映射](./domain-bundle-mapping-methodology.md) - 從 spec FR 反推 DDD domain bundle 邊界、依賴方向 DAG、不變式清單

### 實作詳解

- Clean Architecture SKILL（規劃中）- 完整程式碼範例和案例研究