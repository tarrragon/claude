// layout.ts 的測試：以線分組、活動計數、預設展開、手動切換的展開狀態與群組的顯示文字。

import { describe, expect, test } from 'claude-code/testing'

import type { DispatchRow, GroupActivity } from '../types'
import { TICKET_349, session } from './fixtures'
import { parseLanes } from '../hooks/lanes'
import {
  OTHER_GROUP_ID,
  formatActivity,
  formatGateTicket,
  formatGroupDispatchRow,
  formatGroupTitle,
  formatQueueRow,
  isDefaultExpanded,
  isGroupExpanded,
  laneGroupId,
  laneGroups,
  queueRowSegments,
  toggledOverrides,
} from '../hooks/layout'

/** TICKET_349 的線：L7（f9）351 → 145、L9（3e）356 → 353.1 ∥ 341.2.1 → 284、L13（1b）337.1 → 337.3 → 337.2.1。 */
const LANES = parseLanes(TICKET_349, '0.5.0-W1-')

const row = (fields: Partial<DispatchRow> = {}): DispatchRow => ({
  lane: null,
  name: 'general-purpose',
  task: '描述',
  stage: '實作',
  dispatchedAt: null,
  ...fields,
})

const NO_CONTEXT = { sessions: [], tickets: [], holders: [] }

const idle: GroupActivity = { dispatching: 0, inGate: 0, isWaiting: false, queued: 3 }

describe('laneGroups', () => {
  test('每條線一個群組，依線號排序，派發列歸到所屬線；對不到線的派發歸最後的「其他」', () => {
    const rows = [row({ lane: 13, task: '337.9' }), row({ lane: null, task: '345', stage: '收尾' }), row({ lane: 7, task: 'A' })]
    const groups = laneGroups(LANES, rows, NO_CONTEXT)
    expect(groups.map(group => group.id)).toEqual([laneGroupId(7), laneGroupId(9), laneGroupId(13), OTHER_GROUP_ID])
    expect(groups.map(group => group.dispatches.map(item => item.task))).toEqual([['A'], [], ['337.9'], ['345']])
    expect(groups[3]?.lane).toBeNull()
  })

  test('對照：沒有對不到線的派發時，不產生「其他」群組', () => {
    const groups = laneGroups(LANES, [row({ lane: 7 })], NO_CONTEXT)
    expect(groups.map(group => group.id)).toEqual([laneGroupId(7), laneGroupId(9), laneGroupId(13)])
  })

  test('線列表為空（349 讀不到或尚無現行佇列行）時，所有派發都在「其他」', () => {
    const groups = laneGroups([], [row({ lane: null }), row({ lane: null })], NO_CONTEXT)
    expect(groups.map(group => [group.id, group.dispatches.length])).toEqual([[OTHER_GROUP_ID, 2]])
  })

  test('活動計數：派發列數、閘門（派發列階段為閘門 + 佇列票的 feat 分支持有閘門）、session 為 waiting、排隊票（completed 不計，讀不到狀態的照計）', () => {
    const rows = [row({ lane: 13, task: '337.9' }), row({ lane: 13, task: '351', stage: '閘門' })]
    const groups = laneGroups(LANES, rows, {
      sessions: [session({ name: 'graph-project-docs-manager-1b', status: 'waiting' })],
      tickets: [
        { id: '0.5.0-W1-337.1', status: 'completed' },
        { id: '0.5.0-W1-337.3', status: 'pending' },
      ],
      holders: [{ branch: 'feat/0.5.0-W1-337.3', since: '16:41:49' }],
    })
    const l13 = groups.find(group => group.id === laneGroupId(13))
    expect(l13?.gateTickets).toEqual([{ serial: '337.3', since: '16:41:49' }])
    expect(l13?.activity).toEqual({ dispatching: 2, inGate: 2, isWaiting: true, queued: 2 })
    // 對照：同一份 context 下 L9 沒有任何活動，只有排隊票
    const l9 = groups.find(group => group.id === laneGroupId(9))
    expect(l9?.activity).toEqual({ dispatching: 0, inGate: 0, isWaiting: false, queued: 4 })
  })

  test('佇列票的 feat 分支持有閘門、而同組已有該票標閘門的派發列時，不重複列為閘門票', () => {
    const groups = laneGroups(LANES, [row({ lane: 7, task: '351', stage: '閘門' })], {
      ...NO_CONTEXT,
      holders: [{ branch: 'feat/0.5.0-W1-351', since: '16:41:49' }],
    })
    const l7 = groups.find(group => group.id === laneGroupId(7))
    expect(l7?.gateTickets).toEqual([])
    expect(l7?.activity.inGate).toBe(1)
  })

  test('閘門持有者不是佇列票的 feat 分支（worktree-agent 分支、其他線的票）時，不算該線的閘門票', () => {
    const groups = laneGroups(LANES, [], {
      ...NO_CONTEXT,
      holders: [
        { branch: 'worktree-agent-a352c31d77c3daa98', since: '16:19:45' },
        { branch: 'feat/0.5.0-W1-351', since: '16:41:49' },
      ],
    })
    expect(groups.map(group => group.gateTickets.map(gate => gate.serial))).toEqual([['351'], [], []])
  })
})

