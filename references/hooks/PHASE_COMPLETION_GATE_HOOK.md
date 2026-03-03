# Phase Completion Gate Hook 設計文件

## 基本資訊

- **Hook 名稱**: phase-completion-gate-hook.py
- **Hook 類型**: PostToolUse
- **實作語言**: Python 3.11+（UV 單檔模式）
- **版本**: v1.0
- **建立日期**: 2026-01-23

---

## 目的

確保 Phase 完成時的報告完整性和上報到 worklog。解決缺口 2 問題：Phase 完成缺少上報驗證，報告可能只在對話中呈現。

**核心目標**：
- 監控 Phase 3b 和 Phase 4 完成報告的寫入
- 驗證報告內容的完整性
- 提醒開發者補充缺少的內容
- 記錄驗證結果便於追蹤

---

## 觸發時機

### Hook 事件
- **Hook 類型**: PostToolUse
- **觸發工具**: Write、Edit

### 觸發條件
1. 工具執行為 Write 或 Edit
2. 目標檔案位於 `docs/work-logs/` 目錄下
3. Hook 自動執行，無需額外配置

---

## 輸入格式

### Write 工具輸入
```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "docs/work-logs/v0.30.0/0.30.0-W2-003.md",
    "content": "# Phase 3b 實作執行完成\n\n## Problem Analysis\n\n...\n\n## Solution\n\n...\n\n## Test Results\n\n..."
  }
}
```

### Edit 工具輸入
```json
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "docs/work-logs/v0.30.0/0.30.0-W2-003.md",
    "old_string": "<!-- To be filled -->",
    "new_string": "實際內容..."
  }
}
```

---

## 輸出格式

### 成功情況（完整報告）
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse"
  }
}
```

### 警告情況（缺少內容）
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "警告：Phase 完成報告缺少必要內容\n\n缺少的部分:\n- Problem Analysis 實際內容\n- Solution 實際內容\n\n建議:\n1. 補充上述缺少的部分\n2. 確保提供完整的問題分析、解決方案和測試結果\n3. 執行 /ticket track complete {ticket-id} 標記 Ticket 完成\n\n詳見: .claude/rules/flows/tdd-flow.md"
  }
}
```

---

## Exit Code 說明

| Code | 說明 | 觸發情況 |
|------|------|---------|
| 0 | 成功 | Hook 正常執行完成 |
| 1 | 執行錯誤 | JSON 解析失敗或其他異常 |
| 2 | 阻塊錯誤 | 預留（目前不使用） |

---

## 核心邏輯

### 執行流程

```
接收 PostToolUse Hook
    |
    v
驗證輸入格式
    |
    v
檢查是否為 worklog 寫入操作
    |
    +-- 否 --> 直接返回成功
    |
    +-- 是 --> 進入驗證流程
            |
            v
        識別是否為 Phase 完成報告
            |
            +-- 否 --> 返回成功（無警告）
            |
            +-- 是 --> 進入完整性檢查
                    |
                    v
                檢查 worklog 結構
                    |
                    v
                檢查是否包含必要部分
                    - Problem Analysis
                    - Solution
                    - Test Results
                    |
                    v
                檢查是否包含實際內容
                    |
                    +-- 完整 --> 返回成功
                    |
                    +-- 缺少 --> 返回警告 + 列出缺少項目
                    |
                    v
                儲存驗證報告
```

---

## 功能細節

### 1. worklog 檔案識別

**匹配模式**：
- `docs/work-logs/v[\d.]+` - 版本目錄下的檔案
- `docs/work-logs/` - worklog 根目錄檔案

### 2. Phase 完成報告識別

**識別關鍵字**（優先順序）：
1. 檔案名稱中的關鍵字
2. 檔案內容中的關鍵字
3. 標題模式匹配

**關鍵字清單**：
- Phase 3b / Phase 4
- 實作執行完成
- 重構優化完成
- 改善報告
- 評估報告

### 3. worklog 完整性檢查

**必要部分**：
```markdown
## Problem Analysis
## Solution
## Test Results
```

**檢查內容**：
1. 部分是否存在
2. 部分是否有實際內容（非 TODO 佔位符）

**認定為有實際內容的條件**：
- 不僅包含 `<!-- To be filled by executing agent -->` 註解
- 包含超過註解的實際文本

---

## 可觀察性設計

