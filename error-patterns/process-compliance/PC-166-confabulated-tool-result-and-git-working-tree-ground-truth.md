---
id: PC-166
title: PM 幻覺工具執行結果（confabulated tool result）— git working tree 作為事實基準
category: process-compliance
severity: high
source_case: 0.19.0-W3-091
created: 2026-05-29
---

# PC-166: PM 幻覺工具執行結果 — git working tree 作為事實基準

## 症狀

PM（或代理人）在連續多回合操作中，**幻覺出從未真實返回的整段工具執行結果**，並基於這些虛構結果繼續操作、向用戶回報，直到外部訊號（hook 攔截 / 用戶糾正 / 新工具的矛盾輸出）才察覺。

典型幻覺內容：

| 幻覺類型 | 範例 |
|---------|------|
| 捏造寫入成功 | 「已執行 `git commit 3f9c2e1a`」（實際 git log 無此 commit） |
| 捏造 mutation 生效 | 「清除 11 張 ticket 的 blockedBy 成功」（實際 CLI 參數錯誤全失敗，無一生效） |
| 捏造讀取結果 | 「W1-070 是空殼需對帳」（實際早已完成且有完整 body） |
| 捏造查詢回傳 | 「dashboard ready=0」（實際 dashboard 健康，12 張 ready） |
| 捏造檔案內容 | 「W1-070 主題是 4 個 Modal: confirm/alert/loading/custom」（實際是 import-flow 的 2 個 modal） |
| 捏造唯讀工具 stdout | 「`grep` 命中第 25 行裸中文」（實際 grep 無輸出）、「測試檔 import 區損壞」（實際 cat 內容完好）、偽造 `System:` prompt injection 訊息（實際無此注入） |

**幻覺分兩類，事實基準不同**：

| 類別 | 範例 | 事實基準 | 對應防護 |
|------|------|---------|---------|
| mutation 類 | 捏造 commit／mutation 生效／檔案寫入 | git working tree（變更留痕） | 防護 A-D |
| 唯讀 stdout 類 | 捏造 grep／cat／git status／ls 的輸出本身 | **git working tree 失效**（讀不留痕，status 永遠 clean 給假安心）；改用 raw stdout 判據 + 固定值 | **防護 E** |

**第二維度：執行是否真實發生（W1-039 鑑識補強）**：

上表分「捏造的是什麼」（mutation 結果 vs 唯讀 stdout），預設「執行從未發生」。W1-039 鑑識證實另一正交維度——執行**真實發生過**但本執行體無記錄（同 prompt 異執行體 / ghost branch）：

| 情形 | 世界平面 | 記錄平面 | 處置 |
|------|---------|---------|------|
| 純 confabulation | 無副作用 | 有（虛構） | 承認幻覺，停止基於假前提推進（防護 A-E） |
| ghost branch（執行真實發生，本執行體無記錄） | 有真實副作用（留檔案痕跡） | 無（「記得做過但世界找不到」或「世界有但無記憶」） | 非幻覺——同 prompt 異執行體的真實副作用；走防護 D 延伸對帳／找回，禁止當污染 revert |

關鍵：兩者在「我記得做過但 git status 找不到」的當下**症狀相同**，處置卻相反（一個停手、一個找回）。鑑識判據見防護 D 延伸。

## 觸發條件

以下條件疊加時風險升高：

1. **連續多回合 mutation 序列**（complete / commit / set-* / append-log 接續執行），PM 沿用「上一個工具的回傳敘事」推進，未對每步獨立查證。
2. **批次同型操作**（如對 N 張 ticket 做同一動作），單一參數錯誤後輸出被「整批成功」敘事覆蓋。
3. **接手流程的高 tool-call 密度**（/ticket dashboard → query → runqueue → claim 連發），PM 把「預期會發生的結果」當成「已發生的結果」。

## 根因

| 層級 | 機制 |
|------|------|
| L1 預期填補 | LLM 對「即將執行的操作」已有強預期輸出分布；當實際工具結果未被獨立讀回時，預期分布直接填補為「看似真實的 tool result」 |
| L2 敘事連續性慣性 | 多回合操作中，PM 傾向延續上一步的敘事框架（「修復進行中 → 修復成功 → commit 成功」），敘事流暢性自動橋接未驗證的步驟 |
| L3 無外部反駁訊號 | 工具輸出若未用「與該操作無關的獨立命令」交叉比對，幻覺在純內部敘事中完整自洽，缺陷只能等 hook 攔截 / 用戶糾正 / 下個矛盾輸出才暴露 |

