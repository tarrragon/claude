# 驗證責任分配框架

本文件定義系統性的「驗證責任分配」框架，明確各層級的驗證職責，防止未來類似的功能缺口和職責混亂。

> **核心理念**：驗證是多層級、多角色的責任分工。不同階段有不同的驗證者，確保完整的檢查覆蓋。

---

## 框架總覽

```
Level 1 入口層 → Level 2 執行層 → Level 3 完成層 → Level 4 驗收層 → 任務完成
```

| 層級 | 驗證時機 | 驗證者 | 目標 |
|------|---------|-------|------|
| Level 1 入口層 | 命令入口（用戶輸入時） | Hook 系統 | 防止無計畫工作（Ticket 存在 + 認領 + 品質審核） |
| Level 2 執行層 | 任務開始時、階段切換時 | 代理人 | 確保前置條件滿足、無隱藏依賴 |
| Level 3 完成層 | 階段完成時、Ticket 標記完成前 | Hook + 代理人 | 確保產出物完整、文件記錄齊全 |
| Level 4 驗收層 | Ticket complete 後 | acceptance-auditor + PM | 最終品質確認 |

> 各層級驗證內容表格、責任分工、Hook 實作細節、驗收流程圖：.claude/references/verification-framework-details.md

---

## 統一責任對照表

| 驗證項 | 驗證者 | 所屬層級 | 無法通過時 | 最終決策 |
|-------|-------|--------|-----------|--------|
| Ticket 存在 | Hook | Level 1 | 提示建立 | 用戶決定 |
| Ticket 認領 | Hook | Level 1 | 提示認領 | 用戶決定 |
| Ticket 內容品質 | PM | Level 1 | 建議補充 | PM 決定 |
| Solution 並行化 | PM | Level 1 | 建議評估 | PM 決定 |
| 建立後品質審核 | acceptance-auditor + system-analyst | Level 1 | 派發審核代理人 | PM 決定 |
| 前置依賴 | 代理人 | Level 2 | 升級 PM | PM 決定 |
| 環境正常 | 代理人 | Level 2 | 派發 SE | SE 處理 |
| 產出物完整 | Hook | Level 3 | 提示補充 | 代理人決定 |
| 工作日誌 | Hook | Level 3 | 提示更新 | 代理人決定 |
| 驗收條件主動勾選 | PM | Level 3 | complete 前執行 check-acceptance | PM 決定 |
| 並行派發後驗證 | PM | Level 3 | 補派代理人 | PM 決定 |
| 驗收條件 | acceptance-auditor | Level 4 | 要求補充 | PM 決定 |
| 建議追蹤 | acceptance-auditor | Level 4 | 要求處理 | PM 決定 |
| 品質標準 | acceptance-auditor | Level 4 | 建立修正 Ticket | PM 決定 |
| 測試通過 | acceptance-auditor | Level 4 | 派發 incident | PM 決定 |

---

## 驗證失敗處理

| 失敗類型 | 恢復方式 | 時限 |
|---------|--------|------|
| Level 1（Ticket 問題） | 建立或認領 Ticket | 立即 |
| Level 2（前置條件） | 升級 PM 或派發協助代理人 | 立即升級 |
| Level 3（產出物缺陷） | 補充產出物或更新文件 | 同日內 |
| Level 4（品質問題） | 建立修正 Ticket | 本版本內 |

> 失敗流程圖和詳細恢復規則：.claude/references/verification-framework-details.md

---

## 與現有規則的整合

### 與 Skip-gate 的關係

**Skip-gate 防護機制對應**：

| Skip-gate 層級 | 防護機制 | 驗證框架對應 |
|---------------|--------|------------|
| Level 2 | 命令入口防護 | Level 1 入口層驗證 |
| Level 3 | 階段完成防護 | Level 3 完成層驗證 |

### 與決策樹的關係

驗證框架在決策樹的多個層級提供支撐：

| 決策樹層級 | 驗證層級 | 驗證者 |
|-----------|--------|-------|
| 第零層（明確性檢查） | Level 1 | Hook + 代理人 |
| 第四層（Ticket 執行） | Level 1 | Hook |
| 第五層（TDD 階段） | Level 2 + Level 3 | 代理人 + Hook |
| 第七層（完成判斷） | Level 4 | PM |

### TDD 階段驗證檢查點

每個 TDD 階段都有對應的驗證要點：

| Phase | Level 2 前置條件 | Level 3 驗收條件 |
|-------|---------------|----------------|
| SA | - | 架構評估完成 |
| Phase 1 | SA 審查通過 | API 定義完整 |
| Phase 2 | Phase 1 完成 | 測試案例設計完成 |
| Phase 3a | Phase 2 完成 | 策略文件完整 |
| Phase 3b | Phase 3a 完成 | 測試 100% 通過 |
| Phase 4 | Phase 3b 完成 | 評估報告完成 |

---

## 驗證檢查清單與操作指引

> 各層級完整檢查清單（Level 2/3/4）、場景範例、Hook 實作規範、驗證指標：.claude/references/verification-framework-details.md
> 場景範例：.claude/references/verification-scenario-examples.md
> Hook 實作細節：.claude/references/verification-hook-implementation.md

---

## 相關文件

- @.claude/rules/core/decision-tree.md - 主線程決策樹
- @.claude/rules/forbidden/skip-gate.md - Skip-gate 防護機制
- @.claude/rules/core/cognitive-load.md - 認知負擔設計原則
- @.claude/rules/flows/tdd-flow.md - TDD 流程
- @.claude/rules/flows/incident-response.md - 事件回應流程
- .claude/references/verification-scenario-examples.md - 場景範例
- .claude/references/verification-hook-implementation.md - Hook 實作細節

---

**Last Updated**: 2026-03-13
**Version**: 1.7.0 - Level 3 新增「驗收條件主動勾選」驗證項目（0.1.0-W51-001）
**Status**: Active
**Responsible**: rosemary-project-manager, acceptance-auditor, Hook 系統

**Change Log**:
- v1.5.0 (2026-03-04): Level 1 新增建立後品質審核（W4-002）
  - Level 1 驗證表格新增「建立後品質審核」項目
  - 統一責任對照表新增對應項目
  - 配合 ticket-lifecycle.md v5.1.0 建立後強制審核流程
- v1.4.0 (2026-02-26): Level 3 新增並行派發後驗證（W25-003）
  - Level 3 驗證表格新增「並行派發後驗證」項目（git diff --stat 強制驗證）
  - 統一責任對照表新增對應項目（PM 負責、Level 3）
  - 配合 parallel-dispatch.md v2.5.0 新增並行派發後驗證章節
- v1.3.0 (2026-02-10): Level 1 新增 Ticket 內容品質驗證（W17-001）
  - Level 1 驗證表格新增「Ticket 內容品質」和「Solution 並行化」兩項
  - 統一責任對照表新增對應項目
  - 配合 ticket-lifecycle.md v4.1.0 建立後品質驗收機制
- v1.2.0 (2026-02-06): Context 最佳化
  - 簡化主檔案結構，移除重複說明
  - 新增「統一責任對照表」（合併原有 2 個表格）
  - 「常見驗證場景」移至 verification-scenario-examples.md
  - 「Hook 實作規範」詳細內容移至 verification-hook-implementation.md
  - 保留核心架構圖和流程圖完整
  - 添加參考連結方便查閱
- v1.1.0 (2026-01-30): Level 4 驗收層更新
- v1.0.0 (2026-01-23): 初始版本
