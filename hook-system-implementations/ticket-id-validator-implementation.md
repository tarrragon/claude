# Ticket ID Validator Hook 實作文件

## Hook 基本資訊

| 項目 | 內容 |
|------|------|
| **Hook 名稱** | Ticket ID Validator Hook |
| **檔案位置** | `.claude/hooks/ticket-id-validator-hook.py` |
| **Hook 類型** | PostToolUse（非阻塞） |
| **監控工具** | Write |
| **監控路徑** | `docs/work-logs/*/tickets/*.md` 或 `.claude/tickets/*.md` |
| **版本** | 1.0.0 |
| **建立日期** | 2026-01-30 |

---

## 設計目標

驗證 Ticket ID 格式是否符合規範，提供即時的驗證反饋和警告。

### 核心功能

1. **格式驗證** - 確認 Ticket ID 符合正規表達式
2. **版本檢查** - 驗證 Ticket ID 版本與檔案所在目錄版本一致
3. **波次驗證** - 確認 wave 號在合理範圍（1-10）
4. **日誌記錄** - 記錄所有檢查結果

---

## 技術設計

### Ticket ID 正規表達式

```regex
^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)$
```

**格式說明**:
- 第 1 組: 版本號 `(\d+\.\d+\.\d+)` - 如 `0.31.0`
- 字面: `-W`
- 第 2 組: 波次號 `(\d+)` - 如 `5`
- 字面: `-`
- 第 3 組: 序號 `(\d+(?:\.\d+)*)` - 如 `001` 或 `001.1.2`

**支援的格式**:
- 根任務: `0.31.0-W5-001`
- 一層子任務: `0.31.0-W5-001.1`
- 多層子任務: `0.31.0-W5-001.2.3.4`

### 驗證流程

```
接收 Write 工具事件
    |
    v
解析 JSON 輸入
    |
    v
判斷是否為 Ticket 檔案?
    |
    +-- 否 --> 跳過檢查 (return 0)
    |
    +-- 是 --> 提取 Ticket ID
        |
        v
        ID 提取成功?
        |
        +-- 否 --> 產生警告 (return 0)
        |
        +-- 是 --> 驗證格式
            |
            v
            格式正確?
            |
            +-- 否 --> 產生警告 (return 0)
            |
            +-- 是 --> 驗證波次範圍
                |
                v
                波次有效?
                |
                +-- 否 --> 產生警告 (return 0)
                |
                +-- 是 --> 驗證版本一致
                    |
                    v
                    版本一致?
                    |
                    +-- 是 --> 驗證通過 (return 0)
                    +-- 否 --> 產生警告 (return 0)
```

---

## 實作細節

### 環境變數

| 變數 | 用途 | 預設值 |
|------|------|--------|
| `CLAUDE_PROJECT_DIR` | 專案根目錄 | 當前工作目錄 |
| `HOOK_DEBUG` | 啟用詳細日誌 | false |

### 日誌系統

**日誌目錄**: `.claude/hook-logs/ticket-id-validator/`

**日誌檔案**:
1. `ticket-id-validator.log` - 實時執行日誌（DEBUG 級別）
2. `checks-{YYYYMMDD}.log` - 每日檢查摘要

**日誌格式**:
```
[2026-01-30 22:51:44,662] INFO - 訊息
[2026-01-30 22:51:44,662] WARNING - 警告
[2026-01-30 22:51:44,662] ERROR - 錯誤
```

### 依賴項目

無外部依賴（只使用標準庫）:
- `sys`, `json`, `logging`, `re`, `pathlib`, `datetime`, `typing`

---

## Hook 輸出規範

### 成功情況（格式正確）

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse"
  },
  "check_result": {
    "is_valid": true,
    "file_path": "docs/work-logs/v0.31.0/tickets/0.31.0-W5-001.md",
    "ticket_id": "0.31.0-W5-001",
    "warning_message": null,
    "timestamp": "2026-01-30T22:51:44.167856"
  }
}
```

### 警告情況（格式有誤）

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Ticket ID 驗證警告\n\nTicket ID 版本與目錄版本不一致\n...\n\n詳細日誌: .claude/hook-logs/ticket-id-validator/"
  },
  "check_result": {
    "is_valid": false,
    "file_path": "docs/work-logs/v0.31.0/tickets/0.30.0-W5-001.md",
    "ticket_id": "0.30.0-W5-001",
    "warning_message": "Ticket ID 版本與目錄版本不一致...",
    "timestamp": "2026-01-30T22:51:41.230440"
  }
}
```

