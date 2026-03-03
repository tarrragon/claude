# file-type-permission-hook.py - 開始閱讀

歡迎使用 file-type-permission-hook.py！本文件幫助您快速了解和使用這個 PreToolUse Hook。

## 5 分鐘快速開始

### 這個 Hook 做什麼？

根據編輯檔案的類型提供不同的處理方式：

**Ticket 和 Worklog 檔案** → 輸出提示訊息，提醒人工審查

```
[File Permission Guard] 提示: 正在編輯 Ticket 檔案

檔案: .claude/tickets/my-ticket.md
說明: 此類檔案的修改需要人工審查確認
```

**程式碼檔案** → 靜默通過，無任何輸出

```
(無任何輸出)
編輯執行正常進行
```

### 核心特點

- 智能檔案分類：自動判斷檔案類型
- 差異化回應：需要確認的提示，不需要的靜默
- 完整日誌：所有操作都有記錄可追蹤
- 非阻塊設計：永遠不會阻止編輯執行

## 檔案分類速查表

| 檔案路徑 | 行為 |
|---------|------|
| `.claude/tickets/*` | 輸出提示訊息 |
| `docs/work-logs/*` | 輸出提示訊息 |
| `lib/*` | 靜默通過 |
| `test/*` | 靜默通過 |
| `integration_test/*` | 靜默通過 |
| 其他檔案 | 靜默通過 |

## 根據您的需要選擇文件

### 我只是想快速了解

**推薦**: [QUICK-REFERENCE-file-type-permission-hook.md](./QUICK-REFERENCE-file-type-permission-hook.md)
- 2 分鐘了解全部
- 常見問題解答
- 快速使用示例

### 我想深入了解詳細內容

**推薦**: [README-file-type-permission-hook.md](./README-file-type-permission-hook.md)
- 完整功能說明
- 輸入輸出格式
- 測試驗證方法
- 可觀察性設計

### 我想了解實作細節

**推薦**: [IMPLEMENTATION-SUMMARY-file-type-permission-hook.md](./IMPLEMENTATION-SUMMARY-file-type-permission-hook.md)
- 實作摘要
- 技術特點
- 部署狀態
- 配置說明

### 我需要快速查找資訊

**推薦**: [INDEX-file-type-permission-hook.md](./INDEX-file-type-permission-hook.md)
- 檔案導航
- 快速命令
- 技術規格
- 常用查詢

## 常見使用情景

### 情景 1: 編輯 Ticket 檔案

```
1. 執行 Edit 工具編輯 .claude/tickets/IMP-001-feature.md
2. Hook 觸發
3. stderr 輸出提示訊息（提醒人工審查）
4. 編輯執行完成
5. 所有操作記錄到日誌
```

**查看日誌**:
```bash
tail -f .claude/hook-logs/file-type-permission/file-type-permission-*.log
```

### 情景 2: 編輯程式碼檔案

```
1. 執行 Edit 工具編輯 lib/main.dart
2. Hook 觸發（但無任何輸出）
3. 編輯靜默執行
4. 開發流程不受干擾
5. 操作記錄到日誌
```

### 情景 3: 編輯其他檔案

```
1. 執行 Edit 工具編輯 pubspec.yaml
2. Hook 觸發（但無任何輸出）
3. 編輯靜默執行
4. 完全無感知
```

## 技術資訊

- **Hook 類型**: PreToolUse
- **Matcher**: Edit
- **語言**: Python 3.11+
- **依賴**: 無（標準庫）
- **Timeout**: 10 秒
- **Exit Code**: 0（總是允許）

## 部署狀態

所有檔案已建立並經過驗證：

- [x] Hook 核心實現 (file-type-permission-hook.py)
- [x] 完整文件 (README)
- [x] 快速參考 (QUICK-REFERENCE)
- [x] 實作摘要 (IMPLEMENTATION-SUMMARY)
- [x] 文件索引 (INDEX)
- [x] 配置更新 (settings.local.json)
- [x] 語法檢查 (通過)
- [x] 功能測試 (全部通過)

**狀態**: 已完成，準備生產使用

## 常見問題

### Q: 為什麼編輯程式碼檔案沒有任何提示？

**A**: 這是設計的一部分。程式碼檔案無需人工確認，靜默執行可避免干擾開發流程。所有操作都會記錄到日誌中。

### Q: 可以修改提示訊息嗎？

**A**: 可以。編輯 `file-type-permission-hook.py` 中的 `print_permission_prompt()` 函數。詳見 README 文件。

### Q: 可以添加更多檔案類別嗎？

**A**: 可以。編輯 `get_file_category()` 函數添加新的路徑模式。詳見 README 文件。

### Q: Hook 會阻止編輯嗎？

**A**: 不會。所有情況都返回 exit code 0，永遠不會阻止編輯執行。

### Q: 日誌在哪裡？

**A**: 在 `.claude/hook-logs/file-type-permission/` 目錄下，每日一個日誌檔案。

## 快速命令

```bash
# 查看實時日誌
tail -f .claude/hook-logs/file-type-permission/file-type-permission-*.log

# 測試 Ticket 檔案
echo '{"tool_name":"Edit","tool_input":{"file_path":".claude/tickets/test.md"}}' | \
  python3 .claude/hooks/file-type-permission-hook.py

# 驗證語法
python3 -m py_compile .claude/hooks/file-type-permission-hook.py

# 查看完整文件
less .claude/references/hooks/README-file-type-permission-hook.md
```

## 文件地圖

```
.claude/hooks/
├── 00-START-HERE-file-type-permission-hook.md      ← 您正在這裡
├── file-type-permission-hook.py                    ← Hook 核心實現
├── README-file-type-permission-hook.md             ← 完整文件
├── QUICK-REFERENCE-file-type-permission-hook.md    ← 快速參考
├── IMPLEMENTATION-SUMMARY-file-type-permission-hook.md  ← 實作摘要
└── INDEX-file-type-permission-hook.md              ← 文件索引

.claude/
└── settings.local.json                             ← Hook 配置

.claude/hook-logs/
└── file-type-permission/                           ← 執行日誌
```

## 下一步

1. **了解基礎**: 閱讀 [QUICK-REFERENCE-file-type-permission-hook.md](./QUICK-REFERENCE-file-type-permission-hook.md) (2 分鐘)

2. **深入學習**: 閱讀 [README-file-type-permission-hook.md](./README-file-type-permission-hook.md) (10 分鐘)

3. **開始使用**: 啟動新的 Claude Code 會話，Hook 將自動生效

4. **查看日誌**: 觀察 `.claude/hook-logs/file-type-permission/` 中的日誌

5. **需要幫助**: 參考 [INDEX-file-type-permission-hook.md](./INDEX-file-type-permission-hook.md) 查找相關資訊

## 技術支持

如果遇到問題：

1. 檢查 [QUICK-REFERENCE-file-type-permission-hook.md](./QUICK-REFERENCE-file-type-permission-hook.md) 的常見問題
2. 查看 `.claude/hook-logs/file-type-permission/` 中的日誌檔案
3. 驗證 `.claude/settings.local.json` 中的配置
4. 檢查 `file-type-permission-hook.py` 的註解和說明

## 版本資訊

- **版本**: v1.0
- **建立日期**: 2025-01-16
- **狀態**: 完成並驗證
- **維護者**: Claude Code Hook System

---

**準備好開始了嗎？** → 前往 [QUICK-REFERENCE-file-type-permission-hook.md](./QUICK-REFERENCE-file-type-permission-hook.md)
