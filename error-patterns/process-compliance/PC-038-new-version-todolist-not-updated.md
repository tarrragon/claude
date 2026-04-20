<!-- 注意：本文件禁止使用 emoji（交接文件規範） -->

# PC-038: 新版本開始時未同步更新 todolist.yaml

**分類**: process-compliance
**嚴重度**: 高
**首次發現**: 2026-04-05
**相關版本**: v0.17.2

---

## 症狀

- `ticket track summary` 顯示錯誤的活躍版本（v0.18.0 而非 v0.17.2）
- `/ticket` 無子命令時列出的待辦 Ticket 全部來自錯誤版本
- 用戶需手動指正才發現版本偵測錯誤

## 根因

1. v0.17.2 開始開發時（建立 worklog、建立 W1 Ticket、完成 W1 規格），**未同步在 `docs/todolist.yaml` 新增 v0.17.2 條目**
2. `todolist.yaml` 的版本偵測邏輯取第一個 `status: active` 的版本（v0.18.0）
3. v0.18.0/v0.18.1/v0.19.0 仍標記為 `active`，但其描述和里程碑定義已與 CLAUDE.md 不一致

## 行為模式分析

這是「worklog 和 todolist 雙軌制」的同步遺漏：
- 開發者建立了 worklog 目錄和 Ticket 檔案（正確）
- 但忘記在 todolist.yaml 中登記版本條目（遺漏）
- Ticket 系統依賴 todolist.yaml 作為版本偵測的唯一來源，導致偵測失敗

## 解決方案

1. 在 `todolist.yaml` 補上 v0.17.2 條目，標記為 `active`
2. 將尚未開始的 v0.18.0+ 版本從 `active` 改為 `planned`
3. 對齊 CLAUDE.md 里程碑定義

## 預防措施

### 流程檢查

**新版本啟動時的必要步驟**（按順序）：

| 步驟 | 動作 | 驗證 |
|------|------|------|
| 1 | 更新 `docs/todolist.yaml`：新增版本條目，設為 `active` | `ticket track summary` 顯示正確版本 |
| 2 | 建立 worklog 目錄和主工作日誌 | 目錄存在 |
| 3 | 建立 W1 Ticket | Ticket 檔案存在 |

### Hook 建議

考慮在 `doc-sync-check-hook.py`（SessionStart）中加入檢查：
- 掃描 `docs/work-logs/` 中有 worklog 但在 `todolist.yaml` 中不存在的版本
- 掃描 worklog 中有 in_progress/pending Ticket 但在 todolist.yaml 中標記為 completed 的版本

## 影響範圍

- Ticket 系統所有依賴版本偵測的命令（summary/list/query 等）
- `/ticket` 裸指令的待辦列表
- 任何自動化流程依賴 `get_current_version()` 的場景

---

**Last Updated**: 2026-04-05
