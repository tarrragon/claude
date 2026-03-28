# SessionStart 效能監控

SessionStart Hook 數量多（目前 13 個），累積延遲影響用戶體驗。

---

## 效能閾值

| 指標 | 閾值 | 超過時處理 |
|------|------|-----------|
| 單一 Hook 執行時間 | 5 秒 | 優化或降級 |
| 所有 SessionStart Hook 總時間 | 15 秒 | 評估哪些可移至背景 |
| Hook 數量 | 15 個 | 評估合併或移除 |

---

## 監控方式

定期檢查 SessionStart 總延遲，使用 hook-health-check 輸出的時間戳評估。

---

## 優化策略

| 策略 | 適用場景 |
|------|---------|
| 快取結果 | 每次都重新計算但結果很少變化的 Hook |
| 合併 Hook | 功能相近的多個 Hook 合併為一個 |
| 延遲載入 | 非關鍵的檢查移至首次需要時執行 |

---

## 相關文件

- .claude/pm-rules/hook-change-review.md - Hook 修改審核流程
- .claude/rules/core/quality-baseline.md - 品質基線（規則 4：Hook 失敗必須可見）

---

**Last Updated**: 2026-03-27
**Version**: 1.0.0 - 初始版本，定義 SessionStart 效能監控閾值和優化策略（0.2.1-W1-008）
