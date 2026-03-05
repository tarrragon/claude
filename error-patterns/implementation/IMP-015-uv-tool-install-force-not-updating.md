# IMP-015: uv tool install --force 不更新已安裝套件程式碼

**分類**: implementation
**嚴重度**: 中
**發現日期**: 2026-03-06
**相關情境**: ticket CLI 修改後測試仍使用舊版

---

## 症狀

修改 Python 套件原始碼後，執行 `uv tool install . --force` 並重新測試，發現行為沒有改變。
CLI 仍然使用修改前的舊版程式碼。

典型症狀：
- 確認原始碼已修改，但 CLI 行為與修改前相同
- `uv tool install . --force` 顯示「Installed 1 executable」但實際套件未更新
- 直接查看安裝路徑的 `.py` 檔案，仍是舊版內容

## 根因

`uv tool install --force` 只強制覆蓋**執行檔**（`~/.local/bin/ticket`），
但不會重新安裝已快取的**套件程式碼**（`~/.local/share/uv/tools/.../site-packages/`）。

`--reinstall` 才會同時重新安裝套件程式碼。

**本次具體案例**：
```bash
# 錯誤：只更新執行檔，套件程式碼未更新
uv tool install . --force
# 輸出顯示 "~ ticket-system==1.0.0" 但版本號相同，套件程式碼不變

# 正確：完整重新安裝套件程式碼
uv tool install . --reinstall
# 輸出顯示 pyyaml + ticket-system 都被重新安裝
```

## 解決方案

修改 uv tool 管理的 Python 套件原始碼後，必須用 `--reinstall` 重新安裝：

```bash
# 正確做法
(cd .claude/skills/ticket && uv tool install . --reinstall)

# 驗證方式：直接查看安裝路徑確認程式碼已更新
cat ~/.local/share/uv/tools/ticket-system/lib/python*/site-packages/ticket_system/commands/track.py | grep "你修改的內容"
```

## 預防措施

### 修改 uv tool 套件後的標準流程

```bash
# 1. 修改原始碼
# 2. 重新安裝（必須用 --reinstall）
(cd .claude/skills/ticket && uv tool install . --reinstall)
# 3. 驗證安裝路徑的程式碼已更新
# 4. 執行功能測試
```

### 快速驗證方法

```bash
# 搜尋安裝路徑中的關鍵程式碼，確認是否已更新
cat ~/.local/share/uv/tools/<tool-name>/lib/python*/site-packages/<package>/<file>.py | grep "修改特徵"
```

### 關鍵記憶點

| 指令 | 更新執行檔 | 更新套件程式碼 |
|------|-----------|--------------|
| `uv tool install . --force` | 是 | 否 |
| `uv tool install . --reinstall` | 是 | 是 |

## 相關文件

- `.claude/skills/ticket/` - ticket CLI 套件
- CLAUDE.md 測試執行章節 - 建議補充重新安裝步驟說明