describe('isDefaultExpanded', () => {
  test('有派發中代理人、session 為 waiting、或有票在閘門中，任一成立即預設展開', () => {
    expect(isDefaultExpanded({ ...idle, dispatching: 1 })).toBe(true)
    expect(isDefaultExpanded({ ...idle, isWaiting: true })).toBe(true)
    expect(isDefaultExpanded({ ...idle, inGate: 1 })).toBe(true)
  })

  test('反例：三者皆無時預設收合，只有排隊票不算活動', () => {
    expect(isDefaultExpanded(idle)).toBe(false)
    expect(isDefaultExpanded({ ...idle, queued: 0 })).toBe(false)
  })
})

describe('isGroupExpanded / toggledOverrides', () => {
  test('沒有手動狀態時依預設；手動狀態優先於預設，兩個方向皆同', () => {
    expect(isGroupExpanded('lane:7', true, {})).toBe(true)
    expect(isGroupExpanded('lane:7', false, {})).toBe(false)
    expect(isGroupExpanded('lane:7', true, { 'lane:7': false })).toBe(false)
    expect(isGroupExpanded('lane:7', false, { 'lane:7': true })).toBe(true)
    expect(isGroupExpanded('lane:9', false, { 'lane:7': true })).toBe(false)
  })

  test('切換：把該群組記成目前狀態的相反，其他群組的手動狀態保留，不改動傳入的物件', () => {
    const before = { 'lane:9': true }
    const after = toggledOverrides(before, 'lane:7', true)
    expect(after).toEqual({ 'lane:9': true, 'lane:7': false })
    expect(before).toEqual({ 'lane:9': true })
    expect(toggledOverrides(after, 'lane:7', false)).toEqual({ 'lane:9': true, 'lane:7': true })
  })
})

