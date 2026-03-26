# Spec 模板 — Full 模式

適用於新功能開發、跨模組修改、API 變更。6 個必填區段，目標總量 < 5K tokens。

---

## 模板

```markdown
# {Ticket ID} 功能規格

## 1. Purpose（目的）

<!-- 指引：用 3-5 句話回答以下問題（~500 tokens）。
     - 問題背景：為什麼需要這個功能？現狀的痛點是什麼？
     - 目標用戶：誰會使用？直接用戶和間接受益者？
     - 核心價值：解決後帶來什麼改善？用量化指標描述（如「從 5 步減到 1 步」）
     - 非目標：明確列出這次不做什麼（避免範圍蔓延）
-->

### 背景
{現狀痛點描述}

### 目標
{期望達成的具體改善}

### 非目標
- {明確排除的範圍 1}
- {明確排除的範圍 2}

## 2. API Signatures（介面定義）

<!-- 指引：列出所有公開介面的簽名和參數說明（~1000 tokens）。
     - 函式簽名：名稱、參數型別、回傳型別
     - 參數語義：每個參數的含義和有效值範圍
     - 回傳值語義：成功/失敗時的回傳值
     - 若為 class/struct：列出所有公開屬性和方法
-->

### {元件名稱 1}

```{語言}
// 簡短說明此介面的職責
{函式或類別簽名}
```

**參數說明**：

| 參數 | 型別 | 說明 | 有效範圍 |
|------|------|------|---------|
| {param1} | {type} | {說明} | {範圍或約束} |

**回傳值**：{成功時回傳什麼，失敗時回傳什麼}

## 3. GWT Scenarios（行為場景）

<!-- 指引：用 GWT 格式描述 5-15 個行為場景（~1500 tokens）。
     分組方式：
     - 正常流程（Happy Path）：至少 2 個
     - 邊界條件（Boundary）：至少 2 個
     - 異常流程（Error Path）：至少 1 個
     每個 Then 必須是可驗證的具體結果。
-->

### 正常流程

#### 場景 1: {場景名稱}
- **Given**: {前置條件}
- **When**: {觸發動作}
- **Then**: {預期結果}

### 邊界條件

#### 場景 N: {邊界場景名稱}
- **Given**: {邊界前置條件}
- **When**: {觸發動作}
- **Then**: {預期結果}

### 異常流程

#### 場景 M: {異常場景名稱}
- **Given**: {異常前置條件}
- **When**: {觸發動作}
- **Then**: {錯誤處理結果}

## 4. Error Handling（錯誤處理）

<!-- 指引：用表格定義每種錯誤情境的處理策略（~500 tokens）。
     - 列出所有可能的錯誤類型
     - 每種錯誤的處理策略（重試/降級/拋出/忽略）
     - 錯誤訊息格式和內容
     - 是否需要回滾已完成的步驟
-->

| 錯誤情境 | 處理策略 | 回傳/拋出 | 需要回滾？ |
|---------|---------|----------|-----------|
| {錯誤 1} | {策略} | {回傳值或 Exception} | {是/否} |
| {錯誤 2} | {策略} | {回傳值或 Exception} | {是/否} |

## 5. Dependencies（依賴）

<!-- 指引：用表格列出所有外部依賴（~300 tokens）。
     - 外部套件/模組依賴
     - 前置條件（需要先完成的其他功能）
     - 環境假設（作業系統、版本、配置）
     - 依賴不可用時的降級策略
-->

| 依賴 | 類型 | 用途 | 不可用時 |
|------|------|------|---------|
| {依賴 1} | {套件/服務/模組} | {用途} | {降級策略} |

## 6. Acceptance（驗收條件）

<!-- 指引：列出 5-10 條可直接驗證的條件（~500 tokens）。
     - 每條以 checkbox 格式開頭
     - 必須覆蓋所有 GWT Scenarios 的 Then
     - 包含非功能性要求（效能、相容性、安全）
     - 避免模糊詞（「正確處理」→「回傳 ErrorCode.NOT_FOUND」）
-->

- [ ] {條件 1}
- [ ] {條件 2}
```

---

## Full 填寫範例（WebSocket 心跳偵測場景）

