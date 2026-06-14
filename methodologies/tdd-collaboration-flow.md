# TDD 協作開發流程（30 秒核心）

> **本檔已瘦身（W8-018.1）**：完整 Phase 0-4 流程主體已外移至 `/tdd` skill（`.claude/skills/tdd/`），本檔僅保留 30 秒複習清單與路由。需要任何階段的完整操作指引時，直接讀對應的 skill references，不要在本檔尋找細節。

TDD 不只是「測試先寫」，而是設計師導向的團隊協作流程：在實作前透過分階段角色分工想清楚需求、規格、測試與品質。

---

## 四角色分工（30 秒）

| 角色 | 職責 | 對應 Phase |
|------|------|-----------|
| 功能設計師 | 需求分析與功能規劃 | Phase 1 |
| 測試工程師 | 測試案例設計與實作 | Phase 2 |
| 實作工程師 | 策略規劃與程式碼實作 | Phase 3a / 3b |
| 重構設計師 | 程式碼品質改善與架構優化 | Phase 4 |

## 五大協作原則（30 秒）

1. 工作日誌驅動：每階段記錄思考過程與交接資訊
2. 角色明確分工：每角色有明確職責與交付物
3. 文件化交接：透過工作日誌傳遞知識
4. 測試先行：沒有測試不寫程式碼
5. 品質不妥協：每階段有品質門檻，不達標不進入下一階段

## Phase 0-4 一覽（30 秒）

| Phase | 目標 | 完整指引 |
|-------|------|---------|
| Phase 0 | 系統一致性確認、避免重複造輪子 | `.claude/skills/tdd/references/phase0-sa-review.md` |
| Phase 1 | 功能規格、API 介面、驗收標準、SOLID 拆分、行為場景 | `.claude/skills/tdd/references/phase1-design.md` |
| Phase 2 | 測試策略、BDD/Given-When-Then、Mock 策略 | `.claude/skills/tdd/references/phase2-test-design.md` |
| Phase 3a / 3b | 策略規劃、拆分評估、程式碼實作、品質基準 | `.claude/skills/tdd/references/phase3-implementation.md` |
| Phase 4 | 多維度重構分析、重構執行、預期管理、技術債記錄 | `.claude/skills/tdd/references/phase4-refactor.md` |

---

## 完整流程入口

- 開始或推進 TDD 流程：`/tdd` skill（`.claude/skills/tdd/SKILL.md`）—— 子命令 `start` / `next` / `split` / `status` / `phase4-exempt`
- 流程編排規則：`.claude/pm-rules/tdd-flow.md`
- 重構驅動的預期管理：已整合於 `.claude/skills/tdd/references/phase4-refactor.md`「重構驅動的預期管理」章節

## 知識捕獲與專家審查（現行載體）

原本散落於各 Phase 的「Memory 知識捕獲」與「專家效能審查」已改由現行載體承接：

| 原內容 | 現行載體 |
|--------|---------|
| Memory Network Builder 知識捕獲 | `continuous-learning` skill（`.claude/skills/continuous-learning/skill.md`，session 結束自動觸發） |
| John Carmack 效能審查 | `ginger-performance-tuner` 代理人（`.claude/agents/ginger-performance-tuner.md`） |
| 多視角品質審查 | `parallel-evaluation` skill（Phase 4a 情境 B、Phase 4c 情境 A） |

---

## 相關文件

- TDD 全流程指導：`.claude/skills/tdd/SKILL.md`
- TDD 流程規則：`.claude/pm-rules/tdd-flow.md`
- 認知負擔原則：`.claude/rules/core/cognitive-load.md`

---

**Last Updated**: 2026-06-13
**Version**: 3.0.0 — W8-018.1 整併瘦身：完整 Phase 0-4 流程主體外移至 `/tdd` skill references（distinct 內容「重構驅動的預期管理」整合進 phase4-refactor.md），原檔瘦身為 30 秒核心 + 路由；移除全檔 emoji；DEPRECATED 引用（memory-network-builder / john-carmack）改指向現行載體（continuous-learning skill / ginger-performance-tuner）。歷史 1841 行完整版見 git log。