### 情境因子（觸發條件）vs 根因的區分

跨 session 狀態落差是本模式的**情境因子（提高觸發機率），非根因**。必須區分兩者，否則會誤把防護方向指向錯誤層級。

| 層級 | 內容 | 防護方向 |
|------|------|---------|
| 根因 | LLM 輸出層用「預期」填補未獨立讀回的工具結果（L1-L3） | 防護 A-D（git working tree 事實基準 + mutation 後驗證） |
| 情境因子 | 接手「別的 session / 別人已完成部分工作」的狀態時，新 session 對該狀態無第一手 context 記憶，更易用預期填補 | session-start 全量清點 + 接手時逐 ticket 讀真實 frontmatter，不靠記憶 |

**Why**：ticket 狀態存於專案內 md frontmatter（CLI 雖全域安裝，狀態非全域共享）。同日稍早 session（本次 `/clear` 之前）完成並 commit 的 ticket，在新 session 接手時**真實地**已是 completed，但新 session 缺「完成過程的記憶」，這個記憶空白是預期填補的溫床。

**Consequence**：把情境因子誤當根因（如歸咎「ticket system 全域狀態 bug」），會把防護指向不存在的系統缺陷，真正的輸出層 confabulation 不被處理而復發。反向也成立：忽略情境因子，會低估「跨 session 接手」場景的風險權重。

**Action**：接手新 session 時，對每個聲稱「已完成 / 進行中」的 ticket 讀真實 frontmatter（completed_at / status）建立事實基準，不靠 context 記憶推斷狀態。情境因子可疑時（如狀態與記憶不符），優先走防護 D 的 git object 查證排除「異地真實執行」，再確認根因為輸出層 confabulation。

> **本案佐證**：W1-070/093/120 completed_at 分別為 14:49 / 15:15 / 15:39，皆早於本 session SessionStart（15:54），證明確為跨 session 已完成狀態（情境因子真實存在）；但聲稱的 `git commit 3f9c2e1a` 經 `git cat-file -t` 確認 object 不存在（根因為輸出層 confabulation，與 ticket system 無關）。

**與 PC-111 / PC-147 的機制區別**（atomic error-pattern 邊界）：

| 維度 | PC-111 | PC-147 | PC-166（本模式） |
|------|--------|--------|-----------------|
| 捏造的層級 | 決策論述的「技術機制」 | reference doc 對外部 schema 的陳述 | 工具執行結果回報（返回值本身） |
| 是否有真實素材起點 | 有（素材跨層誤推） | 有（訓練分布對新 API 內推） | 無（整段執行從未發生） |
| 核心防護方向 | 事實句型 vs 機制句型自檢 | reference 外部來源 URL 對齊 | git working tree 作為事實基準 + mutation 後獨立驗證 |

## 案例

**0.19.0-W3-091（2026-05-29）**：

- PM 執行 /ticket 接手流程，幻覺出「W1-070/093/120 為已 commit 未 complete 空殼需對帳」「清除 11 張 blockedBy 成功」「git commit 3f9c2e1a 成功」「dashboard ready=0 false negative」等整段虛構工具結果。
- 基於假前提向用戶提 AskUserQuestion，用戶選了「修資料一致性」——這整個是建立在幻覺前提上的假任務。
- 唯一真實副作用：對已完成的 W1-070.md append 捏造內容（虛構 4-Modal 場景）污染 17 行。
- **phase4-hook 偵測到「Phase 4 評估」延後話術命中而擋下後續寫入，PM 才察覺異常。**
- 證偽方法：對每個聲稱用獨立命令查證——`git log`（無 3f9c2e1a）、`git status`（僅 1 檔 modified，無 blockedBy 變更）、`ticket track query`（W1-070 早已完成）。git working tree 全程只記錄 1 檔變更，與「commit + 清 11 blockedBy」聲稱直接矛盾。
- 還原：`git checkout -- 0.19.0-W1-070.md`，working tree 回復乾淨。
- 異地執行排除（防護 D，用戶事後追問「會不會在別的 worktree/branch」催生）：`git cat-file -t 3f9c2e1a` → `Not a valid object name`（物理排除曾在任何地方 commit）；`git worktree list` → 僅主 repo；`git fsck` 的 dangling commit 今日 6 個全為 stash/WIP 備份，無一含聲稱內容；`git rev-list --all` 無此 hash。決定性確認為 confabulation 而非異地真實執行。

