# track 子命令（sessions、reclaim、activity、conflicts、onboard、hook-liveness、artifacts）

> **用途**：`track` 子命令詳解之一：sessions、reclaim、activity、conflicts、onboard、hook-liveness、artifacts。
>
> **同族檔**：`track-command-commit.md`、`track-command-update.md`、`track-command-dispatch.md`、`track-command-session.md`、`track-command-query.md`、`track-command-health.md`。原檔 `track-command.md` 保留檔頭與保留段落，並為各被移走段標保留路由，被移走段標在原檔以同名標題加一行路由保留，既有〈段標〉引用不需改寫。

---

## track sessions 子命令

> 來源：multi-PM 協調層 Phase 1，issue tarrragon/claude#77

read-only 查詢 `pm-registry.json`，列出同專案 PM session 清單（heartbeat 新鮮度 / 認領 tickets 與 files 數），供多 PM 並行時互相察知彼此範圍。

### 用法

```bash
ticket track sessions [--format {table,json}]
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--format` | `table` | `table`（人閱讀）/ `json`（腳本消費，輸出 `{"sessions": [...]}`） |

### Registry 位置與 Schema

- 路徑：`<git rev-parse --git-common-dir>/pm-registry.json`（worktree 內亦解析回主 repo `.git/`，跨 worktree 共用單一實例）
- 內容 schema（v2；`schema_version` 欄位標記）：`sessions.<session_id>` 含 `name` / `project` / `registered_at` / `heartbeat_ts` / `tickets` / `files`（v1 曾含 `parent_session_id`，v2 已移除——恆等 `session_id` 的冗餘欄位，見 `.claude/lib/pm_registry.py` 檔頭 docstring「v2 相對 v1 的變更」；舊版 v1 檔案仍可讀取，寫入時自然正規化為 v2 形狀）
- **契約住址**：`.claude/lib/pm_registry.py` 檔頭 docstring 自稱「Registry Schema 契約 v2（單一來源，本模組不得自行變更欄位/結構）」，為 registry schema 唯一權威定義；本節與其餘消費端（`.claude/references/bash-tool-usage-details.md`、`.claude/references/parallel-dispatch-agent-lifecycle-details.md` 等）僅描述讀取端行為，不重複定義 schema，變更 schema 須先改該 docstring 再同步消費端
- 寫入端（hooks 職責）：SessionStart 註冊 + heartbeat 更新、Stop/handoff 釋放；本命令僅讀取，不寫入

### 輸出格式（table）

```
=== PM Sessions ===
  session_id  name                 age(min)  status  tickets  files  reclaimable
  ---------------------------------------------------------------------------------
  session-a   flutter-balance-b6          5  FRESH         1      2  -
  session-b   flutter-balance-c2         45  STALE         2      3  0.2.1-W3-100, 0.2.1-W3-101
```

### 欄位定義

| 欄位 | 說明 |
|------|------|
| `session_id` | CC hook 輸入 JSON 的 `session_id` |
| `name` | session 名稱（未提供時退回 `session_id`） |
| `age(min)` | heartbeat 與查詢當下的分鐘差（整數，捨去）；無法解析時顯示 `?` |
| `status` | `FRESH`（heartbeat 30 分鐘內）/ `STALE`（逾 30 分鐘或無法解析） |
| `tickets` | 該 session 認領的 ticket 數 |
| `files` | 該 session 認領的檔案數 |
| `reclaimable` | `STALE` session 持有的全部 ticket id（逗號分隔）；`FRESH` 時恆為 `-`。僅 heartbeat 新鮮度輕量判準，非「track reclaim 子命令」實際執行前的 ghost 鑑識三查結果——兩者為兩層判定，見該章節「與 sessions/runqueue 顯示層判定的差異」 |

### 降級行為（不阻擋工作流）

| 情境 | 行為 |
|------|------|
| `pm-registry.json` 缺檔 | 輸出空表 + exit 0 |
| JSON 解析失敗 | stderr 提示 + 輸出空表 + exit 0 |
| 非 git repo / git 不可用 | 輸出空表 + exit 0 |
| session `heartbeat_ts` 缺失或格式錯誤 | fail-open 視為 `STALE`（不可靜默呈現「新鮮」假象） |

### 設計約束

