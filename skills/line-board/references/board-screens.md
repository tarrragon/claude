# line-board 畫面規格與資料來源

本檔是 `SKILL.md` 的依據：看板各區塊的資料來源、版面、狀態判定與讀取約定。調整看板或看板顯示異常時查閱。啟用、關閉與設定檔見 `SKILL.md`。

版面以線分組：最上方是「用戶待辦」群組，其下每條線一個可折疊群組，底部是「各 session」與「合併閘門最近紀錄」兩個同樣可折疊的區塊（見〈版面：以線分組的可折疊群組〉）。

| 內容 | 資料來源（相對 repo root，另註明者除外） |
|------|---------------------------|
| 用戶待辦 | 協調票 Solution 段的用戶待辦行與完成行（U1），加上各線等用戶（U2，判定同 `line_status` 的等用戶段）；格式權威是 multi-session-orchestration 的 `references/line-continuity.md` §2〈用戶待辦〉，見〈版面〉 |
| 線與佇列 | 協調票（專案設定檔的 `coordinationTicket`）的 Solution 段落（自 `## Solution` 起到下一個 `## ` 標題前）中的現行佇列行，每條線一個群組，依線號排序；線目標顯示在群組標題的第二行 |
| 佇列票即時狀態 | 群組內佇列列的每個票號旁標 `〔status〕`，`→`（依序）與 `∥`（並行）原樣保留，票號後的註記接在狀態後；狀態只讀主 checkout（`git worktree list` 第一筆）的票檔 frontmatter，讀不到時標 `unknown`。不讀各 worktree 的票檔：ticket CLI 在 worktree 中也把票務寫回主 repo，worktree 內的票檔是分支開出當下的舊副本 |
| 佇列票摘要 | 佇列細節（見〈版面〉）列出的 title，與狀態同一次讀取主 checkout 票檔 frontmatter 的 `title:`；讀不到時標 `（讀不到 title）` |
| 派發中代理人 | 主 checkout 的 `.claude/dispatch-active.json` 的 `dispatches` 陣列，列在所屬線的群組內，見〈派發中代理人〉 |
| 各 session | `~/.claude/sessions/*.json`（家目錄取自 `HOME`），見下節 |
| 合併閘門 | `.claude/logs/worktree-merge.log` 中 `[合併閘門] 開始` 與 `[合併閘門] 結束` 行的最後 8 行，精簡為欄位顯示（見下節）；預檢、合併前驗收、合併前測試等其他行不顯示 |
| 更新時間 | 每 30 秒重讀一次，Pane 頂端顯示最近一次讀取的本機時間 |

## 版面：以線分組的可折疊群組

每個群組（用戶待辦、線群組、其他、各 session、合併閘門）畫在一個圓角框線（`borderStyle="round"`）的 Box 內，框線左右共占 2 欄。框內先是標題，標題的第一行（標題列）是一個按鍵，按下（Pane 取得焦點後以 Enter 或點擊）即切換展開與收合；收合時框內只有標題，展開時標題之後接內容，內容縮排 2 欄。標題列一律為主題鍵 `suggestion` 色的粗體，與內容各行的狀態色區分；主題鍵的實際顏色隨 Claude Code 主題變化（深色主題為淺藍、淺色主題為較深的藍），不用 ANSI 藍是因為它在黑底終端機上不明顯。

- **用戶待辦**：畫在更新時間之下、所有提示行與線群組之上，標題只有一行 `▾ 用戶待辦（N）`，預設展開。內容每項一行，U1 在前、U2 在後：

  ```text
  <事項>｜<鍵>                      U1，不帶鍵的待辦行寫「主控」
  <事項>｜L<n> <短票號>（S1／S3）    U2，有票號
  <事項>｜L<n>（S2／S3）             U2，沒有票號
  ```

  - U1 依各鍵最後一次寫入待辦行的順序；同一個鍵以最後一行為準，最後一行是完成行就不列。U2 依線號，各線內依 S1、S3、S2
  - S2（session 停下來等用戶）為要人處理的洋紅粗體，其他各行不上色
  - 沒有任何一項時不畫群組，只畫一行淡色的 `用戶待辦：無`（session 狀態讀不到時為 `用戶待辦：無（session 狀態讀不到，S2 未判）`）；協調票讀不到時不畫（判不出有沒有待辦，由「解析失敗」提示說明）
