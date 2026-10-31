// contextJudge.ts 的測試：用量檔的解析、待 compact／待 clear 判定（分母選擇、主控與一般線門檻）、
// 各 session 列的用量字尾、線標題的標記與恢復開工徽章，以及用量檔清理的路徑檢查與孤兒檔挑選。

import { describe, expect, test } from 'claude-code/testing'

import { CONTEXT_USAGE_DIR } from '../hooks/contextUsage'
import {
  COORDINATOR_T_COMPACT,
  LANE_T_CLEAR,
  LANE_T_COMPACT,
  ORPHAN_AGE_MS,
  RESUME_BADGE_MS,
  contextMarkLabel,
  contextMarkOf,
  contextUsageSuffix,
  isDeletableUsagePath,
  laneContextLabel,
  laneContextStatus,
  orphanUsageFiles,
  parseContextUsageDetailed,
  parseContextUsageFile,
  phaseText,
  recentResume,
  resumeBadgeText,
  selectedPercent,
} from '../hooks/contextJudge'
import type { ContextUsageRecord, QueueToken, TicketStatus } from '../types'
import { session } from './fixtures'

const NOW = 1_793_450_000_000
const ID = 'b953833f-4d2e-43c3-82c6-7ef169a4b86b'

/** auto-compact 關閉（threshold null）的記錄；percent 與 compactPercent 預設相同。 */
const record = (fields: Partial<ContextUsageRecord> = {}): ContextUsageRecord => ({
  sessionId: ID,
  phase: null,
  tokens: 400_000,
  window: 1_000_000,
  percent: 40,
  compactWindow: 1_000_000,
  compactPercent: 40,
  autoCompactThreshold: null,
  measuredAt: NOW - 60_000,
  ...fields,
})

describe('門檻常數', () => {
  test('一般線 45／30，主控 60（主控不判待 clear）', () => {
    expect([LANE_T_COMPACT, LANE_T_CLEAR, COORDINATOR_T_COMPACT]).toEqual([45, 30, 60])
  })
})

describe('parseContextUsageFile', () => {
  test('正向對照：583.1 寫出的完整記錄可還原', () => {
    const text = `${JSON.stringify(record())}\n`
    expect(parseContextUsageFile(text)).toEqual(record())
  })

  test('沒有 phase 欄位的舊版記錄（0.6.0）以 phase null 讀入', () => {
    const { phase: _phase, ...old } = record()
    expect(parseContextUsageFile(JSON.stringify(old))?.phase).toBeNull()
  })

  test('JSON 無效、缺 sessionId、window 或 measuredAt 不是數字時回傳 null', () => {
    expect(parseContextUsageFile('{"sessionId":')).toBeNull()
    expect(parseContextUsageFile(JSON.stringify({ ...record(), sessionId: 1 }))).toBeNull()
    expect(parseContextUsageFile(JSON.stringify({ ...record(), window: 'x' }))).toBeNull()
    expect(parseContextUsageFile(JSON.stringify({ ...record(), measuredAt: null }))).toBeNull()
  })
})

describe('selectedPercent：分母選擇規則', () => {
  test('auto-compact 開啟（threshold 有值）用 compactPercent；關閉（null）用 percent', () => {
    const split = { percent: 20, compactPercent: 50 }
    expect(selectedPercent(record({ ...split, autoCompactThreshold: 380_000 }))).toBe(50)
    expect(selectedPercent(record({ ...split, autoCompactThreshold: null }))).toBe(20)
  })

  test('選中值為 null（compact 後 tokens 缺席）時為 null，不當成 0', () => {
    expect(selectedPercent(record({ tokens: null, percent: null, compactPercent: null }))).toBeNull()
  })
})

