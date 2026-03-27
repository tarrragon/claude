# CQ-005: Mock 路徑未隨函式遷移同步更新

**發現日期**: 2026-03-07
**相關 Ticket**: 0.1.0-W7-001, 0.1.0-W8-001

## 症狀

- 執行測試時出現 `AttributeError: <module> does not have the attribute '_function_name'`
- `@patch("module.path._function_name")` 中的路徑找不到目標
- 測試在重構前正常，重構後（函式遷移/重命名）出現失敗

## 根因

函式從一個模組遷移至另一個模組（或從私有改為公開），但測試中的 `@patch` 路徑未隨之更新。正確的 patch 位置是函式使用端，不是定義端。

## 解決方案

1. 確認函式在目標模組中的實際引入方式（`from X import Y` → patch 使用端）
2. 更新 `@patch` 路徑為使用端模組 + 新名稱

## 預防措施

1. 函式遷移（特別是從私有升為公開）後，立即搜尋測試檔案中的相關 `@patch` 路徑
2. `grep -r "_old_function_name" tests/` 找出需要更新的路徑
3. 遷移 Ticket 的驗收條件中明確加入「更新相關測試 Mock 路徑」
4. CI 全量測試才能覆蓋此類問題，本地只跑被修改模組的測試容易遺漏