```markdown
# 0.2.0-W2-001.4 功能規格（心跳偵測子功能）

## 1. Purpose（目的）

### 背景
WebSocket 長連線在網路不穩定時可能靜默斷開（TCP 層未通知），
Client 無法感知連線已失效，持續等待永遠不會到達的訊息。

### 目標
實作雙向心跳偵測機制，Server 定期發送 ping，Client 回應 pong，
超時未回應則主動斷開並通知 Client 重新連線。
從「靜默斷開等到用戶投訴」改善為「30 秒內自動偵測並觸發重連」。

### 非目標
- 不處理 Client 端重連邏輯（屬前端 Ticket）
- 不實作自適應心跳間隔（V2 範圍）

## 2. API Signatures（介面定義）

### HeartbeatManager

```go
// HeartbeatManager 管理單一 WebSocket 連線的心跳偵測
type HeartbeatManager struct {
    conn      *websocket.Conn
    interval  time.Duration
    timeout   time.Duration
}

func NewHeartbeatManager(conn *websocket.Conn, opts ...HeartbeatOption) *HeartbeatManager
func (h *HeartbeatManager) Start(ctx context.Context) error
func (h *HeartbeatManager) Stop()
func (h *HeartbeatManager) LastPongAt() time.Time
```

**參數說明**：

| 參數 | 型別 | 說明 | 有效範圍 |
|------|------|------|---------|
| conn | *websocket.Conn | 目標 WebSocket 連線 | 非 nil，已建立連線 |
| interval | time.Duration | ping 發送間隔 | 5s - 120s，預設 30s |
| timeout | time.Duration | pong 等待逾時 | interval 的 1-3 倍，預設 10s |

**回傳值**：Start() 在連線關閉或 context 取消時回傳 error

## 3. GWT Scenarios（行為場景）

### 正常流程

#### 場景 1: 正常心跳交換
- **Given**: Client 已建立 WebSocket 連線，HeartbeatManager 已啟動
- **When**: 經過 30 秒（interval）
- **Then**: Server 發送 ping frame，Client 回應 pong，LastPongAt 更新

#### 場景 2: 連線正常關閉
- **Given**: HeartbeatManager 正在運行
- **When**: 呼叫 Stop()
- **Then**: 停止發送 ping，釋放 goroutine，不觸發斷線處理

### 邊界條件

#### 場景 3: pong 在逾時邊界到達
- **Given**: ping 已發送，timeout 設為 10s
- **When**: pong 在第 9.9 秒到達
- **Then**: 視為正常，更新 LastPongAt，不觸發斷線

#### 場景 4: 多個連線同時心跳
- **Given**: 3 個 Client 各自有 HeartbeatManager
- **When**: 同時運行心跳偵測
- **Then**: 各自獨立運作，互不影響

### 異常流程

#### 場景 5: pong 逾時
- **Given**: ping 已發送，timeout 設為 10s
- **When**: 超過 10 秒未收到 pong
- **Then**: 關閉連線，Start() 回傳 ErrPongTimeout

#### 場景 6: 發送 ping 時連線已斷開
- **Given**: HeartbeatManager 正在運行
- **When**: 底層 TCP 連線已斷開，嘗試發送 ping
- **Then**: 寫入失敗，關閉連線，Start() 回傳 write error

## 4. Error Handling（錯誤處理）

| 錯誤情境 | 處理策略 | 回傳/拋出 | 需要回滾？ |
|---------|---------|----------|-----------|
| pong 逾時 | 關閉連線 | ErrPongTimeout | 否 |
| ping 寫入失敗 | 關閉連線 | 原始 write error | 否 |
| context 取消 | 停止心跳 | context.Canceled | 否 |
| conn 為 nil | 拒絕啟動 | ErrNilConnection | 否 |

## 5. Dependencies（依賴）

| 依賴 | 類型 | 用途 | 不可用時 |
|------|------|------|---------|
| gorilla/websocket | 套件 | WebSocket 連線管理 | 無法運作 |
| context | 標準庫 | goroutine 生命週期控制 | 無法運作 |

## 6. Acceptance（驗收條件）

- [ ] ping 按 interval 定期發送（預設 30s）
- [ ] pong 逾時（預設 10s）後主動關閉連線
- [ ] Stop() 呼叫後 goroutine 正確釋放
- [ ] 多連線獨立心跳互不干擾
- [ ] conn 為 nil 時回傳 ErrNilConnection
- [ ] pong 在逾時邊界內到達時不觸發斷線
```

---

## Full validate 維度

Full 模式的 `/spec validate` 掃描 3 個核心維度（同 Lite），並額外提示情境相關問題（並發安全、效能約束、安全性、依賴明確性）供撰寫者自行考慮。

> 詳見 SKILL.md「掃描維度」和「情境相關提問」章節。

---

**Version**: 1.0.0
**Last Updated**: 2026-03-25