- **線群組的標題**分三行，不以 `｜` 分隔，收合時 `▾` 改為 `▸`；沒有目標或沒有活動計數時省略該行。session 狀態的判定見〈各 session 狀態〉最後一點：

  ```text
  ▾ L<n> <session 名稱>［<session 狀態>］[［待 compact］|［待 clear］][［/compact 後已恢復 HH:MM］]
  目標：<目標>
  <活動計數>
  ```

  `［狀態］` 之後的標記與徽章見〈context 用量〉的〈線標題的標記與徽章〉；兩者皆無時標題列只到 `［狀態］`
- **活動計數**：依序為 `N 派發中`、`N 閘門`、`等你處理`、`N 排隊`，只列不為零的項目，以 ` · ` 分隔。各項與展開後的內容一一對應：
  - `派發中`：群組內派發列的數目
  - `閘門`：階段為 `閘門` 的派發列，加上閘門票列（佇列中某張票的 `feat/<票號>` 分支正持有合併閘門；同組已有該票標閘門的派發列時不重複列）
  - `等你處理`：該線的 session 狀態為 `waiting`
  - `排隊`：佇列列的票數
- **展開後的內容**，依序：派發列（`<代理人>｜<任務>｜<流程階段>｜<距派發時間>`）、閘門票列（`閘門｜<短票號>｜自 HH:MM:SS`）、佇列列（`排隊：<票序>`）、佇列細節按鍵
- **佇列細節**：佇列列維持一行，其下一個按鍵 `▸ 佇列細節`，預設收合；按下後改為 `▾ 佇列細節`，其下縮排 2 欄逐張列出佇列列中的票，每張一行：

  ```text
  <短票號>｜<status>｜<title>
  ```

  - 只列佇列列中的票：`completed` 不列，同一張票在票序中出現多次只列一次；沒有佇列列的線（整條線已完成）與「其他」群組沒有這個按鍵
  - 各行依該票在佇列列中的五色狀態上色，以 `truncate-end` 截斷（寬度不足時保留短票號與狀態）
  - title 取自主 checkout 票檔 frontmatter 的 `title:`（單引號或雙引號包住的值去掉引號），與 status 同一次讀檔；票檔讀不到或沒有 title 欄時標 `（讀不到 title）`
  - 展開狀態與群組相同，記在 `line-board.expanded`，鍵為 `lane:<n>:detail`；收合整個線群組再展開時維持原狀態
- **五色狀態**（依「輪到誰處理」，判定集中在 `hooks/statusColor.ts`）：

  | 狀態 | 顏色 | 派發列 | 佇列列中的票 | 各 session |
  |------|------|--------|-------------|-----------|
  | 待辦 | 灰 | — | `pending` 且沒有派發列 | — |
  | 進行中（無派發中代理人，等子票或 PM 收尾） | 綠 | — | `in_progress` 且沒有派發列 | — |
  | 代理人執行中 | 青 | 階段為 `實作`、`審查`、`事故分析` | 有這三種階段的派發列 | — |
  | 閘門 | 黃 | 階段為 `閘門`（閘門票列同） | 有階段為閘門的派發列，或列為閘門票 | — |
  | 要人處理 | 洋紅 | 階段為 `收尾` | 有階段為收尾的派發列 | `waiting` |

  - 佇列票依該票所有的派發列判定（不限同一群組，以短票號比對任務欄）；同一張票有多個階段時依序取閘門、要人處理、代理人執行中。沒有派發列且狀態為 `unknown` 等其他值的票不上色，分隔符不上色
  - 「進行中」取綠：其餘四色、標題列的藍（主題鍵 `suggestion`）、錯誤提示的紅已占用，白與預設文字色無從分辨，黑在深色終端機上看不見
