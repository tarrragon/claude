# IMP-007: 跨邊界操作的不對稱更新

## 基本資訊

- **Pattern ID**: IMP-007
- **分類**: 程式碼實作
- **來源版本**: v0.31.0
- **發現日期**: 2026-03-02
- **風險等級**: 中
- **來源**: ticket migrate 批量遷移 0.30.0-W5 → 0.31.0-W27 時發現

## 問題描述

### 症狀

1. **TD-1（版本定位不對稱）**：跨版本遷移時 `ticket migrate --config` 找不到 source ticket（60 個全部失敗），必須手動加 `--version 0.30.0` 才能定位。
2. **TD-2（欄位更新遺漏）**：遷移後 frontmatter 的 `version` 欄位仍為舊版本（`0.30.0`），需手動 `sed` 修正 60 個檔案。

### 根本原因 (5 Why 分析)

**TD-1**:
1. Why 1: `load_ticket(version, source_id)` 找不到 source ticket
2. Why 2: `version` 被 `resolve_version()` 解析為當前活躍版本 `0.31.0`
3. Why 3: source ticket 實際存在於 `0.30.0` 目錄
4. Why 4: 函式的 target 側已正確從 ID 提取版本（第 376 行），但 source 側沒有
5. Why 5 (根本原因): **source 和 target 使用了不對稱的版本提取策略** -- target 從 ID 提取，source 依賴外部參數

**TD-2**:
1. Why 1: 遷移後 `version: 0.30.0` 未更新
2. Why 2: 更新邏輯只更新了 `id` 和 `wave`，遺漏 `version`
3. Why 3 (根本原因): **欄位更新清單不完整** -- 沒有列舉所有需要更新的 frontmatter 欄位

### 受影響程式碼

```python
# TD-1: source 側使用全域 version（錯誤）
ticket = load_ticket(version, source_id)       # 行 329
_backup_ticket(version, source_id)             # 行 344
get_ticket_path(version, source_id)            # 行 372

# 對比: target 側從 ID 提取版本（正確）
target_version = target_components["version"]  # 行 376

# TD-2: 欄位更新不完整
ticket["id"] = target_id        # 有更新
ticket["wave"] = components["wave"]  # 有更新
# ticket["version"] = ???       # 遺漏！
```

## 修復方案

```python
# TD-1: 從 source_id 提取版本，source 和 target 使用相同策略
source_components = _extract_id_components(source_id)
source_version = source_components["version"] if source_components else version

# TD-2: 補上 version 欄位更新
ticket["version"] = components["version"]
ticket["wave"] = components["wave"]
```

## 共通模式：不對稱更新

本模式與以下已知錯誤模式屬於同一家族：

| Pattern | 不對稱類型 | 共通點 |
|---------|-----------|--------|
| IMP-003 | 變數作用域：移動了定義，未更新引用 | 改了一側忘了另一側 |
| IMP-005 | 模組遷移：移動了檔案，未更新 import | 改了一側忘了另一側 |
| **IMP-007** | 跨邊界操作：target 側正確，source 側遺漏 | 改了一側忘了另一側 |

**根本行為模式**：當一個操作涉及「兩側」（source/target、定義/引用、檔案/import），開發者修正了其中一側後，容易忽略另一側需要相同的處理。

## 防護措施

### 對稱性檢查清單

當函式同時操作 source 和 target 時，強制逐行比對：

- [ ] source 側的版本/路徑提取方式和 target 側是否對稱？
- [ ] source 側和 target 側是否使用相同的策略（從 ID 提取 vs 依賴外部參數）？
- [ ] 所有需要更新的欄位是否完整列舉？（對照資料模型逐欄位檢查）

### 欄位更新完整性檢查

當修改資料記錄的 ID 時，強制檢查：

- [ ] 列出 ID 變更會影響的所有衍生欄位（version、wave、chain、parent 等）
- [ ] 逐一確認每個衍生欄位都有更新邏輯
- [ ] 確認欄位更新順序正確（先更新基礎欄位，再更新衍生欄位）

### 偵測方法

| 偵測方式 | 可偵測 | 說明 |
|---------|--------|------|
| Code Review | 是 | 人工比對 source/target 對稱性 |
| 跨版本測試 | 是 | 用不同版本的 source 和 target 測試 |
| 同版本測試 | 否 | 同版本遷移不會觸發此 bug |
| 靜態分析 | 部分 | 可偵測未使用的參數，但難以偵測語義錯誤 |

## 修復紀錄

- **Commit**: `2388b15` - fix: ticket migrate 支援跨版本遷移
- **修改檔案**: `.claude/skills/ticket/ticket_system/commands/migrate.py`
- **變更**: +8 行 -3 行

---

**Last Updated**: 2026-03-02
**Version**: 1.0.0
