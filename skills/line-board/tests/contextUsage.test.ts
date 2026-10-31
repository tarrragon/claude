// contextUsage.ts 的測試：session.measure 寫入的 context 用量檔——何時寫、寫到哪、寫什麼。
// compact 後 tokens 缺席時記錄必須是 null 而非 0（0 會被讀成「幾乎沒用」），以正反兩組輸入對照。

import { describe, expect, test } from 'claude-code/testing'

import {
  CONTEXT_USAGE_DIR,
  contextUsagePath,
  contextUsageRecord,
  isContextChanged,
  serializeContextUsage,
} from '../hooks/contextUsage'

const SESSION_ID = 'b953833f-4d2e-43c3-82c6-7ef169a4b86b'
const MEASURED_AT = 1_793_000_000_000

describe('isContextChanged', () => {
  test('正向對照：changed 含 context 時要寫檔', () => {
    expect(isContextChanged(['context'])).toBe(true)
    expect(isContextChanged(['rateLimits', 'context', 'cost'])).toBe(true)
  })

  test('changed 只含 rateLimits 或 cost 時不寫檔', () => {
    expect(isContextChanged(['rateLimits'])).toBe(false)
    expect(isContextChanged(['cost'])).toBe(false)
    expect(isContextChanged(['rateLimits', 'cost'])).toBe(false)
  })
})

describe('contextUsagePath', () => {
  test('寫到主 checkout 的 hook-logs/line-board/context/<sessionId>.json', () => {
    expect(contextUsagePath('/repo', SESSION_ID)).toBe(`/repo/${CONTEXT_USAGE_DIR}/${SESSION_ID}.json`)
  })

  test('sessionId 含路徑字元或為空時不給路徑（不寫出 context 目錄之外）', () => {
    expect(contextUsagePath('/repo', '../escape')).toBeNull()
    expect(contextUsagePath('/repo', 'a/b')).toBeNull()
    expect(contextUsagePath('/repo', '')).toBeNull()
  })
})

describe('contextUsageRecord', () => {
  test('正向對照：有 tokens 時記錄 tokens、window、percent 與量測時間', () => {
    const record = contextUsageRecord({
      sessionId: SESSION_ID,
      context: { tokens: 120_000, window: 200_000, percent: 60 },
      compaction: null,
      measuredAt: MEASURED_AT,
    })
    expect(record).toEqual({
      sessionId: SESSION_ID,
      phase: null,
      tokens: 120_000,
      window: 200_000,
      percent: 60,
      compactWindow: null,
      compactPercent: null,
      autoCompactThreshold: null,
      measuredAt: MEASURED_AT,
    })
  })

  test('compact 後 tokens 與 percent 缺席時記為 null，不寫成 0（與有值的對照組不同）', () => {
    const present = contextUsageRecord({
      sessionId: SESSION_ID,
      context: { tokens: 30_000, window: 200_000, percent: 15 },
      compaction: null,
      measuredAt: MEASURED_AT,
    })
    const absent = contextUsageRecord({ sessionId: SESSION_ID, context: { window: 200_000 }, compaction: null, measuredAt: MEASURED_AT })
    expect(absent.tokens).toBeNull()
    expect(absent.percent).toBeNull()
    expect(absent.compactPercent).toBeNull()
    expect(absent.window).toBe(200_000)
    expect(present.tokens).not.toBe(absent.tokens)
    expect(present.percent).not.toBe(absent.percent)
  })

  test('有 compaction window 時另算以它為分母的百分比（四捨五入整數）', () => {
    const record = contextUsageRecord({
      sessionId: SESSION_ID,
      context: { tokens: 100_000, window: 1_000_000, percent: 10 },
      compaction: { rawMaxTokens: 400_000, autoCompactThreshold: 380_000 },
      measuredAt: MEASURED_AT,
    })
    expect(record.compactWindow).toBe(400_000)
    expect(record.compactPercent).toBe(25)
    expect(record.autoCompactThreshold).toBe(380_000)
    expect(record.percent).toBe(10)
  })

  test('正向對照：帶 phase 時記錄保留 phase；不帶時為 null（不省略欄位）', () => {
    const phase = { kind: 'resumed', source: 'compact', at: MEASURED_AT - 1 } as const
    const withPhase = contextUsageRecord({
      sessionId: SESSION_ID,
      context: { tokens: 1, window: 200_000, percent: 0 },
      compaction: null,
      phase,
      measuredAt: MEASURED_AT,
    })
    const withoutPhase = contextUsageRecord({ sessionId: SESSION_ID, context: { tokens: 1, window: 200_000, percent: 0 }, compaction: null, measuredAt: MEASURED_AT })
    expect(withPhase.phase).toEqual(phase)
    expect(withoutPhase.phase).toBeNull()
    expect(JSON.parse(serializeContextUsage(withoutPhase))).toHaveProperty('phase', null)
  })

  test('auto-compact 關閉時 autoCompactThreshold 為 null', () => {
    const record = contextUsageRecord({
      sessionId: SESSION_ID,
      context: { tokens: 1, window: 200_000, percent: 0 },
      compaction: { rawMaxTokens: 200_000 },
      measuredAt: MEASURED_AT,
    })
    expect(record.autoCompactThreshold).toBeNull()
    expect(record.compactWindow).toBe(200_000)
  })
})

describe('serializeContextUsage', () => {
  test('輸出可被 JSON.parse 還原的整份記錄，結尾換行', () => {
    const record = contextUsageRecord({ sessionId: SESSION_ID, context: { window: 200_000 }, compaction: null, measuredAt: MEASURED_AT })
    const text = serializeContextUsage(record)
    expect(text.endsWith('\n')).toBe(true)
    expect(JSON.parse(text)).toEqual(record)
    // null 欄位保留在檔內（讀者據以判定「量測過但缺席」，而非「欄位遺失」）
    expect(JSON.parse(text)).toHaveProperty('tokens', null)
  })
})
