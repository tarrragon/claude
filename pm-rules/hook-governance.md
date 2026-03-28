# Hook 治理規則

Hook 是系統治理的核心基礎設施。本文件涵蓋 Hook 修改審核和 SessionStart 效能監控。

---

## Hook 修改審核

### 審核層級

| 修改類型 | 審核要求 |
|---------|---------|
| 新增 Hook | PM 評估必要性 + 測試驗證 |
| 修改既有 Hook 行為 | PM 確認影響範圍 + AST 語法驗證 |
| 刪除 Hook | PM 確認無依賴 + 記錄刪除原因 |
| 降級 Hook（如 AUTO→WARN） | 建立 Ticket 追蹤，記錄降級原因 |

### 驗證清單

- [ ] Python AST 語法驗證通過
- [ ] Hook 不影響其他 Hook 的運作
- [ ] settings.json 中的 Hook 註冊已更新（如適用）
- [ ] 修改原因已記錄在 Ticket 或 commit 訊息中

---

## SessionStart 效能監控

SessionStart Hook 數量多（目前 13 個），累積延遲影響用戶體驗。

### 效能閾值

| 指標 | 閾值 | 超過時處理 |
|------|------|-----------|
| 單一 Hook 執行時間 | 5 秒 | 優化或降級 |
| 所有 SessionStart Hook 總時間 | 15 秒 | 評估哪些可移至背景 |
| Hook 數量 | 15 個 | 評估合併或移除 |

### 監控方式

使用 hook-health-check 輸出的時間戳評估 SessionStart 總延遲。

**執行指令**：

```bash
# 查看 SessionStart Hook 執行時間（從 hook-health-check 輸出中提取）
# hook-health-check 在每次 SessionStart 時自動執行，輸出包含每個 Hook 的時間戳

# 手動檢查所有 SessionStart Hook 數量
grep -c '"SessionStart"' .claude/settings.json

# 檢查 Hook 健康狀態輸出
# SessionStart 時自動輸出，格式：[timestamp] [INFO] [OK] hook-name.py (last update: Xh ago)
```

**檢查頻率**：

| 頻率 | 觸發條件 |
|------|---------|
| 每次新增 Hook 後 | 確認總數未超過 15 個閾值 |
| 版本收尾時 | 評估是否有可合併或移除的 Hook |
| 用戶反饋啟動慢時 | 即時排查 |

### 優化策略

| 策略 | 適用場景 |
|------|---------|
| 快取結果 | 每次都重新計算但結果很少變化的 Hook |
| 合併 Hook | 功能相近的多個 Hook 合併為一個 |
| 延遲載入 | 非關鍵的檢查移至首次需要時執行 |

---

## 相關文件

- .claude/rules/core/quality-baseline.md - 品質基線（規則 4：Hook 失敗必須可見）
- .claude/pm-rules/incident-response.md - 事件回應流程

---

**Last Updated**: 2026-03-28
**Version**: 1.0.0 - 合併 hook-change-review.md + session-start-performance.md（0.2.1-W3-002）
