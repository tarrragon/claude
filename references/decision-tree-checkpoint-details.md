# 決策樹第八層：完成後路由 Checkpoint 詳細流程

本文件為 `decision-tree.md` 第八層的詳細展開，包含 Checkpoint 0~4 的完整流程說明、各情境子規則，以及 Resume 後標準化接手流程（Checkpoint R）。

主檔概覽：`.claude/rules/core/decision-tree.md`

---

## Checkpoint 0：建立後 Handoff 判斷

**適用時機**：Ticket 建立/拆分完成後

**判斷規則**：

| 情況 | 路由 |
|------|------|
| 建立了子任務或獨立 Ticket，且可並行派發（creation_accepted + 檔案無重疊 + 敘述完善 + 符合並行安全條件） | 留在當前 session → 並行派發代理人 → 進入 Checkpoint 1 |
| 建立了子任務且不可並行派發 | commit → handoff → 新 session 逐一處理子任務 |
| 建立了獨立 Ticket（非子任務，不可並行） | commit → handoff → 新 session 認領執行 |
| 非建立/拆分場景（執行完成、Phase 完成等） | 跳過，進入 Checkpoint 1 |

---

## Checkpoint 1：變更狀態檢查

**觸發時機**：任何任務完成後、並行派發代理人回報後

**判斷規則**：

| 情況 | 路由 |
|------|------|
| git status 有未提交變更 + 批量變更 | AskUserQuestion #15（備份確認） |
| git status 有未提交變更 | 建議 commit（/commit-as-prompt） |
| git status 無變更 | 跳至 Checkpoint 3 |

---

## Checkpoint 1.5：錯誤學習經驗確認（AskUserQuestion #16）

**觸發時機**：commit 成功後，進入 Checkpoint 2 之前

**執行順序**：commit 成功 → #16 → #11

**選項**：

| 選項 | 說明 |
|------|------|
| 無需記錄（Recommended） | 本次 commit 無特殊錯誤經驗 |
| 記錄錯誤學習經驗 | 執行 /error-pattern add → 可能產生新 commit → 回到 Checkpoint 1.5 |
| 稍後記錄 | 繼續工作，之後再補記錄 |

---

## Checkpoint 2：Commit 後情境評估

**觸發時機**：每次 git commit 成功後

**強制前置動作**：`ticket track list --wave {n} --status pending in_progress`（取得數據後再評估，禁止依賴記憶判斷）

**前置分流**：當前 commit 是否屬於 TDD Phase 完成？識別依據：已完成 ticket 含 `tdd_phase` 欄位。

### 情境 D：TDD Phase 完成路由（優先於情境 A/B/C）

**識別**：ticket 含 `tdd_phase` 欄位

| Phase 完成 | 路由 |
|-----------|------|
| Phase 1/2/3a | 全自動 → 下一 Phase 代理人 [注 1] |
| Phase 3b | PM 自動檢查豁免條件 [注 2]：符合 → 全自動進入 Phase 4b；不符合 → AskUserQuestion #13（選擇 Phase 4a 或 4b） |
| Phase 4a/4b | 全自動 → 下一 Phase（Phase 4b 可豁免跳至 tech-debt [注 2]） |
| Phase 4c | 強制 /tech-debt-capture → AskUserQuestion #13（不可跳過） |

**注 [1] Phase 代理人對應**：Phase 1 → sage-test-architect、Phase 2 → pepper-test-implementer、Phase 3a → parsley-flutter-developer

**注 [2] 豁免條件**（Phase 3b → 跳過 4a；Phase 4b → 跳過 4c）：`<=2 檔案` / `DOC 類型` / `任務範圍單純（單一模組、修改目的明確）`

---

### 情境 A：ticket 仍 in_progress（Context 刷新）

**識別**：查詢結果有自己的 ticket 仍 in_progress

**目的**：Context 刷新（新 session 繼續同一 ticket）

→ **AskUserQuestion #11a**（選項與 CLI 命令詳見 `.claude/references/askuserquestion-scene-details.md` 場景 11）