- **佇列列不列 `completed` 的票**（連同其註記）：被去掉的票兩側的分隔符併成一個，任一為 `→` 時為 `→`，首尾的分隔符去掉；整條線都已完成時沒有佇列列，標題的活動計數也沒有排隊數
- **其他**：派發列對不到任何線時歸最後的「其他」群組，標題為 `▾ 其他` 與其下一行活動計數，內容只有派發列；沒有這種派發時不顯示
- **底部兩區塊**的標題只有名稱一行（`▾ 各 session`、`▾ 合併閘門最近紀錄`）
- **預設展開**：有派發中代理人、session 為 `waiting`、或有票在閘門中的線展開，其餘收合（只有排隊票不算活動）；預設每輪讀取後依新資料重算。用戶待辦與底部兩個區塊預設展開。無活動的線，標題列之下的目標與活動計數以淡色顯示；標題列維持 `suggestion` 色粗體不變淡（實機上淡色會把標題色換成灰色，標題列就與其下各行同色）
- **手動切換**：按過的群組以群組 id（`userTodos`、`lane:<n>`、`other`、`sessions`、`mergeGate`，佇列細節為 `lane:<n>:detail`）把展開狀態記在 `$.state` 的 `line-board.expanded`，之後以手動狀態為準，每 30 秒的資料刷新不覆寫；hot reload 不遺失，看板 session 結束後清空
- 提示行排在用戶待辦之下、線群組之上：協調票讀不到（「解析失敗」）或沒有現行佇列行（「協調票尚無現行佇列行」）、派發紀錄讀不到或格式錯誤、session 狀態讀取失敗、目前沒有派發中的代理人
- 群組多到超出 Pane 高度時 Pane 可捲動；fullscreen 且夠寬時 Pane 停靠在側邊

## 各 session 狀態（`~/.claude/sessions/*.json`）

Claude Code 為每個執行中的 session 寫一個 `<pid>.json`，含 `sessionId`、`name`、`cwd`、`status`（`busy`／`idle`，執行 shell 命令時為 `shell`，停下來等用戶時為 `waiting` 並附 `waitingFor`）、`statusUpdatedAt`（epoch 毫秒）與 `procStart`（行程啟動時間）。

- **只讀副檔名為 `.json` 的檔案**。同目錄的 `<pid>.<hash>.key` 是金鑰，看板任何情況下都不讀（測試以放了 `.key` 的目錄斷言這一點）
- 只列 cwd 等於主 checkout 或位於 `git worktree list` 任一路徑之下的 session；其他專案的 session 不列出
- 以 `TZ=UTC LC_ALL=C ps -p <pid> -o lstart=` 確認存活：exit 不為 0，或輸出的啟動時間與 `procStart` 不同（pid 已被其他行程重複使用），都不列出，只在區塊末尾顯示「另有 N 個狀態檔的 pid 已結束」
  - `procStart` 是 UTC，格式同 `ps -o lstart`（如 `Mon Oct 19 09:09:02 2026`）；不帶 `TZ=UTC` 的 `ps` 輸出本機時間，無法逐字比對（2026-10-19 以 2.1.303 的真實 session 對照：UTC 輸出與 `procStart` 逐字相同，本機 CST 輸出晚 8 小時）。比對前兩者都去頭尾空白並壓縮連續空白
  - 無從比對時退回只看 exit code：狀態檔沒有 `procStart`、或任一方不符上述格式（例如 Claude Code 改了 `procStart` 的格式）。這時 pid 重複使用不會被辨識出來
  - `ps` 本身無法執行時視為存活
- 排序：`waiting`、`busy` 與 `shell`（同組，組內依名稱）、`idle`，其他狀態值排最後；狀態一律原樣顯示。`waiting` 以洋紅粗體顯示（要人處理，見〈版面〉的五色狀態；黃色留給閘門）
- 每列：`<name>｜<status>[：<waitingFor>]｜<距 statusUpdatedAt 的時間>[｜ctx <百分比>%（<距量測的時間>）]`，時間以最近一次讀取的時刻計。用量字尾見下方〈context 用量〉；沒有用量檔的 session 不加
- 線群組標題列的 `［狀態］`：以協調票現行佇列行括號內的 session 名稱比對存活 session 的 `name`（同名多筆取最新一筆），比對不到標 `離線`；sessions 目錄讀不到時標 `狀態不明`

這是 Claude Code 的內部檔案，官方沒有文件承諾格式。Claude Code 升版後除了〈驗證〉的指令，還要以真實的 sessions 目錄對照一次（檔案欄位、status 值，以及 `procStart` 是否仍與 `TZ=UTC ps -p <pid> -o lstart=` 逐字相同）。

### context 用量（`.claude/hook-logs/line-board/context/<sessionId>.json`）

每個載入 line-board 的 session 以 `session.measure` 把自己的用量寫進主 checkout 的用量檔（`hooks/contextUsage.ts`），看板讀檔（`hooks/contextJudge.ts`），不靠 AI 回報。