### 日誌位置
- **日誌目錄**: `.claude/hook-logs/phase-completion-gate/`
- **主日誌**: `phase-completion-gate.log`
- **報告檔案**: `completion-report-{timestamp}.json`

### 日誌級別

| 級別 | 說明 | 範例 |
|------|------|------|
| INFO | 重要事件 | 識別到 worklog 操作、Phase 完成報告 |
| DEBUG | 詳細信息 | JSON 輸入、檔案路徑判斷 |
| WARNING | 警告 | 缺少內容、檔案讀取失敗 |
| ERROR | 錯誤 | JSON 解析失敗、異常 |

### 報告檔案格式

```json
{
  "timestamp": "2026-01-23T19:59:38.884588",
  "file_path": "docs/work-logs/v0.30.0/0.30.0-W2-003.md",
  "is_phase_completion": true,
  "phase_type": "Phase 3b",
  "worklog_complete": true,
  "missing_items": [],
  "ticket_msg": null
}
```

---

## 測試驗證

### 已通過的測試

| 測試案例 | 狀態 | 說明 |
|---------|------|------|
| Phase 3b 完整報告 | 通過 | Hook 正確識別完整的 Phase 完成報告 |
| Phase 4 不完整報告 | 通過 | Hook 正確偵測缺少的內容並輸出警告 |
| 一般筆記檔案 | 通過 | Hook 正確識別非 Phase 完成報告 |
| 非 worklog 檔案 | 通過 | Hook 正確忽略非 worklog 檔案操作 |

### 測試命令

```bash
# 語法檢查
python3 -m py_compile /Users/tarragon/Projects/book_overview_app/.claude/hooks/phase-completion-gate-hook.py

# 手動執行測試
export HOOK_DEBUG=true
cat /tmp/test-input.json | python3 /Users/tarragon/Projects/book_overview_app/.claude/hooks/phase-completion-gate-hook.py

# 查看日誌
tail -50 /Users/tarragon/Projects/book_overview_app/.claude/hook-logs/phase-completion-gate/phase-completion-gate.log

# 查看報告
ls -lt /Users/tarragon/Projects/book_overview_app/.claude/hook-logs/phase-completion-gate/completion-report-*.json
```

---

## 已知限制

### 1. Ticket 完成狀態驗證
**問題**：無法直接執行或查詢 `/ticket track complete` 的執行狀態
**當前方案**：輸出提醒訊息，建議用戶檢查
**未來改善**：建立 Ticket 狀態查詢 API

### 2. Edit 工具檔案讀取
**問題**：Edit 工具只包含修改內容，需要讀取整個檔案進行驗證
**當前方案**：嘗試直接讀取檔案（可能存在並發讀寫問題）
**未來改善**：透過工具輸出提供檔案完整內容

### 3. 執行時序驗證
**問題**：無法驗證 worklog 更新和 /ticket track complete 的執行順序
**當前方案**：記錄時間戳記供後期分析
**未來改善**：建立執行順序追蹤機制

---

## 配置說明

### 環境變數

| 變數 | 說明 | 預設值 | 範例 |
|------|------|--------|------|
| `CLAUDE_PROJECT_DIR` | 專案根目錄 | 當前目錄 | `/path/to/project` |
| `HOOK_DEBUG` | 啟用詳細日誌 | false | `true` / `false` |

### 預設行為

- Hook 自動監控所有 Write/Edit 操作到 `docs/work-logs/` 目錄
- 自動識別 Phase 完成報告
- 自動驗證 worklog 完整性
- 自動儲存驗證報告

---

## 相關文件

- [TDD 流程](./../rules/flows/tdd-flow.md) - 完整 TDD 流程說明
- @.claude/agents/cinnamon-refactor-owl.md - Phase 4 執行指南
- [五重文件系統](./../rules/core/document-system.md) - 文件系統規則
- [Ticket 0.30.0-W2-004](./../../../docs/work-logs/v0.30.0/tickets/0.30.0-W2-004.md) - 原始 Ticket

---

## 維護清單

- [x] Hook 檔案建立
- [x] 語法檢查通過
- [x] 基本功能測試通過
- [x] 日誌記錄完成
- [x] 報告生成完成
- [x] 設計文件撰寫完成
- [ ] 整合到 settings.local.json（待後續）
- [ ] 生產環境部署（待後續）

---

**Last Updated**: 2026-01-23
**Version**: 1.0
**Status**: Ready for Integration

