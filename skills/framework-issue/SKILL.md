---
name: framework-issue
description: "Creates and lists framework issues on the canonical framework repo (tarrragon/claude) via gh CLI. Use when tracking a framework-level problem, error-pattern canonical reference, provenance anchor, or cross-consumer fix across projects. Triggers include: framework issue, canonical issue, 跨 consumer 修復追蹤, 框架 issue, error-pattern canonical. Do NOT use for project-local docs/work-logs tickets (use the ticket skill instead)."
metadata:
  version: 1.4.0
---

# Framework Issue

於框架 canonical repo（`tarrragon/claude`）標準化建立與查詢 framework
issue。framework issue 三重用途：provenance 錨點、error-pattern canonical
去重 key、跨 consumer 修復追蹤。本 skill 僅包 `gh` CLI，所有不可用狀態優雅降級。

## Commands

| 命令 | 包裝 | 用途 |
|------|------|------|
| create | `gh issue create --repo tarrragon/claude` | 建立 framework issue |
| list | `gh issue list --repo tarrragon/claude` | 列出 / 去重查詢 framework issue |
| link | 寫本地 error-pattern 檔 | 把 canonical_issue stamp 進 error-pattern 分類資訊表格 |
| fix-status | `gh issue view/edit --repo tarrragon/claude` | 查 / 更新 issue body 內跨 consumer 修復矩陣（軸 C） |
| fix-version | `gh issue view/edit --repo tarrragon/claude` | 於 issue body 追加修復版本號註記（軸 D，供 close 前置檢查） |
| close | `gh issue close --repo tarrragon/claude` | 關閉 issue，前置檢查已有修復版本號註記 |

> 範圍：本 skill 含 create / list / link / fix-status / fix-version / close，六命令齊備。

## Usage

create：

```bash
python3 .claude/skills/framework-issue/scripts/create_issue.py \
  --title "標題" [--body "內文"] [--label bug] [--label canonical]
```

body 一律自動附加環境資訊區段 `<!-- env-info -->`（OS / Claude Code 版本 /
Python 版本），供跨環境排查徵狀差異；任一項收集失敗降級為 `unknown`，不阻擋
issue 建立。

list：

```bash
python3 .claude/skills/framework-issue/scripts/list_issues.py \
  [--state open|closed|all] [--label X] [--limit 30] [--search "關鍵字"]
```

建 issue 前先用 `list --search "<關鍵字>"` 查既有 canonical issue 避免重複。

link：

```bash
python3 .claude/skills/framework-issue/scripts/link_issue.py \
  <error-pattern-id-或路徑> <issue-ref>
# 例：link PC-020 tarrragon/claude#42
```

link 把 `| canonical_issue | <issue-ref> |` 寫入該 error-pattern 的
「## 分類資訊」表格（落點為表格列，非 YAML frontmatter，與既有結構一致）。
pattern 可傳 id（如 `PC-020`，於 `error-patterns/` 下遞迴解析 `<id>-*.md`）或
直接傳 `.md` 路徑。重複 link 為**更新既有列**而非新增重複列；找不到 pattern
或缺分類資訊表格時降級報錯（exit 3）不寫檔。link 寫的是本地檔，不真打
GitHub API；issue ref 由呼叫端先以 create / list 取得。

升格時機：error-pattern 升格為 canonical 後，先 `create` / 找到對應 framework
issue，再以 `link` 把 issue ref stamp 回 error-pattern 作 canonical 錨點。詳見
`.claude/methodologies/error-pattern-numbering-methodology.md`「canonical 升格機制」。

`<issue-ref>`（fix-status / fix-version / close 三命令共用）支援
`owner/repo#N`、`#N`、純數字 `N` 三種形態；`owner/repo` 前綴存在時須與框架
repo（`tarrragon/claude`）相符，否則明確報錯（exit 3）而非靜默改號——gh
CLI 位置參數僅接受純數字或 URL，`owner/repo#N` 會被 gh 拒絕（invalid issue
format），三命令內部先正規化為純數字再呼叫 gh。

fix-status（軸 C：跨 consumer 修復追蹤）：

