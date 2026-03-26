# Python 品質規則

本文件為 Python 語言的品質規則補充。通用規則見 quality-common.md。

> **適用代理人**：thyme-python-developer、basil-hook-architect

---

## 1. 風格與型別

- 遵循 PEP 8 風格
- 所有公開函式必須有完整的型別標註
- 公開函式必須有文件字串（docstring）

---

## 2. 執行方式（UV 優先，強制）

> **核心原則**：所有 Python 執行優先使用 UV，確保版本一致性。

| 場景 | 正確做法 | 禁止做法 |
|------|---------|---------|
| 執行測試 | `uv run pytest ...` | `python3 -m pytest ...` |
| 執行腳本 | `uv run python script.py` | `python3 script.py` |
| 安裝套件 | `uv pip install ...` | `pip install ...` |
| 執行模組 | `uv run python -m module` | `python3 -m module` |

**Fallback 條件**（僅以下情況允許 `python3`）：UV 不可用、非專案目錄、系統級工具。使用時必須註明原因。

**原因**：UV 根據 `pyproject.toml` 選擇正確 Python 版本，避免系統 Python 版本不匹配（如 3.9 不支援 PEP 604 `str | None`）。

---

## 3. 訊息常數管理

Python 模組的硬編碼字串必須提取到專用 messages 模組：

正確做法（集中管理）：

```python
class CreateMessages:
    SUCCESS = "Ticket {ticket_id} 建立成功"
    MISSING_TITLE = "缺少必填欄位：title"

# 使用
print(CreateMessages.SUCCESS.format(ticket_id=tid))
```

錯誤做法（散落各處）：

```python
print(f"Ticket {tid} 建立成功")
```

**命名規範**：

| 常數類型 | 命名規則 | 範例 |
|---------|---------|------|
| 訊息常數 | 大寫蛇形 | `FILE_NOT_FOUND` |
| Messages 類別 | PascalCase + Messages | `CreateMessages` |
| 格式化 | 使用 `format()` 佔位符 | `"{name} 已完成"` |

---

## 4. 常數管理（強制）

> **核心原則**：Python 模組的業務邏輯常數必須集中定義，禁止硬編碼數值或業務字串散落各處。

**常數定義位置**：

| 作用域 | 定義方式 | 範例 |
|--------|---------|------|
| 單一模組使用 | 模組頂部常數 | `MAX_RETRIES = 3` |
| 跨模組共用 | 獨立 `constants.py` 檔案 | `ticket_system/lib/constants.py` |
| 相關常數群組 | `IntEnum` 或常數類別 | `class Limits(IntEnum)` |

正確做法：

```python
# constants.py
MAX_TICKET_TITLE_LENGTH = 200
DEFAULT_WAVE = 1
SUPPORTED_STATUS = {"pending", "in_progress", "completed", "blocked"}

# 使用
if len(title) > MAX_TICKET_TITLE_LENGTH:
    raise ValueError(...)
```

錯誤做法：

```python
if len(title) > 200:  # 魔法數字
    raise ValueError(...)
```

---

## 5. 魔法數字消除

Python 特有的處理方式：

| 方法 | 適用場景 | 範例 |
|------|---------|------|
| `len()` | 字串前綴長度 | `line[len(PREFIX):]` |
| `removeprefix()` | Python 3.9+ | `line.removeprefix(PREFIX)` |
| `IntEnum` | 相關常數群組 | `class Limits(IntEnum)` |

---

## 6. Python 品質檢查清單

（在通用清單基礎上追加）

- [ ] 使用 UV 執行（`uv run pytest` / `uv run python`）
- [ ] 型別標註完整
- [ ] 公開函式有 docstring
- [ ] 訊息提取到 Messages 類別，無硬編碼使用者訊息
- [ ] 業務常數集中在 `constants.py`，無魔法數字
- [ ] 魔法數字消除（使用 `len()`、`IntEnum` 或具名常數）

---

## 相關文件

- .claude/rules/core/quality-common.md - 通用品質基線

---

**Last Updated**: 2026-03-26
**Version**: 1.2.0 - 合併 python-execution.md 內容（0.2.0-W5-012.2 context 瘦身）
