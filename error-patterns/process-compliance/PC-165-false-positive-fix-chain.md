---
id: PC-165
title: False Positive 修復鏈 — 測試綠燈不等於 Runtime 正確
category: process-compliance
severity: high
status: active
created: 2026-05-28
related:
- PC-028
- PC-082
- PC-131
- PC-136
---

# PC-165: False Positive 修復鏈 — 測試綠燈不等於 Runtime 正確

修復 ticket 在測試套件下全通過（綠燈），但 runtime 行為未改變或未生效；後續 ticket 基於「修復已生效」假設執行進一步操作（移除舊路徑、清理表層補救、推進依賴鏈），造成連鎖回歸。根因在於測試斷言不覆蓋實際 runtime 路徑（特別是訊息系統、日誌系統、跨模組整合等隱性依賴），加上動態語言（JavaScript）對多餘參數靜默忽略，使修復鏈中每步看似獨立通過、實則端到端未驗證。

**Why**：測試綠燈與 runtime 正確之間存在「斷言覆蓋落差」。當測試 mock 取代真實依賴、斷言只檢查 DOM 結構或回傳值結構（而非訊息文字、實際呼叫參數、實際取用的資料來源）時，被 mock 的部分能繼續運作，但實際 runtime 整合路徑可能完全失效。一旦此種「綠燈但無效」的修復被視為「修復已生效」，後續 ticket 會以此為前提推進，將表層補救（如直接在 GlobalMessages 加 key）移除，暴露根本未生效的修復。

**Consequence**：

| 層級 | 影響 |
|------|------|
| Runtime | 使用者可見的功能回歸（如 popup 訊息顯示為 `[Missing: KEY]`）；阻塞版本發布 / 內測 |
| 信任 | 測試套件的「通過 = 可信」承諾被打破，後續代理人 / 審查者難判斷哪些通過是真實的 |
| 追溯 | 多 ticket 連鎖（W1-004 → W1-105 → W1-106 → W1-108）才能反向定位根因，每次回溯成本高 |
| 設計債 | 表層補救（在 GlobalMessages 加 key）反而是「唯一實際生效」的修復，原始 local dict 設計從未生效，技術債潛伏 |

**Action**：

1. 修復「訊息系統」「日誌系統」「跨模組整合」「設計時跨檔同步」類 bug 時，acceptance 必須含 **runtime 層級驗證**（chrome-devtools-mcp 實機載入、integration test 斷言訊息文字、log 內容比對），而非僅 unit test pass / 結構斷言。
2. 後續 ticket 若 why 含「基於 X ticket 修復已生效的假設」（如「W1-105 已修好 constructor，可以移除 GlobalMessages popup key」），必須先用 runtime 驗證假設成立，再執行（不可直接信任前序 ticket 的綠燈結論）。
3. 動態語言（JavaScript / Python kwargs）函式簽章變更時，grep 全專案 caller 確認參數數量與順序匹配；JS 靜默忽略多餘參數的特性使這類錯誤潛伏期可達數年。

---

## 觸發案例

### W1-105 / W1-106 / W1-108 連鎖根因事件鏈（2026-05-27 揭露）

**時序**：

