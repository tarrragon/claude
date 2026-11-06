---
id: PC-GPD-003
title: worktree 隔離檢查拒收多行內容加串接的 CLI 命令，代理人壓平 markdown 後章節標題失效阻擋 complete
category: process-compliance
severity: medium
source_case: 單行 token 替換型 IMP 票於 worktree 補寫 Solution 自檢章節（2026-09-01）
created: 2026-09-01
---

# PC-GPD-003: worktree 隔離檢查拒收多行內容加串接的 CLI 命令，代理人壓平 markdown 後章節標題失效阻擋 complete

## 症狀

代理人在 `isolation: worktree` 下執行 `ticket track append-log <id> "<多行內容>" --section Solution; echo rc=$?` 這類命令時，Claude Code 平台的 worktree 隔離檢查拒絕執行。這項檢查屬於平台 runtime，不是專案 hook。拒絕訊息原文如下：

```
This agent is isolated in the worktree <wt>, but this command runs ticket with a value computed at runtime (command output) inside a construct too complex to verify, so what it runs cannot be shown not to be git. Refusing to run it — a worktree-isolated agent's git operations must target its own worktree. Split it into plain, separate commands and run them from <wt>.
```

觸發的是兩個條件的組合：一是多行內容或命令替換，二是 `;` 串接。只有其中一個條件時不會被拒（實測見下方〈觸發判準實測〉）。

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
| L1 平台靜態檢查無法驗證組合結構 | 平台要確認隔離代理人的命令不會對 worktree 以外的位置執行 git。命令同時含多行內容（或命令替換）與 `;` 串接時，平台判為 `construct too complex to verify`，拒絕執行。內容含 git 字樣時，訊息改為 `names git in a form too complex to verify`。只有換行時不會被拒，所以「含換行即拒」的理解不正確 |
| L2 代理人降級策略錯誤 | 代理人選擇「壓成單行以通過守衛」，保住了字面內容卻丟失結構。對 markdown 而言換行是語意載體，不是排版裝飾 |
| L3 gate 與寫入端判準不對稱 | 寫入端（append-log）不驗證章節結構，驗收端（complete gate）要求行首標題。中間沒有任何一層在內容被壓平當下發出訊號 |

三層共振的結果是：代理人以為補完了、gate 說沒補、PM 看內容明明在——三方各自正確，衝突點在「章節」的定義從未統一。

## 觸發條件

同時滿足：

1. 代理人以 `isolation: worktree` 派發
2. 任務要求寫入含子章節、條列或程式碼標記的 ticket body
3. 寫入命令同時含多行內容（或 heredoc 命令替換）與 `;` 串接，例如 `"$(cat <<'EOF' ... EOF)"; echo rc=$?`。派發 prompt 要求「以 `out=$(...); rc=$?` 記錄 rc」時，代理人容易寫出這個形態
4. ticket schema 對該章節有行首標題層級的必填檢查

### 觸發判準實測

在 `isolation: worktree` 的唯讀探針代理人內，各形態只送一次，逐字照抄，不重試。平台檢查是靜態判定，每種形態測一次即可。測試命令為 `ticket track query <id>` 加上不同參數，不寫入：

| 形態 | 平台拒絕 | 結果 |
|---|---|---|
| 單引號多行參數，無串接 | 否 | argparse `unrecognized arguments`，rc=2 |
| heredoc 命令替換，無串接 | 否 | argparse `unrecognized arguments`，rc=2 |
| 單行參數 + `; echo rc=$?` | 否 | 正常查詢，rc=0 |
| 單行，無串接（對照組） | 否 | 正常查詢 |

在被觀測的代理人 transcript 中，被拒的樣本共 7 次，每次都同時含多行內容（或命令替換）與 `; echo rc=$?`。代理人去掉串接、改成單行後才通過。尚未實測的形態是「多行內容、無串接」的實際 append-log 寫入：探針為避免寫入，只用了查詢命令。

## 處置

| 角色 | 動作 |
|------|------|
| 代理人 | 平台拒收時，照拒絕訊息拆成單一命令，屬於 `tool-selection` 規則 2 的「too complex to verify」例外。拆分時不要把內容壓成單行。首選以 Write 寫入 scratchpad 內容檔（非票檔）再 `append-log --content-file <路徑>` 傳入（命令列不含換行）；`--content-file` 不可用時改為分次 `append-log` 逐段追加（每次單行），或於 NeedsContext 記錄「內容已備妥但無法保留換行」並交由 PM 落檔 |
| PM | 於主倉庫（無 worktree guard）以 `ticket track append-log --section <章節> --replace` 重寫該章節，還原換行、標題層級與 backtick。文字內容取自代理人產出，不改寫，並於節末標註排版還原者與原因 |
| PM | 禁止代填章節的實質內容——排版還原與內容代寫是兩件事。前者可做，後者等於捏造代理人的自檢記錄 |

## 預防

- worktree 派發一律以 `ticket track dispatch --isolation worktree` 產生骨架。骨架已含多行內容指引；手寫 prompt 會遺失這一行，同一天已觀測到兩次。需要補充的內容附加在骨架之後
- 派發 prompt 若要求代理人寫入含子章節的 ticket body，明示「多行內容以 scratchpad 內容檔加 --content-file 傳入，不得壓成單行」
- 派發 prompt 不要求隔離代理人把寫入命令與 `; echo rc=$?` 串接。rc 由工具結果的 exit code 判讀
- 章節結構檢查應前移到寫入端：`append-log` 收到含 `###` 但不在行首的內容時發 WARNING，而非留到 complete gate 才擋
- 判斷是否命中本模式的最快檢查：`grep -n '^### 自檢結果' <ticket.md>`。有內容但無行首命中，即為壓平

## 邊界

本模式與 IMP-066（subagent 在 worktree 下看不到主 repo 新建 ticket）、PC-167（分析代理人 worktree 內無 commit，PM 須 transcribe）同屬 worktree 隔離的副作用族，但機制不同：IMP-066 是可見性、PC-167 是零寫入、本模式是寫入成功但結構受損。前兩者代理人交白卷，本模式代理人交出看似完成的產出，因此更難察覺。

## 相關

- `.claude/error-patterns/implementation/IMP-066-subagent-worktree-ticket-cli-invisible.md`
- `.claude/error-patterns/process-compliance/PC-167-analysis-agent-worktree-no-write-transcribe-burden.md`
- `.claude/rules/core/bash-tool-usage-rules.md` 規則五（長文字用 heredoc；本模式為該規則在 worktree 下的失效情境）
- `.claude/rules/core/structured-content-generation.md`（章節結構應由工具制式化，非依賴寫入者手工維持）