describe('contextMarkOf：正向對照（必標）', () => {
  test('一般線持有 in_progress 票且達 45 → 待 compact', () => {
    expect(contextMarkOf({ record: record({ percent: 45, compactPercent: 45 }), role: 'lane', holdsInProgress: true })).toBe('compact')
  })

  test('一般線未持有 in_progress 票且達 30 → 待 clear', () => {
    expect(contextMarkOf({ record: record({ percent: 30, compactPercent: 30 }), role: 'lane', holdsInProgress: false })).toBe('clear')
  })

  test('主控達 60 → 待 compact', () => {
    expect(contextMarkOf({ record: record({ percent: 60, compactPercent: 60 }), role: 'coordinator', holdsInProgress: false })).toBe('compact')
  })

  test('分母差異：同一份記錄，auto-compact 開啟時以 compactPercent 跨門檻而標記，關閉時不標（兩組結果不同）', () => {
    const split = { percent: 20, compactPercent: 50 }
    const on = contextMarkOf({ record: record({ ...split, autoCompactThreshold: 380_000 }), role: 'lane', holdsInProgress: true })
    const off = contextMarkOf({ record: record({ ...split, autoCompactThreshold: null }), role: 'lane', holdsInProgress: true })
    expect(on).toBe('compact')
    expect(off).toBeNull()
  })

  test('分母差異反向：percent 跨門檻而 compactPercent 未跨，結果與上一組相反', () => {
    const split = { percent: 50, compactPercent: 20 }
    expect(contextMarkOf({ record: record({ ...split, autoCompactThreshold: 380_000 }), role: 'lane', holdsInProgress: true })).toBeNull()
    expect(contextMarkOf({ record: record({ ...split, autoCompactThreshold: null }), role: 'lane', holdsInProgress: true })).toBe('compact')
  })
})

describe('contextMarkOf：反向對照（不標）', () => {
  test('低於門檻不標：一般線持有票 44、未持有 29', () => {
    expect(contextMarkOf({ record: record({ percent: 44, compactPercent: 44 }), role: 'lane', holdsInProgress: true })).toBeNull()
    expect(contextMarkOf({ record: record({ percent: 29, compactPercent: 29 }), role: 'lane', holdsInProgress: false })).toBeNull()
  })

  test('主控與一般線的差異：同為 50 且持有票，一般線標待 compact、主控不標；同為 35 且未持有，一般線標待 clear、主控不標', () => {
    const at50 = record({ percent: 50, compactPercent: 50 })
    expect(contextMarkOf({ record: at50, role: 'lane', holdsInProgress: true })).toBe('compact')
    expect(contextMarkOf({ record: at50, role: 'coordinator', holdsInProgress: true })).toBeNull()
    const at35 = record({ percent: 35, compactPercent: 35 })
    expect(contextMarkOf({ record: at35, role: 'lane', holdsInProgress: false })).toBe('clear')
    expect(contextMarkOf({ record: at35, role: 'coordinator', holdsInProgress: false })).toBeNull()
  })

  test('compact 後無用量（tokens 缺席）不標', () => {
    const empty = record({ tokens: null, percent: null, compactPercent: null })
    expect(contextMarkOf({ record: empty, role: 'lane', holdsInProgress: true })).toBeNull()
    expect(contextMarkOf({ record: empty, role: 'lane', holdsInProgress: false })).toBeNull()
  })

  test('收線或不屬於任何線的 session（role none）不標', () => {
    expect(contextMarkOf({ record: record({ percent: 90, compactPercent: 90 }), role: 'none', holdsInProgress: false })).toBeNull()
  })

  test('沒有用量檔不標', () => {
    expect(contextMarkOf({ record: null, role: 'lane', holdsInProgress: true })).toBeNull()
  })
})

