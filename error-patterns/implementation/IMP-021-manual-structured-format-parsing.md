# IMP-021: 手動文字解析結構化格式

## 基本資訊

- **Pattern ID**: IMP-021
- **分類**: 程式碼實作
- **來源版本**: v0.1.0
- **發現日期**: 2026-03-06
- **風險等級**: 中
- **關聯 Ticket**: 0.1.0-W2-005

## 問題描述

### 症狀

使用逐行文字搜尋解析結構化格式檔案（TOML、YAML、JSON），導致多種隱性缺陷：
- 格式假設脆弱（只支援特定引號、空格格式）
- 跨節點污染（欄位名在多個節點重複時誤命中）
- 狀態管理複雜（追蹤「當前在哪個 section」的布林旗標容易出錯）

### 根因

開發者傾向於「快速實作」而選擇簡單的字串匹配，忽略標準庫已提供完整的結構化解析器。

### 具體案例

**package_manager.py 的 3 個 _extract_* 函式**：

```python
# 錯誤：逐行文字搜尋
def _extract_version_from_pyproject(pyproject_path):
    with open(pyproject_path, "r") as f:
        for line in f:
            if line.strip().startswith('version = "'):  # 只支援雙引號+特定空格
                return line.split('"')[1]

# 正確：使用 tomllib 結構化解析
def _extract_version_from_pyproject(pyproject_path):
    data = _parse_pyproject(pyproject_path)  # tomllib.load()
    return data.get("project", {}).get("version")
```

**三個同時存在的缺陷**：

| 缺陷 | 描述 | 對應模式 |
|------|------|---------|
| 魔法假設 | 只支援 `version = "x.y.z"` 格式，單引號或不同空格即失敗 | IMP-002 |
| 狀態管理 | `_extract_cli_name` 的 `in_scripts_section` 旗標在多次呼叫間未重置 | IMP-003 |
| 跨節點污染 | `name = "..."` 可能命中 `[tool.hatch]` 等非 `[project]` 節點 | IMP-011 |

## 解決方案

### 原則

**結構化格式必須用結構化解析器**。

| 格式 | Python 標準庫/推薦工具 |
|------|----------------------|
| TOML | `tomllib`（Python 3.11+）或 `tomli` |
| JSON | `json` |
| YAML | `pyyaml` 或 `ruamel.yaml` |
| XML | `xml.etree.ElementTree` |
| INI | `configparser` |

### 共用解析函式 + 快取

當同一檔案需要提取多個欄位時，建立共用解析函式避免重複 I/O：

```python
_cache: dict[str, Optional[dict]] = {}

def _parse_pyproject(path: Path) -> Optional[dict]:
    key = str(path)
    if key in _cache:
        return _cache[key]
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
            _cache[key] = data
            return data
    except Exception:
        _cache[key] = None
        return None
```

## 防護措施

### 程式碼審查檢查項

- [ ] 是否有對 TOML/YAML/JSON/XML 檔案使用 `open()` + `for line in f` 的模式？
- [ ] 是否有用 `startswith()` / `split()` / 正則表達式解析結構化格式？
- [ ] 如果有，是否可以改用對應的標準庫解析器？

### 識別關鍵字

程式碼中出現以下模式時應檢查：

```python
# 警告信號
for line in f:
    if line.strip().startswith('key = ')  # 手動解析 TOML
    if '"' in line:                        # 手動提取引號內容
    in_section = True                      # 手動追蹤 section 狀態
```

## 與既有模式的關係

| 模式 | 關係 |
|------|------|
| IMP-002（魔法假設） | 本模式的子症狀之一 |
| IMP-003（作用域迴歸） | 狀態管理旗標的問題 |
| IMP-011（格式匹配不完整） | 跨節點污染的問題 |
| IMP-012（重新實作標準庫） | 相關但不同：IMP-012 是覆寫標準庫類別，本模式是忽略標準庫解析器 |
