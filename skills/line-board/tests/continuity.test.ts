// continuity.ts 的測試：來源紀錄解析、四種接續狀態與來源不明、三種過期偵測與三種等用戶訊號（各含 E2 正向對照）、輸出文字。

import { describe, expect, test } from 'claude-code/testing'

import { session } from './fixtures'
import { continuityTicketIds, formatLineStatus, lastSourceOf, lineStatusReport, parseSourceLog, parseWaitingMark, ticketStatusOf } from '../hooks/continuity'
import { endedForm, parseLaneLines, parseLanes } from '../hooks/lanes'
import type { ContextUsageRecord, LaneLine, SessionState, SourceLogEntry, TicketStatus } from '../types'

const PREFIX = '0.5.0-W1-'

/** 存活的 session：名稱與完整 sessionId（前 8 碼對應來源紀錄）。 */
const live = (name: string, sessionId: string | null, pid = 100): SessionState =>
  session({ name, status: 'idle', pid, cwd: '/repo', sessionId })

const entry = (time: string, source: string, sessionPrefix: string): SourceLogEntry => ({ time, source, sessionPrefix })

const lane = (n: number, sessionName: string | null, queue: string): LaneLine => ({ lane: n, session: sessionName, queue })

const report = (input: { lanes: LaneLine[]; sessions?: SessionState[]; log?: SourceLogEntry[]; tickets?: TicketStatus[] }) =>
  lineStatusReport({ sessions: [], log: [], tickets: [], prefix: PREFIX, ...input })

describe('parseSourceLog', () => {
  test('取時間、source、sessionId 前 8 碼；不符格式的行略過', () => {
    const text = [
      '[2026-10-31T15:13:07] source=clear session_id=f3450a54',
      '手動註記',
      '[2026-10-31T15:14:45] source=startup session_id=1aab01de',
      '',
    ].join('\n')
    expect(parseSourceLog(text)).toEqual([
      entry('2026-10-31T15:13:07', 'clear', 'f3450a54'),
      entry('2026-10-31T15:14:45', 'startup', '1aab01de'),
    ])
  })
})

describe('lastSourceOf', () => {
  test('同一 id 取時間最晚的一筆（多個 checkout 的紀錄合併後不依檔序）', () => {
    const log = [entry('2026-10-31T15:00:00', 'compact', 'aaaaaaaa'), entry('2026-10-31T09:00:00', 'startup', 'aaaaaaaa')]
    expect(lastSourceOf(log, 'aaaaaaaa-1111')?.source).toBe('compact')
  })

  test('查無此 id 為 undefined', () => {
    expect(lastSourceOf([entry('t', 'clear', 'bbbbbbbb')], 'aaaaaaaa-1111')).toBeUndefined()
  })
})

describe('接續狀態', () => {
  test('已收線：票序為（無）或（結束）', () => {
    const result = report({ lanes: [lane(1, 'a', '（無）'), lane(2, null, '（結束）')] })
    expect(result.lanes.map(l => l.state)).toEqual(['ended', 'ended'])
    expect(result.stale).toEqual([])
  })

  test('/clear 後繼續：存活 session 的 sessionId 最後一筆為 source=clear', () => {
    const result = report({
      lanes: [lane(3, '看板工具', '571.2 → 571.1')],
      sessions: [live('看板工具', 'c1c1c1c1-0000')],
      log: [entry('2026-10-31T10:00:00', 'startup', 'c1c1c1c1'), entry('2026-10-31T15:00:00', 'clear', 'c1c1c1c1')],
    })
    expect(result.lanes[0]).toEqual({
      lane: 3,
      session: '看板工具',
      state: 'clear',
      evidence: 'sessionId c1c1c1c1，log 2026-10-31T15:00:00 source=clear',
    })
  })

  test('/compact 後繼續：最後一筆為 source=compact', () => {
    const result = report({
      lanes: [lane(4, 'b', '100')],
      sessions: [live('b', 'd2d2d2d2-0000')],
      log: [entry('2026-10-31T11:00:00', 'compact', 'd2d2d2d2')],
    })
    expect(result.lanes[0]?.state).toBe('compact')
  })

  test('新 session 接手：最後一筆為 source=startup', () => {
    const result = report({
      lanes: [lane(5, 'c', '100')],
      sessions: [live('c', 'e3e3e3e3-0000')],
      log: [entry('2026-10-31T12:00:00', 'startup', 'e3e3e3e3')],
    })
    expect(result.lanes[0]?.state).toBe('startup')
  })

  test('來源不明：來源紀錄查無此 id、source 不在判讀表（resume）、session 檔沒有 sessionId、佇列行未寫名稱', () => {
    const result = report({
      lanes: [lane(6, 'd', '100'), lane(7, 'e', '100'), lane(8, 'f', '100'), lane(9, null, '100')],
      sessions: [live('d', 'f4f4f4f4-0000', 1), live('e', 'a5a5a5a5-0000', 2), live('f', null, 3)],
      log: [entry('2026-10-31T12:00:00', 'resume', 'a5a5a5a5')],
    })
    expect(result.lanes.map(l => l.state)).toEqual(['unknown', 'unknown', 'unknown', 'unknown'])
    expect(result.lanes.map(l => l.evidence)).toEqual([
      'sessionId f4f4f4f4，來源紀錄查無此 id',
      'sessionId a5a5a5a5，log 2026-10-31T12:00:00 source=resume',
      'pid 3 的 session 檔沒有 sessionId',
      '現行佇列行未寫 session 名稱',
    ])
  })
})

