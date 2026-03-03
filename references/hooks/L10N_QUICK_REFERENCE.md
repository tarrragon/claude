# L10n 同步驗證 Hook - 快速參考

## 一句話說明

當編輯 `lib/l10n/` 下的 ARB 檔案後，Hook 自動檢查是否需要執行 `flutter gen-l10n` 生成對應的 Dart 本地化檔案。

## 使用流程

```
編輯 ARB 檔案
    ↓
Hook 自動觸發
    ↓
檢查同步狀態
    ├─ 已同步: ✅ 允許繼續
    ├─ 不同步: ⚠️  警告 + 修復指引
    └─ 缺失: ❌ 錯誤 + 修復步驟
```

## 修復步驟（3 步）

如果收到警告或錯誤提示:

```bash
# 1. 執行 L10n 生成
flutter gen-l10n

# 2. 驗證生成成功
flutter analyze

# 3. 重新編輯或提交
# (正常使用流程)
```

## 配置位置

- Hook 實作: `.claude/hooks/l10n-sync-verification-hook.py`
- 配置檔案: `.claude/settings.local.json` (PostToolUse Hook)
- 日誌目錄: `.claude/hook-logs/l10n-sync/`

## 觸發條件

- 工具: Edit (編輯工具)
- 檔案: 任何 `.arb` 檔案在 `lib/l10n/` 目錄
- 自動執行: 無需手動操作

## 檢查邏輯

| 狀態 | 定義 | 決策 | 行為 |
|------|------|------|------|
| 同步 | ARB mtime <= 生成檔案 mtime | allow | ✅ 允許繼續 |
| 不同步 | ARB mtime > 生成檔案 mtime | warn | ⚠️  警告，允許繼續 |
| 缺失 | 生成檔案不存在 | error | ❌ 阻塊操作 |

## 常見情況

### 情況 1: 編輯 ARB 檔案

```bash
# 編輯 app_zh_TW.arb
# Hook 自動觸發檢查...

# 如果出現警告: 執行 flutter gen-l10n
# 如果無輸出: 已同步，繼續工作
```

### 情況 2: 編輯其他 Dart 檔案

```bash
# 編輯普通 Dart 檔案 (e.g., lib/widgets/home.dart)
# Hook 檢查，發現非 ARB 檔案，自動跳過
# (無任何提示)
```

### 情況 3: 生成檔案缺失（新環境）

```bash
# 編輯 ARB 檔案
# Hook 檢查發現生成檔案不存在
# 提示執行: flutter gen-l10n
```

## 日誌查看

```bash
# 查看最近的檢查日誌
tail -f .claude/hook-logs/l10n-sync/verification-*.log

# 查看特定日期的日誌
cat .claude/hook-logs/l10n-sync/verification-20260115.log
```

## 常見問題

### Q1: Hook 為什麼沒有執行?
- A: 檢查編輯的檔案是否為 ARB 檔案（`.arb` 擴展名）
- A: 檢查路徑是否包含 `l10n` 目錄

### Q2: 為什麼總是提示不同步?
- A: 執行 `flutter gen-l10n` 更新生成檔案
- A: 確認命令執行成功（無錯誤）

### Q3: 能自動執行 `flutter gen-l10n` 嗎?
- A: 目前不支援自動執行（需額外權限）
- A: 建議手動執行，確保可控

## 相關命令快速查詢

```bash
# L10n 生成（必須執行）
flutter gen-l10n

# 驗證國際化（檢查是否正確）
flutter analyze

# 檢查生成檔案
ls -la lib/l10n/generated/

# 查看 Hook 日誌
ls -la .claude/hook-logs/l10n-sync/

# 查看 Hook 配置
grep -A 20 "PostToolUse" .claude/settings.local.json
```

## 設計特點

- 自動化: 無需手動操作，編輯後自動檢查
- 及時: 編輯流程中即時提示，無需等 CI
- 清晰: 提供具體的修復步驟
- 輕量: 使用 Python 標準庫，無外部依賴
- 可靠: JSON 格式化輸出，易於整合

## 技術細節

- 語言: Python 3.11+
- Hook 類型: PostToolUse
- Matcher: Edit 工具
- Timeout: 30 秒
- 檢查方法: 比較 ARB 和 Dart 檔案的 mtime

## 更多資訊

詳細文件: `.claude/references/hooks/L10N_SYNC_VERIFICATION_README.md`
Ticket 記錄: `docs/work-logs/v0.27.0/tickets/0.27.0-TD-001.md`
設定檔: `.claude/settings.local.json`