describe('contextUsageSuffix：各 session 列的用量字尾', () => {
  test('有用量時為 ctx <百分比>%（量測距今）；百分比依分母選擇規則', () => {
    expect(contextUsageSuffix(record({ measuredAt: NOW - 180_000 }), NOW)).toBe('ctx 40%（3 分前）')
    expect(contextUsageSuffix(record({ percent: 20, compactPercent: 50, autoCompactThreshold: 1 }), NOW)).toBe('ctx 50%（1 分前）')
  })

  test('compact 後無用量時寫「ctx 未量測」並附量測時間，不寫 0%', () => {
    expect(contextUsageSuffix(record({ tokens: null, percent: null, compactPercent: null }), NOW)).toBe('ctx 未量測（1 分前）')
  })

  test('沒有用量檔時沒有字尾', () => {
    expect(contextUsageSuffix(null, NOW)).toBeNull()
  })
})

describe('isDeletableUsagePath：刪除前的路徑檢查', () => {
  const dir = `/repo/${CONTEXT_USAGE_DIR}`

  test('正向對照：context 目錄下、檔名為 sessionId 格式的 .json 可刪', () => {
    expect(isDeletableUsagePath('/repo', `${dir}/${ID}.json`)).toBe(true)
  })

  test('反向對照：目錄外、子目錄、跳出目錄、檔名格式不符、非 .json 都不可刪', () => {
    expect(isDeletableUsagePath('/repo', `/repo/.claude/hook-logs/${ID}.json`)).toBe(false)
    expect(isDeletableUsagePath('/repo', `${dir}/sub/${ID}.json`)).toBe(false)
    expect(isDeletableUsagePath('/repo', `${dir}/../${ID}.json`)).toBe(false)
    expect(isDeletableUsagePath('/repo', `${dir}/a b.json`)).toBe(false)
    expect(isDeletableUsagePath('/repo', `${dir}/${ID}.txt`)).toBe(false)
    expect(isDeletableUsagePath('/repo', `${dir}/.json`)).toBe(false)
    expect(isDeletableUsagePath('/other', `${dir}/${ID}.json`)).toBe(false)
  })
})

describe('orphanUsageFiles：孤兒檔挑選', () => {
  const old = NOW - ORPHAN_AGE_MS - 1
  const fresh = NOW - ORPHAN_AGE_MS + 60_000
  const file = (name: string, mtimeMs: number, kind = 'file') => ({ name, kind, mtimeMs })

  test('正向對照：超過 24 小時且不屬於存活 session 的 .json 列入', () => {
    expect(orphanUsageFiles([file('dead.json', old)], new Set([ID]), NOW)).toEqual(['dead.json'])
  })

  test('反向對照：存活 session 的檔、未滿 24 小時、非一般檔、檔名格式不符都不列入', () => {
    const entries = [file(`${ID}.json`, old), file('young.json', fresh), file('dir.json', old, 'directory'), file('a b.json', old), file('x.txt', old)]
    expect(orphanUsageFiles(entries, new Set([ID]), NOW)).toEqual([])
  })
})

