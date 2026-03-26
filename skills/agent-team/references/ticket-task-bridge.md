# Ticket-Task 橋接規則

本文件定義 Agent Teams 的 Task List 與 Ticket 系統之間的橋接規則。

---

## 核心原則

| 原則 | 說明 |
|------|------|
| Ticket 是 Source of Truth | 所有工作記錄以 Ticket .md 檔案為準 |
| Task 是 ephemeral 協調層 | Agent Teams Task List 隨 session 結束消失 |
| 1:1 映射 | 每個 Task 必須關聯一個 Ticket（或子 Ticket） |
| 雙向更新 | Task 狀態變更時同步更新 Ticket |
| Complete 權限隔離 | Teammate 更新進度，PM 執行 complete |

---

## TaskCreate 規範

PM 建立 Task 時，metadata 必須包含 ticketId：

```json
{
  "title": "實作 BookSearch Domain 層",
  "description": "...",
  "metadata": {
    "ticketId": "0.31.0-W22-001.1",
    "waveId": "W22"
  }
}
```

**必填欄位**：

| 欄位 | 說明 |
|------|------|
| ticketId | 對應的 Ticket ID |
| waveId | 所屬 Wave |

---

## Teammate 必須執行的 Ticket 操作

| 時機 | Ticket 指令 | 說明 |
|------|------------|------|
| 開始工作 | `ticket track claim {ticketId}` | 若 PM 未預先認領 |
| 重要進展 | `ticket track append-log {ticketId} --section "Solution" "進展描述"` | 更新執行日誌 |
| 完成前 | `ticket track append-log {ticketId} --section "Test Results" "測試結果"` | 記錄測試結果 |
| 完成 | TaskUpdate status=completed + SendMessage 給 team-lead | 標記 Task 完成 |

### 操作範例

**Teammate 開始工作**：

```bash
# 1. 認領 Ticket
ticket track claim 0.31.0-W22-001.1

# 2. 閱讀 Ticket 了解任務
ticket track query 0.31.0-W22-001.1
```

**Teammate 更新進展**：

```bash
# 記錄解決方案進展
ticket track append-log 0.31.0-W22-001.1 --section "Solution" "完成 SearchQuery 值物件實作，包含 keyword、filter、pagination 三個屬性"
```

**Teammate 完成工作**：

```bash
# 1. 記錄測試結果
ticket track append-log 0.31.0-W22-001.1 --section "Test Results" "12 tests passed, 0 failed"

# 2. 標記 Task 完成（使用 TaskUpdate 工具）
# 3. 通知 team-lead（使用 SendMessage 工具）
```

---

## 禁止操作

| 禁止操作 | 原因 | 替代方式 |
|---------|------|---------|
| `ticket track complete` | PM 驗收後專屬操作 | TaskUpdate + SendMessage 通知 PM |
| `ticket create` | PM 專屬操作 | SendMessage 建議 PM 建立 |
| 修改 Ticket frontmatter | PM 專屬操作 | 透過 append-log 更新內容 |

---

## 狀態同步規則

### Task → Ticket 狀態對應

| Task 狀態 | Ticket 動作 | 說明 |
|----------|------------|------|
| created | 無 | PM 已預先建立 Ticket |
| in_progress | claim | Teammate 認領 |
| completed | PM 驗收後 complete | Teammate 不可自行 complete |
| blocked | release | Teammate 釋放，升級 PM |

### 一致性保證

- Teammate 開始工作前必須確認 Ticket 存在
- Teammate 完成 Task 前必須確認 Ticket 日誌已更新
- PM 在 TeamDelete 前必須確認所有 Ticket 狀態正確

---

## 相關文件

- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期
- .claude/skills/ticket/SKILL.md - Ticket 操作指南

---

**Last Updated**: 2026-02-25
**Version**: 1.0.0
