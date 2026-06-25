# 教學撞牆記錄與回補流程 — 以 Challenge 001/002 為例

設計 Use Case 時發現教學假設和實際場景對不上——接下來怎麼辦？

本專案以 blog 教學文章作為設計決策的權威來源（SOT），實作必須對齊教學。以下展示發現教學缺口時的處理流程：記錄 challenge → 回補教學 → 更新 `sync-pending.md`（教學同步待辦清單）。

---

## 場景 1：UseCase 設計階段發現教學缺口（Challenge 001）

### 發現

設計 UC-04（Python SDK 場景）時發現：教學假設 SDK 跑在長期 app 中，但 Hook 是 <1 秒的短命腳本。daemon thread 和 flush interval 全無效。

### 記錄

建立 `docs/challenges/001-teaching-gaps-from-usecase-design.md`：

```markdown
# UC 設計階段發現的教學缺口

## 發現時機
2026-06-21，UseCase 設計階段。

## Gap 清單
| Gap | 主題 | 教學假設 | 實際場景 | 優先級 |
|-----|------|---------|---------|--------|
| Gap-2 | 短生命週期腳本 | 長期 app | <1 秒 Hook | P0 |
| Gap-5 | 聚合查詢 | 逐筆篩選 | 分群統計 | P0 |
...

## 建議教學補充方向
每個 Gap 附具體的教學章節和補充建議。
```

### 更新 sync-pending

```markdown
- [ ] 2026-06-21: [P0] 短生命週期腳本的 SDK 行為
  → monitoring/05-platform-adaptation/python-platform.md
```

### 回補教學

在 blog repo 建 feature branch，寫入教學補充：

```bash
cd ~/project/blog
git checkout -b feat/monitor-teaching-backfill-001
# 編輯 python-platform.md 新增「短生命週期腳本」章節
git commit -m "docs(monitoring): 短生命週期腳本 SDK 行為"
```

### 標記完成

sync-pending 更新為 `[synced]`，標記分支和 commit。

## 場景 2：Spec 設計與教學偏移（Challenge 002）

### 發現

Spec review 時發現 SaaS 訪談推導出的設計與教學衝突（5 處偏移）。

### 記錄

建立 `docs/challenges/002-spec-teaching-drift.md`，含偏移清單和根因分析。

### 處理偏移

1. **Spec 對齊教學**（高嚴重度）：查詢端點路徑改回教學定義
2. **教學回補**（缺口）：DDL 欄位在教學中補齊

### 流程改善

Challenge 003 進一步發現「Spec 補缺口時跳過教學確認」的流程反模式。修正：CLAUDE.md 強制操作擴充。

## 操作清單

教學缺口不記錄的話，同一個問題會在下次版本重現——v0.2 的 Challenge 002 正是因為缺口未被追蹤而再次偏移。

遇到教學缺口或偏移時（格式見 `docs/challenges/README.md`）：

1. 記錄到 `docs/challenges/NNN-{描述}.md`
2. 更新 `docs/sync-pending.md`（未同步項標 `- [ ]`）
3. 在 blog repo 建 feature branch 回補
4. 同步完成後在 sync-pending 標 `[synced]`
5. 如發現流程缺口，建 ANA ticket 追蹤改善
