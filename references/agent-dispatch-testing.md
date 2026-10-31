# Agent Dispatch Template（測試入口政策）

> **用途**：派發 prompt 情境與政策詳解之一：測試入口政策（測試入口、閘門逐檔檢查、全套件合併閘門、終止長時間測試、tests/ 修改派發 SOP）。
>
> **同族檔**：`agent-dispatch-closeout.md`、`agent-dispatch-testing.md`、`agent-dispatch-worktree.md`、`agent-dispatch-pm-edit.md`、`agent-dispatch-variants.md`。原檔 `agent-dispatch-template.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

### 測試入口

**Why/Consequence**：代理人自拼 `uv run --with pytest` 會漏掉套件已在 pyproject 宣告的依賴，缺依賴偽裝成既有失敗或收集錯誤（實例：缺 pyyaml 使讀票面的斷言退回快照而失敗；缺 pytest-mock 使 ticket skill 測試 41 errors）。

**Action**：prompt 的測試命令一律複製下表入口，不自拼 `--with`。`<checkout>` 代入執行測試所在 checkout 的根絕對路徑：在 linked worktree 內是該 worktree 的路徑，不是主倉庫；代入主倉庫路徑會改跑主倉庫的程式碼，worktree 內的修改沒有被測到，結果照樣綠燈。單檔或相關測試檔以 pytest 位置參數附在命令後（例：`uv --directory <checkout>/.claude/hooks run pytest <path>`）。hooks 的 conftest 在缺依賴時提示的就是這條指令，兩者字面一致。

| 套件 | 入口命令 | 依賴來源 |
|------|---------|---------|
| hooks 與 lib（lib/tests 由 hooks 的 testpaths 帶入） | `uv --directory <checkout>/.claude/hooks run pytest` | `.claude/hooks/pyproject.toml` |
| scripts | `uv --directory <checkout>/.claude/scripts run pytest` | `.claude/scripts/pyproject.toml` |
| skills/ticket（含 ticket_system/tests） | `uv --directory <checkout>/.claude/skills/ticket run pytest` | `.claude/skills/ticket/pyproject.toml` |
| skills/doc、worktree、skill-sync、project-init、version-release、mermaid-ascii、branch-worktree-guardian | `uv --directory <checkout>/.claude/skills/<skill> run pytest` | 各 skill 自己的 pyproject |
| skills/framework-issue、broken-link-check、spec、version-bootstrap（無自有 pyproject） | `uv --directory <checkout>/.claude/hooks run pytest <checkout>/.claude/skills/<skill>/tests` | `.claude/hooks/pyproject.toml` |

**邊界**：入口預設安裝 dev group；缺依賴時改 pyproject，不在命令補 `--with`。dispatch 骨架的入口由 `dispatch_skeleton.entry_commands_for_files` 依 `.claude/skills/<skill>/pyproject.toml` 是否存在推導，`test_track_dispatch.py` 的比對測試在本表落後檔案系統時翻紅。

### 閘門逐檔檢查套件由代理人提交前在本機執行

**觸發條件**：checkout 根有合併閘門宣告（`.claude/project-integration/merge-gate.yaml`），且派發票的 where.files 落在宣告中某個套件的範圍內。

**套件分兩類，分工不同**：

| 類別 | 辨識方式 | 誰執行 | 理由 |
|------|---------|-------|------|
| 逐檔檢查 | 宣告帶 `changed_files`（例：格式檢查） | 代理人提交前在本機跑，閘門再驗一次 | 只對本次改動檔執行，結果完全由本票改動決定，本機就能重現 |
| 全套件 | 宣告不帶 `changed_files` | 閘門執行；代理人只跑相關測試檔（見下節） | 命令不帶路徑會跑全套件，與「代理人只跑相關測試檔」的分工衝突 |

**Why/Consequence**：逐檔檢查套件不在本機先跑，紅燈要到合併閘門才出現，分支被退回、多佔一輪閘門名額，排在後面的分支跟著等；而這類紅燈在提交前就能完全發現。

**Action**：

- `ticket track dispatch` 產生的骨架會把逐檔檢查命令併入收尾句的 commit 之前（`提交前跑閘門逐檔檢查（結束碼須為 0）：…`，權威為 `dispatch_skeleton.py` 的 `GATE_CHECK_CLAUSE`）。PM 經 CLI 派發時不需另寫；手寫 prompt 時須照宣告自行補上該句
- 代理人照子句命令執行，結束碼非 0 時先修正再重跑到 0 才提交：格式類套件去掉 `--set-exit-if-changed` 等檢查旗標、以寫入模式重跑同一命令即可修正；其他類別依該套件的錯誤輸出修正
- 全套件類套件的相關測試入口，取宣告中該套件的 `command` 並附上相關測試檔路徑；不帶路徑執行即為全套件，不在本任務範圍

### 全套件由合併閘門執行，代理人只跑相關測試檔（TEST-BAL-006）

**觸發條件**：派發任務的驗收含「跑全套件」「全數通過」類回報，或 prompt 需要寫測試命令。

**Why/Consequence**：全套件在合併前由合併閘門於快照內依改動範圍執行，紅燈不合併（`.claude/skills/worktree/SKILL.md`〈合併前全套件〉）。實作代理人與驗收代理人再各跑一次，同一張票至少重複跑兩次全套件，成本隨票數倍增。縮小母體的風險仍在：命令列一帶入任一路徑，設定檔的收集入口整條失效，只跑所指路徑，縮小後的母體照樣 exit 0、照樣顯示 passed（見 `.claude/error-patterns/test/TEST-BAL-006-explicit-test-path-overrides-multi-entry-testpaths.md`），所以局部執行必須明寫為局部。

**Action**：prompt 的測試段改為下列分工，任務段不寫「跑全套件」的概括說法：

```
全套件由合併閘門在合併前執行，本任務不跑全套件。
只跑本票相關測試檔，命令取自〈測試入口〉並附相關測試檔路徑
（flutter 為 python3 .claude/scripts/run-with-timeout.py 600 -- fvm flutter test <測試檔> --reporter compact）。
回報須明寫「局部執行」，列出所跑命令原文與測試檔清單，不得宣稱全套件通過。
```

驗收方（acceptance-auditor）在合併前只驗相關測試檔與 `dart analyze`，complete 時（合併後）讀 `.claude/logs/worktree-merge.log` 的 `[合併閘門] 結束｜target main｜分支 <分支>｜commit <sha>｜結果 寫入` 行，不自跑全套件；合併前找不到閘門結果時等合併後再驗。

**相關測試檔怎麼找**：以被改動物的字面 grep 所有測試目錄，命中的檔全數列入，命中幾個套件就各以該套件的〈測試入口〉跑一次。

| 改動物 | 搜尋鍵 |
|--------|-------|
| hook 檔 | hook 檔名（含連字號，測試只能以路徑載入，檔名必出現在測試檔中） |
| Python 模組 | 模組名（import 路徑）與主要符號名 |
| 參數或旗標的驗證 | 參數的 Namespace 欄位名與 CLI 旗標名兩種寫法（例：`dedup_checked` 與 `dedup-checked`） |
| 輸出字面、錯誤訊息 | 改動前的字面 |

搜尋範圍是所有測試目錄，不只改動檔所在套件：`.claude/hooks/tests`、`.claude/lib/tests`、`.claude/scripts/tests`、`.claude/skills/*/tests`、`.claude/skills/*/ticket_system/tests`。範例：

```
git grep -n -e dedup_checked -e dedup-checked -- '*test*'
grep -rl worktree-merge-reminder .claude/hooks/tests .claude/skills/*/tests
```

只憑目錄或檔名挑選會漏兩類：同名測試檔分處兩個套件，只改到其中一份；以被改參數作旁路的使用端，檔名不含被改模組名。兩類都在合併閘門跑全套件時才紅，紅燈已經佔用一輪閘門名額（見 `.claude/error-patterns/process-compliance/PC-BAL-061-acceptance-scope-bounded-by-where-files-misses-sibling-mock-drift.md`〈變體〉）。經 dispatcher 或 registry 間接執行的整合測試不含上述字面，這類仍由閘門的全套件兜底，回報不得宣稱已涵蓋。

**例外：任務明確要求代理人跑全套件**（例如閘門被 `--skip-gate` 略過、或範圍在閘門之外的人工驗證）時，改用下列對帳格式；該格式同時供 PM 或驗收方核對任何一次全套件執行的回報（含閘門結果行）是否為完整母體。以下所列對帳規則以 pytest 為例。

**Action（例外情境）**：prompt 必須含以下句子，且任務段中的「跑全套件」一律改寫為下列無路徑指令：

```
全套件指令為 (cd <pkg> && uv run pytest -q -rfE)，命令列不帶任何測試路徑。
回報必須附：(1) 所跑命令原文；(2) 同目錄 pytest --collect-only -q 的全量數；
(3) 執行摘要各結果數（passed / failed / skipped / error 等）與 deselected 數。三者須滿足：執行數 = 全量 - deselected。
(4) 有 failed 或 error 時，附完整的 FAILED / ERROR 行。這些行不得被 tail、grep 或 grep -v 過濾掉；
只想看尾段時，先用 tee 留存全量日誌，再從日誌取尾段。
```

回報須保留失敗項與錯誤項的 nodeid，驗收方才能不重跑就定位。`-rfE` 讓摘要區固定列出 failed 與 error 的 nodeid，不依賴 pytest 的預設值（`-r` 會取代預設的 reportchars，只寫 `-rf` 會漏掉 ERROR 行）。nodeid 遺失的主因是 tail 的行數不夠，或 grep 把它濾掉；所以先用 tee 留下完整日誌，再從日誌取尾段。遺失後驗收方只能重跑全套件，成本由驗收方承擔。

判成敗讀 exit code，不讀輸出外觀；exit code 須在 tail 之前取得，否則整行的結果是 tail 的：

```
set -o pipefail; (cd <pkg> && uv run pytest -q -rfE) 2>&1 | tee <log>; rc=$?; tail -n 40 <log>
```

`pipefail` 使 `| tee` 這一段回傳 pytest 的結果，`rc` 在 tail 之前取值。警告行比正常輸出短且措辭不同，最易被濾掉（`.claude/rules/core/bash-tool-usage-rules.md` 規則二）。

對帳時兩種摘要格式都要處理：

| 摘要末行格式 | 全量數 | 對帳 |
|------|------|------|
| `N tests collected`（僅 1 項時為單數 `1 test collected`） | N | 執行數（passed + failed + skipped 等）須等於 N |
| `N/M tests collected (K deselected)` | M | 執行數須等於 M - K，且 N = M - K |

不等即停手查證，不以 exit 0 或「全數通過」收尾；只跑局部時，回報須明寫「局部執行」並列出未涵蓋範圍，不得宣稱全套件通過。`<pkg>` 由 PM 在派發時代入。工具層另有執行當下的提示（conftest 外掛），與本節互補：外掛負責當場警告，本節負責讓事後回報可對帳。

### 終止長時間測試後驗證子程序已退出約束句

**觸發條件**：派發的代理人會跑長時間測試或背景測試（全套測試、watch 型執行器、以背景 shell 啟動的測試任務），且可能在中途終止後改用其他參數重跑。

**Why/Consequence**：代理人終止的是自己的背景 shell 或工具任務；測試執行器另外啟動的長駐子程序（編譯伺服器、測試隔離程序）不一定隨之結束。「已送出終止」與「程序樹已全部結束」是兩件事，回報若依記憶寫「已終止」，殘留程序會在該 worktree 內持續空轉，吃掉共用機器的 CPU 與磁碟。後果由並行的其他代理人承擔（負載飆高、磁碟寫滿導致他票全套測試失敗），造成者改用重跑完成任務，從自己的視角看不到異常，受害票的失敗又被歸因到該票本身。

**Action**：prompt 必須含以下句子（可併入任務段或獨立一行）：

```
測試需要逾時上限時，一律經 python3 .claude/scripts/run-with-timeout.py <秒數> -- <命令> 啟動，
不用 timeout、alarm 加 exec 或背景 sleep 後 kill 單一 PID；禁用 pkill 與 killall。
終止任何長時間或背景測試後，必須以 pgrep -f <worktree 絕對路徑> 確認無殘留程序，
並在回報中附上該命令的輸出（無輸出即寫「pgrep 無輸出」）。
pgrep 有命中時，逐一以 ps -o command= -p <pid> 確認命中的是測試程序本身
（如 flutter_tester、dartvm、pytest），而非命令列含同字串的其他 shell。
殘留程序確認屬本 worktree 後先送 SIGTERM，再以同一命令確認已退出。
需要等待程序結束時，等已知 PID（kill -0 <pid>），不以 pgrep -f 樣式作迴圈條件。
回報「已終止」而無 pgrep 結果視為未驗證。
```

驗證依據是程序清單（世界平面），不是代理人對自己動作的記憶；`<worktree 絕對路徑>` 由 PM 在派發時代入實際路徑。

**逾時須經包裝腳本（Why/Consequence）**：逾時當下沒有任何「終止動作」可觸發上述自檢，殘留只能在啟動方式上預防。只對單一程序送訊號的逾時寫法（`alarm` 加 `exec`、背景 `sleep` 後 `kill <pid>`），訊號只送達最上層程序；flutter 工具與 `flutter_tester` 同屬一個程序群組，最上層結束後它們被 launchd 收養並繼續執行。`timeout` 在 macOS 預設環境不存在，照抄即失敗，使用者因此各自改寫成上述單一程序寫法。`pkill`／`killall` 依名稱比對全機程序，會終止其他 worktree 與其他專案的測試。**Action**：逾時一律經 `run-with-timeout.py`（以新程序群組啟動，逾時對整個群組先 TERM 後 KILL，結束碼 124）；事後清理改用 `python3 .claude/scripts/orphan-test-procs.py`（只認定本專案範圍內被收養的測試執行器，以及包裝腳本登記過而包裝腳本已不在的程序群組；預設只列出，加 `--kill` 才終止）。

**pgrep -f 的比對陷阱（Why/Consequence）**：macOS 的 pgrep 預設只排除自身與祖先程序，不排除其他 shell；任何命令列含相同字串的 shell 都會被比對到。兩個各自寫成 `until ! pgrep -f "<樣式>"; do sleep 5; done` 的等待迴圈，命令列都含該樣式，會互相比對到對方而永遠不退出，即使實際的測試早已結束，實例中空等超過 15 小時，代理人已回報「等待背景工作」後長時間無下文。**Action**：命中後以 ps 確認程序身分再判定為殘留；等待程序結束一律綁定已知 PID，PID 不明時先取得 PID（啟動時以 `$!` 記錄），不以樣式比對代替。

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
## tests/ 修改派發 SOP（W1-051）

> **已被取代**：本 SOP 在共用主工作樹以 `git checkout -b` 建 feat branch，違反 `.claude/pm-rules/parallel-dispatch.md`〈禁止在共用主工作樹切換或建立分支（強制）〉。涉及 tests/ 的實作派發改用 `isolation: "worktree"`，派發位置查該檔〈派發位置判準（強制）〉；本節保留為歷史記錄，不再作為派發選項。

**用途**：派發涉及 tests/ 修改的 agent 前，PM 必須先建立 feat branch，避免代理人在受保護的 main branch 上被 branch-verify-hook 阻擋。

**Why**：`.claude/hooks/branch-verify-hook.py` 的 `exempt_prefixes = [.claude/, docs/, scripts/experiments/]`，tests/ 不在豁免清單。tests/ 與 src/ 是緊耦合對偶——tests/ 變更通常反映「規格變更」需要對應 src/ 變更才完整，允許 tests/ 在 main 上直接修改會增加紅燈直接進 main 的風險，違反 quality-baseline 規則 1。

**Consequence**：跳過此 SOP 會導致代理人 Edit tests/ 第一次嘗試被 hook deny，浪費代理人回合（PC-042 ~20 tool call 上限）；嚴重時代理人 self-imposed early stop 誤判平台不允許（PC-112 同精神）。

**Action**：依下方觸發條件 + 操作步驟執行。

### 觸發條件

| 情境 | 是否需先建 feat branch |
|------|-------------------|
| ticket where.files 含 tests/ 路徑 | 是 |
| 代理人 prompt 含 Edit/Write tests/* | 是 |
| TDD Phase 2 由 PM 前台寫 RED 測試 | 是 |
| 純讀取 tests/（如分析測試結構） | 否 |
| isolation: worktree 派發（cc runtime 自動建 worktree） | 否（worktree 自動隔離） |

### 操作步驟（派發前）

PM 在 main branch 執行：

```bash
git checkout -b feat/<ticket-id>-<short-desc>
```

範例：`feat/0.19.0-W1-081-worklogs-root-dynamic` <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

命名建議：feat 前綴 + 完整 ticket ID + 簡短描述（kebab-case，3-5 字）。

### 操作步驟（派發後）

1. agent 在 feat branch 上 Edit / 跑測試 / commit
2. PM 接收回報、驗證 acceptance、寫 Phase 4 評估報告
3. PM 切回 main：`git checkout main`
4. Fast-forward merge：`git merge feat/<branch-name> --no-edit`

### 為何不採方案 B（擴大 exempt 加 tests/）

允許 tests/ 在 main 上直接編輯會在以下情境放任紅燈：(1) RED 測試 commit 直接進 main、(2) 測試失敗未及修復即 commit、(3) 多並行 ticket 同時改 tests/ 互相覆蓋。feat branch 隔離強制完整 GREEN 後才 merge，符合品質承諾。

### 為何不採方案 A（強制 worktree）

worktree CLI 目前有 bug（W1-118 偵測：誤報「基礎分支 main 不存在」），在 W1-118 修復前不可依賴。即便 W1-118 修復，git checkout -b 對於小型 ticket（< 1 day）仍是 lower-overhead 的選擇（無需切目錄、無需後續 worktree merge 步驟）。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

<!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->
### 實證（W1-081 session）

PM 試圖直接 Edit tests/unit/scripts/build-version-check.test.js 被 branch-verify-hook 擋下，fallback 到 `git checkout -b feat/0.19.0-W1-081-worklogs-root-dynamic`，完成 Phase 2/3b/4 後 fast-forward merge 回 main，全流程無 friction（5 個 commit fast-forward 整合）。 <!-- rule8-exempt: relocation:自 .claude/references/agent-dispatch-template.md 逐字搬移 -->

---
