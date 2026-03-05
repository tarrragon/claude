# 環境例外情境修復指南

本文件提供各種環境問題的預建修復引導，讓 project-init 遇到問題時直接使用靜態內容而非 LLM 生成。

涵蓋所有例外情境及平台特定的修復步驟。

---

## ToolNotFoundError — 工具未找到

### Python 未找到

症狀：
```
Python: 版本未安裝
狀態: Python 3.14+ 是必需的
```

修復步驟：

1. 訪問 https://www.python.org/downloads 下載 Python 3.14 或更高版本
2. 執行安裝程式並完成安裝
3. 驗證安裝：執行 `python3 --version` 確認版本 >= 3.14
4. 重新執行 `project-init check`

macOS 用戶（使用 Homebrew）：
```bash
brew install python@3.14
# 驗證
python3 --version
```

Linux 用戶（Debian/Ubuntu）：
```bash
sudo apt-get update
sudo apt-get install -y python3.14
# 驗證
python3 --version
```

Windows 用戶：
建議使用官方安裝程式，安裝時勾選「Add Python to PATH」選項。

### UV 未找到

症狀：
```
UV: 版本未安裝
狀態: UV 是必需的
```

修復步驟：

1. 訪問 https://docs.astral.sh/uv/guides/installing-uv/
2. 根據平台選擇合適的安裝方式
3. 驗證安裝：執行 `uv --version`
4. 重新執行 `project-init check`

macOS 用戶（推薦使用 curl）：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# 驗證
uv --version
```

Linux 用戶：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# 或使用套件管理器（如果可用）
sudo apt-get install uv  # Debian/Ubuntu（如果在套件庫中）
```

Windows 用戶：
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# 驗證
uv --version
```

### ripgrep 未找到

症狀：
```
ripgrep: 版本未安裝
狀態: ripgrep 是可選的，但建議安裝
```

修復步驟（依平台選擇）：

#### macOS

1. 確保已安裝 Homebrew（https://brew.sh）
2. 執行：`brew install ripgrep`
3. 驗證：`rg --version`
4. 重新執行 `project-init check`

#### Linux

Debian/Ubuntu：
```bash
sudo apt-get update
sudo apt-get install -y ripgrep
```

Fedora/RHEL：
```bash
sudo dnf install -y ripgrep
```

Arch Linux：
```bash
sudo pacman -S ripgrep
```

驗證：`rg --version`

#### Windows

選項 1（使用 winget）：
```bash
winget install -e --id BurntSushi.ripgrep.MSVC
```

選項 2（使用 scoop）：
```bash
scoop install ripgrep
```

驗證：`rg --version`

---

## VersionTooOldError — 版本過舊

### Python 版本過舊（< 3.14）

症狀：
```
Python: 版本 3.10.x 不符合最低要求
狀態: 需要 Python 3.14+
```

升級步驟：

macOS（使用 Homebrew）：
```bash
# 移除舊版本（可選）
brew uninstall python@3.10

# 安裝 Python 3.14+
brew install python@3.14

# 驗證
python3 --version
```

Linux（Debian/Ubuntu）：
```bash
sudo apt-get update
sudo apt-get install -y python3.14

# 設定為預設版本
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.14 1
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 2

# 驗證
python3 --version
```

Windows：
1. 訪問 https://www.python.org/downloads 下載 Python 3.14+
2. 執行安裝程式，選擇「Upgrade Now」或卸載舊版後重新安裝
3. 驗證：`python3 --version`

### UV 版本過舊

症狀：
```
UV: 版本 0.1.0 不符合最低要求
狀態: 需要 UV 0.2.0+
```

更新步驟：

所有平台（統一方式）：
```bash
# 更新 UV
uv self update

# 驗證
uv --version
```

如果 `uv self update` 無法使用，重新安裝：

macOS/Linux：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows：
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

## PermissionDeniedError — 權限被拒

### 無法寫入安裝目錄

症狀：
```
UV: Permission denied 時無法寫入目錄
狀態: 檢查目錄權限
```

修復步驟：

1. 識別無法寫入的目錄（錯誤訊息會顯示路徑）
2. 檢查目錄所有者：`ls -l /path/to/directory`
3. 修復權限：

**如果目錄歸當前用戶**：
```bash
chmod u+w /path/to/directory
```

**如果目錄歸其他用戶（如 root）**：
```bash
# 方式 1：使用 sudo 變更所有者
sudo chown -R $USER /path/to/directory

# 方式 2：或賦予寫入權限給所有人（不推薦）
sudo chmod -R 755 /path/to/directory
```

### 無法建立虛擬環境

症狀：
```
創建虛擬環境時權限被拒
```

修復步驟：

1. 檢查 UV 快取目錄權限：
```bash
ls -ld ~/.cache/uv
```

2. 修復權限：
```bash
chmod -R u+w ~/.cache/uv
```

3. 清理 UV 快取並重試：
```bash
uv cache clean
project-init check
```

---

## NetworkError — 網路錯誤

### PyPI 連線失敗

症狀：
```
UV: 無法連線到 PyPI
狀態: 檢查網路連線和代理設定
```

修復步驟：

1. 確認網路連線：
```bash
ping pypi.org
```

2. 檢查是否需要代理設定：
```bash
# 設定 HTTP 代理（如果需要）
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080

