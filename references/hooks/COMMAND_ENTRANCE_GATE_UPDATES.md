# Command Entrance Gate Hook 更新總結

## 版本
- **版本**: 2.0.0（阻塞式驗證）
- **更新日期**: 2026-01-27
- **Ticket**: 0.30.1-W2-002

## 概述

將 `command-entrance-gate-hook.py` 從非阻塞式警告升級為阻塞式強制驗證。

### 主要變更

| 項目 | 舊版 (1.0.0) | 新版 (2.0.0) |
|------|-------------|------------|
| 無 Ticket 時 | exit code 0（警告） | exit code 2（阻塞） |
| Ticket 未認領 | exit code 0（警告） | exit code 2（阻塞） |
| 決策樹驗證 | 無 | 新增驗證函式 |
| 驗證層級 | 單層（Ticket 存在） | 雙層（Ticket + 決策樹） |

## 新增功能

### 1. 決策樹欄位驗證

新增 `validate_ticket_has_decision_tree()` 函式，檢查 Ticket 是否包含決策過程記錄：

```python
def validate_ticket_has_decision_tree(ticket_content: str) -> bool:
    """驗證 Ticket 是否包含決策樹欄位"""
    # 檢查 YAML frontmatter 中的 decision_tree_path 欄位
    # 或檢查內容中的「## 決策樹」、「## Decision Tree」等區段
```

**檢查規則**：
- YAML frontmatter 中的 `decision_tree_path:` 欄位
- 內容中的「## 決策樹」
- 內容中的「## Decision Tree」
- 內容中的「## 決策樹路徑」
- 內容中的「## 決策流程」

### 2. 雙層驗證機制

`check_ticket_status()` 現在執行兩層驗證：

**第一層**：Ticket 存在性和認領狀態
- 無 Ticket → 錯誤
- Ticket pending → 錯誤（需先認領）
- Ticket in_progress → 繼續第二層驗證

**第二層**：決策樹欄位驗證
- in_progress 的 Ticket 必須包含決策樹欄位
- 無決策樹 → 錯誤

### 3. 清晰的錯誤訊息

每個驗證失敗都提供明確的錯誤訊息：

```
錯誤：[具體問題]

為什麼阻止執行：
  [解釋為什麼此規則必要]

建議操作:
  1. [具體操作步驟]
  2. [替代方案]

詳見: [相關文件連結]
```

## Exit Code 規範

| Code | 狀態 | 說明 |
|------|------|------|
| 0 | SUCCESS | 命令允許執行 |
| 1 | ERROR | Hook 執行錯誤 |
| 2 | BLOCK | 開發命令驗證失敗，阻止執行 |

## Hook 輸出格式

Hook 現在在 `check_result` 中包含：

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[錯誤訊息或警告]"  // 只有驗證失敗時存在
  },
  "check_result": {
    "is_development_command": true,
    "ticket_validation_passed": true,
    "ticket_id": "0.30.1-W2-001",
    "should_block": false,
    "exit_code": "EXIT_SUCCESS",
    "timestamp": "2026-01-27T..."
  }
}
```

## 驗收條件檢查

- [x] 無 Ticket 時 exit code 為 2（阻塞）
- [x] Ticket 無決策樹欄位時 exit code 為 2（阻塞）
- [x] 新增 validate_ticket_has_decision_tree 函式
- [x] 錯誤訊息清晰說明問題和建議操作
- [x] 有完整的日誌記錄
- [x] 單元測試全部通過（7/7）

## 主要程式碼變更

### extract_ticket_status()
- **前**：返回 `(ticket_id, status)` 元組
- **後**：返回 `(ticket_id, status, content)` 元組，包含完整 Ticket 內容

### get_latest_pending_ticket()
- **前**：返回 `(ticket_id, status)` 或 `None`
- **後**：返回 `(ticket_id, status, content)` 或 `None`

### check_ticket_status()
- **前**：檢查 Ticket 存在性和認領狀態
- **後**：執行雙層驗證（存在性 + 決策樹欄位）
- 返回值從 `(has_ticket, msg, ticket_id)` 改為 `(is_valid, error_msg, ticket_id)`

### generate_hook_output()
- **前**：參數 `has_ticket`, `ticket_msg`
- **後**：參數 `is_valid`, `error_msg`
- 新增 `should_block` 和 `exit_code` 欄位到 `check_result`

### save_check_log()
- 參數名稱改為 `is_valid`（而非 `has_ticket`）
- 日誌記錄新增 `TicketValidationPassed` 欄位

### main()
- **第 8 步（決定 exit code）**：
  - 原本：總是返回 `EXIT_SUCCESS`
  - 新版：驗證失敗時返回 `EXIT_BLOCK`

## 日誌記錄

### hook-logs 目錄結構

```
.claude/hook-logs/command-entrance-gate/
├── command-entrance-gate.log          # 詳細執行日誌
└── checks-YYYYMMDD.log               # 每日檢查摘要
```

### 檢查摘要日誌格式

```
[2026-01-27T22:29:15.123456]
  Prompt: 實作新功能...
  IsDevelopmentCommand: True
  TicketValidationPassed: False
  TicketID: None
  Status: BLOCKED
