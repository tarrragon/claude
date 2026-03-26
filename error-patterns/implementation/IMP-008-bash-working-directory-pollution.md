# IMP-008：Bash 工作目錄污染

**錯誤碼**: IMP-008
**分類**: Implementation / Tool Usage
**風險等級**: 中（影響操作正確性，不影響資料安全）
**發現日期**: 2026-03-03
**狀態**: 已記錄，已加入防護規則

---

## 症狀

同一 session 內先執行含 `cd` 的命令：
```bash
cd .claude/skills/ticket && uv run ticket track list
```

後續命令找不到預期路徑：
```
Exit code 127: No such file or directory: ./scripts/sync-claude-push.sh
Exit code 1:   ls: scripts/sync-claude-push.sh: No such file or directory
```

即使檔案確實存在，相對路徑也失效。

---

## 根本原因

Claude Code 的 Bash 工具在同一 session 內保持**持久 shell 狀態**。

- `cd` 執行後，工作目錄永久改變（直到 session 結束）
- 後續所有 Bash 命令相對路徑都基於新工作目錄計算
- 與一般 terminal 的行為完全一致，但跨越多個工具呼叫時容易被忽視

---

## 防護方案

### 立即修復（發現污染後）

```bash
# 確認當前目錄
pwd

# 切回專案根目錄
cd /path/to/project
```

### 預防措施（避免污染）

```bash
# 方法 1：子 shell（推薦）
(cd .claude/skills/ticket && uv run ticket track list)

# 方法 2：uv -d 參數
uv -d .claude/skills/ticket run ticket track list

# 方法 3：每次命令前明確指定絕對路徑
cd /project/root && ./scripts/sync-push.sh
```

---

## 相關規則

- @.claude/rules/core/bash-tool-usage-rules.md - 完整防護規範

---

## 發現背景

**版本**: 0.31.1
**操作**: 執行 ticket 查詢後接著執行 sync-push
**根因鏈**: `cd .claude/skills/ticket` → 工作目錄污染 → `./scripts/sync-claude-push.sh` 找不到
**修復**: 改用絕對路徑 `cd /path/to/project && bash scripts/...`
