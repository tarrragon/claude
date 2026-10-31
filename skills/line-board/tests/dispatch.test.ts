// dispatch.ts 的測試：派發紀錄解析、ISO 時間、流程階段推導、派發列與派發票號。

import { describe, expect, test } from 'claude-code/testing'

import {
  dispatchRows,
  dispatchStage,
  dispatchTicketIds,
  parseDispatchFile,
  parseIsoMs,
} from '../hooks/dispatch'
import { dispatch, dispatchJson, session } from './fixtures'
import { parseLanes } from '../hooks/lanes'

describe('parseDispatchFile', () => {
  test('取 dispatches 各筆的代理人、session、票號、描述與時間；空字串票號為 null，tombstones 不讀', () => {
    const text = JSON.stringify({
      dispatches: [
        dispatchJson({ agent_id: 'a1', session_id: 's1', name: 'linux', agent_description: '審查 337.8' }),
        dispatchJson({
          agent_id: 'a2',
          session_id: 's2',
          ticket_id: '0.5.0-W1-337.9',
          turn_ended_at: '2026-10-19T07:58:00+00:00',
        }),
      ],
      tombstones: [{ agent_id: 'a3', created_at: '2026-10-19T07:00:00+00:00' }],
    })
    expect(parseDispatchFile(text)).toEqual([
      {
        agentId: 'a1',
        name: 'linux',
        sessionId: 's1',
        ticketId: null,
        description: '審查 337.8',
        dispatchedAt: '2026-10-19T07:57:00.000000+00:00',
        turnEndedAt: null,
      },
      {
        agentId: 'a2',
        name: 'general-purpose',
        sessionId: 's2',
        ticketId: '0.5.0-W1-337.9',
        description: '描述',
        dispatchedAt: '2026-10-19T07:57:00.000000+00:00',
        turnEndedAt: '2026-10-19T07:58:00+00:00',
      },
    ])
  })

  test('反例：JSON 無效、不是物件或 dispatches 不是陣列時回傳 null', () => {
    expect(parseDispatchFile('{"dispatches": [')).toBeNull()
    expect(parseDispatchFile('null')).toBeNull()
    expect(parseDispatchFile('{"dispatches": {}}')).toBeNull()
    expect(parseDispatchFile('{}')).toBeNull()
    // 對照：空陣列是合法的「沒有派發」，不是格式錯誤
    expect(parseDispatchFile('{"dispatches": []}')).toEqual([])
  })

  test('缺少 agent_id、session_id 或 name 的條目略過，其餘照常', () => {
    const text = JSON.stringify({
      dispatches: [
        dispatchJson({ agent_id: undefined }),
        dispatchJson({ session_id: 7 }),
        dispatchJson({ name: '' }),
        'not-an-object',
        dispatchJson({ agent_id: 'ok' }),
      ],
    })
    expect(parseDispatchFile(text)?.map(record => record.agentId)).toEqual(['ok'])
  })
})

describe('parseIsoMs', () => {
  test('帶微秒與時區位移的 ISO 時間取到毫秒；格式不符或 null 為 null', () => {
    expect(parseIsoMs('2026-10-19T07:57:00.123456+00:00')).toBe(Date.UTC(2026, 9, 19, 7, 57, 0, 123))
    expect(parseIsoMs('2026-10-19T15:57:00+08:00')).toBe(Date.UTC(2026, 9, 19, 7, 57, 0))
    expect(parseIsoMs('昨天')).toBeNull()
    expect(parseIsoMs(null)).toBeNull()
  })
})

describe('dispatchStage', () => {
  const ENDED = '2026-10-19T07:58:00+00:00'

  test('未結束的實作代理人為「實作」', () => {
    expect(dispatchStage(dispatch({ ticketId: '0.5.0-W1-337.9' }), 'in_progress', [])).toBe('實作')
    expect(dispatchStage(dispatch(), undefined, [])).toBe('實作')
  })

  test('未結束的審查類代理人為「審查」；對照：同一條目換成實作代理人即為「實作」', () => {
    for (const name of ['linux', 'basil-writing-critic', 'acceptance-auditor']) {
      expect(dispatchStage(dispatch({ name }), undefined, [])).toBe('審查')
    }
    expect(dispatchStage(dispatch({ name: 'general-purpose' }), undefined, [])).toBe('實作')
  })

  test('未結束的 incident-responder 為「事故分析」', () => {
    expect(dispatchStage(dispatch({ name: 'incident-responder' }), undefined, [])).toBe('事故分析')
  })

  test('分支 worktree-agent-<agent_id> 在閘門持有者中為「閘門」，已結束亦同；對照：不在持有者中時依原規則', () => {
    const running = dispatch({ agentId: 'a352c31d77c3daa98', ticketId: '0.5.0-W1-351' })
    const ended = { ...running, turnEndedAt: ENDED }
    const holders = ['worktree-agent-a352c31d77c3daa98']
    expect(dispatchStage(running, 'in_progress', holders)).toBe('閘門')
    expect(dispatchStage(ended, 'in_progress', holders)).toBe('閘門')
    expect(dispatchStage(running, 'in_progress', ['worktree-agent-other'])).toBe('實作')
    expect(dispatchStage(ended, 'in_progress', [])).toBe('收尾')
  })

  test('已結束且票未 completed 為「收尾」（票狀態讀不到亦同）；對照：票已 completed 時不列', () => {
    const ended = dispatch({ ticketId: '0.5.0-W1-345', turnEndedAt: ENDED })
    expect(dispatchStage(ended, 'pending', [])).toBe('收尾')
    expect(dispatchStage(ended, 'unknown', [])).toBe('收尾')
    expect(dispatchStage(ended, undefined, [])).toBe('收尾')
    expect(dispatchStage(ended, 'completed', [])).toBeNull()
  })

  test('票已 completed 時不列，代理人未結束亦同', () => {
    expect(dispatchStage(dispatch({ ticketId: '0.5.0-W1-337.1' }), 'completed', [])).toBeNull()
  })

  test('已結束且沒有票號的條目不列（沒有票可收尾）；對照：未結束時照常列出', () => {
    expect(dispatchStage(dispatch({ name: 'linux', turnEndedAt: ENDED }), undefined, [])).toBeNull()
    expect(dispatchStage(dispatch({ name: 'linux' }), undefined, [])).toBe('審查')
  })
})

