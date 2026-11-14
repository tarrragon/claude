// Pane 的端到端繪製：線群組的標題列（session 狀態、目標）與票序、可折疊的各 session 與合併閘門兩區塊、協調票的兩種空狀態，
// 以及專案設定（協調票）的讀取：有設定才自動開 Pane、沒有設定時 /board 顯示設定提示、協調票與佇列票的票檔路徑推導。
// 群組的派發列、活動計數、預設展開與手動切換在 boardDispatch.test.ts；佇列細節在 boardQueue.test.ts；各 domain 的純函式在同名的 *.test.ts。
// 每個 test 以 { timeoutMs: PANE_TEST_TIMEOUT_MS } 設逾時，數值與依據見 paneHarness.ts 的 PANE_TEST_TIMEOUT_MS。

import { describe, expect, test } from 'claude-code/testing'

import {
  MALFORMED_GATE_LINES,
  MERGE_LOG,
  MERGE_LOG_HOLDING,
  NO_TICKET_LANE_LINES,
  REAL_LSTART_UTC,
  REAL_PROC_START,
  TEMPLATE_NOTE,
  TICKET_349,
  TICKET_349_GOALS,
  overlapLogUntil,
  sessionJson,
  ticketFile,
} from './fixtures'
import { GROUP_BORDER_COLUMNS } from '../hooks/lanesView'
import { GROUP_INDENT, MERGE_GATE_GROUP_ID, SESSIONS_GROUP_ID, groupToggleKey, laneGroupId } from '../hooks/layout'
import { MERGE_LOG_PATH } from '../hooks/mergeGate'
import {
  COORDINATION_TICKET,
  COORDINATION_TICKET_FILE,
  PANE_TEST_TIMEOUT_MS,
  SESSIONS,
  TICKET_FOLDER,
  cliError,
  cliMultiple,
  cliNone,
  cliOk,
  runBoardCommand,
  sessionStub,
  startBoard,
  titleOf,
} from './paneHarness'
import type { CliFailure } from './paneHarness'

/** 佇列無票號的線在標題列的標示（board-screens.md〈線群組的標題〉）：以字面寫在測試，標示文字改動時測試跟著改。 */
const QUEUE_NO_TICKET_LABEL = '［佇列無票號］'

/** 呼叫 line_status 工具，回傳工具結果文字。 */
async function callLineStatus($: Parameters<typeof runBoardCommand>[0]): Promise<string> {
  const outcome = await $.tool.call({ tool: 'mcp__line-board__line_status' } as never)
  return String((outcome as { result?: unknown }).result)
}

/**
 * 終端機顯示寬度：CJK 與全形字元占 2 欄，其餘 1 欄。
 * 測試套件只拿得到畫出的樹、拿不到終端機的實際繪製，以此推算一行在固定欄寬的面板內是否放得下。
 */
function displayWidth(text: string): number {
  let width = 0
  for (const char of text) {
    const code = char.codePointAt(0) ?? 0
    const isWide =
      (code >= 0x1100 && code <= 0x115f) ||
      (code >= 0x2e80 && code <= 0xa4cf) ||
      (code >= 0xac00 && code <= 0xd7a3) ||
      (code >= 0xf900 && code <= 0xfaff) ||
      (code >= 0xfe30 && code <= 0xfe4f) ||
      (code >= 0xff00 && code <= 0xff60) ||
      (code >= 0xffe0 && code <= 0xffe6)
    width += isWide ? 2 : 1
  }
  return width
}

