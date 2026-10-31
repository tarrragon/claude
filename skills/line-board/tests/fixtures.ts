// line-board 測試共用的 fixture：349 票檔、合併閘門紀錄、session 狀態檔、派發紀錄的仿真資料與建構函式。
// 由各 *.test.ts 匯入；本檔不是測試檔，不含任何 test。

import type { DispatchRecord, SessionState } from '../types'

/**
 * queue-line-cases.json 全文的逐字副本（claude-code/testing 不能 import .json 也不能 node:fs）。
 * 兩個標記之間的第一個反引號到最後一個反引號即 JSON 全文，漂移守衛（538.2 Python 測試）逐字比對；改案例時兩處同改。
 */
// BEGIN queue-line-cases.json
const QUEUE_LINE_CASES_RAW = String.raw`{
  "_doc": "佇列行解析的唯一案例來源：lanes.test.ts 與後續 Python hook 共用。text 為協調票全文，prefix 為短票號前綴，expect 為各線 {lane, session, tickets[{serial,id,note}]}（只列 ticket token）。category: positive_control = 容易被誤判的寫法（括號附註、全終態但未寫（無）），normal = 一般寫法。",
  "cases": [
    {
      "name": "正常寫法：session 名稱、→ 與 ∥",
      "category": "normal",
      "prefix": "0.5.0-W1-",
      "text": "## Solution\n**L5 現行佇列**（s-a）：100 → 337.1 ∥ 353\n",
      "expect": [
        {
          "lane": 5,
          "session": "s-a",
          "tickets": [
            { "serial": "100", "id": "0.5.0-W1-100", "note": "" },
            { "serial": "337.1", "id": "0.5.0-W1-337.1", "note": "" },
            { "serial": "353", "id": "0.5.0-W1-353", "note": "" }
          ]
        }
      ]
    },
    {
      "name": "正常寫法：最後一行票序為（無）的線不列入",
      "category": "normal",
      "prefix": "0.5.0-W1-",
      "text": "## Solution\n**L5 現行佇列**：100\n**L5 現行佇列**：（無）\n",
      "expect": []
    },
    {
      "name": "正向對照：票號後括號附註原樣進 note，仍是活線",
      "category": "positive_control",
      "prefix": "0.5.0-W1-",
      "text": "## Solution\n**L5 現行佇列**：100（已完成，待合併）→ 101（待用戶驗證）\n",
      "expect": [
        {
          "lane": 5,
          "session": null,
          "tickets": [
            { "serial": "100", "id": "0.5.0-W1-100", "note": "（已完成，待合併）" },
            { "serial": "101", "id": "0.5.0-W1-101", "note": "（待用戶驗證）" }
          ]
        }
      ]
    },
    {
      "name": "正向對照：票序為（無）加括號附註不等於（無），線仍列入",
      "category": "positive_control",
      "prefix": "0.5.0-W1-",
      "text": "## Solution\n**L5 現行佇列**：（無）（全數終態）\n",
      "expect": [{ "lane": 5, "session": null, "tickets": [] }]
    },
    {
      "name": "正向對照：票全為終態但行尾未寫（無），解析不推斷終態，線仍列入",
      "category": "positive_control",
      "prefix": "0.5.0-W1-",
      "text": "## Solution\n**L5 現行佇列**：100（completed）→ 101（completed）\n",
      "expect": [
        {
          "lane": 5,
          "session": null,
          "tickets": [
            { "serial": "100", "id": "0.5.0-W1-100", "note": "（completed）" },
            { "serial": "101", "id": "0.5.0-W1-101", "note": "（completed）" }
          ]
        }
      ]
    }
  ]
}
`
// END queue-line-cases.json

/** 佇列行共用案例（解析自上方逐字副本）。 */
export const QUEUE_LINE_CASES: {
  name: string
  category: 'normal' | 'positive_control'
  prefix: string
  text: string
  expect: { lane: number; session: string | null; tickets: { serial: string; id: string; note: string }[] }[]
}[] = JSON.parse(QUEUE_LINE_CASES_RAW).cases

/** 〈看板讀取約定〉的格式說明行：行首不是 `**L`，行內以反引號引用範本，不得被當成一條線。 */
export const TEMPLATE_NOTE =
  '337 看板掃本票整個 Solution，每個 `L<n>` 只取最後一次出現的現行佇列行。格式：`**L<n> 現行佇列**（<ListAgents 顯示的 session 名稱>）：<短票號，以 → 與 ∥ 分隔>`，獨立成段、行首即 `**L`。'

/** 行首即範本、但 n 不是數字：不得被當成一條線。 */
export const TEMPLATE_AT_LINE_START = '**L<n> 現行佇列**（<session 名稱>）：<票序>'

/**
 * 仿 349 票檔結構：舊〈分派〉段的佇列行、清單項的舊格式現行佇列、格式說明行，
 * 以及同一條線的多行現行佇列（歷史行在前、現行行在後），最後接 `## Test Results`。
 */
