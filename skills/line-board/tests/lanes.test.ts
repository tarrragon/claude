// lanes.ts 的測試：349 現行佇列行與線目標行解析、票序拆分與格式化。

import { describe, expect, test } from 'claude-code/testing'

import { QUEUE_LINE_CASES, TEMPLATE_AT_LINE_START,TEMPLATE_NOTE, TICKET_349, TICKET_349_GOALS } from './fixtures'
import { formatQueue, laneTicketIds, parseLaneGoals, parseLanes, parseQueue } from '../hooks/lanes'
import { ticketPrefixOf } from '../hooks/shared'

/** fixtures 的協調票（349）推導出的短票號前綴；本檔的完整票號皆以它補全。 */
const PREFIX = '0.5.0-W1-'

describe('parseLanes', () => {
  test('短票號以協調票推導的前綴補全：兩個不同協調票解析同一佇列行，各補成自己的完整票號（E1 對照）', () => {
    const text = '## Solution\n**L5 現行佇列**：100 → 337.1 ∥ W3-012\n'
    const idsUnder = (coordinator: string) => laneTicketIds(parseLanes(text, ticketPrefixOf(coordinator) ?? ''))
    expect(idsUnder('0.5.0-W1-349')).not.toEqual(idsUnder('0.6.0-W2-010'))
    expect(idsUnder('0.5.0-W1-349')).toEqual(['0.5.0-W1-100', '0.5.0-W1-337.1', '0.5.0-W3-012'])
    expect(idsUnder('0.6.0-W2-010')).toEqual(['0.6.0-W2-100', '0.6.0-W2-337.1', '0.6.0-W3-012'])
  })

  test('同一條線有多行時只取最後一行；歷史行與舊格式行的票號不進結果', () => {
    const lanes = parseLanes(TICKET_349, PREFIX)
    expect(lanes.map(lane => lane.lane)).toEqual([7, 9, 13])
    expect(laneTicketIds(lanes)).toEqual([
      '0.5.0-W1-351',
      '0.5.0-W1-145',
      '0.5.0-W1-356',
      '0.5.0-W1-353.1',
      '0.5.0-W1-341.2.1',
      '0.5.0-W1-284',
      '0.5.0-W1-337.1',
      '0.5.0-W1-337.3',
      '0.5.0-W1-337.2.1',
    ])
    const ids = laneTicketIds(lanes)
    for (const historical of ['328.1', '348', '341.1', '343', '257', '350', '328', '900']) {
      expect(ids.includes(`0.5.0-W1-${historical}`)).toBe(false)
    }
  })

  test('最後一行票序為（無）的線不顯示；session 名稱原樣保留，改派時取最後一行的名稱', () => {
    const lanes = parseLanes(TICKET_349, PREFIX)
    expect(lanes.some(lane => lane.lane === 11)).toBe(false)
    expect(lanes.map(lane => lane.session)).toEqual([
      'graph-project-docs-manager-f9',
      'graph-project-docs-manager-3e',
      'graph-project-docs-manager-1b',
    ])
  })

  test('反例：格式說明行（反引號引用範本）與行首範本（n 非數字）都不算一條線', () => {
    expect(parseLanes(`## Solution\n${TEMPLATE_NOTE}\n${TEMPLATE_AT_LINE_START}\n`, PREFIX)).toEqual([])
  })

  test('只比對行首：清單項的舊格式行不算一條線', () => {
    expect(parseLanes('## Solution\n- **L7 現行佇列**（s）：257\n  **L8 現行佇列**（s）：258\n', PREFIX)).toEqual([])
  })

  test('只掃 Solution：其他二級段落的現行佇列行不列入', () => {
    expect(parseLanes(TICKET_349, PREFIX).some(lane => lane.lane === 20 || lane.lane === 30)).toBe(false)
  })

  test('沒有任何現行佇列行（含沒有 Solution）時回傳空陣列', () => {
    expect(parseLanes('---\nstatus: pending\n---\n## Solution\n### 分派\n佇列：341.1\n', PREFIX)).toEqual([])
    expect(parseLanes('', PREFIX)).toEqual([])
  })

  test('行內沒寫 session 名稱時為 null；沒有目標行時 goal 為 null', () => {
    expect(parseLanes('## Solution\n**L5 現行佇列**：100\n', PREFIX)).toEqual([
      { lane: 5, session: null, goal: null, tokens: [{ kind: 'ticket', serial: '100', id: '0.5.0-W1-100', note: '' }] },
    ])
  })

  test('線目標：取該線最後一行目標行；沒有目標行的線為 null（E1 對照）', () => {
    const withGoals = parseLanes(TICKET_349_GOALS, PREFIX)
    const without = parseLanes(TICKET_349, PREFIX)
    expect(withGoals.map(lane => lane.goal)).not.toEqual(without.map(lane => lane.goal))
    expect(without.map(lane => lane.goal)).toEqual([null, null, null])
    expect(withGoals.find(lane => lane.lane === 13)?.goal).toBe('顯示各線目標與派發中代理人')
  })

  test('parseLaneGoals：不依賴現行佇列行，只回傳最後一行仍有目標的線', () => {
    expect([...parseLaneGoals(TICKET_349_GOALS)]).toEqual([[13, '顯示各線目標與派發中代理人']])
    expect([...parseLaneGoals('## Solution\n**L2 目標**：乙\n**L3 目標**：\n')]).toEqual([[2, '乙']])
  })

  test('線目標：最後一行寫（無）時清除較早的目標', () => {
    expect(parseLanes(TICKET_349_GOALS, PREFIX).find(lane => lane.lane === 7)?.goal).toBeNull()
    expect(parseLanes('## Solution\n**L5 現行佇列**：100\n**L5 目標**：甲\n', PREFIX).map(lane => lane.goal)).toEqual(['甲'])
    expect(parseLanes('## Solution\n**L5 現行佇列**：100\n**L5 目標**：甲\n**L5 目標**：（無）\n', PREFIX).map(lane => lane.goal)).toEqual([
      null,
    ])
  })

  test('線目標：寫（無）清除後再寫目標即恢復，取最後一行', () => {
    const text = '## Solution\n**L5 現行佇列**：100\n**L5 目標**：甲\n**L5 目標**：（無）\n**L5 目標**：乙\n'
    expect(parseLanes(text, PREFIX).map(lane => lane.goal)).toEqual(['乙'])
  })

  test('反例：清單項、表格內、反引號範本與 Solution 之外的目標行不被採用（E2）', () => {
    expect(parseLanes(TICKET_349_GOALS, PREFIX).find(lane => lane.lane === 9)?.goal).toBeNull()
    for (const line of [
      '- **L5 目標**：清單項',
      '| **L5 目標**：表格 | x |',
      '說明：`**L5 目標**：範本`',
      '`**L5 目標**：整行反引號`',
      '  **L5 目標**：縮排',
    ]) {
      expect(parseLanes(`## Solution\n**L5 現行佇列**：100\n${line}\n`, PREFIX).map(lane => lane.goal)).toEqual([null])
    }
    // 對照：同一段文字寫在行首即被採用，確認上列輸入是被判定排除，不是解析本身失效
    expect(parseLanes('## Solution\n**L5 現行佇列**：100\n**L5 目標**：行首\n', PREFIX).map(lane => lane.goal)).toEqual(['行首'])
  })
})

