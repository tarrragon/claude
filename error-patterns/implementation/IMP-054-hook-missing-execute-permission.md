---
id: IMP-054
title: Hook 腳本缺少執行權限導致靜默失敗
category: implementation
severity: high
first_seen: 2026-04-11
ticket: N/A（Session 中直接發現）
related:
  - PC-086
  - ARCH-BAL-015
---

# IMP-054: Hook 腳本缺少執行權限導致靜默失敗

## 症狀

- Claude Code 顯示 `Failed with non-blocking status code: /bin/sh: ... Permission denied`
- Hook 看似正常但檢查從未執行
- 新建的 Hook 在 settings.json 已註冊，但不觸發
- 或顯示 `PostToolUse:Bash hook error` / `PreToolUse:Read hook error`（每次觸發對應事件皆報錯）

## 根因

`.claude/hooks/` 下的 `.py` 檔案缺少執行權限（`chmod +x`）。Write 工具建立的檔案預設權限為 `644`（`-rw-r--r--`），不含執行位元。

settings.json 的 Hook 命令格式若為**直接路徑**（不含 `python3` 前綴），Claude Code 依賴 shebang 機制直接執行該檔案，因此必須有執行位元：

```json
"command": "$CLAUDE_PROJECT_DIR/.claude/hooks/xxx.py"
```

若命令格式為 `python3` 前綴則不受此限：

```json
"command": "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/xxx.py"
```

常見發生場景：
1. 代理人用 Write 工具建立新 Hook 檔案，預設無 `+x` 權限（平台機制，非人為疏忽）
2. 從其他系統複製或 git clone 後權限遺失
3. 批量建立 Hook 時遺漏權限設定

## 影響範圍

- 所有 Hook 事件（SessionStart / PreToolUse / PostToolUse / Stop）
- 2026-04-11 發現時有 45 個腳本缺少執行權限

### 具體案例：post-ticket-complete-checkpoint-hook.py（2026-03-08 首次發現）

- **症狀**：每次 Bash 指令執行後出現 `PostToolUse:Bash hook error`
- **根因**：某 Ticket 使用 Write 工具建立 `post-ticket-complete-checkpoint-hook.py`，檔案權限為 `-rw-r--r--`（644），但已登記在 PostToolUse:Bash hooks 中
- **影響範圍**：所有 Bash 指令（包括搜尋、ls 等）每次執行後都觸發失敗

受影響的 hook 清單（同次發現）：
- `post-ticket-complete-checkpoint-hook.py`（PostToolUse:Bash）
- `ticket-file-access-guard-hook.py`（PreToolUse）
- `askuserquestion-reminder-hook.py`（PreToolUse）
- `language-guard-hook.py`（UserPromptSubmit）

## 解決方案

```bash
# 單一檔案
chmod +x .claude/hooks/<hook-file-name>.py

# 一次性修正所有 Hook 權限
chmod +x .claude/hooks/**/*.py
```

建立 Hook 檔案後立即執行以下三步驟：

```bash
# Step 1: 建立 hook 檔案
Write .claude/hooks/xxx-hook.py

# Step 2: 立即設定執行權限（不可省略）
chmod +x .claude/hooks/xxx-hook.py

# Step 3: 驗證
ls -la .claude/hooks/xxx-hook.py  # 確認 rwxr-xr-x
```

### 快速診斷指令

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

## 防護措施

1. **初始化流程檢查**：`hook-completeness-check.py` 新增權限掃描，SessionStart 時自動偵測並修正（掃描軸僅限 `hooks_dir` 頂層，子目錄誤掃教訓見 ARCH-BAL-015）
2. **Hook 建立檢查清單**：建立 Hook 的 AC 必須包含「檔案已設定執行權限」
3. **與 IMP-051 聯動**：新建 Hook 時同時確認註冊（IMP-051）和權限（IMP-054）

## 行為模式

Write 工具建立檔案時不會設定執行權限，這是平台機制而非人為疏忽。必須在流程中加入自動防護，不能依賴人工記憶。與 IMP-051（未註冊）屬同類問題——建立檔案只是第一步，還需要完成配套設定。

**與 PC-086 的分工**：本文件記錄技術根因與機械修法（chmod +x 本身）；PC-086 記錄 subagent 建檔情境下的行為模式根因（「subagent 寫檔缺系統約束」，與其他同類案例並列），並延伸至權限之外的其他配套設定（frontmatter 格式、shebang）。兩者互為交叉引用，非重複記錄。

## 相關文件

- `.claude/error-patterns/process-compliance/PC-086-subagent-hook-script-missing-exec-bit.md` — subagent 建檔情境的行為模式根因分析
- `.claude/error-patterns/architecture/ARCH-BAL-015-remediation-scan-scope-exceeds-real-need.md` — 本 pattern 衍生的自動 chmod 補救機制，其掃描軸過寬波及不需要 exec bit 的測試檔，反向產生 git mode-only 變更遺留
- `.claude/hooks/hook-completeness-check.py` — Hook 完整性檢查（權限掃描實作）
- `.claude/rules/core/quality-baseline.md` - Hook 失敗必須可見規則

---

**Last Updated**: 2026-08-10
**Version**: 1.1.0 - 併入 IMP-026（新建 Hook 檔案後未設定執行權限）全文：具體案例（post-ticket-complete-checkpoint-hook.py 及受影響 hook 清單）、根因中直接路徑 vs python3 前綴的 shebang 機制說明、快速診斷指令；IMP-026 已刪除，所有引用改指向本文件；補 frontmatter `related` 交叉引用 PC-086 / ARCH-BAL-015
**Version**: 1.0.0