- version-agnostic：見〈共用旗標語意（track 系列命令通用）〉
- 僅列 `project` 欄位等於當前 `git rev-parse --show-toplevel` 的 session（同專案篩選；git 不可用時不篩選，保留全部）
- stale 判定閾值固定 30 分鐘（`STALE_THRESHOLD_MINUTES`）；`reclaimable` 欄位僅為輕量標記（heartbeat 判準），實際執行 reclaim（轉回 pending + 清 lease）另見「track reclaim 子命令」章節（multi-PM 協調層 Phase 3）
- Registry Schema 契約 v2 為 hooks 與 CLI 兩職責共同 SSOT，本命令不得自行變更 schema

---

## track reclaim 子命令

> 來源：multi-PM 協調層 Phase 3，issue tarrragon/claude#77

現行 `claim` 永不過期，PM session 崩潰後持票永久鎖死。`reclaim` 提供受控釋放路徑：僅接受 `in_progress` 且無 FRESH session 佐證（或 registry 未追蹤）的票，並強制執行 ghost 鑑識三查，任一命中或無法判定即拒絕。

### 用法

```bash
ticket track reclaim <ticket_id> [--version V]              # dry-run：僅印鑑識報告
ticket track reclaim <ticket_id> [--version V] --confirm    # 三查全過才實際轉回 pending
```

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--version` | 自動偵測 | 版本號（ticket_id 本身含版本段時可省略，CLI 自動解析） |
| `--confirm` | False | 三查鑑識全過才生效：轉回 pending 並清除 registry lease；未加此旗標僅印 dry-run 報告 |

### Ghost 鑑識三查

`--confirm` 是否放行取決於前兩查（未合併分支、髒檔交集）：任一命中或無法判定即拒絕（與 `--confirm` 是否給出無關——`--confirm` 只決定「前兩查皆通過後是否落地」，不能覆蓋其結果）。第 3 查（缺 Exit Status）為 soft warning，**不計入拒絕與否的判定**，僅記錄於鑑識報告供人工參考：

| 查 | 判定內容 | 命中條件 | 是否影響 `--confirm` 放行 |
|----|---------|---------|---------|
| 1. 未合併分支 | `git branch --no-merged` 是否存在含 ticket_id 的分支名 | 存在即命中 | 是，命中即拒絕 |
| 2. 髒檔交集 | `git status --porcelain` 路徑與票面 `where.files` 是否有交集 | 有交集即命中 | 是，命中即拒絕 |
| 3. 缺 Exit Status | 票面 `Exit Status` 章節是否仍為佔位符或未找到 | 缺失/佔位符即命中 | 否，警告，不計入結論（`lease.py` `GhostReport.clean` 明式排除本項） |

第 1、2 查依賴 git 查詢；查詢本身失敗（非「查到零筆」）時標記為「無法判定」，與「通過」區分對待——查詢失敗不可視為通過（防止 fail-open 誤放行），且與命中同樣導致拒絕。第 3 查為純票面內容比對，不受此影響，且不參與拒絕判定。

**判準（依實作改寫，非文件先前所述「三查任一命中即拒絕」）**：第 3 查刻意不計入拒絕判定。**Why**：遺留票的定義正是執行者已不在，`Exit Status` 章節必然無人能填——若把這種常態當拒絕條件，會使 reclaim 對它最該服務的對象（真正遺留的票）不可用，逼流量繞去零鑑識的 `ticket track release`。「執行中票不可 reclaim」的性質已由 `check_reclaimable` 的 FRESH lease 判定於呼叫鑑識前獨立把關；owner 為 None（registry 未追蹤 lease）時則由前兩查覆蓋——執行中的代理人通常仍有未合併分支或未提交變更，可視為間接把關。**Action**：`--confirm` 對某張明顯已死的 session 持票持續拒絕，只可能因命中前兩查其一，非因缺 Exit Status；判讀鑑識報告時，第 3 查「缺失/佔位符（警告，不影響鑑識結果）」不構成拒絕理由。

### 輸出格式（dry-run 範例）

```
[reclaim] 0.2.1-W3-100: registry 未追蹤此票 lease（無 FRESH session 佐證），允許依 ghost 鑑識判定
=== Ghost 鑑識報告: 0.2.1-W3-100 ===
  1. 未合併分支: 通過
  2. 髒檔交集: 通過
  3. Exit Status 章節: 已填寫
  結論: 鑑識通過，允許 reclaim
