// sessions.ts 的測試：session 狀態檔篩選與解析、本 repo 判定、排序、線列 session 狀態、pid 存活比對。

import { describe, expect, test } from 'claude-code/testing'

import { REAL_LSTART_LOCAL, REAL_LSTART_UTC, REAL_PROC_START, session, sessionJson } from './fixtures'
import {
  isInRepo,
  isSessionProcessAlive,
  laneSessionStatus,
  normalizeProcStart,
  parseSessionFile,
  sessionStatusFileNames,
  sortSessions,
} from '../hooks/sessions'

describe('sessionStatusFileNames', () => {
  test('只取 .json 一般檔案；.key 金鑰與目錄不在其中', () => {
    const entry = (name: string, kind: 'file' | 'dir' = 'file') => ({ name, kind, size: 1, mtimeMs: 0, isLink: false })
    expect(
      sessionStatusFileNames([
        entry('101.json'),
        entry('101.abc.key'),
        entry('102.json.key'),
        entry('sub.json', 'dir'),
        entry('103.json'),
      ]),
    ).toEqual(['101.json', '103.json'])
  })
})

describe('parseSessionFile', () => {
  test('取 pid、name、cwd、status、waitingFor、statusUpdatedAt、procStart、sessionId，其他欄位不保存', () => {
    const text = sessionJson({
      pid: 7,
      name: 's-7',
      cwd: '/repo',
      status: 'waiting',
      waitingFor: 'input needed',
      statusUpdatedAt: 1000,
      procStart: 'Mon Oct 19 09:09:02 2026',
    })
    expect(parseSessionFile(text)).toEqual({
      pid: 7,
      name: 's-7',
      cwd: '/repo',
      status: 'waiting',
      waitingFor: 'input needed',
      statusUpdatedAt: 1000,
      procStart: 'Mon Oct 19 09:09:02 2026',
      sessionId: 'x',
    })
  })

  test('沒有 waitingFor、statusUpdatedAt、procStart 或 sessionId 時為 null；未知 status 原樣保存', () => {
    expect(parseSessionFile(sessionJson({ pid: 7, name: 's', cwd: '/r', status: 'compacting', sessionId: undefined }))).toEqual({
      pid: 7,
      name: 's',
      cwd: '/r',
      status: 'compacting',
      waitingFor: null,
      statusUpdatedAt: null,
      procStart: null,
      sessionId: null,
    })
  })

  test('JSON 無效或缺少必要欄位時回傳 null', () => {
    expect(parseSessionFile('{"pid": 7, "name"')).toBeNull()
    expect(parseSessionFile('null')).toBeNull()
    expect(parseSessionFile(sessionJson({ pid: '7', name: 's', cwd: '/r', status: 'idle' }))).toBeNull()
    expect(parseSessionFile(sessionJson({ pid: 7, name: 's', cwd: '/r' }))).toBeNull()
  })
})

describe('isInRepo', () => {
  test('等於或位於任一 checkout 之下才算；名稱前綴相同的兄弟目錄不算', () => {
    const paths = ['/repo', '/repo/.claude/worktrees/agent-x']
    expect(isInRepo('/repo', paths)).toBe(true)
    expect(isInRepo('/repo/tools', paths)).toBe(true)
    expect(isInRepo('/repo/.claude/worktrees/agent-x/lib', paths)).toBe(true)
    expect(isInRepo('/repo-other', paths)).toBe(false)
    expect(isInRepo('/other', paths)).toBe(false)
  })
})

describe('sortSessions', () => {
  test('shell 與 busy 同組（組內依名稱交錯），排在 waiting 之後、idle 之前；status 原值保留', () => {
    const sorted = sortSessions([
      session({ name: 'e', status: 'idle' }),
      session({ name: 'c', status: 'shell' }),
      session({ name: 'd', status: 'busy' }),
      session({ name: 'a', status: 'busy' }),
      session({ name: 'f', status: 'waiting' }),
    ])
    expect(sorted.map(item => `${item.status}:${item.name}`)).toEqual(['waiting:f', 'busy:a', 'shell:c', 'busy:d', 'idle:e'])
  })

  test('依 waiting、busy、idle 排序，未知 status 排最後；同狀態依名稱', () => {
    const sorted = sortSessions([
      session({ name: 'b', status: 'idle' }),
      session({ name: 'z', status: 'compacting' }),
      session({ name: 'c', status: 'busy' }),
      session({ name: 'a', status: 'idle' }),
      session({ name: 'd', status: 'waiting' }),
    ])
    expect(sorted.map(item => `${item.status}:${item.name}`)).toEqual([
      'waiting:d',
      'busy:c',
      'idle:a',
      'idle:b',
      'compacting:z',
    ])
  })
})

describe('laneSessionStatus', () => {
  const sessions = [
    session({ name: 's-1', status: 'waiting', waitingFor: 'input needed', statusUpdatedAt: 5 }),
    session({ name: 's-2', status: 'idle', statusUpdatedAt: 1 }),
    session({ name: 's-2', status: 'busy', statusUpdatedAt: 9 }),
  ]

  test('waiting 附 waitingFor；同名多筆取最新一筆；比對不到為離線', () => {
    expect(laneSessionStatus(sessions, 's-1')).toBe('waiting：input needed')
    expect(laneSessionStatus(sessions, 's-2')).toBe('busy')
    expect(laneSessionStatus(sessions, 's-9')).toBe('離線')
    expect(laneSessionStatus(sessions, null)).toBe('')
  })
})

describe('normalizeProcStart', () => {
  test('去頭尾空白、壓縮連續空白（個位數日期的補位空白）；不符 lstart 格式時為 null', () => {
    expect(normalizeProcStart(REAL_LSTART_UTC)).toBe(REAL_PROC_START)
    expect(normalizeProcStart('Mon Oct  5 09:09:02 2026')).toBe('Mon Oct 5 09:09:02 2026')
    expect(normalizeProcStart('2026-10-19T09:09:02Z')).toBeNull()
    expect(normalizeProcStart('')).toBeNull()
    expect(normalizeProcStart(null)).toBeNull()
  })
})

describe('isSessionProcessAlive', () => {
  test('真實 session：UTC 的 ps 輸出與 procStart 相同，判為存活', () => {
    expect(isSessionProcessAlive(0, REAL_LSTART_UTC, REAL_PROC_START)).toBe(true)
  })

  test('反例：pid 存在但啟動時間與 procStart 不符（pid 被重複使用），不列為存活', () => {
    expect(isSessionProcessAlive(0, 'Mon Oct 19 11:30:00 2026\n', REAL_PROC_START)).toBe(false)
  })

  test('對照：同一行程的本機時區輸出與 procStart 差 8 小時，比對不符；看板因此以 TZ=UTC 執行 ps', () => {
    expect(isSessionProcessAlive(0, REAL_LSTART_LOCAL, REAL_PROC_START)).toBe(false)
  })

  test('ps exit 不為 0 時為已結束，與 procStart 無關', () => {
    expect(isSessionProcessAlive(1, '', REAL_PROC_START)).toBe(false)
    expect(isSessionProcessAlive(1, '', null)).toBe(false)
  })

  test('無從比對（procStart 缺少或格式不符、ps 無輸出）時退回只看 exit code', () => {
    expect(isSessionProcessAlive(0, REAL_LSTART_UTC, null)).toBe(true)
    expect(isSessionProcessAlive(0, REAL_LSTART_UTC, '2026-10-19T09:09:02Z')).toBe(true)
    expect(isSessionProcessAlive(0, '', REAL_PROC_START)).toBe(true)
  })
})