# 重新執行
project-init check
```

3. 如果使用代理，在 pip 配置中設定（永久）：

建立或編輯 `~/.pip/pip.conf`（macOS/Linux）或 `%APPDATA%\pip\pip.ini`（Windows）：
```ini
[global]
index-url = https://pypi.org/simple
proxy = [user:passwd@]proxy.server:port
```

4. 使用替代映射源（中國用戶）：
```bash
# 臨時使用清華源
uv pip install --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple package_name

# 或配置為預設源
uv config set --global index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

### 下載超時

症狀：
```
UV: 下載套件時超時
```

修復步驟：

1. 增加超時時間並重試：
```bash
# 設定環境變數增加超時
export UV_HTTP_TIMEOUT=120  # 120 秒

# 重新執行
project-init check
```

2. 如果仍然失敗，嘗試離線安裝或使用替代源（見上述 PyPI 連線失敗章節）

---

## DiskSpaceError — 磁碟空間不足

症狀：
```
磁碟: 磁碟空間不足
狀態: 無法完成安裝或快取操作
```

修復步驟：

1. 檢查磁碟空間：
```bash
# macOS/Linux
df -h

# Windows
dir C:\
```

2. 清理 UV 快取：
```bash
# 檢查快取大小
du -sh ~/.cache/uv

# 清理快取
uv cache clean
```

3. 清理 Python 快取（__pycache__）：
```bash
# 在專案根目錄執行
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type d -name .pytest_cache -exec rm -rf {} +
```

4. 清理其他臨時檔案：

macOS：
```bash
# 清理舊日誌
rm -rf ~/Library/Logs/*

# 清理 Homebrew 快取
brew cleanup
```

Linux：
```bash
# 清理套件管理器快取
sudo apt-get autoclean
sudo apt-get autoremove
```

5. 需要更多空間時，考慮：
   - 移除不需要的大型檔案
   - 擴充磁碟容量
   - 使用外部儲存設備

---

## ConfigurationError — 設定錯誤

### PATH 環境變數問題

症狀：
```
工具已安裝但找不到（不在 PATH 中）
```

修復步驟：

檢查 PATH：
```bash
echo $PATH
```

macOS/Linux：

編輯 `~/.zshrc`（或 `~/.bashrc`）：
```bash
# 檢查 Python 所在位置
which python3

# 編輯 shell profile
nano ~/.zshrc

# 新增此行（替換實際路徑）
export PATH="/usr/local/bin:$PATH"

# 保存並重新載入
source ~/.zshrc

# 驗證
python3 --version
```

Windows：

1. 開啟「環境變數」（按 Win+X，搜尋「環境變數」）
2. 在「系統變數」中尋找 PATH
3. 點擊編輯，新增 Python 安裝路徑（如 `C:\Users\YourName\AppData\Local\Programs\Python\Python311`）
4. 重啟所有終端機和編輯器

### Shell Profile 未更新

症狀：
```
安裝後工具仍找不到（需要重啟終端機）
```

修復步驟：

1. 重啟終端機或執行：
```bash
source ~/.zshrc      # zsh
source ~/.bashrc     # bash
```

2. 或建立新終端機標籤/視窗

3. 驗證：
```bash
python3 --version
uv --version
rg --version
```

---

## ExecutionError — 執行錯誤

### Hook 編譯失敗

症狀：
```
Hook 系統: 編譯狀態: X 個失敗
PEP 723: 執行: 失敗
```

修復步驟：

1. 檢查失敗的 Hook（查看詳細日誌）：
```bash
ls -la .claude/hooks/
```

2. 驗證 Hook 語法：
```bash
python3 -m py_compile .claude/hooks/specific-hook.py
```

3. 如果有語法錯誤，修復錯誤後重新執行

4. 清理 Hook 編譯快取：
```bash
# 移除 .pyc 檔案
find .claude/hooks -name "*.pyc" -delete

# 移除 __pycache__
rm -rf .claude/hooks/__pycache__
```

5. 重新檢查環境：
```bash
project-init check
```

### 自製套件安裝失敗

症狀：
```
ticket (1.0.0) [MISSING]
  → 需執行: uv tool install .
```

修復步驟：

1. 導航至套件目錄：
```bash
cd .claude/skills/ticket
```

2. 執行安裝：
```bash
uv tool install .
```

3. 驗證安裝：
```bash
ticket --version
```

4. 如果仍然失敗，強制重新安裝：
```bash
uv tool uninstall ticket
uv cache clean
uv tool install . --reinstall
```

### PEP 723 執行失敗

症狀：
```
PEP 723: 執行: 失敗
```

修復步驟：

1. PEP 723 是 Python 3.12+ 的特性，檢查 Python 版本：
```bash
python3 --version
```

2. 如果版本 < 3.12，升級 Python（見 VersionTooOldError 章節）

3. 重新檢查：
```bash
project-init check
```

---

Last Updated: 2026-03-03
Version: 1.0.0
