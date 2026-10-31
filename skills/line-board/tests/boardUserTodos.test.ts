// Pane 的「用戶待辦」群組端到端：U1（協調票的用戶待辦行）與 U2（各線等用戶）都經看板列出、完成項不列、
// 群組位在各線群組之上、S2 以洋紅粗體顯示、沒有任何一項時為一行「用戶待辦：無」、協調票讀不到時不畫。
// 待辦行解析與顯示列的純函式在 userTodos.test.ts。

import { describe, expect, test } from 'claude-code/testing'

import { TICKET_349 } from './fixtures'
import { groupToggleKey, laneGroupId } from '../hooks/layout'
import { MERGE_LOG_PATH } from '../hooks/mergeGate'
import { ticketFileCandidates } from '../hooks/shared'
import { USER_TODOS_GROUP_ID } from '../hooks/userTodos'
import { COORDINATION_TICKET, sessionStub, startBoard } from './paneHarness'

const COORDINATION_TICKET_FILE = ticketFileCandidates(COORDINATION_TICKET)[0] ?? ''
/** 佇列票 337.3（L13 的佇列）的票檔路徑。 */
const TICKET_337_3_FILE = ticketFileCandidates('0.5.0-W1-337.3')[0] ?? ''

/** 在 TICKET_349 的 Solution 段末尾（`## Test Results` 之前）加上 lines。 */
const withSolutionLines = (lines: readonly string[]): string => TICKET_349.replace('## Test Results', `${lines.join('\n')}\n## Test Results`)

describe('Pane：用戶待辦', () => {
  test('U1 與 U2（S1、S2、S3 各一）都列出（U1 在前），完成的待辦不列；S2 洋紅粗體、其他不上色；群組位在各線群組之上', async ($, on) => {
    // L9 改寫一行帶「等用戶」註記的佇列行（S3）；其 session -3e 的 pid 已結束，不會另有 S2
    const coordination = withSolutionLines([
      '**L9 現行佇列**（graph-project-docs-manager-3e）：356（等用戶裁定）',
      '**用戶待辦**（560）：裁定標注',
      '**用戶待辦**：開 L44 session',
      '**用戶待辦**（562）：已處理的事項',
      '**用戶待辦完成**（562）：用戶已處理',
    ])
    const ticket337 = '---\nstatus: in_progress\n---\n## Solution\n**等用戶**：實測 --debug\n'
    const { ui } = await startBoard(
      $,
      on,
      sessionStub({ [`/repo/${COORDINATION_TICKET_FILE}`]: coordination, [`/repo/${TICKET_337_3_FILE}`]: ticket337 }),
    )
    const header = await ui.find({ type: 'Button', key: groupToggleKey(USER_TODOS_GROUP_ID) })
    expect(header?.text).toBe('▾ 用戶待辦（5）')
    const expected = [
      '裁定標注｜560',
      '開 L44 session｜主控',
      '等用戶裁定｜L9 356（S3）',
      '實測 --debug｜L13 337.3（S1）',
      'input needed｜L13（S2）',
    ]
    const rows = await ui.findAll({ type: 'Text', text: /｜(560|主控|L\d+)/ })
    expect(rows.map(row => row.text)).toEqual(expected)
    expect(rows.map(row => [row.props.color, row.props.bold ?? false])).toEqual([
      [undefined, false],
      [undefined, false],
      [undefined, false],
      [undefined, false],
      ['magenta', true],
    ])
    expect(await ui.find({ type: 'Text', text: /已處理的事項/ })).toBeUndefined()
    // 用戶待辦群組排在第一個線群組之前
    const drawn = JSON.stringify(await ui.drawn())
    const lane7 = await ui.find({ type: 'Button', key: groupToggleKey(laneGroupId(7)) })
    expect(drawn.indexOf('用戶待辦（5）')).toBeGreaterThanOrEqual(0)
    expect(drawn.indexOf('用戶待辦（5）')).toBeLessThan(drawn.indexOf(lane7?.text ?? '\u0000'))
    await ui.unmount()
  })

  test('按下標題列收合後不畫各項，標題列仍顯示計數', async ($, on) => {
    const coordination = withSolutionLines(['**用戶待辦**（560）：裁定標注'])
    const { ui } = await startBoard($, on, sessionStub({ [`/repo/${COORDINATION_TICKET_FILE}`]: coordination }))
    await ui.press({ key: groupToggleKey(USER_TODOS_GROUP_ID) })
    // 計數 2 = 這一行 U1，加上 sessionStub 中 L13 的 session（-1b）為 waiting 的 S2
    expect((await ui.find({ type: 'Button', key: groupToggleKey(USER_TODOS_GROUP_ID) }))?.text).toBe('▸ 用戶待辦（2）')
    expect(await ui.find({ type: 'Text', text: '裁定標注｜560' })).toBeUndefined()
    await ui.unmount()
  })

  test('沒有待辦行也沒有線在等用戶時為一行「用戶待辦：無」，不畫群組', async ($, on) => {
    const coordination = '---\nstatus: in_progress\n---\n## Solution\n**L7 現行佇列**（nobody）：351\n**用戶待辦**（1）：x\n**用戶待辦完成**（1）：y\n'
    const { ui } = await startBoard($, on, sessionStub({ [`/repo/${COORDINATION_TICKET_FILE}`]: coordination }))
    expect(await ui.find({ type: 'Text', text: /^用戶待辦：無$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: groupToggleKey(USER_TODOS_GROUP_ID) })).toBeUndefined()
    await ui.unmount()
  })

  test('session 狀態讀不到且沒有其他項目時，不寫「無」，改註明 S2 未判', async ($, on) => {
    const coordination = '---\nstatus: in_progress\n---\n## Solution\n**L7 現行佇列**（nobody）：351\n'
    const { ui } = await startBoard($, on, { files: { [`/repo/${COORDINATION_TICKET_FILE}`]: coordination } })
    expect(await ui.find({ type: 'Text', text: /^用戶待辦：無$/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /^用戶待辦：無（session 狀態讀不到，S2 未判）$/ })).toBeDefined()
    await ui.unmount()
  })

  test('協調票讀不到時不畫用戶待辦（不寫「無」）', async ($, on) => {
    const { ui } = await startBoard($, on, { files: { [`/repo/${MERGE_LOG_PATH}`]: '' }, sessionEntries: [] })
    expect(await ui.find({ type: 'Text', text: /^解析失敗：協調票讀不到/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^用戶待辦/ })).toBeUndefined()
    expect(await ui.find({ type: 'Button', key: groupToggleKey(USER_TODOS_GROUP_ID) })).toBeUndefined()
    await ui.unmount()
  })
})
