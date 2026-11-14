# Ticket 檔案命名清單（現存後綴清單）

> 來源：`.claude/references/ticket-id-conventions.md` 第 4 節外放

本清單列出專案實際使用的所有後綴檔案樣式，已被系統識別為有效。檔名以 `<ticket-id>` 代表票號本體，`v` 前綴變體另行標註；括號內數字為該樣式的現存檔案數。

---

## TDD Phase 文件 - Phase 1（設計）
1. `<ticket-id>-phase1-design.md`（3 個）
2. `<ticket-id>-phase1-feature-spec.md`（1 個）
3. `v<ticket-id>-feature-design.md`（1 個，`v` 前綴變體）

## TDD Phase 文件 - Phase 2（測試設計）
4. `<ticket-id>-phase2-test-design.md`（4 個）
5. `v<ticket-id>-phase2-test-design.md`（1 個，`v` 前綴變體）
6. `<ticket-id>-phase2-tests.md`（2 個；變體：`-tests` 代替 `-test-design`）
7. `<ticket-id>-test-design.md`（1 個；縮寫：`-test-design` 代替 `-phase2-test-design`）

## TDD Phase 文件 - Phase 3a（策略）
8. `<ticket-id>-phase3a-strategy.md`（5 個）
9. `v<ticket-id>-phase3a-strategy.md`（1 個，`v` 前綴變體）

## TDD Phase 文件 - Phase 3b（執行和測試）
10. `<ticket-id>-test-case-design.md`（1 個；Phase 2 變體：`-test-case-design`）
11. `<ticket-id>-phase3b-test-report.md`（1 個）
12. `<ticket-id>-phase3b-execution-log.md`（1 個）
13. `<ticket-id>-phase3b-execution-report.md`（1 個）
14. `v<ticket-id>-phase3b-execution-report.md`（1 個，`v` 前綴變體）

## TDD Phase 文件 - Phase 4（重構）
15. `<ticket-id>-refactoring-report.md`（1 個）
16. `<version>-W<wave>-refactor.md`（1 個，無序號的波次級檔名）
17. `v<ticket-id>-refactor.md`（2 個，`v` 前綴變體）

## 分析和報告
18. `<ticket-id>-test-cases.md`（1 個）
19. `<ticket-id>-test-cases-quick-reference.md`（1 個）
20. `<ticket-id>-analysis.md`（1 個）
21. `<ticket-id>-uc-analysis.md`（1 個）

## 邊界情況（具體描述性後綴）
22. `v<version>-refactor-ticket-cli-set-relations.md`（非常具體的模組名稱後綴：`-refactor-ticket-cli-set-relations`，**不納入白名單**）
23. `v<version>-onboarding-framework.md`（內容描述後綴：`-onboarding-framework`，**不納入白名單**）

## 非規範檔案（需更正）
24. `W41-refactor-worklog.md`（**非規範格式**：缺少版本號前綴，應改為 `<version>-W41-xxx-refactor-worklog.md`）

---

## 現狀摘要

清單中 32 個正規檔案均可被 `extract_core_ticket_id()` 函式正確解析，並在 `list_tickets()` 中進行去重載入。2 個邊界檔案因其過度具體的描述後綴**故意不納入白名單**（目的是讓這類"一次性"後綴受到 Hook 警告，提醒檔案命名是否合適），1 個非規範檔案需修正。

---

**Last Updated**: 2026-03-13
**Source**: ticket-id-conventions.md 第 4 節外放
