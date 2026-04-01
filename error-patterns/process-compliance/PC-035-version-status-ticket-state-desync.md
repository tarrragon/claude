# PC-035: 版本 status=completed 但仍有 pending tickets 導致 CLI 篩選失敗

## 錯誤症狀

- `ticket track list --wave N --status pending` 回傳空結果，但實際有 pending tickets
- PM 誤判「Wave 全部完成」，跳過待處理任務
- 只有加上 `--version X.Y.Z` 明確指定版本時才能正確查詢

## 根因分析

兩個因素交互作用：

1. **版本狀態不一致**：todolist.yaml 中版本被標記為 `completed`，但該版本仍有 pending tickets（例如多視角審查後追加的 Ticket）
2. **CLI 版本偵測邏輯**：`get_current_version()` 取 todolist.yaml 第一個 `status=active` 的版本，導致 `--wave` 篩選在錯誤的版本目錄下搜尋

## 觸發場景

- 版本收尾時標記 completed，之後又透過審查/分析追加新 tickets
- 多版本 active 並行開發時，目標版本不是第一個 active 版本

## 解決方案

### 已實施修正（W5-009）

1. **todolist.yaml**：將版本 status 改回 `active`
2. **track_query.py**：`execute_list` 新增跨版本搜尋 — 當 `--wave` 指定但未指定 `--version` 時，遍歷所有 active 版本搜尋匹配的 Wave

### 建議的防護措施

1. **ticket create 時自動檢查**：若目標版本 `status=completed`，自動改回 `active` 並輸出警告
2. **version-release 收尾時驗證**：標記版本 completed 前，確認該版本無 pending/in_progress tickets
3. **定期健康檢查 Hook**：SessionStart 時掃描 completed 版本是否存在非完成狀態的 tickets

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| CLI 修復 | 跨版本搜尋邏輯（W5-009） | 已實施 |
| 自動恢復 | ticket create 偵測 completed 版本自動改回 active | 待建 Ticket |
| 預防檢查 | version-release 標記前驗證 pending tickets | 待建 Ticket |

## 相關 Ticket

- 0.16.3-W5-009：修復 ticket track list --wave 跨版本搜尋失敗

## 教訓

版本的 `status` 欄位和 ticket 的實際狀態是兩個獨立的事實來源。當兩者不一致時，CLI 會基於錯誤的版本上下文運作。任何修改版本狀態的操作都應驗證 ticket 實際狀態。