```

## 單元測試

### 測試覆蓋

| 測試 | 說明 | 狀態 |
|------|------|------|
| test_is_development_command | 開發命令識別 | PASS |
| test_validate_ticket_has_decision_tree | 決策樹欄位驗證 | PASS |
| test_extract_ticket_status | Ticket 狀態提取 | PASS |
| test_generate_hook_output_blocking | 阻塊情況輸出 | PASS |
| test_generate_hook_output_allowing | 允許情況輸出 | PASS |
| test_generate_hook_output_non_dev_command | 非開發命令輸出 | PASS |
| test_blocking_error_messages | 阻塊錯誤訊息 | PASS |

### 執行測試

```bash
python3 .claude/hooks/tests/test_command_entrance_gate.py
```

## 設定與環境變數

### HOOK_DEBUG
啟用詳細日誌輸出：

```bash
export HOOK_DEBUG=true
```

### CLAUDE_PROJECT_DIR
自定義專案目錄（默認使用當前工作目錄）：

```bash
export CLAUDE_PROJECT_DIR=/path/to/project
```

## 向後相容性

本更新是 breaking change：

- **舊版行為**：非開發命令警告，但允許執行
- **新版行為**：非開發命令阻止執行

### 遷移指南

用戶應在遇到 exit code 2 時：

1. 建立對應的 Ticket（如無）
2. 認領 Ticket（如未認領）
3. 添加決策樹欄位到 Ticket
4. 重新執行命令

## 相關規則文件

- [Skip-gate 防護機制](../../rules/forbidden/skip-gate.md)
- [決策樹規則](../../rules/core/decision-tree.md)
- [Ticket 生命週期](../../rules/flows/ticket-lifecycle.md)

## 下一步

### Hook 系統升級計畫

- [x] Level 2 驗證（命令入口防護）- 本 Ticket 完成
- [ ] Level 3 驗證（階段完成防護）- 未來版本
- [ ] Hook 系統儀表板 - 未來版本

### 相關 Ticket

- [0.30.1-W2-001] Phase 完成層驗證 Hook（開發中）
- [0.30.1-W2-003] 決策樹驗證優化（計畫中）
- [0.30.1-W2-004] Hook 系統監控儀表板（計畫中）

## 故障排除

### Hook 執行失敗（exit code 1）

檢查日誌：

```bash
cat .claude/hook-logs/command-entrance-gate/command-entrance-gate.log
```

常見問題：
- JSON 格式錯誤：檢查輸入格式
- 檔案權限問題：確保日誌目錄可寫
- 環境變數問題：檢查 CLAUDE_PROJECT_DIR 設定

### Ticket 驗證失敗（exit code 2）

檢查 Hook 輸出中的 `additionalContext` 欄位，按建議操作執行。

---

**更新者**：parsley-flutter-developer
**審核狀態**：待審核
**文件狀態**：完成