/** 本機時間的 `HH:MM`（徽章以本機時間顯示，測試機的時區不固定）。 */
const hhmm = (ms: number): string => {
  const date = new Date(ms)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

describe('contextMarkLabel：線標題的待 compact／待 clear 標記', () => {
  test('compact、clear 各有標記，null 為空字串', () => {
    expect([contextMarkLabel('compact'), contextMarkLabel('clear'), contextMarkLabel(null)]).toEqual(['［待 compact］', '［待 clear］', ''])
  })
})

describe('recentResume：恢復開工徽章的判定', () => {
  const resumed = (ago: number, source: 'compact' | 'clear' = 'compact') => record({ phase: { kind: 'resumed', source, at: NOW - ago } })

  test('正向對照：resumed 且未滿 10 分鐘（含剛好 10 分鐘）回傳 phase', () => {
    expect(RESUME_BADGE_MS).toBe(10 * 60 * 1000)
    expect(recentResume(resumed(9 * 60_000), NOW)).toEqual({ kind: 'resumed', source: 'compact', at: NOW - 9 * 60_000 })
    expect(recentResume(resumed(RESUME_BADGE_MS, 'clear'), NOW)?.source).toBe('clear')
  })

  test('反向對照：超過 10 分鐘、compacted 尚未開工、沒有 phase、沒有用量檔都為 null', () => {
    expect(recentResume(resumed(RESUME_BADGE_MS + 1), NOW)).toBeNull()
    expect(recentResume(record({ phase: { kind: 'compacted', source: 'compact', at: NOW - 1000 } }), NOW)).toBeNull()
    expect(recentResume(record(), NOW)).toBeNull()
    expect(recentResume(null, NOW)).toBeNull()
  })

  test('徽章文字：`［/<來源> 後已恢復 HH:MM］`，時間為本機時間', () => {
    const at = NOW - 120_000
    expect(resumeBadgeText({ kind: 'resumed', source: 'compact', at })).toBe(`［/compact 後已恢復 ${hhmm(at)}］`)
    expect(resumeBadgeText({ kind: 'resumed', source: 'clear', at })).toBe(`［/clear 後已恢復 ${hhmm(at)}］`)
  })
})

describe('laneContextLabel：線標題的標記與徽章', () => {
  const ticketToken = (serial: string): QueueToken => ({ kind: 'ticket', serial, id: `0.5.0-W1-${serial}`, note: '' })
  const tickets: TicketStatus[] = [
    { id: '0.5.0-W1-1', status: 'in_progress' },
    { id: '0.5.0-W1-2', status: 'pending' },
  ]
  const sessions = [session({ name: 'L-a', status: 'busy', sessionId: 'sid-a' }), session({ name: '主控', status: 'busy', sessionId: 'sid-m' })]
  const label = (sessionName: string | null, serials: string[], usages: Record<string, ContextUsageRecord>) =>
    laneContextLabel({ sessionName, tokens: serials.map(ticketToken), tickets, sessions, usages, nowMs: NOW })

  test('正向對照：持有 in_progress 票且達 45 標待 compact；未持有且達 30 標待 clear；主控達 60 標待 compact', () => {
    expect(label('L-a', ['2', '1'], { 'sid-a': record({ percent: 45 }) })).toBe('［待 compact］')
    expect(label('L-a', ['2'], { 'sid-a': record({ percent: 30 }) })).toBe('［待 clear］')
    expect(label('主控', ['2'], { 'sid-m': record({ percent: 60 }) })).toBe('［待 compact］')
  })

  test('正向對照：標記之後接恢復開工徽章', () => {
    const at = NOW - 60_000
    const usage = record({ percent: 50, phase: { kind: 'resumed', source: 'compact', at } })
    expect(label('L-a', ['1'], { 'sid-a': usage })).toBe(`［待 compact］［/compact 後已恢復 ${hhmm(at)}］`)
  })

  test('反向對照：低於門檻、主控未達 60、用量缺席、沒有 session 名稱、session 不存活或沒有用量檔都不標', () => {
    expect(label('L-a', ['1'], { 'sid-a': record({ percent: 44 }) })).toBe('')
    expect(label('L-a', ['2'], { 'sid-a': record({ percent: 29 }) })).toBe('')
    expect(label('主控', ['1'], { 'sid-m': record({ percent: 59 }) })).toBe('')
    expect(label('L-a', ['1'], { 'sid-a': record({ percent: null, compactPercent: null }) })).toBe('')
    expect(label(null, ['1'], { 'sid-a': record({ percent: 90 }) })).toBe('')
    expect(label('L-gone', ['1'], { 'sid-a': record({ percent: 90 }) })).toBe('')
    expect(label('L-a', ['1'], {})).toBe('')
  })
})

describe('parseContextUsageDetailed：解析失敗附原因', () => {
  test('成立時回傳與 parseContextUsageFile 相同的記錄', () => {
    const text = JSON.stringify(record())
    expect(parseContextUsageDetailed(text)).toEqual({ kind: 'ok', record: record() })
  })

  test('JSON 無效、不是物件、缺必要欄位各有不同原因', () => {
    const invalid = parseContextUsageDetailed('{"sessionId":')
    expect(invalid.kind).toBe('invalid')
    expect((invalid.kind === 'invalid' ? invalid.reason : '').startsWith('JSON 無效（')).toBe(true)
    expect(parseContextUsageDetailed('[]')).toEqual({ kind: 'invalid', reason: '缺 sessionId、window 或 measuredAt' })
    expect(parseContextUsageDetailed('3')).toEqual({ kind: 'invalid', reason: '內容不是 JSON 物件' })
    expect(parseContextUsageDetailed(JSON.stringify({ ...record(), window: 'x' }))).toEqual({
      kind: 'invalid',
      reason: '缺 sessionId、window 或 measuredAt',
    })
  })
})

describe('phaseText', () => {
  test('compacted 與 resumed 都列，附來源與本機 HH:MM，不受徽章 10 分鐘限制', () => {
    const at = NOW - RESUME_BADGE_MS - 60_000
    expect(phaseText({ kind: 'compacted', source: 'compact', at })).toBe(`phase compacted（compact，${hhmm(at)}）`)
    expect(phaseText({ kind: 'resumed', source: 'clear', at })).toBe(`phase resumed（clear，${hhmm(at)}）`)
  })
})

describe('laneContextStatus：line_status 的用量段', () => {
  const ticketToken = (serial: string): QueueToken => ({ kind: 'ticket', serial, id: `0.5.0-W1-${serial}`, note: '' })
  const tickets: TicketStatus[] = [{ id: '0.5.0-W1-1', status: 'in_progress' }]
  const sessions = [session({ name: 'L-a', status: 'busy', sessionId: 'sid-a' }), session({ name: 'L-nosid', status: 'busy', sessionId: null })]
  const status = (
    sessionName: string | null,
    usages: Record<string, ContextUsageRecord>,
    failures: Record<string, string> = {},
  ) => laneContextStatus({ sessionName, tokens: [ticketToken('1')], tickets, sessions, usages, failures, nowMs: NOW })

  test('有用量檔：用量接看板同一份的標記與徽章，有 phase 再接 phase 段', () => {
    const at = NOW - 60_000
    const usage = record({ percent: 47, phase: { kind: 'resumed', source: 'compact', at } })
    expect(status('L-a', { 'sid-a': usage })).toBe(`ctx 47%（1 分前）［待 compact］［/compact 後已恢復 ${hhmm(at)}］｜phase resumed（compact，${hhmm(at)}）`)
    expect(status('L-a', { 'sid-a': record({ percent: 20 }) })).toBe('ctx 20%（1 分前）')
  })

  test('無用量檔：寫「ctx 無用量檔」', () => {
    expect(status('L-a', {})).toBe('ctx 無用量檔')
  })

  test('compact 後尚未量測：寫「ctx 未量測」不標記，phase 為 compacted', () => {
    const at = NOW - 30_000
    const usage = record({ tokens: null, percent: null, compactPercent: null, phase: { kind: 'compacted', source: 'compact', at } })
    expect(status('L-a', { 'sid-a': usage })).toBe(`ctx 未量測（1 分前）｜phase compacted（compact，${hhmm(at)}）`)
  })

  test('用量檔解析失敗：寫出原因，不與「無用量檔」同句', () => {
    const text = status('L-a', {}, { 'sid-a': 'JSON 無效（Unexpected end）' })
    expect(text).toBe('ctx 用量檔解析失敗：JSON 無效（Unexpected end）')
    expect(text).not.toBe(status('L-a', {}))
  })

  test('持有者無從查起時沒有用量段：名稱未寫、名稱不存活、session 檔沒有 sessionId', () => {
    expect(status(null, { 'sid-a': record() })).toBeNull()
    expect(status('L-gone', { 'sid-a': record() })).toBeNull()
    expect(status('L-nosid', {})).toBeNull()
  })
})