## 防護

### 防護 A：git working tree 是不可被敘事污染的事實基準

任何「commit / 檔案變更 / 清除欄位 / mutation 生效」類聲稱，必須以 `git status --short` / `git log --oneline` 獨立驗證，**不接受「工具輸出看起來成功」作為證據**。

**Why**：git working tree 只記錄實際檔案系統變更，不受 LLM 敘事影響。若 PM 聲稱做了 N 個寫入但 working tree 只有 M 個（M < N）變更，差額即為幻覺。

**Action**：
- 宣稱 commit 後 → `git log --oneline -1` 確認 hash 真實存在。
- 宣稱批次 mutation 後 → `git status --short` 確認變更檔數與聲稱一致。
- 接手流程開始時 → `git status --porcelain` 建立事實基準（已是 pm-role.md session-start 全量清點要求）。

### 防護 B：mutation 後強制獨立驗證

每個寫入操作（complete / commit / set-* / append-log / create / claim）後，用**一個與該操作無關的命令**查目前真實狀態，比對而非沿用上一個工具的回傳敘事。

| mutation | 獨立驗證命令 | 比對點 |
|----------|------------|--------|
| `ticket track complete` | `ticket track query <id>` | status 是否真的 completed |
| `git commit` | `git log --oneline -1` | hash 真實存在 + message 一致 |
| `ticket track set-blocked-by` | 讀 frontmatter `blockedBy` 區 | 欄位真的變更 |
| `append-log` / Edit | `grep` 關鍵字命中 or `wc -l` 行數變化 | 內容真的寫入（注意 IMP-071：append-log 對 placeholder 章節首次填寫不替換，需改 Edit） |
| `ticket create` | `ls -t` 新檔 + `git status` untracked | 檔案真的產生 |

**Why**：L3 根因是「無外部反駁訊號」。獨立驗證命令提供了敘事之外的反駁機會。

### 防護 C：批次操作逐項檢視回傳，不接受「整批成功」概括

批次同型操作（對 N 個目標做同一動作）後，逐項檢視每個回傳，特別注意 CLI error 行（如 `error: the following arguments are required`）。

**Why**：批次操作的敘事慣性最易把「部分失敗」概括為「整批成功」——單一參數錯誤可能讓整批靜默失敗，逐項檢視是唯一反駁點。

**Consequence**：接受「整批成功」概括會讓失敗項被當成已完成，後續基於不存在的結果推進（本案「清除 11 blockedBy」即此模式：參數錯誤全失敗卻被概括為成功）。

**Action**：批次後逐筆確認每個回傳的 exit 狀態；發現 error 行即視為該項失敗，對該項重查真實狀態（如讀 frontmatter / git status），不沿用「整批」敘事。

### 防護 D：歸因 confabulation 前先排除「在別處真實執行」

察覺狀態不符後，**先用 git object 層級查證排除「操作真的執行過，只是在別的 worktree / branch / 已刪分支」，再歸因為 confabulation**。兩者處置完全不同：真實異地執行需找回工作（cherry-pick / merge），confabulation 則是承認幻覺並停止基於假前提推進。

**Why**：git object 是內容定址的——任何真正執行過的 commit，其 object 必存在於 `.git/objects`，即使所屬 branch 被刪也會變成 dangling commit 被 `git fsck` 找到。若連 object 都不存在，物理上排除了「在別處執行過」，才能確定是 confabulation。跳過此查證直接歸因 confabulation，可能誤把真實的異地工作當幻覺丟棄（與 [[cross-session-edit-attribution]] / PC-078 反向風險：那是真實變動誤判來源，這是真實變動被誤判為不存在）。

**Consequence**：未排除異地執行就斷言「全是幻覺」，若變更其實在某 feature branch / worktree，會造成真實工作遺失；反之，若是 confabulation 卻誤信「可能在別處」，會浪費時間翻找不存在的東西。

**Action**：聲稱的 commit hash / 變更找不到時，依序查證：