- **只讀存活 session 的檔**：以上方存活判定後的 `sessionId` 逐一讀 `<sessionId>.json`，不列目錄，所以已結束 session 留下的檔不會被讀到。內容的 `sessionId` 與檔名不符的檔不採用
- **百分比的分母**：`autoCompactThreshold` 有值（auto-compact 開啟）用 `compactPercent`（以 compaction window 為分母），為 null 用 `percent`（以模型 window 為分母，同狀態列）。compact 剛完成、下一次回應前沒有用量，寫「ctx 未量測」，不寫 0%
- **量測時間只顯示不停判**：用量檔只在用量變動時寫入，閒置 session 最後一次的值仍然準確；閒置正是最可能去 compact 的時候
- **待 compact／待 clear 判定**（`contextMarkOf`，看板線標題與 `line_status` 共用）：

  | session | 待 compact | 待 clear |
  |---------|-----------|----------|
  | 一般線（未收線） | 持有 in_progress 票且達 `LANE_T_COMPACT`（45） | 未持有 in_progress 票且達 `LANE_T_CLEAR`（30） |
  | 主控 | 達 `COORDINATOR_T_COMPACT`（60） | 不判定 |
  | 收線或不屬於任何線 | 不判定 | 不判定 |

  門檻依據：583 盤點的兩次實際 compact 在 45% 與 33%；主控長駐，compact 屬例外處理
- **線標題的標記與徽章**（`laneContextLabel`）：線群組標題列 `［狀態］` 之後依序接：
  - 標記：判定為待 compact 標 `［待 compact］`、待 clear 標 `［待 clear］`。以佇列行括號內的 session 名稱找存活 session（同〈各 session 狀態〉的比對），再以其 `sessionId` 取用量檔；名稱為「主控」套主控門檻，其他套一般線門檻。「持有 in_progress 票」指該線佇列中有票在主 checkout 為 `in_progress`。收線的線不在看板上，不會被標
  - 恢復開工徽章：用量檔的 `phase` 為 `resumed` 且距今不超過 10 分鐘（`RESUME_BADGE_MS`，含 10 分鐘）時標 `［/<compact|clear> 後已恢復 HH:MM］`，時間為進入 resumed 的本機時間；`compacted`（compact 完成但尚未開工）不標。徽章讓主控在恢復開工通知之外，回頭看板時仍看得到哪條線剛恢復
  - 沒有 session 名稱、session 不存活、沒有用量檔、用量缺席（compact 後下一次回應前）時都不標
- **`line_status` 的 context 段**（`laneContextStatus`）：未收線的線在依據之後接 `｜<context 段>`，標記與徽章取 `laneContextLabel`（與線標題同一份），另加 `phase` 段（不受徽章 10 分鐘限制）。與看板不同，沒有用量檔明寫 `ctx 無用量檔`，用量檔存在但解析不成立寫 `ctx 用量檔解析失敗：<原因>`（`readers.ts` 的 `readContextUsageStates` 回傳原因；看板只取成立的記錄）。各寫法的判讀與主控接續動作見 `multi-session-orchestration` 的 `references/line-continuity.md` §3〈context 段的判讀〉
- **清理**：每個 session 在 `session.end`（任何 reason）刪自己的用量檔，`/clear` 刪的是舊 id 的檔；看板每小時掃一次 context 目錄，刪除 mtime 超過 24 小時且不屬於存活 session 的檔。刪除前檢查路徑直接位於 context 目錄下、檔名符合 `[A-Za-z0-9_-]+\.json`，不符就不刪（`isDeletableUsagePath`）。`$.fs` 沒有刪除操作，以 `rm -f` 刪除

## 派發中代理人（`.claude/dispatch-active.json`）

`$.agent.list()` 只列看板 session 自己派發的代理人，跨 session 的派發改讀派發紀錄。只讀主 checkout 的這一份：派發紀錄由主 checkout 的 hook 維護，worktree 內的檔案是分支開出當下的舊副本。