describe('Pane', () => {
  test('各 session：只列本 repo（含 worktree）且 pid 存活者，waiting 最前，shell 與 busy 同組並顯示原值，未知狀態原樣；.key 從未被讀取', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui, readPaths } = await startBoard($, on, sessionStub({ [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349 }))
    const rows = await ui.findAll({ type: 'Text', text: /^(graph-project-docs-manager|blog|KEY)-/ })
    expect(rows.map(row => row.text)).toEqual([
      'graph-project-docs-manager-1b｜waiting：input needed｜12 秒前',
      'graph-project-docs-manager-a2｜shell｜30 秒前',
      'graph-project-docs-manager-f9｜busy｜1 分前',
      'graph-project-docs-manager-d7｜idle｜2 小時前',
      'graph-project-docs-manager-q1｜compacting｜0 秒前',
    ])
    expect(await ui.find({ type: 'Text', text: /^另有 1 個狀態檔的 pid 已結束/ })).toBeDefined()
    expect(readPaths.some(path => path.endsWith('.key'))).toBe(false)
    expect(readPaths.filter(path => path.startsWith(SESSIONS)).length).toBe(7)
    await ui.unmount()
  })

  test('各 session：waiting 以洋紅粗體顯示（要人處理），其他狀態不上色', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, sessionStub({ [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349 }))
    const rows = await ui.findAll({ type: 'Text', text: /^graph-project-docs-manager-/ })
    expect(rows.map(row => [row.text.split('｜')[1], row.props.color, row.props.bold ?? false])).toEqual([
      ['waiting：input needed', 'magenta', true],
      ['shell', undefined, false],
      ['busy', undefined, false],
      ['idle', undefined, false],
      ['compacting', undefined, false],
    ])
    await ui.unmount()
  })

  test('反例：pid 存在但 ps 的啟動時間與 procStart 不符時不列出、計入已結束；ps 以 TZ=UTC 執行', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const reused = { pid: 201, name: 'graph-project-docs-manager-old', cwd: '/repo', status: 'busy', procStart: REAL_PROC_START }
    const same = { pid: 202, name: 'graph-project-docs-manager-live', cwd: '/repo', status: 'idle', procStart: REAL_PROC_START }
    const { ui, psCalls } = await startBoard($, on, {
      files: {
        [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349,
        [`${SESSIONS}/201.json`]: sessionJson(reused),
        [`${SESSIONS}/202.json`]: sessionJson(same),
      },
      sessionEntries: ['201.json', '202.json'],
      lstart: { 201: 'Mon Oct 19 11:30:00 2026    \n', 202: REAL_LSTART_UTC },
    })
    const rows = await ui.findAll({ type: 'Text', text: /^graph-project-docs-manager-/ })
    expect(rows.map(row => row.text)).toEqual(['graph-project-docs-manager-live｜idle｜時間不明'])
    expect(await ui.find({ type: 'Text', text: /^另有 1 個狀態檔的 pid 已結束/ })).toBeDefined()
    const call = psCalls.find(item => item.argv[2] === '201')
    expect(call?.argv).toEqual(['ps', '-p', '201', '-o', 'lstart='])
    expect(call?.env).toEqual({ TZ: 'UTC', LC_ALL: 'C' })
    await ui.unmount()
  })

  test('線標題列 session 旁標狀態：存活者取其 status，pid 已結束或找不到的為離線', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, sessionStub({ [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349 }))
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L7 graph-project-docs-manager-f9［busy］$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L13 graph-project-docs-manager-1b［waiting：input needed］$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L9 graph-project-docs-manager-3e［離線］$/ })).toBeDefined()
    await ui.unmount()
  })

  test('線標題顯示目標：有目標行的線在標題列下一行顯示「目標：<文字>」、再下一行為活動計數，寫（無）或沒有可採用目標行的線省略目標行', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, { files: { [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349_GOALS } })
    const l13 = await titleOf(ui, laneGroupId(13))
    expect(l13?.length).toBe(3)
    expect(l13?.[0]).toMatch(/^[▸▾] L13 /)
    expect(l13?.slice(1)).toEqual(['目標：顯示各線目標與派發中代理人', expect.stringMatching(/^\d+ 排隊$/)])
    const l7 = await titleOf(ui, laneGroupId(7))
    const l9 = await titleOf(ui, laneGroupId(9))
    expect(l7?.length).toBe(2)
    expect(l9?.length).toBe(2)
    expect(l7?.join('\n')).not.toContain('目標')
    expect(l9?.join('\n')).not.toContain('目標')
    for (const ignored of ['舊目標', '清單項的目標', '表格內的目標', '反引號範本的目標', '會被清除的目標', 'Solution 之外的目標']) {
      expect(await ui.find({ text: new RegExp(ignored) })).toBeUndefined()
    }
    await ui.unmount()
  })

  test('對照：協調票沒有任何目標行時，所有線標題都沒有目標行', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, { files: { [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349 } })
    const rows = await ui.findAll({ type: 'Button', text: /^[▸▾] L\d+ / })
    expect(rows.length).toBe(3)
    for (const row of rows) expect(row.text).not.toContain('目標')
    expect(await ui.find({ type: 'Text', text: /^目標：/ })).toBeUndefined()
    await ui.unmount()
  })

  test('sessions 目錄無法列出時，各 session 區塊顯示讀取失敗，線標題列標狀態不明', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, { files: { [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349 } })
    expect(await ui.find({ type: 'Text', text: /^讀取 ~\/\.claude\/sessions 失敗/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L7 graph-project-docs-manager-f9［狀態不明］$/ })).toBeDefined()
    await ui.unmount()
  })

  test('「各 session」與「合併閘門最近紀錄」預設展開，按標題列收合後只剩標題列，再按一次展開', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard(
      $,
      on,
      sessionStub({ [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349, [`/repo/${MERGE_LOG_PATH}`]: MERGE_LOG }),
    )
    const sessionRow = { type: 'Text', text: /^graph-project-docs-manager-1b｜waiting/ }
    const gateRow = { type: 'Text', text: /^16:11:45｜結束｜/ }
    expect((await ui.find({ type: 'Button', key: groupToggleKey(SESSIONS_GROUP_ID) }))?.text).toBe('▾ 各 session')
    expect((await ui.find({ type: 'Button', key: groupToggleKey(MERGE_GATE_GROUP_ID) }))?.text).toBe('▾ 合併閘門最近紀錄')
    expect(await ui.find(sessionRow)).toBeDefined()
    expect(await ui.find(gateRow)).toBeDefined()
    await ui.press({ key: groupToggleKey(SESSIONS_GROUP_ID) })
    await ui.press({ key: groupToggleKey(MERGE_GATE_GROUP_ID) })
    expect((await ui.find({ type: 'Button', key: groupToggleKey(SESSIONS_GROUP_ID) }))?.text).toBe('▸ 各 session')
    expect((await ui.find({ type: 'Button', key: groupToggleKey(MERGE_GATE_GROUP_ID) }))?.text).toBe('▸ 合併閘門最近紀錄')
    expect(await ui.find(sessionRow)).toBeUndefined()
    expect(await ui.find(gateRow)).toBeUndefined()
    await ui.press({ key: groupToggleKey(SESSIONS_GROUP_ID) })
    expect(await ui.find(sessionRow)).toBeDefined()
    expect(await ui.find(gateRow)).toBeUndefined()
    await ui.unmount()
  })

  test('每條線一個群組（線號、session、票號與 main 的狀態），歷史票號不出現；收合的線按標題列後才列出票序；閘門區只有開始與結束', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, {
      files: {
        [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349,
        [`/repo/${TICKET_FOLDER}/0.5.0-W1-351.md`]: ticketFile('in_progress'),
        [`/wt/${TICKET_FOLDER}/0.5.0-W1-351.md`]: ticketFile('pending'),
        [`/repo/${TICKET_FOLDER}/0.5.0-W1-337.1.md`]: ticketFile('completed'),
        [`/repo/${MERGE_LOG_PATH}`]: MERGE_LOG,
      },
    })
    expect(await titleOf(ui, laneGroupId(7))).toEqual([expect.stringMatching(/^▸ L7 graph-project-docs-manager-f9［[^］]*］$/), '2 排隊'])
    expect(await ui.find({ type: 'Text', text: /^排隊：351/ })).toBeUndefined()
    await ui.press({ key: groupToggleKey(laneGroupId(7)) })
    await ui.press({ key: groupToggleKey(laneGroupId(13)) })
    expect(await ui.find({ type: 'Text', text: /^排隊：351〔in_progress〕 → 145〔unknown〕$/ })).toBeDefined()
    // 337.1 在 main 已 completed，不在佇列列中
    expect(await ui.find({ type: 'Text', text: /^排隊：337\.3〔unknown〕 → 337\.2\.1〔unknown〕$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /337\.1〔/ })).toBeUndefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L13 graph-project-docs-manager-1b［[^］]*］$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L9 / })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L11 / })).toBeUndefined()
    expect(await ui.find({ text: /328\.1|348〔/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /^16:04:26｜開始｜0\.5\.0-W1-328$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^16:11:45｜結束｜0\.5\.0-W1-328｜寫入$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^閘門使用中/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /預檢/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /\[合併前測試\]/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /^更新 \d{4}-\d{2}-\d{2} / })).toBeDefined()
    await ui.unmount()
  })

  test('面板寬 60 欄：閘門每行精簡為時間｜開始或結束｜短分支｜結果，整行放得下，持有者列在區塊最上方', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard(
      $,
      on,
      { files: { [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349, [`/repo/${MERGE_LOG_PATH}`]: MERGE_LOG_HOLDING } },
      60,
    )
    const heading = await ui.find({ type: 'Button', key: groupToggleKey(MERGE_GATE_GROUP_ID) })
    const holders = await ui.findAll({ type: 'Text', text: /^閘門使用中：/ })
    expect(holders.map(row => row.text)).toEqual(['閘門使用中：0.5.0-W1-351（自 16:41:49）'])
    const holder = holders[0]
    const rows = await ui.findAll({ type: 'Text', text: /^\d{2}:\d{2}:\d{2}｜(開始|結束)｜/ })
    expect(rows.map(row => row.text)).toEqual([
      '16:19:45｜開始｜agent-a352c3',
      '16:21:08｜開始｜agent-a74808',
      '16:21:11｜結束｜agent-a74808｜寫入',
      '16:31:50｜結束｜agent-a352c3｜寫入',
      '22:15:13｜結束｜worktree-doc-split-338-2-5｜中止',
      '16:41:49｜開始｜0.5.0-W1-351',
    ])
    // 群組外框的左右框線占 GROUP_BORDER_COLUMNS 欄、內容再縮排 GROUP_INDENT 欄，每行可用的寬度為兩者之外的部分
    for (const row of rows) expect(displayWidth(row.text)).toBeLessThanOrEqual(60 - GROUP_BORDER_COLUMNS - GROUP_INDENT)
    expect(rows.map(row => row.props.color)).toEqual([undefined, undefined, 'green', 'green', 'yellow', undefined])
    expect(await ui.find({ type: 'Text', text: /worktree-agent-/ })).toBeUndefined()
    // 持有者提示排在標題之後、第一行紀錄之前
    const drawn = JSON.stringify(await ui.drawn())
    const order = [heading?.text, holder?.text, rows[0]?.text].map(text => drawn.indexOf(text ?? '\u0000'))
    expect(order.every(index => index >= 0)).toBe(true)
    expect(order).toEqual([...order].sort((a, b) => a - b))
    await ui.unmount()
  })

  test('重疊的合併：兩個分支同時持有閘門時各列一行，依開始順序；預檢行不顯示', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, {
      files: {
        [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349,
        [`/repo/${MERGE_LOG_PATH}`]: overlapLogUntil('16:21:09'),
      },
    })
    const holders = await ui.findAll({ type: 'Text', text: /^閘門使用中：/ })
    expect(holders.map(row => row.text)).toEqual([
      '閘門使用中：agent-a352c3（自 16:19:45）',
      '閘門使用中：agent-a74808（自 16:21:08）',
    ])
    expect(holders.map(row => row.props.color)).toEqual(['yellow', 'yellow'])
    expect(await ui.find({ type: 'Text', text: /預檢/ })).toBeUndefined()
    await ui.unmount()
  })

  test('反例：格式不符的閘門行原樣顯示，其他行照常精簡', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, {
      files: {
        [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349,
        [`/repo/${MERGE_LOG_PATH}`]: [MERGE_LOG, ...MALFORMED_GATE_LINES].join('\n'),
      },
    })
    for (const line of MALFORMED_GATE_LINES) {
      expect((await ui.find({ type: 'Text', text: line }))?.text).toBe(line)
    }
    expect(await ui.find({ type: 'Text', text: /^16:11:45｜結束｜0\.5\.0-W1-328｜寫入$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: `讀取 ${MERGE_LOG_PATH} 失敗` })).toBeUndefined()
    await ui.unmount()
  })

  test('協調票讀得到但沒有任何現行佇列行時顯示「協調票尚無現行佇列行」', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, {
      files: {
        [`/repo/${COORDINATION_TICKET_FILE}`]: `---\nstatus: pending\n---\n## Solution\n${TEMPLATE_NOTE}\n`,
        [`/repo/${MERGE_LOG_PATH}`]: '',
      },
      sessionEntries: [],
    })
    expect(await ui.find({ type: 'Text', text: /^協調票尚無現行佇列行$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^解析失敗/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /^（本 repo 沒有執行中的 session）$/ })).toBeDefined()
    await ui.unmount()
  })

  test('對照：協調票檔讀不到時顯示「解析失敗：協調票讀不到」與票檔路徑，而非「尚無現行佇列行」', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, { files: { [`/wt/${COORDINATION_TICKET_FILE}`]: TICKET_349 } })
    expect(await ui.find({ type: 'Text', text: new RegExp(`^解析失敗：協調票讀不到（${COORDINATION_TICKET_FILE}：`) })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /尚無現行佇列行/ })).toBeUndefined()
    await ui.unmount()
  })

  test('佇列行只含非票號文字的線，標題列標「佇列無票號」（E2）；同一協調票含票號的線不標（E1 對照）', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const text = `## Solution\n${NO_TICKET_LANE_LINES}\n`
    const { ui } = await startBoard($, on, { files: { [`/repo/${COORDINATION_TICKET_FILE}`]: text } })
    for (const lane of [5, 6, 9]) {
      expect((await titleOf(ui, laneGroupId(lane)))?.[0]).toContain(QUEUE_NO_TICKET_LABEL)
    }
    // 附說明的收線寫法標［收線寫法］，與 line_status 的過期項同類，不標［佇列無票號］
    const endedTitle = (await titleOf(ui, laneGroupId(10)))?.[0]
    expect(endedTitle).toContain('［收線寫法］')
    expect(endedTitle).not.toContain(QUEUE_NO_TICKET_LABEL)
    for (const lane of [7, 8]) {
      const title = await titleOf(ui, laneGroupId(lane))
      expect(title?.[0]).toMatch(new RegExp(`^[▸▾] L${lane} `))
      expect(title?.[0]).not.toContain(QUEUE_NO_TICKET_LABEL)
    }
    await ui.unmount()
  })
})

