# IMP-012: 重新實作標準庫功能且遺漏初始化

## 分類
- **類型**: implementation
- **嚴重度**: 高
- **發現版本**: v0.31.1
- **發現日期**: 2026-03-04

## 模式描述

自訂子類別覆寫 `__init__` 時跳過 `super().__init__()`，導致父類別的關鍵屬性未初始化。當標準庫已提供所需功能（如參數化開關）時，自訂子類別本身就是不必要的。

## 具體案例

### 案例 A：LazyFileHandler 缺少 filters 屬性

**症狀**：所有使用 `setup_hook_logging` 的 Hook 在第一次 `logger.info()` 時 crash

**錯誤訊息**：
```
AttributeError: 'LazyFileHandler' object has no attribute 'filters'. Did you mean: 'filter'?
```

**根因**：W3-004 為了實現「延遲建立日誌檔案」，自訂了 `LazyFileHandler(logging.FileHandler)`，但 `__init__` 中沒有呼叫 `super().__init__()`：

```python
class LazyFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None):
        self.filename = filename
        self.mode = mode
        self.encoding = encoding
        self.stream = None  # 沒有呼叫 super().__init__()!
```

`logging.Handler.__init__()` 負責初始化 `self.filters`、`self.lock`、`self.level`、`self.formatter` 等核心屬性。全部缺失導致任何日誌操作都會 crash。

**影響範圍**：所有 44 個使用 `setup_hook_logging` 的 Hook

**位置**：`.claude/hooks/hook_utils.py` 第 225-251 行

**修復**：刪除 `LazyFileHandler` 類別，改用標準庫的 `logging.FileHandler(..., delay=True)`。Python 的 FileHandler 從 3.0 版起就支援 `delay=True` 參數，效果完全相同：初始化時不開啟檔案，第一次 `emit()` 才建立。

**教訓**：
1. 自訂子類別前先查閱標準庫是否已有參數化支援（`delay=True` 從 Python 3.0 就存在）
2. 覆寫 `__init__` 時必須呼叫 `super().__init__()` — 遺漏會導致繼承鏈中所有父類別的屬性初始化被跳過
3. `py_compile` 和靜態分析無法偵測此類問題（屬性在執行時動態建立）

## 共通模式

| 共通點 | 說明 |
|-------|------|
| 標準庫已有方案 | 自訂實作是多餘的，增加風險 |
| 繼承鏈斷裂 | 跳過 `super().__init__()` 導致所有父類別初始化失敗 |
| 延遲爆發 | 編譯期無法偵測，執行時第一次使用才 crash |
| 全面影響 | 基礎設施層的 bug 影響所有使用者 |

## 防護措施

### 寫自訂子類別前
- [ ] 查閱父類別是否已有參數化支援（如 `delay=True`、`lazy=True`）
- [ ] 搜尋 Python 官方文檔確認是否有內建方案
- [ ] 若確實需要自訂，`__init__` 的第一行必須是 `super().__init__(...)`

### 覆寫 __init__ 時
- [ ] 確認 `super().__init__()` 已被呼叫
- [ ] 了解父類別 `__init__` 初始化了哪些屬性
- [ ] 如果故意跳過父類別初始化，必須手動初始化所有必要屬性並加註解說明原因

### 驗證
- [ ] 執行時測試（`py_compile` 無法偵測此類問題）
- [ ] 呼叫該類別的所有公開方法至少一次
- [ ] 特別驗證 `emit()`、`handle()`、`filter()` 等繼承方法

## 與其他模式的關聯

| 錯誤模式 | 關聯 |
|---------|------|
| IMP-003（作用域迴歸） | 同屬「修改繼承/作用域時未完整驗證」|
| IMP-005（import 遷移不完整） | 同屬「重構後引用更新不完整」|
| IMP-006（Hook 隱性故障） | LazyFileHandler bug 導致 Hook 故障的表現形式相同 |

## 相關文件
- `.claude/hooks/hook_utils.py` - 修復位置
- [Python logging.FileHandler 文檔](https://docs.python.org/3/library/logging.handlers.html#filehandler) - `delay` 參數說明