describe('過期偵測：收線寫法', () => {
  test('E2 正向對照：「（無）— 說明」判為已收線，並列為收線寫法過期項', () => {
    const result = report({ lanes: [lane(35, '整合測試卡住', '（無）— 移交 L40，見 564')] })
    expect(result.lanes[0]?.state).toBe('ended')
    expect(result.stale.map(s => [s.lane, s.kind])).toEqual([[35, 'ended-with-note']])
  })

  test('E2 正向對照：「無（說明）」（收線記號沒有括號）同樣列為過期項', () => {
    expect(report({ lanes: [lane(22, '框架線', '無（482.2 等 508.8）')] }).stale.map(s => s.kind)).toEqual(['ended-with-note'])
  })

  test('對照：只寫（無）不列過期項；票序中段出現（無）不算收線', () => {
    expect(endedForm('（無）')).toBe('exact')
    expect(endedForm('100（無）')).toBeNull()
    expect(endedForm('100 → 200')).toBeNull()
  })

  test('看板與 line_status 收線定義一致：（無）與（結束）看板都不顯示；附說明的寫法看板仍顯示、line_status 列過期項', () => {
    const text = '## Solution\n**L1 現行佇列**：（無）\n**L2 現行佇列**：（結束）\n**L3 現行佇列**：（無）— 說明\n'
    expect(parseLanes(text, PREFIX).map(l => l.lane)).toEqual([3])
    const result = report({ lanes: parseLaneLines(text) })
    expect(result.lanes.map(l => l.state)).toEqual(['ended', 'ended', 'ended'])
    expect(result.stale.map(s => s.lane)).toEqual([3])
  })

  test('協調票原文經 parseLaneLines 後仍保留收線的線，L35 的寫法可被偵測', () => {
    const text = '## Solution\n**L35 現行佇列**（整合測試卡住）：（無）— 說明\n**L36 現行佇列**（UX實驗）：（無）\n'
    const result = report({ lanes: parseLaneLines(text) })
    expect(result.lanes.map(l => [l.lane, l.state])).toEqual([
      [35, 'ended'],
      [36, 'ended'],
    ])
    expect(result.stale.map(s => s.lane)).toEqual([35])
  })
})

describe('過期偵測：無人持有', () => {
  test('E2 正向對照：佇列行的名稱不在存活 session 中，且佇列仍有內容', () => {
    const result = report({ lanes: [lane(18, '畫面接真資料', '508.8 → 168')], sessions: [live('其他線', 'aaaaaaaa-0')] })
    expect(result.lanes[0]?.state).toBe('orphan')
    expect(result.stale.map(s => [s.lane, s.kind])).toEqual([[18, 'orphan']])
  })

  test('E2 正向對照：佇列行未寫名稱且佇列仍有內容，同樣列為無人持有（狀態仍為來源不明）', () => {
    const result = report({ lanes: [lane(9, null, '100')] })
    expect(result.lanes[0]?.state).toBe('unknown')
    expect(result.stale.map(s => [s.lane, s.kind])).toEqual([[9, 'orphan']])
  })

  test('對照：名稱在存活 session 中時不列', () => {
    const result = report({
      lanes: [lane(18, '畫面接真資料', '508.8')],
      sessions: [live('畫面接真資料', 'aaaaaaaa-0')],
      log: [entry('t', 'startup', 'aaaaaaaa')],
    })
    expect(result.stale).toEqual([])
  })
})

