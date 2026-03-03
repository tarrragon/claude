# File Type Permission Hook - 快速參考

## 功能總結

PreToolUse Hook，根據編輯檔案類型決定是否需要人工確認。

## 檔案分類

| 檔案路徑 | 行為 | 輸出 |
|---------|------|------|
| `.claude/tickets/*` | 提示確認 | stderr 訊息 + JSON |
| `docs/work-logs/*` | 提示確認 | stderr 訊息 + JSON |
| `lib/*` | 自動通過 | 無輸出 |
| `test/*` | 自動通過 | 無輸出 |
| `integration_test/*` | 自動通過 | 無輸出 |
| 其他檔案 | 自動通過 | 無輸出 |

## 提示訊息格式

編輯 Ticket/Worklog 時會看到：

```
[File Permission Guard] 提示: 正在編輯 Ticket/Worklog 檔案

檔案: {file_path}
說明: 此類檔案的修改需要人工審查確認
```

## 檔案位置

| 檔案 | 路徑 |
|------|------|
| Hook 腳本 | `.claude/hooks/file-type-permission-hook.py` |
| 完整文件 | `.claude/references/hooks/README-file-type-permission-hook.md` |
| 實作摘要 | `.claude/references/hooks/IMPLEMENTATION-SUMMARY-file-type-permission-hook.md` |
| 執行日誌 | `.claude/hook-logs/file-type-permission/` |

## 配置位置

`.claude/settings.local.json` 中的 PreToolUse 配置：

```json
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
```

## 工作流程

### 編輯 Ticket 檔案 (.claude/tickets/*)

1. 執行 Edit 工具
2. Hook 觸發
3. 識別為 Ticket 檔案
4. **stderr 輸出提示訊息**
5. 編輯執行（exit code 0）
6. 操作日誌記錄

### 編輯程式碼檔案 (lib/*, test/*, 等)

1. 執行 Edit 工具
2. Hook 觸發
3. 識別為程式碼檔案
4. **無任何輸出**（靜默通過）
5. 編輯執行
6. 操作日誌記錄

## 日誌查看

檢查 Hook 執行記錄：

```bash
tail -f .claude/hook-logs/file-type-permission/file-type-permission-*.log
```

## 測試驗證

快速驗證 Hook 功能：

```bash
# Ticket 檔案測試
echo '{"tool_name":"Edit","tool_input":{"file_path":".claude/tickets/test.md"}}' | \
  python3 .claude/hooks/file-type-permission-hook.py

# 程式碼檔案測試（應無輸出）
echo '{"tool_name":"Edit","tool_input":{"file_path":"lib/main.dart"}}' | \
  python3 .claude/hooks/file-type-permission-hook.py
```

## 常見問題

### Q: 為什麼編輯程式碼檔案沒有輸出？
A: 設計如此。程式碼檔案無需人工確認，靜默通過可避免干擾開發流程。日誌中仍然會記錄所有操作。

### Q: Ticket 檔案提示訊息在哪裡看？
A: stderr 輸出會在 Claude Code 的 UI 中顯示為提示訊息。檢查 `.claude/hook-logs/` 中的日誌確認執行。

### Q: 可以修改檔案分類嗎？
A: 需要修改 `get_file_category()` 函數中的路徑模式。檢查 README 文件了解實作細節。

## 相關資源

- 完整文件: README-file-type-permission-hook.md
- 實作摘要: IMPLEMENTATION-SUMMARY-file-type-permission-hook.md
- Hook 規範: .claude/hook-specs/
- 方法論: .claude/methodologies/hook-system-methodology.md

---

**最後更新**: 2025-01-16
**版本**: v1.0
**狀態**: 正式發佈
