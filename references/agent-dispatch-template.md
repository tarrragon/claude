# Agent Dispatch Template — 職責邊界聲明骨架

> **用途**：PM 派發代理人時，prompt 必含「職責邊界聲明」開場結構，讓代理人在執行前確認任務符合其定義的允許產出範圍，阻擋越界行為。
>
> **實證來源**：
> - W5-001 session（pepper / thyme-A / thyme-B）：派發 prompt 含職責邊界聲明，無越界案例
> - W5-001 sage 越界案例：派發 prompt 缺職責邊界聲明，sage 寫了禁止範圍的 .py 測試
>
> **設計依據**：quality-baseline 規則 6（失敗案例學習原則）— 從實證有效的派發模式固化為強制骨架。

---

## 骨架

派發 prompt 必含以下開場結構：

```
Ticket: {ticket_id}

## 職責邊界聲明

{agent-name} 的 agent 定義為「{agent-description 引文，來自 .claude/agents/{agent}.md frontmatter}」。

**允許的產出**:
- {列出本 ticket 範圍內允許的檔案/動作}

**禁止的產出**:
- {列出本 ticket 範圍外或代理人定義禁止的檔案/動作}

本 prompt 符合職責邊界，請繼續執行。

## 執行

{具體執行步驟、Ticket 指令、引用 Context Bundle}

## 禁止
- {與其他並行 Ticket 衝突的修改範圍}
- {本 Ticket 不應涉及的副作用}
```

---

## 三段式快速填空骨架（W17-048 方案 F）

> **用途**：PM 派發前最常用的中文對話式骨架。把 context 寫入 ticket 後，直接複製以下骨架填三個空格即可派發。prompt 控制在 **10-15 行**，穩過 Hook 30 行上限。

### 骨架（3 段）

```markdown
Ticket: {ticket_id}

## 任務

{一句話動作描述，≤ 40 字}

讀取 ticket：`ticket track full {ticket_id}`
依 Context Bundle 執行流程。遇阻立即停下回報，禁繞過 Hook。
```

### IMP 實戰範例（實作派發）

```markdown
Ticket: 0.18.0-W17-046.1

## 任務

擴充 TICKET_EXEMPT_AGENT_TYPES 白名單 + 補充 Hook 判別準則註解 + 新增測試。

讀取 ticket：`ticket track full 0.18.0-W17-046.1`
依 Problem Analysis 的 Context Bundle 規格實作 + commit + complete。
遇阻立即停下回報，禁繞過 Hook。
```

### ANA 實戰範例（分析派發）

```markdown
Ticket: 0.18.0-W17-043

## 任務

分析 scenario-17 AskUserQuestion 提醒在 append-log 誤觸發根因。

讀取 ticket：`ticket track full 0.18.0-W17-043`
依 acceptance 產出分析報告寫入 Solution，衍生修復 ticket 後 complete。
遇阻即停回報，禁繞過 Hook。
```

### DOC 實戰範例（文件派發）

```markdown
Ticket: 0.18.0-W17-048.3

## 任務

新增 agent-dispatch-template.md「短 prompt 三段式骨架」範例區。

讀取 ticket：`ticket track full 0.18.0-W17-048.3`
依 Context Bundle 設計文件結構，append Solution + commit + complete。
遇阻即停回報。
```

### 填空檢查清單

派發前確認：

- [ ] 第一行為 `Ticket: {id}`（Hook 強制驗證）
- [ ] 含「讀取 ticket」指引（W17-048.2 軟提示檢查）
- [ ] context 已在 ticket 的 Problem Analysis / Context Bundle（不塞 prompt）
- [ ] prompt 總行數 ≤ 15 行（遠低於 30 行硬上限）
- [ ] 動作描述一句話可理解（不堆疊多個動詞）

---

## 短 Prompt Snippets（PC-040 / PC-065）

以下 snippets 是派發時優先使用的短版骨架。完整 context 必須先寫入 Ticket Context Bundle；prompt 只保留 Ticket ID、邊界摘要與執行指令。每個 snippet 第一行固定為 `Ticket: {id}`。

### 單任務

```markdown
Ticket: {id}

{agent-name}: Read ticket md and execute the current acceptance criteria.
Allowed: {allowed files/actions from where.files}
Forbidden: {out-of-scope files/actions}
Use precise staging only: git add {exact files}
If context is insufficient, append NeedsContext and stop.
```