describe('過期偵測：佇列已完成未收線', () => {
  const sessions = [live('a', 'aaaaaaaa-0')]
  const log = [entry('t', 'startup', 'aaaaaaaa')]

  test('E2 正向對照：佇列的票全部 completed，現行佇列行不是（無）', () => {
    const tickets = [
      { id: '0.5.0-W1-100', status: 'completed' },
      { id: '0.5.0-W1-200', status: 'completed' },
    ]
    const result = report({ lanes: [lane(1, 'a', '100 → 200')], sessions, log, tickets })
    expect(result.stale.map(s => [s.lane, s.kind])).toEqual([[1, 'all-done']])
  })

  test('對照：有一張未完成、或佇列沒有票號時不列', () => {
    const tickets = [
      { id: '0.5.0-W1-100', status: 'completed' },
      { id: '0.5.0-W1-200', status: 'in_progress' },
    ]
    expect(report({ lanes: [lane(1, 'a', '100 → 200')], sessions, log, tickets }).stale).toEqual([])
    expect(report({ lanes: [lane(1, 'a', '等主控通知')], sessions, log }).stale).toEqual([])
  })
})

describe('continuityTicketIds', () => {
  test('只取未收線的線的票號，去重', () => {
    const lanes = [lane(1, 'a', '100 → 200'), lane(2, 'b', '（無）— 300'), lane(3, 'c', '200 ∥ 400')]
    expect(continuityTicketIds(lanes, PREFIX)).toEqual(['0.5.0-W1-100', '0.5.0-W1-200', '0.5.0-W1-400'])
  })
})

describe('parseWaitingMark', () => {
  const ticketText = (...solution: string[]) =>
    ['---', 'status: in_progress', '---', '## Problem Analysis', '格式：`**等用戶**：<事項>`', '## Solution', ...solution, '## Test Results', '**等用戶**：不在 Solution 段'].join('\n')

  test('取 Solution 段最後一行標記的事項', () => {
    expect(parseWaitingMark(ticketText('**等用戶**：開 --debug 重啟', '說明', '**等用戶**：在 worktree 開 session'))).toBe('在 worktree 開 session')
  })

  test('最後一行是解除行時為 null；解除後再標記則重新列出', () => {
    expect(parseWaitingMark(ticketText('**等用戶**：開 --debug', '**等用戶解除**：已重啟'))).toBeNull()
    expect(parseWaitingMark(ticketText('**等用戶**：a', '**等用戶解除**：b', '**等用戶**：c'))).toBe('c')
  })

  test('其他段落的標記、Solution 內行中引用的格式、自由文字「待用戶」都不算', () => {
    expect(parseWaitingMark(ticketText('待用戶：在 worktree 路徑開互動式 session', 'S1 格式為 `**等用戶**：<事項>`'))).toBeNull()
  })

  test('縮排行與 fenced code block 內的格式示例不算；fence 結束後的標記照算', () => {
    expect(parseWaitingMark(ticketText('  **等用戶**：縮排', '```', '**等用戶**：<事項>', '```'))).toBeNull()
    expect(parseWaitingMark(ticketText('```', '**等用戶解除**：示例', '```', '**等用戶**：真的在等'))).toBe('真的在等')
  })

  test('冒號後沒寫事項的標記照樣列出，不視為解除', () => {
    expect(parseWaitingMark(ticketText('**等用戶**：開 --debug', '**等用戶**：'))).toBe('標記未附事項')
  })
})

describe('ticketStatusOf：票檔原文組成佇列票狀態（readers.ts 讀到票檔後一律經此）', () => {
  const ticketText = (...solution: string[]) => ['---', 'title: 示例', 'status: in_progress', '---', '## Solution', ...solution].join('\n')

  test('E2 正向對照：Solution 末行為標記時，waiting 為事項，與 status、title 同一次組成', () => {
    expect(ticketStatusOf('0.5.0-W1-200', ticketText('**等用戶**：開 --debug 重啟'))).toEqual({
      id: '0.5.0-W1-200',
      status: 'in_progress',
      title: '示例',
      waiting: '開 --debug 重啟',
    })
  })

  test('負向對照：Solution 末行為解除行時，waiting 為 null', () => {
    expect(ticketStatusOf('0.5.0-W1-200', ticketText('**等用戶**：開 --debug 重啟', '**等用戶解除**：已重啟')).waiting).toBeNull()
  })
})

