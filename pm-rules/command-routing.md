# 決策樹 — 命令路由

> 訊息類型判斷為「命令」時的完整路由流程。
>
> 路由入口：.claude/pm-rules/decision-tree.md
> 來源：決策樹二元化拆分

---

## 明確性檢查（命令分支）

> 當定義不明確時，應該往上詢問確認，而非強行做出判斷。
> **工具要求**：向用戶呈現選項供選擇時，必須使用 AskUserQuestion 工具，禁止文字提問。

| 情境 | 觸發條件 | 確認目標 |
|------|---------|---------|
| 複雜需求 | 觸發 3+ 代理人 | 確認 use case 和優先級 |
| 模糊需求 | 無法用「動詞+目標」描述 | 確認具體需求 |

---

## 訊息類型識別

| 關鍵字 | 判斷為命令 |
|-------|-----------|
| "實作"、"建立"、"修復"、"處理"、"執行"、"開始"、"測試"、"驗證"、"調整" | 進入本檔案的命令路由 |

---

## 命令處理流程

```
是命令
    |
    v
是開發/修改命令? ─是→ [Level 2] Hook 系統驗證 Ticket
               |
               └─否→ 是除錯命令? ─是→ [強制] 派發 incident-responder
                                |       （詳見 incident-routing.md）
                                └─否→ PM 向用戶確認意圖（AskUserQuestion）
```

| 判斷條件 | 路由 |
|---------|------|
| 開發命令（實作/建立/新增/重構） | Hook 驗證 Ticket → **pending 需 creation_accepted**（見 execution-discovery-rules.md）→ 行為分類 → 分工路由（見下） |
| 安全相關（auth/token/permission） | → 強制派發 security-reviewer |
| 除錯命令（test failed/crash/bug） | → [強制] WRAP 快速模式（根因多選項擴增）→ 派發 incident-responder（見 incident-routing.md） |

### 分工路由（基於 subagent ~20 tool call 限制，PC-042）

| Ticket 類型 | 執行方式 | 理由 |
|------------|---------|------|
| ANA（分析） | **PM 前台執行 + [強制] WRAP 分析** | 需跨文件讀取、WRAP 防止決策深度不足 |
| DOC（文件修改） | **PM 前台執行** | 修改範圍明確、無需代理人 |
| IMP（實作） | **代理人背景派發** | 機械性程式碼工作、PM 同時做其他事 |
| TST（測試） | **代理人背景派發** | 測試撰寫和執行適合代理人 |
| **驗證類子任務**（跑測試/掃描/建置/打包/AC 實況驗證） | → **[強制] 建子 Ticket 背景派發，不詢問用戶** | 有明確 SOP，詢問只會阻礙主線 |
| **執行中發現技術債/問題/回歸/超範圍需求** | → **[強制] 立即 `/ticket create`，不詢問，不中斷主線** |

> 驗證類子任務完整規則：.claude/pm-rules/parallel-dispatch.md（驗證類任務自動派發章節）
> 詳細 SOP：.claude/references/background-dispatch-rules.md（驗證類任務自動派發章節）

### 影響範圍驗證（DOC/ANA/IMP 修改後強制）

> **根因**：修改只看「直接目標」，沒有系統性掃描「引用來源」。本專案 55 個 error-pattern 涉及遺漏/未同步，是最常見的錯誤類型。

任何規則/概念/API 修改完成後，**commit 前**必須執行：

| 步驟 | 動作 | 命令 |
|------|------|------|
| 1 | 列出本次修改的核心概念/規則名稱 | 人工識別 |
| 2 | 反向搜尋所有引用該概念的檔案 | `grep -rl "概念名" .claude/` |
| 3 | 逐一確認是否需要同步更新 | 人工判斷 |
| 4 | 有遺漏 → 補充修改 → 回到步驟 1 | 迭代 |

**典型遺漏場景**：

| 改了什麼 | 容易漏的位置 |
|---------|------------|
| Skill 觸發條件 | 決策樹路由表、PM 規則 |
| PM 行為規則 | 決策樹流程圖、Checkpoint 規則 |
| Hook 功能 | settings.json 註冊、error-pattern 記錄 |
| 常數/API 定義 | 所有消費端的引用 |

> 代理人路徑表（Source of Truth）：.claude/pm-rules/agent-path-registry.md
> IMP-003 防護：.claude/error-patterns/implementation/IMP-003-refactoring-scope-regression.md

### Worktree 路由

涉及背景實作代理人、並行修改、或隔離 session 的命令，先讀：

- .claude/pm-rules/worktree-operations.md - `--worktree` / `-w`、`isolation: worktree`、`worktree.sparsePaths`、`WorktreeCreate` / `WorktreeRemove`、stale cleanup
- .claude/references/agent-dispatch-decision.md - 目標檔案位置與代理人派發策略

路由摘要：

| 目標 | 路由 |
|------|------|
| 非 `.claude/` 實作或測試 | 背景代理人可用 `isolation: worktree` |
| `.claude/` Edit/Write | PM 前台或主 repo 流程，不派 worktree subagent |
| 人工隔離 session | `claude --worktree <path>` 或 `claude -w <path>` |
| 大型但範圍明確任務 | 可加 `worktree.sparsePaths` |

---

## TDD 階段判斷

> **PROP 核准後**：進入 TDD 前，必須先完成文件準備流程。
> 詳見：.claude/pm-rules/proposal-to-development-flow.md

| 階段 | 代理人 | 進入條件 |
|------|-------|---------|
| 文件準備 | PM | PROP 核准 |
| SA 前置審查 | saffron-system-analyst | 文件準備完成，新功能/架構變更 |
| Legacy Code 評估 | PM + 多視角審查（含語言代理人） | 接手舊專案/測試大量失敗/無測試 |
| Phase 1 | lavender-interface-designer | SA 通過 |
| Phase 2 | sage-test-architect | Phase 1 完成 |
| Phase 3a | pepper-test-implementer | Phase 2 完成 |
| Phase 3b | parsley-flutter-developer | Phase 3a 完成 |
| Phase 4a | /parallel-evaluation B（多視角重構分析） | Phase 3b 完成（標準流程） |
| Phase 4b | cinnamon-refactor-owl（依 4a 報告執行） | Phase 4a 完成（或豁免時直接進入） |
| Phase 4c | /parallel-evaluation A（多視角再審核） | Phase 4b 完成（標準流程） |

> TDD 完整流程：.claude/pm-rules/tdd-flow.md

---

## 相關文件

- .claude/pm-rules/decision-tree.md - 路由索引
- .claude/pm-rules/tdd-flow.md - TDD 完整流程
- .claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期
- .claude/pm-rules/incident-routing.md - 事件回應路由
- .claude/references/agent-dispatch-decision.md - **代理人派發決策表**（IMP/TST 派發前必讀；目標檔案位置 × permissionMode 決策矩陣）
- .claude/pm-rules/worktree-operations.md - **Worktree 操作 SOP**（`--worktree` / `-w`、`isolation: worktree`、sparsePaths、Hook events、清理）

---

**Last Updated**: 2026-04-21
**Version**: 1.2.0 - 補充 worktree 路由入口
