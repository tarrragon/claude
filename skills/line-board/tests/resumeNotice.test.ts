// resumeNotice.ts 的測試：線 session 在 /compact 或 /clear 後恢復開工的判定、通知對象與通知文字。
// 正向對照：compact（含 auto）與 clear 各一必觸發；反向對照：每個排除條件各一，不得觸發。

import { describe, expect, test } from 'claude-code/testing'

import { resumeNoticeDecision, resumeNoticeText, resumePhaseOf, stepResume } from '../hooks/resumeNotice'
import type { PendingResume, ResumeEvent } from '../hooks/resumeNotice'
import type { LaneLine } from '../types'

const T0 = 1_793_450_000_000
const T1 = T0 + 60_000

/** 依序套用事件，回傳最後一步的結果與過程中所有恢復開工。 */
function run(events: readonly ResumeEvent[], start: PendingResume | null = null) {
  let pending = start
  const resumed = []
  for (const event of events) {
    const step = stepResume(pending, event)
    pending = step.pending
    if (step.resumed !== null) resumed.push(step.resumed)
  }
  return { pending, resumed }
}

const manualCompact: ResumeEvent = { kind: 'compact', trigger: 'manual', isSkipped: false, at: T0 }
const work: ResumeEvent = { kind: 'submit', at: T1 }

describe('stepResume：正向對照（必須觸發）', () => {
  test('compact 完成後第一個 prompt 視為恢復開工，來源 compact', () => {
    const { resumed, pending } = run([manualCompact, work])
    expect(resumed).toEqual([{ source: 'compact', at: T0, resumedAt: T1 }])
    expect(pending).toBeNull()
  })

  test('auto compact（trigger=auto）照樣算 compact 完成', () => {
    const { resumed } = run([{ kind: 'compact', trigger: 'auto', isSkipped: false, at: T0 }, work])
    expect(resumed).toEqual([{ source: 'compact', at: T0, resumedAt: T1 }])
  })

  test('clear（session.end reason=clear）後第一個 prompt 視為恢復開工，來源 clear', () => {
    const { resumed } = run([{ kind: 'end', reason: 'clear', at: T0 }, work])
    expect(resumed).toEqual([{ source: 'clear', at: T0, resumedAt: T1 }])
  })

  test('slash command（非 /compact、/clear）也算開工', () => {
    const { resumed } = run([manualCompact, { kind: 'submit', command: 'ticket', at: T1 }])
    expect(resumed).toHaveLength(1)
  })

  test('同一次 compact 只觸發一次：第二個 prompt 不再觸發', () => {
    const { resumed } = run([manualCompact, work, { kind: 'submit', at: T1 + 1 }])
    expect(resumed).toHaveLength(1)
  })
})

describe('stepResume：反向對照（不得觸發）', () => {
  test('compact 被否決（skip）不設待通知', () => {
    expect(run([{ ...manualCompact, isSkipped: true }, work]).resumed).toEqual([])
  })

  test('precompute 不設待通知', () => {
    expect(run([{ kind: 'compact', trigger: 'precompute', isSkipped: false, at: T0 }, work]).resumed).toEqual([])
  })

  test('subagent 自己的 compact（帶 agentId）不設待通知', () => {
    expect(run([{ ...manualCompact, agentId: 'a123' }, work]).resumed).toEqual([])
  })

  test('session.end reason=resume 不設待通知，且清掉先前的待通知', () => {
    expect(run([{ kind: 'end', reason: 'resume', at: T0 }, work]).resumed).toEqual([])
    expect(run([manualCompact, { kind: 'end', reason: 'resume', at: T0 + 1 }, work]).resumed).toEqual([])
  })

  test('/compact 與 /clear 本身的 prompt.submit 不算開工，待通知保留', () => {
    const afterCompactCommand = run([manualCompact, { kind: 'submit', command: 'compact', at: T1 }])
    expect(afterCompactCommand.resumed).toEqual([])
    expect(afterCompactCommand.pending).toEqual({ source: 'compact', at: T0 })
    const afterClearCommand = run([{ kind: 'end', reason: 'clear', at: T0 }, { kind: 'submit', command: 'clear', at: T1 }])
    expect(afterClearCommand.resumed).toEqual([])
    expect(afterClearCommand.pending).toEqual({ source: 'clear', at: T0 })
  })

  test('沒有 compact 或 clear 時（startup），prompt 不觸發', () => {
    expect(run([work]).resumed).toEqual([])
  })
})

const lines: LaneLine[] = [
  { lane: 39, session: '看板工具', queue: '0.5.0-W1-585 → 0.5.0-W1-583.2' },
  { lane: 40, session: '主控', queue: '0.5.0-W1-349' },
  { lane: 41, session: '已收線的線', queue: '（結束）' },
  { lane: 42, session: '收線附說明', queue: '無（併入 L39）' },
]

describe('resumeNoticeDecision：送或不送，不送時帶原因（寫入送出紀錄檔）', () => {
  test('正向對照：比對到未收線的線為 send，帶線號與名稱', () => {
    expect(resumeNoticeDecision({ sessionName: '看板工具', lines })).toEqual({ kind: 'send', target: { lane: 39, name: '看板工具' } })
  })

  test('每個不送條件各帶自己的原因', () => {
    expect(resumeNoticeDecision({ sessionName: null, lines })).toEqual({ kind: 'skip', reason: 'no-session-name' })
    expect(resumeNoticeDecision({ sessionName: '主控', lines })).toEqual({ kind: 'skip', reason: 'coordinator' })
    expect(resumeNoticeDecision({ sessionName: '不存在的線', lines })).toEqual({ kind: 'skip', reason: 'lane-not-found' })
    expect(resumeNoticeDecision({ sessionName: '已收線的線', lines })).toEqual({ kind: 'skip', reason: 'lane-ended' })
    expect(resumeNoticeDecision({ sessionName: '收線附說明', lines })).toEqual({ kind: 'skip', reason: 'lane-ended' })
  })
})

describe('resumeNoticeText', () => {
  test('固定一行：L<n>（<名稱>）已恢復開工：<時間>，來源 <compact|clear>', () => {
    expect(resumeNoticeText({ lane: 39, name: '看板工具' }, '21:30:05', 'compact')).toBe('L39（看板工具）已恢復開工：21:30:05，來源 compact')
    expect(resumeNoticeText({ lane: 39, name: '看板工具' }, '21:30:05', 'clear')).toBe('L39（看板工具）已恢復開工：21:30:05，來源 clear')
    expect(resumeNoticeText({ lane: 39, name: '看板工具' }, '21:30:05', 'compact')).not.toContain('\n')
  })
})

describe('resumePhaseOf：輔管道寫入用量檔的 phase', () => {
  test('有待通知時為 compacted，恢復開工後為 resumed，皆帶來源與時間', () => {
    expect(resumePhaseOf({ source: 'compact', at: T0 }, null)).toEqual({ kind: 'compacted', source: 'compact', at: T0 })
    expect(resumePhaseOf(null, { source: 'clear', at: T0, resumedAt: T1 })).toEqual({ kind: 'resumed', source: 'clear', at: T1 })
  })

  test('兩者皆無時為 null（不寫成空物件）', () => {
    expect(resumePhaseOf(null, null)).toBeNull()
  })
})
