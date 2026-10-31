---
name: worktree
description: "Use this skill for managing git worktrees for Ticket-based development. Triggers include: creating a worktree for a new ticket, checking worktree status, viewing all worktrees, or any mention of /worktree, worktree management, feature branches, or setting up development environment."
argument-hint: "<subcommand> [args]"
allowed-tools: Bash, Read, Write, Edit
metadata:
  version: 1.6.7
---

# Worktree Management SKILL

統一 Git Worktree 管理工具 — 簡化並行開發流程。

## 核心功能

管理 git worktree，自動從 Ticket ID 推導分支名和路徑。支援多 Ticket 並行開發時的環境隔離。

---

## Agent isolation worktree（cc 自動建 worktree-agent-*）

> 完整行為說明（機制、base ref 陷阱、dart MCP 洩漏、ticket 狀態 root 分離、殭屍清理、EnterWorktree mid-session 切換）：`references/agent-isolation-worktree.md`（按需讀取）。本節僅速查表，逐項路由。

cc runtime 派發 `isolation: "worktree"` 的 subagent 時自動建立隔離 worktree（`.claude/worktrees/agent-XXXXXXXX`，分支 `worktree-agent-XXXXXXXX`，附 PID lock），與本 SKILL 的人工 `/worktree create` 為不同來源。目的是讓 subagent 檔案改動與主 repo 解耦，避免並行派發互相覆蓋。

| 議題 | 一行結論 | 詳見 references 節 |
|------|---------|-----------------|
| worktree base 落點 | base 取自 `origin/main`（非 local main HEAD），落後時建在 stale 基底；派發前先 push | 〈Base ref 與隔離邊界〉 |
| dart MCP 寫入洩漏 | daemon root 綁主 repo，worktree 內禁用 dart MCP 寫入工具，改 Bash `dart fix`/`dart format` 或 Edit | 〈Base ref 與隔離邊界〉 |
| ticket 狀態該寫哪 | ticket md 讀寫恆落主倉庫（刻意設計，非洩漏）；程式碼提交才走 worktree 分支，`ticket track commit` 需帶 `--worktree` | 〈ticket 狀態統一寫入主倉庫〉 |
| 殭屍累積 | cc 結束不自動 remove，累積佔磁碟；本專案有 SessionStart hook 自動 GC | 〈殭屍問題〉〈手動清理指令〉 |
| 與人工 /worktree create 的區別 | 路徑/分支/生命週期/清理機制皆不同，判別看路徑前綴（`.claude/worktrees/agent-` vs `../ccsession-`） | 〈與人工 /worktree create 的區別〉 |
| EnterWorktree mid-session 切換 | v2.1.157 起可中途切換 worktree；切換後須 `git branch --show-current` + `pwd` 查核再 commit/merge | 〈EnterWorktree mid-session 切換〉 |

**Action**：遇上述議題任一者，先查 references 對應節再處置，不要憑印象操作。

---

## worktree 不含的狀態（0.2.1-W3-274，框架 issue 46）

> **核心概念**：git worktree 是**版本控制層**的隔離機制，只複製 git 追蹤的內容（已 commit 或已 staged 的檔案）。任何 `.gitignore` 排除、或執行期才產生的狀態，都不會隨 worktree 建立而出現在新的工作目錄中。適用於本 SKILL 的人工 `/worktree create` 與 cc runtime 自動建立的 agent isolation worktree 兩者。

### 三類典型非 git 狀態

| 類別 | 說明 | 典型症狀（未補齊時） |
|------|------|---------------------|
| gitignore 排除的產物 | 建置或套件管理工具產生但被 `.gitignore` 排除的檔案或目錄 | 測試/建置找不到對應資源，錯誤訊息通常不直接指向「worktree 缺此目錄」這個根因 |
| 建置快取 | 編譯器/工具鏈的中介快取（非追蹤內容，重建耗時但非必要進 git） | 首次建置變慢，或依賴快取的步驟失敗 |
| 依賴目錄 | 套件管理器安裝的第三方依賴（通常 `.gitignore` 排除，體積大不適合進 git） | 依賴解析/引用失敗 |

**Why**：worktree 共享 git object store，但各自的 working directory 是獨立生成的——`.gitignore` 排除的內容從未進入 git object store，自然不會出現在任何新建立的 worktree 中，與 base 落後 main 幾個 commit 是完全不同的機制（見 `references/agent-isolation-worktree.md`〈Base ref 與隔離邊界〉：該節處理「git 追蹤內容落後多少」，本節處理「git 完全不追蹤的內容從未存在」）。

