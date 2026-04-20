---
id: IMP-062
title: Windows 平台 Hook 啟動失敗與編碼斷層
category: implementation
severity: high
first_seen: 2026-04-15
---

# IMP-062: Windows 平台 Hook 啟動失敗與編碼斷層

## 症狀

Windows 環境下 Hook 系統出現以下任一或組合症狀：

- Claude Code UI 顯示 `Failed with non-blocking status code: No stderr output`
- 中文輸出亂碼（如 `@@: ? ?@@@X@@-@h@@@@@@`）
- `json.load(sys.stdin)` 失敗但異常訊息也是亂碼
- Hook 在 macOS/Linux 運作正常但 Windows 上完全不啟動

## 根因

Windows 平台有**三個獨立的斷層點**，任一發生都會導致 Hook 無法正常運作。macOS/Linux 因預設配置正確而從未觸發。

### 斷層 1：Microsoft Store Python Stub（致命）

Windows 11 預裝 `C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python.exe`，此為 Microsoft Store 啟動器存根：

- 未安裝真實 Python 時，執行會 exit code 9009
- **不寫任何 stdout 或 stderr**
- 若 Claude Code 透過 `.py` 副檔名關聯啟動 Hook，會呼叫到此 stub
- 結果：Hook「啟動」但實際完全沒執行，且無任何錯誤訊息可供診斷

### 斷層 2：Git core.autocrlf 污染 Shebang

Windows 環境預設 `git config core.autocrlf=true`，checkout 時將 LF 轉為 CRLF：

- Hook 的 shebang `#!/usr/bin/env -S uv run --quiet --script` 變成 `...uv run --quiet --script\r`
- `env` 試圖解析命令時，`\r` 成為命令一部分，找不到 `uv run\r --quiet` 的可執行檔
- 結果：exit 127，stderr 可能被中斷寫入，或被 CRLF 破壞無法顯示

### 斷層 3：Console Codepage 非 UTF-8

Windows console 預設使用地區化 codepage（繁中 cp950、簡中 cp936、英文 cp437），非 UTF-8：

- Python 未強制 UTF-8 時，`sys.stdin/stdout/stderr` 採用 locale codepage
- Hook 讀取 Claude Code 傳入的 UTF-8 JSON 時 `json.load` 拋出 UnicodeDecodeError
- 異常寫 stderr 時，若 stderr 也用 cp950，中文訊息二次編碼失敗
- 結果：異常訊息空白或亂碼，呈現為「No stderr output」

## 診斷方式

請使用者在 PowerShell 執行：

```powershell
# 1. 確認 Python 是否為 stub
python --version
$LASTEXITCODE    # 若為 9009 表示是 stub

# 2. 確認 console codepage
chcp

# 3. 確認 git autocrlf
git config --get core.autocrlf

# 4. 確認 hook 檔案換行符
$bytes = [System.IO.File]::ReadAllBytes('.claude\hooks\<任一>.py')
($bytes[0..30] | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
# 看是否包含 0D 0A（CRLF）或只有 0A（LF）
```

## 解決方案

### 斷層 1 解決：安裝真實 Python

1. 從 python.org 下載並安裝 Python 3.12+
2. 關閉 Microsoft Store App 執行別名：
   - 設定 → 應用程式 → 進階應用程式設定 → App 執行別名
   - 關閉 `python.exe` 與 `python3.exe`
3. 驗證 `python --version` 有版本號輸出且 `$LASTEXITCODE=0`

### 斷層 2 解決：強制 LF 換行

1. 專案根目錄建立 `.gitattributes` 強制關鍵檔案為 LF：
   ```
   *.py            text eol=lf
   *.sh            text eol=lf
   .gitattributes  text eol=lf
   ```
2. `.claude/.gitattributes` 同步（隨框架 sync 傳播）
3. Windows 使用者 clone 後執行：
   ```bash
   git config core.autocrlf false
   git rm --cached -r .
   git reset --hard
   ```

### 斷層 3 解決：UTF-8 I/O 強制

於 `hook_utils/hook_base.py` 提供 `ensure_utf8_io()`：

```python
def ensure_utf8_io() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, AttributeError):
            continue
```

並由 `setup_hook_logging()` 自動呼叫，所有 Hook 零侵入獲得 UTF-8 保護。

額外補充：所有 `subprocess.run/Popen/check_output` 呼叫必須加 `encoding="utf-8", errors="replace"`，否則子程序輸出仍會用 locale codepage 解碼。

## 防護措施

### Hook 開發規範

| 規則 | 說明 |
|------|------|
| Hook 入口呼叫 `ensure_utf8_io()` | 透過 `setup_hook_logging()` 自動觸發 |
| subprocess 必加 encoding | `encoding="utf-8", errors="replace"` |
| settings.json 路徑使用 forward slash | 跨平台通用 |
| 專案必須有 `.gitattributes` | 強制 `*.py text eol=lf` |

### Hook 作者檢查清單

- [ ] Hook 入口透過 `setup_hook_logging()` 觸發 `ensure_utf8_io()`
- [ ] 所有 subprocess 呼叫含 `encoding="utf-8"` 參數
- [ ] `git check-attr eol <hook.py>` 顯示 `eol: lf`
- [ ] 使用者文件提醒：Windows 需安裝真實 Python + 關閉 Store 別名

### Code Review 檢查項目

- [ ] 新增 Hook 是否透過共用機制獲得 UTF-8 保護？
- [ ] 新增 subprocess 呼叫是否指定 encoding？
- [ ] 文件是否提及 Windows 特殊安裝步驟？

## 相關資訊

- **影響範圍**: 所有 `.claude/hooks/` 下的 Hook（在 Windows 環境）
- **macOS/Linux 不受影響**: 預設 UTF-8 locale + Unix shebang 解析 + 真實 Python
- **關聯錯誤模式**:
  - IMP-048：Hook stderr 觸發 hook error（macOS 場景，stderr 有內容）
  - IMP-054：Hook 缺執行權限（macOS 場景，chmod +x）
  - IMP-055：Hook stdout 純文字破壞 JSON validation

## 行為模式

跨平台開發陷阱典型案例：**開發者在 macOS/Linux 運作正常就假設 Windows 也能用**。Windows 有三個獨立斷層點，只要任一沒處理，就會呈現完全不同的失敗症狀（stub 無輸出、shebang 污染、亂碼）。防護設計必須覆蓋三層，不能只處理其中一層。

`ensure_utf8_io()` 的零侵入設計（透過 `setup_hook_logging` 自動呼叫）是此類跨平台問題的典範解法——個別 Hook 不需要知道跨平台細節，共用基礎設施統一處理。

---

**Created**: 2026-04-15
**Category**: implementation
