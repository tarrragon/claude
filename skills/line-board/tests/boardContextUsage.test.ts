// 「各 session」列的 context 用量字尾（Pane 端到端）：只讀存活 session 的用量檔，有檔加字尾、沒有檔不加。

import { describe, expect, test } from 'claude-code/testing'

import { CONTEXT_USAGE_DIR } from '../hooks/contextUsage'
import { ticketFileCandidates } from '../hooks/shared'
import { COORDINATION_TICKET, NOW_MS, sessionStub, startBoard } from './paneHarness'

const COORDINATION_TICKET_FILE = ticketFileCandidates(COORDINATION_TICKET)[0] ?? ''
const USAGE_DIR = `/repo/${CONTEXT_USAGE_DIR}`

/** 用量檔內容（583.1 寫出的形狀，auto-compact 關閉）。 */
const usageJson = (sessionId: string, fields: Record<string, unknown>) =>
  JSON.stringify({
    sessionId,
    phase: null,
    tokens: 420_000,
    window: 1_000_000,
    percent: 42,
    compactWindow: 1_000_000,
    compactPercent: 42,
    autoCompactThreshold: null,
    measuredAt: NOW_MS - 180_000,
    ...fields,
  })

describe('各 session 列的用量字尾', () => {
  test('正向對照：有用量檔的 session 行尾加「ctx <百分比>%（距今）」；compact 後無用量寫「ctx 未量測」；沒有用量檔的不加', async ($, on) => {
    const stub = sessionStub({
      [`/repo/${COORDINATION_TICKET_FILE}`]: '## Solution\n',
      [`${USAGE_DIR}/sid-101.json`]: usageJson('sid-101', {}),
      [`${USAGE_DIR}/sid-103.json`]: usageJson('sid-103', { tokens: null, percent: null, compactPercent: null, measuredAt: NOW_MS - 30_000 }),
    })
    const { ui } = await startBoard($, on, stub)
    const rows = await ui.findAll({ type: 'Text', text: /^graph-project-docs-manager-(f9|d7|1b)｜/ })
    expect(rows.map(row => row.text)).toEqual([
      'graph-project-docs-manager-1b｜waiting：input needed｜12 秒前',
      'graph-project-docs-manager-f9｜busy｜1 分前｜ctx 42%（3 分前）',
      'graph-project-docs-manager-d7｜idle｜2 小時前｜ctx 未量測（30 秒前）',
    ])
    await ui.unmount()
  })

  test('反向對照：已結束 session（pid 106）的用量檔不讀；sessionId 不符的用量檔不採用', async ($, on) => {
    const stub = sessionStub({
      [`/repo/${COORDINATION_TICKET_FILE}`]: '## Solution\n',
      [`${USAGE_DIR}/sid-106.json`]: usageJson('sid-106', {}),
      [`${USAGE_DIR}/sid-101.json`]: usageJson('someone-else', {}),
    })
    const { ui, readPaths } = await startBoard($, on, stub)
    expect(readPaths).not.toContain(`${USAGE_DIR}/sid-106.json`)
    const row = await ui.find({ type: 'Text', text: /^graph-project-docs-manager-f9｜/ })
    expect(row?.text).toBe('graph-project-docs-manager-f9｜busy｜1 分前')
    await ui.unmount()
  })
})
