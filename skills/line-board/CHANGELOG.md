# line-board 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 0.11.0（2026-10-31）— 跨專案行為變更：`line_status` 每條未收線的線在依據之後接 context 段：`ctx <百分比>%（<距量測>）`、看板線標題同一份的 `［待 compact］`／`［待 clear］` 標記與恢復開工徽章，用量檔有 `phase` 時再接 `｜phase <compacted|resumed>（<來源>，HH:MM）`（不受徽章 10 分鐘限制）。沒有用量檔寫 `ctx 無用量檔`，用量檔存在但解析不成立寫 `ctx 用量檔解析失敗：<原因>`；持有者無從查起的線沒有 context 段。看板 Pane 不變。

- `hooks/contextJudge.ts` 新增 `laneContextStatus`（標記與徽章經 `laneContextLabel`）、`phaseText`、`parseContextUsageDetailed`（失敗附原因：JSON 無效、不是物件、缺必要欄位；`parseContextUsageFile` 改為經此函式）、型別 `ContextUsageParse`、`ContextUsageFailures`。
- `readers.ts` 新增 `readContextUsageStates`（另回傳解析失敗的 sessionId 與原因，含檔內 sessionId 與檔名不符）；`readContextUsages` 改為取其 `usages`。
- `continuity.ts` 的 `lineStatusReport` 新增選填輸入 `context`（用量、失敗原因、判定時間），`LaneContinuity` 新增選填 `context`；`formatLineStatus` 接在依據之後。`lineStatus.ts` 每次呼叫讀主 checkout 的用量檔並傳入。
- `references/board-screens.md`〈context 用量〉補 `line_status` 的 context 段。

**Version**: 0.10.0（2026-10-31）— 跨專案行為變更：恢復開工通知的主管道（跨 session 訊息給主控）預設關閉。實測 auto mode 下 plugin 在事件中主動送訊沒有對應的使用者請求，classifier 不給判定而拒送（紀錄檔 `step=sent isDelivered=false`），與 0.7.0 寫明的「暫扣就關」同類。關閉後紀錄檔改寫 `step=send-disabled`；輔管道（用量檔 `phase`）與線標題的恢復開工徽章不變，主控以這兩者與 `line_status` 為準。

- `register.tsx`：`IS_RESUME_NOTICE_SEND_ENABLED` 改為 `false`，註解寫明關閉理由。送出路徑與 `resume-notice.log` 保留。

**Version**: 0.9.1（2026-10-31）— 恢復開工通知新增送出紀錄檔：每次恢復開工在主 checkout 的 `.claude/hook-logs/line-board/resume-notice.log` 寫一行（時間、sessionId 前 8 碼、來源、走到的步驟、跨 session 傳送的回傳或例外），只保留最後 500 行。原本設定讀不到、session 或協調票讀不到、判定不送三處只 return 或只記 debug，送出被拒也只記 debug，主管道沒收到通知時無從定位原因。通知的判定與文字不變。

- 新增 `hooks/resumeNoticeLog.ts`（`resumeNoticeLogLine`、`appendCappedLog`、`RESUME_NOTICE_LOG_PATH`、`RESUME_NOTICE_LOG_MAX_LINES`、`ResumeNoticeOutcome`）。
- `hooks/resumeNotice.ts`：`resumeNoticeTarget` 改為 `resumeNoticeDecision`，不送時回傳原因（`no-session-name`、`coordinator`、`lane-not-found`、`lane-ended`）。
- `register.tsx`：`notifyResumed` 拆為 `sendResumeNotice`（回傳步驟與結果）與 `appendResumeNoticeLog`（寫不進去送 transcript）。

**Version**: 0.9.0（2026-10-31）— 跨專案行為變更：線群組標題列在 `［狀態］` 之後加 context 用量的標記與恢復開工徽章。達門檻的線標 `［待 compact］` 或 `［待 clear］`（判定同 0.8.0 的 `contextMarkOf`）；恢復開工後 10 分鐘內標 `［/compact 後已恢復 HH:MM］`（`/clear` 同理，本機時間）。沒有用量檔、未達門檻、超過 10 分鐘的線，標題列與 0.8.0 相同。