- 每筆取 `agent_id`、`name`（代理人類型）、`session_id`、`ticket_id`、`agent_description`、`dispatched_at`、`turn_ended_at`；`agent_id`、`session_id`、`name` 任一缺少的條目略過。`tombstones` 不讀
- **所屬線**：以 `session_id` 對 `~/.claude/sessions/*.json` 的 `sessionId` 找存活的 session（存活判定同〈各 session 狀態〉），再以其 `name` 對協調票現行佇列行括號內的 session 名稱取線號；對不到任何線的歸「其他」
- **流程階段**，依序判定：
  1. 有票號且該票在主 checkout 為 `completed`：不列
  2. 分支 `worktree-agent-<agent_id>` 是合併閘門的持有者（見〈合併閘門紀錄的顯示〉）：`閘門`，代理人是否已結束皆同。`branch_name` 欄只記 `worktree`，分支名由 `agent_id` 組出
  3. 未結束（`turn_ended_at` 為 null）：審查類代理人為 `審查`，`incident-responder` 為 `事故分析`，其餘為 `實作`。審查類清單集中在 `hooks/dispatch.ts` 的 `REVIEW_AGENTS`，以該常數為準。**維護點**：這份清單由人手動維護，不會從 `.claude/agents/` 自動取得；`.claude/agents/` 新增審查類代理人時，要同步加進 `REVIEW_AGENTS`，漏加的代理人在未結束時會被判成 `實作`
  4. 已結束且有票號（票未 `completed`，含票檔讀不到）：`收尾`；已結束且沒有票號：不列（沒有票可收尾）
- **不列出**：session 已不存活（狀態檔不存在或 pid 已結束），以及上列判定為不列的條目
- 每列列在所屬線的群組內：`<代理人>｜<任務>｜<流程階段>｜<距 dispatched_at 的時間>`，所屬線由群組標題表達；對不到線的列在「其他」群組。任務為短票號（與票序相同，去掉協調票票號的前綴），沒有票號時為 `agent_description`。同線保留紀錄中的順序；以 `truncate-middle` 截斷
- 派發紀錄讀不到或格式錯誤（JSON 無效、`dispatches` 不是陣列）時，群組之上顯示讀取失敗，各群組照常但沒有派發列；sessions 目錄讀不到時無從判定存活，不列派發列並標明；協調票或閘門紀錄讀不到時照樣列出，線一律歸其他、不判定閘門

這是本專案框架的內部檔案，欄位由派發 hook 決定；欄位改名時本區塊的條目會被略過或顯示讀取失敗。

## 合併閘門紀錄的顯示

面板停靠在側邊時寬度有限，整行原文會把分支名與結果擠出畫面，因此每行只顯示四個欄位：

```text
<HH:MM:SS>｜開始｜<短分支名>
<HH:MM:SS>｜結束｜<短分支名>｜<結果>
```

- 時間只取時間戳的 `HH:MM:SS`；分支取自 `分支` 欄，結果取自 `結果` 欄。`commit` 欄不顯示：開始行記的是當時 main 的 HEAD，結束行只有結果為「寫入」時才是合併 commit
- 短分支名：`worktree-agent-<id>` 縮成 `agent-<id 前 6 碼>`，`feat/<票號>` 縮成票號，其他分支原樣
- 結束行依結果上色：寫入為綠、中止為黃、拒絕與紅燈為紅，其他結果不上色
- 欄位行以 `truncate-middle` 截斷：寬度不足時保留行首時間與行尾結果
- 時間戳、分支或結果（結束行）缺少的 `[合併閘門]` 行原樣顯示，不丟棄
- **閘門使用中**：整份紀錄中，每個分支取最後一筆開始行，其後沒有同一分支的結束行者都列出，每個一行 `閘門使用中：<短分支名>（自 HH:MM:SS）`，依開始順序排在區塊最上方；沒有任何持有者時不顯示。持有者可能同時有多個：免跑測試的合併不佔 heavy 名額，可與其他分支的合併重疊（實例：16:19:45 a352 開始、16:21 a748 開始並結束、16:31:50 a352 才結束，其間 a352 一直持有）
  - 開始與結束以 `分支` 欄配對，不以下一行配對；`[合併閘門] 預檢` 行（無衝突的合併在開始與結束之間多記的一行，帶分支與結果欄）不是結束行，篩選時已濾掉
  - 合併程序異常終止、沒寫結束行時，該分支會一直列為持有者，直到它再次合併並寫出結束行

## 協調票現行佇列行的格式

```text
**L<n> 現行佇列**（<session 名稱>）：<短票號，以 → 與 ∥ 分隔>
```

