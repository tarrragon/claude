# IMP-040: 狀態機終態未受保護 — 純計算函式覆蓋顯式狀態

## 錯誤摘要

| 項目 | 說明 |
|------|------|
| **分類** | Implementation |
| **嚴重性** | Critical（生產環境 bug，狀態回歸） |
| **發現版本** | v0.2.0 |
| **相關 Ticket** | 0.2.0-W2-001.3 |

## 症狀

- Session 被 SubagentStop 顯式設為 `completed` 後，定時掃描 `ScanAndUpdateStatus` 或後續 JSONL 事件將其覆蓋回 `active`
- 已完成的 session 在 UI 上「復活」，使用者看到錯誤的狀態

## 根因分析

**行為模式**：`computeStatus` 函式純粹根據時間差計算狀態（elapsed < 2min → active），不檢查 session 是否已被顯式設為終態。兩個呼叫路徑都會觸發覆蓋：

1. `ScanAndUpdateStatus()` 定時掃描所有 session，呼叫 `computeStatus` → completed 被覆蓋為 active
2. `UpsertFromSessionEvent()` 收到非 session_completed 事件時呼叫 `computeStatus` → 同上

**設計缺陷**：狀態機缺少「終態不可逆」的設計約束。`completed` 應該是 absorbing state（吸收態），一旦進入就不應被任何計算函式覆蓋。

## 解決方案

在 `computeStatus` 函式開頭加入終態保護：

```go
func (r *SessionRegistry) computeStatus(session *SessionInfo, now time.Time) SessionStatus {
    if session == nil {
        return SessionStatusActive
    }
    // completed 是終態，不可被時間計算覆蓋
    if session.Status == SessionStatusCompleted {
        return SessionStatusCompleted
    }
    // ... 原有時間計算邏輯
}
```

## 防護措施

- 設計狀態機時，必須明確標註哪些狀態是終態（absorbing state）
- 所有計算/推導狀態的函式，必須在計算前檢查是否已處於終態
- 測試必須包含「終態不可逆性」測試：設定終態 → 觸發可能覆蓋的操作 → 斷言狀態不變

## 通用檢查清單（設計狀態機時）

- [ ] 列出所有終態（terminal/absorbing states）
- [ ] 每個「狀態計算」函式是否保護終態？
- [ ] 每個「狀態更新」路徑是否尊重終態？
- [ ] 是否有「終態不可逆性」測試？

## 教訓

純計算函式（如基於時間差的狀態推導）天然不具備「上下文感知」。它只知道輸入參數，不知道「這個 session 是怎麼到達當前狀態的」。終態保護必須在計算函式內部顯式實作，不能依賴呼叫者記得檢查。