describe('dispatchRows', () => {
  const sessions = [
    session({ name: 's-l13', status: 'busy', sessionId: 'sid-13' }),
    session({ name: 's-l7', status: 'idle', sessionId: 'sid-7' }),
    session({ name: 's-free', status: 'idle', sessionId: 'sid-free' }),
  ]
  const PREFIX = '0.5.0-W1-'
  const lanes = parseLanes('## Solution\n**L13 現行佇列**（s-l13）：337.9\n\n**L7 現行佇列**（s-l7）：351\n', PREFIX)
  const context = { sessions, lanes, tickets: [{ id: '0.5.0-W1-337.1', status: 'completed' }], holders: [] }

  test('session_id 對到存活 session，以其名稱對到線；對不到線的歸其他（null）；依線號排序、其他最後；票號顯示短票號', () => {
    const rows = dispatchRows(
      [
        dispatch({ agentId: 'a-free', sessionId: 'sid-free', description: '其他線的派發' }),
        dispatch({ agentId: 'a-13', sessionId: 'sid-13', ticketId: '0.5.0-W1-337.9' }),
        dispatch({ agentId: 'a-7', sessionId: 'sid-7', name: 'linux', description: '審查 351' }),
      ],
      context,
      PREFIX,
    )
    expect(rows.map(row => [row.lane, row.name, row.task, row.stage])).toEqual([
      [7, 'linux', '審查 351', '審查'],
      [13, 'general-purpose', '337.9', '實作'],
      [null, 'general-purpose', '其他線的派發', '實作'],
    ])
  })

  test('E2：session 不存活或票已 completed 的舊條目不列；對照：同一條目在 session 存活且票未完成時列出', () => {
    const deadSession = dispatch({ agentId: 'a-dead', sessionId: 'sid-gone' })
    const completed = dispatch({ agentId: 'a-done', sessionId: 'sid-13', ticketId: '0.5.0-W1-337.1' })
    expect(dispatchRows([deadSession, completed], context, PREFIX)).toEqual([])
    const alive = { ...deadSession, sessionId: 'sid-13' }
    const pending = { ...completed, ticketId: '0.5.0-W1-337.9' }
    expect(dispatchRows([alive, pending], context, PREFIX).map(row => row.stage)).toEqual(['實作', '實作'])
  })

  test('E1：同一批紀錄以兩個不同前綴呼叫，任務欄不同，且各自只去掉該前綴', () => {
    const records = [
      dispatch({ agentId: 'a-5', sessionId: 'sid-13', ticketId: '0.5.0-W1-337.9' }),
      dispatch({ agentId: 'a-6', sessionId: 'sid-7', ticketId: '0.6.0-W2-12.3' }),
    ]
    const tasksOf = (prefix: string) => dispatchRows(records, context, prefix).map(row => row.task)
    expect(tasksOf('0.5.0-W1-')).not.toEqual(tasksOf('0.6.0-W2-'))
    expect(tasksOf('0.5.0-W1-')).toEqual(['0.6.0-W2-12.3', '337.9'])
    expect(tasksOf('0.6.0-W2-')).toEqual(['12.3', '0.5.0-W1-337.9'])
  })

  test('dispatchTicketIds：有票號的條目的完整票號，去重並保留順序', () => {
    expect(
      dispatchTicketIds([
        dispatch({ ticketId: '0.5.0-W1-351' }),
        dispatch(),
        dispatch({ ticketId: '0.5.0-W1-337.9' }),
        dispatch({ ticketId: '0.5.0-W1-351' }),
      ]),
    ).toEqual(['0.5.0-W1-351', '0.5.0-W1-337.9'])
  })
})