describe('等用戶偵測', () => {
  const sessions = [live('a', 'aaaaaaaa-0')]
  const log = [entry('t', 'startup', 'aaaaaaaa')]
  const pending = (id: string, waiting: string | null = null): TicketStatus => ({ id, status: 'in_progress', waiting })

  test('E2 正向對照 S1：佇列中未完成的票有等用戶標記', () => {
    const result = report({ lanes: [lane(1, 'a', '100 → 200')], sessions, log, tickets: [pending('0.5.0-W1-100'), pending('0.5.0-W1-200', '開 --debug 重啟')] })
    expect(result.waiting).toEqual([{ lane: 1, session: 'a', ticketId: '0.5.0-W1-200', item: '開 --debug 重啟', source: 'S1' }])
  })

  test('E2 正向對照 S2：該線 session 的 status 為 waiting，事項取 waitingFor', () => {
    const waitingSession = session({ name: 'a', status: 'waiting', waitingFor: 'approve Bash', pid: 100, cwd: '/repo', sessionId: 'aaaaaaaa-0' })
    const result = report({ lanes: [lane(1, 'a', '100')], sessions: [waitingSession], log, tickets: [pending('0.5.0-W1-100')] })
    expect(result.waiting).toEqual([{ lane: 1, session: 'a', ticketId: null, item: 'approve Bash', source: 'S2' }])
  })

  test('E2 正向對照 S3：佇列行的票註記或文字含「等用戶」', () => {
    const result = report({ lanes: [lane(1, 'a', '511（等用戶開 --debug）→ 512')], sessions, log, tickets: [pending('0.5.0-W1-511')] })
    expect(result.waiting).toEqual([{ lane: 1, session: 'a', ticketId: '0.5.0-W1-511', item: '等用戶開 --debug', source: 'S3' }])
    const textOnly = report({ lanes: [lane(2, 'a', '等用戶裁定方向')], sessions, log })
    expect(textOnly.waiting).toEqual([{ lane: 2, session: 'a', ticketId: null, item: '等用戶裁定方向', source: 'S3' }])
  })

  test('負向對照：已 completed 的票，標記與佇列註記都不列', () => {
    const tickets = [{ id: '0.5.0-W1-100', status: 'completed', waiting: '開 --debug' }]
    expect(report({ lanes: [lane(1, 'a', '100（等用戶）')], sessions, log, tickets }).waiting).toEqual([])
  })

  test('負向對照：自由文字「待用戶」、session idle、已收線的線都不列', () => {
    const tickets = [pending('0.5.0-W1-100', parseWaitingMark('## Solution\n待用戶：在 worktree 開 session'))]
    expect(report({ lanes: [lane(1, 'a', '100（待用戶回覆）')], sessions, log, tickets }).waiting).toEqual([])
    expect(report({ lanes: [lane(2, 'b', '（無）')], sessions: [session({ name: 'b', status: 'waiting', pid: 101, cwd: '/repo' })] }).waiting).toEqual([])
  })

  test('負向對照：收線附說明的線（說明含「等用戶」、佇列票帶標記）也不判 S1／S3', () => {
    const result = report({ lanes: [lane(3, 'a', '（無）— 300 等用戶裁定')], sessions, log, tickets: [pending('0.5.0-W1-300', '開 --debug')] })
    expect(result.waiting).toEqual([])
  })

  test('負向對照：同一條線較早的佇列行含「等用戶」，現行佇列行沒有時不列', () => {
    const text = [
      '## Solution',
      '**L1 現行佇列**（a）：511（等用戶開 --debug）',
      '**L1 現行佇列**（a）：512',
    ].join('\n')
    const result = report({ lanes: parseLaneLines(text), sessions, log, tickets: [pending('0.5.0-W1-512')] })
    expect(result.waiting).toEqual([])
  })
})

