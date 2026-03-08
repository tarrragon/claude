# IMP-026: 新建 Hook 檔案後未設定執行權限

## 分類
- **類型**: implementation
- **嚴重度**: 高
- **發現版本**: v0.1.1
- **發現日期**: 2026-03-08
- **來源 Ticket**: 0.1.1-W5-001

## 模式描述

使用 Write 工具新建 Hook Python 檔案後，未執行 `chmod +x` 設定執行權限。
若該 Hook 已登記在 `settings.json` 中（使用直接路徑格式 `$CLAUDE_PROJECT_DIR/.claude/hooks/xxx.py`），
Claude Code 每次觸發對應事件時都會嘗試直接執行該檔案，因缺少執行權限而失敗，
在 UI 顯示 `PostToolUse:Bash hook error` 或 `PreToolUse:Read hook error`。

## 具體案例

### 案例：post-ticket-complete-checkpoint-hook.py（W15-011）

- **症狀**：每次 Bash 指令執行後出現 `PostToolUse:Bash hook error`
- **根因**：W15-011 使用 Write 工具建立 `post-ticket-complete-checkpoint-hook.py`，
  檔案權限為 `-rw-r--r--`（644），但已登記在 PostToolUse:Bash hooks 中
- **影響範圍**：所有 Bash 指令（包括搜尋、ls 等）每次執行後都觸發失敗

受影響的 hook 清單（同次發現）：
- `post-ticket-complete-checkpoint-hook.py`（PostToolUse:Bash）
- `ticket-file-access-guard-hook.py`（PreToolUse）
- `askuserquestion-reminder-hook.py`（PreToolUse）
- `language-guard-hook.py`（UserPromptSubmit）

## 根因分析

Write 工具建立的檔案預設權限為 `644`（`-rw-r--r--`），不包含執行位元。
Hook 的 `settings.json` 命令格式為直接路徑（不含 `python3` 前綴），依賴 shebang 機制執行，
因此必須有執行位元。

```json
"command": "$CLAUDE_PROJECT_DIR/.claude/hooks/xxx.py"
```

vs.

```json
"command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/xxx.py"
```

前者需要 +x，後者不需要。

## 解決方案

建立 Hook 檔案後立即執行：
```bash
chmod +x .claude/hooks/<hook-file-name>.py
```

## 預防措施

### 1. 建立 Hook 的標準 SOP（強制）

每次使用 Write 工具建立新 Hook 後，必須立即執行 chmod：

```bash
# Step 1: 建立 hook 檔案
Write .claude/hooks/xxx-hook.py

# Step 2: 立即設定執行權限（不可省略）
chmod +x .claude/hooks/xxx-hook.py

# Step 3: 驗證
ls -la .claude/hooks/xxx-hook.py  # 確認 rwxr-xr-x
```

### 2. hook-completeness-check.py 可加入權限檢查

現有的 `hook-completeness-check.py`（SessionStart）可擴充為同時檢查已登記 hook 的執行權限，
偵測到缺少 +x 時輸出警告（非阻塞）。

### 3. 快速診斷指令

當出現大量 PostToolUse/PreToolUse hook error 時，立即執行：
```bash
python3 - <<'EOF'
import json, os
from pathlib import Path
with open(".claude/settings.json") as f:
    settings = json.load(f)
project_dir = os.getcwd()
for event, groups in settings.get("hooks", {}).items():
    for group in groups:
        for hook in group.get("hooks", []):
            cmd = hook.get("command", "").split()[0].replace("$CLAUDE_PROJECT_DIR", project_dir)
            p = Path(cmd)
            if p.exists() and not os.access(p, os.X_OK):
                print(f"[NO EXEC] {event}: {p.name}")
EOF
```

## 相關文件

- `.claude/rules/core/quality-baseline.md` - Hook 失敗必須可見規則
- `.claude/hooks/hook-completeness-check.py` - Hook 完整性檢查（可擴充）
- `0.1.1-W5-001` - 修正 Ticket

---

**Last Updated**: 2026-03-08
**Version**: 1.0.0