1. **2025-09-04**（commit `2367c48b`）：Logger.js 初始建立，`constructor(name = 'App', level = 'INFO')` 兩參數，`this.messages = GlobalMessages` 在 constructor body L68 hardcoded。
2. **2025-09-04**（commit `4be88fa6`）：popup.js / book-search-filter-integrated.js / readmoo-platform-migration-validator.js 同日建立，三處 caller 以 `new Logger('Name', 'INFO', localMessages)` 形式傳第三參數。**Logger 端從未實作接收，JavaScript 靜默忽略第三參數**。整個 popup / search-filter / validator local dict 注入機制從建立日起即未生效，潛伏 8 個月。
3. **2026-05-26（W1-004）**：popup 出現 `[Missing: KEY]`，開發者採表層補救——直接將 5 個 popup-specific key 加入 GlobalMessages。此修復實際生效（因為 Logger 確實取用 GlobalMessages），但根因（local dict 機制失效）未識別。
4. **2026-05-27（W1-105）**：修復 MessageDictionary constructor 為 union signature 支援 `new MessageDictionary({ KEY: { template, defaultLevel } })`。**測試 41/41 通過**。但 Logger 仍 hardcoded `this.messages = GlobalMessages`，三處 caller 註冊的 local dict 仍未被取用——**runtime 完全無效**。
5. **2026-05-27（W1-106，commit `f39a9f04`）**：基於「W1-105 已修好 local dict 機制」的假設，移除 GlobalMessages 中 5 個 popup-specific key。popup-interface.test.js 36 個 test case **零 case 檢查 Logger 訊息文字**（mock Logger 不走真實 messages 解析路徑），測試全綠通過。但 popup runtime 100% 回歸 `[Missing: KEY]`。
6. **2026-05-27（W1-108）**：PM 前台分析 grep `new Logger(` 全專案呼叫，發現 30+ 處呼叫中 3 處傳第三參數，對照 Logger constructor 簽章，識破 JS 靜默忽略多餘參數的根因。
7. **2026-05-27（W1-112）**：incident ANA 全面評估，實機驗證 5/5 key 確認回歸 `[Missing: KEY]`，產出 5 個 spawn ticket（含本 PC error-pattern）。

**False positive 在每步如何被遮蔽**：

| Ticket | 綠燈內容 | 為何遮蔽 runtime 無效 |
|--------|---------|---------------------|
| W1-105 | MessageDictionary unit test 41/41 通過 | 測試只驗 MessageDictionary 本身註冊邏輯；不驗 Logger 是否取用註冊結果 |
| W1-106 | popup-interface.test.js 36 case 全綠 | 36 case 零 case 用 `expect(...).toContain('POPUP_')` 或斷言 Logger 訊息文字；mock Logger 跳過 messages 解析路徑 |
| 整體 | npm test 套件全綠 | 整合測試層無 runtime 訊息文字斷言；popup-interface.test 與 Logger.test 各管各的，跨模組整合未驗 |

**根本機制（三層共振）**：

1. **JavaScript 靜默忽略多餘函式參數**：`new Logger('A', 'B', extraArg)` 在 constructor `(name, level) => {}` 下不報錯，`extraArg` 默默丟失。此為語言層特性，bug 潛伏期可達數年。
2. **測試斷言不覆蓋 runtime 文字**：popup-interface.test.js 設計時 mock Logger，斷言聚焦 DOM 結構與互動，不斷言訊息文字內容——這在純 UI 測試合理，但對「修復訊息系統」類 ticket 而言不夠。
3. **後續 ticket 信任前序綠燈**：W1-106 撰寫時，作者讀到 W1-105 已 completed 且 acceptance 全勾，合理推論「local dict 機制已修好」，未獨立驗證假設成立。

---

## 根本原因

### 表層原因

| 原因 | 說明 |
|------|------|
| 測試斷言不覆蓋訊息文字 | popup-interface.test.js 36 case 零文字斷言；單元層各管各，跨模組整合未驗 |
| JavaScript 靜默忽略多餘參數 | constructor 兩參數 vs caller 傳三參數，無 TypeError、無 warning |
| 後續 ticket 信任前序綠燈 | W1-106 未獨立驗證「W1-105 修好 local dict 機制」假設成立 |
| Mock 自洽 | mock Logger 在測試環境替代真實 Logger，繞過真實 messages 解析路徑 |

### 深層原因

| 維度 | 說明 |
|------|------|
| Acceptance 設計缺 runtime 層 | 修復「訊息系統」「日誌系統」類 bug 的 acceptance 通常只要求 unit test pass，未要求 chrome-devtools-mcp 實機驗證或 integration 斷言訊息文字 |
| 動態語言設計安全網薄 | JavaScript 不強制函式簽章對齊，依賴開發者自律 grep caller；無 TypeScript-like 編譯期保護 |
| 表層補救正回饋遮蔽 | W1-004 加 GlobalMessages 表層補救「實際生效」，反而讓 popup 跑得起來，掩蓋 local dict 機制從未生效的事實達 8 個月 |
| 修復鏈推進無中間檢查點 | W1-105 → W1-106 推進時無「runtime 驗證假設」的強制檢查點，連續綠燈直接推進到下一個 ticket |