describe('formatLineStatus', () => {
  test('未收線各線一行、已收線合併一行、過期項逐條、等用戶逐條、末行為判讀規則路由', () => {
    const text = formatLineStatus(
      {
        lanes: [
          { lane: 3, session: '看板工具', state: 'clear', evidence: 'sessionId c1c1c1c1，log t source=clear' },
          { lane: 35, session: 'x', state: 'ended', evidence: '票序「（無）— 說明」' },
          { lane: 36, session: 'y', state: 'ended', evidence: '票序「（無）」' },
        ],
        stale: [{ lane: 35, kind: 'ended-with-note', detail: '說明' }],
        waiting: [
          { lane: 3, session: '看板工具', ticketId: '0.5.0-W1-580', item: '開 --debug 重啟', source: 'S1' },
          { lane: 3, session: '看板工具', ticketId: null, item: 'approve Bash', source: 'S2' },
          { lane: 4, session: null, ticketId: '0.5.0-W1-511', item: '等用戶開 --debug', source: 'S3' },
        ],
      },
      { coordinationTicket: '0.5.0-W1-349', readAt: '2026-10-31 15:30:00' },
    )
    expect(text.split('\n')).toEqual([
      '各線接續狀態（協調票 0.5.0-W1-349，讀取 2026-10-31 15:30:00）',
      'L3（看板工具）：/clear 後繼續｜sessionId c1c1c1c1，log t source=clear',
      '已收線：L35、L36',
      '過期項（1）：',
      '- L35 收線寫法：說明',
      '等用戶（3）：',
      '- L3（看板工具）0.5.0-W1-580：開 --debug 重啟（S1）',
      '- L3（看板工具）：approve Bash（S2）',
      '- L4 0.5.0-W1-511：等用戶開 --debug（S3）',
      '判讀規則與各狀態的接續動作：.claude/skills/multi-session-orchestration/references/line-continuity.md §2',
    ])
  })

  test('未收線的線帶用量段時接在依據之後；沒有用量段的線維持原樣', () => {
    const text = formatLineStatus(
      {
        lanes: [
          { lane: 1, session: 'a', state: 'compact', evidence: 'e1', context: 'ctx 47%（1 分前）［待 compact］' },
          { lane: 2, session: 'b', state: 'orphan', evidence: 'e2' },
        ],
        stale: [],
        waiting: [],
      },
      { coordinationTicket: 'c', readAt: 't' },
    )
    expect(text).toContain('L1（a）：/compact 後繼續｜e1｜ctx 47%（1 分前）［待 compact］')
    expect(text).toContain('L2（b）：無人持有｜e2\n')
  })

  test('沒有未收線的線、沒有過期項、沒有等用戶時明寫「無」', () => {
    const text = formatLineStatus({ lanes: [], stale: [], waiting: [] }, { coordinationTicket: 'c', readAt: 't' })
    expect(text).toContain('未收線的線：無')
    expect(text).toContain('過期項：無')
    expect(text).toContain('等用戶：無')
  })
})

describe('lineStatusReport：用量段', () => {
  const usage = (sessionId: string, percent: number | null): ContextUsageRecord => ({
    sessionId,
    phase: null,
    tokens: percent === null ? null : percent * 10_000,
    window: 1_000_000,
    percent,
    compactWindow: null,
    compactPercent: null,
    autoCompactThreshold: null,
    measuredAt: 1_000,
  })
  const lanes = [lane(1, 'a', '0.5.0-W1-10'), lane(2, 'b', '0.5.0-W1-11'), lane(3, 'c', '（無）')]
  const sessions = [live('a', 'aaaaaaaa-1', 101), live('b', 'bbbbbbbb-1', 102), live('c', 'cccccccc-1', 103)]
  const tickets: TicketStatus[] = [{ id: '0.5.0-W1-10', status: 'in_progress' }, { id: '0.5.0-W1-11', status: 'pending' }]

  test('正向對照：達門檻的線帶標記（持有 in_progress 待 compact、未持有待 clear）', () => {
    const result = lineStatusReport({
      lanes,
      sessions,
      log: [],
      tickets,
      prefix: PREFIX,
      context: { usages: { 'aaaaaaaa-1': usage('aaaaaaaa-1', 45), 'bbbbbbbb-1': usage('bbbbbbbb-1', 30) }, failures: {}, nowMs: 61_000 },
    })
    expect(result.lanes.map(item => item.context)).toEqual(['ctx 45%（1 分前）［待 compact］', 'ctx 30%（1 分前）［待 clear］', undefined])
  })

  test('反向對照：未達門檻不標；無用量檔與解析失敗各自明寫；不提供 context 時沒有用量段', () => {
    const result = lineStatusReport({
      lanes,
      sessions,
      log: [],
      tickets,
      prefix: PREFIX,
      context: { usages: { 'aaaaaaaa-1': usage('aaaaaaaa-1', 44) }, failures: { 'bbbbbbbb-1': '內容不是 JSON 物件' }, nowMs: 61_000 },
    })
    expect(result.lanes.map(item => item.context)).toEqual(['ctx 44%（1 分前）', 'ctx 用量檔解析失敗：內容不是 JSON 物件', undefined])
    const noUsage = lineStatusReport({ lanes, sessions, log: [], tickets, prefix: PREFIX, context: { usages: {}, failures: {}, nowMs: 0 } })
    expect(noUsage.lanes[0]?.context).toBe('ctx 無用量檔')
    expect(report({ lanes, sessions, tickets }).lanes.every(item => item.context === undefined)).toBe(true)
  })
})
