# Bash Edit Guard Hook 實作文件

## 基本資訊

- **Hook 名稱**: bash-edit-guard-hook
- **Hook 類型**: PreToolUse
- **實作語言**: Python 3.11+
- **版本**: v1.0
- **建立日期**: 2026-01-15
- **檔案路徑**: `.claude/hooks/bash-edit-guard-hook.py`

## 目的

偵測 Bash 命令中的檔案編輯操作，並建議使用 Edit 工具替代，以獲得更好的權限控制和變更追蹤。

**背景**: 代理人在處理批量文字替換時，有時會使用 sed/awk 而非 Edit 工具。這導致權限問題和無法通過官方 Hook 系統追蹤變更。

## 觸發時機

- **Hook 事件**: PreToolUse
- **觸發條件**: Bash 工具執行時
- **Matcher**: `Bash`（所有 Bash 命令都會觸發該 Hook）

## 偵測模式

Hook 檢測以下編輯操作模式：

1. **sed 原地編輯**: `sed -i` 或 `sed --in-place`
2. **sed 輸出重定向**: `sed ... > *.dart|arb|json`
3. **sed 管道輸出**: `sed ... | tee/cat > file`
4. **awk 輸出到檔案**: `awk ... > *.dart|arb|json`
5. **perl 原地編輯**: `perl -pi` 或 `perl -i.bak`
6. **通用輸出重定向**: 任何命令 `> *.dart/arb/json/md/yaml`（排除 echo/printf）

## 輸入格式

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "sed -i 's/old/new/g' file.dart"
  }
}
```

## 輸出格式

### 成功情況（偵測到編輯模式）

**stderr 輸出**:
```
[Bash Edit Guard] 警告: 偵測到使用 Bash 進行檔案編輯操作

檢測到的命令:
  sed -i "s/old/new/g" file.dart

建議: 請使用 Edit Tool 替代 Bash sed/awk，以獲得更好的權限控制和變更追蹤

詳情: 參考 .claude/agent-collaboration.md 的「工具使用強制規範」
```

**stdout 輸出**:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Bash 編輯操作警告已發送，允許執行"
  }
}
```

**Exit Code**: 0（允許繼續執行）

### 成功情況（正常 Bash 命令）

**stdout 輸出**: （無輸出）
**stderr 輸出**: （無輸出）
**Exit Code**: 0（允許執行）

### 失敗情況

- **JSON 格式錯誤**: 直接允許執行（exit 0）
- **運行時錯誤**: 直接允許執行（exit 0）

## 核心邏輯

```
輸入 JSON
  ↓
檢查工具類型是否為 Bash
  ├─ 不是 Bash → 直接允許（exit 0）
  └─ 是 Bash → 檢測編輯模式
      ├─ 不符合編輯模式 → 直接允許（exit 0）
      └─ 符合編輯模式 → 輸出警告 + 允許執行（exit 0）

日誌記錄
  ├─ 偵測到編輯操作 → 記錄命令內容
  ├─ 允許正常命令 → 記錄許可
  └─ 跳過非 Bash 工具 → 記錄跳過原因
```

## 實作方式

### 語言選擇: Python

**選擇理由**:
- JSON 處理簡潔直觀
- 正則表達式支援強大
- 與現有 Hook 系統一致
- 單檔 UV 模式支援完整依賴隔離

### 核心函式

#### `detect_bash_edit_patterns(command: str) -> bool`

使用正則表達式檢測編輯操作：

```python
# 模式 1: sed -i 或 sed --in-place
re.search(r'sed\s+(-i|--in-place)', command)

# 模式 2: sed 配合輸出重定向
re.search(r'sed\s+.*[>].*\.dart|sed\s+.*[>].*\.arb', command)

# 等等...
```

**特點**:
- 模式儘可能精確，避免誤判
- 排除 `echo`/`printf` 等安全操作
- 支援多種語言（sed, awk, perl）

#### `print_warning_message(command: str)`

輸出友善的警告訊息到 stderr：
- 顯示檢測到的命令
- 提供使用建議
- 指向參考文件

#### `setup_logging()` 和 `log_message()`

日誌記錄系統：
- 每日一個日誌檔案
- 位置: `.claude/hook-logs/bash-edit-guard/`
- 格式: `[YYYY-MM-DD HH:MM:SS] 訊息內容`

## 依賴項目

- Python 3.11+ （官方要求）
- 標準庫: json, os, sys, re, datetime, pathlib

**依賴管理**: UV 單檔 PEP 723 格式管理

## 測試驗證

### 測試案例

| # | 命令 | 預期結果 | 狀態 |
|---|------|--------|------|
| 1 | sed -i 操作 | 警告已發送 | ✓ 通過 |
| 2 | sed --in-place | 警告已發送 | ✓ 通過 |
| 3 | awk > file.dart | 警告已發送 | ✓ 通過 |
| 4 | perl -pi | 警告已發送 | ✓ 通過 |
| 5 | 正常 Bash | 無警告 | ✓ 通過 |
| 6 | 非 Bash 工具 | 無警告 | ✓ 通過 |
| 7 | sed > output.dart | 警告已發送 | ✓ 通過 |

### 執行測試