### 並行多任務

```markdown
Ticket: {id}

{agent-name}: Execute only this ticket from the dispatch-plan.
Allowed: {this ticket files/actions}
Forbidden: other parallel tickets' files and git add . / git add -A
Commit policy: {agent commit | PM commit | no commit}
If blocked, report Exit Status without touching sibling scope.
```

### Group Coordinator

```markdown
Ticket: {id}

{agent-name}: Update the group/coordinator ticket only.
Use the dispatch-plan table to track children/spawned tickets.
Do not implement child scope or batch-dispatch agents.
Record blockers, deps, and next runnable ticket IDs.
```

---

## Dispatch-Plan Template

對 2+ ticket、group ticket、spawned follow-up、或任何需要並行/序列混合派發的場景，PM 先在 ticket Problem Analysis 或 Solution 寫入 dispatch-plan。dispatch-plan 是 orchestration description，不是 batch dispatch CLI。

| ticket | agent | files | deps | context source | commit policy | run mode |
|--------|-------|-------|------|----------------|---------------|----------|
| `{id}` | `{agent}` | `{exact files}` | `{none | ids}` | `{Context Bundle | handoff | manual note}` | `{agent commit | PM commit | no commit}` | `{parallel | serial | blocked}` |

欄位要求：

| 欄位 | 內容要求 |
|------|---------|
| `ticket` | 單一 ticket ID；不得把多個 ticket 合成同一列 |
| `agent` | 指定 agent 或 PM 前台 |
| `files` | 精確檔案 ownership；未知時先補 Context Bundle，不派發 |
| `deps` | blockedBy / 前置 ticket；無依賴填 `none` |
| `context source` | agent 應讀取的持久化 context 來源 |
| `commit policy` | 明確 agent 自 commit、PM 統一 commit、或 no commit |
| `run mode` | `parallel`、`serial` 或 `blocked`；不得用 `batch` 表示自動批量執行 |

---

## 填寫要點

| 欄位 | 內容要求 |
|------|---------|
| `{agent-name}` | 代理人名稱（如 `thyme-python-developer`） |
| `{agent-description 引文}` | 從 `.claude/agents/{agent}.md` frontmatter `description` 直接引用 |
| 允許的產出 | 對照代理人可編輯路徑表 + 本 Ticket `where.files` 交集 |
| 禁止的產出 | 並行 Ticket 範圍、代理人定義外的檔案類型、跨 Ticket 動作 |

---

## 適用範圍

| 場景 | 是否強制引用骨架 |
|------|----------------|
| 所有 TDD Phase 派發（Phase 1-4） | 強制 |
| 所有背景代理人派發（`run_in_background: true`） | 強制 |
| ANA / DOC / IMP 各類 Ticket 派發 | 強制 |
| 並行派發（多代理人同時） | 強制（尤其重要，範圍劃分清楚） |
| 探索類代理人（Explore、查詢類） | 選用（無寫入風險時可省略） |

---

## 為何不直接依賴代理人定義？

代理人 frontmatter 已定義職責，但實務證明僅靠代理人端檢查不足夠：

| 防護層 | 失效模式 |
|-------|---------|
| 代理人端 agent 定義 | 代理人可能為滿足 prompt 具體要求而越界 |
| Hook 預檢（branch-verify-hook） | 僅檢查路徑白名單，無法判斷 Ticket 範圍 |
| **Prompt 端職責邊界聲明** | **派發時即明示邊界，代理人執行前有自檢依據** |

三層防護並存，prompt 端聲明是派發時的最後防線。

---

## 相關文件

- `.claude/pm-rules/parallel-dispatch.md` — 引用本模板為強制骨架
- `.claude/pm-rules/decision-tree.md` — 代理人可編輯路徑對照表
- `.claude/rules/core/quality-baseline.md` — 規則 6 失敗案例學習原則

---

**Last Updated**: 2026-04-22
**Version**: 1.1.0 — 新增短 prompt snippets 與 dispatch-plan template（W17-044）

**Version**: 1.0.0 — 從 W5-009 方案 2 落地（Ticket 0.18.0-W5-044）
