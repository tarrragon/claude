# L10n 同步驗證 Hook

## 基本資訊

- Hook 名稱: `l10n-sync-verification-hook.py`
- Hook 類型: PostToolUse
- 版本: v1.0
- 建立日期: 2026-01-15
- 觸發事件: Edit (編輯 ARB 檔案後)
- Timeout: 30 秒 (30000ms)

## 目的

在 Flutter 應用程式開發流程中，當開發者修改國際化 ARB (Application Resource Bundle) 檔案後，必須執行 `flutter gen-l10n` 命令重新生成對應的 Dart 本地化檔案。

此 Hook 的目的是自動偵測 ARB 檔案的修改，並驗證對應的生成檔案是否已更新。若未同步，會提供清楚的警告和修復指引。

## 觸發條件

- 事件: PostToolUse (檔案編輯後)
- 目標檔案: `lib/l10n/*.arb`
- 檢查範圍: 所有以 `app_` 開頭的 ARB 檔案

## 工作流程

```
使用者編輯 ARB 檔案 (Edit Tool)
          ↓
    Hook 自動觸發
          ↓
    是否為 ARB 檔案?
    ├─ 否 → 跳過檢查，正常結束
    └─ 是 → 執行同步驗證
          ↓
    ARB 和生成檔案同步?
    ├─ 是 → 允許繼續 (exit 0)
    ├─ 否 (ARB 新於生成檔案) → 警告使用者，提示修復步驟 (exit 0)
    └─ 否 (生成檔案缺失) → 錯誤，阻塊操作 (exit 2)
```

## 檢查邏輯

### 步驟 1: 識別 ARB 檔案

檢查編輯的檔案是否為 ARB 檔案:
- 檔案擴展名為 `.arb`
- 檔案路徑包含 `l10n` 目錄
- 排除備份檔案 (`.bak`)

### 步驟 2: 掃描所有 ARB 檔案

列出 `lib/l10n/` 目錄下的所有 ARB 檔案，並對每個檔案檢查對應的生成 Dart 檔案。

**命名規則**:
- `app_en.arb` → `lib/l10n/generated/app_localizations_en.dart`
- `app_zh_TW.arb` → `lib/l10n/generated/app_localizations_zh.dart`
- `app_zh_CN.arb` → `lib/l10n/generated/app_localizations_zh.dart`
- `app.arb` (主檔案) → `lib/l10n/generated/app_localizations.dart`

### 步驟 3: 比較修改時間 (mtime)

對每個 ARB 檔案和對應的生成檔案進行比較:

```
情況 1: 生成檔案不存在
  狀態: missing
  決策: error (exit code 2)
  原因: L10n 生成流程未執行

情況 2: ARB mtime > 生成檔案 mtime
  狀態: out_of_sync
  決策: warn (exit code 0)
  原因: ARB 檔案已修改，生成檔案過時

情況 3: ARB mtime <= 生成檔案 mtime
  狀態: synced
  決策: allow (exit code 0)
  原因: 已同步，無需重新生成
```

## 輸入格式

Hook 從 stdin 接收 JSON 格式的輸入:

```json
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "lib/l10n/app_zh_TW.arb",
    "content": "..."
  },
  "session_id": "abc123"
}
```

## 輸出格式

### 成功（同步）

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "decision": "allow"
  }
}
```

Exit code: 0

### 警告（不同步）

stderr:
```
⚠️  警告: ARB 檔案未同步

以下 ARB 檔案新於其對應的生成檔案:
  - app_zh_TW.arb (修改: 2026-01-15T10:30:00)
    → app_localizations_zh.dart (生成: 2026-01-15T09:00:00)

📋 修復步驟:
1. 執行命令: flutter gen-l10n
2. 驗證生成成功: flutter analyze
3. 重新執行編輯操作或提交
```

stdout:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "decision": "allow",
    "reason": "ARB 檔案已修改，請執行 flutter gen-l10n 更新生成檔案"
  }
}
```

Exit code: 0

### 錯誤（缺少生成檔案）

stderr:
```
❌ 錯誤: L10n 生成檔案缺失

以下生成檔案不存在:
  - app_localizations_zh.dart
  - app_localizations_en.dart

📋 修復步驟:
1. 執行命令: flutter gen-l10n
2. 驗證生成成功: flutter analyze
3. 重新執行編輯操作或提交
```

