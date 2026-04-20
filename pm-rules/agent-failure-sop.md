# 代理人失敗 SOP（PC-045）

> **來源**：PC-045 — PM 代理人失敗時自行撰寫產品程式碼。

代理人派發後可能出現以下情況。PM **永遠不自己寫程式碼**，而是按 SOP 處理。

---

## 代理人完成確認 SOP（強制，來源 PC-050）

> **核心原則**：收到完成通知 ≠ 全部完成。必須清點 dispatch-active.json 確認所有代理人都已完成。

**收到任何代理人完成通知時**，執行以下兩步：

```bash
# 步驟 1：確認剩餘活躍派發
cat .claude/dispatch-active.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
if d:
    print('[WAIT] 仍有 {} 個代理人在執行：'.format(len(d)))
    for x in d:
        print('  - {}'.format(x.get('agent_description', '?')))
else:
    print('[OK] 所有代理人已完成，可開始驗收。')
"
```

```bash
# 步驟 2：確認分支狀態
pwd && git branch --show-current
git worktree list
git branch | grep feat/
```

| 結果 | 行動 |
|------|------|
| 仍有活躍派發 | **等待**：不做 commit/merge/complete，切去做其他 Ticket 準備工作 |
| 無活躍派發 | 開始驗收：檢查變更 → commit → merge |

**補充驗證工具**：對懷疑尚未完成但 dispatch-active.json 已清除的代理人（Hook 延遲清理 / race 情況），可呼叫 `TaskOutput(task_id=<agentId>, block=false, timeout=3000)` 確認 `<status>` 標籤。此為補充，非取代 dispatch-active.json（後者為計數 Source of Truth）。安全使用規則見 PC-050「TaskOutput 安全使用範本」。

> 完整 Checkpoint 流程（含 1.85 代理人清點）：.claude/pm-rules/completion-checkpoint-rules.md

---

## 失敗判斷前置步驟（強制）

> **禁止**：看到主倉庫 `git status` 沒有變更就直接判定代理人失敗。代理人可能在 worktree 或 feature 分支上完成了工作。

判斷代理人是否失敗**之前**，必須先確認：

| 步驟 | 命令 | 目的 |
|------|------|------|
| -1 | `find .claude/hook-logs -name "*.log" -mmin -5 -exec grep -l "ERROR\|Exception\|TypeError" {} \;` | 檢查是否有 Hook error 干擾代理人（防範環境異常誤判） |
| 0 | `cat .claude/dispatch-active.json` | 確認代理人是否仍在活躍派發中（可能還沒完成） |
| 0.5 | `TaskOutput(task_id=<agentId>, block=false, timeout=3000)` 讀 `<status>` 標籤 | 對懷疑失敗的代理人確認 runtime 狀態（補 PC-050 模式 D 盲點） |
| 0.5-A | **派發時間閾值檢查**：若代理人派發距今 < 2 分鐘且收到 Hook 完成訊號，Step 0.5 **強制執行**（禁用 Hook 訊號作為失敗依據） | 防 PC-050 模式 E / PC-070：Hook 廣播訊號與 runtime 狀態不同步 |
| 1 | `pwd && git branch --show-current` | 確認當前分支（可能被代理人污染到其他分支） |
| 2 | `git worktree list` | 檢查是否有 worktree 包含代理人的 commit |
| 3 | `git branch \| grep feat/` | 檢查是否有 feature 分支包含代理人的 commit |
| 4 | `git log main..{branch} --oneline` | 查看分支上的未合併 commit |

> **Hook error 可見性**：terminal 上的 Hook error 只有用戶看得到，PM 和代理人都看不到。代理人完成後 `agent-commit-verification-hook` 會自動掃描 hook-logs 並輸出摘要，但 PM 主動判斷時仍需執行 Step -1 確認環境是否正常。

> **Step 0.5 TaskOutput 安全規則**：只讀 `<status>` 標籤（`running`/`completed`/`error`），**禁止讀 `<output>` body**（流式 JSONL transcript，會污染 context 且違反 PC-050 模式 D 防護）。若 `<status>` 為 `running`，不可判失敗。完整安全範本見 .claude/error-patterns/process-compliance/PC-050-premature-agent-completion-judgment.md 「TaskOutput 安全使用範本」章節。

