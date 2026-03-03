# 技術債務提醒 Hook 使用指南

## 概述

技術債務提醒 Hook 在 Session 啟動時自動檢查當前版本是否有待處理的技術債務，並在控制台顯示警告訊息。

**檔案**: `.claude/hooks/tech-debt-reminder.py`
**Hook 類型**: SessionStart
**語言**: Python 3.10+
**依賴**: pyyaml >= 6.0

## 功能說明

### 工作流程

1. **讀取版本號** - 從 `pubspec.yaml` 提取當前應用版本 (例如 0.20.5)
2. **解析版本系列** - 將版本轉換為版本系列 (例如 v0.20.x)
3. **定位 Tickets 目錄** - 搜尋 `docs/work-logs/v{major}.{minor}.0/tickets/`
4. **掃描 TD Tickets** - 查找所有 `ticket_type: tech-debt` 的檔案
5. **過濾待處理項目** - 篩選 `status: pending` 的 Tickets
6. **顯示警告訊息** - 以格式化 Markdown 顯示待處理列表

### 邊界條件處理

| 條件 | 行為 |
|------|------|
| **無 stdin 輸入** | 靜默跳過（SessionStart 可能無 stdin） |
| **無 pubspec.yaml** | 靜默跳過 |
| **無法解析版本號** | 靜默跳過 |
| **tickets 目錄不存在** | 靜默跳過 |
| **無 pending TD Tickets** | 不輸出任何訊息 (suppressOutput: true) |
| **執行出錯** | 靜默跳過，不中斷 Session 啟動 |

## 輸出格式

### 案例 1: 有待處理技術債務

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "⚠️ 技術債務提醒\n\n當前版本 v0.20.x 有 4 個待處理技術債務：\n\n  1. 0.20.0-TD-001: `book_tags.book_id` 缺少資料庫索引 (風險等級: low)\n  2. 0.20.0-TD-002: `loadInitial` 和 `loadMore` 錯誤處理邏輯可 (風險等級: low)\n  3. 0.20.0-TD-003: 8 個 info 級別 linter 警告 (風險等級: critical)\n  4. 0.20.0-TD-004: `BackgroundProcessingService` 尚未到 Repository (風險等級: medium)\n\n建議：\n  1. 在開始新功能開發前處理這些技術債務\n  2. 或使用 /ticket track 將目標版本延後\n  3. 查看詳細 Ticket: docs/work-logs/v*/tickets/\n\n---\n\n_此提醒由 tech-debt-reminder Hook 自動生成_\n"
  },
  "suppressOutput": false
}
```

### 案例 2: 無待處理技術債務

```json
{
  "suppressOutput": true
}
```

## 使用方法

### 方式 1: SessionStart Hook 自動觸發（推薦）

無需配置，Hook 系統會自動在 Session 啟動時執行。

### 方式 2: 手動測試

```bash
# 基本測試
echo '{"session_id":"test-session"}' | uv run .claude/hooks/tech-debt-reminder.py

# 啟用詳細日誌
HOOK_DEBUG=true echo '{"session_id":"test-session"}' | uv run .claude/hooks/tech-debt-reminder.py
```

### 方式 3: 檢視執行日誌

```bash
# 查看最新日誌
tail -f .claude/hook-logs/tech-debt-reminder/tech-debt-reminder.log

# 查看特定日期日誌
grep "2026-01-07" .claude/hook-logs/tech-debt-reminder/tech-debt-reminder.log
```

## Ticket Frontmatter 格式

Hook 會自動掃描符合以下條件的 Markdown 檔案：

```yaml
---
ticket_id: 0.20.0-TD-001           # 必需
ticket_type: "tech-debt"           # 必需（exact match）
status: pending                    # 必需（exact match）
risk_level: low|medium|high|critical  # 選項（用於排序）
target: "描述"                      # 用於顯示
version: 0.21.0                    # 記錄目標版本
---
```

**掃描規則**:
1. 檔案位置: `docs/work-logs/v{major}.{minor}.0/tickets/`
2. 檔案名稱: 包含 "TD" (例如 `0.20.0-TD-001.md`)
3. Frontmatter: 必須包含 `---...---` YAML 區塊
4. 過濾條件:
   - `ticket_type == "tech-debt"`
   - `status == "pending"`

## 效能特性

| 項目 | 說明 |
|------|------|
| **執行時間** | ~100-200ms (IO bound) |
| **記憶體佔用** | < 5MB |
| **快取機制** | 無（每次執行都掃描） |
| **並行支援** | 安全（無共享狀態） |

## 疑難排解

### 問題 1: Hook 未執行

**可能原因**:
- SessionStart Hook 未在 `.claude/settings.local.json` 中配置
- Hook 檔案不可執行

**解決方案**:
```bash
# 檢查檔案權限
ls -l .claude/hooks/tech-debt-reminder.py
# 應該看到: -rwx...

# 修復權限
chmod +x .claude/hooks/tech-debt-reminder.py

# 檢查 settings.local.json 配置
# (通常無需配置，Hook 系統應自動識別)
```

### 問題 2: 掃描不到 Tickets

**可能原因**:
- Tickets 目錄路徑不符合預期
- Frontmatter 格式不正確
- 版本號格式不符

**解決方案**:
```bash
# 檢查目錄結構
ls -la docs/work-logs/v0.20.0/tickets/

# 檢查 Frontmatter 格式
head -20 docs/work-logs/v0.20.0/tickets/0.20.0-TD-001.md

# 啟用詳細日誌查看解析詳情
HOOK_DEBUG=true echo '{}' | uv run .claude/hooks/tech-debt-reminder.py 2>&1 | grep -i "debug"
```

### 問題 3: pyyaml 依賴錯誤

**錯誤訊息**:
```
Error: pyyaml is required. Install with: uv run --upgrade pyyaml
```

**解決方案**:
```bash
# uv 會自動安裝依賴，通常無需手動操作
# 如果仍有問題，嘗試清除 uv 快取
rm -rf ~/.cache/uv/

# 重新執行
echo '{}' | uv run .claude/hooks/tech-debt-reminder.py
```

## 整合建議

### 與 CI/CD 整合

可將 Hook 集成到自動化流程中：

```bash
#!/bin/bash
# 檢查當前版本是否有待處理 TD
echo '{}' | uv run .claude/hooks/tech-debt-reminder.py | grep -q "suppressOutput.*false"

if [ $? -eq 0 ]; then
    echo "警告: 檢測到待處理技術債務"
    # 可選: 阻止自動發佈或構建
    exit 1
fi
```

### 與任務追蹤整合

結合 `/ticket track` 指令管理 TD Tickets：

```bash
# 查看具體 TD Ticket
/ticket track 0.20.0-TD-001

# 延後 TD 到下一版本
/ticket track 0.20.0-TD-001 --defer v0.21.0
```

## 相關檔案

- **Hook 實作**: `.claude/hooks/tech-debt-reminder.py`
- **日誌目錄**: `.claude/hook-logs/tech-debt-reminder/`
- **Tickets 目錄**: `docs/work-logs/v{X}.{Y}.0/tickets/`
- **配置文件**: `.claude/settings.local.json` (通常無需修改)

## 版本資訊

**Hook 版本**: v1.0
**建立日期**: 2026-01-07
**相容性**: Python 3.10+, pyyaml 6.0+

---

_此文件由 tech-debt-reminder Hook 專案自動維護_
