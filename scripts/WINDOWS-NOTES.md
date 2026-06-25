# Windows 使用者 sync 腳本注意事項

## 為什麼需要這份文件

**Why**：`.claude/` 框架同步腳本（`sync-claude-push.py` / `sync-claude-pull.py`）在 Windows 環境執行時，git 對檔案 executable bit 的處理與 macOS/Linux 不同，若未理解此差異，push 出去的 hook 檔案會被記錄為不可執行（`100644`），下游使用者 pull 回來後 shell 無法直接執行 hook 腳本。

**Consequence**：Windows 執行 sync-push 曾導致 v1.36.2 遠端 repo 一次新增 379 個 hook 相關 `.py` 檔案，mode 全為 `100644`（應為 `100755`）。所有 Mac 使用者 pull 下來後，`Stop hook` 和 `SessionStart hook` 執行時觸發 `Permission denied`，直到手動 `chmod +x` 才恢復。

**Action**：Windows 使用者執行 sync-push 前，閱讀本文件並依照建議流程操作；若已推出錯誤 mode，本地 sync-pull 的 safety net 會自動修復 `hooks/**/*.py`。

---

## 根因說明

### Windows 檔案系統與 git 的互動

| 環境 | Filesystem | Executable bit | git `core.filemode` 預設 |
|------|-----------|----------------|------------------------|
| macOS / Linux | APFS / ext4 / XFS | POSIX 屬性 | `true`（讀寫 mode） |
| Windows | NTFS | 無原生概念 | `false`（不碰 mode） |

### `git add` 對新檔案的行為差異

| 場景 | macOS / Linux 行為 | Windows 行為 |
|------|-------------------|-------------|
| 既有檔案（已 tracked） | `core.filemode=true` 時從 filesystem 讀 mode；`false` 時保留既有 index mode | `core.filemode=false` 保留既有 index mode |
| **新檔案（首次 add）** | 從 filesystem 讀 mode（含 shebang 的 `.py` 通常為 `100755`） | **無法從 NTFS 推斷，fallback 為 `100644`** |

**關鍵**：`core.filemode=false` 只保護「既有檔案」的既有 mode，對「新增檔案」的首次 mode 判定沒有保護力。Windows 新增任何 `.py` 檔案，git 預設都會記為 `100644`。

### v1.36.2 實例

- 該 commit 新增 `hooks/acceptance_checkers/` 等目錄共 379 個 `.py` 檔案
- Remote repo mode 分布：v1.17.0 時 847 × `100644` + 147 × `100755`；v1.36.2 後 1226 × `100644` + **147 × `100755`（完全沒增加）**
- 證實：既有 `100755` 被保留，但新增檔案全部降權為 `100644`

---

## Windows 使用者操作建議

### 建議 1：優先在 macOS / Linux 執行 sync-push

**Why**：macOS/Linux 能正確從 filesystem 推斷 executable bit，新檔 mode 自動正確。

**How to apply**：若你同時有 Mac/Linux 開發環境，初次 sync-push 請在 macOS/Linux 上做；Windows 僅做 sync-pull 或補充性 push。

### 建議 2：依賴 sync-claude-push.py 內建 safety net

**Why**：最新版 `sync-claude-push.py` 包含兩層 safety net：
1. `restore_executable_bits()` — push 前對 `temp_dir/hooks/**/*.py` 執行 filesystem chmod +x（macOS/Linux 有效）
2. （規劃中）`git update-index --chmod=+x` — 顯式設定 git index mode（跨平台一致，治本方案）

**How to apply**：不需特別操作，執行 `python3 ./.claude/scripts/sync-claude-push.py "<訊息>"` 即可；safety net 會自動生效。

### 建議 3：push 前手動驗證 mode

**Why**：safety net 是自動防護，但仍建議 Windows 使用者手動確認一次，防止邏輯漏網。

**How to apply**（push 前的檢查流程）：

```bash
# 步驟 1：確認既有 hook mode 未損壞（應顯示 100755）
git ls-files --stage .claude/hooks/acceptance-gate-hook.py

# 步驟 2：執行 push
python3 ./.claude/scripts/sync-claude-push.py "你的訊息"

# 步驟 3：push 完成後，clone 遠端 repo 抽驗新檔 mode
#         若 hooks/ 下新增 .py 是 100644，表示 safety net 未生效，需回報 issue
```

### 建議 4：遇到 mode 損壞時的救援

**Why**：sync-pull safety net 會自動 chmod +x `hooks/**/*.py`。若仍遇 Permission denied，表示 safety net 覆蓋範圍外（例如 `scripts/` 下或 skill 內 scripts）。

**How to apply**：

```bash
# 手動對所有 hook 檔案還原 executable bit
find .claude/hooks -name "*.py" -exec chmod +x {} \;

# 檢查是否有其他受影響目錄
find .claude -name "*.py" -not -perm -u+x | head -10
```

---

## sync-pull safety net 說明