---

## 與 PC-028 / PC-082 / PC-131 / PC-136 的關係

| PC | 領域 | 與本 PC 共通機制 |
|----|------|----------------|
| PC-028 | agent report unverified assumption | 同源「未驗證即推進」；PC-028 聚焦代理人回報層，本 PC 聚焦 ticket 修復鏈層 |
| PC-082 | regression fix direction（restore vs remove） | 共通「修復方向誤判」；本 PC 是 PC-082 在「跨 ticket 修復鏈」場景的延伸 |
| PC-131 | external tool authority skepticism | 共通「不應盲信權威輸出」；PC-131 針對外部工具，本 PC 針對前序 ticket 綠燈結論 |
| PC-136 | structural fix incomplete caller scan | 同源「函式簽章變更 grep caller 不全」；本 PC 含 PC-136 子集，並擴展到測試層 false positive |
| IMP-078 | runtime API mismatch | 共通「測試環境 vs 目標環境差異」上位概念；IMP-078 聚焦跨環境部署（Node.js vs Browser API），與本 PC「修復鏈 false positive」並列存在，交集案例為 W1-047.1~.5 |

**整合 advice**：未來修訂時，可考慮將 PC-028 / PC-131 / PC-165 整併為「未驗證信任」上位 PC，下分代理人回報 / 外部工具 / ticket 修復鏈三個觸發領域。另，IMP-078（CE-Node runtime mismatch）與本 PC 為並列關係：兩者同屬「測試綠燈但 runtime 失效」表層症狀，但根因領域正交（實作層 API 選擇 vs 流程層修復鏈），交集案例 W1-047.1~.5 同時具備兩者特徵，診斷時宜雙向對照。

---

## 正確做法

### Approach A：修復類 ticket acceptance 強制含 runtime 驗證（推薦）

| 動作 | 何時 |
|------|------|
| 撰寫修復類 ticket 時，acceptance 必含至少 1 項 runtime 層級驗證（chrome-devtools-mcp 實機 / integration 斷言訊息文字 / 跨模組整合 e2e） | ticket 撰寫期 |
| Acceptance 範例：`[ ] chrome-devtools-mcp 載 extension 開 popup，console 不含 [Missing: KEY]`（含具體實證證據要求） | ticket 撰寫期 |
| 撰寫者無法在 ticket 中提供 runtime 證據時，acceptance 標明留給執行 agent 補完 | ticket 撰寫期 |

**Why**：unit test 綠燈是必要條件不是充分條件；訊息系統 / 日誌系統 / 多模組整合類修復必須由實機 runtime 驗收。

**Consequence**：每個修復類 ticket 多 1 項 acceptance；執行 agent 多 5-10 分鐘 chrome-devtools-mcp 操作。權衡：避免 W1-105 → W1-106 → W1-108 連鎖回溯成本（多 ticket、多代理人輪迴）。

**Action**：將本流程加入 IMP ticket 撰寫 SOP；對「修復類 + 訊息/日誌/跨模組」三標籤聯集的 ticket 強制套用。

### Approach B：後續 ticket 信任前序修復前獨立驗證假設

| 動作 | 何時 |
|------|------|
| ticket why 含「基於 X ticket 修復已生效」字樣時，PM claim 前必執行 1 次假設驗證（不依賴 X ticket 的 acceptance 勾選） | claim 前 |
| 驗證方法：實機 runtime / grep 確認修復點實際生效 / 跑 integration test 並讀 log | claim 前 |
| 驗證失敗即不 claim，改建 ANA ticket 評估 | claim 前 |

**Why**：前序 ticket 的綠燈不等於修復生效；信任傳遞性在 false positive 修復鏈下會放大錯誤。

**Consequence**：claim 前多 5-10 分鐘驗證；對「修復假設依賴鏈」中的 ticket 必要。

**Action**：將本流程加入 `pm-rules/decision-tree.md` 或 ticket claim SOP。

### Approach C：JavaScript 函式簽章變更 grep caller 強制（長期）