> **Step 0.5-A 派發時間閾值強制條款（PC-050 模式 E / PC-070）**：若以下條件**同時成立**，Step 0.5 TaskOutput 查詢**強制執行**，禁止基於 Hook 訊號推論失敗：
>
> 1. 代理人派發距今 **< 2 分鐘**（派發時間戳可從 `dispatch-active.json` 歷史或 agent 派發紀錄取得；無紀錄時採保守預設：假設 < 2 分鐘）
> 2. 觀察到 Hook 廣播完成訊號（`PostToolUse:Agent hook additional context` 或 `dispatch-active.json` 清空）
> 3. 目標檔案 `git status` 無變更 / ticket Solution 仍為模板
>
> **行動**：執行 `ToolSearch(query="select:TaskOutput")` → `TaskOutput(task_id=<agentId>, block=false, timeout=3000)` → 只讀 `<status>`。若 `running`，**停止推論、等完成通知**。
>
> **替代假設檢查**：在 Step 0.5 結果出來前，PM 至少生成 2 個假設（A: 代理人失敗；B: 代理人仍在工作）。單一假設錨定違反 PC-070 根因 4。

**只有 hook-logs 無 error 且 dispatch-active.json 為空且 TaskOutput `<status>` 非 running 且所有分支都沒有代理人的 commit 後，才能判定代理人失敗。**

---

## 失敗類型與處理

| 失敗類型 | 症狀 | PM 處理方式 |
|---------|------|-----------|
| 看似沒改 | source 無變更（但可能在其他分支） | **先執行前置步驟**，確認無分支 commit 後才判定失敗 |
| 完全沒改 | 前置步驟確認無任何分支有 commit | 檢查 prompt 是否清楚，**重新派發** |
| 改了錯誤檔案 | 修改了非目標檔案 | 回退變更，調整 prompt 指定檔案，重新派發 |
| 回合耗盡 | 代理人報告截斷，部分完成 | 簡化 prompt（減少讀取範圍），重新派發 |
| 改壞既有測試 | 舊測試 FAIL | 回退變更，在 prompt 加入「不可修改測試」約束，重新派發 |
| 背景代理人超時 | 長時間無回應 | 用 SendMessage 催促摘要，或取消後重新派發 |

---

## 重試守則：保持原 Ticket scope

重新派發代理人時**禁止擴大原 Ticket 的工作範圍**。保持原驗收條件作為 prompt 的邊界。

| 場景 | 正確 | 錯誤 |
|------|------|------|
| 代理人只做了 2/5 子命令 | prompt 指明「剩餘 3 個子命令」 | 改寫為「全部 6 個子命令」覆蓋原 scope |
| 代理人改了錯誤檔案 | 回退變更 + 明確指定正確檔案 | 一併要求代理人處理其他周邊檔案 |
| 代理人回報部分完成 | 續做剩餘部分，驗收條件不變 | 趁機追加新驗收條件 |

**原因**：擴大 scope 會讓代理人再次耗盡回合；驗收條件偏移也會讓後續審查失真。若需擴大範圍，應建立新 Ticket 追蹤，不要夾帶到重試 prompt。

---

## 處理流程

```
代理人完成但結果不符預期
    |
    v
0. 執行失敗判斷前置步驟（檢查分支和 worktree）
    |
    v
1. 確認失敗類型（上表）
    |
    v
2. 分析原因（prompt 不清？任務太大？檔案指定錯誤？）
    |
    v
3. 調整 prompt → 前台重新派發
    |
    v
4. 如果連續 2 次失敗 → 建立 incident Ticket 分析根因
    |
    v
[禁止] 永遠不自己寫程式碼，連「幫忙修一小段」都不行
```

---

## 常見滑坡場景（必須警覺）

| 場景 | 誘惑 | 正確做法 |
|------|------|---------|
| PM 剛寫完 RED 測試，代理人 GREEN 失敗 | 「我已經知道怎麼做了，自己寫比較快」 | RED 測試完成是角色切換斷點，GREEN 只能派發 |
| 只差一行就能修好 | 「改一行不算寫程式碼吧」 | 算。派發代理人改那一行 |
| 用戶在等結果，時間壓力大 | 「先自己做，下次再改流程」 | 背景派發後去做其他 Ticket 準備工作，代理人完成再回來驗收 |

---

## 相關文件

- .claude/rules/core/pm-role.md — 核心禁令與情境路由
- .claude/pm-rules/completion-checkpoint-rules.md — 完整 Checkpoint 流程
- .claude/references/pm-agent-observability.md — TaskOutput 安全範本
- .claude/error-patterns/process-compliance/PC-045-pm-writes-product-code-on-agent-failure.md
- .claude/error-patterns/process-compliance/PC-050-premature-agent-completion-judgment.md
- .claude/error-patterns/process-compliance/PC-070-pm-hook-signal-agent-failure-inference.md

---

**Last Updated**: 2026-04-16
**Version**: 1.0.0 — 從 rules/core/pm-role.md 拆出（W10-076.2 拆分；原檔 v3.7.0 L162-L292）
**Source**: PC-045 + PC-050 + PC-070 教訓疊加