[reclaim] 0.2.1-W3-100: dry-run 完成，鑑識通過；加 --confirm 執行實際 reclaim
```

### 與 sessions/runqueue 顯示層判定的差異

**結論**：「`sessions`/`runqueue` 顯示為可 reclaim 候選」與「`reclaim --confirm` 實際放行」是兩層判定，前者是列表級的粗篩提示，後者才是逐票的精確判定；粗篩顯示候選不保證 `--confirm` 會放行。

`runqueue` 的 `[RECLAIMABLE]` 標記經 `is_lease_reclaimable` 判定：持有者 session heartbeat 逾 TTL，**或** registry 已載入但未追蹤此票 lease（含 graceful SessionEnd 釋放後 entry 已刪除的情形）。`sessions` 的 `reclaimable` 欄**不呼叫**本函式，而是 `track_sessions.py` 自算（僅 `status == "STALE"` 才列）——判準分岔，語意對象不同（一為接手提示，一為 session 逾時）。兩者皆**不含**本命令的 ghost 鑑識三查——鑑識涉及 git 呼叫，不適合逐票渲染表格時觸發。

### Exit code

| 值 | 說明 |
|----|------|
| 0 | dry-run 鑑識通過 / `--confirm` 且落地成功 |
| 1 | 找不到 ticket、票非 in_progress、有 FRESH session 佐證、鑑識未通過、或落地時票面更新失敗 |

### `--confirm` 落地：鑑識報告寫入 Solution

`--confirm` 且三查（依上方判準，僅第 1、2 查計入拒絕判定）全過、實際轉回 pending 後，鑑識報告額外 append-log 進票面 `Solution` 章節，供事後對帳（原僅印終端機，`--confirm` 決策無法回溯稽核）。dry-run（未帶 `--confirm`）與三查未通過兩路徑皆不落地寫入。落票為稽核強化，非 `reclaim` 成功的前提——落票本身失敗（如 hook 內部例外）不影響 `reclaim` 已完成的狀態轉換，僅記 stderr。

### 設計約束

- 外層流程跨兩把獨立鎖，非單一原子操作：`check_reclaimable` 讀 registry（無鎖快照）→ ghost 鑑識（純讀取，無鎖）→ 落地持 ticket md 的 `file_lock` → 之後才持 registry 的 `_registry_lock` 清 lease。理論上存在窄視窗（owner session 可能在鑑識後、落地前恢復心跳），影響侷限於「STALE 誤判為短暫失聯的 session 遺失一張已無在途工作證據的票」，非資料損毀風險
- registry 未追蹤該票 lease 時仍允許依 ghost 鑑識判定（registry 缺失非阻擋條件，同 Registry Schema 契約「損毀/缺檔處置」降級語意）

---

## track activity 子命令

> 來源：multi-PM 協調層 Phase 2，L1 新鮮度

票面進度是事件驅動更新（claim/append-log/complete），事件間有 27-35 分鐘常態靜默窗口（依歷史 ticket 事件時間戳觀察得出的經驗範圍，非正式統計抽樣結果；如需重算可對照近期 `.claude/hook-logs/` 或 ticket `updated` 時間戳間隔），靜默本身無法判斷「在做/卡住/session 已死」。`activity` 從既有副作用機械推導每張 `in_progress` 票的最後活動時間，把靜默從歧義降為可判定狀態。

### 用法

```bash
ticket track activity [--version V] [--all] [--format {table,json}]
```

### 三源（取最新者，附來源標記）

| 來源標記 | 說明 |
|---------|------|
| `md_mtime` | ticket md 檔案的磁碟 mtime |
| `git_commit` | `git log --grep=<id>` 最後一筆 commit 的 committer 時間 |
| `dirty_file` | working tree 髒檔命中該票 `where.files` 的歸屬，取命中檔案的磁碟 mtime |
| `no-signal` | 三源皆缺（非錯誤，票剛 claim 尚無任何副作用時的正常狀態） |

**父子票邊界**（判準）：子票 commit 不計入父票活動，父票 `git_commit` 源不會被子票覆蓋（實作機制：`git log --grep` 加 `--fixed-strings` 並在 Python 端逐一驗證候選 commit 的 subject 是否為「獨立引用」，見 `track_activity.py` 程式碼註解）。

### 輸出格式（table）

```
=== Ticket Activity (L1) ===
  id            last_activity              source      agent
  ---------------------------------------------------------------
  0.2.1-W3-001  2026-08-18T10:00:00+00:00  git_commit  thyme-python-developer
