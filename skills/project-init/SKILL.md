---
name: project-init
description: "Use this skill whenever the user needs to check or set up development environment, initialize project dependencies, install required tools, or verify system compatibility. Triggers include: environment initialization, setup environment, check environment, install tools, verify dependencies, environment status, platform setup, or any mention of /project-init."
argument-hint: "<subcommand>"
allowed-tools: Bash(project-init *), Read, Write, Edit
---

# Project Init Tool v1.0

環境初始化工具 — 檢查和設定開發環境

---

## 重要：執行方式（必讀）

### 正確方式

```bash
# 使用已安裝的 project-init CLI（推薦）
project-init --version
project-init check
project-init setup

# 或在 project-init 目錄下使用 uv run
cd .claude/skills/project-init && uv run project-init check
```

### 錯誤方式（禁止）

```bash
# 以下方式會失敗，請勿使用
python3 .claude/skills/project-init/project_init/scripts/main.py
uv run python .claude/skills/project-init/project_init/scripts/main.py
```

**原因**：`project_init` 是 Python 套件，必須透過 `pyproject.toml` 定義的入口點執行。

---

## 執行方式

### 全局安裝（推薦）

全局安裝後可在任何目錄執行 `project-init` 指令。

```bash
# 首次安裝（只需執行一次）
cd .claude/skills/project-init
uv tool install .

# 之後在任何目錄執行
project-init --version
project-init check
project-init setup
```

### 本地執行（開發用）

在 project-init 目錄下使用 `uv run`：

```bash
cd .claude/skills/project-init
uv run project-init check
uv run project-init setup
```

---

## 子指令說明

### project-init --version

輸出版本號。

```bash
project-init --version
# 輸出: project-init 1.0.0
```

### project-init check

掃描環境狀態（唯讀檢查，不修改任何東西）。

檢查項目：
- **OS** — 作業系統和版本
- **Python** — Python 版本（需 3.11+）
- **UV** — UV 套件管理工具
- **ripgrep** — 文字搜尋工具（可選）
- **Hook 系統** — Hook 編譯狀態和 PEP 723 支援
- **自製套件** — 掃描 `.claude/skills/*/pyproject.toml` 並檢查安裝狀態

```bash
project-init check
```

**輸出範例**：

```
============================================================
project-init check — 環境狀態報告
============================================================

[OS]
  macOS 14.6

[Python]
  版本: 3.11.13
  路徑: /opt/homebrew/bin/python3

[UV]
  版本: 0.4.5
  路徑: /opt/homebrew/bin/uv

[ripgrep]
  版本: 14.1.0
  路徑: /opt/homebrew/bin/rg

[Hook 系統]
  Hook 數量: 15
  編譯狀態: 全部通過
  PEP 723: [OK]

[自製套件]
  ticket (1.0.0) [OK]
  project-init (1.0.0) [OK]

============================================================
總結: 6/6 項目正常
============================================================
```

### project-init setup

完整安裝/更新環境（檢查並執行必要的操作）。

步驟：
1. 執行 check（掃描環境狀態）
2. 處理缺失的必要工具（Python、UV）並輸出安裝指令
3. 更新自製套件（如有新版本）

```bash
project-init setup
```

**輸出範例**：

```
============================================================
project-init setup — 環境設定
============================================================

[1/3] 檢查環境狀態...
[環境檢查輸出...]

[2/3] 處理缺失和過時工具...
  [無需處理]

[3/3] 更新自製套件...
  ticket (1.0.0) [OK]
  project-init (1.0.0) [OK]

============================================================
設定完成: 0 項已自動修復，0 項需手動處理
============================================================
```

---

## 安裝和更新

### 首次安裝

```bash
cd .claude/skills/project-init
uv tool install .
```

### 更新（程式碼修改後）

```bash
cd .claude/skills/project-init
uv tool install . --force --reinstall
```

> **重要**：使用 `--force --reinstall` 旗標確保程式碼變更生效。更多資訊見 Project Memory 中的「uv tool 重新安裝」。

### 驗證安裝

```bash
project-init --version
# 輸出: project-init 1.0.0
```

---

## 常見使用情境

### 新開發者加入

```bash
# 檢查環境
project-init check

# 如有缺失工具，執行設定
project-init setup
```

### 更新依賴或 Hook

```bash
# 更新 project-init 工具
cd .claude/skills/project-init
uv tool install . --force --reinstall

# 重新檢查環境
project-init check
```

### 驗證 Hook 系統

```bash
# check 包含 Hook 編譯狀態驗證
project-init check

# 查看 Hook 系統部分的結果
```

---

## 依賴項

project-init 僅依賴 Python 標準函式庫：

- `argparse` — CLI 參數解析
- `dataclasses` — 資料結構
- `pathlib` — 路徑操作
- `subprocess` — 執行外部命令
- `json` — JSON 序列化

無額外的第三方依賴。

---

## 參考文件

- `references/platform-install-guide.md` - 各平台詳細安裝指南
- `references/remediation-guides.md` - 各種例外情境的預建修復引導

---

## 故障排除

### 執行出現 ModuleNotFoundError

確認使用正確的執行方式：

```bash
# 正確 — 使用全局 CLI
project-init check

# 正確 — 在目錄下使用 uv run
cd .claude/skills/project-init && uv run project-init check

# 錯誤 — 直接執行 Python 檔案
python3 .claude/skills/project-init/project_init/scripts/main.py
```

### project-init 找不到

確認已安裝：

```bash
# 檢查是否已安裝
which project-init

# 如未安裝，執行安裝
cd .claude/skills/project-init
uv tool install .
```

### 環境檢查失敗

查看 check 指令的完整輸出，識別 `[MISSING]` 或 `[ERROR]` 的項目，依指示操作。

---

## 相關技巧

### 整合到開發流程

在 Hook 或自動化指令中使用 project-init 驗證環境：

```bash
# 檢查環境是否就緒
project-init check || (project-init setup && echo "環境已就緒")
```

### 搭配其他工具

結合 UV 和 project-init 進行完整設定：

```bash
# 檢查環境
project-init check

# 更新所有工具
uv tool upgrade --all

# 重新檢查
project-init check
```

---

**Last Updated**: 2026-03-03
**Version**: 1.0.0
