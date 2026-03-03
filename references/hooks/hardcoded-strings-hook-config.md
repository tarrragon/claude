# 硬編碼字串檢查 Hook 配置說明

## Hook 概述

**Hook 名稱**: check-hardcoded-strings
**類型**: PreCommit（提交前檢查）
**目的**: 防止 Presentation 層新增硬編碼 UI 字符串
**版本**: v1.0

---

## 如何整合到 settings.local.json

在 `.claude/settings.local.json` 中添加 Hook 配置：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/check-hardcoded-strings.sh",
            "timeout": 30000
          }
        ]
      }
    ]
  }
}
```

### 配置說明

| 參數 | 值 | 說明 |
|------|-----|------|
| Hook 事件 | PreToolUse | 檔案編輯前檢查 |
| Matcher | Edit\|Write | 監聽檔案編輯和寫入操作 |
| 指令 | check-hardcoded-strings.sh | Hook 執行腳本 |
| Timeout | 30000ms (30秒) | 足以掃描所有 Presentation 層檔案 |

---

## Hook 執行流程

### 觸發時機

1. **手動執行**: 開發者執行 `Edit` 或 `Write` 工具修改檔案
2. **自動偵測**: Hook 系統監聽檔案變更
3. **檢查執行**: 掃描修改的檔案或整個 Presentation 層

### 檢查邏輯

```
檔案修改
  ↓
Hook 觸發 (PreToolUse)
  ↓
掃描 lib/presentation/ 下的 .dart 檔案
  ↓
檢查硬編碼中文字符串
  ↓
排除合法的中文使用 (AppLogger, print, l10n)
  ↓
生成報告和日誌
  ↓
Exit Code 2 (發現問題) 或 Exit Code 0 (通過)
```

### 輸出位置

- **日誌**: `.claude/hook-logs/hardcoded-strings/check-[timestamp].log`
- **報告**: `.claude/hook-logs/hardcoded-strings/report-[timestamp].md`
- **錯誤輸出**: stderr（包含修復指引）

---

## 使用方式

### 自動執行（推薦）

一旦配置到 settings.local.json，Hook 會自動執行：

```bash
# 編輯檔案時自動觸發
# 如發現硬編碼字符串，會阻止操作並顯示報告
```

### 手動執行

```bash
# 檢查單個檔案
./.claude/hooks/check-hardcoded-strings.sh lib/presentation/widgets/my_widget.dart

# 檢查整個 Presentation 層
./.claude/hooks/check-hardcoded-strings.sh

# 查看最新報告
cat .claude/hook-logs/hardcoded-strings/report-*.md | tail -1
```

---

## 檢查規則

### 檢測對象

**檔案範圍**: `lib/presentation/**/*.dart`

**字符串模式**:
- 單引號中的中文: `'[中文字符]'`
- 雙引號中的中文: `"[中文字符]"`

### 排除規則

以下情況**不會**被標記為硬編碼字符串：

1. **日誌調用**
   ```dart
   AppLogger.debug('日誌訊息')  // ✅ 允許
   print('debug: 載入完成')     // ✅ 允許
   debugPrint('測試')           // ✅ 允許
   ```

2. **i18n 使用**
   ```dart
   Text(l10n.bookTitle)         // ✅ 允許（正確使用）
   l10n.someKey                 // ✅ 允許
   ```

3. **測試檔案**
   ```
   test/                        // ✅ 排除整個 test 目錄
   **/*_test.dart              // ✅ 排除測試檔案
   ```

4. **註解**
   ```dart
   // 這是中文註解    // ✅ 允許
   /// 文件註解       // ✅ 允許
   ```

### 檢查示例

```dart
// ❌ 會被標記（硬編碼字符串）
Text('書籍標題')
Container(child: Text('匯入書籍'))

// ✅ 會通過（使用 i18n）
Text(l10n.bookTitle)
Text(l10n.importBooks)

// ✅ 會通過（日誌調用）
AppLogger.debug('檢查開始')
print('載入完成')

// ✅ 會通過（測試檔案）
// test/widgets/my_widget_test.dart 中的硬編碼字符串
```

---

## 錯誤處理

### 發現硬編碼字符串時

1. **阻止操作**: Hook 返回 Exit Code 2，阻止提交
2. **顯示報告**: stderr 輸出完整的修復指引
3. **記錄日誌**: 詳細記錄到 `.claude/hook-logs/hardcoded-strings/`

### 修復流程

1. **查看報告**
   ```bash
   cat .claude/hook-logs/hardcoded-strings/report-[latest].md
   ```

2. **添加 i18n 字符**
   - 編輯 `lib/l10n/app_zh_TW.arb`
   - 編輯 `lib/l10n/app_en.arb`

3. **生成代碼**
   ```bash
   flutter gen-l10n
   ```

4. **更新 Dart 代碼**
   ```dart
   // 從硬編碼改為 i18n
   Text(l10n.newKey)
   ```

5. **重新執行**
   ```bash
   git add .
   # 提交時會自動檢查
   ```

---

## 常見問題

### Q: Hook 檢查太頻繁，影響開發效率？

A: 當前設置為 PreToolUse，僅在編輯時檢查。可調整：
- 改為 PreCommit：只在提交時檢查
- 增加 Timeout：預留更多時間
- 優化排除規則：減少誤報

### Q: 我確定需要使用硬編碼中文怎麼辦？

A: 除了日誌（AppLogger、print），其他硬編碼中文應通過 i18n 系統管理。如有特殊需求：
1. 與團隊討論
2. 更新排除規則
3. 記錄決策理由

### Q: Hook 報告丟失怎麼辦？

A: 檢查 `.claude/hook-logs/hardcoded-strings/` 目錄：
```bash
ls -lt .claude/hook-logs/hardcoded-strings/ | head -5
```

### Q: 如何禁用此 Hook？

A: 暫時移除 settings.local.json 中的配置。**不建議永久禁用**，應改為調整規則或增加排除項。

---

## 效能考量

### 檢查時間

- 單檔案: < 100ms
- 整個 Presentation 層 (~100 個檔案): 2-5 秒
- Timeout: 30 秒（足裕充足）

### 優化方向

1. **增量檢查**: 未來可只檢查修改的檔案
2. **快取**: 記錄已檢查檔案的指紋
3. **平行化**: 同時掃描多個檔案

---

## 升級計畫

### v0.27.0 計畫

根據實際使用情況，考慮升級：

1. **custom_lint 化**
   - IDE 即時提示
   - 更精確的 AST 分析
   - 更好的開發體驗

2. **規則優化**
   - 根據誤報情況調整
   - 增加更多排除規則
   - 改善檢查準確度

3. **CI/CD 集成**
   - 在 Pipeline 中執行檢查
   - 自動化報告生成
   - 集中式質量管控

### 升級決策依據

- 開發者反饋
- Hook 執行數據
- 誤報率統計
- 投資回報分析

---

## 文件參考

- **i18n 使用指南**: `docs/i18n-guidelines.md`
- **方案分析**: `docs/work-logs/v0.26.0/hardcoded-string-lint-analysis.md`
- **Ticket**: `docs/work-logs/v0.26.0/tickets/0.26.0-W3-001.md`
- **檢查日誌**: `.claude/hook-logs/hardcoded-strings/`

---

## 聯絡和支援

- **Hook 開發者**: basil-hook-architect
- **問題報告**: 建立 Ticket，描述遇到的問題
- **改進建議**: 歡迎提出優化建議

---

**配置版本**: 1.0
**最後更新**: 2026-01-15
**狀態**: ✅ 已完成，待整合到 settings.local.json
