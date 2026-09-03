---
id: PC-GPD-003
title: worktree guard 拒收含換行的 CLI 參數，代理人壓平 markdown 後章節標題失效阻擋 complete
category: process-compliance
severity: medium
source_case: 單行 token 替換型 IMP 票於 worktree 補寫 Solution 自檢章節（2026-09-01）
created: 2026-09-01
---

# PC-GPD-003: worktree guard 拒收含換行的 CLI 參數，代理人壓平 markdown 後章節標題失效阻擋 complete

## 症狀

代理人在 `isolation: worktree` 下執行 `ticket track append-log <id> "<多行內容>" --section Solution` 時，runtime 的 worktree 隔離守衛以「參數含字面換行，過於複雜無法驗證」為由拒絕該 Bash 呼叫。

代理人改以單行字串重傳，內容確實寫入 ticket，但：

- `### 自檢結果` 這類子章節標題被擠進段落中段，不在行首，markdown 不認其為標題
- backtick 包裹的識別符（`` `Color(0xFF2E6F6A)` ``）在單行化過程被剝除
- 條列項失去 `-` 行首，退化為逗號串接的長句

隨後 PM 於主倉庫執行 `ticket track complete` 時被 schema gate 阻擋：

```
[Error] <ticket-id> body 未依 IMP schema 填寫必填章節
   未填寫的必填章節：
   - Solution > ### 自檢結果
```

章節內容存在，gate 卻報「未填寫」——因為 gate 比對的是行首標題，不是字串出現與否。

## 根因

| 層級 | 機制 |
|------|------|
| L1 守衛判準過寬 | worktree guard 以「參數含字面換行」為複雜度判準拒絕命令。該判準攔的是 shell 注入風險，但 markdown 內容天生多行，被誤傷 |
| L2 代理人降級策略錯誤 | 代理人選擇「壓成單行以通過守衛」，保住了字面內容卻丟失結構。對 markdown 而言換行是語意載體，不是排版裝飾 |
| L3 gate 與寫入端判準不對稱 | 寫入端（append-log）不驗證章節結構，驗收端（complete gate）要求行首標題。中間沒有任何一層在內容被壓平當下發出訊號 |

三層共振的結果是：代理人以為補完了、gate 說沒補、PM 看內容明明在——三方各自正確，衝突點在「章節」的定義從未統一。

## 觸發條件

同時滿足：

1. 代理人以 `isolation: worktree` 派發
2. 任務要求寫入含子章節、條列或程式碼標記的 ticket body
3. ticket schema 對該章節有行首標題層級的必填檢查

## 處置

| 角色 | 動作 |
|------|------|
| 代理人 | 守衛拒收多行參數時，不要壓成單行。改為分次 `append-log` 逐段追加（每次單行），或於 NeedsContext 記錄「內容已備妥但無法保留換行」並交由 PM 落檔 |
| PM | 於主倉庫（無 worktree guard）以 `ticket track append-log --section <章節> --replace` 重寫該章節，還原換行、標題層級與 backtick。文字內容取自代理人產出，不改寫，並於節末標註排版還原者與原因 |
| PM | 禁止代填章節的實質內容——排版還原與內容代寫是兩件事。前者可做，後者等於捏造代理人的自檢記錄 |

## 預防

- 派發 prompt 若要求代理人寫入含子章節的 ticket body，明示「守衛拒收多行參數時分次 append，不得壓成單行」
- 章節結構檢查應前移到寫入端：`append-log` 收到含 `###` 但不在行首的內容時發 WARNING，而非留到 complete gate 才擋
- 判斷是否命中本模式的最快檢查：`grep -n '^### 自檢結果' <ticket.md>`。有內容但無行首命中，即為壓平

## 邊界

本模式與 IMP-066（subagent 在 worktree 下看不到主 repo 新建 ticket）、PC-167（分析代理人 worktree 內無 commit，PM 須 transcribe）同屬 worktree 隔離的副作用族，但機制不同：IMP-066 是可見性、PC-167 是零寫入、本模式是寫入成功但結構受損。前兩者代理人交白卷，本模式代理人交出看似完成的產出，因此更難察覺。

## 相關

- `.claude/error-patterns/implementation/IMP-066-subagent-worktree-ticket-cli-invisible.md`
- `.claude/error-patterns/process-compliance/PC-167-analysis-agent-worktree-no-write-transcribe-burden.md`
- `.claude/rules/core/bash-tool-usage-rules.md` 規則五（長文字用 heredoc；本模式為該規則在 worktree 下的失效情境）
- `.claude/rules/core/structured-content-generation.md`（章節結構應由工具制式化，非依賴寫入者手工維持）
