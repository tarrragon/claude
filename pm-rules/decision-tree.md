# 主線程決策路由

本文件是規則系統的核心路由索引，指向各決策路徑的專屬檔案。

> **架構**：入口用二元過濾（快速縮小範圍），子路由用多路表格（直接對照選項）。
>
> **管理哲學**：主管的價值不在於解決問題的速度，而在於讓團隊的人力發揮到極致。
> 詳見：.claude/rules/core/pm-role.md
>
> **適用對象**：本文件的行為限制僅適用於 rosemary-project-manager（主線程）。被派發的 subagent 依據自身職責定義執行，不受主線程行為限制。

---

## 決策流程總覽

```
接收訊息
    |
    v
[Skill 匹配層] 已註冊 Skill 觸發條件匹配?
    +── 是 → 使用 Skill tool 執行（結束）
    +── 否 ↓
    v
[派發閘門] → dispatch-gate.md
    複雜度關卡（指數 > 10 必須拆分）
    Context Bundle 關卡（三步驟檢查）
    並行化判斷
    |
    v（通過閘門）
[第零層：明確性檢查] 包含明確錯誤關鍵字?
    +── 是 → incident-routing.md
    +── 否 ↓
    v
[第一層：類型判斷] 問題 / 命令 / 其他?
    +── 問題 → question-routing.md
    |   （"怎麼樣"、"進度"、"為什麼"、"如何"、"是什麼"、"?"）
    +── 命令 → command-routing.md
    |   （"實作"、"建立"、"修復"、"處理"、"執行"、"開始"、"測試"）
    +── 其他 → PM 向用戶確認意圖（AskUserQuestion）

--- 以下按條件觸發，非線性序列 ---

[執行中發現]   → execution-discovery-rules.md（觸發：發現技術債/問題）
[完成後發現]   → execution-discovery-rules.md 3.5-B 層（觸發：completed Ticket 需修正）
[任務完成]     → completion-checkpoint-rules.md（觸發：Ticket complete 後）
```

> 視覺化 Mermaid 圖表：.claude/references/decision-tree-diagrams.md

---

## Skill 匹配層（最高優先）

Skill 是預建的專用工具，優先於代理人派發。

| 優先級 | 匹配方式 | 範例 |
|--------|---------|------|
| 1 | 明確指令 (`/skill-name`) | `/ticket track summary` |
| 2 | Skill description 中的觸發關鍵字 | 「確認待辦的 ticket」→ ticket Skill |
| 3 | Hook `[SKILL 提示]` 輸出 | Hook 建議使用某 Skill |

無 Skill 匹配 → 進入派發閘門。

---

## 路由表

| 分支條件 | 路由檔案 | 適用場景 |
|---------|---------|---------|
| 所有派發前（強制） | dispatch-gate.md | 複雜度關卡 + Context Bundle + 並行化 |
| ANA/Debug/提案（強制 WRAP） | /wrap-decision | 分析、除錯、提案評估必須先 WRAP（0.18.0-W4-002） |
| 問題類型訊息 | question-routing.md | 查詢、諮詢、進度 |
| 命令類型訊息 | command-routing.md | 開發、修改、TDD 階段 |
| 錯誤/失敗 | incident-routing.md | 事件回應（含 WRAP 強制） |
| 執行中發現 | execution-discovery-rules.md | 技術債、超範圍需求 |
| 完成後發現 | execution-discovery-rules.md 3.5-B | completed Ticket 交付物需修正 |
| 任務完成 | completion-checkpoint-rules.md | Checkpoint 循環（0/0.5/1/1.5/1.8/1.9/2/3/4/R） |
| TDD 完成路由 | tdd-completion-routing.md | Checkpoint 2 情境 D（TDD Phase 完成） |
| 代理人管理 | agent-dispatch-enforcement.md | 觸發優先級、強制命令、違規 |
| Ticket 進度更新（強制） | completion-checkpoint-rules.md | Checkpoint 轉換時更新 Ticket |
| 代理人權限查詢 | agent-path-registry.md | 路徑表 Source of Truth |

---

## 相關文件

### 路由子檔案（決策路由分支）

- .claude/pm-rules/dispatch-gate.md - 派發閘門（複雜度 + Context Bundle + 並行化）
- .claude/pm-rules/question-routing.md - 問題路由（查詢、諮詢）
- .claude/pm-rules/command-routing.md - 命令路由（開發、TDD）
- .claude/pm-rules/incident-routing.md - 事件回應路由

### Domain 拆分檔案（DDD 邊界，W3-007.1）

- .claude/pm-rules/execution-discovery-rules.md - 執行 Domain（第三層半 + 第四層）
- .claude/pm-rules/completion-checkpoint-rules.md - 完成 Domain（第七層 + 第八層）
- .claude/pm-rules/agent-dispatch-enforcement.md - 代理人管理 Domain

### 共用參考

- .claude/pm-rules/agent-path-registry.md - 代理人路徑權限表（Source of Truth）
- .claude/pm-rules/context-bundle-spec.md - Context Bundle 規範

### 支撐規則

- .claude/pm-rules/parallel-dispatch.md - 並行派發指南
- .claude/pm-rules/tdd-flow.md - TDD 流程
- .claude/pm-rules/incident-response.md - 事件回應詳細流程
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期
- .claude/pm-rules/skip-gate.md - Skip-gate 防護
- .claude/pm-rules/askuserquestion-rules.md - AskUserQuestion 規則
- .claude/references/decision-tree-checkpoint-details.md - Checkpoint 詳細流程

---

**Last Updated**: 2026-04-09
**Version**: 9.0.0 - 二元化拆分：主檔案精簡為路由索引（從 311 行 → ~90 行）