```bash
# view：顯示哪些 consumer 修了該壞 change
python3 .claude/skills/framework-issue/scripts/fix_status.py <issue-ref>

# mark-fixed：把「本 consumer」標為 fixed 並回寫 issue body
python3 .claude/skills/framework-issue/scripts/fix_status.py <issue-ref> --mark-fixed
```

修復狀態 SSOT 為 framework issue body 內的標記區段
`<!-- fix-matrix -->...<!-- /fix-matrix -->`，內嵌 markdown 表格
`| consumer | status |`（flat-base 號無狀態無法追蹤，此為 framework issue
獨有價值）。read=`gh issue view --json body` 解析；write=更新區段後
`gh issue edit --body-file` 回寫；矩陣不存在時 `--mark-fixed` 自動初始化。

consumer 自我識別沿用 `.claude/error-patterns/_project-registry.yaml` + git
toplevel basename（同 error-pattern allocator 的 `identify_project_code`），
**不需也不接受手動傳 consumer 名**；basename 未登錄於 registry 時降級報錯
（防止靜默產生錯誤 consumer 前綴）。

fix-version（軸 D：修復版本號註記，供 close 前置檢查）：

```bash
python3 .claude/skills/framework-issue/scripts/fix_version.py <issue-ref> \
  --summary "徵狀摘要" [--version X.Y.Z] [--date YYYY-MM-DD]
```

版本號註記 SSOT 為 issue body 內的標記區段
`<!-- fix-versions -->...<!-- /fix-versions -->`，內嵌 markdown 表格
`| version | date | summary |`。`--version` 省略時讀取本地 `.claude/VERSION`
（即 sync-push 後已同步至框架 repo 的版本號）；`--date` 省略時為今日。同版本號
重複標記為**更新既有列**（覆蓋日期/摘要），不新增重複列。多筆版本號可累積於
同一 issue（一次修復對應一筆，close 後發現新徵狀仍可再追加，見下）。

close（包裝 `gh issue close`，前置檢查版本號註記存在）：

```bash
python3 .claude/skills/framework-issue/scripts/close_issue.py <issue-ref> \
  [--reason completed|"not planned"] [--comment "說明"]
```

close 前置檢查 issue body 是否已有 `fix-version` 寫入的非空版本號註記；缺少時
降級報錯（exit 3）提示先執行 `sync-push` 取得框架版本號並用 `fix-version`
註記，避免各專案各自關閉造成同步狀態不一致、其他 consumer 無版本可追溯。
close 後仍可再追加版本號：`fix-version` 對 body 的編輯不要求 issue 為 open
狀態，重開或直接編輯 body 皆可。

## Graceful Degradation

`scripts/gh_common.py` 的 `preflight()` 與 `run_gh()` 將下列狀態轉為清楚的
stderr 提示與 exit code `3`（`EXIT_DEGRADED`），不拋 traceback：

| 狀態 | 偵測 | 提示方向 |
|------|------|---------|
| gh 未安裝 | `shutil.which("gh")` 為 None | 安裝 GitHub CLI |
| gh 未登入 | `gh auth status` exit != 0 | 執行 `gh auth login` |
| 目標 repo Issues 停用 | gh stderr 含 disabled + issue | 於 repo Settings 啟用 Issues |
| gh 執行例外 | OSError / SubprocessError | 確認安裝完整與網路可用 |

exit code：`0` 成功、`3` 降級、其餘為 gh 原始錯誤碼經 `run_gh` 轉為 `3`。

## Examples

| 情境 | 動作 | 結果 |
|------|------|------|
| 建 canonical issue | `create --title "X" --label canonical` | 成功印 issue URL，exit 0 |
| 去重查詢 | `list --search "PC-V1-009"` | 列出符合 issue，exit 0 |
| gh 未登入 | 任一命令 | stderr 提示 `gh auth login`，exit 3 |
| 註記修復版本號 | `fix-version <ref> --summary "..."` | 版本號取自 `.claude/VERSION`，寫入 fix-versions 區段，exit 0 |
| 關閉但未註記版本號 | `close <ref>` | stderr 提示先執行 fix-version，exit 3 |