describe('parseLanes 共用案例（queue-line-cases.json 的 TS 副本 QUEUE_LINE_CASES）', () => {
  for (const c of QUEUE_LINE_CASES) {
    test(`${c.category}：${c.name}`, () => {
      const actual = parseLanes(c.text, c.prefix).map(lane => ({
        lane: lane.lane,
        session: lane.session,
        tickets: lane.tokens.flatMap(t => (t.kind === 'ticket' ? [{ serial: t.serial, id: t.id, note: t.note }] : [])),
      }))
      expect(actual).toEqual(c.expect)
    })
  }
})

describe('parseQueue', () => {
  test('保留 → 與 ∥ 的順序結構，子序號可多層，票號後的註記另存', () => {
    expect(parseQueue('337.1（待用戶實機驗證）→ 353.1 ∥ 341.2.1', PREFIX)).toEqual([
      { kind: 'ticket', serial: '337.1', id: '0.5.0-W1-337.1', note: '（待用戶實機驗證）' },
      { kind: 'sep', text: '→' },
      { kind: 'ticket', serial: '353.1', id: '0.5.0-W1-353.1', note: '' },
      { kind: 'sep', text: '∥' },
      { kind: 'ticket', serial: '341.2.1', id: '0.5.0-W1-341.2.1', note: '' },
    ])
  })

  test('短票號以傳入的前綴補成完整票號：兩個前綴解析同一票序結果不同（E1 對照）', () => {
    const withPrefix = parseQueue('100 → 337.1', '0.6.0-W2-')
    expect(withPrefix).not.toEqual(parseQueue('100 → 337.1', PREFIX))
    expect(withPrefix).toEqual([
      { kind: 'ticket', serial: '100', id: '0.6.0-W2-100', note: '' },
      { kind: 'sep', text: '→' },
      { kind: 'ticket', serial: '337.1', id: '0.6.0-W2-337.1', note: '' },
    ])
  })

  test('完整票號原樣作為 id，不套前綴；顯示用 serial 保留原寫法，其後為註記', () => {
    expect(parseQueue('0.6.0-W3-012.1（跨版）∥ 100', '0.5.0-W1-')).toEqual([
      { kind: 'ticket', serial: '0.6.0-W3-012.1', id: '0.6.0-W3-012.1', note: '（跨版）' },
      { kind: 'sep', text: '∥' },
      { kind: 'ticket', serial: '100', id: '0.5.0-W1-100', note: '' },
    ])
  })

  test('W<n>-<序號> 以前綴的版本補成完整票號（同版本異 wave）', () => {
    expect(parseQueue('W2-005.1（異 wave）→ W1-349', '0.5.0-W1-')).toEqual([
      { kind: 'ticket', serial: 'W2-005.1', id: '0.5.0-W2-005.1', note: '（異 wave）' },
      { kind: 'sep', text: '→' },
      { kind: 'ticket', serial: 'W1-349', id: '0.5.0-W1-349', note: '' },
    ])
  })

  test('無法辨識的文字仍為 text：W 寫法缺序號、版本不完整、前綴推不出版本時的 W 寫法', () => {
    expect(parseQueue('W2-x → 0.5-W1-001 → 12', '0.5.0-W1-')).toEqual([
      { kind: 'text', text: 'W2-x' },
      { kind: 'sep', text: '→' },
      { kind: 'text', text: '0.5-W1-001' },
      { kind: 'sep', text: '→' },
      { kind: 'text', text: '12' },
    ])
    expect(parseQueue('W2-005', 'L7-')).toEqual([{ kind: 'text', text: 'W2-005' }])
  })

  test('不以票號開頭的一步保留為文字', () => {
    expect(parseQueue('待定 → 100', PREFIX)).toEqual([
      { kind: 'text', text: '待定' },
      { kind: 'sep', text: '→' },
      { kind: 'ticket', serial: '100', id: '0.5.0-W1-100', note: '' },
    ])
  })
})

describe('formatQueue', () => {
  test('票號旁標狀態、註記接在狀態後、查不到狀態只顯示票號', () => {
    const tokens = parseQueue('337.1（待驗證）→ 353.1 ∥ 999', PREFIX)
    const text = formatQueue(tokens, [
      { id: '0.5.0-W1-337.1', status: 'in_progress' },
      { id: '0.5.0-W1-353.1', status: 'pending' },
    ])
    expect(text).toBe('337.1〔in_progress〕（待驗證） → 353.1〔pending〕 ∥ 999')
  })
})