### 跳過情況（非 Ticket 檔案）

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse"
  },
  "check_result": {
    "is_valid": true,
    "file_path": "lib/presentation/widget.dart",
    "ticket_id": null,
    "warning_message": null,
    "timestamp": "2026-01-30T22:51:50.123456"
  }
}
```

---

## 配置方式

### settings.json 中的註冊

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/ticket-id-validator-hook.py"
          }
        ]
      }
    ]
  }
}
```

### 配置檢查清單

- [x] 路徑使用相對路徑（`.claude/hooks/...`）
- [x] 檔案有執行權限（`chmod +x`）
- [x] 檔案有正確的 shebang（`#!/usr/bin/env -S uv run --quiet --script`）
- [x] JSON 語法有效
- [x] 在 PostToolUse → Write 區段中

---

## 測試驗證結果

### 測試案例

| 案例 | 輸入 | 預期結果 | 實際結果 | 通過 |
|------|------|---------|---------|------|
| 有效 ID | `0.31.0-W5-001` | 通過 | 通過 | ✓ |
| 子任務 | `0.31.0-W5-001.2.1` | 通過 | 通過 | ✓ |
| 波次超出 | `0.31.0-W99-001` | 警告 | 警告 | ✓ |
| 版本不一致 | 目錄 v0.31.0, ID 0.30.0 | 警告 | 警告 | ✓ |
| 非 Ticket 檔案 | `lib/widget.dart` | 跳過 | 跳過 | ✓ |

### 質量指標

- **語法檢查**: ✓ 通過
- **日誌系統**: ✓ 正常
- **JSON 輸出**: ✓ 有效
- **錯誤處理**: ✓ 完整
- **文件完整性**: ✓ 詳細

---

## 使用場景

### 場景 1: Ticket 建立時

開發者建立新 Ticket 檔案時，Hook 會自動驗證 ID 格式。

**流程**:
1. 使用 Write 工具建立 `0.31.0-W5-001.md`
2. Hook 自動檢查格式
3. 如有問題，Hook 輸出警告訊息
4. 開發者根據建議修正

### 場景 2: Ticket 編輯時

修改 Ticket 檔案時，Hook 會再次驗證。

### 場景 3: Ticket 遷移時

將 Ticket 從一個版本目錄移到另一個時，版本一致性檢查會發出警告。

---

## 常見問題

### Q1: 波次號的合理範圍是多少？

**A**: 1-10。這是為了防止不合理的波次號。如果需要超過 10 波，建議重新規劃版本。

### Q2: Hook 是否會阻止 Ticket 建立？

**A**: 否。Hook 是 PostToolUse 型別，不阻塞。它只提供警告訊息。

### Q3: 子任務 ID 可以有多少層級？

**A**: 理論上無限制。正規表達式支援 `(\d+(?:\.\d+)*)` 格式。

### Q4: 如何關閉 Hook？

**A**: 在 settings.json 中移除相應的 Hook 配置項即可。

---

## 未來改進

| 改進項 | 說明 | 優先級 |
|-------|------|--------|
| ID 碰撞檢測 | 檢測是否已存在同名 Ticket | P2 |
| 自動修復建議 | 提供自動修復選項 | P2 |
| 黑名單機制 | 支援特定版本的 Ticket ID 黑名單 | P3 |
| 統計報告 | 生成每日驗證統計報告 | P3 |

---

## 相關文件

- **Hook 實作**: `.claude/hooks/ticket-id-validator-hook.py`
- **配置檔案**: `.claude/settings.json`
- **測試報告**: `docs/work-logs/v0.31.0/tickets/0.31.0-W5-001-test-report.md`
- **日誌目錄**: `.claude/hook-logs/ticket-id-validator/`

---

## 提交資訊

- **Ticket ID**: 0.31.0-W5-001
- **實作時間**: 2026-01-30 22:50-22:51
- **版本**: 1.0.0
- **狀態**: 完成並通過所有測試

---

**Last Updated**: 2026-01-30
**Version**: 1.0.0
**Status**: ✓ Production Ready