## Comment-as-Section 協作協定

上方 Commands / Usage 描述的六命令（create/list/link/fix-status/fix-version/
close）以 issue body 內的固定標記區段（`fix-matrix`／`fix-versions`）追蹤跨
consumer 修復狀態，適用於「一個壞 change、多個 consumer 各自修復」的場景。

**comment-as-section** 是另一套模型，適用於「問題的分析與方案 context 需要
跨專案共享，且內容會隨框架理解反覆更新」的場景——即 framework issue 的一般
協作寫法。兩套模型可在同一 issue 並存：fix-matrix／fix-versions 仍留在 body
固定區段，comment-as-section 額外把結構化內容搬到具備穩定 id 的 comment。採
用此協定的 issue，body 內含標記 `<!-- fw-issue-schema: comment-as-section
v1 -->`。

**核心動機**：GitHub comment 具穩定 id 且可經 API 精準編輯，故「結構化」與
「跨寫者無競爭」不互斥。body 是讀取－修改－寫回，多方同時更新會靜默覆蓋，因
此不作為協作載體，只保留問題陳述、協定說明與區段索引。

### 六個操作

實作於 `.claude/skills/framework-issue/scripts/section_comment.py`（唯一
CLI 入口，子命令對應下表）。

| 操作 | 用途 | 誰可執行 |
|------|------|---------|
| `init` | 查重後建立全部區段 comment（如「當前結論」「方案評估」「工作流定義」），取得各 comment id 後回填一次 body 的區段索引表 | 建立該 issue 的 session |
| `dedup` | 唯讀查重：與 `init` 內建的查重共用同一機制，但不建立任何 comment/issue，供 `init` 前單獨核對關鍵字涵蓋範圍 | 任何 session |
| `update` | 以 comment id 精準編輯指定區段內容，不影響同 issue 其他 comment | 該區段的 owner |
| `observe` | 附加觀測 comment（實測、反證、疑慮），不需 owner、不需協商 | 任何 session，隨時 |
| `show` | 以 body 的區段索引為起點輸出，區分「當前結論區段」與「觀測流」，讀者不需讀完全部 comment | 任何 session |
| `check` | 輸出三項警訊（見下）：comment 數閾值、當前結論時效、索引一致性 | 任何 session |

**`init` 兩階段順序**：comment id 在區段建立後才存在，索引無法在建立時一併
寫入，故 `init` 必為「查重 → 先建區段 comment → 取得 id → 回填一次 body
索引表」。body 其後不再由工具改寫，`update` 只動區段 comment。

### CLI 語法

```bash
# init：--dedup-keywords 必填（可多值，每組可含空白，逐一加引號）；
# --sections-file 為 JSON 陣列 [{"name": "區段名", "content": "內容"}, ...]
python3 .claude/skills/framework-issue/scripts/section_comment.py init <issue-ref> \
  --owner <session識別> \
  --sections-file <path/to/sections.json> \
  --dedup-keywords "關鍵字組一" "關鍵字組二"

# dedup：唯讀，不需 issue-ref（查整個框架 repo），僅列命中清單
python3 .claude/skills/framework-issue/scripts/section_comment.py dedup \
  --keywords "關鍵字組一" "關鍵字組二"

# update：以 comment id 精準 PATCH，content-file 內容不含首行標記（工具自動保留）
python3 .claude/skills/framework-issue/scripts/section_comment.py update <comment-id> \
  --content-file <path/to/content.md>

# observe：附加觀測 comment，不需 owner
python3 .claude/skills/framework-issue/scripts/section_comment.py observe <issue-ref> \
  --summary "觀測摘要" --session <session識別> --content-file <path/to/observation.md>

# show / check：唯讀，check 的兩項閾值可覆蓋預設值
python3 .claude/skills/framework-issue/scripts/section_comment.py show <issue-ref>
python3 .claude/skills/framework-issue/scripts/section_comment.py check <issue-ref> \
  [--comment-threshold 30] [--stale-days 7]
```

