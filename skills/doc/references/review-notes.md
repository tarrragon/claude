# 審查記錄

## 2026-03-30 多視角審查（兩輪）

### 已修復項目

| # | 項目 | 修復 commit |
|---|------|-----------|
| 1 | references 模板路徑指向 docs/（已改為 Skill） | 66503a9 |
| 2 | PROP-004 缺反向引用 W2 Tickets | 66503a9 |
| 3 | tracking.yaml 缺 PROP-004/005 entry | 66503a9 |
| 4 | usecase 模板缺 platform/extension_status | 66503a9 |
| 5 | SKILL.md 未標記 CLI 未實作 | 66503a9 |
| 6 | PROP-000 檔案名缺 PROP- 前綴 | e3a39db |
| 7 | PROP-005 引用鏈斷裂 | e3a39db |
| 8 | spec-template analytics/security 無效值 | e3a39db |
| 9 | tracking.yaml done 項 verified_by 為 null | e3a39db |
| 10 | proposals.md 欄位表不完整 | 本次 |
| 11 | W2 驗收條件量化 | 本次 |
| 12 | W2-002 P0 理由補充 | 本次 |
| 13 | withdrawn 語義擴展涵蓋「被否決」 | 本次 |
| 14 | proposals.md source 欄位補充允許值 | 本次 |

### 用戶否決的建議

| 建議 | 否決理由 |
|------|---------|
| 砍掉 tracking.yaml checklist（DRY 違反） | 需求生命週期 != 任務生命週期，提案可能被撤回或需求變更 |
| 砍掉 CLI 到 2 個命令 | 查詢精確性是長期需求，避免 grep 產生大量不相關結果 |

### 設計評分

| 輪次 | 評分 | 說明 |
|------|------|------|
| 第一輪 | Acceptable（含 Garbage 項） | 過度簡化建議被否決 |
| 第二輪 | Acceptable（無 Garbage） | 修正後骨架合理，整合章節 Good taste |

---

## 2026-03-30 W4-001 三視角審查（品質/架構/設計）

### 修復 Ticket

0.16.2-W4-002：修復 /doc 文件引用不一致（8 項修復）

### 用戶否決的建議（第三次重複提出）

| 建議 | 否決理由 | 歷史 |
|------|---------|------|
| 砍掉 tracking.yaml checklist | 需求生命週期 != 任務生命週期 | 第二次否決（同第一輪） |
| 砍掉 CLI 到 2 個命令 | 查詢精確性是長期需求 | 第二次否決（同第一輪） |
| proposal-evaluation-guide 精簡 | .claude/ 是跨專案通用框架，資安維度對其他專案適用 | 新提出，否決 |
| proposal-template 12 → 5 欄位 | 每個欄位都有結構化用途（導航/分類/排程），砍掉會讓 nav 功能失效 | 新提出，否決 |
