# PM Stale Ticket Cleanup Session 方法論

## 核心概念

Stale ticket（pending > 7 天）claim 前必先執行三步驗證判定路徑分叉，再依結果選擇 bookkeeping（驗證收尾）或實際修復。PM 可依成本判斷自行前台修復或派發代理人。

## 三步驗證（claim 前必做）

| 步驟 | 動作 | 目的 |
|------|------|------|
| 1 | `grep` / 執行目標測試，確認問題是否仍存在 | 排除已消失問題 |
| 2 | `git log --all` 查是否有外溢修復 commit | 判定路徑分叉（含跨 wave 查詢） |
| 3 | 確認外溢修復完整性或問題仍存在 | 選定執行路徑 |

`git log` 必須含 `--all` 或查跨 wave commit——外溢修復可能來自不同 wave 的批次清理（如 W1 ANA spawn 修復 W4 ticket 問題）。

## 路徑分叉

| 第二步結果 | 路徑 | 動作 |
|-----------|------|------|
| 有外溢修復 | **Bookkeeping** | 驗證修復有效 → 記錄根因鏈 + 外溢 commit SHA → complete |
| 無外溢修復，問題仍在 | **實際修復** | 評估修復成本 → PM 前台修或派發代理人 |
| 無外溢修復，問題已消失 | **環境變化收尾** | 紀錄消失原因 → close with reason |

## PM 前台修復判準

PM 可前台修復（不派發代理人）的條件——全部滿足才適用：

- 修改屬規格層（測試斷言調整、文件更新），無 `src/` 變更
- 單檔案 + 有限 Edit（<= 5 個）
- PM 已完成診斷，不需代理人探索
- 預估成本 <= 派發溝通成本

## 代理人自主執行判準

ticket 可派發代理人全自主（self-managed）的條件：

- Problem Analysis 已完整（根因 + 影響範圍 + 策略選擇）
- 修改範圍邊界清晰，代理人不需反問 PM
- Worktree merge 責任須明確（代理人 self-merge 或 PM 接手）

## 檢查清單

- [ ] claim 前已執行三步驗證？
- [ ] git log 查詢範圍含跨 wave commit（`--all`）？
- [ ] 路徑分叉已確定（bookkeeping / 實際修復 / 環境變化）？
- [ ] PC-162 注意：ticket 描述可能與現況漂移，以三步驗證結果為準
- [ ] Bookkeeping 路徑：外溢修復 commit SHA 已記錄於 Problem Analysis？
- [ ] 實際修復路徑：PM 前台修 vs 派發已依判準決定？

## Reference

- `.claude/error-patterns/process-compliance/PC-055-ticket-ac-drift-undetected.md` — AC 與實況漂移
- `.claude/error-patterns/process-compliance/PC-167-analysis-agent-worktree-no-write-transcribe-burden.md` — 分析代理人 worktree 轉錄負擔
- `.claude/error-patterns/process-compliance/PC-162-*.md` — Stale 描述漂移
- `.claude/methodologies/case-studies/v0.19.0-W4-session-2026-05-31.md` — 8 case source data
- `feedback_stale_ticket_cleanup_sop` — Memory: stale claim 三步驗證
- `feedback_pm_test_perf_direct_edit_sop` — Memory: PM 前台修 tests/perf/
- `feedback_analysis_agent_worktree_partial_commit` — Memory: 分析代理人 worktree partial commit

---

**Last Updated**: 2026-06-20
**Version**: 1.0.0 — 初始建立，提取自 v0.19.0 W4 session source data（8 case，四組 SOP），冷卻期 20 天觀察命中率 >50% 達提取門檻
**Source**: 1.1.0-W1-017
