# Phase 3b 代理人派發 Prompt 模板

PM 派發 Phase 3b 子任務時使用此模板，從結構化規格中提取必要資訊，限定代理人 context 消耗。

> **來源**：0.2.0-W3-005 — 目前 prompt 要求代理人讀取 3 份完整設計文件，context 消耗過高。

---

## 核心原則

**代理人只需知道「要通過哪些測試」和「介面長什麼樣」**。

代理人不需要讀取完整的 Phase 1/2/3a 設計文件。PM 在派發時提取必要區段，直接嵌入 prompt。

---

## 模板

```markdown
## 任務

{Ticket ID} — 通過測試群組 {TC 範圍}（{群組描述}）

## API 簽名（從 Phase 1 feature-spec 提取）

{僅複製與此測試群組相關的 API 簽名，包含參數型別和回傳值}

## 測試案例（從 Phase 2 test-design 提取）

{僅複製此測試群組的 GWT 場景，含 Given/When/Then}

## 相關常數（從現有程式碼提取）

{僅列出此子任務需要使用的既有常數定義和匯入路徑}

## 修改檔案

{列出此子任務允許修改的檔案清單}

## 禁止

- 不要讀取完整的 Phase 1/2/3a 設計文件
- 不要修改上述清單以外的檔案
- 不要新增未在測試案例中定義的功能
```

---

## PM 提取指引

### 三類必要資訊

| 類別 | 來源 | 提取方式 |
|------|------|---------|
| API 簽名 | Phase 1 feature-spec §2 | 複製與測試群組相關的函式簽名和參數表 |
| 測試案例 | Phase 2 test-design | 複製對應 GWT 場景（含 Given/When/Then） |
| 相關常數 | 現有程式碼 | grep 提取代理人需要 import 的常數 |

### 提取步驟

1. **確認測試群組範圍**：從 Phase 2 test-design 中識別此子任務對應的 TC 編號範圍
2. **提取 API 簽名**：從 Phase 1 feature-spec 的 §2（API Signatures）複製相關介面定義
3. **提取測試案例**：從 Phase 2 test-design 複製對應的 GWT 場景
4. **掃描相關常數**：在現有程式碼中 grep 此子任務會用到的常數和型別定義
5. **組裝 prompt**：按模板格式填入，確認 context 預算

### Context 預算

| 項目 | 上限 | 說明 |
|------|------|------|
| API 簽名 | < 2K tokens | 只含相關介面，非全部 |
| 測試案例 | < 5K tokens | 只含此群組的 GWT |
| 相關常數 | < 1K tokens | 只含需要 import 的 |
| 代理人實作空間 | < 12K tokens | 程式碼撰寫和工具互動 |
| **單一子任務合計** | **< 20K tokens** | 超過需再拆分 |

---

## 範例

### 派發範例（WebSocket Server 心跳子任務）

```markdown
## 任務

0.2.0-W2-001.4.2 — 通過測試群組 TC-14~TC-16,TC-18~TC-34（事件推送 + 心跳 + 分頁 + 並發）

## API 簽名

// HeartbeatManager 管理單一 WebSocket 連線的心跳偵測
func NewHeartbeatManager(conn *websocket.Conn, opts ...HeartbeatOption) *HeartbeatManager
func (h *HeartbeatManager) Start(ctx context.Context) error
func (h *HeartbeatManager) Stop()

// EventRouter 將 SessionEvent 路由到對應的訂閱者
func (r *EventRouter) RouteEvent(event SessionEvent) error
func (r *EventRouter) Subscribe(clientID string, filter SubscriptionFilter) error

## 測試案例

### TC-14: 事件推送 — 正常路由
- Given: Client 已訂閱 session_id="abc"
- When: SessionEvent{SessionID: "abc"} 到達
- Then: Client 收到 session_event 訊息

### TC-17: 心跳 — pong 逾時
- Given: HeartbeatManager 已啟動，timeout=10s
- When: 超過 10s 未收到 pong
- Then: 連線關閉，回傳 ErrPongTimeout

## 相關常數

// server/constants.go
const HeartbeatIntervalSecs = 30
const HeartbeatTimeoutSecs = 10
const MaxPageSize = 100

## 修改檔案

- server/heartbeat_manager.go
- server/event_router.go
- server/heartbeat_manager_test.go
- server/event_router_test.go
```

---

## 禁止行為

| 禁止 | 說明 |
|------|------|
| 在 prompt 中要求代理人「先讀取 Phase 1/2/3a 文件」 | PM 應預先提取，代理人只讀 prompt |
| 提供整份設計文件的路徑 | 代理人會讀取全文，浪費 context |
| 省略測試案例只給「通過所有測試」 | 代理人需要知道具體的 GWT 才能實作 |
| 省略 API 簽名 | 代理人需要知道函式介面才能實作 |

---

## 相關文件

- .claude/pm-rules/tdd-flow.md - 3b 拆分評估（測試群組導向）
- .claude/rules/guides/task-splitting.md - 策略 7：按測試群組拆分
- .claude/skills/spec/SKILL.md - /spec Skill（Phase 1 產出物品質工具）

---

**Version**: 1.0.0
**Last Updated**: 2026-03-25
**Source**: 0.2.0-W3-005