stdout:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "decision": "block"
  }
}
```

Exit code: 2

## 可觀察性

### 日誌位置

所有執行日誌存儲在: `.claude/hook-logs/l10n-sync/`

### 日誌格式

檔案名: `verification-YYYYMMDD.log`

日誌條目:
```json
{
  "timestamp": "2026-01-15T10:30:00.123456",
  "event_type": "l10n_check",
  "details": {
    "file_edited": "lib/l10n/app_zh_TW.arb",
    "is_synced": false,
    "decision": "warn",
    "details": {
      "arb_files_checked": ["app_en.arb", "app_zh_TW.arb"],
      "sync_status": {
        "app_en.arb": "synced",
        "app_zh_TW.arb": "out_of_sync"
      },
      "out_of_sync_files": [
        {
          "arb_file": "app_zh_TW.arb",
          "arb_mtime": "2026-01-15T10:30:00",
          "dart_file": "app_localizations_zh.dart",
          "dart_mtime": "2026-01-15T09:00:00"
        }
      ],
      "missing_generated_files": []
    }
  }
}
```

## 技術實現

### 語言選擇: Python UV 單檔模式

使用 Python 而非 Bash 的原因:
1. JSON 處理: 原生支援 JSON 解析和生成
2. 路徑操作: pathlib 提供簡潔的檔案系統操作
3. 時間比較: datetime 模組便於 mtime 比較
4. 錯誤處理: 更好的異常處理機制
5. 可維護性: 複雜邏輯用 Python 更清晰

### 依賴項目

- Python 3.11+
- 標準庫: json, os, sys, pathlib, datetime

無需外部依賴，確保高度可移植性。

### 核心函式

| 函式 | 用途 |
|------|------|
| `get_project_root()` | 取得專案根目錄 |
| `setup_log_directory()` | 建立日誌目錄 |
| `read_stdin_json()` | 讀取 stdin JSON 輸入 |
| `is_arb_file()` | 檢查是否為 ARB 檔案 |
| `get_arb_files()` | 掃描所有 ARB 檔案 |
| `get_generated_dart_file()` | 取得對應的生成 Dart 檔案 |
| `check_l10n_sync()` | 執行同步驗證 |
| `generate_error_message()` | 生成錯誤訊息 |

## 錯誤處理

### 無效 JSON 輸入

如果 stdin 無法解析為 JSON，Hook 會:
1. 輸出錯誤訊息到 stderr
2. 以 exit code 1 終止

### 專案根目錄無法定位

Hook 優先使用環境變數 `$CLAUDE_PROJECT_DIR`，如果未設定則使用當前工作目錄。

## 使用範例

### 場景 1: 編輯 ARB 檔案但未執行 gen-l10n

```bash
# 編輯 ARB 檔案
# Hook 會自動觸發，檢查發現 ARB 新於生成檔案

# 輸出警告訊息，提示需要執行:
flutter gen-l10n

# 執行命令後重新編輯，Hook 不會再提示
```

### 場景 2: 編輯非 ARB 檔案

```bash
# 編輯 Dart 檔案 (e.g., lib/widgets/home.dart)
# Hook 自動識別非 ARB 檔案，跳過檢查，無輸出

# 編輯正常進行
```

### 場景 3: ARB 生成檔案缺失

```bash
# 編輯 ARB 檔案
# Hook 檢查發現生成檔案不存在（新設定或清理後）

# 輸出錯誤訊息，阻塊編輯
# 需要執行:
flutter gen-l10n

# 完成後重新編輯
```

## 設定檢查清單

設定檔: `.claude/settings.local.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/l10n-sync-verification-hook.py",
            "timeout": 30000
          }
        ]
      }
    ]
  }
}
```

檢查清單:
- [x] Hook 檔案位置: `.claude/hooks/l10n-sync-verification-hook.py`
- [x] Hook 檔案可執行: `chmod +x` 已設定
- [x] Hook 類型: PostToolUse (Edit 工具)
- [x] Matcher: 所有 Edit 操作都會觸發
- [x] Timeout: 30 秒 (合理範圍，簡單檢查)
- [x] 權限: 已添加到 settings.local.json 的 allow 列表

## 測試驗證

### 測試 1: 非 ARB 檔案

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"lib/widgets/home.dart"}}' | \
  python3 .claude/hooks/l10n-sync-verification-hook.py

# 預期: exit code 0, 無輸出
```