**Consequence**：未載明補齊方式時，代理人各自在 worktree 內摸索，成功與否取決於個別代理人是否碰巧試出正確命令，同一問題在不同代理人間重複發生而無人留下可複用記錄（框架 issue 46 症狀一實證：四個代理人三個撞牆且回報各異，有解法但不在任何文件或 prompt 中）。

**Action**：具體前置命令屬於 consumer 專案知識（依語言/框架/套件管理器而異），**本 SKILL 不列舉任何專案專屬命令字面**。consumer 專案應：

1. 在專案層文件（`CLAUDE.md` 對應章節或 `scripts/` 下的腳本）記錄本專案 worktree 建立後所需的前置命令
2. 派發需在 worktree 內執行測試/建置的 agent 時，在派發 prompt 引用該文件——見 `.claude/references/agent-dispatch-template.md`「環境前置欄位」

**例外：可自動補齊的 gitignore 排除產物**——當缺漏檔案內容為固定樣板（無機器相依內容，可用固定字串重建，非真正的本機產物）時，`worktree_manager.py` 的 `create` 子命令會直接寫入補齊，不需 agent 手動介入。目前涵蓋：macOS 平台的 `macos/Flutter/Flutter-Debug.xcconfig`、`Flutter-Release.xcconfig`（僅 `#include` 相對路徑，Flutter 官方樣板固定內容）。此類補齊僅在 worktree 內偵測到對應平台目錄（如 `macos/Flutter/`）時才動作，對不含該平台的專案為無操作（no-op），不違反上述「不列舉專案專屬命令」原則——此為程式碼層的 opinionated default，非文件字面列舉。CocoaPods（`Pods/` 目錄）因需網路且耗時，不自動執行 `pod install`，`create` 完成時僅輸出提示指令。

---

## 快速開始

### 建立 Worktree

```bash
/worktree create 1.0.0-W9-002.1
```

自動建立：
- 分支：`feat/1.0.0-W9-002.1`
- Worktree：`../ccsession-1.0.0-W9-002.1`

建立完成後輸出 `cd` 指令，一鍵切換工作環境。

### 查看 Worktree 狀態

```bash
# 查看所有 worktree
/worktree status

# 查看特定 Ticket 的 worktree
/worktree status 1.0.0-W9-002.1
```

顯示：
- 路徑和分支
- 相對於 main 的 commit 領先/落後情況
- 未 commit 的變更數

---

## 子命令詳細說明

> 完整參數表、推導規則、成功範例與錯誤情境：`references/subcommands.md`（按需讀取）。本節保留於〈快速開始〉的最小指令示範已足夠日常使用；需要查特定參數或錯誤訊息時才讀該檔。

- `create`：建立 worktree，見 `references/subcommands.md`〈create — 建立 Worktree〉
- `status`：查看 worktree 狀態，見 `references/subcommands.md`〈status — 查看 Worktree 狀態〉
- `merge`：前置驗證後以隔離索引 CAS 直接完成合併（支援 `--branch <分支名>`、`--pre-acceptance <理由>`、`--message <合併訊息>`、`--ticket <票號>`；落後 base 僅提示）（不再輸出 `git merge` 指令）；含 `pre_merge_check` 合併前檢查掛點（簽名、時機、失敗語意、重試成本），見 `references/subcommands.md`〈merge — 以隔離索引 CAS 合併分支〉
- `cleanup`：三閘門安全清理。無參數為掃描模式；`<ticket-id>` 或 `--branch <分支名>`（擇一，後者用於 `worktree-agent-<id>`）為精確模式；`--force` 略過 Level 2／3 警告，Level 1 未 commit 不可繞過；移除逾時上限 300 秒（`WORKTREE_REMOVE_TIMEOUT_SECONDS`），實際耗時寫入 `worktree-merge.log`；移除失敗時僅在「status 全為 tracked 刪除且 HEAD 為 main 祖先」兩條件皆成立才以 `remove --force` 收尾並 prune，否則非 0 並列出不成立項；worktree 被鎖時停手回報鎖原因與 pid 存活，`--unlock` 明示才解鎖；半刪 worktree（status 全為 tracked 刪除且 HEAD 為 main 祖先）重跑 cleanup 時 Level 1 放行並走收尾，有 untracked 或 modified 仍擋下；語意變更：`git branch -d` 失敗時 rc 由原本的 0 改為 1；實作在 `scripts/cleanup_command.py`，模組位置與測試替換規則見 `references/subcommands.md`〈cleanup — 模組位置〉

