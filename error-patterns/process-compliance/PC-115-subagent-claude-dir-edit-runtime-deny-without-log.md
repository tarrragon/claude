---
id: PC-115
title: subagent 對 .claude/ Edit 被 runtime 拒絕且無 hook 訊息
category: process-compliance
severity: high
created: 2026-05-02
source_ticket: 0.18.0-W17-097
related_pc:
  - PC-040
  - PC-114
related_arch:
  - ARCH-015
---

## 症狀

subagent 派發後嘗試 Edit/Write 主 repo `.claude/` 下檔案：

- Edit 工具回傳「Permission to use Edit has been denied」
- 無 hook stderr 訊息（非 exit 2 deny）
- `.claude/hook-logs/` 全目錄無相關紀錄
- 同 session 同檔案，PM 主線程 Edit 立即成功

## 根因（**未解**：W17-097/098/099/100/101/102/103 五輪 + W17-108/109 三階段對照，Hypothesis K 強形式已否證）

**狀態：根因待重啟調查**。Hypothesis K（session 級 prefix-based 權限快取需 PM 暖機）於 2026-05-02 21:00 新 session 三階段對照實驗中被決定性否證——冷快取下 subagent `.claude/` Edit 兩次皆 success。W17-097.1-.4 DENY 4/4 的真實根因仍未識別。詳見 `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W17-108.md` 與 `0.18.0-W17-109.md`。

### Hypothesis K（已否證的工作假設，保留作歷史紀錄）

原推論：CC v2.1.126 對 subagent `.claude/` Edit 有「session 級 prefix-based 權限快取」：

- session 內**首次** subagent `.claude/` Edit 觸發互動式 permission prompt
- 在 subagent 無 UI 環境下，prompt 自動 deny
- **PM 互動式 Edit 過 `.claude/` 任一檔**會在 session 中快取「`.claude/` 已授權」
- 之後 subagent `.claude/` Edit 都繼承快取 → success（即使是不同檔，因為 prefix-based 涵蓋整個 `.claude/`）

**否證證據**（W17-108 Phase A）：本 session PM 從未 Edit `.claude/`，subagent 對 `.claude/methodologies/atomic-ticket-methodology.md` 兩次 Edit 皆 success。預測為 deny，實測為 success。

### 新 session 三階段對照實驗矩陣（W17-108/109，2026-05-02 21:00）

| 階段 | PM 已 Edit `.claude/` | Subagent 目標檔 | Subagent Edit 結果 | 對 Hypothesis K |
|------|--------------------|---------------|------------------|----------------|
| A (W17-108) | 否（冷快取）| atomic-ticket-methodology.md | success x2 | **否證強形式** |
| B | PM 自己 Edit + revert atomic-ticket-methodology.md | — | — | 觸發暖機 |
| C (W17-109) | 是（不同檔） | comment-writing-methodology.md | success x2 | 與 A 相同無差異 |

A=success 否決強形式 K（「需 PM 暖機」）；C=success 證實「暖機後對不同檔也 success」但因 A 已 success，C 無法獨立支持任何假設。

### 五輪歷史實驗矩陣（W17-097～W17-103，與 Hypothesis K 預測相符但已被新 session 反例推翻）

| 實驗 | 並行 | Edit 內容 | PM 已 Edit `.claude/` 任一檔 | 結果 |
|-----|----|----|----|----|
| W17-097.1-.4 | 4 | 複雜（import + 8 替換）| 否 | DENY 4/4 |
| W17-099 | 1 | 簡單 | 是 | success |
| W17-100 (E1) | 1 | 複雜 | 是 | success |
| W17-101.1-.4 (E2) | 4 | 簡單 | 是 | success 4/4 |
| W17-102 (Test G) | 1 | 簡單（PM 未碰過該檔）| 是（其他檔已 Edit）| success |

並行/Edit 複雜度/prompt 結構/PM 接觸該檔（檔案層級）四個變因被獨立否證。剩下 prefix 層級 PM 接觸史與五實驗結果**全相符且零反例**——但 2026-05-02 21:00 新 session Phase A 提供反例：冷快取下 subagent Edit 兩次皆 success，五輪結果並非「Hypothesis K 唯一解釋」。

### 驗證對照（同一 session, 19:33:49 同一時點）

| Actor | Path | Branch | Hooks 結果 | permissionMode | Result |
|-------|------|--------|----------|----------------|--------|
| PM 主線程 | .claude/skills/ticket/lifecycle.py | main | 全 exit 0 | n/a | SUCCESS |
| thyme subagent | 同上 | main | 全 exit 0 | bypassPermissions | DENIED |

唯一差異 = `agentId`（subagent vs PM）。

### 不可覆蓋的三層

| 機制 | 是否影響 deny | 證據 |
|------|------------|------|
| Hook 系統（PreToolUse Edit）| 否 | 5 個 hook（main-thread-edit-restriction / branch-verify / file-type-permission / ticket-path-guard / ticket-file-access-guard）全 exit 0 allow |
| settings.json `permissions.allow` | 否 | 含 `Edit`/`Write` 但 subagent 仍拒 |
| agent frontmatter `permissionMode: bypassPermissions` | 否 | thyme 已設 bypassPermissions 仍拒 |