- `hooks/contextJudge.ts` 新增 `laneContextLabel`（依 session 名稱找存活 session 與用量檔；名稱為主控以主控門檻判定；持有 in_progress 票＝佇列中有票在主 checkout 為 in_progress）、`contextMarkLabel`、`recentResume`、`resumeBadgeText` 與常數 `RESUME_BADGE_MS`，供 `line_status` 共用（後續版本接上）。
- `hooks/lanesView.tsx` 的線群組標題列接上 `laneContextLabel`。
- `references/board-screens.md` 的線群組標題格式與〈context 用量〉補標記與徽章。

**Version**: 0.8.0（2026-10-31）— 跨專案行為變更：「各 session」區塊每列在有用量檔時，行尾加 `｜ctx <百分比>%（<距量測的時間>）`；compact 後沒有用量時寫 `ctx 未量測`。沒有用量檔的 session 不加字尾。用量檔開始有清理：session 結束時刪自己的檔，看板每小時刪 24 小時以上的孤兒檔。

- 新增 `hooks/contextJudge.ts`：`parseContextUsageFile`、`selectedPercent`（auto-compact 開啟用 `compactPercent`，關閉用 `percent`）、`contextMarkOf`（待 compact／待 clear，一般線 45／30、主控 60 且不判待 clear；收線或不屬於任何線不判定）、`contextUsageSuffix`、`isDeletableUsagePath`、`orphanUsageFiles`，門檻常數 `LANE_T_COMPACT`、`LANE_T_CLEAR`、`COORDINATOR_T_COMPACT`、`ORPHAN_AGE_MS`。判定函式供線標題標記與 `line_status` 共用（後續版本接上）。
- `readers.ts` 新增 `readContextUsages`（只讀存活 session 的 `<sessionId>.json`，不列目錄）、`sweepOrphanUsageFiles`、`removeUsageFile`（刪除前檢查路徑與檔名，以 `rm -f` 刪除）；`register.tsx` 把用量放進 snapshot、每小時掃孤兒檔、`session.end` 刪自己的檔；`types/index.d.ts` 的 ready snapshot 新增 `usages`。
- 量測時間只顯示不停判：用量檔只在用量變動時寫入，閒置 session 的最後一次值仍準確。
- `references/board-screens.md` 新增〈context 用量〉，結構表補三個用量相關模組。

**Version**: 0.7.0（2026-10-31）— 跨專案行為變更：一般的線在 `/compact` 或 `/clear` 之後重新開工時，line-board 以跨 session 訊息通知名為「主控」的 session，固定一行 `L<n>（<名稱>）已恢復開工：<時間>，來源 compact／clear`；用量檔新增 `phase` 欄位（`compacted`／`resumed`、來源、時間）。看板與 `line_status` 的畫面與輸出不變（`phase` 的讀取端在後續版本）。

- 判定以 plugin 事件為準：`session.compact` 完成且未被否決（含 auto compact，不含 precompute 與 subagent 自己的 compact）、`session.end` 的 reason 為 `clear`；之後第一個送出的 prompt（`/compact`、`/clear` 本身除外）視為恢復開工。
- 不通知：新開的 session、resume、主控自身、已收線的線、名稱比對不到協調票現行佇列行的 session。名稱以 `sessionId` 比對 `~/.claude/sessions` 的狀態檔取得。
- 主管道以 `register.tsx` 的 `IS_RESUME_NOTICE_SEND_ENABLED` 控制，預設開啟；接收端與傳送端權限模式不同時訊息會被暫扣，實測被暫扣時改為關閉。
- 待通知狀態放在模組層變數（`/clear` 換 session id 但行程繼續），plugin 熱重載時遺失，該次漏送不補救。
- 新增 `hooks/resumeNotice.ts`（`stepResume`、`resumeNoticeTarget`、`resumeNoticeText`、`resumePhaseOf`、`COORDINATOR_SESSION_NAME`）；`types/index.d.ts` 新增 `ResumeSource`、`ResumePhase`，`ContextUsageRecord` 加 `phase`；`register.tsx` 註冊 `session.compact`、`session.end`、`prompt.submit`。
- `references/board-screens.md` 新增〈plugin 事件與 settings hooks 同名不同義〉。

