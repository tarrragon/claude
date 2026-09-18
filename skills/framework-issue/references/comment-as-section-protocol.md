# Comment-as-Section 協作協定

framework issue 的一般協作寫法。適用於「問題的分析與方案 context 需要跨專案共享，且內容會隨框架理解反覆更新」的場景。與 fix-matrix 模型可在同一 issue 並存：fix-matrix／fix-versions 留在 body 固定區段，本協定把結構化內容放到具穩定 id 的 comment。採用本協定的 issue，body 含標記 `<!-- fw-issue-schema: comment-as-section v1 -->`。

**核心動機**：GitHub comment 具穩定 id 且可經 API 精準編輯，「結構化」與「跨寫者無競爭」因此不互斥。body 是讀取－修改－寫回，多方同時更新會靜默覆蓋，故不作協作載體，只保留問題陳述、協定說明與區段索引。

- [操作一覽](#操作一覽)
- [CLI 語法](#cli-語法)
- [區段與觀測標記格式](#區段與觀測標記格式)
- [init 前查重：三種關係處置](#init-前查重三種關係處置)
- [check 的三項警訊](#check-的三項警訊)
- [增長語意與 close 語意](#增長語意與-close-語意)
- [已知限制](#已知限制)

## 操作一覽

實作於 `scripts/section_comment.py`（唯一 CLI 入口，子命令對應下表）。

| 操作 | 用途 | 誰可執行 |
|------|------|---------|
| `init` | 查重後建立全部區段 comment（如「當前結論」「問題與方案」「待辦與來源」），取得各 comment id 後與既有索引列合併回填一次 body 的區段索引表；issue 已有任何區段 comment 時預設拒絕（exit 3，提示改用 `add`），`--force` 可略過此檢查 | 首位建區段的 session（issue 本身可由他人建立） |
| `add` | 對已 `init` 過的 issue 建立單一區段 comment，在既有索引表追加一列（不存在索引表時建立），其他既有列不受影響 | 任何 session（成為該區段 owner） |
| `dedup` | 唯讀查重：與 `init` 內建查重共用同一機制，不建立任何 comment／issue，供 `init` 前單獨核對關鍵字涵蓋範圍 | 任何 session |
| `update` | 以 comment id 精準編輯指定區段內容，不影響同 issue 其他 comment | 該區段的 owner |
| `transfer-owner` | PATCH 指定區段 comment 首行標記的 owner 欄，內容不變 | 移交雙方協商後，任一方執行 |
| `observe` | 附加觀測 comment（實測、反證、疑慮），不需 owner、不需協商 | 任何 session，隨時 |
| `show` | 以 body 的區段索引為起點輸出，區分「當前結論區段」與「觀測流」；每則區段列附 owner（從首行標記回推） | 任何 session |
| `check` | 輸出三項警訊（見下）：當前結論時效、comment 數閾值、索引一致性 | 任何 session |
| `todo` | 唯讀：跨 open issue 聚合全部「待辦與來源*」區段的表格列（見下方〈待辦表欄位與列舉〉），預設掃本 consumer 擁有的 open issue，`--all`／`--issue N` 可改變範圍；支援 `--status`／`--stage`／`--priority`／`--consumer` 篩選與 `--json` | 任何 session |

**`init` 兩階段順序**：comment id 在區段建立後才存在，索引無法在建立時一併寫入，故 `init` 必為「查重 → （無 `--force` 時先掃描既有區段 comment，已有則拒絕）→ 建區段 comment → 取得 id → 讀 body 與既有索引列合併 → PATCH 一次」。body 其後不再由工具改寫，`update` 只動區段 comment。區段 comment 全數建立成功即把 `(issue number, owner, updated_at)` 落地到本地擁有登記檔 `.claude/state/framework-issue-owned.json`（per-worktree、不入版控），不等索引回填；回填失敗時登記仍成立，供 SessionStart 檢查省去搜尋往返。`init` 原本以本次區段清單整段覆寫索引，第二個 session 對已 `init` 過的 issue 再次執行會使第一個 session 的既有區段從 `show` 消失（見 #81 事故）；現改為與既有索引列合併，且預設拒絕已有區段的 issue（避免誤用），`--force` 才會略過拒絕檢查並執行合併。

**`add` 補上「`init` 預設每張 issue 只能跑一次」的缺口**：後續 session 要在同一 issue 新增區段時仍建議用 `add`（不需重新查重），流程為「POST 單一區段 comment → 讀 body → 合併既有索引列與新列 → PATCH 一次」，既有列的 comment id／連結不變；成功後同樣落地擁有登記檔。`init`／`add` 共用同一 owner 格式驗證（見下方〈owner 識別格式〉），`transfer-owner` 另有獨立的跨 consumer 逃生口驗證，不合法一律 exit 3 並印格式說明。`add`／`init` 合併索引列時皆以 comment id 去重，並把 body 內未加 `<!-- section-index -->` 標記的手寫索引表視為既有列來源（讀 `parse_index_table` 結果）整段移除後併入合併結果，不再於其後追加第二張表。`add` 成功時比照 `transfer-owner` 逐字印出結果（`區段「<名稱>」已建立 @ <issue-ref>，owner=<值>`），操作者不需另開 comment 即可確認建立結果。

## CLI 語法

```bash
# init：--dedup-keywords 必填（可多值，每組可含空白，逐一加引號）
# --sections-file 為 JSON 陣列 [{"name": "區段名", "content": "內容"}, ...]
# issue 已有區段 comment 時預設拒絕（exit 3）；--force 略過拒絕檢查並與既有索引列合併
# owner 預設自行推導，不需指定；--owner 僅供覆寫確認，給值須與推導值相符
python3 .claude/skills/framework-issue/scripts/section_comment.py init <issue-ref> \
  --sections-file <path/to/sections.json> \
  --dedup-keywords "關鍵字組一" "關鍵字組二" \
  [--force] [--owner <推導值，僅供覆寫確認>]

# add：對已 init 過的 issue 追加單一區段，content-file 內容不含首行標記
# owner 預設自行推導，不需指定；--owner 僅供覆寫確認，給值須與推導值相符
python3 .claude/skills/framework-issue/scripts/section_comment.py add <issue-ref> \
  --name "<區段名>" --content-file <path/to/content.md> [--owner <推導值，僅供覆寫確認>]

# dedup：唯讀，不需 issue-ref（查整個框架 repo），僅列命中清單
python3 .claude/skills/framework-issue/scripts/section_comment.py dedup \
  --keywords "關鍵字組一" "關鍵字組二"

# update：以 comment id 精準 PATCH，content-file 內容不含首行標記（工具自動保留）
python3 .claude/skills/framework-issue/scripts/section_comment.py update <comment-id> \
  --content-file <path/to/content.md>

# transfer-owner：PATCH 首行標記的 owner 欄，內容不變
python3 .claude/skills/framework-issue/scripts/section_comment.py transfer-owner <comment-id> \
  --to <新 session 識別>

# observe：附加觀測 comment，不需 owner
python3 .claude/skills/framework-issue/scripts/section_comment.py observe <issue-ref> \
  --summary "觀測摘要" --session <session識別> --content-file <path/to/observation.md>

# show / check：唯讀，check 的兩項閾值可覆蓋預設值
python3 .claude/skills/framework-issue/scripts/section_comment.py show <issue-ref>
python3 .claude/skills/framework-issue/scripts/section_comment.py check <issue-ref> \
  [--comment-threshold 30] [--stale-days 7]

# todo：唯讀，跨 issue 聚合「待辦與來源*」表格列；範圍三選一（預設本 consumer
# 擁有的 open issue，缺登記檔時退回 owner 前綴推導），--all／--issue 互斥
python3 .claude/skills/framework-issue/scripts/section_comment.py todo \
  [--all | --issue <N>] \
  [--status <狀態值>] [--stage <階段值>] [--priority <優先級值>] \
  [--consumer <consumer前綴>] [--json]
```

`<issue-ref>` 支援 `owner/repo#N`（限框架 repo，前綴不符即 exit 3）、`#N`、純數字三種形態；gh CLI 位置參數只吃純數字或 URL，工具內部先正規化。

## 區段與觀測標記格式

區段 comment 首行帶 HTML 註解標記，供定址與 owner 判定，GitHub 渲染時不可見：

```
<!-- section: <名稱> owner: <session識別> -->
## <名稱>

（區段內容）
```

觀測 comment 由 `observe` 自動寫入首行標記，`--summary` 與 `--session` 落在此處，內容從第二行起：

```
<!-- observation: <摘要> by <session識別> -->
（觀測內容）
```

兩種標記字首不同（`section:`／`observation:`），區段抽取正則只命中前者。`show` 依此區分：有 `section:` 標記者列入區段，其餘（含 `observation:` 標記與手寫的一般 comment）列入觀測流，摘要取自標記。每則區段列輸出格式為 `- <名稱> owner=<值> updated_at=<值>`，owner 從該 comment 首行標記回推——`transfer-owner` 是唯一會改 owner 的操作，若 `show` 不印 owner，驗證移交結果需另外開 comment 核對，驗證手段不在同一套 CLI 內。

body 的區段索引表格式：

```markdown
## 區段索引

| 區段 | 永久連結 |
|------|---------|
| 當前結論（讀者入口） | https://github.com/<owner>/<repo>/issues/<N>#issuecomment-<id> |
| <其他區段名> | https://github.com/<owner>/<repo>/issues/<N>#issuecomment-<id> |

觀測 comment 不列入索引。
```

標題與表頭之間可放一段導言（入口宣稱、索引重生指令等）。`init`／`add` 每次重渲染索引時會回讀該導言並寫回原位置——導言若不回讀，`upsert_section` 的整段替換會在下一次執行時把它靜默抹除。issue 原本是無工具標記的手寫索引（標題＋導言＋表格）時，三者整塊處理：列併入工具索引、導言遷至標題與表頭之間、原處的標題與導言一併移除，body 內因此只留一份標題與一張表（`tarrragon/claude#82` 曾出現兩個標題而第一個底下沒有表格，即此處未整塊處理的後果）。

**owner 識別格式**：`init`／`add` 現預設自行推導 owner，格式為
`<本專案 kebab-case 推導前綴>-<session uuid 前 8 碼十六進位>`（占位形態，
不寫任何具體 consumer 的字面值）；前綴取本專案主 repo 目錄名 kebab 化
（同 `_project_owner_prefix()` 邏輯），尾碼取本 session
`CLAUDE_CODE_SESSION_ID` 環境變數前 8 碼十六進位，不自行編號、不用代理
人名。`--owner` 降為覆寫確認用途——省略不填即自動組出正確值，給值時須
與推導值完全相符，不符一律 exit 3 並印診斷（推導值／傳入值／不符欄
位）；推導失敗（`CLAUDE_CODE_SESSION_ID` 環境變數缺席）時同樣 exit 3
並印三項診斷（環境變數是否存在、推導出的前綴、該 uuid 是否在
`pm-registry.json` 中），無任何靜默降級路徑——此為刻意設計：先前允許
以純格式檢查通過任意傳入值的降級路徑，正是派發者需代填 owner 而導致
漏填的根源，本版本消滅此路徑，改由 CLI 承擔取值責任。尾碼段記錄的是
「哪一次 session 寫的」，不是「現在該找誰」：session 結束後該識別不再
可定址，擁有關係實質屬於專案（前綴段），有事以 `observe` 留在 issue
上，不以訊息找 owner。SessionStart 的擁有 issue 檢查在登記檔缺失時以
專案目錄名推導前綴粗篩，`flutter_balance-pm` 這類形態會被漏檢。
`transfer-owner` 為跨 consumer 移交的逃生口，不受本次改動影響，仍走
獨立的 `validate_owner_for_transfer`，不錨定本專案前綴、不依賴 session
id 推導，僅檢查通用形狀。

### 待辦表欄位與列舉

區段名以「待辦與來源」開頭者（`ticket-intake.md` 的「待辦與來源（<consumer>）」慣例），內容首張 markdown 表格受 `init`／`add`／`update` 寫入端驗證；`todo` 則以同一 schema 讀取聚合。缺必要欄位或「狀態」「階段」列舉值不合法，寫入端 exit 3 並印合法值集合與違規列；`todo` 對表頭不符的區段只印警告並跳過，不中止其餘聚合。

必要欄位（缺任一即 exit 3）：`來源票`、`做什麼`、`acceptance 條數`、`優先級`、`階段`、`狀態`。`型別` 為選填欄，存在時須緊接在 `來源票` 之後（非附加於表尾），此為既有 issue 實跑觀測到的欄位順序，非任意排列皆合法：

```markdown
| 來源票 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |
|--------|--------|----------------|--------|------|------|
| <ticket-id> | <一句話描述> | <整數> | P0~P3 | 本版 | 待裁票 |
```

或帶選填 `型別` 欄：

```markdown
| 來源票 | 型別 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |
|--------|------|--------|----------------|--------|------|------|
| <ticket-id> | IMP | <一句話描述> | <整數> | P0~P3 | 本版 | 待裁票 |
```

「狀態」列舉（5 值）：`待裁票`、`已裁票`、`進行中`、`完成`、`不執行`。

「階段」列舉（4 值）：`可立即執行`、`本版`、`下版`、`待條件`。

兩組列舉為寫入端起生效日的權威值，不追溯驗證既有 comment 內容——唯讀掃描曾實測既有表格「狀態」欄逾 12 種自由文字、「階段」欄逾 8 種，`todo` 的結構檢查（僅比對表頭）仍可正常聚合這些既有列，篩選旗標（`--status`／`--stage`）對這些舊值只是查無結果，不會出錯。

## init 前查重：三種關係處置

`init` 的 `--dedup-keywords` 為必填（工具強制），CLI 在建立任何區段 comment 前先以每組關鍵字搜尋既有 issue（`--match title,body,comments`），把命中清單與回顯的關鍵字集合印於輸出。**命中不等於重複**：全文檢索涵蓋 comment 內文，互相引用的 issue 在每組關鍵字下會同時命中彼此（實測：`#79`／`#81`／`#82` 三張在五組關鍵字下每組皆同時命中），須逐一判定關係，不可自動判定：

| 關係 | 判定依據 | 處置 |
|------|---------|------|
| 重複，射程不重疊 | 同一問題領域、同一層級，但與既有「當前結論*」區段涵蓋的主題不同 | `add --owner <本方識別>` 帶命名後綴（見 `ticket-intake.md`〈以 add 加進他方已 init 的 issue 時〉），成為新區段 owner，不建新 issue |
| 重複，射程重疊 | 同一問題領域、同一層級，且與既有「當前結論*」區段處理同一主題 | `observe`，觀測首行指名重疊的既有區段名稱；不建新 issue |
| 切分 | 同一領域、不同層級（如體系層對單一 skill 層） | 建新 issue，分工邊界寫入雙方各自「當前結論」末段（body 與索引不再改寫，互標不走 body） |
| 引用 | 僅提及，領域不同 | 單向指向即可，不需互標 |

**射程是否重疊由讀者在 `show` 輸出上直接判定**：比對本方要落的結論與既有「當前結論*」區段各自的主題（後綴或內容），非機械可驗——工具不檢查名稱重複（見下方〈已知限制〉），關係判定者需自行核對。**覆寫條款（優先於上表）**：主題已被同機器活躍的他方 session 認領時，一律只 `observe`，不受本表「重複」判定影響（見 `ticket-intake.md`〈前提與分工〉2：對方認領的主題本方只加 `observe`，不 init、不 close 對方列出的票）。

判定時讀內容不看標題：刻意切分的兩張（如 `#79` 體系層與 `#82` 單一 skill 層）標題會相似，看標題會誤判為重複而去合併，把切分還原成一張大 issue。工具只列命中清單，關係一律由建立者標註，不阻擋 `init` 繼續執行。

**實作細節：多詞關鍵字組採 token 聯集**。`gh search issues` 對多詞查詢的 AND 語意要求詞彙落在同一欄位實例內（同一則 comment 或同一 body），詞彙分屬不同 comment 時單一查詢會漏判。CLI 把含空白的關鍵字組拆為單詞分別查詢後於本地聯集，代價是命中清單雜訊增加，換取避免漏判。查詢失敗略過的 token 數固定重述於報告末行。

**命中詞與命中位置**：每筆命中另標示「命中詞」（哪些 token 命中此 issue）與「命中位置」（title／body／comments 任一子集，title／body 為本地子字串比對，comments 為對該 issue 全部 comment 本地比對），並依命中 token 數遞減排序——命中多個 token 的 issue 較可能是真實重複，優先排在報告前段，協助從大量雜訊命中中快速排除只命中單一 token 者。此為近似判定，非精確重現 GitHub 全文檢索的分詞語意。

## check 的三項警訊

| 警訊 | 判準 | 定位 |
|------|------|------|
| 當前結論時效（主警訊） | 名稱以「當前結論」開頭的**全部**區段（含 `add` 附加的後綴區段，如「當前結論（unipos：規則 8）」），各自的 `updated_at` 落後於最新觀測 comment 的 `created_at` 超過設定期間 | 資產與負債的分界在此，不在 open/close 狀態。逐則輸出並標明 owner，附落後期間內新增的觀測連結，這是 owner 得知有新觀測的唯一機械管道（GitHub 通知是帳號層，session 不繼承未讀狀態）。多 owner 定位改採前綴比對後，第二 owner 的後綴區段不再缺此涵蓋 |
| comment 數閾值（輔助） | 單張 issue 的 comment 總數超過設定閾值 | 與主警訊合看，comment 數本身不代表失效 |
| 索引一致性 | body 區段索引列出的 comment id，與實際存在的區段 comment 不一致 | 索引在區段 comment 增刪後不會自動跟上 |

「同一問題領域出現第二張 issue」不是 `check` 的輸出項，其檢查點在 `init` 之前：此類失效一旦發生，兩張 issue 各自的 `check` 都看不出彼此的存在。

`check` 由 SessionStart hook 對本 session 擁有區段的 issue 自動執行；擁有關係讀本地登記檔，登記檔缺失時退回目錄名前綴推導。

## 增長語意與 close 語意

**open issue 數增長不是失效訊號**。ticket 一張對應一個不可逆的執行單位，issue 一張對應一個可逆的問題領域。同一領域的認識會反覆更新，issue 長期 open 代表該領域仍在活動，comment 累積是資產。

**close 語意**：代表「當前結論」暫時穩定、無進行中工作，不代表問題已被最終解決；框架後續演進時直接 reopen 同一張，不另開新張。讀者看到 closed 不應推論內容過期，過期與否由 `check` 的主警訊判斷。

fix-matrix 模型的 `close` 另有版本號前置檢查，屬不同機制層次：前者檢查「有無版本號可追溯」，本節定義「close 這個動作在協定裡代表什麼」。

## 已知限制

| 限制 | 影響 | 現行處置 |
|------|------|---------|
| 查重關鍵字集合會過期 | 失效無明確事件觸發，訊號弱於索引過期 | 不為它加 `check`；查重出現誤判時以此為第一個查證方向 |
| `init --force`／`add` 合併索引時不檢查區段名稱是否與既有列重複 | 同名區段各自成一列（id 不同），索引表本身無法從名稱區分 | 沿用既有命名後綴慣例（見 `ticket-intake.md`〈以 add 加進他方已 init 的 issue 時〉——該小節位於 `ticket-intake.md`，非本檔），不在工具層強制唯一性 |