- 行首即 `**L`，n 必須是數字；清單項（`- **L7 …`）、表格內、以反引號引用範本的說明行都不算
- 同一條線有多行時只取最後一行，較早的行是歷史，其票號不出現在看板
- 最後一行的票序整段寫 `（無）` 或 `（結束）` 表示這條線結束，看板不顯示該線；收線記號後面再接說明（如 `（無）— 說明`、`無（…）`）不算收線，看板照常顯示，`line_status` 列為過期項（判定在 `lanes.ts` 的 `endedForm`，看板與工具共用）
- 括號內的 session 名稱原樣顯示；行內沒寫時顯示「（未標 session）」

畫面能分辨兩種空狀態：「協調票尚無現行佇列行」（票檔讀得到但 Solution 內沒有任何現行佇列行）與「解析失敗」（票檔讀不到）。

### 線目標行（由主控寫在協調票）

```text
**L<n> 目標**：<一句話目標>
```

- 判定與現行佇列行相同：同樣只掃 Solution，行首即 `**L`、n 為數字；清單項、表格內、以反引號引用範本的行不算
- 同一條線有多行時只取最後一行；最後一行寫 `（無）` 或留空表示清除，該線不顯示目標；清除後再寫新的目標行即恢復顯示
- 目標只顯示在有現行佇列行的線上，為該線群組標題的第二行：`目標：<目標>`；沒有現行佇列行或已結束的線，目標行不顯示

## line_status 工具（模型可呼叫）

plugin 在 `session.start` 以 `$.tool.register` 註冊 `mcp__line-board__line_status`，給主控的模型讀各線接續狀態、過期項與等用戶。工具的用途、輸出內容與讀法屬 `multi-session-orchestration` 的 `references/line-continuity.md` §3；本節只記實作面。

| 項目 | 內容 |
|------|------|
| 位置 | 未指定 `isDeferred`，依平台規則放在 ToolSearch 後面；模型先以 ToolSearch 搜尋 `line_status` 再呼叫 |
| 可見範圍 | plugin 載入的 session 都看得到，代理人 session 也看得到（實測 2026-10-31，Explore 代理人可呼叫）。工具唯讀、無副作用，不限只給主控 |
| 讀取 | 每次呼叫都重讀，不取 Pane 的 snapshot：Pane 只在設定成立時定時刷新，且最多落後一個刷新間隔 |
| 失敗 | 設定不成立、協調票或 session 讀不到時回傳說明原因的文字，不 deny，模型才讀得到「為何判不出」 |
| 等用戶 | 票面標記（S1）在 `readers.ts` 讀佇列票 status 的同一次讀檔中解析（`TicketStatus.waiting`），看板與工具共用該讀取；判定與輸出在 `continuity.ts`。訊號定義的權威是 `line-continuity.md` §2〈等用戶〉 |
| 來源紀錄 | 合併各 checkout 的 `.claude/hook-logs/session-source-diagnostic/diagnostic.log`（worktree 內啟動的 session 寫入該 worktree 的檔），同一 sessionId 取時間最晚的一筆 |
| 型別 | 平台型別根的 MCP 條目列出已連線 server 的工具後，`tool.call` 的過濾名稱就收窄為那些名稱；自己註冊的工具須在 `types/index.d.ts` 的 `McpToolInputs` 補宣告，否則 `tsc` 報 TS2322。閘門快照沒有 MCP 條目時過濾名稱不收窄，所以只有手動型別檢查會擋 |

## 結構