| 動作 | 何時 |
|------|------|
| 任何函式 / class constructor 簽章變更（增減參數、改順序），grep 全專案 caller 確認匹配 | 簽章變更時 |
| 不匹配 caller 須同步更新或顯式宣告為 deprecated | 簽章變更時 |
| 對熱點類（Logger / Event / Storage 等基礎類）建立 caller scan acceptance template | 模板化階段 |

**Why**：JS 靜默忽略多餘參數使簽章不對齊的 bug 潛伏期極長；W1-105 案例已潛伏 8 個月。

**Consequence**：簽章變更時多 5 分鐘 grep；對熱點類效益最高（單次掃描可預防多年潛伏 bug）。

**Action**：將本流程加入 IMP ticket 撰寫 SOP；列為 PC-136 的協同 PC。

---

## 防護措施

### 第一層：修復類 ticket acceptance 模板（短期）

**適用條件**：適用於所有「修復類 + 訊息/日誌/跨模組整合」三標籤聯集的 IMP ticket。零工程成本，依賴撰寫者自律與 PM 派發前審查。

撰寫者 / PM 套用「修復類 acceptance template」，至少含 1 項 runtime 驗證項。執行 agent 完成 runtime 驗證項作為 complete 必要條件。

### 第二層：claim 前假設驗證（中期）

**適用條件**：適用於 why 含「基於 X ticket 修復已生效」字樣的 ticket。中等流程成本（claim 前 5-10 分鐘），但對 false positive 修復鏈防護強度高。

PM 在 claim 此類 ticket 前獨立驗證假設成立；可派發短任務（如「chrome-devtools-mcp 載 extension 確認 X 行為」）作為前置子任務。

### 第三層：JavaScript 簽章變更 caller scan 強制（長期）

**適用條件**：適用於函式 / class constructor 簽章變更（增減參數、改順序）。可結合 lint rule 或 hook 強制執行。

簽章變更 commit 前，grep 全專案 caller 確認匹配；不匹配者同步更新。

---

## 邊界與例外

| 情境 | 適用 |
|------|------|
| 修復訊息系統 / 日誌系統 / 跨模組整合類 bug | 適用（核心情境） |
| 修復純 UI / 純資料結構 bug（無跨模組整合） | 部分適用——unit test 通常足夠，但仍建議 integration 斷言 |
| 純 refactor（不改行為） | 不適用——可依賴測試綠燈作驗證 |
| 後續 ticket 不依賴前序修復假設（如獨立功能新增） | 不適用 |
| 靜態類型語言（TypeScript / Dart） | 部分適用——編譯期阻擋簽章不匹配，但測試 mock 仍可能遮蔽 runtime 路徑 |
| 動態類型語言（JavaScript / Python kwargs） | 強烈適用——語言層無安全網，依賴流程層 |

**邊界判定原則**：本 PC 觸發前提是「修復鏈中存在跨模組整合 + 測試 mock 替代真實依賴 + 後續 ticket 信任前序綠燈」三條件聯集。任一條件不成立可降級適用。

---

## 相關

| 參考 | 關聯 |
|------|------|
| PC-028 | agent report unverified assumption（同源未驗證信任） |
| PC-082 | regression fix direction restore vs remove（修復方向誤判家族） |
| PC-131 | external tool authority skepticism（不盲信權威輸出） |
| PC-136 | structural fix incomplete caller scan（簽章變更 grep 不全） |
| W1-004 | 表層補救加 GlobalMessages 5 popup key（事件鏈起點） |
| W1-105 | MessageDictionary constructor union signature（false positive 第一步） |
| W1-106 | 移除 GlobalMessages 5 popup key（false positive 第二步，commit f39a9f04） |
| W1-108 | PM 前台識破 Logger 簽章不對齊（根因揭露） |
| W1-112 | incident ANA 全面評估（本 PC 來源） |
| W1-113 | Revert W1-106（spawn IMP） |
| W1-115 | Logger constructor 加第三參數 messages（spawn IMP，根因修復） |
| W1-116 | Logger local dict 測試補強（spawn IMP，覆蓋缺口修復） |

---

**Last Updated**: 2026-05-28
**Version**: 1.0.0 — 初始建立，源 W1-105 / W1-106 / W1-108 / W1-112 事件鏈（W1-114 落地 W1-112 ANA Solution 第 5 spawn）
