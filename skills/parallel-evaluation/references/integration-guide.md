# 整合指南

並行評估與決策樹、Agent Teams、TDD 流程的整合方式。

---

## 與決策樹的整合

### 整合點

並行評估在決策樹的多個層級可被觸發：

| 決策樹層級 | 觸發條件 | 建議情境 |
|-----------|---------|---------|
| 第負一層 | 收到多角度評估需求 | 依標的選擇 A-F |
| 第五層 Phase 3b 後 | 實作完成，準備 review | 情境 A |
| 第五層 Phase 4 前 | 準備重構評估 | 情境 B |
| 第六層 incident 後 | 分析報告產出 | 情境 F |
| SA 前置審查 | 新架構決策 | 情境 C |
| 規則/Skill 維護 | 系統設計文件變更後 | 情境 G |

### 觸發流程

```
決策樹判斷需要多角度評估
    |
    v
選擇情境（A-F）
    |
    v
執行 /parallel-evaluation
    |
    v
Phase 1 → Phase 2 → Phase 3
    |
    v
行動清單回到決策樹繼續處理
```

---

## 與 Agent Teams 的關係

### 何時用並行評估 vs Agent Teams

| 維度 | 並行評估 | Agent Teams |
|------|---------|-------------|
| Agent 互動 | 無（各自獨立掃描） | 有（即時協商） |
| 產出合併 | PM 彙整 | Team lead 協調 |
| 適用場景 | 品質掃描、快速評估 | 共同設計、協作開發 |
| 成本 | 標準（N 個 Task subagent） | 3-4x（Team 開銷） |

**判斷原則**：「Agent A 的發現會改變 Agent B 的工作嗎？」

- 否（各自獨立掃描）→ 並行評估（Task subagent）
- 是（需即時互動）→ Agent Teams

### 並行評估的派發方式

並行評估的 Phase 2 使用標準的 Task subagent 並行派發：

```
PM 收集標的（Phase 1）
    |
    v
並行派發 2-4 個 Agent（Phase 2）
  Agent A: 視角 1 掃描
  Agent B: 視角 2 掃描
  Agent C: 視角 3 掃描
    |
    v
所有 Agent 回報完成
    |
    v
PM 彙整和過濾（Phase 3）
```

---

## 與 TDD 流程的整合

### 各 Phase 的建議整合點

| TDD Phase | 整合時機 | 建議情境 | 必要性 |
|-----------|---------|---------|-------|
| Phase 0 (SA) | 架構決策前 | 情境 C | 選用 |
| Phase 1 | 功能設計完成後 | 情境 D | 選用 |
| Phase 3b | 實作完成後 | 情境 A | 選用 |
| Phase 4 | 重構評估前 | 情境 B | 選用 |

並行評估是**選用工具**，不是 TDD 流程的強制步驟。當以下條件符合時建議使用：

- 變更影響 3+ 個模組
- 存在多個可能的改善方向
- 希望快速掃描品質風險

### 與 incident-response 流程的整合

情境 F 是 incident-response 流程的可選延伸：

```
錯誤發生 → /pre-fix-eval → incident-responder 分析
    |
    v
[可選] 情境 F 並行審查分析結論
    |
    +-- 審查通過 → 建立 Ticket → 派發修復
    +-- 審查不通過 → 回到分析，補充遺漏的視角
```

**建議觸發情境 F 的條件**：

- incident-responder 的結論影響 3+ 個模組
- 修復方案的變更風險為「高」
- 結論中包含推測性判斷
- 錯誤的重現條件不明確

---

## 與 /bulk-evaluate 的關係

`/bulk-evaluate` 是並行評估的正交工具，兩者並行軸不同。

| 維度 | /parallel-evaluation | /bulk-evaluate |
|------|---------------------|---------------|
| 並行軸 | N 個視角 x 1 組標的 | 1 個標準 x N 個單位 |
| Agent 互動 | 無（各自掃描同一標的） | 無（各自處理不同目標） |
| 產出合併 | PM 彙整為行動清單 | 各 Agent 寫入子 Ticket |
| Context 影響 | 主線程接收彙整結果 | 主線程只看統計摘要 |
| 派發原則 | 2-4 個 Agent（視角數） | 1 目標 = 1 Agent（單一職責） |

**選擇原則**：

- 需要多角度掃描同一標的 → `/parallel-evaluation`
- 需要用同一標準掃描 N 個獨立目標 → `/bulk-evaluate`
- 兩者可組合：先用 `/bulk-evaluate` 批量掃描，再用 `/parallel-evaluation` 審查結論

---

## 與 /simplify 的關係

`/simplify` 是並行評估情境 A 的特化版本，專注於程式碼變更審查。

| 維度 | /simplify | /parallel-evaluation 情境 A |
|------|-----------|---------------------------|
| 標的 | git diff 的變更 | 任何程式碼範圍 |
| 視角 | 固定 3 個（Reuse, Quality, Efficiency） | 可自訂 |
| 行動 | 直接修改程式碼 | 產出行動清單 |
| 適用 | 快速 code review + fix | 評估但不立即行動 |

**選擇原則**：

- 需要快速審查 + 直接修復 → `/simplify`
- 需要評估但不確定是否行動 → `/parallel-evaluation` 情境 A

---

## 報告流轉

並行評估報告的後續處理：

| 報告結果 | 後續行動 | 負責人 |
|---------|---------|-------|
| 有「必須執行」項目 | 直接修復或建立 Ticket | PM 決定 |
| 只有「值得執行」項目 | 評估是否在當前版本處理 | PM 決定 |
| 全部跳過 | 記錄到工作日誌，繼續 | PM |
| 情境 F 不通過 | 回到分析階段 | PM |

---

## 相關文件

- .claude/methodologies/parallel-evaluation-methodology.md - 完整方法論
- .claude/skills/parallel-evaluation/SKILL.md - 操作指南
- .claude/skills/bulk-evaluate/SKILL.md - 批量評估工具（正交工具）
- .claude/rules/core/decision-tree.md - 主線程決策樹
- .claude/rules/guides/parallel-dispatch.md - 並行派發指南
- .claude/rules/flows/incident-response.md - 事件回應流程
- .claude/rules/flows/tdd-flow.md - TDD 流程

---

**Last Updated**: 2026-03-02
**Version**: 1.0.0
