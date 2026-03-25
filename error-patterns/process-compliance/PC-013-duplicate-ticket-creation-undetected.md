# PC-013: 重複 Ticket 建立未被偵測

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-013 |
| 類別 | process-compliance |
| 來源版本 | v0.1.0 |
| 發現日期 | 2026-03-12 |
| 風險等級 | 低 |
| 來源 | 0.1.0-W41-003/W41-004 釐清過程 |

### 症狀

1. 同一 Wave 中出現兩個標題高度相似的 Ticket（W41-003 和 W41-004）
2. 兩者目標完全相同：統一活躍 Hook 中重複的 `get_project_root` 定義
3. 其中一個（W41-003）有具體的 4 個檔案清單，另一個（W41-004）完全空白
4. 建立後審核（acceptance-auditor + system-analyst）未偵測到重複

### 根本原因（5 Why 分析）

1. Why 1：同一批次建立了兩個功能重疊的 Ticket
2. Why 2：批次建立時未交叉比對同 Wave 其他 Ticket 的標題和目標
3. Why 3：`/ticket create` 流程無「重複偵測」機制
4. Why 4：建立後審核（creation_accepted 流程）的 system-analyst 審查項目不含「與同 Wave 其他 Ticket 比對」
5. Why 5：根本原因：Ticket 建立流程缺乏**同 Wave 重複偵測**步驟

---

## 解決方案

### 正確做法

建立 Ticket 前，先查詢同 Wave 是否有相似目標的 Ticket：

```bash
# 查看同 Wave 所有 Ticket
ticket track list --wave {n}

# 搜尋相似標題
grep -r "get_project_root" docs/work-logs/v{version}/tickets/ --include="*.md" -l
```

### 預防措施

1. **建立後審核補充**：system-analyst 審查時應包含「同 Wave 重複 Ticket 比對」檢查項
2. **批次建立時**：PM 應先列出所有計畫建立的 Ticket 清單，人工去重後再執行建立
3. **長期改善**：考慮在 `/ticket create` 加入同 Wave 標題相似度警告

### 錯誤做法

| 錯誤 | 說明 |
|------|------|
| 不檢查直接建立 | 可能導致重複工作或混亂 |
| 發現重複後兩個都保留 | 浪費追蹤資源，增加認知負擔 |
| 刪除有內容的那個 | 應保留資訊更完整的 Ticket |

---

## 影響範圍

| 項目 | 影響 |
|------|------|
| 直接影響 | 浪費 Ticket 管理成本，可能導致重複派發 |
| 間接影響 | 增加 Wave 管理認知負擔 |
| 風險等級 | 低（發現後易修正，刪除重複即可） |

---

## 再發案例

### 案例 2：跨 Ticket 子任務功能重疊（2026-03-23）

| 項目 | 值 |
|------|------|
| 來源 | 0.1.2-W3-002 Phase 4a 審查 |
| 症狀 | PM 為審查發現的既有 Bug（detect_vague_acceptance 永遠回傳 True）建立 W3-003，但 W3-001.2 已涵蓋完全相同問題（vague_passed dead branch） |
| 根因 | 建立修復 Ticket 前未查詢既有 pending Ticket，且問題分散在不同父任務的子任務中不易察覺 |
| 處理 | 刪除 W3-003，確認 W3-001.2 已涵蓋 |

**新增教訓**：重複不僅發生在「同 Wave 標題相似」，也會發生在「跨 Ticket 子任務功能重疊」場景。建立修復 Ticket 前，除了 `ticket track list --wave {n}`，還需 `grep` 搜尋問題關鍵字（如函式名）確認無重複。

---

## 相關資訊

| 項目 | 值 |
|------|------|
| 相關 Ticket | 0.1.0-W41-003, 0.1.0-W41-004（已刪除）; 0.1.2-W3-003（已刪除，與 W3-001.2 重複） |
| 防護機制 | 建議：system-analyst 審查清單補充重複比對；建立修復 Ticket 前強制查詢 pending tickets |
| 相關錯誤模式 | PC-002（Ticket 設計未確認現有類似實作） |