### 合併前全套件（merge 預設行為）

`merge` 預設先取得 heavy 名額（改動不在全套件範圍內者不取），再於名額內執行 commit-tree、於合併 commit 的 detached worktree 快照內跑全套件、update-ref，update-ref 完成或中止後才釋放，檢查窗口不含排隊時間；快照內套件經 `run-with-timeout.py` 但以環境標記 `CLAUDE_SLOT_HELD_BY` 免重複取得名額；紅燈即不合併、列出失敗項、exit 1，快照無論成敗皆移除。實作在 `scripts/merge_gate.py`。

| 改動範圍（相對當下 main） | 跑的套件 |
|--------------------------|---------|
| `lib/`、`test/`、`integration_test/`、`macos/`、`docs/`、`assets/`（票檔與版本日誌除外）、`pubspec.*` 等 | Flutter：`fvm flutter test` |
| `.claude/skills/<名稱>/`（該 skill 帶 `tests/`） | `skill:<名稱>`：有 `pyproject.toml` 跑 `uv --directory .claude/skills/<名稱> run pytest`；無則借 hooks 環境 `uv --directory .claude/hooks run pytest -p no:cacheprovider ../skills/<名稱>/tests` |
| `.claude/scripts/` | scripts pytest：`uv --directory .claude/scripts run pytest` |
| `.claude/lib/` | hooks pytest（其 testpaths 已含 `../lib/tests`）＋ scripts pytest ＋ 所有「帶 `tests/` 且有 .py 匯入 `lib`」的 skill（掃描快照得出，不寫死清單） |
| `.claude/hooks/`、無 `tests/` 的 skill、rules、settings.json 等其他 `.claude/` 路徑 | hooks pytest：`uv --directory .claude/hooks run pytest`（hook 測試會讀這些檔） |
| 只改票檔、版本日誌或其他範圍外路徑 | 免跑；範圍外路徑（豁免清單除外）以 `WARNING` 列出，超過 10 個截斷並附總數，部分免跑時同樣列出；只提醒，不改變放行與否 |

**專案宣告（取代內建 Flutter 對應）**：專案可在 `.claude/project-integration/merge-gate.yaml`（根層 `project-integration/`，sync 雙向排除）宣告套件對應；閘門從合併快照（合併 commit）讀取，分支自身新增或修改的宣告對該分支即時生效。

```yaml
suites:
  <套件名>:                     # 不可為 hooks、scripts 或 skill: 開頭（框架保留）
    prefixes: [<路徑前綴>, ...]  # 與 files 至少一項
    files: [<精確檔名>, ...]
    command: [<argv>, ...]      # 相對快照根目錄執行
    artifacts:                  # 選填；缺產物時先以 generate 生成
      - path: <gitignored 產物路徑>
        generate: [<argv>, ...]
    summary: <正規式>           # 選填；摘要行（取輸出尾端最後一個命中行的命中片段）
    failure: <正規式>           # 選填；失敗行（紅燈時列出所有命中行）
    changed_files: <正規式>     # 選填；只檢查改動檔的套件（如格式檢查）
```

- 宣告檔存在：宣告的套件**取代**上表第一列的 Flutter 對應（不疊加）；`.claude/` 下的對應固定保留、不可宣告。宣告的前綴與檔名同時視為「已對應」，不列入未對應路徑警告。套件順序為宣告順序，排在 hooks、scripts、skill 之前。
- `summary`／`failure` 有填時優先使用；未填沿用 pytest／flutter 規則，再退回輸出尾段（失敗項）或「無摘要」。宣告命令的輸出格式由專案決定（如 bun：`summary: '^\s*\d+ (pass|fail)'`、`failure: '\(fail\)'`）。
- `changed_files`（選填正規式）：套件只在「本次改動中有路徑落在 `prefixes`／`files` 內且符合此正規式」時入選；執行時閘門把這些路徑中仍存在於快照者附加到 `command` 尾端。符合檔全數已刪除時該套件免跑，輸出一行 `套件 <名>：免跑｜...`（狀態字樣為「免跑」，與「綠燈」區分）。未宣告者 argv 不變。例：`command: [fvm, dart, format, --output=none, --set-exit-if-changed]` 搭配 `changed_files: '\.dart$'`。
- 宣告檔不存在：沿用內建 Flutter 對應，並印一行 `[合併前測試] INFO：未找到專案宣告 ...`。
- 格式錯誤（YAML 無法解析、缺 `command`、`prefixes` 與 `files` 皆空、使用保留名、`artifacts` 缺 `generate`、`summary`／`failure`／`changed_files` 非字串或無法編譯為正規式）：閘門判紅（fail-closed），訊息指名檔案與欄位，不退回內建對應。

