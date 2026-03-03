# Handoff 待恢復任務提醒 Hook 實作文件

## 基本資訊

- **Hook 名稱**: handoff-reminder-hook
- **Hook 類型**: SessionStart
- **實作語言**: Python 3.10+
- **版本**: v1.0.0
- **建立日期**: 2026-02-03
- **Ticket ID**: 0.31.0-W3-002.2

---

## 目的

在 Claude Session 啟動時檢查是否有待恢復的 handoff 任務，並顯示清晰的提醒訊息，幫助用戶快速恢復中斷的任務。

---

## 觸發時機

- **Hook 事件**: SessionStart
- **觸發條件**: 每次啟動新 Claude Session 時自動觸發
- **無 Matcher**: SessionStart Hook 無 Matcher，無條件執行

---

## 輸入格式

SessionStart Hook 提供的 JSON 資料（通過 stdin）：

```json
{
  "session_id": "string",
  "transcript_path": "string",
  "source": "string"
}
```

注：SessionStart 可能無 stdin 輸入，Hook 應該優雅地處理此情況。

---

## 輸出格式

### 有待恢復任務時

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "============================================================\n[Handoff 提醒] 有 N 個待恢復的任務\n============================================================\n\n待恢復任務：\n  1. {ticket_id}: {title}\n     方向: {direction}\n  ...\n\n執行提醒：\n  /ticket resume <id>        恢復指定任務 context\n  /ticket resume --list      查看完整清單\n\n============================================================\n"
  },
  "suppressOutput": false
}
```

### 無待恢復任務時（靜默）

```json
{
  "suppressOutput": true
}
```

---

## 實作說明

### 核心邏輯

1. **掃描 handoff/pending 目錄**: 讀取所有 JSON 檔案
2. **解析 JSON 內容**: 提取 ticket_id、title、direction 等欄位
3. **生成提醒訊息**: 格式化待恢復任務清單
4. **輸出 Hook 結果**: 返回格式化的 Hook 輸出

### 關鍵特性

- 自動掃描 `.claude/handoff/pending/` 目錄
- 支援無限數量的待恢復任務
- 包含 `/ticket resume` 指令提示
- 無待恢復任務時靜默（不影響 Session 啟動）
- 完整的日誌記錄和錯誤處理
- 支援 HOOK_DEBUG 環境變數進行除錯

---

## 依賴項目

- Python 3.10+
- 標準庫（無額外依賴）

---

## 檔案位置

| 檔案 | 位置 |
|------|------|
| Hook 腳本 | `.claude/hooks/handoff-reminder-hook.py` |
| 設定檔 | `.claude/settings.local.json` |
| 日誌目錄 | `.claude/hook-logs/handoff-reminder/` |
| Handoff 檔案 | `.claude/handoff/pending/*.json` |

---

## 配置

在 `.claude/settings.local.json` 中的 SessionStart 下註冊：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/handoff-reminder-hook.py",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

**Timeout 設定**: 10 秒（充足於掃描和處理任務）

---

## 測試方法

### 1. 語法檢查

```bash
python3 -m py_compile .claude/hooks/handoff-reminder-hook.py
```

### 2. 功能測試（有待恢復任務）

```bash
cd /Users/mac-eric/project/book_overview_app
CLAUDE_PROJECT_DIR=. echo '{}' | python3 .claude/hooks/handoff-reminder-hook.py
```

預期輸出：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "============================================================\n[Handoff 提醒] 有 N 個待恢復的任務\n..."
  },
  "suppressOutput": false
}
```

### 3. 無輸入測試

```bash
CLAUDE_PROJECT_DIR=. python3 .claude/hooks/handoff-reminder-hook.py < /dev/null
```

預期輸出：
```json
{
  "suppressOutput": true
}
```

### 4. 除錯模式

```bash
HOOK_DEBUG=true CLAUDE_PROJECT_DIR=. echo '{}' | python3 .claude/hooks/handoff-reminder-hook.py 2>&1
```

---

## 可觀察性

### 日誌位置

```
.claude/hook-logs/handoff-reminder/handoff-reminder-YYYYMMDD.log
```

### 日誌內容

```
[2026-02-03 11:19:39,825] INFO - Handoff 提醒 Hook 啟動
[2026-02-03 11:19:39,828] INFO - 專案根目錄: /Users/mac-eric/project/book_overview_app
[2026-02-03 11:19:39,828] INFO - 掃描完成，找到 2 個待恢復任務
[2026-02-03 11:19:39,828] INFO - Hook 執行完成
```

### 除錯日誌

當 HOOK_DEBUG=true 時，會記錄詳細的掃描過程：

```
[2026-02-03 11:19:39,825] DEBUG - 輸入 JSON: {...}
[2026-02-03 11:19:39,826] DEBUG - 掃描檔案: 0.31.0-W4-001.1.json
[2026-02-03 11:19:39,827] DEBUG - 找到待恢復任務: 0.31.0-W4-001.1 - 設計統一 ticket-system SKILL 架構
```

---

## 錯誤處理

| 錯誤情況 | 處理方式 |
|---------|---------|
| handoff/pending 目錄不存在 | 靜默跳過（無待恢復任務） |
| 無 stdin 輸入 | 靜默跳過（SessionStart 無 stdin） |
| JSON 解析失敗 | 記錄警告，跳過該檔案 |
| 檔案讀取失敗 | 記錄警告，繼續掃描其他檔案 |
| 通用執行錯誤 | 記錄錯誤，靜默跳過（不中斷 Session） |

---

## 提醒訊息格式

```
============================================================
[Handoff 提醒] 有 N 個待恢復的任務
============================================================

待恢復任務：
  1. {ticket_id}: {title}
     方向: {direction}
  2. ...

執行提醒：
  /ticket resume <id>        恢復指定任務 context
  /ticket resume --list      查看完整清單

============================================================
```

---

## 設計決策

### 1. 靜默模式

無待恢復任務時不輸出任何訊息，避免不必要的提醒。

### 2. 非阻塊式

Hook 失敗時也不阻塊 Session 啟動，確保系統穩定性。

### 3. 簡潔提醒

只顯示必要資訊（ticket_id、title、direction），避免過度詳細。

### 4. 指令提示

包含 `/ticket resume` 指令的使用說明，方便用戶快速操作。

---

## 與其他系統的整合

### 與 ticket-system 整合

- 讀取 `.claude/handoff/pending/` 目錄中的 JSON 檔案
- 提取 ticket_id 用於 `/ticket resume` 指令

### 與 SessionStart Hook 整合

- 在 tech-debt-reminder 之後執行
- 不影響其他 SessionStart Hook 的執行

### 與 SKILL 系統整合

- 提醒訊息中包含 `/ticket resume` 指令
- 指導用戶使用正確的 SKILL 指令恢復任務

---

## 維護指南

### 添加新特性

如需添加新功能（如過濾、排序），請：

1. 在 `scan_handoff_pending_directory()` 中添加過濾邏輯
2. 在 `generate_reminder_message()` 中修改格式
3. 更新此文檔
4. 執行完整測試

### 修改日誌格式

修改日誌格式時應在 `setup_logging()` 中進行。

### 調整 Timeout

如掃描效能下降，可在 settings.local.json 中調整 timeout 值（預設 10000ms）。

---

## 測試驗證報告

### 語法檢查

- [x] Python 語法檢查通過
- [x] UV 依賴檢查通過（無外部依賴）

### 功能測試

- [x] 掃描 .claude/handoff/pending/ 目錄成功
- [x] 讀取 JSON 檔案成功
- [x] 生成提醒訊息成功
- [x] Hook 輸出格式正確
- [x] 無待恢復任務時靜默成功

### 集成測試

- [x] 在 settings.local.json 中成功註冊
- [x] JSON 配置格式驗證通過
- [x] SessionStart Hook 觸發正常

### 日誌驗證

- [x] 日誌目錄自動建立
- [x] 日誌內容記錄完整
- [x] DEBUG 模式日誌正常

---

## 後續優化建議

1. **性能優化**: 如 handoff 檔案過多，可添加快取機制
2. **排序功能**: 按時間戳或優先級排序待恢復任務
3. **統計資訊**: 記錄待恢復任務的統計資訊
4. **過濾功能**: 支援按 direction 過濾

---

## 參考資源

- [Handoff 系統設計文件](.claude/hook-specs/ticket-handoff-hook-implementation.md)
- [SessionStart Hook 官方規範](.claude/hook-system-reference.md)
- [Hook 系統方法論](.claude/methodologies/hook-system-methodology.md)

---

**最後更新**: 2026-02-03
**版本**: 1.0.0
**狀態**: 完成並測試通過