起因：多線協調時，線 session 做完 `/compact` 或 `/clear` 後，主控要主動詢問才知道它是否已經回到工作（2026-10-31）。

**Version**: 0.6.0（2026-10-31）— 跨專案行為變更：每個載入 line-board 的 session 以 `session.measure` 把自己的 context 用量寫到主 checkout 的 `.claude/hook-logs/line-board/context/<sessionId>.json`，每輪回應 context 用量變動時覆寫一次。看板與 `line_status` 的畫面與輸出不變（讀檔與「待 compact／待 clear」判定在後續版本）。

- 記錄欄位：`sessionId`、`tokens`、`window`、`percent`（以模型 window 為分母，同狀態列）、`compactWindow`、`compactPercent`（以 /context 的 compaction window 為分母）、`autoCompactThreshold`、`measuredAt`（毫秒）。缺席的量測寫 `null`，不寫 0：compact 剛完成到下一次回應前 `tokens`／`percent` 為 `null`。
- compaction window 以 `$.session.usage({ breakdown: 'summary' })` 本機估算量測（不送 API），依模型 window 快取。
- 不看專案設定：沒有協調票的專案也會寫用量檔（只在 `hook-logs/` 下，已被 `.gitignore` 涵蓋）。寫入失敗第一次送 transcript，之後只記 debug。
- 新增 `hooks/contextUsage.ts`（`isContextChanged`、`contextUsagePath`、`contextUsageRecord`、`serializeContextUsage`）；`types/index.d.ts` 新增 `ContextUsageRecord`；`register.tsx` 註冊 `session.measure`。

起因：多線協調時主控要知道哪條線該 `/compact`、哪條該 `/clear`，靠各線自報不可靠；改由每個 session 自己量測寫檔（2026-10-31）。

**Version**: 0.5.0（2026-10-31）— 跨專案行為變更：看板最上方新增「用戶待辦（N）」群組，集中列出要用戶處理的事項，預設展開；沒有任何一項時只顯示一行「用戶待辦：無」。

- 兩種來源，都從票面讀出：U1 協調票 Solution 段的待辦行 `**用戶待辦**（<鍵>）：<事項>`，以同鍵的完成行 `**用戶待辦完成**（<鍵>）：` 解除（不帶鍵的行以事項全文配對）；U2 各線等用戶，判定同 `line_status` 的等用戶段。格式權威是 multi-session-orchestration 的 `references/line-continuity.md` §2〈用戶待辦〉。
- 每項一行：U1 為 `<事項>｜<鍵>`（不帶鍵寫「主控」），U2 為 `<事項>｜L<n> <短票號>（S#）`；S2 洋紅粗體。
- 帶鍵與不帶鍵的項目分開配對；空括號的行略過；session 狀態讀不到且沒有任何一項時寫「用戶待辦：無（session 狀態讀不到，S2 未判）」。
- 新增 `hooks/userTodos.ts`（`parseUserTodos`、`userTodoRows`）與 `hooks/userTodosView.tsx`；`lanes.ts` 新增 `unfencedSolutionLines`，S1 標記與待辦行共用 fence 過濾；`continuity.ts` 匯出 `lanesWaiting`，`lineStatusReport` 的等用戶段改為直接呼叫它；`readers.ts` 的 `readLanes` 另帶出現行佇列行原文（`lines`）與待辦（`todos`）；`types/index.d.ts` 新增 `UserTodo`、`UserTodoRow`，`LanesResult` 加兩欄。
- `line_status` 的輸出不變。

起因：用戶回報主控要用戶處理的事項散在回覆裡，被 Stop hook 回應與各線訊息淹沒，找不到（2026-10-31）。

**Version**: 0.4.0（2026-10-31）— 跨專案行為變更：`line_status` 輸出多一段「等用戶（N）」，列出停在等用戶的線，每項一行 `L<n>（名稱）<票號>：<事項>（S1／S2／S3）`；沒有任何一項時寫「等用戶：無」。這一段與過期項分列。