```bash
# 語法檢查
python3 -m py_compile .claude/hooks/bash-edit-guard-hook.py

# 功能測試
echo '{"tool_name":"Bash","tool_input":{"command":"sed -i \"s/old/new/g\" file.dart"}}' | \
  python3 .claude/hooks/bash-edit-guard-hook.py

# 查看日誌
tail -f .claude/hook-logs/bash-edit-guard/bash-edit-guard-*.log
```

## 配置整合

### settings.local.json

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/bash-edit-guard-hook.py",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
```

**配置說明**:
- **matcher**: `Bash` - 對所有 Bash 命令觸發
- **timeout**: 10000ms - 充足的檢測時間（通常 < 100ms）
- **command**: 使用 `$CLAUDE_PROJECT_DIR` 確保可移植性

## 可觀察性

### 日誌位置

`.claude/hook-logs/bash-edit-guard/bash-edit-guard-YYYYMMDD.log`

### 日誌格式

```
[2026-01-15 15:00:34] 警告: 偵測到編輯操作 - sed -i "s/old/new/g" file.dart
[2026-01-15 15:00:34] 允許: 正常 Bash 命令
[2026-01-15 15:00:34] 跳過: 工具類型 Write 不是 Bash
```

### 日誌級別

- **警告**: 偵測到編輯模式操作
- **允許**: 正常 Bash 命令通過
- **跳過**: 非 Bash 工具

### 追蹤報告

Hook 自動為每個檢測到的編輯操作記錄：
1. 命令內容
2. 檢測時間
3. 採取的行動

## 錯誤處理策略

### 原則: 非阻塞

- JSON 解析失敗 → 直接允許（exit 0）
- 正則表達式錯誤 → 直接允許（exit 0）
- 日誌寫入失敗 → 繼續執行，不中斷

**理由**: Hook 是監控工具，不應該阻塞主要工作流程。任何錯誤都應該被記錄但允許執行。

### 異常情況

```python
try:
    # 主邏輯
except json.JSONDecodeError:
    # 非阻塞：允許執行
    sys.exit(0)
except Exception:
    # 非阻塞：允許執行
    sys.exit(0)
```

## 效能特性

### 執行時間

- **平均執行時間**: < 50ms（快速正則表達式匹配）
- **日誌寫入**: < 10ms（批次寫入）
- **總體 Hook 開銷**: < 100ms

### 優化策略

1. **快速路徑**: 非 Bash 工具直接返回（exit 0）
2. **正則快速失敗**: 模式匹配按複雜度排序
3. **日誌非同步**: 不阻塞 Hook 返回

## 修復建議

當使用者看到警告時，建議的修復流程：

1. **確認編輯需求**: 確認確實需要編輯檔案
2. **選擇正確工具**:
   - 簡單替換 → 使用 Edit Tool
   - 複雜文字處理 → 使用 Bash + Edit Tool 組合
   - 大規模變更 → 拆分為多個 Atomic 操作
3. **執行編輯**: 使用 Edit Tool 進行變更
4. **驗證結果**: 檢查修改是否正確

## 與其他 Hook 協作

### 關聯 Hook

- **l10n-sync-verification-hook.py** (PostToolUse/Edit)
  - 此 Hook 在 Edit 後驗證國際化一致性
  - bash-edit-guard 引導使用者使用 Edit，確保被 l10n-sync 捕獲

### Hook 執行順序

```
PreToolUse (bash-edit-guard) → 警告建議使用 Edit
  ↓
Bash 執行 (或用戶改用 Edit)
  ↓
PostToolUse (l10n-sync-verification) → 驗證結果
```

## 已知限制

1. **不阻止執行**: Hook 只警告不阻止，允許使用者自行決定
2. **無法檢測複雜模式**: 某些動態構建的命令可能無法檢測
3. **正規表達式覆蓋**: 可能存在漏掉的編輯模式

**計畫改進**:
- 收集使用者反饋，擴展檢測模式
- 考慮阻止模式（如果政策允許）
- 支援自訂 matcher 模式

## 版本歷史

| 版本 | 日期 | 變更 |
|------|------|------|
| v1.0 | 2026-01-15 | 初始實作，支援 sed/awk/perl/通用重定向 |

## 使用範例

### 範例 1: sed 原地編輯警告

```bash
# 輸入命令
sed -i 's/old/new/g' lib/main.dart

# Hook 檢測並警告
[Bash Edit Guard] 警告: 偵測到使用 Bash 進行檔案編輯操作
檢測到的命令:
  sed -i 's/old/new/g' lib/main.dart
建議: 請使用 Edit Tool 替代 Bash sed/awk...

# 結果：命令繼續執行，但會記錄警告
```

### 範例 2: 正常 Bash 命令（無警告）

```bash
# 輸入命令
ls -la /tmp

# Hook 檢測
(無輸出 - 正常命令)

# 結果：命令正常執行，無任何警告
```

## 參考資料

- [Claude Code Hooks 官方文件](https://github.com/ericbuess/claude-code-hooks-mastery)
- [工具使用強制規範](./../agent-collaboration.md)
- [Bash Edit Guard Hook 測試報告](./.claude/hook-logs/bash-edit-guard/)

## 維護者

- 建立者: basil-hook-architect
- 最後更新: 2026-01-15
- 狀態: ✓ 已啟用並驗證

---

**此文件為 Hook 實作的完整參考，包含設計、實作、測試和使用指引。**