`<issue-ref>` 支援 `owner/repo#N`（限框架 repo）、`#N`、純數字三種形態。

### 區段與觀測標記格式

區段 comment 首行帶 HTML 註解標記，供定址與 owner 判定，GitHub 渲染時不
可見：

```
<!-- section: <名稱> owner: <session-或建立者識別> -->
## <名稱>

（區段內容）
```

觀測 comment 不需標記，為一般 comment，內容即觀測本身（實測結果、反證、疑
慮）。`show` 依有無區段標記區分兩者：有標記者列入「當前結論區段」／其他具名
區段，無標記者列入「觀測流」。

body 的區段索引表格式：

```markdown
## 區段索引

| 區段 | 永久連結 |
|------|---------|
| 當前結論（讀者入口） | https://github.com/<owner>/<repo>/issues/<N>#issuecomment-<id> |
| <其他區段名> | https://github.com/<owner>/<repo>/issues/<N>#issuecomment-<id> |

觀測 comment 不列入索引。
```

### init 前查重：三種關係處置

`init` 的 `--dedup-keywords` 為必填參數（工具強制，非僅文件建議），CLI 會
在建立任何區段 comment 前先以每組關鍵字搜尋既有 issue（`--match
title,body,comments`，標題與 comment 內文皆涵蓋），並把命中清單與回顯的關
鍵字集合印於 `init` 輸出。**命中不等於重複**：全文檢索涵蓋 comment 內文，
互相引用的 issue 在每組關鍵字下會同時命中彼此，須逐一判定關係，不可自動判
定重複：

| 關係 | 判定依據 | 處置 |
|------|---------|------|
| 重複 | 同一問題領域、同一層級 | 併入既有 issue，以區段或觀測附加，不建新 issue |
| 切分 | 同一領域、不同層級（如體系層對單一 skill 層） | 建新 issue，雙方 body 互標分工（各自的區段索引附一行指向對方） |
| 引用 | 僅提及，領域不同 | 單向指向即可，不需互標 |

工具只列命中清單，關係一律由建立者標註，不自動判定、不阻擋 `init` 繼續執
行（命中清單僅供人工審閱後自行決定是否中止）。單獨核對關鍵字涵蓋範圍（不
建立 issue）時用 `dedup` 子命令，與 `init` 內建查重共用同一邏輯。

**實作細節：多詞關鍵字組採 token 聯集，非單一 AND 查詢**——`gh search
issues` 對多詞查詢的 AND 語意要求詞彙落在同一欄位實例內（同一則 comment
或同一 body），詞彙分屬同一 issue 的不同 comment 時單一查詢會漏判（實測：
`#79`／`#81`／`#82` 已知集合以「skill 拆分」單一查詢會漏掉 `#79`，因兩詞
分屬 `#79` 的不同 comment）。CLI 因此把含空白的關鍵字組拆為單詞分別查詢後
於本地聯集，代價是命中清單雜訊增加（單詞查詢範圍較寬），換取避免漏判。

### check 的三項警訊

| 警訊 | 判準 | 定位 |
|------|------|------|
| 當前結論時效（主警訊） | 「當前結論」區段的 `updated_at` 落後於最新觀測 comment 的 `created_at` 超過設定期間 | 資產與負債的分界在此，不在 issue 的 open/close 狀態 |
| comment 數閾值（輔助） | 單張 issue 的 comment 總數超過設定閾值 | 與主警訊合看，comment 數本身不代表失效 |
| 索引一致性 | body 區段索引列出的 comment id，與實際存在的區段 comment（依標記抽取）不一致 | 索引在區段 comment 增刪後不會自動跟上，屬第三種「內容存在但指向錯誤」的來源 |

「同一問題領域出現第二張 issue」不是 `check` 的輸出項，其檢查點在 `init`
之前（見上方查重章節），因為此類失效一旦發生，兩張 issue 各自的 `check` 都
看不出彼此的存在。

### 增長語意與 close 語意