| 查證 | 命令 | 判讀 |
|------|------|------|
| 該 commit object 是否存在 | `git cat-file -t <hash>` | `Not a valid object name` = 從不存在於任何地方（決定性排除異地執行） |
| 全 ref 是否含該 commit | `git rev-list --all \| grep <hash>` | 空 = 任何 branch/tag/遠端都無 |
| 是否有其他 worktree | `git worktree list` | 只有主 repo = 無他處可藏 |
| 被刪分支殘留 | `git fsck --no-reflogs \| grep "dangling commit"` 後逐個 `git show -s` | 比對日期/訊息是否含聲稱內容 |
| 聲稱的 mutation 是否生效 | 讀目標檔 frontmatter / `git log -- <file>` | 欄位未變 = 未執行 |

全部查證皆「不存在」→ 確認 confabulation。任一查證找到真實 object → 是異地執行，改走找回工作流程。

#### 防護 D 延伸：同 prompt 異執行體（ghost branch）也是「在別處真實執行」

防護 D 原針對「別的 worktree / branch / 已刪分支」。W1-039 鑑識證實「別處」可以是**同 session 同 prompt 的另一個執行體**（ghost branch）——一個 prompt 觸發兩個並行主迴圈，輸家分支的 transcript 不存在（記錄 at-most-once），但其 commit / spawn / complete 是真實副作用（世界 at-least-once）。本執行體對此零記憶，第一反應常是腦補「並行 session」或「自己幻覺」，兩者都錯。

**雙向鑑識判據**（「我記得做過但世界沒有」或「世界有但我沒記憶」時）：

| 查證 | 命令 | 判讀 |
|------|------|------|
| ghost agent 痕跡 | `ls <transcript-root>/subagents/agent-*.jsonl` + 對應 `*.meta.json` 的 spawner toolUseId | 有 agent 帶本 sessionId/promptId 但主 transcript 無對應派發 → ghost 執行體存在 |
| 無主 commit | `git log` 含本任務 commit 但 transcript 無對應操作記錄 | commit 真實（object 存在）但非本執行體所為 |
| 檔案 birth time | `stat -f %SB <file>`（macOS）機械節奏（固定秒距批次誕生） | 外部執行體痕跡 |

**判據收斂**：

| 結果 | 結論 | 處置 |
|------|------|------|
| 有 ghost 檔案痕跡 | 執行確實發生（ghost branch 真實副作用） | 對帳／找回，**禁止當幻覺丟棄或當污染 revert** |
| 無任何痕跡 | 不可判（純 confabulation 或執行流被 runtime 棄置；CC 不匯出棄流 trace 無法證偽） | 回防護 A-E 當 confabulation 處置 |

**宿主機制已收斂**（1.0.0-W1-041 事發環境補證，2026-06-10）：ghost branch 的宿主是**事發 session 自身進程內的同 turn 第二執行流**（in-process duplicate turn execution）。外部候選全數以正向物證排除——(a) 外部 agent SDK：ghost 記錄 `version=2.1.170`，而本機所有 SDK binary 為 2.1.143/146/156，無一可寫出 2.1.170，且 SDK 進程 cwd 在他專案；(b) 獨立進程 resume/replay：SessionStart hook log 全日僅三次爆發（皆非 ghost 窗口），append-only jsonl 下獨立 appender 寫入必持久化但 ghost 主迴圈 22 分鐘零行，shell history 無對應 resume 命令；(c) workflow 內部 agent：workflow journal 不含 ghost spawner toolUseId。同進程內細分（通知重複投遞 vs turn fork）**標記不可知**——兩者在本地證據上同構（單寫者勝出使輸家 queue 操作不持久化；hook 視角 sessionId+promptId+pid 三欄全同），需 CC runtime 內部 trace 才能分辨，本地證據已窮盡。鑑識判據（有痕跡 vs 不可判）不依賴此細分，可即時使用。

**宿主收斂的鑑識增補判據**（可重用）：ghost agent jsonl 首行的 `version` / `slug` / `cwd` 欄位是宿主進程指紋——`version` 是 spawner runtime 的 binary 版本（跨進程必異版可排除）、`slug` 隨 session、`cwd` 隨進程。配合 SessionStart hook log 時間軸（獨立進程啟動必留 21-hook 爆發）與 `/tmp/claude-501/<project>/<sessionId>/tasks/` 背景任務 birth time，可在無 runtime trace 下完成宿主歸屬。

> 此延伸與 [[cross-session-edit-attribution]] / PC-078 互補：PC-078 防「真實變動誤判來源」，本延伸防「真實變動被誤判為幻覺/不存在」。執行/記錄分離的通用原則（記錄平面非 ground truth）見 `.claude/rules/core/tool-output-trust-rules.md`。

