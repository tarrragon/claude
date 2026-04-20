# PC-094: TD 清單即時校準缺失

## 基本資訊

- **Pattern ID**: PC-094
- **分類**: 流程合規（process-compliance）
- **來源版本**: v0.18.0
- **發現日期**: 2026-04-19
- **風險等級**: 低-中
- **相關 Pattern**: PC-093（YAGNI 累積反模式）

---

## 問題描述

### 症狀

TD（Technical Debt）在 Phase 3a/3b 中段已實際處理，但 Phase 1 寫下的 TD 清單未即時更新，導致 Phase 4 評估時將「已完成項」誤認為「待處理項」，造成評估偏差或重複建立 follow-up Ticket。

### 表現形式

| 表現 | 說明 |
|------|------|
| TD 清單與實作演進脫鉤 | 4 視角逐項判斷時才發現「已處理」 |
| Phase 4 評估才校準 | 應該在每個 Phase 結束就校準 |
| Follow-up Ticket 重複建立 | 已完成的 TD 被誤建為延後追蹤 Ticket |
| 後續 Ticket 以過時 TD 當路線圖 | 子 Ticket 規劃以 TD 清單為依據，誤導實作方向 |

---

## W10-017.8 案例

### TD4: ticket-query 全掃瞄風險

- Phase 1 列出：「改用 --version --status 過濾版 CLI」
- Phase 3a C4 修正：實作已傳 `--status in_progress`
- Phase 4 4 視角發現：TD 描述與程式碼實況不符
- 應在 Phase 3a 修正時即時關閉 TD4

### TD7: uncommitted=-1 哨兵值

- Phase 1 列出：「考慮 Optional[int] 或 Sentinel 物件」
- Phase 3a C3 修正：已改 `Optional[int] = None`
- Phase 4 4 視角發現：仍掛在 TD 清單
- 應在 Phase 3a C3 落地時即時關閉 TD7

---

## 根因分析

### 直接原因

TD 清單視為 Phase 1 一次性產物，未建立「Phase 演進中校準」機制。

### 深層原因

| 動機類型 | 表面說法 | 深層動機 |
|---------|---------|---------|
| A 文件靜態化 | 「TD 清單是 Phase 1 規劃」 | 把規劃文件當不可變紀錄 |
| B 校準成本 | 「Phase 演進每次校準麻煩」 | 校準成本評估錯誤（其實低） |
| C 流程缺失 | 「沒人提醒要校準」 | 缺乏 hook 或檢查機制 |

---

## 防護機制

### 規則建議

1. **每 Phase 結束強制 TD 校準**：Phase 3a/3b/4 結束時，逐項核對 TD 清單，標註「已處理」「無需處理」「仍待處理」三狀態。

2. **TD 清單版本化**：在 ticket md 中維護 TD 演進記錄，不只列「Phase 1 識別 7 TD」也列「Phase 3a 處理 2 TD」「Phase 4 處理 4 TD」。

3. **CLI 校準提示**：`ticket track tdd-status <id> --check-td-drift` 比對 TD 清單與 commit 訊息中的 TD 引用，提示可能的校準缺失。

4. **Phase 4 評估前 TD 清單預檢**：派發 4 視角前 PM 先逐項核對 TD 清單與 commit 歷史，校準後再派發，避免視角浪費 token 在已處理項上。

---

## 與 PC-090/PC-093 的關係

| Pattern | 焦點 |
|---------|------|
| PC-090 | close 時機判斷錯誤 |
| PC-093 | YAGNI 累積（推測性抽象延後） |
| PC-094 | TD 清單與實作脫鉤 |

三者均涉及「Phase 演進中的決策管理」，但角度不同：PC-090 是收尾、PC-093 是源頭、PC-094 是過程。

---

**Last Updated**: 2026-04-19
**Version**: 1.0.0
**Source**: W10-017.8 Phase 4 parallel-evaluation 4 視角共識
