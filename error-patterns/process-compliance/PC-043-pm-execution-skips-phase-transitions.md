# PC-043: PM 直接執行 Ticket 時跳過階段轉換和欄位更新

## 錯誤症狀

PM 直接執行 DOC/ANA 類型 Ticket 時，claim 後一口氣做完所有工作再 complete，中間不更新 Ticket 的 5W1H 欄位和執行日誌。Ticket 檔案中 when/where/how 停留在「待定義」，執行日誌在最後才補填或被 CLI 警告才補。

## 根因分析

**直接原因**：ticket-lifecycle 認領階段沒有「5W1H 待定義欄位補全」的強制步驟，執行階段沒有「階段轉換時即時填寫日誌」的要求。

**深層原因**：
1. PM 作為 AI，沒有「主動回頭更新文件」的內在驅動力——必須靠規則強制
2. session context 中已有所有資訊，PM 感覺「不需要」寫回 Ticket，但 session 是臨時的，Ticket 是持久的
3. 規則只定義了「完成前必須填寫執行日誌」，沒有定義「何時填寫」

## 影響

| 影響 | 說明 |
|------|------|
| 資訊只留 session | 如果 session 被 clear 或 compact，決策過程無法追溯 |
| Ticket 失去追蹤價值 | when/where/how 為「待定義」的 Ticket 無法被其他 session 復用 |
| 跨 session 接手困難 | 下個 session resume 時只看到空白的執行日誌 |

## 正確做法

1. claim 後立即檢查 when/where/how，待定義的必須先更新（set-when/set-where/set-how）
2. 分析完成時 append-log Problem Analysis，不等最後才補
3. 每完成一個 AC 時 append-log Solution，記錄進度
4. 驗證完成時 append-log Test Results

核心原則：Ticket 是資訊的持久化載體，session context 是臨時的。

## 預防措施

| 措施 | 類型 | 狀態 |
|------|------|------|
| ticket-lifecycle 認領階段新增 5W1H 補全（強制） | 規則更新 | 已完成（W3-010.1） |
| ticket-lifecycle-phases 執行階段新增即時日誌要求 | 規則更新 | 已完成（W3-010.1） |
| claim 後 CLI checklist 新增待定義欄位提醒 | CLI 改善 | 待實施 |

## 發現來源

- Ticket: W3-006, W3-009 執行過程
- 場景：PM 直接執行 DOC Ticket，claim → 修改檔案 → complete，中間未更新 5W1H 和執行日誌
- 日期：2026-04-06

## 相關錯誤模式

- PC-042: 規則文件過長導致代理人回合耗盡

---

**Created**: 2026-04-06
**Version**: 1.0.0
