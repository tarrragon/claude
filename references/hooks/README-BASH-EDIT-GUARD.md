# Bash Edit Guard Hook - 快速參考

## 概述

Bash Edit Guard 是一個 PreToolUse Hook，用於偵測 Bash 中的檔案編輯操作，並建議使用 Edit 工具替代。

**狀態**: ✓ 已啟用
**版本**: v1.0
**檔案**: `.claude/hooks/bash-edit-guard-hook.py`

## 它做什麼?

當您執行 Bash 命令進行檔案編輯（如 `sed -i`）時，Hook 會：

1. **檢測編輯操作** - 掃描 sed/awk/perl 等編輯工具
2. **發送警告** - 輸出友善的警告訊息
3. **建議修復** - 提示使用 Edit Tool 替代
4. **記錄操作** - 在 `.claude/hook-logs/bash-edit-guard/` 記錄

## 偵測的操作

Hook 會警告以下操作：

- `sed -i` 或 `sed --in-place`
- `awk ... > file.dart`
- `perl -pi`
- 任何輸出重定向到程式碼檔案的操作

## 警告訊息範例

```
[Bash Edit Guard] 警告: 偵測到使用 Bash 進行檔案編輯操作

檢測到的命令:
  sed -i "s/old/new/g" file.dart

建議: 請使用 Edit Tool 替代 Bash sed/awk，
以獲得更好的權限控制和變更追蹤

詳情: 參考 .claude/agent-collaboration.md 的「工具使用強制規範」
```

## 自動觸發

Hook 在以下時機自動觸發：

1. 執行任何 Bash 命令
2. 命令中包含編輯操作
3. **警告發送，命令繼續執行**（不阻止）

## 查看日誌

```bash
# 查看今日所有檢測
tail -f .claude/hook-logs/bash-edit-guard/bash-edit-guard-*.log

# 統計警告次數
grep "警告" .claude/hook-logs/bash-edit-guard/*.log | wc -l
```

## 修復建議

如果看到警告，建議流程：

1. **使用 Edit Tool** - 替代 Bash sed/awk
   ```
   # 不推薦
   sed -i 's/old/new/g' file.dart

   # 推薦
   # 使用 Edit Tool 進行修改
   ```

2. **為什麼?**
   - Edit Tool 提供更好的權限控制
   - 變更會被自動追蹤
   - 整合國際化驗證系統

## 了解更多

- **詳細文件**: `BASH_EDIT_GUARD_HOOK.md`
- **實作文件**: `BASH_EDIT_GUARD_IMPLEMENTATION_SUMMARY.md`
- **日誌位置**: `.claude/hook-logs/bash-edit-guard/`

## 常見問題

### Q: 警告會阻止我的命令嗎?
A: 不會。警告只是提示，命令會繼續執行。

### Q: 我可以忽略警告嗎?
A: 可以，但建議改用 Edit Tool 以遵循最佳實踐。

### Q: 如何禁用此 Hook?
A: 編輯 `.claude/settings.local.json`，移除 Bash 的 PreToolUse 配置。

### Q: 為什麼推薦使用 Edit Tool?
A:
- 更好的權限控制
- 自動變更追蹤
- 整合品質檢驗系統
- 支援國際化驗證

## 配置詳情

**settings.local.json**:
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

## 效能

- **執行時間**: < 50ms（快速正則表達式匹配）
- **開銷**: 可忽略（無法感知）

## 版本歷史

| 版本 | 日期 | 內容 |
|------|------|------|
| v1.0 | 2026-01-15 | 初始發布 |

---

**此 Hook 已啟用並準備投入使用。**