- 三種訊號：S1 佇列中未 completed 的票，其 Solution 段最後一行等用戶標記（`**等用戶**：`，`**等用戶解除**：` 解除）；S2 該線 session 的 `status` 為 `waiting`；S3 現行佇列行的票註記或文字含「等用戶」。已收線的線不判。訊號定義的權威是 multi-session-orchestration 的 `references/line-continuity.md` §2〈等用戶〉。
- S1 標記只認嚴格行首、不在 fenced code block 內的行；冒號後沒寫事項照樣列出（`標記未附事項`），只有解除行能清除。
- `continuity.ts` 新增 `parseWaitingMark`、`ticketStatusOf`（票檔原文組成 status、title、waiting，`readers.ts` 的 `readTicketStatus` 讀到票檔後一律經此）與等用戶判定；`lanes.ts` 匯出 `solutionLines`；`types/index.d.ts` 新增 `WaitingSource`、`WaitingItem`，`LineStatusReport` 加 `waiting`，`TicketStatus` 加選填的 `waiting`。
- 看板畫面不變。

起因：一條線把待用戶實測的事項寫在票面卻沒有傳訊，主控沒讀到，直到用戶問起才發現；用戶裁定加入偵測（2026-10-31）。

**Version**: 0.3.1（2026-10-31）— 文件：`references/board-screens.md` 新增〈實機驗證時的載入時機〉，記錄 `/clear` 不重新觸發 plugin 的 `session.start`，以及 plugin 檔案變動時既有 session 可能熱重載（實測時間點不一）；`SKILL.md` 按需讀取表加路由。起因：`line_status` 合併後實測，有一個 session 晚數分鐘才看到工具（2026-10-31）。

**Version**: 0.3.0（2026-10-31）— 跨專案行為變更：plugin 載入的 session（含代理人 session）多一個模型可呼叫的唯讀工具 `mcp__line-board__line_status`，位於 ToolSearch 後面。

- 輸出每條未收線的線的接續狀態（/clear 後繼續、/compact 後繼續、新 session 接手、無人持有、來源不明）與判讀依據，已收線合併一行。
- 列出過期項：票序以收線記號開頭但後面還有文字、名稱不在存活 session 中但仍有佇列、佇列的票全部 completed 但還沒收線。
- 判讀規則只在新的 `hooks/continuity.ts` 實作一份；`lanes.ts` 新增 `parseLaneLines`（保留收線的線的原文），`parseLanes` 改由它濾出。
- 看板行為變更：收線判定改由 `lanes.ts` 的 `endedForm` 決定（看板與工具共用），票序整段為 `（結束）` 的線也不再顯示，原本只認 `（無）`，與 multi-session-orchestration 的收線定義不一致。
- `types/index.d.ts` 補 `McpToolInputs` 宣告，否則手動型別檢查擋下 `tool.call` 的過濾名稱。

起因：主控換 session 後要靠用戶提示接續，且附說明的收線寫法使收線的線一直顯示離線；用戶依 WRAP 裁定由看板提供判讀工具（2026-10-31）。

**Version**: 0.2.0（2026-10-28）— 跨專案行為變更：所有 consumer 專案 sync 後，session 啟動多一個看板 plugin（`defaultEnabled: true`，skills 目錄自動載入，須接受 workspace trust）。看板只在專案設定檔 `.claude/project-integration/multi-session.json` 的 `coordinationTicket` 成立時自動開 Pane 並定時讀取；沒有設定檔或設定不成立時不自動開 Pane、不定時讀取，輸入 `/board` 才顯示設定提示（原因、設定檔路徑、格式）。不要看板的專案在 `enabledPlugins` 設 `"line-board@skills-dir": false`。`SKILL.md` 補齊啟用與關閉、設定檔格式、無設定行為、合併閘門套件範例；原 `README.md` 的畫面規格移入 `references/board-screens.md`（skill 不帶 README）。起因：用戶裁定看板所有專案預設開啟（2026-10-21）。

**Version**: 0.1.0 — 從專案工具目錄搬入 `.claude/skills/line-board/`，成為 skill 形態的 plugin；`SKILL.md` 為佔位。
