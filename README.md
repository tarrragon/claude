# Claude Code 開發框架

> 放在專案 `.claude/` 目錄使用的 Claude Code 開發框架：每件工作記成一張票，主線程（你在 Claude Code 直接對話的 Claude）擔任 PM 拆分與派發，
> 代理人（主線程以 Agent 工具派出、各自執行一項任務的 subagent）執行，Hook 在工具呼叫前後檢查規則。支援多個 session 同時推進同一個 repo。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

目前版本見 [VERSION](./VERSION)，每一版的變更見 [CHANGELOG.md](./CHANGELOG.md)。

---

## 目錄

- [這套框架做什麼](#這套框架做什麼)
- [安裝](#安裝)
- [第一次使用](#第一次使用)
- [更新到新版本](#更新到新版本)
- [設定檔分工](#設定檔分工)
- [日常使用：主線程與代理人](#日常使用主線程與代理人)
- [Ticket 系統](#ticket-系統)
- [專案版本：規劃期與執行期](#專案版本規劃期與執行期)
- [並行開發：worktree 與合併閘門](#並行開發worktree-與合併閘門)
- [多 session 協作](#多-session-協作)
- [line-board 線狀態面板（/board）](#line-board-線狀態面板board)
- [回報框架問題](#回報框架問題)
- [單獨使用 skill：skill-sync](#單獨使用-skillskill-sync)
- [其他常用指令](#其他常用指令)
- [目錄結構](#目錄結構)
- [核心文件索引](#核心文件索引)
- [框架的版本與發佈](#框架的版本與發佈)
- [移除](#移除)
- [授權](#授權)

---

## 這套框架做什麼

單獨使用 Claude Code 時，工作脈絡只存在對話裡：session 結束、`/clear` 或 context 壓縮之後就讀不到。本框架把脈絡移到檔案，讓下一個 session 或另一個代理人能從檔案接手。

| 機制 | 做法 | 解決的問題 |
|------|------|-----------|
| 票 | 每件工作是一張 Markdown 票，記錄目標、驗收條件、分析與結論 | 接手者讀票面即可繼續，不依賴對話記憶 |
| 主線程即 PM | 你對話的主線程負責拆分、建票、派發、驗收；程式碼由代理人寫 | 主線程的 context 留給決策，不被實作細節塞滿 |
| 版本兩期 | 每個版本先規劃並凍結範圍，再執行；執行期的新發現排進後續版本 | 版本有固定終點，不會邊做邊膨脹 |
| Hook | 在工具呼叫前後檢查規則，違規時擋下或提醒 | 規則由程式執行，不依賴模型記得 |
| 多 session 協作 | 一個主控 session 協調多條工作線；線狀態面板（line-board 在終端機內另開的畫面）依線列出佇列與票的狀態 | 多個 session 同時推進同一個 repo，不互相覆蓋 |

框架有兩種角色：**主控方**維護框架本身（`tarrragon/claude` 發佈的內容），並負責發版；**consumer** 是使用框架的專案。你的專案是 consumer：用框架開發自己的產品，框架本身的問題回報 issue（見〈回報框架問題〉），不修改 `.claude/` 的通用內容。專案自己的設定與本地特化除外：本地特化是專案在 `.claude/` 內新增、並列進 `sync-preserve.yaml` 的檔案，例如自建的代理人；拉取時原地保留，連以上游內容整份覆蓋 `.claude/` 的拉取（還沒有同步基準點時就是這種拉取，見〈首次安裝〉第 6 步）也不動它們。兩者的位置見〈設定檔分工〉。

### 適用前提

- 專案是 git repo，預設分支名為 `main`：`worktree create` 從 `main` 建立分支，`worktree merge` 合併進 `main`。
- 接受 TDD 流程：功能依 Phase 0 到 Phase 4 推進（見〈日常使用〉）。
- 接受分工：主線程不寫產品程式碼，由代理人實作。
- 現成的實作代理人支援 Flutter、Python、Go；其他語言要用範本自建（見〈日常使用〉的 Phase 3b）。
- 合併閘門是 `worktree merge` 合併前的檢查：先在合併結果的快照裡跑測試，紅燈就不合併。專案沒有宣告要跑哪些測試時，只有合併結果的根目錄有 `pubspec.yaml`，改到 `lib/`、`test/`、`docs/` 等 Flutter 預設範圍才會跑 `fvm flutter test`；非 Flutter 專案要宣告自己的測試（見〈並行開發〉）。
- 對話、票、工作日誌與 commit 訊息的描述一律使用繁體中文。

### 導入後會多出什麼

| 位置 | 內容 |
|------|------|
| 專案 repo | `.claude/`、`CLAUDE.md`；`project-init onboard` 會建立 `docs/work-logs/` 與 `docs/todolist.yaml` |
| git 行為 | 票的寫入與 Claude 回應結束時會自動 commit；SessionStart 在 `.git/hooks/` 安裝兩個 git 原生 hook，你自己在終端機的 git 操作也會經過。各項見表下〈git 行為的細節〉 |
| 本機 | `~/.local/bin` 下的 CLI shim，所有使用這套框架的專案共用（見〈首次安裝〉第 1 步）；`~/.cache/claude-slot`（測試名額）與 `~/.cache/claude-proc-registry`（行程登記），同樣由所有專案共用 |
| 對外連線 | `/sync-pull` 從 GitHub clone 框架，收尾時再讀取 `tarrragon/claude-skills` 的版本清單（`versions.json`），比對本地 skill。`gh` 可用且已登入時，SessionStart（startup、resume）會以「owner <專案目錄名>」搜尋 `tarrragon/claude` 的 issue，專案目錄名因此送到 GitHub。例外是本機已有 owned-issues 登記檔：它在你以 `section_comment.py` 的 init 或 update 寫過 framework issue 的區段之後才會建立，一般 consumer 沒有，所以這項搜尋對一般 consumer 會執行。這個檢查沒有關閉開關，沒有 `gh` 時不執行。回報框架 issue 時，內文與查重關鍵字也會送到 GitHub |
| 對話規則 | 自動載入的規則要求繁體中文，並禁止 emoji 與一組禁用詞（[rules/core/language-constraints.md](./rules/core/language-constraints.md)）。這是框架的通用規則，專案不能修改 |
| context | 每個 session 開始時自動載入 `CLAUDE.md` 與 `rules/` 下的規則，這一層有 token 預算，由 SessionStart 量測，預算見 [references/auto-load-stub-conventions.md](./references/auto-load-stub-conventions.md) |

#### git 行為的細節

- **票的自動 commit**：票的寫入（建票、認領、追加日誌等）會在 main 自動產生 `chore(<票號>)` commit。每次 Claude 回應結束時（Stop 事件），Stop hook 也會提交本 session 認領中、還沒提交的票檔；這只在主 checkout、且沒有背景代理人執行時發生。
- **worktree 內的自動提交**：session 在 worktree 內、且沒有背景代理人執行時，Stop 事件會以 `git add -A` 加 `--no-verify` 自動提交該 worktree 內的全部變更（含未追蹤檔），不經 `pre-commit` 檢查。
- **`pre-commit`**：`git commit` 時只檢查 `.claude/settings.json` 能否解析。原有的 `pre-commit` 會改名為 `pre-commit.local`，由新的 `pre-commit` 串接呼叫。
- **`reference-transaction`**：每次寫入分支（commit、合併、票的自動提交）前，以框架的檢查掃描新 commit 的內容，命中阻擋條件時中止這次寫入，`git commit --no-verify` 也跳不過它。主要的阻擋條件有兩項：在保護分支上直接提交豁免路徑以外的檔案（你在終端機的 commit 也會被擋；保護分支見〈Hook 擋下時〉），以及在 `.claude/` 下新增專案識別符（如票號）。
- **`core.hooksPath`**：設了它時 git 不讀 `.git/hooks/`，兩個 git 原生 hook 都不生效；安裝時只對 `pre-commit` 印出警告。

兩個 git 原生 hook 的細節見 [references/hook-architect-technical-reference.md](./references/hook-architect-technical-reference.md)〈git 原生 hook 的安裝與移除〉。

### 能關閉與不能關閉的部分

| 部分 | 做法 |
|------|------|
| line-board 線狀態面板 | 可關閉，見〈line-board 線狀態面板〉 |
| 只同步部分 skill | 以 `.claude/sync-skills.yaml` 的 `mode: select` 選擇要同步的 skill，見 [references/sync-exclusion-guide.md](./references/sync-exclusion-guide.md)〈sync-skills.yaml — 選擇性 Skill 同步〉；完全不同步框架、只取個別 skill 時見〈單獨使用 skill〉 |
| 個別 Hook | 註冊在 `settings.json`，屬框架（見〈設定檔分工〉）；框架沒有提供在專案層逐一關閉的設定 |

---

## 安裝

### 需要的工具

| 工具 | 用途 |
|------|------|
| Claude Code | 執行環境 |
| git 2.28 以上 | 版本控制、worktree；`reference-transaction` hook 從 2.28 開始提供 |
| Python 3.11 以上 | 工具腳本（`sync-claude-pull.py` 宣告 `>=3.11`）。`project-init check` 只回報偵測到的版本，不判斷是否足夠 |
| uv | 執行 Hook、skill 的 CLI 與測試。沒有 uv 時 Hook 與 `project-init` 都無法執行 |
| pyyaml（裝在 `python3` 指向的 Python） | 同步腳本 `sync-claude-pull.py` 拉取後，依 `config/hook-registry.yaml` 把 `settings.json` 缺少的 hook 補登記。缺少 pyyaml 時，腳本在 stderr 印出「auto_register_hooks 降級：缺少 pyyaml」並跳過這一步，結束碼不變；登記表有、`settings.json` 沒有的 hook 不會補上 |
| gh（GitHub CLI，已登入） | 回報框架 issue |
| zhtw-mcp（選用） | 繁體中文用語檢查。不使用時建立 `.claude/.zhtw-mcp-skip`，略過啟動時的可用性檢查 |

各作業系統的安裝方式見 [platform-install-guide.md](./skills/project-init/references/platform-install-guide.md)。

### 首次安裝

專案已經有 `.claude/` 或 `CLAUDE.md` 時，先把它們移到別處備份。Claude Code 在你核准權限時會自動建立 `.claude/settings.local.json`，所以用過 Claude Code 的專案幾乎都有。

```bash
cd <你的專案>
git clone https://github.com/tarrragon/claude.git .claude
rm -rf .claude/.git
rm -rf .claude/.github
```

刪除 `.claude/.git` 是因為 `.claude/` 要納入你專案自己的 git，之後的更新改用 `/sync-pull`，不用 `git pull`。刪除 `.claude/.github` 是因為 clone 把上游根層的 `.github`（issue 範本，不屬於 `.claude/` 的內容）一併帶進來；第一次 `/sync-pull` 會把它當舊版殘留清除，留下未提交的刪除，下一次更新會被拒絕。

接著在專案根目錄啟動 Claude Code，依序完成：

1. **接受 workspace trust**：Claude Code 第一次在這個目錄啟動時，會詢問是否信任此資料夾，選信任；已信任過的目錄不會再詢問。之後 SessionStart hook 會把框架的 CLI（如 `ticket`、`worktree`、`doc`、`skill-sync`、`project-init`）安裝成 `~/.local/bin` 下的 shim（轉呼叫框架腳本的小型啟動檔，讓你在終端機直接輸入指令名稱）。以 `command -v ticket` 確認 shim 在 PATH 中（應顯示 `~/.local/bin` 下的路徑），找不到時把 `export PATH="$HOME/.local/bin:$PATH"` 加進 shell 設定檔（如 `~/.zshrc`）。shim 也可手動安裝：`python3 .claude/scripts/install-skill-clis.py`。
2. **檢查環境**：`project-init check` 檢查 Python、uv、ripgrep 等項目，git 與 gh 要自己確認。
3. **建立 `CLAUDE.md`**：複製 `.claude/templates/CLAUDE-template.md` 到專案根目錄，填入專案身份、技術選型與 Phase 3b 的實作代理人。有備份時，把舊 `CLAUDE.md` 的內容併進來。
4. **建立 `settings.local.json`**：複製 `.claude/templates/settings-local-template.json` 為 `.claude/settings.local.json`，依檔內說明刪除註解：`_README`、`_INSTRUCTIONS` 兩個鍵，以及 `permissions.allow` 清單內以 `_COMMENT` 開頭的字串；再移除不適用的語言權限。有備份時，把舊 `settings.local.json` 的權限與 MCP 設定併進來。接著執行 `project-init onboard`：它檢查設定是否完整，檢查的項目由前面幾步建立，所以排在這裡；並列出 Flutter 專屬與專案專屬的 Hook 清單（分類見 `.claude/config/hook-language-classification.yaml`）。
5. **提交**：先把框架要求的條目加進專案根目錄的 `.gitignore`，讓 `settings.local.json`、`hook-logs/` 等本機狀態與本機設定不進版控。下面的命令印出 `.claude/` 內的條目，把每一行加進 `.gitignore`；另外加上 `coverage/` 與 `docs/work-logs/**/*.md.lock`（票檔的鎖）。SessionStart 的 `.gitignore` 檢查以同一份清單比對。

   ```bash
   python3 -c 'import sys; sys.path.insert(0, ".claude/lib"); import sync_exclude_manifest as m; print("\n".join(sorted(m.required_gitignore_entry(n) for n in m.GITIGNORE_EXPECTED)))'
   ```

   接著 `git add .gitignore .claude CLAUDE.md` 後 commit，訊息建議用 `chore(sync): install .claude <版號>`（版號取 `.claude/VERSION`）。換機器時判斷某個檔是不是框架裝進來的，會以這筆提交辨認（見〈在另一台機器接手〉第 4 步）。
6. **建立同步基準點**：到自己的終端機執行 `python3 .claude/scripts/sync-claude-pull.py`，記錄同步基準點（`.claude/.sync-state.json`）。這次拉取沒有基準點，拉取中可能出現確認詢問；在 Claude Code 內執行時（包括 `/sync-pull`）腳本讀不到你的輸入，無法回答，所以在終端機執行；出現 `Apply full overlay? [y/N]` 時，照〈更新到新版本〉核對 dry-run 清單再回答。執行後以 `grep -q last_synced_base_sha .claude/.sync-state.json 2>/dev/null && echo Y || echo N` 確認。有了基準點，之後的更新才會做三方合併，保留你本地的修改；沒有基準點時，更新會以上游內容整份覆蓋 `.claude/`（本機設定與 `sync-preserve.yaml` 列出的檔案除外），本地修改會被蓋掉。剛安裝、尚未做任何本地修改時，最適合建立基準點。
7. **放回自訂的 command 與 agent**：有備份時，做三個動作：
   - 把自訂的 command、agent 放回 `.claude/commands/`、`.claude/agents/`，與框架同名時改名。
   - 把每個檔案相對於 `.claude/` 的路徑列進 `.claude/sync-preserve.yaml`：

     ```yaml
     preserve:
       - agents/<你的代理人>.md
     ```

   - 提交這些檔案；`sync-preserve.yaml` 本身在 `.gitignore` 裡，不進 git。

   `sync-preserve.yaml` 在沒有基準點的拉取、上游日後新增同名檔、換機器時生效，換機器時可複製這份清單過去。這一步放在第 6 步之後，是因為第 6 步那次拉取沒有基準點，會刪除或轉存不在上游的檔案；自訂檔晚一步放回，就不會經過那次清除。

   自訂檔含專案票號時，在 `.claude/` 內寫入會被 `reference-stability-rule8-guard-hook.py` 擋下（框架檔案禁止引用專案票號）。移除票號，或改放 `.claude/project-integration/`（該目錄不同步，不在掃描範圍）。

### 在另一台機器接手

專案已經在別台機器安裝過框架，這台機器 clone 專案之後，依序做：

1. **clone**：`git clone <專案 repo>`。`.claude/` 已在專案的 git 裡，不需要再 clone 框架。
2. **啟動並信任**：在專案根目錄啟動 Claude Code，接受 workspace trust；SessionStart 會自動安裝 CLI shim（做法與驗證見〈首次安裝〉第 1 步）。
3. **建立 `settings.local.json`**：複製 `.claude/templates/settings-local-template.json` 為 `.claude/settings.local.json`（做法見〈首次安裝〉第 4 步）。專案專屬權限與 MCP 設定從原機器的檔案自行帶過來。
4. **複製同步狀態**：從原機器複製 `.claude/.sync-state.json` 與 `.claude/sync-preserve.yaml` 到這台機器的 `.claude/`，兩個檔案都不進 git。兩檔記錄的是上游 commit 與檔案清單，內容不隨機器改變；複製後第一次更新就走三方合併，`.sync-state.json` 內的固定版本（`pinned_version`）也一併帶過來。不複製這個檔，這台機器就沒有固定版本。

   原機器取不到這兩個檔時，在這台機器重建：
   - 執行 `python3 .claude/scripts/sync-claude-pull.py --audit` 列出「本地有上游無」的檔案。它是唯讀稽核，不改 `.claude/` 的檔案內容，只會產生 Python 的 `__pycache__`。列出的檔逐一判斷是不是自己建的，自建的就把相對於 `.claude/` 的路徑列進 `.claude/sync-preserve.yaml`：
     - 已追蹤的檔：以 `git log --format='%h %s' -- .claude/<路徑>` 看最早那筆提交（輸出的最後一行）。它是安裝框架的提交或 `chore(sync)` 開頭的拉取提交，就是框架裝進來的；是其他提交，就是自建。安裝提交沒有用 `chore(sync)` 開頭時，以 `git log --diff-filter=A --format='%h %s' -- .claude/VERSION` 查出是哪一筆。自建檔與安裝在同一筆提交時，這個方法分不出來，改看檔名與內容判斷。
     - 未追蹤的檔（`git log` 沒有輸出）：是這台機器上自己放進去的，視為自建；不想保留就先刪除。

     不要照 `--audit` 輸出的「可忽略此提醒」做：沒有基準點時，下次拉取會刪除或轉存這些檔案。
   - 基準點留到第一次更新時建立：照〈更新到新版本〉沒有基準點的做法，並以 `--bump v$(cat .claude/VERSION)` 先固定在專案目前的版本。沒有固定版本就直接拉，目標是上游最新版，等於同時升級框架。固定版本會記在 `.sync-state.json`，之後的拉取都停在這一版；要升級時執行不帶版號的 `python3 .claude/scripts/sync-claude-pull.py --bump` 解除固定。
5. **補回其他只在本機的狀態**：`.claude/sync-skills.yaml`（選擇性同步的設定）從原機器複製；不使用 zhtw-mcp 時重建 `.claude/.zhtw-mcp-skip`。`.claude/handoff/` 不跨機器，在原機器交接的票改用 `ticket track full <票號>` 讀票面接手，不用 `ticket resume`。

---

## 第一次使用

1. **登記第一個版本**：在 `docs/todolist.yaml` 寫一個版本條目（格式見〈專案版本：規劃期與執行期〉）。版號自訂，例如 `0.1.0`；`status` 填 `active`，`worklog` 指向版本目錄。`ticket create` 會檢查版本是否已登記。
2. **建立工作日誌主檔**：在版本目錄建立 `v<版號>-main.md`。版本是 active 或 planned 卻缺主檔時，SessionStart 的版本追蹤檢查會提醒。
3. **宣告合併閘門**（非 Flutter 專案）：在派發之前宣告 `.claude/project-integration/merge-gate.yaml`，格式見〈並行開發〉。沒有宣告時，快照根目錄有 `pubspec.yaml` 才會在改到 `test/`、`docs/` 等 Flutter 預設路徑時跑 `fvm flutter test`，其他路徑不跑測試。
4. **提出第一個需求**：用一般的話告訴主線程要做什麼，主線程會拆成票、建票。你也可以自己用 `ticket create` 建票（見〈Ticket 系統〉）。
5. **凍結範圍**：範圍定案、票建完之後，執行凍結程序（見〈專案版本：規劃期與執行期〉），版本才進入執行期。要多 session 協作，就在凍結前建好協調票（見〈開始協作〉）。
6. **在 worktree 裡改程式碼**：主線程以隔離 worktree 派發代理人，或你以 `worktree create <票號>` 建立。
7. **驗收、合併、完成**：主線程依票面驗收，再依分支來源合併，合併前依合併閘門宣告跑測試。隔離派發的票在合併並驗證之後才標為完成。命令見〈並行開發〉。
   - `worktree create` 建的分支：票已是 completed 時，執行 `worktree merge <票號>`。票完成前就要合併時，才加 `--pre-acceptance "<理由>"`，理由寫為什麼要先合併，例如哪幾條驗收要等合併後才驗。
   - 隔離派發的分支：`worktree merge --branch <分支名>`，complete 在合併並驗證之後執行。

---

## 更新到新版本

拉取前，到 `tarrragon/claude` 的 CHANGELOG.md 逐版讀目前版本（`.claude/VERSION`）之後各版的「對 consumer 的影響」。本機的 `.claude/CHANGELOG.md` 要拉取之後才有新版本的內容。

**拉取前確認基準點**：

```bash
grep -q last_synced_base_sha .claude/.sync-state.json 2>/dev/null && echo Y || echo N   # Y 是有基準點，N 是沒有
```

沒有基準點的情況（舊版安裝、另一台機器、新 clone）下，拉取會以上游內容整份覆蓋 `.claude/`：不在上游、也沒列進 `sync-preserve.yaml` 的本地檔案，未追蹤的被刪除，已追蹤的被移到 `.sync-conflicts/`。這種情況先備好 `sync-preserve.yaml`（做法見〈在另一台機器接手〉），再到自己的終端機直接執行腳本。腳本先印 dry-run 清單，再詢問 `Apply full overlay? [y/N]`。清單裡的 `- delete:`（未追蹤，會直接刪除）或 `-> conflict:`（已追蹤，會轉存到 `.sync-conflicts/`）出現自己建的檔時，回答 N，把該檔列進 `sync-preserve.yaml` 後重跑。回答 N 之後發生什麼，取決於你本地腳本的版本（拉取時執行的是目前 `.claude/` 裡的腳本，版本看 `.claude/VERSION`）：3.2.0 起中止且不改任何檔案；3.1.0 以前收尾照跑，可能刪除 `.claude/.github/` 而留下未提交的刪除，這時重跑會被拒，先執行 `git restore -- .claude/.github` 再重跑。沒有固定版本（`pinned_version`）而不想連帶升級時，用下面的 `--bump v<版號>` 先固定在目前的版本，版號取 `.claude/VERSION`；之後要升級再以不帶版號的 `--bump` 解除固定。

```bash
/sync-pull                                                   # 在 Claude Code 內執行；沒有基準點時不要用，見下
python3 .claude/scripts/sync-claude-pull.py                  # 在自己的終端機直接執行；沒有基準點時用這一行
python3 .claude/scripts/sync-claude-pull.py --bump v<版號>   # 固定在某一版
python3 .claude/scripts/sync-claude-pull.py --bump           # 解除固定，回到最新版
```

- `/sync-pull` 在 Claude Code 內執行腳本，腳本讀不到你的輸入，無法回答確認詢問，等同回答 N。沒有基準點而有本地差異時，腳本中止拉取、不寫入基準點；其餘行為依本地腳本的版本（`.claude/VERSION`）而定：
  - 3.2.0 起：以結束碼 1 結束，印出中止原因與處置，不印「成功拉取」，不跑收尾。
  - 3.1.0 以前：仍印「成功拉取」、結束碼 0。收尾照跑，可能已刪除 `.claude/.github/`（見〈首次安裝〉），留下未提交的刪除。先 `git restore -- .claude/.github`（或提交），再到終端機重跑；工作區有未提交的刪除時，下一次更新會被拒絕。

`tarrragon/claude` 只接受發版推送，每次推送對應一個 `v<版號>` tag。因此沒有固定版本時，拉到的就是最新發版的版本。固定了版本時（`.sync-state.json` 的 `pinned_version` 是某個版號，例如以〈在另一台機器接手〉第 4 步的做法建立基準點之後），拉取停在該版，輸出會印「版本 pin：<版號> → 對齊上游 <sha>（非最新 HEAD）」；要升級時以不帶版號的 `--bump` 解除固定。

**拉取被拒，而未提交的變更只有 `.pyc`**：`.claude/` 下的 `__pycache__/*.pyc` 曾被提交進版控時（例如照較早的〈首次安裝〉第 5 步以 `git add .claude` 提交），同步腳本與 Hook 執行時會重寫這些檔，已提交的 `.pyc` 就成了未提交的修改，腳本以「警告: .claude 有未提交的變更」拒絕拉取。`git status --porcelain -- .claude/` 只列出 `__pycache__` 下的檔時，清除一次即可：

```bash
git rm -r --cached --quiet -- '.claude/*__pycache__*'   # 停止追蹤，不刪磁碟上的檔
echo '.claude/**/__pycache__' >> .gitignore             # 之後不再被加入
git add .gitignore
git commit -m "chore: 停止追蹤 .claude 下的 __pycache__"
```

commit 之後再拉取。

拉取之後：

1. **檢視變更**：先看拉取輸出的標題行。「更新 .claude 資料夾（三方合併）」加上「已記錄 base SHA」或「暫不推進」是有基準點的更新，本地獨有的檔不會被刪，只以 `git diff --stat -- .claude/` 確認變更來自上游。標題行是「更新 .claude 資料夾（全量 overlay）」時（沒有基準點，或基準點在上游已不可達），核對三份清單，其中自己建的檔放回原位並列進 `sync-preserve.yaml`：
   - 其一，`git status --porcelain -- .claude/` 中標 `D` 的檔案：以 `git restore -- .claude/<路徑>` 放回。
   - 其二，輸出中「本地獨有 git 追蹤檔已轉存 .sync-conflicts/」底下列出的檔案：它們也會出現在其一，可同樣以 `git restore` 放回。轉存的副本在 `.claude/.sync-conflicts/`，檔名是把路徑的 `/` 換成 `__`（`agents/my-agent.md` 存為 `agents__my-agent.md`）。
   - 其三，輸出中「刪除 N 個非 git 追蹤的過時檔案」底下列出的檔案：已從磁碟刪除，變空的目錄也一併刪除。從輸出中「備份位置」那一行所列的目錄取回，先建回所在目錄：`mkdir -p .claude/<所在目錄>`，再 `cp <備份位置>/.claude/<路徑> .claude/<路徑>`。

   最後執行 `grep -q last_synced_base_sha .claude/.sync-state.json 2>/dev/null && echo Y || echo N`，確認基準點已建立。
2. **處理衝突**：衝突區塊以標記寫回原檔，對照副本在 `.claude/.sync-conflicts/`。逐檔決定採本地、採上游或手動合併後，執行 `python3 .claude/scripts/sync-claude-pull.py --resolve-done` 推進基準點。
3. **提交**：把這次拉取的變更提交成單一 commit（訊息格式 `chore(sync): pull .claude 更新（上游 <short-sha>）`），不與其他工作混在一起。提交後，刪除 `.claude/.sync-conflicts/`，殘留會在下次拉取時與新衝突混在一起；全量 overlay 的更新要先處理完第 1 步列出的轉存檔再刪。
4. **處理幽靈註冊**：拉取收尾若出現「settings.local.json 含 hook 註冊」的警告，先不帶參數執行 `.claude/hooks/hook-registration-coverage-check.py` 看命中哪幾筆，再加 `--fix` 執行，從 `settings.local.json` 移除指向已不存在檔案的註冊。
5. **對齊專案**：執行 `/framework-update-adaptation`。這一步逐項分類本次的變更（專案對框架檔案的修改被上游覆寫、上游廢除或改名、產物要重驗等），依類別建票，由後續的票處理。
6. **重啟 session**：已啟動的 session 不會重新讀取 hook 註冊，拉取後要重啟才會用新版 Hook。

各步驟的細節見 [commands/sync-pull.md](./commands/sync-pull.md)〈pull 後檢查清單（強制）〉，同步原理見 [references/sync-mechanism-guide.md](./references/sync-mechanism-guide.md)。

---

## 設定檔分工

| 檔案 | 內容 | 維護者 | 拉取時 | 進 git |
|------|------|-------|-------|-------|
| `.claude/settings.json` | Hook 註冊、框架權限、狀態列 | 框架 | 隨 `/sync-pull` 更新，不在專案修改 | 是 |
| `.claude/settings.local.json` | 回應格式（`outputStyle`）、MCP server、環境變數、專案專屬權限 | 專案 | 不同步 | 否，每台機器各自從範本建立 |
| `CLAUDE.md`（專案根目錄） | 專案身份、技術選型、實作代理人 | 專案 | 不同步 | 是 |
| `.claude/project-integration/` | 專案對框架的宣告，例如合併閘門要跑哪些測試 | 專案 | 不同步 | 是 |
| `.claude/sync-preserve.yaml` | 本地特化的清單：拉取時要原地保留的檔案 | 專案 | 本身不同步；列入的檔案不被覆蓋或刪除 | 否 |

`.claude/.sync-state.json`（同步基準點）、`.claude/sync-skills.yaml` 與 `hook-logs/` 等本機狀態與本機設定也不進 git。`.gitignore` 要加的條目以〈首次安裝〉第 5 步的命令輸出為準，分類見 [references/sync-exclusion-guide.md](./references/sync-exclusion-guide.md)〈五類分類定義〉。

這些不進 git 的檔案不會跟著 clone 到另一台機器；換機器或新 clone 後怎麼補回，見〈在另一台機器接手〉。

---

## 日常使用：主線程與代理人

### 主線程扮演 PM

你在 Claude Code 對話的主線程依這個循環工作：

1. 聽需求，拆成票。
2. 把脈絡寫進票，派發代理人執行。
3. 讀代理人的回報，依票面的驗收條件驗收，然後提交驗收通過的變更。

主線程不寫產品程式碼，也不直接改測試檔，這兩項由 Hook 擋下。產品程式碼由代理人寫，代理人定義在 [agents/](./agents/)。TDD 流程的分工如下：

| 階段 | 代理人 | 做什麼 |
|------|-------|-------|
| Phase 0 | saffron-system-analyst | 系統一致性前置審查 |
| Phase 1 | lavender-interface-designer | 功能規格與介面 |
| Phase 2 | sage-test-architect | 測試案例設計 |
| Phase 3a | pepper-test-implementer | 語言無關的實作策略 |
| Phase 3b | 語言實作代理人，在 `CLAUDE.md` 指定。現成的有 parsley-flutter-developer、thyme-python-developer、fennel-go-developer；其他語言以 `agents/language-agent-template.md` 自建，放在 `.claude/agents/`，並列進 `sync-preserve.yaml`（沒有基準點的拉取與換機器時，靠它原地保留） | 實作到測試全綠 |
| Phase 4 | `/parallel-evaluation` 與 cinnamon-refactor-owl | 多視角評估與重構 |

流程主文見 [pm-rules/tdd-flow.md](./pm-rules/tdd-flow.md)，`/tdd` 會引導每個階段。代理人清單見 [agents/README.md](./agents/README.md)；各代理人能產出什麼、禁止做什麼，見各自的定義檔 `agents/<名稱>.md`〈允許產出〉〈禁止行為〉。

### 回應格式

`settings.local.json` 範本預設把 `outputStyle` 設為 `5W1H Structured Response`：每則回應以 Who／What／When／Where／Why／How 六欄開頭，格式定義在 [output-styles/5w1h-format.md](./output-styles/5w1h-format.md)。回應的讀者常是下一個 session 或代理人，固定六欄讓讀者一眼看出這則回應的執行者、目的與做法。不要這個格式時，刪除 `settings.local.json` 的 `outputStyle`。

### Hook 擋下時

框架註冊在 `settings.json` 的 Hook 只在 Claude 的工具呼叫與 session 事件（如啟動、回應結束）時執行，你自己在編輯器與終端機的操作不受影響；例外是框架安裝的 git 原生 hook（見〈導入後會多出什麼〉）。Hook 擋下操作時，訊息會寫明原因與替代做法。常見的幾種：

| 被擋的操作 | 改用 |
|-----------|------|
| 裸 `cd` 切換目錄 | git 操作用 `git -C <路徑> <命令>`；其他命令用子 shell `(cd <路徑> && <命令>)` |
| 主線程直接讀票檔 | `ticket track full <票號>` |
| `git add -A`、`git add .` 等廣域暫存 | 精確 `git add <檔案>`，以 `git diff --cached --name-only` 核對後再 commit |
| 主線程寫產品程式碼 | 建票派發代理人 |
| 在保護分支（`main`、`master`、`develop`、`release/*`、`production`）上修改或提交豁免路徑以外的檔案（Edit、Write 與 Bash 的 `git commit` 都會被擋）。豁免路徑是 `.claude/`、`docs/`、`scripts/experiments/` 開頭的路徑，以及專案根目錄的 `CLAUDE.md`、`README.md`、`CHANGELOG.md`、`package.json`、`manifest.json`、`.gitignore`、`.gitattributes` | 在 worktree 裡改 |
| 寫入 Claude Code 原生 memory | 依情境寫進 `error-patterns/`、規則或專案的 `docs/`，訊息會指出該寫到哪裡 |

照訊息給的替代做法改，不要換個寫法繞過。Hook 判斷錯誤時，回報框架 issue（見〈回報框架問題〉）。

---

## Ticket 系統

### 票的位置與類型

每件工作是一張 Markdown 票，路徑為 `docs/work-logs/v<major>/v<major.minor>/v<版號>/tickets/<版號>-W<波次>-<序號>.md`。波次（wave）是版本內相互隔離的執行批次，不同波次的票不互相依賴；版本只有一批時，建票一律用 `--wave 1`。frontmatter 記錄狀態、執行者、驗收條件等欄位，票的內文依序記錄任務摘要、問題分析、解法與測試結果。

| 類型 | 用途 |
|------|------|
| IMP | 實作 |
| ADJ | 調整、修復問題 |
| ANA | 分析。結論要求的後續工作要在 complete 前建好落地票，血緣依落地版本分流：屬本版範圍的以 `ticket create --parent <ANA 票號>` 建成子票，子票全部終態才能 complete；依兩期排進後續版本的，在目標版本以 `--version <目標版本> --source-ticket <ANA 票號>` 建根票（目標版本要先登記），建好即可 complete（[pm-rules/ticket-lifecycle.md](./pm-rules/ticket-lifecycle.md)〈ANA Ticket 落地下游血緣選擇〉）。complete 時 Hook 比對 Solution 規劃的後續工作數與已落地數（子票、`spawned_tickets`、已判定的 spawn request），一張都沒落地就擋下，少於規劃數時只警告 |
| DOC | 文件 |

### 基本操作

```bash
ticket create --version <版號> --wave 1 --type IMP \
  --action "實作" --target "<對象>" --why "<需求依據>" \
  --who "<執行者>" --when "<觸發時機>" --how-strategy "<實作策略>" \
  --where-files "<會改到的檔案>" \
  --acceptance "<可驗證的條件>" --acceptance "<另一條條件>" \
  --decision-tree-entry "<決策樹層級>" --decision-tree-decision "<決策>" \
  --decision-tree-rationale "<理由>"

ticket track dashboard --top 5                        # 進行中、待接手、可認領的票
ticket track claim <票號>                              # 認領
ticket track full <票號>                               # 讀完整票面
ticket track append-log <票號> --section Solution --content-file <內容檔>   # 內容逐字從檔案讀入
ticket track check-acceptance <票號> --all --as <執行者>   # --all 勾選全部驗收條件
ticket track complete <票號> --as <執行者>                 # --as 申報執行身份，須與票面的目前執行者相符
```

- 建立根票時，範例裡的 `--why`、`--who`、`--when`、`--how-strategy`、`--where-files`、`--acceptance` 與 decision-tree 三個參數缺任一項，會以結束碼 1 拒絕建票（DOC 票不需要 `--why`）。
- `--decision-tree-entry`、`--decision-tree-decision`、`--decision-tree-rationale` 記錄這張票從主線程決策樹（[pm-rules/decision-tree.md](./pm-rules/decision-tree.md)）的哪一層進入、做了什麼決策、理由是什麼，例如 `--decision-tree-entry "第五層:TDD"`。DOC 票與以 `--parent` 建立的子票可以省略這三個參數。
- `--who` 設定票的目前執行者。之後 `check-acceptance`、`complete` 的 `--as` 要填同一個值，不符會被拒絕。
- 在 Claude Code 內輸入不帶參數的 `/ticket`，會列出進行中與可認領的票讓你選。
- 換 session 時，票還在進行中就以 `ticket handoff <票號> --context-refresh` 交接，票已完成則以 `ticket handoff <票號>` 交接（依任務鏈自動判斷方向）；接手方以 `ticket resume <票號>` 載入。
- 命令參數含反引號時，不放進雙引號（shell 會把反引號內的文字當成命令執行）；改用檔案傳入，如 `append-log` 的 `--content-file`，或單引號包住整個參數。
- 你或 Claude 以腳本呼叫寫入類命令（create、append-log、complete 等）時，以結束碼判斷成敗，不以輸出外觀判斷。
- 驗收只審三項固定檢查：能不能跑（本票相關測試全綠、建置沒有新增錯誤）、有沒有動到票面宣告範圍外的檔案、輸出格式是否符合票面。其他觀察記成後續版本的票，不退件（[pm-rules/verification-framework.md](./pm-rules/verification-framework.md)〈驗收三項固定檢查〉）。

### 多個 clone 同時建票

`ticket create` 取同一波次目前最大的序號再加 1。最大號從四個地方收集：本地工作樹、本地 main、同一 repo 的其他 worktree，以及已 fetch 的 remote-tracking 主分支（`origin/main` 或 `origin/master`）。另一台機器或另一個 clone 建的票，在你 fetch 之前不會出現在這四處，所以兩邊仍可能配到同一個票號。

- **降低機率**：建票前先 `git fetch`。fetch 後，對方已推上 origin 的票號會被計入，不會再配到同號。
- **撞號怎麼出現**：兩邊各自 commit 了同名的票檔，合併或 pull 時，該票檔出現 add/add 衝突（`both added`）。衝突只發生在票檔路徑上，內容是兩張不同的票。
- **處置**：
  1. 以 `git merge --abort` 中止這次合併，兩邊的票都保留原樣。
  2. 在自己這邊把較晚建立、或尚未被別處引用的那張改號：先以 `ticket migrate <舊票號> <新票號> --dry-run` 預覽，再去掉 `--dry-run` 執行。新票號取 fetch 後最大號的下一號。
  3. 改號完成後，migrate 會列出票檔以外仍引用舊票號的位置（commit 訊息、文件、其他票），逐一確認是否要改。
  4. commit 後重新合併。
- **之後查舊號**：舊票號被留在 commit 訊息或對話紀錄裡時，以 `ticket track resolve <舊票號>` 查出現行票號。

完整命令見 [skills/ticket/SKILL.md](./skills/ticket/SKILL.md)〈子命令路由表〉，生命週期規則見 [pm-rules/ticket-lifecycle.md](./pm-rules/ticket-lifecycle.md)。

---

## 專案版本：規劃期與執行期

`docs/todolist.yaml` 是版本索引，也是版本狀態的權威來源：

```yaml
versions:
  - version: "0.2.0"
    description: "<這一版的目標>"
    status: "active"     # planned / active / completed
    worklog: "docs/work-logs/v0/v0.2/v0.2.0/"   # 票與工作日誌的目錄
    # scope: frozen      # 規劃期結束、凍結時才加上；加上後本版不再收新的根票（凍結的兩步見下表）
```

`worklog` 欄位不能省略：協調票、線狀態面板與狀態列靠這個欄位找到版本的票目錄，缺了多 session 協作就找不到協調票；`ticket` 指令本身依版號推導票的位置，不讀這個欄位。

每個版本（major、minor、patch 都一樣）分成兩期：

| 期 | 做什麼 | 不做什麼 | 結束條件 |
|----|-------|---------|---------|
| 規劃期 | 檢討方向、修改規格與設計、決定範圍、建好全部的票並寫定 acceptance | — | 範圍定案後執行凍結程序，步驟見 `.claude/pm-rules/version-progression.md`〈版本生命週期〉「凍結程序」。其中一步是為必要的 pending 票寫入 `scope_blocker` 欄位：發版檢查只把帶 `scope_blocker` 的 pending 票當成阻擋，沒帶的會被判為移到下一版 |
| 執行期 | 照已建的票派發、驗收、合併 | 修改本版規格、因新發現開本版衍生票 | 帶 `scope_blocker` 的票與進行中的票都完成後發版，其餘 pending 票在發版時移到下一版 |

`status` 與兩期的對應：凍結前（`planned`，或 `active` 而沒有 `scope: frozen`）是規劃期；`active` 加上 `scope: frozen` 是執行期；發版時 `/version-release` 把 `status` 改為 `completed`。

執行期的新發現照常建票，但排進後續版本：

- 本版承諾未達成的問題（規格寫了但沒做到、資料錯誤、跑不起來），進下一個 patch（x.y.z+1）。
- 改善、技術債、新能力，進下一個 minor 的候選池。
- 根源在 `.claude/` 通用內容的問題，不建本地票，回報 issue（見〈回報框架問題〉）。
- 唯一例外是讓本版執行跑不起來的問題（測試紅燈、建置失敗、資料損壞），在本版建票並帶 `--scope-blocker <理由>`。

排進後續版本的票，目標版本要先在 `docs/todolist.yaml` 登記為 `planned`，再以 `--version <該版號>` 建票；未登記的版本會被 `ticket create` 拒絕。本版凍結時，下一個 minor 就要登記好。

版本的工作日誌主檔是 `docs/work-logs/v<major>/v<major.minor>/v<版號>/v<版號>-main.md`，與 `tickets/` 目錄同層。規劃期可用 `/version-bootstrap` 把提案展開成票，發版前用 `/version-release` 檢查。完整規則見 [pm-rules/version-progression.md](./pm-rules/version-progression.md)〈兩期：規劃期與執行期〉〈版本生命週期〉。

---

## 並行開發：worktree 與合併閘門

主 checkout（專案原本的工作目錄，相對於 worktree 而言）停在 main，不在主 checkout 切換或建立分支。程式碼修改在 worktree（git 從同一個 repo 另開的工作目錄，各自 checkout 一個分支）裡做：

```bash
worktree create <票號>                            # 在專案目錄旁建立 ../<專案目錄名>-<票號>，分支 feat/<票號>
worktree status                                   # 查看各 worktree 的狀態
worktree merge <票號>                             # 合併；票要先是 completed
worktree merge <票號> --pre-acceptance "<理由>"   # 票還沒完成就先合併，理由寫進 .claude/logs/worktree-merge.log
worktree merge --branch <分支名>                  # 只用於萃取不到票號的分支（如隔離派發的 worktree-agent-<id>）；不查票狀態，也沒有票可對照
worktree cleanup <票號>                           # 清理已合併的 worktree
```

- 票不是 completed 時，`worktree merge <票號>` 在合併前就拒絕，以結束碼 1 結束，main 與分支都不變。拒絕訊息會建議先 complete；要先合併再完成票時，改用 `--pre-acceptance`。
- worktree 只含 git 追蹤的內容。`.gitignore` 排除的依賴（如 `node_modules`）要在 worktree 內另外安裝，建置快取則在第一次建置時重新產生（較慢），見 worktree SKILL〈worktree 不含的狀態〉。

以 Agent 工具派發代理人時，可加上參數 `isolation: "worktree"`，由 Claude Code 自動建立隔離 worktree。隔離 worktree 從 `origin/main` 建立（`worktree create` 則從本機 `main`），派發前先 push main，否則會建在舊的基底上。這種派發下代理人只做到在 worktree 內 commit；主線程以 `worktree merge --branch <分支名>` 合併（經合併閘門），驗證之後才在主 checkout 執行 `complete`（見 [references/agent-definition-standard-details.md](./references/agent-definition-standard-details.md)〈隔離派發的收尾界線〉）。

**合併前全套件**（合併閘門）：`worktree merge` 先在合併結果的快照裡跑測試，紅燈就不合併並列出失敗項。`.claude/` 內的套件由框架對應。專案自己的測試要在 `.claude/project-integration/merge-gate.yaml` 宣告。沒有宣告時，內建對應只在合併快照根目錄有 `pubspec.yaml` 時生效（沒有則下列路徑都算範圍外，只印 WARNING）；有的話，改到 `lib/`、`test/`、`integration_test/`、`macos/`、`docs/`、`assets/` 或 `pubspec.yaml` 等 Flutter 設定檔會跑內建的 `fvm flutter test`，改到不屬於任何套件的其他路徑則只印 WARNING、不跑測試就合併，所以非 Flutter 專案一定要宣告：

```yaml
suites:
  app:
    prefixes: [src/, test/]
    command: [npm, test]
```

**測試名額**：主線程與代理人跑測試時，命令經 `python3 .claude/scripts/run-with-timeout.py <秒數> -- <命令>` 執行，`<秒數>` 是命令本身的逾時上限（排隊時間不計入）。腳本判為較重的命令（如沒有指定測試檔的全套件）才排隊取得全機共用名額，避免多個 session 同時跑全套件拖垮機器。結束碼 124 是逾時，125 是等不到名額（命令沒有執行）。

worktree 指令與合併閘門見 [skills/worktree/SKILL.md](./skills/worktree/SKILL.md)〈合併前全套件（merge 預設行為）〉，測試名額見 [shared-resources.md](./skills/multi-session-orchestration/references/shared-resources.md)〈2. 名額佇列〉。

---

## 多 session 協作

多個 Claude Code session 同時推進同一個 repo 時，由一個主控 session 協調，其他 session 各負責一條工作線。完整操作見 [skills/multi-session-orchestration/SKILL.md](./skills/multi-session-orchestration/SKILL.md)。

### 角色

| 角色 | session 名稱 | 做什麼 |
|------|-------------|-------|
| 主控 | `主控` | 分線、排佇列、轉達你的裁決、協調共用資源。主控長駐，不例行 `/clear` 或 `/compact` |
| 線 | 線的主題，如 `ticket-cli` | 依佇列推進一批同主題的票，同主題的票共用已讀過的程式與事實 |

這裡的「主控」是協調各線的 session，與〈這套框架做什麼〉中維護框架的「主控方」是兩回事。

### 開始協作

1. 選一個 session 擔任主控，執行 `/rename 主控`。
2. 主控建立協調票。版本已凍結（`docs/todolist.yaml` 有 `scope: frozen`）時，`ticket create` 會擋下新的根票，包括協調票：改對進行中的票執行 `ticket track set-coordination <票號>`，或在凍結前建好協調票。版本尚未凍結時，在〈Ticket 系統〉的 `ticket create` 參數之外加上 `--coordination`，建好後以 `ticket track claim <票號>` 認領（新票是 pending，認領後才是 in_progress）。協調票是 active 版本中帶 `coordination: true` 且狀態為 in_progress 的票，線狀態面板與狀態列都從它讀取資料。
3. 主控在協調票的 `## Solution` 為每條線寫目標行與現行佇列行。佇列變動時追加新行，不改舊行，每條線以最後一行為準：

   ```text
   **L1 目標**：<一句話目標>

   **L1 現行佇列**（<session 名稱>）：<票號> → <票號> → <票號>
   ```

   目標行與佇列行各自獨立成段：行首就是 `**L`、前面不留空白，不放進清單或表格。上面的範例在編號清單內，複製時去掉縮排。收線（這條線不再派票）時佇列寫 `（無）`，線狀態面板靠它判定這條線已收線。

4. 每條線開一個 session，以線主題命名：`claude -n <名稱>`。主控把佇列與注意事項寄給該線。

### 溝通

- session 之間以 Claude Code 的跨 session 訊息溝通：`ListAgents` 列出可定址的 session，`SendMessage` 寄送。
- 主控的位址寫成 `主控 [<ref>]`，ref 取自主控自己 `ListAgents` 的第一行。每個專案的主控都叫「主控」，只寫名稱可能寄到別的專案。
- 票面是權威，訊息只是通知：發現、裁定、收尾狀態先寫進票，訊息只引用票號。session 結束後訊息就讀不到了，票面仍在。
- 線停下來等你處理時，會在所持的票寫上「等用戶」標記並通知主控；主控把待你處理的事項以「用戶待辦」標記寫進協調票，線狀態面板的「用戶待辦」區會列出來。兩種標記的格式見 [line-continuity.md](./skills/multi-session-orchestration/references/line-continuity.md)〈等用戶〉〈用戶待辦〉。

### 共用資源

合併閘門、測試名額、主 checkout 的本地 main 由所有線共用，細節見 [shared-resources.md](./skills/multi-session-orchestration/references/shared-resources.md)。

- 單一 session 時，`.claude/`、`docs/` 等豁免路徑可以直接在 main 修改（見〈Hook 擋下時〉）。多 session 時，票檔與 ticket 命令自動提交的檔案以外的修改（含 `.claude/`、`docs/` 下的其他檔案）都在 worktree 做、經合併閘門合入，只有這兩類直接在主 checkout 提交。版本登記（`docs/todolist.yaml`）不在這兩類內：先在 worktree 登記並合併，再建該版的票。原因是各線共用同一個本地 main，在主 checkout 提交的其他變更會被別條線的推送一併帶上 main，等於略過閘門。
- 更新框架（`/sync-pull`）前，先讓各線收線、回到單一 session，再在主 checkout 照〈更新到新版本〉進行：單一 session 時 `.claude/` 屬豁免路徑，可以在 main 修改；多 session 時拉取的變更要走 worktree，而 worktree 裡沒有基準點。
- 兩條線的票改到同一個檔案而互等時，主控先建一張拆分評估票，排在兩張票之前；拆分評估票把檔案拆開之後，各票再改各自的新檔。判準見 [file-split-by-contention.md](./skills/cognitive-load-assessment/references/file-split-by-contention.md)。

### /clear 與 /compact 之後

- **線**：主軸不變（續做、轉階段、context 達門檻）時，線收尾寫好票面後，由你在原 session 輸入 `/clear`，主控再重新派發。只有主軸改變時才由你 `/rename <新線主題>` 或另開 session；改名後舊名立即無法定址，主控要同時更新現行佇列行裡的 session 名稱。收線後由你關閉該 session。
- **主控**：只在 context 將要耗盡、或你明示要清除時才 `/clear` 或 `/compact`。清除後，主控先以 `line_status` 工具判讀各線狀態，分為已收線、`/clear` 後繼續、`/compact` 後繼續、新 session 接手。判讀結果寫進協調票，再向你回報。
- 你說「繼續工作」這類沒有指定對象的指示時，主控先列出開線計畫表給你確認，不直接派票。

---

## line-board 線狀態面板（/board）

line-board 是隨 skills 目錄載入的 Claude Code plugin，讓你在一個終端機裡就看到多 session 並行開發的現況，不必逐一切換 session。其他文件與 plugin 說明目前稱這個面板為「看板」。預設啟用，第一次載入時要接受 workspace trust。

| 介面 | 內容 |
|------|------|
| 線狀態面板（Pane，終端機內另開的一塊畫面） | 用戶待辦、每條線的現行佇列與票狀態、派發中的代理人、這個專案（主 checkout 與各 worktree）中各 session 的狀態、合併閘門最近紀錄。輸入 `/board` 開啟，關掉後也用它重開 |
| 狀態列 | 在你原本的狀態列上方另起一行 `L<線編號> │ <session 名稱>`（線編號即協調票裡 L1、L2 的數字；session 沒有對應的線時只顯示名稱），切換終端機時能看出自己在哪一條線。這一行由 `settings.json` 的狀態列設定提供，不屬於 plugin |
| `line_status` 工具 | 供模型呼叫，回報各線的接續狀態與過期項；主控清除 context 後接續時使用 |

- 有協調票時，session 啟動會自動開啟線狀態面板。沒有協調票時不開啟、也不定時讀取，只用單一 session 的專案不受影響。
- 符合條件的協調票有多張時，線狀態面板列出候選票號，請你裁定。
- 線狀態面板只讀寫本機檔案（每輪把 context 用量寫進 `.claude/hook-logs/line-board/`），不改設定，不連網。
- 不想使用時，在 `settings.local.json` 或使用者層 `~/.claude/settings.json` 加上 `{ "enabledPlugins": { "line-board@skills-dir": false } }`。關閉 plugin 不影響狀態列的線號那一行。

畫面規格見 [board-screens.md](./skills/line-board/references/board-screens.md)，資料來源見 [skills/line-board/SKILL.md](./skills/line-board/SKILL.md)〈協調票來源〉。

---

## 回報框架問題

先判斷問題屬於哪一邊：把專案名稱與路徑換掉之後問題仍成立，且根源在 `.claude/` 的通用內容，就是框架問題；否則是專案問題，照常建專案的票。

框架問題回報到 `tarrragon/claude` 的 issue，`.claude/` 下框架 skill 的問題也回報到這裡；第三方 vendored skill（如 `skills/impeccable/`，來源見該目錄的 `NOTICE.md`）的問題，回報到它的上游。這是公開 repo，內文照下列寫：

- 每則 issue 都寫：現象、預期與重現步驟。
- 被 Hook 擋下時另外附上：擋下的訊息全文、hook 名稱，以及 `.claude/hook-logs/` 下該 hook 的日誌目錄裡當天相關的幾行（目錄名是 hook 寫日誌用的識別名稱，不一定等於檔名，常省略 `-hook`；以 `ls .claude/hook-logs/` 對照）。
- 不放專案名稱、內部路徑或機密。日誌與擋下的訊息常含專案的絕對路徑，貼上前把專案名稱與路徑換成 `<專案>`、`<路徑>` 這類佔位符。

```bash
FI=.claude/skills/framework-issue/scripts
python3 $FI/section_comment.py dedup --keywords "<關鍵字>" "<另一組關鍵字>"   # 先查重
python3 $FI/create_issue.py --title "<標題>" --body "$(cat <內文的檔案>)"    # 沒有重複才建立
```

內文先寫進一個檔案，再以 `"$(cat <內文的檔案>)"` 傳入。擋下的訊息常含反引號，依〈Ticket 系統〉的通則，不直接寫在雙引號裡。

沒有 gh 時，先在 GitHub 網頁的 `tarrragon/claude` Issues 頁以關鍵字搜尋查重，沒有重複再以「框架問題回報」範本建立 issue（範本要求填 `.claude/VERSION`）。

- `create_issue.py` 會自動附上環境資訊與框架版本（`.claude/VERSION`）。
- 查重命中時，逐一判定命中的 issue 與你的問題是什麼關係：判定為重複，就改用 `python3 $FI/section_comment.py observe <issue 號> --summary "<摘要>" --session <識別> --content-file <內容檔>` 補充實測（`--session` 會公開寫進 comment 首行，不要放專案名稱），`observe` 同樣會自動附上框架版本；同一領域、不同層級（例如框架整體對單一 skill）是切分，只是提及、領域不同是引用，這兩種就建新 issue 並在內文引用（見 [comment-as-section-protocol.md](./skills/framework-issue/references/comment-as-section-protocol.md)〈init 前查重：三種關係處置〉）。
- 結束碼 3 表示降級、結果不完整，或被拒絕而沒有送出（例如 gh 未登入、部分查詢失敗、observe 的內容為空），讀 stderr 的說明。
- consumer 不自行修改 `.claude/` 的通用內容。修正由主控方排進某個版本發版，issue 會留言寫明哪一版修好，之後以 `/sync-pull` 取得。
- 等修復期間，如果框架問題讓你的工作需要繞路、重做或停工，在該 issue 以 `observe` 附一則觀測，`--summary` 與內容檔第一行都寫「拖慢專案」與受影響的工作。主控方規劃版本時會讀這些標記（見 [escalation-flow.md](./skills/framework-issue/references/escalation-flow.md)〈修復時點：版本分診〉）。

判斷流程與命令細節見 [skills/framework-issue/SKILL.md](./skills/framework-issue/SKILL.md)，角色判定見 [escalation-flow.md](./skills/framework-issue/references/escalation-flow.md)〈角色：主控方與 consumer〉。

---

## 單獨使用 skill：skill-sync

skill 發佈庫 `tarrragon/claude-skills` 收錄可以單獨安裝的 skill。使用前先取得 `skill-sync`，依機器的狀況擇一：
- 機器上有已安裝框架的專案：SessionStart 會自動安裝 `skill-sync` shim，直接用，或以 `uv run --project <那個專案>/.claude/skills/skill-sync skill-sync <子命令>` 呼叫。
- 機器上沒有框架專案：先把 `tarrragon/claude` clone 到任一目錄，再執行 `uv tool install --from <clone 的目錄>/skills/skill-sync skill-sync`。這會裝到 `~/.local/bin`，之後若在同一台機器開了框架專案，那個專案的 SessionStart 會蓋掉這支（見下）。

| 情境 | 做法 |
|------|------|
| 只想用某些 skill，不同步整個框架 | `skill-sync list` 查看可用的 skill，`skill-sync pull <名稱>` 裝進 `.claude/skills/<名稱>/` |
| 你的專案在 `CLAUDE.md` 宣告為某個 skill 的開發上游 | 在本地修改該 skill，以 `skill-sync push <名稱>` 送進發佈庫；主控方發版前收入框架。推送前先跑不帶名稱的 `skill-sync pull`，確認本地與發佈庫哪一邊領先。發佈庫領先時先 `skill-sync pull <名稱>`：它會整份覆蓋本地，拉完要把尚未推送的本地修改補回，再推送 |

- 同一台機器上有框架專案時，那個專案的 SessionStart 會把 `~/.local/bin/skill-sync` 改成框架的 shim，蓋掉非框架專案用 `uv tool install` 裝的版本。非框架專案改以 `uv run --project <clone 的目錄>/skills/skill-sync skill-sync <子命令>` 直接呼叫，不依賴 `~/.local/bin` 的那一支。
- 以整個框架同步為前提的 skill（如 line-board、framework-update-adaptation）不收錄。
- 開發上游要有 `tarrragon/claude-skills` 的推送權限：`skill-sync push` 會 clone 發佈庫後直接 `git push`，沒有權限時推送失敗。
- 宣告開發上游的例外只涵蓋宣告的 skill，同一專案對其他 `.claude/` 內容仍只回報 issue。

細節見 [skills/skill-sync/SKILL.md](./skills/skill-sync/SKILL.md)〈Before you push: resolve direction first〉（推送前先確認同步方向）。

---

## 其他常用指令

| 指令 | 用途 |
|------|------|
| `/ticket` | 列出進行中與可認領的票，讓你選擇 |
| `/tdd` | TDD 各階段引導 |
| `/parallel-evaluation` | 多視角審查：程式碼、架構、分析結論 |
| `/wrap-decision` | 卡關、重大決策、根因分析時擴增選項並做現實檢驗 |
| `/error-pattern` | 查詢與記錄錯誤模式，知識庫在 [error-patterns/](./error-patterns/) |
| `/doc` | 提案、規格、用例文件（proposals／spec／usecases）與追溯 |
| `/version-bootstrap` | 規劃期：把版本提案展開成票 |
| `/version-release` | 發版前檢查與收尾 |
| `/strategic-compact` | 判斷何時手動 `/compact` |
| `/project-init` | 環境檢查與設定 |
| `/framework-update-adaptation` | `/sync-pull` 之後對齊你的專案 |

常用 skill 的對照見 [pm-rules/skill-index.md](./pm-rules/skill-index.md)；全部 skill 以 [skills/](./skills/) 目錄為準。

---

## 目錄結構

主要目錄與檔案（不是完整清單）：

```text
.claude/
├── README.md / VERSION / CHANGELOG.md / LICENSE / THIRD-PARTY-NOTICES.md
├── settings.json              # 框架：Hook 註冊、權限、狀態列（隨拉取更新）
├── settings.local.json        # 專案：回應格式、MCP、環境變數（不同步）
├── rules/core/                # 每回合自動載入的通用規則
├── pm-rules/                  # 主線程按需讀取的流程規則：決策樹、TDD、票、派發、版本
├── references/                # 按需讀取的詳細說明
├── methodologies/             # 方法論
├── agents/                    # 代理人定義
├── skills/                    # skill，含 CLI 工具與 line-board plugin
├── hooks/                     # Hook 腳本（Python）
├── lib/                       # hooks 與 skills 共用的模組
├── config/                    # 框架設定：Hook 語言分類與註冊表、代理人清單等 YAML
├── scripts/                   # 同步、測試名額、清理等工具腳本
├── error-patterns/            # 錯誤模式知識庫
├── commands/                  # slash 命令（/sync-pull 等）
├── output-styles/             # 回應格式（5W1H）
├── templates/                 # CLAUDE.md、settings.local.json 等模板
└── project-integration/       # 專案自建：對框架的宣告（不同步）
```

Claude Code 啟動時自動載入 `CLAUDE.md` 與 `rules/` 下的規則，其他目錄按需讀取。`rules/core/` 只放每回合都要遵守的規則，情境性內容放 `references/`，分層原則見 [rules/README.md](./rules/README.md)。

---

## 核心文件索引

| 想知道 | 讀 |
|-------|---|
| 規則的分層與載入方式 | [rules/README.md](./rules/README.md) |
| 主線程收到任務後怎麼決定 | [pm-rules/decision-tree.md](./pm-rules/decision-tree.md) |
| 品質底線 | [rules/core/quality-baseline.md](./rules/core/quality-baseline.md) |
| 票的生命週期 | [pm-rules/ticket-lifecycle.md](./pm-rules/ticket-lifecycle.md) |
| 版本兩期、patch 與 minor 的分界 | [pm-rules/version-progression.md](./pm-rules/version-progression.md)〈兩期：規劃期與執行期〉〈收斂：patch 線與 minor 推進〉 |
| 驗收三項固定檢查 | [pm-rules/verification-framework.md](./pm-rules/verification-framework.md)〈驗收三項固定檢查〉 |
| 並行派發 | [pm-rules/parallel-dispatch.md](./pm-rules/parallel-dispatch.md) |
| 測試失敗或錯誤發生時 | [pm-rules/incident-response.md](./pm-rules/incident-response.md)、[pm-rules/skip-gate.md](./pm-rules/skip-gate.md) |
| 方法論 | [pm-rules/methodology-index.md](./pm-rules/methodology-index.md) |
| 常用 skill 指令（全部以 `skills/` 目錄為準） | [pm-rules/skill-index.md](./pm-rules/skill-index.md) |
| 同步機制 | [references/sync-mechanism-guide.md](./references/sync-mechanism-guide.md) |

---

## 框架的版本與發佈

| Repo | 角色 |
|------|------|
| `tarrragon/claude` | 框架發佈通道：每次推送對應一個 `v<版號>` tag；framework issue 也收在這裡 |
| `tarrragon/claude-skills` | skill 發佈庫：可單獨安裝的 skill |
| 主控方 repo（不公開） | 框架的修改、規劃與發版 |

版號採 SemVer，從 3.0.0 開始：

| 層級 | 何時遞增 |
|------|---------|
| major | consumer 端契約不相容，例如 sync 流程、`settings.json` 結構、ticket schema 改變，需要下游遷移 |
| minor | 依規劃發版的一批功能或修正 |
| patch | 本 minor 承諾未達成的修復：規格寫了但沒做到、資料錯誤、跑不起來 |

`create_issue.py` 與 `observe` 會自動附上 `.claude/VERSION`，主控方據此判斷問題在哪一版修好、是不是回歸。

---

## 移除

1. **移出自己的內容**：`CLAUDE.md`、`settings.local.json` 裡你自己加的內容，以及放在 `.claude/` 下的自訂 command、agent，先複製到別處。第 3 步會連同它們一起刪除。
2. **清理 worktree**：執行不帶參數的 `worktree cleanup` 列出所有 worktree，再逐一以 `worktree cleanup <票號>`（隔離派發的用 `--branch <分支名>`）清理。清理有閘門：worktree 內有未 commit 的變更一律擋下；分支還沒推送、也還沒合併進 `main` 時警告並擋下，確定要丟棄時加 `--force`。`worktree` 指令在 `.claude/` 內，刪除 `.claude/` 之後就不能用了。
3. **刪除框架**：刪除 `.claude/` 與 `CLAUDE.md`；不保留票與工作日誌時，一併刪除 `docs/work-logs/` 與 `docs/todolist.yaml`。接著執行 `git worktree prune`，清掉目錄已不存在的 worktree 登記。`.gitignore` 裡〈首次安裝〉第 5 步加的條目可以一併刪除。
4. **刪除 git 原生 hook**：`.git/hooks/` 下的 `pre-commit` 與 `reference-transaction`（worktree 共用 `git rev-parse --git-common-dir` 下的同一份）。只刪框架裝的檔案：以 `grep -l git-ref-transaction-guard-install-hook "$(git rev-parse --git-common-dir)/hooks/"*` 列出，沒列出的是你自己的 hook。安裝時有 `pre-commit.local`，把它改名回 `pre-commit`。只刪 `.claude/` 不會讓 commit 失敗，這兩個 hook 找不到框架腳本時直接放行。
5. **刪除 CLI shim 與全機共用目錄**：`~/.local/bin` 下的 CLI shim，以及 `~/.cache/claude-slot`、`~/.cache/claude-proc-registry` 兩個目錄，由所有使用框架的專案共用，確定沒有其他專案在用時再刪。框架的 shim 以 `grep -l install-skill-clis ~/.local/bin/*` 列出；同一目錄可能還有其他工具（如 `uv`），不要整個目錄刪除。

git hook 的移除步驟見 [references/hook-architect-technical-reference.md](./references/hook-architect-technical-reference.md)〈git 原生 hook 的安裝與移除〉。

---

## 授權

這套框架（`.claude/` 的內容）採用 MIT 授權條款，全文見 [LICENSE](./LICENSE)。例外：目錄內另附授權檔的部分依該檔，例如 `skills/impeccable/` 採 Apache 2.0（見該目錄的 `LICENSE` 與 `NOTICE.md`）。

---

**最後更新**: 2026-11-10
**維護者**: [@tarrragon](https://github.com/tarrragon)
