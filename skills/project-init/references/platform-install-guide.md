# 各平台安裝指南

本文件提供在不同作業系統上安裝 project-init 及其依賴項的詳細步驟。

---

## macOS

### 1. Python 3.11+

#### 使用 Homebrew（推薦）

```bash
# 安裝 Homebrew（如未安裝）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安裝 Python 3.11+
brew install python@3.11

# 驗證
python3 --version
# 輸出應為 Python 3.11.x 或更高
```

#### 使用官方安裝程式

1. 訪問 [python.org](https://www.python.org/downloads/)
2. 下載 macOS 安裝程式（3.11 或更高版本）
3. 執行安裝程式並按步驟進行

### 2. UV

#### 使用 Homebrew（推薦）

```bash
brew install uv
```

#### 使用官方安裝指令

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

驗證：

```bash
uv --version
# 輸出應為 uv x.y.z
```

### 3. ripgrep（可選）

```bash
brew install ripgrep
```

驗證：

```bash
rg --version
# 輸出應為 ripgrep x.y.z
```

---

## Linux

### Ubuntu / Debian

#### 1. Python 3.11+

```bash
# 更新套件列表
sudo apt update

# 安裝 Python 3.11
sudo apt install python3.11 python3.11-venv python3.11-dev

# 設定預設版本（可選）
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# 驗證
python3 --version
```

#### 2. UV

```bash
# 下載並安裝
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
python3 -m pip install uv

# 驗證
uv --version
```

#### 3. ripgrep（可選）

```bash
sudo apt install ripgrep

# 驗證
rg --version
```

### Fedora / RHEL / CentOS

#### 1. Python 3.11+

```bash
# 使用 DNF
sudo dnf install python3.11 python3.11-devel

# 或 YUM（較舊系統）
sudo yum install python3.11

# 驗證
python3 --version
```

#### 2. UV

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# 驗證
uv --version
```

#### 3. ripgrep（可選）

```bash
sudo dnf install ripgrep
# 或
sudo yum install ripgrep
```

### Arch Linux

#### 1. Python 3.11+

```bash
sudo pacman -S python

# 驗證
python3 --version
```

#### 2. UV

```bash
sudo pacman -S uv
# 或
sudo pacman -S uv-bin

# 驗證
uv --version
```

#### 3. ripgrep（可選）

```bash
sudo pacman -S ripgrep

# 驗證
rg --version
```

---

## Windows

### 1. Python 3.11+

#### 方式 A：使用官方安裝程式（推薦）

1. 訪問 [python.org](https://www.python.org/downloads/)
2. 下載 Windows 安裝程式（3.11 或更高版本）
3. 執行安裝程式
4. **重要**：勾選「Add Python to PATH」選項
5. 選擇「Install Now」或自訂安裝

驗證：

```bash
python --version
# 或
python3 --version
```

#### 方式 B：使用 Chocolatey

```bash
# 安裝 Chocolatey（如未安裝）
# 在 PowerShell（以管理員身份執行）:
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 安裝 Python
choco install python

# 驗證
python --version
```

### 2. UV

#### 方式 A：官方安裝指令

在 PowerShell 中執行：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 方式 B：使用 Chocolatey

```bash
choco install uv
```

#### 方式 C：使用 pip

```bash
python -m pip install uv
```

驗證：

```bash
uv --version
```

### 3. ripgrep（可選）

#### 方式 A：使用 Chocolatey

```bash
choco install ripgrep
```

#### 方式 B：官方下載

1. 訪問 [BurntSushi/ripgrep](https://github.com/BurntSushi/ripgrep/releases)
2. 下載 `ripgrep-x.y.z-x86_64-pc-windows-msvc.zip`
3. 解壓到 `C:\Program Files\ripgrep\` 或其他目錄
4. 將該目錄加入 PATH 環境變數

驗證：

```bash
rg --version
```

---

## 安裝完整檢查清單

安裝完成後，執行此清單驗證所有必要工具已就緒：

- [ ] Python 3.11+ 已安裝
  ```bash
  python3 --version
  # 應輸出 Python 3.11.x 或更高
  ```

- [ ] UV 已安裝
  ```bash
  uv --version
  # 應輸出 uv x.y.z
  ```

- [ ] ripgrep 已安裝（可選但建議）
  ```bash
  rg --version
  # 應輸出 ripgrep x.y.z
  ```

- [ ] Python 已加入 PATH
  ```bash
  which python3  # macOS/Linux
  # 或
  where python   # Windows
  ```

- [ ] UV 已加入 PATH
  ```bash
  which uv       # macOS/Linux
  # 或
  where uv       # Windows
  ```

---

## 故障排除

### Python 不在 PATH 中

**macOS/Linux**：

```bash
# 檢查 Python 位置
which python3

# 如找不到，新增到 .bashrc 或 .zshrc
export PATH="/usr/local/bin:$PATH"

# 重新載入
source ~/.bashrc  # 或 source ~/.zshrc
```

**Windows**：

1. 開啟「環境變數」設定
2. 編輯 `Path` 環境變數
3. 新增 Python 安裝目錄（如 `C:\Users\YourUser\AppData\Local\Programs\Python\Python311`）
4. 重啟終端

### UV 安裝失敗

嘗試使用 pip：

```bash
python3 -m pip install --upgrade uv
```

### Python 版本過舊

檢查當前版本：

```bash
python3 --version
```

如低於 3.11，需升級。使用對應平台的安裝指南重新安裝。

---

## 相關文件

- [Python 官方文件](https://www.python.org/doc/)
- [UV 官方文件](https://docs.astral.sh/uv/)
- [ripgrep GitHub](https://github.com/BurntSushi/ripgrep)

---

**Last Updated**: 2026-03-03
**Version**: 1.0.0