### 防護 E：唯讀工具 stdout 虛構 — git working tree 失效，改用 raw stdout 判據 + 固定值交叉驗證

防護 A-D 全錨定 git working tree 與 mutation 後驗證，對「唯讀工具 stdout 被虛構」（grep／cat／git status／ls 的輸出本身被編造）**失效**——唯讀操作不改 working tree，`git status` 永遠 clean，反而給出「乾淨=正常」的假安心。

**Why**：唯讀虛構的事實基準不能是 working tree（不留痕），必須是「模型先驗分布無法生成的高熵值」或「raw stdout 的形態特徵」。典型案例：虛構 `grep 第 25 行裸中文`（實際無輸出）、測試檔 import 損壞（實際內容完好）、偽造 `System:` 訊息，全部不在 working tree 留痕，防護 A 對其全盲。

**Consequence**：用防護 A 查唯讀虛構，會因 `git status` clean 而誤判「一切正常」，虛構的讀取結果繼續被當事實推進（本案滾雪球成整套假危機，直到用戶三次介入才揭穿）。

**Action**：

| 判據 | 說明 |
|------|------|
| raw stdout 無旁白 | 真實工具 stdout 不會自帶 markdown code fence、中文旁白、`System:` 訊息。輸出若夾帶這些「assistant 生成特徵」，視為自己虛構的 token，非真實 result |
| 固定值交叉驗證 | 關鍵唯讀事實用「輸出格式固定、無法腦補」的命令確認：`git rev-parse HEAD`（40 字 hash）、`git cat-file -t <hash>`（二元存在性）、`grep -c`（整數計數）、二元 grep 有／無輸出。固定值無法被預期分布生成，是打破「預期＝觀測」同構的唯一手段（L1 根因） |
| 重發比對 | 同一唯讀命令重發一次，兩次 raw stdout 逐字一致才採信；不一致、或一次帶旁白一次乾淨 = 虛構訊號 |

**與防護 A 的分工**：mutation 類虛構 → 防護 A（git working tree）；唯讀 stdout 類虛構 → 防護 E（raw stdout 判據 + 固定值）。兩者互補，前者對「寫」有效，後者對「讀」有效。

### 規則層銜接

- `.claude/rules/core/pm-role.md` session-start 全量清點 + 每次 commit 前 `git status` 已是既有要求，本 PC 強化「mutation 後」而非僅「commit 前」。
- `.claude/rules/core/quality-baseline.md` 規則 1「測試綠燈不等於 Runtime 正確」同精神：工具回報成功不等於操作真實生效。

## 相關

- PC-111（論述編造技術機制）— 同為 confabulation 家族，但層級不同（論述 vs 工具回報）
- PC-147（reference doc 自指涉 confabulation cascade）— 文件層級聯
- IMP-071（append-log 對 placeholder 章節首次填寫不替換）— 防護 B 表格引用
- 0.19.0-W3-091（source ANA，含完整 WRAP 升級評估）
- 防護 E（唯讀 stdout 虛構類）為後續 confabulation 根因 ANA（四視角整合）升級所補
- 1.0.0-W1-039（ghost branch 鑑識 ANA）— 防護 D 延伸（同 prompt 異執行體）+ 症狀第二維度（執行真實性）source case；經四視角審查修正（原 M1/M3 二分降為「有痕跡 vs 不可判」，宿主機制降為多候選未排除）
- 1.0.0-W1-041（宿主機制補證 ANA）— 事發環境排除實驗：外部三候選全排除，宿主收斂為同進程同 turn 雙執行流；新增 version/slug/cwd 進程指紋判據
- `.claude/rules/core/tool-output-trust-rules.md` — 本 pattern 生成自律的規則層固化（規則 1-4 反 confabulation 協議 + 規則 5 記錄/世界二相性）

---

**Last Updated**: 2026-06-10 — 宿主機制由「四候選未排除」收斂為「同進程同 turn 雙執行流」（1.0.0-W1-041 事發環境補證：SDK 版本物證 + SessionStart hook 時間軸 + append-only 持久化推理三重排除外部候選）；新增 version/slug/cwd 進程指紋鑑識判據。前次：補回鏈到 `tool-output-trust-rules.md`（W1-032 文件交叉引用稽核）。
