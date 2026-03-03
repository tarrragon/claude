# File Type Permission Hook - 文件索引

快速查找 file-type-permission-hook.py 相關的文件和資源。

## 核心檔案

### 1. Hook 實現

**檔案**: `file-type-permission-hook.py`
**大小**: 4.8K
**類型**: PreToolUse Hook (Python 3.11+)
**功能**: 根據編輯檔案類型決定是否需要人工確認

### 2. 文件檔案

| 檔案 | 內容 | 適用場景 |
|------|------|--------|
| [README-file-type-permission-hook.md](./README-file-type-permission-hook.md) | 完整功能文件、輸入輸出格式、測試方法 | 需要詳細了解 Hook 運作方式 |
| [QUICK-REFERENCE-file-type-permission-hook.md](./QUICK-REFERENCE-file-type-permission-hook.md) | 快速參考、檔案分類表、常見問題 | 快速查詢和常見問題解答 |
| [IMPLEMENTATION-SUMMARY-file-type-permission-hook.md](./IMPLEMENTATION-SUMMARY-file-type-permission-hook.md) | 實作摘要、技術特點、部署檢查清單 | 了解實作細節和部署狀態 |
| [INDEX-file-type-permission-hook.md](./INDEX-file-type-permission-hook.md) | 本文件 | 快速導航所有文件 |

## 快速導航

### 我想了解 Hook 是什麼

開始於: [QUICK-REFERENCE-file-type-permission-hook.md](./QUICK-REFERENCE-file-type-permission-hook.md)
- 檔案分類表
- 功能總結
- 使用流程

### 我想測試 Hook

參考: [README-file-type-permission-hook.md](./README-file-type-permission-hook.md) 的「測試驗證」章節
- 語法檢查
- 功能測試
- Debug 驗證

### 我想查看實作細節

參考: [README-file-type-permission-hook.md](./README-file-type-permission-hook.md) 的「實作細節」章節
- 核心邏輯
- 日誌位置
- 配置說明

### 我需要解決問題

1. 檢查日誌: `.claude/hook-logs/file-type-permission/`
2. 參考: [QUICK-REFERENCE-file-type-permission-hook.md](./QUICK-REFERENCE-file-type-permission-hook.md) 的「常見問題」章節

### 我想驗證部署狀態

參考: [IMPLEMENTATION-SUMMARY-file-type-permission-hook.md](./IMPLEMENTATION-SUMMARY-file-type-permission-hook.md)
- 部署檢查清單
- 測試驗證結果
- 使用指南

## 功能速查

### 檔案分類

```
.claude/tickets/*        → Ticket 檔案（需要確認）
docs/work-logs/*         → Worklog 檔案（需要確認）
lib/*                    → 程式碼檔案（靜默通過）
test/*                   → 測試檔案（靜默通過）
integration_test/*       → 整合測試（靜默通過）
其他檔案                 → 靜默通過
```

### 提示訊息格式

```
[File Permission Guard] 提示: 正在編輯 Ticket/Worklog 檔案

檔案: {file_path}
說明: 此類檔案的修改需要人工審查確認
```

### 日誌位置

```
.claude/hook-logs/file-type-permission/file-type-permission-YYYYMMDD.log
```

## 配置資訊

**位置**: `.claude/settings.local.json`

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/file-type-permission-hook.py",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

## 常用命令

### 查看日誌

```bash
tail -f .claude/hook-logs/file-type-permission/file-type-permission-*.log
```

### 測試 Hook

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":".claude/tickets/test.md"}}' | \
  python3 .claude/hooks/file-type-permission-hook.py
```

### 驗證語法

```bash
python3 -m py_compile .claude/hooks/file-type-permission-hook.py
```

## 技術規格

| 項目 | 值 |
|------|-----|
| Hook 類型 | PreToolUse |
| Matcher | Edit |
| 語言 | Python 3.11+ |
| 依賴 | 無（標準庫）|
| Timeout | 10000ms (10 秒) |
| Exit Code | 0 (總是允許) |
| 日誌格式 | 每日一檔 |

## 版本資訊

- **版本**: v1.0
- **建立日期**: 2025-01-16
- **狀態**: 完成並驗證
- **最後更新**: 2025-01-16

## 相關資源

- Hook 規範: `.claude/hook-specs/`
- 方法論: `.claude/methodologies/hook-system-methodology.md`
- 官方文件: `.claude/hook-system-reference.md`

## 需要協助？

1. **快速問題**: 檢查 [QUICK-REFERENCE-file-type-permission-hook.md](./QUICK-REFERENCE-file-type-permission-hook.md) 的 FAQ 章節

2. **技術細節**: 查看 [README-file-type-permission-hook.md](./README-file-type-permission-hook.md)

3. **實作細節**: 查看 [IMPLEMENTATION-SUMMARY-file-type-permission-hook.md](./IMPLEMENTATION-SUMMARY-file-type-permission-hook.md)

4. **查看日誌**: `.claude/hook-logs/file-type-permission/`

5. **查看原始碼**: `file-type-permission-hook.py` (包含詳細註解)

---

**最後更新**: 2025-01-16
**維護者**: Claude Code Hook System
