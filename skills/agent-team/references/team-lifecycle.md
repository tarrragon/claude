# Agent Teams 生命週期

本文件定義 Agent Teams 從建立到關閉的完整生命週期操作指引。

---

## 生命週期總覽

```
Stage 1: Plan（PM 準備）
    |
    v
Stage 2: Create（PM 建立 Team）
    |
    v
Stage 3: Coordinate（Team 協作）
    |
    v
Stage 4: Converge（結果收集）
    |
    v
Stage 5: Shutdown（清理）
```

---

## Stage 1: Plan（PM 準備）

**執行者**：rosemary-project-manager

### 1.1 確認 Ticket

- [ ] 所有子任務的 Ticket 已建立
- [ ] Ticket 狀態為 pending
- [ ] 驗收條件已定義

### 1.2 設計任務分解

- [ ] 確定需要幾個 teammates
- [ ] 每個 teammate 的角色和職責
- [ ] 任務間的依賴關係

### 1.3 並行安全檢查

- [ ] 檔案無重疊：各任務修改的檔案集合無交集
- [ ] 測試無衝突：各任務的測試可獨立執行
- [ ] 依賴無循環：任務之間無先後依賴關係
- [ ] Wave 無跨越：所有任務屬於同一個 Wave

### 1.4 成本評估

| 項目 | 評估 |
|------|------|
| 預估 teammate 數量 | {N} |
| 預估 Token 倍率 | 3-4x |
| 是否有更簡單的替代方案 | Task subagent 是否足夠？ |

---

## Stage 2: Create（PM 建立 Team）

**執行者**：rosemary-project-manager

### 2.1 建立 Team

```
TeamCreate(name="{team_name}", description="{team_description}")
```

### 2.2 建立 Tasks

為每個子任務建立 Task，metadata 必須包含 ticketId：

```
TaskCreate(
  team_name="{team_name}",
  title="{task_title}",
  description="{task_description}"
)
```

### 2.3 Spawn Teammates

為每個 teammate 使用 Task tool 搭配入職模板：

```
Task(
  subagent_type="{agent_type}",
  team_name="{team_name}",
  prompt="{入職模板（已替換變數）}"
)
```

---

## Stage 3: Coordinate（Team 協作）

**執行者**：Team 全體

### Teammates 的工作流程

```
Teammate 啟動
    |
    v
閱讀入職指令
    |
    v
ticket track claim {ticketId}
    |
    v
執行工作
    |
    +-- 重要進展 → ticket track append-log
    +-- 遇到阻塞 → SendMessage 給 team-lead
    +-- 需要溝通 → SendMessage 給指定 teammate
    |
    v
工作完成
    |
    v
ticket track append-log（Test Results）
    |
    v
TaskUpdate(status=completed)
    |
    v
SendMessage 通知 team-lead
```

### PM 的監控職責

| 監控項目 | 方式 | 頻率 |
|---------|------|------|
| Task 進度 | TaskList 查看 | 自動通知 |
| Teammate 訊息 | SendMessage 自動送達 | 即時 |
| 阻塞處理 | 回應 teammate 升級 | 即時 |
| Ticket 狀態 | ticket track query | 按需 |

---

## Stage 4: Converge（結果收集）

**執行者**：rosemary-project-manager

### 4.1 確認所有 Task 完成

```
TaskList(team_name="{team_name}")
```

確認所有 Task 狀態為 completed。

### 4.2 驗證 Ticket

- [ ] 每個 Ticket 的日誌已更新（Solution、Test Results）
- [ ] 驗收條件可驗證

### 4.3 派發驗收

依照現有 Ticket 生命週期流程：

```
PM → AskUserQuestion（驗收方式確認）→ acceptance-auditor → 驗收報告
```

---

## Stage 5: Shutdown（清理）

**執行者**：rosemary-project-manager

### 5.1 通知 Teammates 關閉

```
SendMessage(
  team_name="{team_name}",
  message="所有任務已完成，Team 即將關閉。請確認所有工作已儲存。"
)
```

### 5.2 刪除 Team

```
TeamDelete(name="{team_name}")
```

### 5.3 完成 Tickets

驗收通過後：

```
ticket track complete {ticketId_1}
ticket track complete {ticketId_2}
...
```

---

## 成本意識

### Token 成本比較

| 方式 | 相對成本 | 適用場景 |
|------|---------|---------|
| 單一 Task subagent | 1x | 簡單獨立任務 |
| 並行 Task subagent | 1x * N | 獨立並行任務 |
| Agent Teams | 3-4x | 需即時互動的協作任務 |

### 成本優化原則

| 原則 | 說明 |
|------|------|
| 最小化 team 規模 | 只加入真正需要互動的角色 |
| 明確的結束條件 | 避免 teammates 空轉 |
| 及時 shutdown | 任務完成後立即關閉 team |
| 避免過度溝通 | SendMessage 應有明確目的 |

---

## 回退策略

### 何時回退

| 情境 | 指標 | 回退方式 |
|------|------|---------|
| Teammate 長時間無進展 | 5+ 分鐘無更新 | Shutdown → Task subagent |
| 通訊失敗 | SendMessage 無回應 | Shutdown → Task subagent |
| 任務衝突 | 檔案編輯衝突 | Shutdown → 序列派發 |
| 成本超預期 | Token 使用量超預估 2x | Shutdown → Task subagent |

### 回退流程

```
識別回退條件
    |
    v
SendMessage("暫停當前工作，Team 即將回退")
    |
    v
收集已完成的工作（透過 Ticket 日誌）
    |
    v
TeamDelete
    |
    v
改用 Task subagent 繼續
    |
    v
Ticket 狀態保持不變（Ticket 是持久的）
```

### 資料保全

- Ticket .md 檔案不受 Team 關閉影響
- Teammate 的 append-log 記錄已持久化
- 程式碼修改已在檔案系統中
- 只有 Task List 會消失（ephemeral）

---

## 相關文件

- .claude/skills/agent-team/SKILL.md - Agent Teams 指南入口
- .claude/skills/agent-team/references/ticket-task-bridge.md - Ticket-Task 橋接規則
- .claude/skills/agent-team/references/teammate-onboarding-protocol.md - 入職模板
- .claude/rules/flows/ticket-lifecycle.md - Ticket 生命週期
- .claude/rules/guides/parallel-dispatch.md - 並行派發指南

---

**Last Updated**: 2026-02-25
**Version**: 1.0.0
