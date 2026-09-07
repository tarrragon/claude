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
| `init` | 查重後建立全部區段 comment（如「當前結論」「問題與方案」「待辦與來源」），取得各 comment id 後回填一次 body 的區段索引表 | 首位建區段的 session（issue 本身可由他人建立） |
| `add` | 對已 `init` 過的 issue 建立單一區段 comment，在既有索引表追加一列（不存在索引表時建立），其他既有列不受影響 | 任何 session（成為該區段 owner） |
| `dedup` | 唯讀查重：與 `init` 內建查重共用同一機制，不建立任何 comment／issue，供 `init` 前單獨核對關鍵字涵蓋範圍 | 任何 session |
| `update` | 以 comment id 精準編輯指定區段內容，不影響同 issue 其他 comment | 該區段的 owner |
| `transfer-owner` | PATCH 指定區段 comment 首行標記的 owner 欄，內容不變 | 移交雙方協商後，任一方執行 |
| `observe` | 附加觀測 comment（實測、反證、疑慮），不需 owner、不需協商 | 任何 session，隨時 |
| `show` | 以 body 的區段索引為起點輸出，區分「當前結論區段」與「觀測流」 | 任何 session |
| `check` | 輸出三項警訊（見下）：當前結論時效、comment 數閾值、索引一致性 | 任何 session |

**`init` 兩階段順序**：comment id 在區段建立後才存在，索引無法在建立時一併寫入，故 `init` 必為「查重 → 建區段 comment → 取得 id → 回填一次 body 索引表」。body 其後不再由工具改寫，`update` 只動區段 comment。區段 comment 全數建立成功即把 `(issue number, owner, updated_at)` 落地到本地擁有登記檔 `.claude/state/framework-issue-owned.json`（per-worktree、不入版控），不等索引回填；回填失敗時登記仍成立，供 SessionStart 檢查省去搜尋往返。

**`add` 補上「`init` 只能跑一次」的缺口**：後續 session 要在同一 issue 新增區段時改用 `add`，流程為「POST 單一區段 comment → 讀 body → 合併既有索引列與新列 → PATCH 一次」，既有列的 comment id／連結不變；成功後同樣落地擁有登記檔。`init`／`add`／`transfer-owner` 三者共用同一 owner 格式驗證（見下方〈owner 識別格式〉），不合法一律 exit 3 並印格式說明。`add` 與 `init` 共用同一索引偵測機制（`<!-- section-index -->` 標記），body 已有手寫索引表（無此標記）時 `add` 同樣會多出第二張表，而非併入手寫表——此為既有 `init` 限制的延伸，非本次新增缺陷。

## CLI 語法

```bash
# init：--dedup-keywords 必填（可多值，每組可含空白，逐一加引號）
# --sections-file 為 JSON 陣列 [{"name": "區段名", "content": "內容"}, ...]
python3 .claude/skills/framework-issue/scripts/section_comment.py init <issue-ref> \
  --owner <session識別> \
  --sections-file <path/to/sections.json> \
  --dedup-keywords "關鍵字組一" "關鍵字組二"

# add：對已 init 過的 issue 追加單一區段，content-file 內容不含首行標記
python3 .claude/skills/framework-issue/scripts/section_comment.py add <issue-ref> \
  --owner <session識別> --name "<區段名>" --content-file <path/to/content.md>

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

兩種標記字首不同（`section:`／`observation:`），區段抽取正則只命中前者。`show` 依此區分：有 `section:` 標記者列入區段，其餘（含 `observation:` 標記與手寫的一般 comment）列入觀測流，摘要取自標記。

body 的區段索引表格式：

```markdown
## 區段索引

| 區段 | 永久連結 |
|------|---------|
| 當前結論（讀者入口） | https://github.com/<owner>/<repo>/issues/<N>#issuecomment-<id> |
| <其他區段名> | https://github.com/<owner>/<repo>/issues/<N>#issuecomment-<id> |

觀測 comment 不列入索引。
```

**owner 識別格式**：`<專案目錄 kebab-case>-<session 序號>`，如 `flutter-balance-77`。SessionStart 的擁有 issue 檢查在登記檔缺失時以專案目錄名推導前綴粗篩，`flutter_balance-pm` 這類形態會被漏檢。`init`／`add`／`transfer-owner` 三者在 CLI 層即以 `^[a-z0-9]+(-[a-z0-9]+)*-[0-9]+$` 驗證此格式，不合法（如代理人名稱 `framework-issue-curator`、含底線的 `flutter_balance-pm`）一律 exit 3。

## init 前查重：三種關係處置

`init` 的 `--dedup-keywords` 為必填（工具強制），CLI 在建立任何區段 comment 前先以每組關鍵字搜尋既有 issue（`--match title,body,comments`），把命中清單與回顯的關鍵字集合印於輸出。**命中不等於重複**：全文檢索涵蓋 comment 內文，互相引用的 issue 在每組關鍵字下會同時命中彼此（實測：`#79`／`#81`／`#82` 三張在五組關鍵字下每組皆同時命中），須逐一判定關係，不可自動判定：

| 關係 | 判定依據 | 處置 |
|------|---------|------|
| 重複 | 同一問題領域、同一層級 | 併入既有 issue，以區段或觀測附加，不建新 issue |
| 切分 | 同一領域、不同層級（如體系層對單一 skill 層） | 建新 issue，分工邊界寫入雙方各自「當前結論」末段（body 與索引不再改寫，互標不走 body） |
| 引用 | 僅提及，領域不同 | 單向指向即可，不需互標 |

判定時讀內容不看標題：刻意切分的兩張（如 `#79` 體系層與 `#82` 單一 skill 層）標題會相似，看標題會誤判為重複而去合併，把切分還原成一張大 issue。工具只列命中清單，關係一律由建立者標註，不阻擋 `init` 繼續執行。

**實作細節：多詞關鍵字組採 token 聯集**。`gh search issues` 對多詞查詢的 AND 語意要求詞彙落在同一欄位實例內（同一則 comment 或同一 body），詞彙分屬不同 comment 時單一查詢會漏判。CLI 把含空白的關鍵字組拆為單詞分別查詢後於本地聯集，代價是命中清單雜訊增加，換取避免漏判。查詢失敗略過的 token 數固定重述於報告末行。

## check 的三項警訊

| 警訊 | 判準 | 定位 |
|------|------|------|
| 當前結論時效（主警訊） | 「當前結論」區段的 `updated_at` 落後於最新觀測 comment 的 `created_at` 超過設定期間 | 資產與負債的分界在此，不在 open/close 狀態。輸出附落後期間內新增的觀測連結，這是 owner 得知有新觀測的唯一機械管道（GitHub 通知是帳號層，session 不繼承未讀狀態） |
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
| `init` 對無協定標記的舊 issue 不補 `fw-issue-schema` 標記 | 讀者無法從 body 得知該 issue 已採本協定 | 建立者於 sections 之外，以 `gh issue edit` 手動在 body 首行補標記（僅此一次） |
| 查重關鍵字集合會過期 | 失效無明確事件觸發，訊號弱於索引過期 | 不為它加 `check`；查重出現誤判時以此為第一個查證方向 |
