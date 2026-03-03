# 錯誤模式識別參考

PostToolUse Hook 使用的正則表達式模式，用於自動分類錯誤類型。

---

## SYNTAX_ERROR 模式 (6 種)

```
1. Expected.*?['\"]([;})\]])['\"]     - 缺少括號或分號
2. Unexpected\s+(?:end of|token)\b   - 意外 token
3. unterminated string literal         - 字串未結束
4. unexpected end of.*file             - 檔案不完整
5. missing comma                       - 缺少逗號
6. invalid number format               - 無效數字格式
```

---

## COMPILATION_ERROR 模式 (7 種)

```
1. (?:type|variable).*?can't be assigned        - 類型不匹配
2. is not a subtype of                          - 子型檢查失敗
3. Undefined\s+(?:name|class|function)          - 未定義名稱
4. Target of URI.*?doesn't exist                - 導入檔案不存在
5. (?:Class|Function|Method).*?not found        - 引用不存在
6. cannot find symbol                           - 符號未定義
7. incompatible types                           - 類型不相容
```

---

## TEST_FAILURE 模式 (4 種)

```
1. Expected:.*?Actual:                  - 斷言失敗
2. (\d+)\s+tests?\s+failed             - 失敗計數
3. FAILED                               - 失敗標記
4. AssertionError                       - 斷言例外
```

---

## ANALYZER_WARNING 模式 (3 種)

```
1. info\s*-.*?unused               - 未使用的警告
2. warning\s*-                     - lint 警告
3. deprecated\s+(?:function|class|method)  - 已棄用 API
```
