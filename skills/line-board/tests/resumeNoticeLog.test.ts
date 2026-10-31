// resumeNoticeLog.ts 的測試：恢復開工通知的送出紀錄行與上限截斷。
// 正反對照（E2）：不送（target 為 null）寫出原因、送出被拒（isDelivered=false）寫出 reason、送達寫 isDelivered=true；
// 三處提早結束（主管道關閉、設定讀不到、session 或協調票讀不到）與例外各自寫出步驟與原因。

import { describe, expect, test } from 'claude-code/testing'

import { RESUME_NOTICE_LOG_MAX_LINES, appendCappedLog, resumeNoticeLogLine } from '../hooks/resumeNoticeLog'
import type { ResumeNoticeOutcome } from '../hooks/resumeNoticeLog'

const BASE = { time: '2026-10-31 22:30:05', sessionId: 'abcdef12-3456-7890-abcd-ef1234567890', source: 'compact' as const }
const lineOf = (outcome: ResumeNoticeOutcome) => resumeNoticeLogLine({ ...BASE, outcome })

describe('resumeNoticeLogLine：共同欄位', () => {
  test('一行含時間、sessionId 前 8 碼、來源與步驟，欄位以 tab 分隔', () => {
    const line = lineOf({ step: 'sent', isDelivered: true })
    expect(line.split('\t').slice(0, 4)).toEqual(['2026-10-31 22:30:05', 'session=abcdef12', 'source=compact', 'step=sent'])
    expect(line).not.toContain('3456-7890')
  })

  test('原因含換行時壓成一行（一次恢復開工只占一行）', () => {
    const line = lineOf({ step: 'error', detail: '第一行\n第二行\r\n第三行' })
    expect(line).not.toMatch(/[\r\n]/)
    expect(line).toContain('detail=第一行 第二行 第三行')
  })
})

describe('resumeNoticeLogLine：送出結果（E2 正反對照）', () => {
  test('送達：isDelivered=true，不帶 reason', () => {
    const line = lineOf({ step: 'sent', isDelivered: true })
    expect(line).toContain('isDelivered=true')
    expect(line).not.toContain('reason=')
  })

  test('送出被拒：isDelivered=false 並寫出 reason', () => {
    const line = lineOf({ step: 'sent', isDelivered: false, reason: 'held' })
    expect(line).toContain('isDelivered=false')
    expect(line).toContain('reason=held')
  })

  test('target 為 null：寫出不送的原因，且沒有 isDelivered', () => {
    for (const reason of ['no-session-name', 'coordinator', 'lane-not-found', 'lane-ended'] as const) {
      const line = lineOf({ step: 'skipped', reason })
      expect(line).toContain('step=skipped')
      expect(line).toContain(`reason=${reason}`)
      expect(line).not.toContain('isDelivered')
    }
  })
})

describe('resumeNoticeLogLine：提早結束與例外都寫原因', () => {
  test('主管道關閉', () => {
    expect(lineOf({ step: 'send-disabled' })).toContain('step=send-disabled')
  })

  test('設定讀不到：寫出設定的判定與訊息', () => {
    expect(lineOf({ step: 'config-unavailable', detail: 'missing：ENOENT' })).toContain('step=config-unavailable\tdetail=missing：ENOENT')
  })

  test('session 狀態或協調票讀不到：寫出是哪一個與訊息', () => {
    expect(lineOf({ step: 'state-unavailable', detail: '協調票：讀不到票檔' })).toContain('step=state-unavailable\tdetail=協調票：讀不到票檔')
  })

  test('例外：寫出例外訊息', () => {
    expect(lineOf({ step: 'error', detail: 'boom' })).toContain('step=error\tdetail=boom')
  })
})

describe('appendCappedLog', () => {
  test('空檔：只有新的一行，結尾換行', () => {
    expect(appendCappedLog('', 'a', 3)).toBe('a\n')
  })

  test('既有內容之後接上新的一行', () => {
    expect(appendCappedLog('a\nb\n', 'c', 3)).toBe('a\nb\nc\n')
  })

  test('既有內容缺結尾換行時不黏行', () => {
    expect(appendCappedLog('a\nb', 'c', 3)).toBe('a\nb\nc\n')
  })

  test('超過上限只留最後 maxLines 行（不無限增長）', () => {
    expect(appendCappedLog('a\nb\nc\n', 'd', 3)).toBe('b\nc\nd\n')
  })

  test('上限為正整數', () => {
    expect(Number.isInteger(RESUME_NOTICE_LOG_MAX_LINES)).toBe(true)
    expect(RESUME_NOTICE_LOG_MAX_LINES).toBeGreaterThan(0)
  })
})