`sync-claude-pull.py` 完成檔案同步後，會自動對 `.claude/hooks/**/*.py` 強制加入 executable bit。

**覆蓋範圍**：

| 目錄 | safety net 覆蓋 | 原因 |
|------|----------------|------|
| `.claude/hooks/**/*.py` | **是** | 全部應為可執行（shell 直接呼叫） |
| `.claude/scripts/*.py` | 否 | 有 `644` / `755` 混合（sync 腳本本身 `644` 由 `python3` 呼叫） |
| `.claude/skills/*/scripts/*.py` | 否 | 未覆蓋，若遇問題需手動處理 |

**為何不對所有 `.py` 做 chmod**：`.claude/scripts/sync-claude-pull.py` / `sync-claude-push.py` / `sync-claude-status.py` 本身是 `100644`（用 `python3 ./.claude/scripts/xxx.py` 呼叫），盲目 chmod +x 會偏離 git HEAD 記錄的正確 mode。

---

## 除錯步驟

### 症狀：Stop hook 回報 `Permission denied`

```text
Stop hook error: Failed with non-blocking status code:
/bin/sh: /path/to/.claude/hooks/xxx-hook.py: Permission denied
```

### 檢查清單

- [ ] 檔案是否存在？`ls -l .claude/hooks/xxx-hook.py`
- [ ] 檔案有無 `+x`？`-rw-r--r--` 表示沒有
- [ ] `settings.json` 是否註冊此 hook？`grep "xxx-hook" .claude/settings.json`
- [ ] 檔案是否有 shebang？`head -1 .claude/hooks/xxx-hook.py` 應含 `#!/usr/bin/env`

### 快速修復

```bash
chmod +x .claude/hooks/xxx-hook.py
```

### 系統性修復（一次還原所有 hook）

```bash
find .claude/hooks -name "*.py" -exec chmod +x {} \;
```

---

## CLI shim 的 Windows 相容性（ticket / doc / worktree）

**背景**：`ticket` / `doc` / `worktree` 三個 CLI 由 `.claude/scripts/install-skill-clis.py` 安裝為 cwd-resolving shim（POSIX `#!/bin/sh`），內容為 `git rev-parse --show-toplevel` → `uv run --directory <skill> <cli>`（根治全域 namespace 碰撞，見 ARCH-APP-002 / framework issue #12）。

**結論：Windows 上現有 shim 已可用，無需 `.cmd`/`.ps1` 變體。**（0.37.0-W7-004 ANA 結論）

| Windows 環境 | shim 是否可用 | 說明 |
|---|---|---|
| 有 Git for Windows → CC 用 **Git Bash** | 可用 | Git Bash 解析 `#!/bin/sh` shebang，shim 直接執行 |
| **WSL2** | 可用 | 完整 POSIX 環境（CC 沙箱在此完整支援） |
| 無 git → CC 降級 **PowerShell** | 不適用（moot） | 無 git 時 shim 核心 `git rev-parse` 無法運作，且本框架所有 skill 皆強依賴 git → 整個框架本就無法運作 |

**推論鏈**：本框架強依賴 git（shim、ticket 系統、worktree 皆用 git）→ Windows 使用者必然安裝 Git for Windows → CC 在有 git 的 Windows 上使用 Git Bash 作為 Bash 工具 → `#!/bin/sh` shim 被解析、直接可用。

**使用者須知**：
- Windows 使用者請安裝 **Git for Windows**（同時提供 git 與 Git Bash）。
- 若 CC 無法自動找到 Git Bash，於 `settings.json` 設定：
  ```json
  { "env": { "CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe" } }
  ```
- 確認 `uv` 在 PATH 上（CC 不內建 uv，需自行安裝）。

> **邊界**：若未來需支援「在 CC session 外、原生 PowerShell 終端」手動呼叫這三個 CLI，才需考慮 `.cmd`/`.ps1` 變體（W7-004 已設計但未實作；reopen 條件見該 ticket）。
>
> **來源**：CC 官方文件 https://code.claude.com/docs/en/setup.md（Windows Bash 工具 shell 選擇）。

---

## 相關文件

- `.claude/scripts/README-subtree-sync.md` — 同步機制總覽
- `.claude/scripts/sync-claude-push.py` — 推送腳本（含 `restore_executable_bits`）
- `.claude/scripts/sync-claude-pull.py` — 拉取腳本（含 `restore_executable_bits`）
- `.claude/scripts/install-skill-clis.py` — CLI shim installer（ARCH-APP-002）
- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W16-004.md` — 根因分析與修復追蹤

---

**Last Updated**: 2026-06-25
**Version**: 1.1.0 — 新增「CLI shim 的 Windows 相容性」章節（0.37.0-W7-004，framework #12/#13）
**原始版本**: 1.0.0（2026-04-20）— 從 W16-004 根因分析提煉 Windows 使用者指南
**Source**: v1.36.2 大規模 mode 損壞事件 + W16-004 Ticket 實證分析