**open issue 數增長不是失效訊號。** ticket 與 issue 的計數單位不同：ticket
一張對應一個不可逆的執行單位，issue 一張對應一個可逆的問題領域。框架隨理解
持續演進，同一領域的認識會反覆更新，issue 長期 open 代表該領域仍在活動，其
comment 累積是資產而非負債。

**close 語意**：代表「當前結論」暫時穩定、無進行中工作，不代表問題已被最終
解決；框架後續演進時可直接 reopen 同一張 issue 繼續累積，不需另開新張。讀者
看到 issue 為 closed 不應推論其內容已過期——過期與否由 `check` 的當前結論時
效警訊判斷，與 open/close 狀態無關。

> 舊命令集的 `close`（fix-matrix 模型）另有獨立的版本號前置檢查（見上方
> Usage 章節），與本節的 close 語意屬不同機制層次，互不影響：前者檢查「有無
> 版本號可追溯」，後者定義「close 這個動作在協定裡代表什麼」。

## 框架問題升級流程

處理 ticket 過程中，若問題本質屬於 Claude 框架而非本專案，正確路徑是提
framework issue，而非在本地當下修復。本節定義四個環節：介入判斷、兩條後續
路徑、issue 關閉協議、回報前查重 SOP。

### 1. 介入判斷：框架問題 vs 專案問題

**判準**（同時符合視為框架問題）：

| 判準 | 說明 |
|------|------|
| 抽象可攜性 | 敘述替換掉本專案名稱與檔案路徑後依然成立（例如「Hook X 對某類副檔名誤判」而非「<專案名> 的 Y 檔案有 bug」） |
| 資產範圍 | 問題根源在 `.claude/` 下的通用資產（hooks / skills / rules / methodologies / agents），非 `lib/`、`docs/` 等專案專屬產物 |

**Why**：框架資產由 sync-push / sync-pull 在多個 consumer 專案間共享，本地
直接修復只解決當前專案的徵狀，其他消費該框架的專案仍帶著同一個缺陷；把框架層
的因誤判當專案層問題修，修法會貼著單一 consumer 的特例，日後 sync-pull 覆蓋
時風險復發。

**Consequence**：略過此判斷、直接在當下 ticket 內修 `.claude/` 通用資產，會
使該修復困在本地 commit 歷史中不會傳播；下次 `sync-pull` 甚至可能用上游未修
的舊版覆蓋掉本地修復，問題復發且沒有 canonical 記錄可查。

**Action**：識別為框架問題時，執行本 skill 的 `create` 建立 issue（見下方兩
條路徑擇一銜接），不在當前 ticket 直接編輯 `.claude/` 檔案了事。

### 2. 兩條路徑

判定為框架問題後，依當下處理能量選擇：

| 路徑 | 適用情境 | 動作 |
|------|---------|------|
| A：延後接手 | 當下 ticket 的主要目標不是修這個框架問題（順手發現） | 建立 framework issue 記錄徵狀；本地相關 ticket 若因此阻塞則 close（或標記 blocked 說明原因），待未來 `sync-pull` 帶回上游修復後，另開新 ticket 銜接驗證 |
| B：當下接手 | 框架問題本身就是當前任務目標，或不修復無法繼續 | 直接在框架 canonical repo（`tarrragon/claude`）修復，修復後走下方「issue 關閉協議」完整流程 |

**Why**：框架問題的修復地點是 canonical repo，不是本地專案；本地 ticket 若卡
在框架層缺陷上又不切割，會讓專案層任務的驗收標準綁死在框架修復進度上。

**Consequence**：路徑 A 若省略「close 本地 ticket」直接放著不管，會違反
`quality-baseline.md` 規則 5（發現必須追蹤）與決策 trigger 綁定規則（無
trigger 延後）；正確做法是用「等 sync-pull 帶回修復後另開 ticket」作為明確
trigger，不是無 trigger 的「以後再說」。

**Action**：選路徑 A 時，本地 ticket 標記 `blockedBy` 或直接 close 並在
Completion Info 註明「等框架 issue #N 修復後由新 ticket 銜接」；選路徑 B
時，修復完成後立即執行下方「issue 關閉協議」。

### 3. Issue 關閉協議