```

### 設計約束

- 共用旗標語意（--all、version-agnostic）：見〈共用旗標語意（track 系列命令通用）〉，本命令預設已掃描全部 active 版本的 `in_progress` 票
- 髒檔路徑比對用 `PurePosixPath` 前綴判定，非 `string.startswith`（避免 `lib/foo` 誤命中 `lib/foobar.dart`）  <!-- skill-residue-exempt: 說明路徑比對規則的示意路徑，非本專案實際檔案 -->
- git 呼叫一律經 `.claude/lib/git_utils.run_git_command`（已內建 `--no-optional-locks`，避免與並行 PM session 競爭 `.git/index.lock`），lazy import 比照 `ticket_system/lib/claude_lib_loader.py` 的 `_find_claude_dir()` 共用實作
- `attribute_dirty_files()` 為髒檔歸屬第三源的獨立輸出函式，供 `onboard` 命令複用

---

## track conflicts 子命令

> 來源：multi-PM 協調層 Phase 2，where.files 交集

並行派發前跑 `conflicts --among` 確認候選票是否互撞；宣告互斥不代表不撞（Phase 2 盲測實證：宣告 `where.files` 吻合度僅 3/10，即七成 completed 票的實際 commit 超出宣告範圍；來源見 `ticket_system/lib/file_conflict.py` 模組 docstring「Phase 2 盲測實證」，非 `CHANGELOG.md`——原指向已過期，CHANGELOG.md 現無此數字），故本命令內建 impl→test 擴張啟發式擴大偵測面，補「宣告實作檔、漏宣告伴生測試檔與關聯模組」這類缺漏。

### 用法

```bash
ticket track conflicts [--version V] [--all] [--format {table,json}] [--since-days N]
ticket track conflicts --for <ticket-id> [--include-heuristic] [--format {table,json}]
ticket track conflicts --among <id1,id2,...> [--include-heuristic] [--format {table,json}]
```

`--for` 與 `--among` 為針對性查詢：PM 並行派發前只想問「這幾張會不會撞」，
不必人工 grep 全量輸出。二擇一（同時提供時 `--among` 優先）：

- `--for <ticket-id>`：列出該票與其他 `pending`/`in_progress` 票之間的全部衝突對
- `--among <id1,id2,...>`：僅比對指定票組彼此之間（逗號分隔，票組外的票不出現）

兩者皆預設隱藏純目錄層級宣告命中（如 `.claude/hooks/` 對任何位於該目錄下
的檔案宣告皆會匹配，屬噪音來源），需顯式加 `--include-heuristic` 開啟；
未帶 `--for`/`--among` 的既有全量輸出行為不受影響（仍照舊顯示目錄層級命中）。

### 判定規則

1. 兩兩比對 `pending`/`in_progress` 票的 `where.files`（原始宣告 + 啟發式衍生）
2. 路徑交集用 `PurePosixPath` 前綴比對（精確相符或互為上層目錄），非 `string startswith`
3. impl→test 擴張啟發式：對每個宣告檔案路徑額外推導可能的伴生測試檔路徑一併納入交集判定；目前覆蓋兩種慣例——Dart `lib/...` → `test/..._test.dart`（不查真實檔案系統）<!-- skill-residue-exempt: 描述推導慣例的模式示意，非本專案實際檔案 -->；Python `X.py` → 掃描真實檔案系統找出最近的 `tests/` 兄弟目錄（見「Python 測試路徑推導」），找不到真實 `tests/` 目錄時不衍生候選
4. 與 pm-registry 的 `files` 欄位交叉比對：僅採 **FRESH session**（heartbeat 未逾 30 分鐘）的宣告，`in_progress` 票若與其認領 session 的 registry files 完全無交集，輸出 stderr 警告（不影響 exit code）；STALE session 的殘留宣告排除在外，避免死 session 舊宣告誤觸發警告。警告文字附後果與下一步：「衝突判定僅採 write 集合；請校正票面宣告或重跑 claim」——說明本命令的判定基準只看票面宣告（不讀 registry），並指引兩種修正路徑。`write` 集合的判定依據（後綴標記與 type 預設意圖）見 `field-semantics.md`〈where.files 宣告語意〉
5. `[heuristic]` 標記：衝突僅由擴張啟發式衍生路徑觸發（原始宣告值本身無交集）

### 同檔票樹競爭統計

衝突命中的檔案另外統計「近 N 天被幾棵不同票樹修改」（`--since-days`，預設 14），輸出在 table 的 `[競爭]` 段與 json 的 `contention` 鍵（`conflicts` 鍵不變）。table 只列票樹數 >= 2 的檔，json 保留全部。

| 項目 | 規則 |
|------|------|
| 票樹 | commit 訊息中票號的 `版本-波次-序號` 第一段；`chore(` 開頭的 commit 不計 |
| 統計範圍 | 只算衝突命中的檔，不掃全庫；無衝突時不跑 git |
| 拆分建議 | 票樹數達門檻且非聚合檔時附「建議拆分」；判準與聚合檔清單見 `.claude/skills/cognitive-load-assessment/references/file-split-by-contention.md` |
| git 失敗 | stderr 印一行並略過統計，原輸出與 exit code 不變 |

### Python 測試路徑推導

**規則**：`tests/` 為套件根目錄的兄弟層（非緊鄰檔案自身目錄下的子目錄），取最近（最深）一個實際存在的候選；找不到符合的 `tests/` 兄弟目錄時不猜測、不衍生候選。逐層往上檢查每個祖先目錄的演算法細節見 `file_conflict.py` 程式碼註解。

> **與覆核指令的區別**：以上是 `conflicts` 啟發式「推測」原始碼對應測試檔位置的演算法（用於偵測潛在衝突），非本 ticket skill 覆核自身測試套件時該如何執行測試——後者的標準覆核指令與禁止事項見 `references/architecture.md`「覆核測試指令（skill 自身測試套件）」章節（唯一權威版本，本檔不留副本）。

### Exit code

| 值 | 說明 |
|----|------|
| 0 | 無衝突 |
| 1 | 偵測到至少一組衝突（registry 警告不影響此判定） |

### 輸出格式（table）

```
=== File Conflicts ===
  0.2.1-W3-001 <-> 0.2.1-W3-002 [heuristic]: test/domain/foo_test.dart  <!-- skill-residue-exempt: 命令輸出範例的示意路徑，非本專案實際檔案 -->
```

### 設計約束

- 共用旗標語意（--all、version-agnostic）：見〈共用旗標語意（track 系列命令通用）〉
- registry 讀取一律經 `.claude/lib/pm_registry` 的 `get_registry_paths` + `read_registry`
- 純目錄級宣告（如 `lib/domain`）與巢狀檔案級宣告天然會被判為交集——這是已知取捨（issue #77 討論記錄：純目錄級 lease 會造成過度序列化），本命令僅負責偵測呈現，不負責治理宣告粒度

---

## track onboard 子命令

> 來源：multi-PM 協調層 Phase 2，入場四節彙整

`onboard` 為輔助入口，非 PM 接手流程首選（見 `SKILL.md`〈無子命令時的預設行為（dashboard-first）〉，裸 `/ticket` 一律先走 dashboard-first 流程）；本命令讀四節（活同事／孤兒 entry／髒檔歸屬／可認領建議），把 session 啟動已印的 30+ hook 輸出牆收斂為單一固定值表，供需要多 PM 協調細節時查詢。`/clear` 後入場是從世界平面重建三問（我是誰 / 同事是誰 / 我手上有什麼），不是恢復記憶。

### 用法

```bash
ticket track onboard [--version V] [--all] [--top N] [--format {table,json}]
```

### 四節

| 章節 | 資料來源 |
|------|---------|
| 活同事表 | 複用 `track_sessions._build_rows`（FRESH session） |
| 孤兒 entry 表 | 同上（STALE session：heartbeat 已死但 registry entry 未回收） |
| 髒檔歸屬 | 本檔獨立實作，僅比對 `in_progress` 票，見下方「髒檔歸屬設計」 |
| 可認領建議 | 複用 `track_dashboard.load_top_ready`（同 dashboard Ready 章節） |

### 髒檔歸屬設計：輸出判讀對映

| 輸出 | 判讀 | 下一步 |
|------|------|--------|
| 「泛目錄宣告命中 N 票（無鑑別力）」 | 宣告太淺（路徑段數 <= 2，如僅宣告 `.claude/`），無法判斷髒檔真正歸屬 | 收窄該票 `where.files` |
| 精確檔案層級的多票 tie | 真實衝突訊號（非噪音，不收斂） | 跑 `ticket track conflicts --among` 確認 |

呈現方向為 **file -> tickets**（PM 入場真正想知道的是「這個髒檔是誰的」，非「這張票碰了哪些髒檔」）；僅比對 `status == in_progress` 的票；歸屬採最長匹配前綴特異度（精確檔案相符 > 深層目錄相符 > 淺層目錄相符）。目錄型宣告的判定與展開規則見 `field-semantics.md`〈where.files 宣告語意〉。

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--top` | 5 | 可認領建議章節列數上限 |
| `--version` / `--format` | 同 `activity`/`conflicts` | 版本範圍與輸出格式 |
| `--all` | — | 見〈共用旗標語意（track 系列命令通用）〉 |

### 設計約束

- registry 讀取一律經 `.claude/lib/pm_registry` 的 `get_registry_paths` + `read_registry`
- stale 判定完全交由 `track_sessions._build_rows` 內部既有邏輯處理，本命令不重新定義任何 stale 閾值常數
- registry 缺檔/損毀時各節優雅降級（活同事顯示「（無活同事）」、孤兒 entry 顯示「（無孤兒 entry）」，餘二節同款樣式），不阻擋其餘三節輸出

---

## track hook-liveness 子命令

輸入 hook 檔路徑或名稱，查 `.claude/hook-logs/_liveness/*.jsonl` 回報該
hook 的觸發記錄（依 session 聚合筆數、最近一筆 ts、今日筆數），並明確印出
「以什麼名字查」——取代憑檔名慣例（去 `-hook` 後綴等）手組 grep。

### 用法

```bash
ticket track hook-liveness <hook 檔路徑或名稱> [--since <ISO 時間>] [--session <session_id>] [--format table|json]
```

### 0 筆結果的判讀

部分 hook 的 `HOOK_NAME` 常數帶 `-hook` 後綴，與其餘同類 hook 的命名慣例不一致；憑慣例猜測名稱查 liveness 記錄得到「0 筆」，此結果與「hook 未觸發」這個合法結論無法區分，會產生有據可查但錯誤的驗收記錄。本命令解析真實的 `HOOK_NAME`（存在檔案時），並在 0 筆時明確區分兩種原因：

| 情境 | 訊息 |
|------|------|
| 輸入為檔路徑，已解析出 `HOOK_NAME`，該名稱 0 筆 | 「名稱已解析為 X，X 無任何記錄（hook 可能確實未觸發）」 |
| 輸入為字面名稱（非解析自既有檔案），0 筆 | 「名稱為字面輸入，0 筆可能代表名稱輸入錯誤或 hook 確實未觸發」 |

### 名稱解析順序

1. 輸入為存在的檔案路徑（相對於 cwd 或相對於 git toplevel 皆可）→ 讀原始碼解析 `HOOK_NAME = "..."` 常數
2. 無 `HOOK_NAME` 常數 → 退回檔名去 `.py`（`Path(x).stem`）
3. 輸入非存在的檔案路徑 → 視為字面名稱直接使用

### Flag 說明

| Flag | 預設 | 說明 |
|------|------|------|
| `--since` | 無 | 只計入此 ISO 時間之後的記錄 |
| `--session` | 無 | 只掃描指定 `session_id` 的 liveness 檔案 |
| `--format` | `table` | `table`（PM 預設視圖）/ `json`（自動化消費） |

> 防護類 hook ticket 的「本 session 實地觸發確認」標準寫法（以本命令前後差值取代手動 grep 或憑印象判斷）已移至 `.claude/pm-rules/ticket-body-schema.md`「防護類 hook ticket 額外 acceptance」節，內容是 ticket 收尾時的驗收手段規範，不是本命令本身的用法。

---

## track register-artifact / resolve-artifact / list-artifacts 子命令

跨 session 實驗器材（sentinel/探針/對照組樣本，其存在本身即為觀測手段的檔案）的票面登記 CLI 化，取代規範原僅要求「登記三項但格式自由發揮」的手工條款。完整規範見 `.claude/pm-rules/parallel-dispatch.md`「跨 session 實驗器材的自我標示與存活期治理（強制）」。

```bash
ticket track register-artifact <id> --path <路徑> --purpose <用途> --expiry <存活期> [--type 明示|盲測]
ticket track list-artifacts <id> [--json]
ticket track resolve-artifact <id> EXP-N --status removed|kept [--successor <ticket-id>] [--reason <說明>]
```

`register-artifact` 自動編號（`EXP-N`）寫入 Solution 章節固定子章節，同時輸出可直接複製貼上的首行 header 文字（供落地條件一的檔案端標示）。`list-artifacts` 提供結構化讀回（含 `--json`），供收尾檢查程式化消費，不需人工掃描章節。`resolve-artifact` 標記存活期治理的收尾處置：`--status kept` 強制要求 `--successor`（CLI 層面阻止「未指名接手者」漏處置，非僅文件提醒）。

---