export const TICKET_349 = [
  '---',
  'id: 0.5.0-W1-349',
  'status: in_progress',
  '---',
  '## Problem Analysis',
  '**L30 現行佇列**（s-out）：801',
  '## Solution',
  '### 分派（用戶裁定 2026-10-19）',
  '佇列：341.1 → 343 → 284 收尾',
  '### L7 佇列調整',
  '- **L7 現行佇列**：257 ∥ 350 → 328',
  '### 看板讀取約定（2026-10-19，-1b 定案）',
  TEMPLATE_NOTE,
  '',
  TEMPLATE_AT_LINE_START,
  '',
  '**L7 現行佇列**（graph-project-docs-manager-f8）：351 → 328.1 → 348',
  '',
  '**L9 現行佇列**（graph-project-docs-manager-3e）：356 → 353.1 ∥ 341.2.1 → 284',
  '',
  '**L13 現行佇列**（graph-project-docs-manager-1b）：337.1 → 337.2.1',
  '',
  '**L11 現行佇列**（graph-project-docs-manager-x9）：900',
  '### L13 佇列更正',
  '**L13 現行佇列**（graph-project-docs-manager-1b）：337.1（待用戶實機驗證）→ 337.3 → 337.2.1',
  '',
  '**L7 現行佇列**（graph-project-docs-manager-f9）：351 → 145',
  '',
  '**L11 現行佇列**（graph-project-docs-manager-x9）：（無）',
  '## Test Results',
  '**L20 現行佇列**（s-out）：999',
].join('\n')

/**
 * 仿 349 加上線目標行：清單項、表格內、行內反引號範本、行首範本（n 非數字）、整行以反引號包住的目標行都不算；
 * L13 有兩行（舊目標在前），L7 的最後一行寫（無）清除較早的目標，L9 沒有可採用的目標行；
 * Solution 之外的目標行不算。
 */
export const TICKET_349_GOALS = TICKET_349.replace(
  '## Test Results',
  [
    '- **L7 目標**：清單項的目標',
    '| **L9 目標**：表格內的目標 | 備註 |',
    '用戶裁定格式為 `**L<n> 目標**：<一句話目標>`，規則同現行佇列行。',
    '**L<n> 目標**：<一句話目標>',
    '`**L9 目標**：反引號範本的目標`',
    '**L13 目標**：舊目標',
    '',
    '**L13 目標**：顯示各線目標與派發中代理人',
    '',
    '**L7 目標**：會被清除的目標',
    '',
    '**L7 目標**：（無）',
    '## Test Results',
    '**L9 目標**：Solution 之外的目標',
  ].join('\n'),
)

/** 仿 worktree-merge.log：開始／結束之間夾著驗收、測試、預檢等其他行。 */
export const MERGE_LOG = [
  '2026-10-19T16:04:26 [合併前驗收] target=0.5.0-W1-328 reason=收尾',
  '2026-10-19T16:04:26 [合併閘門] 開始｜target main｜分支 feat/0.5.0-W1-328｜commit ee5e80e6b9a4',
  '2026-10-19T16:04:27 [合併閘門] 預檢｜無衝突',
  '2026-10-19T16:09:01 [合併前測試] 套件 hooks：綠燈｜7212 passed',
  '2026-10-19T16:11:45 [合併閘門] 結束｜target main｜分支 feat/0.5.0-W1-328｜commit a9dc3b442c24｜結果 寫入',
  '',
].join('\n')

/**
 * 仿真實 worktree-merge.log（2026-10-19 16:19–16:41 段）：兩個分支的開始與結束交錯，
 * 最後一筆開始（feat/0.5.0-W1-351）沒有對應結束，代表閘門正被它持有。
 * 另插一筆真實紀錄中分支名最長的中止結束行（取自 2026-10-15 的紀錄格式），測窄面板寬度與中止上色。
 */
export const MERGE_LOG_HOLDING = [
  '2026-10-19T16:19:45 [合併閘門] 開始｜target main｜分支 worktree-agent-a352c31d77c3daa98｜commit c6f614e51840',
  '2026-10-19T16:21:08 [合併閘門] 開始｜target main｜分支 worktree-agent-a74808594aa6f7e6f｜commit d198cdfebf44',
  '2026-10-19T16:21:11 [合併閘門] 結束｜target main｜分支 worktree-agent-a74808594aa6f7e6f｜commit fd67ce66f7e5｜結果 寫入',
  '2026-10-19T16:26:50 [合併前測試] 套件 hooks：綠燈｜7222 passed',
  '2026-10-19T16:31:50 [合併閘門] 結束｜target main｜分支 worktree-agent-a352c31d77c3daa98｜commit ca1d747c0332｜結果 寫入',
  '2026-10-15T22:15:13 [合併閘門] 結束｜target main｜分支 worktree-doc-split-338-2-5｜commit 9238cea6802f｜結果 中止',
  '2026-10-19T16:41:49 [合併前驗收] target=0.5.0-W1-351 reason=收尾',
  '2026-10-19T16:41:49 [合併閘門] 開始｜target main｜分支 feat/0.5.0-W1-351｜commit 52477a34f0ce',
  '',
].join('\n')