describe('專案設定', () => {
  /** 有設定與沒有設定兩組共用的 fixture：協調票、session 狀態檔與佇列票的票檔。 */
  const sharedFiles = () =>
    sessionStub({
      [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349,
      [`/repo/${TICKET_FOLDER}/0.5.0-W1-351.md`]: ticketFile('in_progress'),
    })

  test('有設定：session 啟動時自動開 Pane 並畫出各線，/board 已註冊', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui, opened, registered } = await startBoard($, on, sharedFiles())
    expect(opened).toEqual(['line-board'])
    expect(registered).toEqual(['board'])
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L7 / })).toBeDefined()
    await ui.unmount()
  })

  test('對照：同一批 fixture 協調票 0 張時不自動開 Pane、不讀協調票檔也不定時讀取，/board 仍註冊', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui, opened, registered, readPaths, cliCwds, clock } = await startBoard($, on, { ...sharedFiles(), projectConfig: null })
    expect(opened).toEqual([])
    expect(registered).toEqual(['board'])
    await clock.advance(30_000)
    // 啟動時先對 session root（/wt）跑解析 CLI，0 張再對主 checkout 跑；定時讀取不啟動，所以只有這兩次，也沒有讀任何檔案
    expect(cliCwds).toEqual(['/wt', '/repo'])
    expect(readPaths).toEqual([])
    await ui.unmount()
  })

  test('session 在主 checkout 啟動且有設定：開 Pane 先於任何 git 呼叫（E1）', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui, opened, callOrder } = await startBoard($, on, { ...sharedFiles(), sessionRoot: '/repo' })
    expect(opened).toEqual(['line-board'])
    expect(callOrder[0]).toBe('ui.open line-board')
    await ui.unmount()
  })

  test('對照：session 在 worktree 啟動時，root 讀不到設定，先跑 git worktree list 找主 checkout 再開 Pane（E1）', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui, opened, callOrder } = await startBoard($, on, sharedFiles())
    expect(opened).toEqual(['line-board'])
    expect(callOrder[0]).toBe('git worktree list --porcelain')
    expect(callOrder.indexOf('ui.open line-board')).toBeGreaterThan(0)
    await ui.unmount()
  })

  test('對照：session 在主 checkout 啟動但協調票 0 張時不開 Pane，解析 CLI 只跑一次', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui, opened, cliCwds } = await startBoard($, on, { ...sharedFiles(), sessionRoot: '/repo', projectConfig: null })
    expect(opened).toEqual([])
    expect(cliCwds).toEqual(['/repo'])
    await ui.unmount()
  })

  test('啟動檢查丟例外時，失敗原因寫入 transcript（使用者可見）（E2）', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui, opened, logs } = await startBoard($, on, { ...sharedFiles(), rootError: 'session root 讀取失敗' })
    expect(opened).toEqual([])
    expect(logs.filter(log => log.to === 'transcript' && log.text.startsWith('line-board 啟動檢查失敗'))).toHaveLength(1)
    await ui.unmount()
  })

  test('對照：啟動檢查沒有例外時，transcript 沒有啟動檢查失敗的行（E2）', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui, opened, logs } = await startBoard($, on, sharedFiles())
    expect(opened).toEqual(['line-board'])
    expect(logs.filter(log => log.text.startsWith('line-board 啟動檢查失敗'))).toEqual([])
    await ui.unmount()
  })

  const NONE_REASON = /^尚未設定協調票：active 版本沒有標記 `coordination: true` 的進行中票$/

  /** 協調票不成立的情形：名稱、解析 CLI 的回應、提示行的原因、另須出現的行。 */
  const UNSET_CASES: [string, { projectConfig?: string; cliFailure?: CliFailure }, RegExp, (string | RegExp)[]][] = [
    ['0 張', { projectConfig: cliNone() }, NONE_REASON, [/^補法：.*ticket create --coordination/]],
    [
      '多張',
      { projectConfig: cliMultiple(['0.5.0-W1-349', '0.6.0-W1-099']) },
      /^尚未設定協調票：有多張標記 coordination: true 的進行中票，不自行擇一，請用戶裁定$/,
      ['候選：0.5.0-W1-349', '候選：0.6.0-W1-099'],
    ],
    ['CLI 回報 error', { projectConfig: cliError('todolist 不可用：ENOENT') }, /^尚未設定協調票：協調票解析失敗（todolist 不可用：ENOENT）$/, []],
    [
      'CLI 不可用（python3 無法執行）',
      { cliFailure: { throws: 'spawn python3 ENOENT' } },
      /^尚未設定協調票：協調票解析失敗（python3 無法執行（.*spawn python3 ENOENT/,
      [],
    ],
    [
      'CLI 非零結束且 stdout 不是 JSON',
      { cliFailure: { exitCode: 127, stdout: '', stderr: 'python3: command not found' } },
      /^尚未設定協調票：協調票解析失敗（解析 CLI 失敗（exit 127）：python3: command not found）$/,
      [],
    ],
    ['CLI 輸出不是 JSON', { cliFailure: { exitCode: 0, stdout: 'hello', stderr: '' } }, /^尚未設定協調票：協調票解析失敗（輸出不是有效的 JSON/, []],
  ]

  for (const [name, stubPart, reason, extraLines] of UNSET_CASES) {
    test(`${name}：不自動開 Pane；執行 /board 後開啟並顯示原因，不畫線群組也不擇一`, { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
      const { ui, opened, readPaths } = await startBoard($, on, { ...sharedFiles(), ...stubPart })
      expect(opened).toEqual([])
      await runBoardCommand($)
      expect(opened).toEqual(['line-board'])
      expect(await ui.find({ type: 'Text', text: reason })).toBeDefined()
      for (const line of extraLines) expect(await ui.find({ type: 'Text', text: line })).toBeDefined()
      expect(await ui.find({ type: 'Button', text: /^[▸▾] L\d+ / })).toBeUndefined()
      expect(readPaths).not.toContain(`/repo/${COORDINATION_TICKET_FILE}`)
      await ui.unmount()
    })
  }

  {
    const cases: [{ projectConfig?: string; cliFailure?: CliFailure }, RegExp][] = [
      // 先問用戶再補法（line-continuity §3）：舊版「；補法：」緊接成因，不符本 regex 的順序
      [
        { projectConfig: cliNone() },
        /^line_status 無法判讀：active 版本沒有標記 `coordination: true` 的進行中票；不自行判定單一線，先以 AskUserQuestion 問用戶開工作線或單一線.*；用戶選開工作線時才建協調票，補法：.*ticket create --coordination/,
      ],
      [
        { projectConfig: cliMultiple(['0.5.0-W1-349', '0.6.0-W1-099']) },
        /^line_status 無法判讀：active 版本有多張標記 coordination: true 的進行中票，不自行擇一，請用戶裁定：0\.5\.0-W1-349、0\.6\.0-W1-099/,
      ],
      [{ cliFailure: { throws: 'spawn python3 ENOENT' } }, /^line_status 無法判讀：協調票解析失敗：python3 無法執行（.*spawn python3 ENOENT/],
      [{ projectConfig: cliError('todolist 不可用：ENOENT') }, /^line_status 無法判讀：協調票解析失敗：todolist 不可用：ENOENT/],
    ]
    cases.forEach(([stubPart, expected], index) => {
      test(`line_status：協調票不成立（情形 ${index + 1}）回傳原因文字，不拋出也不讀協調票檔`, { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
        const { ui, readPaths } = await startBoard($, on, { ...sharedFiles(), sessionRoot: '/repo', ...stubPart })
        expect(await callLineStatus($)).toMatch(expected)
        expect(readPaths).not.toContain(`/repo/${COORDINATION_TICKET_FILE}`)
        await ui.unmount()
      })
    })
  }

  test('line_status：1 張時照常判讀，解析警告列在輸出', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const warning = '覆寫的協調票 0.5.0-W1-349 已結案，改用自動解析'
    const { ui } = await startBoard($, on, { ...sharedFiles(), sessionRoot: '/repo', projectConfig: cliOk(COORDINATION_TICKET, [warning]) })
    const text = await callLineStatus($)
    expect(text).toContain(`各線接續狀態（協調票 ${COORDINATION_TICKET}`)
    expect(text).toContain(`協調票解析警告：${warning}`)
    await ui.unmount()
  })

  test('對照：協調票 0 張時執行 /board 顯示提示；標記補上後再執行 /board 畫出各線', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const stub = { ...sharedFiles(), projectConfig: null as string | null }
    const { ui } = await startBoard($, on, stub)
    await runBoardCommand($)
    expect(await ui.find({ type: 'Text', text: /^尚未設定協調票：/ })).toBeDefined()
    stub.projectConfig = cliOk('0.5.0-W1-349')
    await runBoardCommand($)
    expect(await ui.find({ type: 'Text', text: /^尚未設定協調票：/ })).toBeUndefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L7 / })).toBeDefined()
    await ui.unmount()
  })

  test('協調票檔的路徑由設定的票號推導：協調票不是預設票號時讀 hierarchical 路徑', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const path = '/repo/docs/work-logs/v0/v0.6/v0.6.0/tickets/0.6.0-W2-010.md'
    const { ui, readPaths } = await startBoard($, on, {
      files: { [path]: TICKET_349 },
      projectConfig: cliOk('0.6.0-W2-010'),
    })
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L7 / })).toBeDefined()
    expect(readPaths).toContain(path)
    expect(readPaths).not.toContain(`/repo/${COORDINATION_TICKET_FILE}`)
    await ui.unmount()
  })

  test('佇列短票號以設定的協調票推導的前綴補全：兩個不同協調票讀同一佇列，各讀自己版本與 wave 的票檔（E1 對照）', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const stub = {
      files: {
        [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349,
        '/repo/docs/work-logs/v0/v0.6/v0.6.0/tickets/0.6.0-W2-010.md': TICKET_349,
      },
      projectConfig: cliOk(COORDINATION_TICKET),
    }
    const { ui, readPaths, clock } = await startBoard($, on, stub)
    const queueReads = () => readPaths.splice(0).filter(path => path.endsWith('-351.md'))
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L7 / })).toBeDefined()
    const under05 = queueReads()
    // 對照：同一份協調票內容，設定檔改為另一版本與 wave 的協調票後重讀
    stub.projectConfig = cliOk('0.6.0-W2-010')
    await clock.advance(30_000)
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L7 / })).toBeDefined()
    const under06 = queueReads()
    await ui.unmount()
    expect(under05).not.toEqual(under06)
    expect(under05).toContain(`/repo/${TICKET_FOLDER}/0.5.0-W1-351.md`)
    expect(under06).toContain('/repo/docs/work-logs/v0/v0.6/v0.6.0/tickets/0.6.0-W2-351.md')
    expect(under06.some(path => path.includes('0.5.0-W1-'))).toBe(false)
  })

  test('對照：協調票只有 flat 票檔時先試 hierarchical、再退回 flat 路徑', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const hierarchical = '/repo/docs/work-logs/v0/v0.6/v0.6.0/tickets/0.6.0-W2-010.md'
    const flat = '/repo/docs/work-logs/v0.6.0/tickets/0.6.0-W2-010.md'
    const { ui, readPaths } = await startBoard($, on, {
      files: { [flat]: TICKET_349 },
      projectConfig: cliOk('0.6.0-W2-010'),
    })
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L7 / })).toBeDefined()
    expect(readPaths.indexOf(hierarchical)).toBeGreaterThanOrEqual(0)
    expect(readPaths.indexOf(hierarchical)).toBeLessThan(readPaths.indexOf(flat))
    await ui.unmount()
  })

  test('佇列票的票檔路徑由票號推導：票檔只在 flat 路徑時退回讀取', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, {
      files: {
        [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349,
        '/repo/docs/work-logs/v0.5.0/tickets/0.5.0-W1-351.md': ticketFile('in_progress'),
      },
    })
    await ui.press({ key: groupToggleKey(laneGroupId(7)) })
    expect(await ui.find({ type: 'Text', text: /^排隊：351〔in_progress〕 → 145〔unknown〕$/ })).toBeDefined()
    await ui.unmount()
  })
})
