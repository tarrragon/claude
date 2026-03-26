# Ticket 檔案命名清單（現存後綴清單）

> 來源：`.claude/references/ticket-id-conventions.md` 第 4 節外放

本清單列出專案實際使用的所有後綴檔案，已被系統識別為有效。

---

## TDD Phase 文件 - Phase 1（設計）
1. `0.1.0-W11-004-phase1-design.md`
2. `0.1.0-W22-007-phase1-design.md`
3. `0.1.0-W39-001-phase1-design.md`
4. `0.1.0-W41-002-phase1-feature-spec.md`
5. `v0.1.0-W44-003-feature-design.md`

## TDD Phase 文件 - Phase 2（測試設計）
6. `0.1.0-W1-005-phase2-test-design.md`
7. `0.1.0-W11-004-phase2-tests.md`（變體：`-tests` 代替 `-test-design`）
8. `0.1.0-W22-007-phase2-tests.md`（變體：`-tests` 代替 `-test-design`）
9. `0.1.0-W39-001-phase2-test-design.md`
10. `0.1.0-W41-001-phase2-test-design.md`
11. `0.1.0-W41-002-phase2-test-design.md`
12. `0.1.0-W43-006-test-design.md`（縮寫：`-test-design` 代替 `-phase2-test-design`）
13. `v0.1.0-W44-003-phase2-test-design.md`

## TDD Phase 文件 - Phase 3a（策略）
14. `0.1.0-W11-004-phase3a-strategy.md`
15. `0.1.0-W22-007-phase3a-strategy.md`
16. `0.1.0-W39-001-phase3a-strategy.md`
17. `0.1.0-W41-001-phase3a-strategy.md`
18. `0.1.0-W41-002-phase3a-strategy.md`
19. `v0.1.0-W44-003-phase3a-strategy.md`

## TDD Phase 文件 - Phase 3b（執行和測試）
20. `0.1.0-W37-002-test-case-design.md`（Phase 2 變體：`-test-case-design`）
21. `0.1.0-W39-001-phase3b-test-report.md`
22. `0.1.0-W44-003-phase3b-execution-log.md`
23. `0.1.0-W41-001-phase3b-execution-report.md`
24. `v0.1.0-W44-003-phase3b-execution-report.md`

## TDD Phase 文件 - Phase 4（重構）
25. `0.1.0-W2-014-refactoring-report.md`
26. `0.1.0-W39-refactor.md`
27. `v0.1.0-W44-003-refactor.md`
28. `v0.2.0-W3-001-refactor.md`

## 分析和報告
29. `0.1.0-W1-005-test-cases.md`
30. `0.1.0-W1-005-test-cases-quick-reference.md`
31. `0.1.0-W25-005-analysis.md`
32. `0.1.1-W1-004-uc-analysis.md`

## 邊界情況（具體描述性後綴）
33. `v0.1.0-refactor-ticket-cli-set-relations.md`（非常具體的模組名稱後綴：`-refactor-ticket-cli-set-relations`，**不納入白名單**）
34. `v0.2.0-onboarding-framework.md`（內容描述後綴：`-onboarding-framework`，**不納入白名單**）

## 非規範檔案（需更正）
35. `W41-refactor-worklog.md`（**非規範格式**：缺少版本號前綴，應改為 `0.1.0-W41-xxx-refactor-worklog.md`）

---

## 現狀摘要

清單中 32 個正規檔案均可被 `extract_core_ticket_id()` 函式正確解析，並在 `list_tickets()` 中進行去重載入。2 個邊界檔案因其過度具體的描述後綴**故意不納入白名單**（目的是讓這類"一次性"後綴受到 Hook 警告，提醒檔案命名是否合適），1 個非規範檔案需修正。

---

**Last Updated**: 2026-03-13
**Source**: ticket-id-conventions.md 第 4 節外放（0.1.0-W48-004）