skill 被 hooks 或 scripts 使用時加跑對應套件：改動涉及某 skill，且快照內 `.claude/hooks`、`.claude/scripts` 的 .py（1）行首 `from X`／`import X` 匯入該 skill 的頂層模組（skill 根與其 `scripts/` 下的 .py 模組名、帶 `__init__.py` 的套件名；`sys.path.insert` 之後的匯入同樣涵蓋），或（2）非測試檔含 `skills/<名稱>/` 路徑引用（讀 skill 檔案），就加跑 hooks／scripts 套件。未被使用的 skill 只跑自己的套件。通用模組名（如 `constants`）可能多報，只會多跑套件。

多個套件依 flutter、hooks、scripts、skill（名稱排序）的固定順序執行，任一紅燈即停。

- 快照內缺 `.dart_tool/package_config.json` 時先 `fvm flutter pub get`；失敗則明確指出缺哪個產物。
- CAS 重試：驗證狀態以套件為單位記錄。依「該套件上次驗過的 commit 到新 commit」的差異，套用上表的套件選擇規則：差異不觸及該套件就沿用其驗證結果，觸及就只重跑該套件；沒有驗證紀錄的套件（例如匯入掃描使套件集合變大）加跑。`RETRY_REUSE_EXEMPT_GLOBS`（`docs/work-logs/**/tickets/*.md`、`docs/work-logs/**/v*-main.md`、`docs/work-logs/topic-assignments.txt`）內的檔案仍不計入差異，語意不變。沿用的套件輸出 `[合併前測試] 套件 <名稱>：沿用｜沿用 <commit 前 12 碼> 的驗證結果｜耗時 0.0s`，重跑者為原本的綠燈／紅燈結果行；重試超過 `GATE_MAX_RETRIES`（預設 3）中止，ref 不變、分支保留。
- 每個套件結束輸出一行結果（套件名、狀態、pytest `N passed` 或 flutter `All tests passed` 等摘要、耗時；紅燈、逾時、中斷也記錄），同時寫入 stdout 與 `.claude/logs/worktree-merge.log`。
- 每次閘門開始與結束各記一行，預檢無衝突時中間多記一行 `[合併閘門] 預檢｜target <分支>｜分支 <來源分支>｜commit <base HEAD 前 12 碼>｜結果 無衝突`（有衝突則無此行，直接記結束行「預檢衝突」；前綴 `[合併閘門]`，與套件結果行 `[合併前測試]` 刻意不同，名額預估的中位數取樣只認後者）：`[合併閘門] 開始｜target <分支>｜分支 <來源分支>｜commit <base HEAD 前 12 碼>`、`[合併閘門] 結束｜target <分支>｜分支 <來源分支>｜commit <前 12 碼>｜結果 <寫入|拒絕|紅燈|逾時|中止|預檢衝突>`。結束行的 commit 在結果為「寫入」時是合併 commit，其餘仍是 base HEAD。「拒絕」涵蓋持有者超出自身預估過久而放棄等待，以及持有期間子程序的名額等待逾時（兩者同為結束碼 125，無法再分）；「逾時」為套件逾時；「預檢衝突」為進場排隊前以 `merge-tree` 試算當下 main 與分支即有文字衝突（不排隊、不占名額，結束碼 1；已合併、空合併、ref 解析失敗放行，由取得名額後的既有路徑判定）；「中止」為取得名額後的 CAS 衝突（含排隊期間 main 前進產生的新衝突）、重試上限、非預期例外或中斷。
- 持有者超出自身預估過久（疑似卡住）而放棄等待是預期內結果：只輸出名額閘門的一行說明，不印 traceback，`merge` 以 125 結束，ref 不變；非預期例外仍保留 traceback。佇列總等待不設上限，不再因前方預估過長而提早拒絕；進場與等待提示寫出「順位 N（持有者之後第 N 位，順位不含持有者），前方 M 筆，前方第一筆：<命令或分支>」與預估等待，呼叫端自行決定是否中止。持有者換人是先到者取得名額後後方遞補，不是插隊。
- `--skip-gate <理由>`：略過閘門，理由必填並寫入 `.claude/logs/worktree-merge.log`。
- 閘門不執行的合併前檢查：分支改到 `.claude/skills/line-board/` 時，PM 在執行 `merge` 前依 `.claude/skills/line-board/SKILL.md`〈合併前型別檢查（手動）〉跑 `tsc` 並讀 rc，未通過不合併。閘門不跑是因為平台型別只在互動式 `--plugin-dir` 啟動時產生，快照內沒有；這一步掛在合併收尾，不依賴派發 prompt 提醒。

