# PC-003: 跨版本未完成任務靜默遺漏

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-003 |
| 類別 | process-compliance |
| 來源版本 | v0.2.0 |
| 發現日期 | 2026-03-05 |
| 風險等級 | 高 |
| 來源 | 0.2.0-W5-001 發現過程 |

### 症狀

1. 執行 `ticket track summary` 只顯示最新版本（如 v0.3.0），回報「沒有 Tickets」
2. PM 據此判斷無待辦任務，實際上 v0.1.0 有 9 個 pending Ticket 未處理
3. 版本已從 v0.1.0 推進到 v0.3.0，前版本任務完全被遺忘
4. 問題不會自動浮現，只有在手動指定 `--version 0.1.0` 時才能發現

### 根本原因（5 Why 分析）

1. Why 1：PM 查詢任務時只看到 v0.3.0 的空結果
2. Why 2：`ticket track summary/list` 預設只顯示當前 active 版本，不交叉檢查其他版本
3. Why 3：版本偵測邏輯（`get_current_version()`）設計為回傳單一版本，不考慮歷史版本狀態
4. Why 4：版本推進流程（`/version-release`）未檢查前版本是否有未完成任務
5. Why 5：根本原因：**系統缺乏跨版本任務完整性檢查機制**，版本推進和任務查詢都是單版本視角

---

## 解決方案

### 已修復：跨版本警告（0.2.0-W5-001）

在 `execute_summary` 和 `execute_list` 結尾新增 `_print_cross_version_warning()`，掃描所有版本目錄，若其他版本有 pending/in_progress Ticket 則輸出警告。

```
[WARNING] 其他版本有未完成的 Ticket：
   v0.1.0: 9 個 pending, 0 個 in_progress
   使用 --version <version> 查看詳情
```

### 待修復：版本推進防護（0.2.0-W5-002）

在 `/version-release check` 中新增前版本未完成任務檢查，阻止在有遺留任務時推進版本。

---

## 預防措施

### 已實作

| 措施 | 說明 | 位置 |
|------|------|------|
| 跨版本警告 | summary/list 自動顯示其他版本未完成任務 | track_query.py `_print_cross_version_warning()` |

### 待實作

| 措施 | 說明 | Ticket |
|------|------|--------|
| 版本推進阻擋 | /version-release check 檢查前版本 | 0.2.0-W5-002 |

---

## 行為模式分析

此模式屬於「靜默遺漏」類型：

- **系統沒有報錯**，回傳的資訊在技術上是正確的（v0.3.0 確實沒有 Ticket）
- **資訊不完整**導致決策錯誤（PM 以為沒有待辦任務）
- **需要主動查詢**才能發現問題（指定 --version）
- **隨時間惡化**：版本越多，遺漏的任務越難被發現

### 類似風險場景

| 場景 | 風險 |
|------|------|
| 跨 Wave 任務遺漏 | summary 只顯示指定 Wave，其他 Wave 的任務被忽略 |
| blocked Ticket 長期未處理 | 被阻塞的任務沒有定期提醒機制 |
| 版本完成後殘留任務 | 版本標記完成但仍有 pending Ticket |

---

## 相關文件

- 0.2.0-W5-001 - 跨版本警告實作
- 0.2.0-W5-002 - 版本推進防護（待處理）
- .claude/rules/flows/version-progression.md - 版本推進決策規則
