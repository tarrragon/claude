# Python 執行規則

本文件定義 Python 腳本和工具的執行方式規範。

---

## 核心原則

> **UV 優先**：所有 Python 執行優先使用 UV，確保版本一致性。

---

## 強制規則

### 規則 1：優先使用 UV 執行

當需要執行 Python 相關命令時，**必須優先使用 UV**：

| 場景 | 正確做法 | 禁止做法 |
|------|---------|---------|
| 執行測試 | `uv run pytest ...` | `python3 -m pytest ...` |
| 執行腳本 | `uv run python script.py` | `python3 script.py` |
| 安裝套件 | `uv pip install ...` | `pip install ...` |
| 執行模組 | `uv run python -m module` | `python3 -m module` |

### 規則 2：Fallback 條件

僅在以下情況允許使用 `python3`：

| 條件 | 說明 |
|------|------|
| UV 不可用 | 系統未安裝 UV |
| 非專案目錄 | 不在有 `pyproject.toml` 的目錄中 |
| 系統工具 | 執行系統級 Python 工具（非專案相關） |

使用 fallback 時必須註明原因。

---

## 原因說明

### 為何 UV 優先？

1. **版本一致性**：UV 根據 `pyproject.toml` 的 `requires-python` 選擇正確版本
2. **依賴隔離**：UV 在虛擬環境中執行，避免污染系統環境
3. **可重現性**：確保所有開發者使用相同的 Python 版本

### 實際案例

**問題場景**（W7-001.1）：

```bash
# 錯誤：使用系統 Python 3.9.6
python3 -m pytest tests/test_cycle_detector.py
# 結果：TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'

# 正確：使用 UV 管理的 Python 3.11.13
uv run pytest tests/test_cycle_detector.py
# 結果：392 tests passed
```

**原因**：
- 系統 Python 3.9 不支援 PEP 604 語法（`str | None`）
- UV 管理的 Python 3.11 支援此語法

---

## 檢查清單

執行 Python 前，確認：

- [ ] 是否在專案目錄中？
- [ ] 是否使用 `uv run` 前綴？
- [ ] 如果無法使用 UV，是否有正當理由？

---

## 相關文件

- @.claude/skills/ticket/SKILL.md - 示範正確的 UV 使用方式
- @.claude/skills/ticket/pyproject.toml - Python 版本要求定義

---

**Last Updated**: 2026-02-05
**Version**: 1.0.0
**Source**: 0.31.0-W7-001.1 修復過程中發現的操作錯誤
