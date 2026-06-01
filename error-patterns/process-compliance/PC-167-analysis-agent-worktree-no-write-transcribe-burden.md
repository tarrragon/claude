---
id: PC-167
title: 分析代理人 worktree 內無 commit ticket body，PM 接手須 transcribe
category: process-compliance
severity: medium
source_case: 0.19.0-W4-015
created: 2026-05-31
---

# PC-167: 分析代理人 worktree 內無 commit ticket body，PM 接手須 transcribe

## 症狀

ANA / 純分析類代理人（如 saffron-system-analyst）在 worktree isolation 模式下完成分析任務，task-notification 回傳完整結論 summary，但**worktree branch HEAD 等於 PM pre-dispatch HEAD**（無新 commit）。

PM 接手後需手動 transcribe agent 結論到 main ticket 的 Problem Analysis / Analysis Result / Solution 章節，並完成剩餘 acceptance（如 spawn 子任務、commit、complete）。

## 典型場景

W4-015 觸發案例：

| 維度 | 觀察 |
|------|------|
| Agent | saffron-system-analyst |
| Dispatch mode | isolation: worktree (af2b28312fdc55bbc) |
| Agent 完成度 | task-notification 含完整 Stage 1/2/3 結論 + acceptance #1-#3 已達成數據 |
| Worktree branch commits | 0（HEAD 等於 PM pre-dispatch HEAD 472f4b5d） |
| Ticket body 寫入 | 無（main 端 Problem Analysis 仍為 placeholder） |
| Acceptance #4（spawn 子任務） | 阻塞（saffron 無 `ticket create` 權限） |
| PM 接手成本 | transcribe ~50 行 Problem Analysis 表格 + spawn IMP + check-acceptance + complete |

## 根因（推測）

| 層級 | 機制 |
|------|------|
| L1 Agent 推論偏誤 | Agent 看到任一 acceptance 因權限受限無法獨立完成（如 #4 spawn 子任務）即 abort 後續所有 acceptance commit 工作，回報 PM「needs context / blocked」而非「partial_success」 |
| L2 Prompt 指引缺失 | PM 派發 prompt 雖含「填 Problem Analysis / Analysis Result」但未明示「先 append-log + commit 完成部分，再回報剩餘需 PM 接手的部分」分階段策略 |
| L3 Worktree state propagation | 即使 agent 在 worktree 內 append-log 成功修改 ticket file，無 git commit 步驟，main 端 merge 不到（與 W4-009 thyme 做 3 個 commit 對比明顯） |

## 觸發條件

以下條件疊加時風險升高：

1. **Agent type 屬「分析角色」**（saffron / bay 等不含 ticket create / set-status 等寫入權限）
2. **Acceptance 含至少一項需 PM 接手的步驟**（spawn 子任務 / build 衍生 IMP 等）
3. **Isolation mode 為 worktree**（agent 在隔離環境，PM 無法即時介入）
4. **Prompt 未明示「分階段 commit」策略**

## 防護措施

### 短期（PM 派發 prompt 模板）

派發分析代理人 + worktree isolation 時，prompt 必須含：

```
完成每階段（acceptance 對應）後：
1. ticket track append-log <id> "$(cat <<'EOF' ... EOF)" --section "<章節名>"
2. git commit -m "chore(<id>): stage N analysis result"
3. 即使後續階段因權限受限無法獨立完成，已完成階段必須先 commit 再回報

若 acceptance 含 spawn 子任務 / build 衍生 IMP（你無權限）：
1. 在 append-log 內明示「acceptance #X 需 PM spawn <類型> ticket，建議內容如下：<具體 spec>」
2. Exit Status 回報 partial_success，acceptance_met 含已完成項
```

### 中期（Agent definition 補強）

saffron-system-analyst / bay-quality-auditor 等分析代理人的 agent definition（區塊 1「允許產出」）應明示：

| 項目 | 要求 |
|------|------|
| 部分完成 commit | 每 stage 完成後必須 append-log + commit，禁止全部 acceptance 結論只回傳 task-notification 而不寫入 ticket |
| 權限受限項處理 | 在 append-log 內明示「需 PM 接手的具體 spec」，禁止靜默 skip |

### 長期（Hook 強制層）

`subagent-stop` hook 可檢查：worktree branch 內 commit 數 = 0 且 agent type ∈ {saffron, bay, ...} 時，輸出 warning 提示 PM「分析代理人無 commit，須 transcribe」。

## 案例

**0.19.0-W4-015**:
- saffron 完成 Stage 1/2/3 分析，task-notification 含完整數據
- worktree branch (af2b28312fdc55bbc) HEAD = PM pre-dispatch HEAD 472f4b5d
- PM 接手 transcribe Problem Analysis (3 個表格 + 結論段) + Solution (Analysis Result + spawn 規劃) + spawn W4-019 IMP + check-acceptance --all + complete
- transcribe cost ~5 tool calls，本可由 saffron 在 worktree 完成

**對比 0.19.0-W4-009**:
- thyme-extension-engineer 完成 Stage 1/2 + check-acceptance + complete
- worktree branch (a7718b0eaf89c2543) 含 3 commits（Stage 1 / Stage 2 / metadata sync）
- PM 接手僅需 merge to main + spawn out-of-scope follow-ups
- transcribe cost = 0

兩者差異：thyme 有 ticket create / complete 權限 → 全程自管；saffron 因權限受限 → 應用 partial commit 模式但實際 abort 全部 commit

## 關聯模式

- agent-definition-standard.md - 本模式建議補強分析代理人的「執行責任」段落
- PC-091 ANA followup must be children - 與 spawn 衍生關係相關
- PC-115 .claude/ edit transient deny - 與 worktree isolation 相關但機制不同
- quality-baseline 規則 5 所有發現必須追蹤 - 本 PC 即為發現追蹤實例

---

**Source**: 0.19.0-W4-015 saffron worktree no-write 觀察 + PM transcribe 接手案例
