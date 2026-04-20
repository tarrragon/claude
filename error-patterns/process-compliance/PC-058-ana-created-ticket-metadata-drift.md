---
id: PC-058
title: ANA 代理人建立 follow-up Ticket 的 metadata 權威性不足
category: process-compliance
severity: medium
related:
 - PC-055
 - PC-057
---

# PC-058: ANA 代理人建立 follow-up Ticket 的 metadata 權威性不足

## 現象

ANA 代理人（如 saffron-system-analyst）完成分析後建立 follow-up IMP/DOC Ticket 時，metadata 欄位（`who`、`acceptance`、`tdd_phase`）可能不符合專案實況：

| 欄位 | 常見漂移 |
|------|---------|
| `who` | 指派語言無關預設（如 parsley-flutter-developer），但專案語言不符 |
| `acceptance` | 單一 bullet 塞多條件，違反 1-item-1-check 原則 |
| `tdd_phase` | 預設 phase1-4 全流程，未評估中等改動是否可簡化 |
| `where.files` | 引用分析時讀取的檔案，未驗證寫入目標正確性 |

## 觸發情境

- ANA 代理人 WRAP 分析後建立 IMP Ticket
- 代理人不持有專案全域知識（CLAUDE.md 指定的語言、慣用代理人）
- PM 未在派發前驗證 Ticket metadata

## 本案實例

- **某 Ticket ANA**（saffron）完成後建立某 Ticket IMP
- 原始 metadata：
 - `who: parsley-flutter-developer`（Flutter 代理人）
 - 專案實況：`.claude/skills/ticket/` 是 Python CLI（uv + Python 3）
 - `acceptance: [單一 bullet 塞 6 條件]`
- PM 於派發前人工修正：
 - `who` → `thyme-python-developer`
 - `acceptance` 拆為 6 項獨立 check item

## 影響

| 若未發現 | 後果 |
|---------|------|
| who 錯誤 | 派發後代理人能力不符，回報「無法執行」或寫出不符專案慣例的程式碼 |
| acceptance 單一 bullet | CLI 無法逐項 check-acceptance，驗收變人工審閱 |
| TDD phase 過多 | 中等改動強走 4 階段流程，浪費代理人時段 |

## 防護措施

### 短期（PM 行為）

PM 驗收 ANA 產出的 follow-up Ticket 時，強制檢查清單：

- [ ] `who` 與專案實際使用的代理人（CLAUDE.md 語言對應）一致？
- [ ] `acceptance` 每項為獨立 1 條件？
- [ ] `tdd_phase` 與 task 範疇匹配（小改動不走完整 TDD）？
- [ ] `where.files` 為寫入目標，非分析參考檔？

### 長期（框架改善）

建議建立 Hook：ANA 類 Ticket 建立後自動掃描新生成的 follow-up Ticket，對照 CLAUDE.md 的 `實作代理人` 欄位，發現不符時 block 並提示 PM 修正。

### ANA 代理人 prompt 強化

在派發 ANA 代理人時，prompt 必須明確附上：
- 專案語言與代理人對照（CLAUDE.md 摘要）
- acceptance 格式要求（1-item-1-check）
- TDD phase 評估原則（依改動範疇決定）

## 與其他 pattern 的關係

- **PC-055**（Ticket AC drift）：本 pattern 的發生源頭之一 — 代理人建立的 Ticket metadata 未經驗證，後續會持續漂移
- **PC-057**（PM prompt exceeds agent responsibility）：反向情境 — 本 pattern 是代理人產出超過其知識邊界；PC-057 是 PM 派發超過代理人職責

## 檢測方式

Ticket 建立後，比對：
```
Ticket.who vs CLAUDE.md "實作代理人" 欄位
Ticket.acceptance 每項長度 < 100 字元且無「;」分隔多條件
Ticket.tdd_phase = {null, phase1, phase1-4} 依改動範疇
```

## 記錄於 Memory

對應 memory 項目：`feedback_ana_created_ticket_metadata_drift.md`