### 測試 2: ARB 檔案（已同步）

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"lib/l10n/app_en.arb"}}' | \
  python3 .claude/hooks/l10n-sync-verification-hook.py

# 預期: exit code 0, 允許繼續
# JSON 輸出: {"hookSpecificOutput": {"decision": "allow"}}
```

### 測試 3: ARB 檔案（未同步）

```bash
# 修改 ARB 檔案的 mtime (使其新於生成檔案)
touch lib/l10n/app_zh_TW.arb

# 執行 Hook
echo '{"tool_name":"Edit","tool_input":{"file_path":"lib/l10n/app_zh_TW.arb"}}' | \
  python3 .claude/hooks/l10n-sync-verification-hook.py

# 預期: exit code 0, 警告訊息
# stderr: 包含修復步驟
# JSON 輸出: {"hookSpecificOutput": {"decision": "allow", "reason": "..."}}
```

### 測試 4: 語法檢查

```bash
python3 -m py_compile .claude/hooks/l10n-sync-verification-hook.py

# 預期: 無錯誤
```

## 故障排除

### Hook 未執行

檢查清單:
1. 確認編輯的檔案是 `.arb` 檔案
2. 確認檔案路徑包含 `l10n` 目錄
3. 查看 debug 日誌: `.claude/hook-logs/l10n-sync/`
4. 驗證配置: `settings.local.json` 是否正確配置 PostToolUse Hook

### Hook 執行但未偵測到變更

原因: 生成檔案比 ARB 檔案更新

解決:
1. 確認 `flutter gen-l10n` 已執行
2. 檢查檔案系統時間同步
3. 清理並重新生成: `flutter clean && flutter gen-l10n`

### 生成檔案路徑識別錯誤

檢查項目:
1. ARB 檔案命名是否符合 `app_*.arb` 格式
2. 生成檔案是否在 `lib/l10n/generated/` 目錄
3. 查看日誌確認識別的對應關係

## 相關文件

- Hook 設定: `.claude/settings.local.json`
- Hook 邏輯: `.claude/hooks/l10n-sync-verification-hook.py`
- 日誌目錄: `.claude/hook-logs/l10n-sync/`
- Ticket: `docs/work-logs/v0.27.0/tickets/0.27.0-TD-001.md`

## 相關命令

```bash
# 手動執行 L10n 生成
flutter gen-l10n

# 檢查國際化是否正確
flutter analyze

# 檢查生成檔案
ls -la lib/l10n/generated/

# 查看 Hook 日誌
ls -la .claude/hook-logs/l10n-sync/
tail -f .claude/hook-logs/l10n-sync/verification-*.log

# 檢查 Hook 配置
cat .claude/settings.local.json | grep -A 20 "PostToolUse"
```

## 設計決策

### 為什麼使用 PostToolUse 而非 PreCommit?

- PostToolUse: 在編輯後立即提示，讓開發者快速執行 gen-l10n
- PreCommit: 在提交前檢查（太晚，已寫入編輯器）

選擇 PostToolUse 的優勢:
1. 及時反饋: 編輯後立即提示
2. 快速修正: 無需等到提交時
3. 更好體驗: 在編輯流程中整合檢查

### 為什麼使用警告而非錯誤阻塊?

- 警告 (exit 0): 允許編輯繼續，但提示需要執行 gen-l10n
- 錯誤 (exit 2): 完全阻塊編輯

決策理由:
1. ARB 編輯本身不是違規（只是提醒）
2. 開發者可能需要多次編輯再執行 gen-l10n
3. 只在生成檔案缺失時才真正阻塊（exit 2）

## 未來改進方向

1. 自動執行 `flutter gen-l10n` （需要額外權限）
2. 多語言支援: 語言碼對應規則優化
3. 效能優化: 只檢查編輯的 ARB 語言版本
4. 分析報告: 生成 L10n 同步狀態報告
5. 整合 CI/CD: 在提交前執行自動檢查