describe('群組的顯示文字', () => {
  test('活動計數只列不為零的項目，以「 · 」分隔；全無時為空字串', () => {
    expect(formatActivity({ dispatching: 2, inGate: 1, isWaiting: true, queued: 3 })).toBe('2 派發中 · 1 閘門 · 等你處理 · 3 排隊')
    expect(formatActivity({ dispatching: 0, inGate: 0, isWaiting: false, queued: 4 })).toBe('4 排隊')
    expect(formatActivity({ dispatching: 0, inGate: 0, isWaiting: false, queued: 0 })).toBe('')
  })

  test('標題列：展開為 ▾、收合為 ▸，各段以「｜」分隔，空段略過', () => {
    expect(formatGroupTitle(['L7', 's［busy］', '', '2 派發中'], true)).toBe('▾ L7｜s［busy］｜2 派發中')
    expect(formatGroupTitle(['L9', 's［離線］', '4 排隊'], false)).toBe('▸ L9｜s［離線］｜4 排隊')
  })

  test('群組內的派發列不帶線號：代理人｜任務｜階段｜距派發時間；缺派發時間為時間不明', () => {
    const nowMs = Date.UTC(2026, 9, 19, 8, 0, 0)
    expect(formatGroupDispatchRow(row({ lane: 7, name: 'linux', task: '337.8', stage: '審查', dispatchedAt: '2026-10-19T07:57:00+00:00' }), nowMs)).toBe(
      'linux｜337.8｜審查｜3 分前',
    )
    expect(formatGroupDispatchRow(row({ lane: 7, name: 'linux', task: '337.8', stage: '審查', dispatchedAt: null }), nowMs)).toBe(
      'linux｜337.8｜審查｜時間不明',
    )
  })

  test('佇列列不列 completed 的票：相鄰的分隔符併成一個（任一為 → 時為 →），首尾的分隔符去掉；沒有未完成的票時為 null', () => {
    const [l7, l9, l13] = LANES
    const done = (...serials: string[]) => serials.map(serial => ({ id: `0.5.0-W1-${serial}`, status: 'completed' }))
    expect(formatQueueRow(l13?.tokens ?? [], done('337.1'))).toBe('排隊：337.3 → 337.2.1')
    expect(formatQueueRow(l9?.tokens ?? [], done('353.1'))).toBe('排隊：356 → 341.2.1 → 284')
    expect(formatQueueRow(l9?.tokens ?? [], done('341.2.1', '284'))).toBe('排隊：356 → 353.1')
    expect(formatQueueRow(l7?.tokens ?? [], done('351', '145'))).toBeNull()
  })

  test('閘門票列與佇列列', () => {
    expect(formatGateTicket({ serial: '351', since: '16:41:49' })).toBe('閘門｜351｜自 16:41:49')
    const tokens = LANES[0]?.tokens ?? []
    expect(formatQueueRow(tokens, [{ id: '0.5.0-W1-351', status: 'in_progress' }])).toBe('排隊：351〔in_progress〕 → 145')
  })

  test('佇列列的分段：每張票一段（附完整票號與短票號），分隔符為不帶票的段；completed 的票不在其中、相鄰分隔符併成一個', () => {
    const [l7, l9] = LANES
    const tickets = [
      { id: '0.5.0-W1-351', status: 'in_progress' },
      { id: '0.5.0-W1-353.1', status: 'completed' },
    ]
    expect(queueRowSegments(l7?.tokens ?? [], tickets)).toEqual([
      { text: '351〔in_progress〕', ticket: { id: '0.5.0-W1-351', serial: '351' } },
      { text: ' → ', ticket: null },
      { text: '145', ticket: { id: '0.5.0-W1-145', serial: '145' } },
    ])
    // L9：356 → 353.1 ∥ 341.2.1 → 284，353.1 完成後兩側的 → 與 ∥ 併成 →
    const l9Segments = queueRowSegments(l9?.tokens ?? [], tickets)
    expect(l9Segments?.map(segment => segment.text)).toEqual(['356', ' → ', '341.2.1', ' → ', '284'])
    expect(l9Segments?.some(segment => segment.ticket?.serial === '353.1')).toBe(false)
    // 各段相接即佇列列去掉「排隊：」的票序
    expect(`排隊：${l9Segments?.map(segment => segment.text).join('')}`).toBe(formatQueueRow(l9?.tokens ?? [], tickets))
  })

  test('對照：佇列的票全部 completed 時分段為 null，與佇列列一致', () => {
    const done = ['351', '145'].map(serial => ({ id: `0.5.0-W1-${serial}`, status: 'completed' }))
    expect(queueRowSegments(LANES[0]?.tokens ?? [], done)).toBeNull()
  })
})