---

### 情境 B：ticket 已 completed + 同 Wave 有 pending 任務（任務切換）

**目的**：任務切換（切換到下一個 ticket）

→ **AskUserQuestion #11b**（選項與 CLI 命令詳見 `.claude/references/askuserquestion-scene-details.md` 場景 11）

---

### 情境 C：ticket 已 completed + 同 Wave 無待處理任務（Wave 完成）

**強制前置步驟：Wave 完成審查**

進入情境 C 時，在判斷 C1/C2 之前，**必須**先執行 `/parallel-evaluation` 對整個 Wave 的變更進行多視角審查。

```
同 Wave 無 pending 任務
    |
    v
[強制] /parallel-evaluation（Wave 完成審查）
    視角：Consistency（跨 Ticket 一致性）、Regression（迴歸風險）、Gap（盲點偵測）
    |
    v
審查發現 → 建立 Ticket（/ticket create，不中斷，不詢問）
    |
    v
[再次查詢] ticket track list --status pending（查詢版本其他 Wave）
```

**觸發條件**：Wave 內所有 Ticket 已 completed（情境 C 的進入條件即為觸發條件）

**審查範圍**：本 Wave 內所有已完成 Ticket 涉及的變更檔案

**審查後處理**：
- 審查發現問題 → 立即建立 Ticket（遵循 plan-to-ticket-flow 執行中額外發現規則）
- 無問題發現 → 繼續 C1/C2 流程

**動作**：[再次查詢] `ticket track list --status pending`（查詢版本其他 Wave）

#### 情境 C1：版本有其他 Wave 的 pending 任務

AskUserQuestion #3a（Wave 收尾 + 開始下一 Wave）

| 選項 | 說明 |
|------|------|
| 開始 Wave X+1（{n} 個待處理任務）（Recommended） | 直接進入下一個 Wave |
| Handoff，下一 session 開始 Wave X+1 | 結束 context，下個 session 繼續 |
| 先提交變更再決定 | git commit 後重新確認 |

#### 情境 C2：版本無任何待處理任務（版本全部完成）

```
[強制] 版本收尾技術債整理
    → 檢查 todolist.yaml 未排程項目
    → 有技術債 → /ticket batch-create 歸入下一版本
    → 無技術債 → 繼續
    |
    v
[強制] /version-release check
→ AskUserQuestion #13（版本推進確認）
```

> 技術債整理流程：.claude/rules/flows/version-progression.md（版本收尾技術債整理流程章節）

---

## Checkpoint 3：後續任務路由（AskUserQuestion #13）

**觸發時機**：分析/規劃/修改/TDD Phase 完成後，有多個後續路由可選

**動態選項（依 task_type）**：

| task_type | 選項 1 | 選項 2 | 選項 3 |
|-----------|--------|--------|--------|
| 分析完成 | 進入實作（建立 Ticket） | /parallel-evaluation F（結論審查） | 先 commit 再決定 |
| 規劃完成 | /parallel-evaluation C/G（審核） | 直接進入 TDD Phase 1 | 先 commit 再決定 |
| Phase 3b 完成（不符合豁免時才觸發 #13） | 進入 Phase 4a（Recommended） | 直接進入 Phase 4b | 先 commit 再決定 |
| Phase 4c + tech-debt 完成 | commit 並查看 Wave 狀態（Recommended） | Handoff，下個 session 繼續 Wave 路由 | 查看所有待處理 Ticket |
| incident 分析完成 | /parallel-evaluation F（結論審查） | 直接建立修復 Ticket | 先 commit 再決定 |
| Wave 完成（有下一 Wave） | 開始 Wave X+1（列出任務） | Handoff 到 Wave X+1 | 先 commit 再決定 |
| 版本完成（無待處理任務） | /version-release check | 查看 ticket track summary | 延後版本推進 |

---

## Checkpoint 4：parallel-evaluation 觸發確認（AskUserQuestion #14）

**觸發時機**：TDD 階段完成或任務完成後，系統建議可用 parallel-evaluation