### 機制推論

CC runtime 設計層保護「框架資產自我修改」：subagent 若能任意改 `.claude/hooks/`、`.claude/agents/`、`.claude/skills/`，可繞過用戶授權系統。`permissionMode: bypassPermissions` 只覆蓋 hook 層 + settings 層，不覆蓋 runtime hardcoded protection。

### 診斷不可見性

deny 訊息為標準 CC 模板「Permission to use Edit has been denied. IMPORTANT: ...」，無 hook stderr 訊息，無 `.claude/hook-logs/` 紀錄。所有 PreToolUse hook 顯示 allow，故診斷時容易誤判為 hook 問題。

### 歷史軌跡

- 2026-04-13 ARCH-015 原結論：「.claude/ 一律被擋」
- 2026-04-18 重驗（v2.1.114）：「主 repo 樹內 .claude/ 可寫」（feedback_arch015_boundary_refinement）
- 2026-05-02 19:33 W17-097.1-.4（v2.1.126）：4 並行 thyme 全 deny（PM 該 session 從未 Edit `.claude/`）
- 2026-05-02 20:21 W17-099 重測（同 session 50 分鐘後）：1 個 thyme 成功 Edit + revert（PM 該 session 已多次 Edit `.claude/`）
- 2026-05-02 20:35-20:55 E1/E2/Test G 三組對照實驗，五輪結果與 Hypothesis K 全相符
- 2026-05-02 W17-103 整合：提出 prefix-based session cache 推論 + 新 session 驗證 prompt
- **2026-05-02 21:00 W17-108/109（新 session，v2.1.126）三階段對照**：
  - Phase A 冷快取（PM 從未 Edit `.claude/`，目標 atomic-ticket-methodology.md）：subagent Edit 兩次皆 success
  - Phase B PM 自己 Edit + revert atomic-ticket-methodology.md
  - Phase C 暖機後不同檔（comment-writing-methodology.md）：subagent Edit 兩次皆 success
  - **結論**：Hypothesis K 強形式被決定性否證；W17-097.1-.4 DENY 4/4 的真實根因仍未識別

## 待重啟調查的候選假設

Hypothesis K 否證後，W17-097.1-.4 的 4/4 deny 仍需解釋。**調查計畫已建立**：W17-110（含 W17-110.1/.2/.3/.4 spawned 子實驗 ticket，按 ROI 排序，含 W17-104 反模式 1-4 自查清單）。可能候選（尚未測試）：

| 候選 | 描述 | 區辨設計 |
|------|------|---------|
| Transient runtime issue | W17-097 那次是 CC runtime 暫時故障，非系統性行為 | 累積多 session 重複 4 並行 + 複雜 Edit 嘗試，看 deny 比率 |
| 並行 + 複雜 Edit 組合 | 並行性與 Edit 複雜度（含 import 修改 + 多處替換）的交互作用 | 控制 Edit 複雜度，分別測 1/2/4 並行 |
| Session 累積狀態 | 上 session 已執行多 commit + pytest 後的某種累積狀態觸發 deny | 新 session 完整重現 W17-097 上下文（多 commit + pytest 累積後）再測 |
| CC 版本內部變化 | 同版號 v2.1.126 內部行為波動 | 記錄 deny 案例的 CC 詳細版本資訊 |

## 防護（**已下調**：Hypothesis K 暖機建議撤回）

| 層級 | 機制 |
|------|------|
| 派發策略 | subagent 對主 repo 樹內 `.claude/` Edit **可預期 success**（W17-099 / 100 / 101 / 102 / 108 / 109 共 9 次連續 success）。例外只剩 W17-097.1-.4 那 4 次未解 deny |
| 失敗回應 | 若實際遭遇 deny（罕見），PM 立即接手 Edit 即可——同時修復本任務 + 為記錄收集數據 |
| 暖機建議 | **撤回**（Phase A 已否證需要暖機） |
| 記憶更新 | feedback_arch015_boundary_refinement.md 同步否證結論 |

## 觸發案例

W17-097：ANA 規劃 5 個 IMP children，前 4 個並行派發 thyme-python-developer 修改 `.claude/skills/ticket/`，全部 Edit deny。PM 接手 W17-097.3 即時成功（commit d357fefd）。

## 鑑別診斷

| 訊號 | 對應 PC |
|------|---------|
| 主 repo `.claude/` Edit 被 runtime 拒絕（無 hook 訊息） | **本 PC-115** |
| 派發前 hook 阻擋（agent-dispatch-validation） | PC-114 |
| MCP write tool 對 text file 被擋 | PC-112 |
| Edit 成功但 prompt 缺 context | PC-040 |

## 後續觀察

- CC 升級或 setting 變更後重驗（記錄版本號 + 日期）
- 若用戶 setting 可關閉此限制，補充至本 PC
