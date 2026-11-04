// Pane 線群組的佇列細節：細節按鍵的預設收合與手動展開、各行的短票號／狀態／title 與五色上色，以及佇列票全部完成時沒有細節按鍵的對照。
// 線群組的標題列與票序、各 session 與合併閘門兩區塊、專案設定在 board.test.ts；派發列與活動計數在 boardDispatch.test.ts。
// 每個 test 以 { timeoutMs: PANE_TEST_TIMEOUT_MS } 設逾時，數值與依據見 paneHarness.ts 的 PANE_TEST_TIMEOUT_MS。

import { describe, expect, test } from 'claude-code/testing'

import { TICKET_349, ticketFile } from './fixtures'
import { laneDetailId } from '../hooks/queueView'
import { groupBodyKey, groupToggleKey, laneGroupId } from '../hooks/layout'
import { COORDINATION_TICKET_FILE, PANE_TEST_TIMEOUT_MS, TICKET_FOLDER, startBoard, textsOf } from './paneHarness'
import type { Ui } from './paneHarness'

describe('Pane', () => {
  /**
   * 佇列細節的票檔：L7 的 351 在 main 為 in_progress 並有 title（worktree 副本的 title 不同）、145 沒有票檔；
   * L13 的 337.1 已完成、337.3 為 pending 並有 title、337.2.1 沒有票檔。
   */
  const detailFiles = (): Record<string, string> => ({
    [`/repo/${COORDINATION_TICKET_FILE}`]: TICKET_349,
    [`/repo/${TICKET_FOLDER}/0.5.0-W1-351.md`]: ticketFile('in_progress', '實作看板細節'),
    [`/wt/${TICKET_FOLDER}/0.5.0-W1-351.md`]: ticketFile('pending', 'WORKTREE 舊副本的 title'),
    [`/repo/${TICKET_FOLDER}/0.5.0-W1-337.1.md`]: ticketFile('completed', '已完成的票'),
    [`/repo/${TICKET_FOLDER}/0.5.0-W1-337.3.md`]: ticketFile('pending', "'等待排程的票'"),
  })

  /** 線群組的佇列細節各行；細節收合（未畫出）時為 undefined。 */
  async function detailOf(ui: Ui, laneId: string): Promise<string[] | undefined> {
    const box = await ui.find({ type: 'Box', key: groupBodyKey(laneDetailId(laneId)) })
    return box === undefined ? undefined : textsOf(box.children)
  }

  test('佇列細節：有佇列列的線群組各有一個細節按鍵，預設收合；按下後逐張列出未完成佇列票的短票號、狀態與 title，title 只讀主 checkout、讀不到時標明', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, { files: detailFiles() })
    await ui.press({ key: groupToggleKey(laneGroupId(7)) })
    await ui.press({ key: groupToggleKey(laneGroupId(13)) })
    for (const id of [laneGroupId(7), laneGroupId(13)]) {
      expect((await ui.find({ type: 'Button', key: groupToggleKey(laneDetailId(id)) }))?.text).toBe('▸ 佇列細節')
      expect(await detailOf(ui, id)).toBeUndefined()
    }
    // 佇列列維持一行
    expect(await ui.find({ type: 'Text', text: /^排隊：351〔in_progress〕 → 145〔unknown〕$/ })).toBeDefined()
    await ui.press({ key: groupToggleKey(laneDetailId(laneGroupId(7))) })
    await ui.press({ key: groupToggleKey(laneDetailId(laneGroupId(13))) })
    expect((await ui.find({ type: 'Button', key: groupToggleKey(laneDetailId(laneGroupId(7))) }))?.text).toBe('▾ 佇列細節')
    expect(await detailOf(ui, laneGroupId(7))).toEqual(['351｜in_progress｜實作看板細節', '145｜unknown｜（讀不到 title）'])
    // 337.1 已 completed，不列
    expect(await detailOf(ui, laneGroupId(13))).toEqual(['337.3｜pending｜等待排程的票', '337.2.1｜unknown｜（讀不到 title）'])
    expect(await ui.find({ text: /已完成的票|WORKTREE/ })).toBeUndefined()
    await ui.unmount()
  })

  test('佇列細節：各行依佇列票的五色狀態上色、以 truncate-end 截斷', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui } = await startBoard($, on, { files: detailFiles() })
    for (const id of [laneGroupId(7), laneGroupId(13)]) {
      await ui.press({ key: groupToggleKey(id) })
      await ui.press({ key: groupToggleKey(laneDetailId(id)) })
    }
    const rows = await ui.findAll({ type: 'Text', text: /^\d{3}[\d.]*｜/ })
    expect(rows.map(row => [row.text.split('｜')[0], row.props.color, row.props.wrap])).toEqual([
      ['351', 'green', 'truncate-end'],
      ['145', undefined, 'truncate-end'],
      ['337.3', 'gray', 'truncate-end'],
      ['337.2.1', undefined, 'truncate-end'],
    ])
    await ui.unmount()
  })

  test('佇列細節：手動展開不被 30 秒刷新覆寫，收合群組再展開後仍維持；再按一次細節按鍵收合', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const { ui, clock } = await startBoard($, on, { files: detailFiles() })
    await ui.press({ key: groupToggleKey(laneGroupId(7)) })
    await ui.press({ key: groupToggleKey(laneDetailId(laneGroupId(7))) })
    await clock.advance(30_000)
    expect(await detailOf(ui, laneGroupId(7))).toEqual(['351｜in_progress｜實作看板細節', '145｜unknown｜（讀不到 title）'])
    await ui.press({ key: groupToggleKey(laneGroupId(7)) })
    expect(await detailOf(ui, laneGroupId(7))).toBeUndefined()
    await ui.press({ key: groupToggleKey(laneGroupId(7)) })
    expect(await detailOf(ui, laneGroupId(7))).toBeDefined()
    await ui.press({ key: groupToggleKey(laneDetailId(laneGroupId(7))) })
    expect(await detailOf(ui, laneGroupId(7))).toBeUndefined()
    expect((await ui.find({ type: 'Button', key: groupToggleKey(laneDetailId(laneGroupId(7))) }))?.text).toBe('▸ 佇列細節')
    await ui.unmount()
  })

  test('對照：佇列票全部完成的線沒有佇列列，也沒有細節按鍵', { timeoutMs: PANE_TEST_TIMEOUT_MS }, async ($, on) => {
    const files = detailFiles()
    files[`/repo/${TICKET_FOLDER}/0.5.0-W1-351.md`] = ticketFile('completed', '實作看板細節')
    files[`/repo/${TICKET_FOLDER}/0.5.0-W1-145.md`] = ticketFile('completed')
    const { ui } = await startBoard($, on, { files })
    await ui.press({ key: groupToggleKey(laneGroupId(7)) })
    await ui.press({ key: groupToggleKey(laneGroupId(13)) })
    expect(await ui.find({ type: 'Button', key: groupToggleKey(laneDetailId(laneGroupId(7))) })).toBeUndefined()
    expect(await ui.find({ type: 'Button', key: groupToggleKey(laneDetailId(laneGroupId(13))) })).toBeDefined()
    await ui.unmount()
  })
})