| 選項 | 說明 |
|------|------|
| 執行 /parallel-evaluation 情境 X（Recommended） | 啟動多視角掃描 |
| 跳過，直接進入下一步 | 觸發場景 12 省略確認 |
| 執行其他情境 | 選擇不同的 parallel-evaluation 情境 |

**parallel-evaluation 情境對照**：

| TDD 階段/事件 | 建議情境 | 視角 |
|--------------|---------|------|
| Phase 3b 完成（→ Phase 4a） | B（重構評估） | Redundancy, Coupling, Complexity |
| Phase 4b 完成（→ Phase 4c） | A（程式碼審查） | Reuse, Quality, Efficiency |
| SA 審查完成 | C（架構評估） | Consistency, Impact, Simplicity |
| 規則/Skill 變更 | G（系統設計） | Consistency, Completeness, CogLoad |
| incident 分析 | F（結論審查） | Evidence, Alternatives, Scope |

---

## Checkpoint R：Resume 後標準化接手流程

`ticket resume <id>` 完成後，CLI 自動輸出「建議下一步」（Checkpoint R）。PM 依此引導執行。

```
ticket resume <id>
    |
    v
[CLI 輸出 Checkpoint R]
  1. [ ] 獨立驗證 Ticket 描述數量/範圍（PC-007）
  2. ticket track claim <id>
  3. ticket track chain <id>（可選）
    |
    v
[PM] AskUserQuestion 確認接手方式（若有疑義）
    |
    +-- 已驗證，直接 claim → ticket track claim <id>
    +-- 需查看任務鏈 → ticket track chain <id>
    +-- 範圍有疑義 → 先更新 Ticket 再 claim
```

**核心原則**：resume 後不直接開始實作，先走 Checkpoint R 確認範圍再 claim。

---

## Handoff 強制動作與前置檢查

### Handoff 強制動作

選擇任何 Handoff 選項後，PM **必須**執行 `/ticket handoff` 建立標準 `pending/*.json` 檔案，**禁止**手動建立 `.claude/handoff/*.md` 交接文件。`/ticket handoff` 會自動判斷下一步方向（父/子/兄弟），確保 `resume --list` 在下一個 session 能正確偵測待恢復任務。

### Handoff 前置檢查（強制）

執行 `/ticket handoff` 前，必須先確認無殘留的 pending handoff，否則 CLI 會報錯「已存在 pending handoff」：

```bash
# 檢查是否有殘留的 pending handoff
ticket handoff --status

# 若有殘留（stale），清理後再執行 handoff
ticket handoff --gc --execute
```

**注意**：`.claude/handoff/pending/` 已列入 `.gitignore`，`pending/*.json` 由 `/ticket handoff` 在本地建立，不需要 git commit。執行 handoff 後可直接結束 session，無需提交這些檔案。

### #11 核心原則與共通規則

詳見 `.claude/references/askuserquestion-scene-details.md` 場景 11（「#11 核心原則：Handoff first」與「#11 共通規則：完成摘要 + /clear 選項」）。

---

## 流程省略防護

**AskUserQuestion #12**：主線程輸出含省略意圖關鍵字時，process-skip-guard-hook 自動偵測並提醒確認。

偵測的 6 類省略行為與選項詳見 `.claude/references/askuserquestion-scene-details.md` 場景 12。

---

## 相關文件

- `.claude/rules/core/decision-tree.md` - 主檔（第八層主幹流程圖）
- `.claude/rules/core/askuserquestion-rules.md` - AskUserQuestion 規則 Source of Truth（場景清單）
- `.claude/references/askuserquestion-scene-details.md` - 場景 1-17 完整操作細節（Source of Truth）
- `.claude/references/ticket-askuserquestion-templates.md` - AskUserQuestion 模板
- `.claude/rules/flows/ticket-lifecycle.md` - Ticket 生命週期

---

**Last Updated**: 2026-03-13
**Version**: 1.4.0 - 情境 C2 新增版本收尾技術債整理步驟（0.1.0-W50-008）