/**
 * 仿真實 worktree-merge.log（2026-10-19 16:19–16:31 段）的重疊合併：a352 開始後，免跑測試的 a748 開始並結束，
 * a352 才結束。兩個開始行後各有一行 328.1 之後的三行格式預檢行（帶分支與結果欄），它不是結束行。
 */
export const MERGE_LOG_OVERLAP = [
  '2026-10-19T16:19:45 [合併閘門] 開始｜target main｜分支 worktree-agent-a352c31d77c3daa98｜commit c6f614e51840',
  '2026-10-19T16:19:46 [合併閘門] 預檢｜target main｜分支 worktree-agent-a352c31d77c3daa98｜commit c6f614e51840｜結果 無衝突',
  '2026-10-19T16:21:08 [合併閘門] 開始｜target main｜分支 worktree-agent-a74808594aa6f7e6f｜commit d198cdfebf44',
  '2026-10-19T16:21:09 [合併閘門] 預檢｜target main｜分支 worktree-agent-a74808594aa6f7e6f｜commit d198cdfebf44｜結果 無衝突',
  '2026-10-19T16:21:11 [合併閘門] 結束｜target main｜分支 worktree-agent-a74808594aa6f7e6f｜commit fd67ce66f7e5｜結果 寫入',
  '2026-10-19T16:26:50 [合併前測試] 套件 hooks：綠燈｜7222 passed',
  '2026-10-19T16:31:50 [合併閘門] 結束｜target main｜分支 worktree-agent-a352c31d77c3daa98｜commit ca1d747c0332｜結果 寫入',
  '',
].join('\n')

/** 格式不符的 `[合併閘門]` 行：開始行沒有欄位、結束行沒有結果、時間戳不是 ISO 形式。 */
export const MALFORMED_GATE_LINES = [
  '2026-10-19T16:50:00 [合併閘門] 開始',
  '2026-10-19T16:51:00 [合併閘門] 結束｜target main｜分支 feat/0.5.0-W1-400｜commit abc',
  '2026-10-19 16:52:00 [合併閘門] 開始｜target main｜分支 feat/0.5.0-W1-401｜commit def',
]

/** MERGE_LOG_OVERLAP 中時間戳不晚於 time（`HH:MM:SS`）的行，模擬看板在該時刻讀到的紀錄。 */
export function overlapLogUntil(time: string): string {
  return MERGE_LOG_OVERLAP.split('\n')
    .filter(line => line.slice(11, 19) <= time)
    .join('\n')
}

/**
 * 仿票檔：frontmatter 有 status，給 title 時另有一行 `title: <title>`（原樣寫入，引號由呼叫端自帶）；
 * 本文另有 status 與 title 行，不得被當成 frontmatter。
 */
export const ticketFile = (status: string, title?: string) =>
  `---\nid: x\n${title === undefined ? '' : `title: ${title}\n`}status: ${status}\nwho: y\n---\n# body\nstatus: ignored\ntitle: ignored\n`

/** 仿 `~/.claude/sessions/<pid>.json`：只放看板用到的欄位與一個不應被保存的欄位。 */
export const sessionJson = (fields: Record<string, unknown>) =>
  JSON.stringify({ sessionId: 'x', messagingSocketPath: '/tmp/sock', ...fields })

export const session = (fields: Partial<SessionState> & { name: string; status: string }): SessionState => ({
  pid: 1,
  cwd: '/repo',
  waitingFor: null,
  statusUpdatedAt: null,
  procStart: null,
  sessionId: null,
  ...fields,
})

/**
 * 取自本機真實 session（2026-10-19，CC 2.1.303，本機時區 CST +08:00）：
 * 狀態檔 procStart 與 `TZ=UTC ps -p <pid> -o lstart=` 逐字相同（ps 輸出另帶行尾空白），
 * 不帶 TZ 的 ps 輸出為本機時間，晚 8 小時。
 */
export const REAL_PROC_START = 'Mon Oct 19 09:09:02 2026'
export const REAL_LSTART_UTC = 'Mon Oct 19 09:09:02 2026    \n'
export const REAL_LSTART_LOCAL = 'Mon Oct 19 17:09:02 2026    \n'

/** 仿 `.claude/dispatch-active.json` 的一筆 dispatches：欄位名與真實檔相同（2026-10-20 對照），預設為未結束、無票號。 */
export const dispatchJson = (fields: Record<string, unknown>) => ({
  agent_description: '描述',
  tool_use_id: 'toolu_x',
  agent_id: 'a000000000000000',
  ticket_id: '',
  files: [],
  branch_name: '',
  dispatched_at: '2026-10-19T07:57:00.000000+00:00',
  session_id: 'sid-x',
  name: 'general-purpose',
  agent_handle: '',
  work_checkout: '',
  turn_ended_at: null,
  ...fields,
})

export const dispatch = (fields: Partial<DispatchRecord> = {}): DispatchRecord => ({
  agentId: 'a1',
  name: 'general-purpose',
  sessionId: 'sid-1',
  ticketId: null,
  description: '描述',
  dispatchedAt: null,
  turnEndedAt: null,
  ...fields,
})