| 檔案 | 職責 |
|------|------|
| `.claude-plugin/plugin.json` | manifest，`types` 指向契約，`defaultEnabled: true` |
| `hooks/hooks.json` | 指向 hooks module |
| `hooks/register.tsx` | 註冊 `/board` 與 `line_status` 工具（`tool.call` 交給 `lineStatus.ts`）、定時刷新的協調（依序呼叫 `readers.ts` 並寫入 snapshot）、讀寫群組的手動展開狀態、組裝 Pane（用戶待辦、線群組、底部兩區塊的折疊外框）；設定不成立時只寫設定提示 |
| `hooks/readers.ts` | 一輪 snapshot 所需各項的讀取：專案設定、checkout 清單、協調票、票檔 status 與 title、session 狀態檔與 pid 存活、派發紀錄、合併閘門紀錄；讀檔與命令一律經 `$`，各項失敗只影響該項 |
| `hooks/lanesView.tsx` | 線群組的繪製（標題三行、派發列、閘門票列、佇列列、佇列細節，各依五色狀態上色）與各群組共用的可折疊外框（框線、主題鍵 `suggestion` 色粗體標題列、內容）；設定提示的繪製 |
| `hooks/dispatchView.tsx` | 由 snapshot 推出派發列，以及派發紀錄讀取失敗等提示行 |
| `hooks/{sessions,mergeGate}View.tsx` | 底部兩區塊的內容：各 session、合併閘門最近紀錄 |
| `hooks/userTodosView.tsx` | 用戶待辦群組的繪製：以 `continuity.ts` 判 U2、`userTodos.ts` 組成各行，S2 洋紅粗體；沒有任何一項時為一行「用戶待辦：無」 |
| 各 `*View.tsx` 共通 | 元素（`Box`、`Text`、`Button`，型別 `Elements`）由 register.tsx 以 `$.ui.resolve(e)` 取得後傳入；各區塊的繪製函式以元素與 snapshot（`ReadyBoard`）為參數 |
| `hooks/parse.ts` | 純函式的匯出彙總：register.tsx、readers.ts 與各 `*View.tsx` 只從這裡取用，本身不含實作 |
| `hooks/shared.ts` | 各 domain 共用：專案設定解析、票號前綴與票檔位置、frontmatter 狀態與 title 解析、checkout 路徑判定、距今時間 |
| `hooks/lanes.ts` | 線與佇列：現行佇列行與線目標行解析（每線取最後一行）、票序拆分與格式化 |
| `hooks/sessions.ts` | 各 session：狀態檔篩選／解析／排序、pid 存活比對（procStart）、本 repo 判定、線列 session 狀態 |
| `hooks/mergeGate.ts` | 合併閘門：紀錄篩選與欄位解析、短分支名、閘門持有者判定、結果顏色 |
| `hooks/dispatch.ts` | 派發中代理人：派發紀錄解析、流程階段推導、派發列；審查類代理人清單 `REVIEW_AGENTS` |
| `hooks/layout.ts` | 版面：以線分組、活動計數、預設展開、手動切換的展開狀態、群組標題列與內容各行的顯示文字、佇列列的分段（供逐票上色） |
| `hooks/statusColor.ts` | 五色狀態：派發階段、佇列票與 session 狀態歸成哪一種狀態，以及各狀態的顏色 |
| `hooks/continuity.ts` | 各線接續狀態：SessionStart 來源紀錄解析、每條線的接續狀態判定、過期偵測、等用戶偵測與票面標記解析、`line_status` 的輸出文字（判讀規則唯一實作） |
| `hooks/userTodos.ts` | 用戶待辦：協調票的待辦行與完成行配對（U1）、用戶待辦群組各行的顯示文字（U1 + U2） |
| `hooks/contextUsage.ts` | context 用量檔的寫入端：何時寫、路徑、記錄內容（含恢復開工的 `phase`） |
| `hooks/contextJudge.ts` | context 用量的讀取端：用量檔解析（含失敗原因）、分母選擇、待 compact／待 clear 判定與門檻常數、各 session 列的用量字尾、線標題的標記與徽章、`line_status` 的 context 段、清理的路徑檢查與孤兒檔挑選 |
| `hooks/resumeNotice.ts` | 恢復開工通知：compact／clear 後第一個 prompt 的判定狀態機、送或不送（不送帶原因）、通知文字、用量檔 `phase` |
| `hooks/resumeNoticeLog.ts` | 恢復開工通知的送出紀錄檔 `.claude/hook-logs/line-board/resume-notice.log`：紀錄行格式（步驟、不送原因、傳送回傳）與上限截斷 |
| `hooks/lineStatus.ts` | `line_status` 的組裝：每次呼叫重讀專案設定、協調票、session 狀態檔、各 checkout 的來源紀錄、佇列票 status 與等用戶標記、主 checkout 的用量檔，交 `continuity.ts` 判讀 |
| `types/index.d.ts` | `$.state` 值（`line-board.snapshot`、`line-board.expanded`）與純函式輸入輸出的型別契約；`McpToolInputs` 補宣告本 plugin 註冊的工具 |
| `tests/*.test.ts` | `claude plugin test` 測試：各 domain 純函式與同名產品檔一一對應；`board.test.ts`、`boardDispatch.test.ts`、`boardUserTodos.test.ts` 為 Pane 端到端繪製，`boardDispatch` 為線群組的派發列、活動計數、預設展開與手動切換，`boardUserTodos` 為用戶待辦群組，`board` 為線標題列、票序、佇列細節與底部兩區塊。`test()` 傳入的 `$` 是測試端 engine，不是 hooks 收到的 plugin `$`（沒有 `ui.log` 等），`readers.ts` 的函式不能直接拿它呼叫；讀到內容後的解析與組裝一律放進 domain 檔的純函式（例：`continuity.ts` 的 `ticketStatusOf`），測試該函式，讀檔本身只經 Pane 端到端覆蓋 |
| `tests/fixtures.ts`、`tests/paneHarness.ts` | 測試共用（非測試檔）：仿真資料與建構函式；Pane 測試的 repo stub、啟動看板、session 狀態檔組 |
| `tsconfig.json` | 只有一行 `extends ./.claude-plugin/types/tsconfig.json`；納入版控 |