---

## 使用場景

### 場景 1：新 Ticket 開發

```bash
# 1. 收到 Ticket 1.0.0-W9-002.1
# 2. 建立 worktree（自動推導名稱）
/worktree create 1.0.0-W9-002.1

# 3. 一鍵切換環境
cd /path/to/project-1.0.0-W9-002.1

# 4. 開始開發...
```

### 場景 2：多 Ticket 並行開發

```bash
# 建立多個 worktree（隔離環境）
/worktree create 1.0.0-W9-002.1
/worktree create 1.0.0-W9-002.2
/worktree create 1.0.0-W9-002.3

# 查看整體狀態
/worktree status

# 查看特定 Ticket 進度
/worktree status 1.0.0-W9-002.1
```

### 場景 3：檢查進度

```bash
# 在任何 worktree 中執行，檢查全局狀態
/worktree status

# 確認該 Ticket 有多少未提交變更
/worktree status 1.0.0-W9-002.1
```

---

## 與 Hook 系統的整合

### branch-verify-hook

在保護分支（main）上編輯時：
- **允許**：`.claude/`、`docs/` 路徑的編輯（規則更新、文件維護）
- **阻止**：程式碼路徑編輯（如 `ui/lib/main.dart`）
- **建議**：使用 `/worktree create <ticket-id>` 建立隔離環境

### branch-status-reminder

Session 啟動時：
- **正確環境**（在 worktree + allowed 分支）→ 靜默
- **異常環境**（主倉庫保護分支）→ 警告 + 建議使用 `/worktree create`

---

## 常見問題

### Q: Worktree 與分支的對應關係是什麼？

**A**: 一個 worktree = 一個獨立的分支 + 隔離的檔案系統。

- 建立 worktree 時同時建立分支
- 多個 worktree 間檔案變更隔離
- 每個 worktree 有獨立的 git working directory

### Q: 能否指定 base 分支？

**A**: 支援。使用 `--base` 參數：

```bash
/worktree create 1.0.0-W9-002.1 --base develop
```

### Q: Dry-run 模式有什麼用？

**A**: 檢查將要執行的 git 命令，不實際建立分支和 worktree。適合驗證操作是否正確。

```bash
/worktree create 1.0.0-W9-002.1 --dry-run
```

### Q: 如何刪除 Worktree？

**A**: 使用 `/worktree cleanup <ticket-id>`（worktree-agent-<id> 用 `/worktree cleanup --branch <分支名>`），經三閘門檢查後移除 worktree 與分支。fallback 為手動 git 命令：

```bash
# 刪除 worktree（保留分支）
git worktree remove ../ccsession-1.0.0-W9-002.1

# 刪除分支
git branch -d feat/1.0.0-W9-002.1
```

---

## 參考資料

- Git Worktree 官方文件：https://git-scm.com/docs/git-worktree

---

## 修改 source 後無需重新安裝（shim 化）

> **重要**：本 skill 已改用 cwd-resolving shim（ARCH-APP-002 / framework issue #12），不再走 `uv tool install`。shim 每次執行都 `uv run --directory .claude/skills/worktree` 當前專案源碼，修改 source 後改動即時生效，無 stale installed 問題（取代舊 `uv-tool-staleness-check-hook` 機制）。

**檢查 / 安裝指令**：

```bash
# 安裝 / 更新 shim（一次安裝 ticket / doc / worktree）
python3 .claude/scripts/install-skill-clis.py

# 檢查是否已 shim 化（exit 0/1）
python3 .claude/scripts/install-skill-clis.py --check
```

---

版本紀錄在同目錄的 `CHANGELOG.md`。
