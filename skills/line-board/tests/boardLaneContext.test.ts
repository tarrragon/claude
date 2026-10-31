// 線標題的待 compact／待 clear 標記與恢復開工徽章（Pane 端到端）：標題列為 `L<n> <session>［狀態］<標記><徽章>`。

import { describe, expect, test } from 'claude-code/testing'

import { CONTEXT_USAGE_DIR } from '../hooks/contextUsage'
import { ticketFileCandidates } from '../hooks/shared'
import { sessionJson, ticketFile } from './fixtures'
import { COORDINATION_TICKET, NOW_MS, SESSIONS, sessionStub, startBoard } from './paneHarness'
import type { Stub } from './paneHarness'

const COORDINATION_TICKET_FILE = ticketFileCandidates(COORDINATION_TICKET)[0] ?? ''
const TICKET_FOLDER = COORDINATION_TICKET_FILE.slice(0, COORDINATION_TICKET_FILE.lastIndexOf('/'))
const USAGE_DIR = `/repo/${CONTEXT_USAGE_DIR}`

/**
 * 五條線：L1（f9，持有 in_progress 的 351）、L2（d7，只有 pending 的 352）、L3（1b，持有 in_progress 的 353）、
 * L4（主控，持有 in_progress 的 354）、L5（a2，已收線）。
 */
const COORDINATION = [
  '## Solution',
  '**L1 現行佇列**（graph-project-docs-manager-f9）：351',
  '**L2 現行佇列**（graph-project-docs-manager-d7）：352',
  '**L3 現行佇列**（graph-project-docs-manager-1b）：353',
  '**L4 現行佇列**（主控）：354',
  '**L5 現行佇列**（graph-project-docs-manager-a2）：（無）',
  '',
].join('\n')

/** 用量檔內容（auto-compact 關閉，以 percent 判定）。 */
const usageJson = (sessionId: string, fields: Record<string, unknown>) =>
  JSON.stringify({
    sessionId,
    phase: null,
    tokens: 0,
    window: 1_000_000,
    percent: 0,
    compactWindow: 1_000_000,
    compactPercent: 0,
    autoCompactThreshold: null,
    measuredAt: NOW_MS - 60_000,
    ...fields,
  })

/** 本機時間的 `HH:MM`。 */
const hhmm = (ms: number): string => {
  const date = new Date(ms)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

/** 協調票、佇列票檔、各 session 的用量檔，另加一個名為「主控」的存活 session（pid 108）。 */
function laneStub(usages: Record<string, string>): Stub {
  const stub = sessionStub({
    [`/repo/${COORDINATION_TICKET_FILE}`]: COORDINATION,
    [`/repo/${TICKET_FOLDER}/0.5.0-W1-351.md`]: ticketFile('in_progress', 'a'),
    [`/repo/${TICKET_FOLDER}/0.5.0-W1-352.md`]: ticketFile('pending', 'b'),
    [`/repo/${TICKET_FOLDER}/0.5.0-W1-353.md`]: ticketFile('in_progress', 'c'),
    [`/repo/${TICKET_FOLDER}/0.5.0-W1-354.md`]: ticketFile('in_progress', 'd'),
    ...Object.fromEntries(Object.entries(usages).map(([sid, text]) => [`${USAGE_DIR}/${sid}.json`, text])),
  })
  stub.files[`${SESSIONS}/108.json`] = sessionJson({ pid: 108, name: '主控', cwd: '/repo', status: 'busy', statusUpdatedAt: NOW_MS, sessionId: 'sid-108' })
  stub.sessionEntries?.push('108.json')
  return stub
}

describe('線標題的標記與恢復開工徽章', () => {
  test('正向對照：持有 in_progress 且達 45 標待 compact、未持有且達 30 標待 clear、主控達 60 標待 compact、10 分鐘內恢復開工顯示徽章', async ($, on) => {
    const resumedAt = NOW_MS - 120_000
    const stub = laneStub({
      'sid-101': usageJson('sid-101', { percent: 50 }),
      'sid-103': usageJson('sid-103', { percent: 35 }),
      'sid-102': usageJson('sid-102', { percent: 20, phase: { kind: 'resumed', source: 'compact', at: resumedAt } }),
      'sid-108': usageJson('sid-108', { percent: 60 }),
    })
    const { ui } = await startBoard($, on, stub)
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L1 graph-project-docs-manager-f9［busy］［待 compact］$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L2 graph-project-docs-manager-d7［idle］［待 clear］$/ })).toBeDefined()
    const l3 = await ui.find({ type: 'Button', text: /^[▸▾] L3 / })
    expect(l3?.text.replace(/^[▸▾] /, '')).toBe(`L3 graph-project-docs-manager-1b［waiting：input needed］［/compact 後已恢復 ${hhmm(resumedAt)}］`)
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L4 主控［busy］［待 compact］$/ })).toBeDefined()
    await ui.unmount()
  })

  test('反向對照：低於門檻、主控未達 60、compact 後無用量、收線的線不標；恢復開工超過 10 分鐘不顯示徽章', async ($, on) => {
    const stub = laneStub({
      'sid-101': usageJson('sid-101', { percent: 44 }),
      'sid-103': usageJson('sid-103', { percent: 29 }),
      'sid-102': usageJson('sid-102', {
        tokens: null,
        percent: null,
        compactPercent: null,
        phase: { kind: 'resumed', source: 'clear', at: NOW_MS - 11 * 60_000 },
      }),
      'sid-108': usageJson('sid-108', { percent: 59 }),
      'sid-107': usageJson('sid-107', { percent: 90 }),
    })
    const { ui } = await startBoard($, on, stub)
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L1 graph-project-docs-manager-f9［busy］$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L2 graph-project-docs-manager-d7［idle］$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L3 graph-project-docs-manager-1b［waiting：input needed］$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L4 主控［busy］$/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', text: /^[▸▾] L5 / })).toBeUndefined()
    expect(await ui.find({ text: /待 compact|待 clear|已恢復/ })).toBeUndefined()
    await ui.unmount()
  })
})