修復完成到正式 close 之間，必須依序完成版本號回註，讓其他 consumer 能追溯此
修復落在框架的哪個版本：

```
修復完成 → sync-push（取得框架版本號）→ fix-version 回註 issue → close
```

| 步驟 | 命令 | 說明 |
|------|------|------|
| 1. 推送修復 | `/sync-push`（或 `python3 ./.claude/scripts/sync-claude-push.py`） | 修復內容推送至框架 repo 後，本地 `.claude/VERSION` 即為此次推送後的框架版本號 |
| 2. 版本號回註 | `python3 .claude/skills/framework-issue/scripts/fix_version.py <issue-ref> --summary "徵狀摘要"` | `--version` 省略時自動讀本地 `.claude/VERSION`；寫入 issue body 的 `fix-versions` 表格 |
| 3. 關閉 issue | `python3 .claude/skills/framework-issue/scripts/close_issue.py <issue-ref> [--reason completed]` | `close` 前置檢查 fix-versions 表格非空，缺少版本號註記會 exit 3 拒關 |

close 後若在其他情境發現同一 issue 的新徵狀，不需重開新 issue：直接對同一
issue 再跑一次「修復 → sync-push → fix-version」即可，`fix-version` 對 body
的編輯不要求 issue 為 open 狀態，版本號表格可累積多筆記錄。

**Why**：`close` 的版本號前置檢查是防止「各專案各自關閉造成同步狀態不一致」
的機械閘門——沒有版本號，其他 consumer 無從得知這個 issue 對應框架的哪次同步。

**Consequence**：跳過 `fix-version` 直接嘗試 `close` 會被 exit 3 拒絕；若繞
過閘門手動在 GitHub 網頁關閉 issue，其他 consumer 執行「回報前查重 SOP」時
會誤判此 issue 已有版本可追溯，實際查無版本號，需重新排查徵狀。

**Action**：接手框架問題修復（路徑 B）或發現舊 issue 新徵狀時，一律走
「sync-push 取版本號 → fix-version 回註 → close」順序，不省略任一步。

### 4. 回報前查重 SOP

準備建立新 framework issue 前，先查既有 issue 避免重複記錄同一問題：

```bash
python3 .claude/skills/framework-issue/scripts/list_issues.py --search "<關鍵字>"
```

| 查詢結果 | 判讀 | 動作 |
|---------|------|------|
| 命中 issue，狀態 closed 且已有 fix-versions 版本號 | 該問題可能已在框架修復，只是本專案尚未同步 | 執行 `/sync-pull` 拉取該版本後的修復，驗證徵狀是否消失；若仍存在，視為新徵狀對同一 issue 追加 `fix-version`（見上方「close 後追加」） |
| 命中 issue，狀態 open，或查無版本號 | 問題已被記錄但尚未修復，或修復未完整回註 | 帶著既有 issue 的脈絡（既有描述、已知環境資訊）接續排查，不重新從零開始；判斷是全新獨立問題才建新 issue |
| 查無任何命中 | 尚未有人記錄 | 依「介入判斷」與「兩條路徑」建立新 issue |

**Why**：`list --search` 是既有命令，成本遠低於重複建立 issue 後才發現重
複；Usage 章節已提醒「建 issue 前先用 list --search 查既有 canonical
issue」，本節把查重結果的三種判讀路徑具體化。

**Consequence**：略過查重直接建立新 issue，會讓同一徵狀在框架 repo 產生多筆
重複記錄，稀釋 canonical 追蹤的價值，也讓查重 SOP 原本要避免的重複工作實際
發生。

**Action**：建立新 issue 前必先查重；依查詢結果落入的判讀分支決定
「sync-pull 驗證」「接續既有脈絡」或「新建 issue」三選一。

## Testing

```bash
uv run --project .claude/hooks pytest \
  .claude/skills/framework-issue/tests/ -v
```

測試以 mock 攔截 gh subprocess，不真打 GitHub API；涵蓋正常路徑與三種降級路徑。

---

版本紀錄在同目錄的 `CHANGELOG.md`。