`.claude-plugin/types/` 與根目錄 `tsconfig.json` 由 Claude Code 載入 mod 時自動產生。`.claude-plugin/types/` 由 Claude Code 自帶的 `.gitignore` 排除，不進版控；`tsconfig.json` 納入版控（plugin-authoring 的分享說明要求保留），下次載入時 Claude Code 會以同內容重新產生。

## 驗證（Claude Code 升版後必須重跑）

mod API 屬 early access，各版本間會變，權威是 Claude Code 寫出的型別檔。升版後依序執行：

```bash
claude plugin validate .claude/skills/line-board   # manifest 與 hooks module 靜態檢查
tsc -p .claude/skills/line-board                   # 型別檢查（需先載入過一次，讓 CC 寫出 types 與 tsconfig）
claude plugin test .claude/skills/line-board       # 執行 tests/*.test.ts
```

合併閘門會在改動觸及 `.claude/skills/line-board/` 時自動執行 `claude plugin test .claude/skills/line-board`（宣告見 `.claude/project-integration/merge-gate.yaml`），失敗即判紅不合併；閘門不跑 `tsc`，型別檢查仍須手動執行。

### 實機驗證時的載入時機

在既有 session 實測 plugin 改動（例如新註冊的工具）前，先確認該 session 已載入新版程式。兩項實測（2026-10-31，Claude Code 2.1.316）：

| 行為 | 實測 | 驗證時的做法 |
|------|------|-------------|
| `/clear` 不重新觸發 plugin 的 `session.start` | 型別定義寫明 `session.start` 在每次全新載入時觸發，「never `/clear`」 | 不以 `/clear` 作為「讓 session 載入新版 plugin」的手段 |
| plugin 檔案變動時，既有 session 可能熱重載 | 合併後，兩個在合併前啟動的 session 都在未重開的情況下收到 deferred tools 通知，`line_status` 出現；兩者出現的時間點不同，其中一個晚了數分鐘 | 合併後先等 deferred tools 通知；沒有出現就重開 session 再驗，不判定為工具註冊失敗 |

`session.start` 只在載入時執行一次，所以在 `session.start` 註冊的工具與 `/board` 指令，都要等 plugin 重新載入後才會更新。

### plugin 事件與 settings hooks 同名不同義

plugin 的事件和 `settings.json` 的 hooks（SessionStart、SessionEnd 等）名稱相近，欄位與觸發時機不同。設計時以 plugin 型別定義（`.claude-plugin/types/claude-code/index.d.ts`）為準，不沿用 settings hooks 的欄位。

| 想偵測的事 | settings hooks | plugin 事件 |
|-----------|---------------|------------|
| session 是不是 compact／clear 後啟動 | SessionStart 的 `source`（startup／resume／clear／compact） | `session.start` 沒有 source，且 `/clear`、compact 都不觸發。compact 用 `session.compact`（`await next(e)` 回傳無 `skip` 才是真的壓縮了）；clear 用 `session.end` 的 `reason === 'clear'`（行程繼續、換新 session id） |
| 本 session 的名稱 | 讀 `~/.claude/sessions/<pid>.json` | 沒有名稱 API；以 `$.session.id()` 比對 sessions 狀態檔的 `sessionId` |

要跨 `/clear` 保留的 plugin 狀態只能放模組層變數（session id 換了，行程沒換），熱重載時會遺失。

`恢復開工通知`（`hooks/resumeNotice.ts`）即依此表實作，判讀與限制見 multi-session-orchestration 的 `references/line-continuity.md` §4〈線 session 的恢復開工通知〉。
