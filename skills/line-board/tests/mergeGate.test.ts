// mergeGate.ts 的測試：合併閘門紀錄篩選與欄位解析、短分支名、顯示文字與結果顏色、閘門持有者判定。

import { describe, expect, test } from 'claude-code/testing'

import { MALFORMED_GATE_LINES, MERGE_LOG, MERGE_LOG_HOLDING, MERGE_LOG_OVERLAP, overlapLogUntil } from './fixtures'
import {
  formatMergeGateEntry,
  formatMergeGateHolders,
  mergeGateEntries,
  mergeGateHolders,
  mergeGateLines,
  mergeGateResultColor,
  parseMergeGateLine,
  shortBranch,
} from '../hooks/mergeGate'

describe('mergeGateLines', () => {
  test('只保留 [合併閘門] 的開始與結束行；預檢、驗收、測試行濾掉', () => {
    const lines = mergeGateLines(MERGE_LOG, 8)
    expect(lines.length).toBe(2)
    expect(lines[0]).toContain('[合併閘門] 開始')
    expect(lines[1]).toContain('[合併閘門] 結束')
    expect(lines.some(line => line.includes('預檢'))).toBe(false)
    expect(lines.some(line => line.includes('[合併前測試]'))).toBe(false)
    expect(lines.some(line => line.includes('[合併前驗收]'))).toBe(false)
  })

  test('篩選後取最後 n 行', () => {
    expect(mergeGateLines(MERGE_LOG, 1)).toEqual([
      '2026-10-19T16:11:45 [合併閘門] 結束｜target main｜分支 feat/0.5.0-W1-328｜commit a9dc3b442c24｜結果 寫入',
    ])
  })
})

describe('parseMergeGateLine', () => {
  test('開始行取時間（HH:MM:SS）與分支；結束行另取結果', () => {
    expect(
      parseMergeGateLine('2026-10-19T16:04:26 [合併閘門] 開始｜target main｜分支 feat/0.5.0-W1-328｜commit ee5e80e6b9a4'),
    ).toEqual({ kind: 'start', time: '16:04:26', branch: 'feat/0.5.0-W1-328' })
    expect(
      parseMergeGateLine(
        '2026-10-19T16:11:45 [合併閘門] 結束｜target main｜分支 feat/0.5.0-W1-328｜commit a9dc3b442c24｜結果 寫入',
      ),
    ).toEqual({ kind: 'end', time: '16:11:45', branch: 'feat/0.5.0-W1-328', result: '寫入' })
  })

  test('反例：格式不符的行原樣保留為 raw，不丟棄、不拋錯', () => {
    for (const line of MALFORMED_GATE_LINES) {
      expect(parseMergeGateLine(line)).toEqual({ kind: 'raw', text: line })
    }
  })

  test('格式不符的行仍在 mergeGateEntries 結果中，順序不變', () => {
    const text = [MERGE_LOG, ...MALFORMED_GATE_LINES].join('\n')
    expect(mergeGateEntries(text).map(entry => entry.kind)).toEqual(['start', 'end', 'raw', 'raw', 'raw'])
  })
})

describe('shortBranch', () => {
  test('worktree-agent-<id> 縮成 agent-<前 6 碼>，feat/<票號> 縮成票號，其他分支原樣', () => {
    expect(shortBranch('worktree-agent-a352c31d77c3daa98')).toBe('agent-a352c3')
    expect(shortBranch('feat/0.5.0-W1-351')).toBe('0.5.0-W1-351')
    expect(shortBranch('worktree-e-batch-306')).toBe('worktree-e-batch-306')
  })
})

describe('formatMergeGateEntry', () => {
  test('開始行為 時間｜開始｜短分支，結束行另接結果；raw 為原文', () => {
    const [start, end] = mergeGateEntries(MERGE_LOG)
    expect(start === undefined ? '' : formatMergeGateEntry(start)).toBe('16:04:26｜開始｜0.5.0-W1-328')
    expect(end === undefined ? '' : formatMergeGateEntry(end)).toBe('16:11:45｜結束｜0.5.0-W1-328｜寫入')
    expect(formatMergeGateEntry({ kind: 'raw', text: 'x [合併閘門] 開始' })).toBe('x [合併閘門] 開始')
  })
})

describe('mergeGateResultColor', () => {
  test('寫入綠、中止黃、拒絕與紅燈紅，其他結果不上色', () => {
    expect(mergeGateResultColor('寫入')).toBe('green')
    expect(mergeGateResultColor('中止')).toBe('yellow')
    expect(mergeGateResultColor('拒絕')).toBe('red')
    expect(mergeGateResultColor('紅燈')).toBe('red')
    expect(mergeGateResultColor('其他')).toBeUndefined()
  })
})

describe('mergeGateHolders', () => {
  test('重疊的合併：16:21 之後至 16:31:50 前 a352 仍列為持有者；預檢行不當成結束', () => {
    const a352 = { branch: 'worktree-agent-a352c31d77c3daa98', since: '16:19:45' }
    const a748 = { branch: 'worktree-agent-a74808594aa6f7e6f', since: '16:21:08' }
    // 16:19:46 的預檢行帶分支與結果欄，若被當成結束，a352 在此就會消失
    expect(mergeGateHolders(mergeGateEntries(overlapLogUntil('16:19:46')))).toEqual([a352])
    expect(mergeGateHolders(mergeGateEntries(overlapLogUntil('16:21:08')))).toEqual([a352, a748])
    expect(mergeGateHolders(mergeGateEntries(overlapLogUntil('16:21:11')))).toEqual([a352])
    expect(mergeGateHolders(mergeGateEntries(overlapLogUntil('16:31:49')))).toEqual([a352])
    expect(formatMergeGateHolders([a352, a748])).toEqual([
      '閘門使用中：agent-a352c3（自 16:19:45）',
      '閘門使用中：agent-a74808（自 16:21:08）',
    ])
  })

  test('對照：所有開始都有同分支的結束時回傳空陣列，不顯示任何持有者', () => {
    expect(mergeGateHolders(mergeGateEntries(MERGE_LOG_OVERLAP))).toEqual([])
    expect(mergeGateHolders(mergeGateEntries(MERGE_LOG))).toEqual([])
    expect(mergeGateHolders([])).toEqual([])
    expect(formatMergeGateHolders([])).toEqual([])
  })

  test('開始與結束交錯時，只列出尚未結束的分支', () => {
    const holders = mergeGateHolders(mergeGateEntries(MERGE_LOG_HOLDING))
    expect(holders).toEqual([{ branch: 'feat/0.5.0-W1-351', since: '16:41:49' }])
    expect(formatMergeGateHolders(holders)).toEqual(['閘門使用中：0.5.0-W1-351（自 16:41:49）'])
  })

  test('同分支先前已結束、重新開始後尚未結束時，仍視為持有', () => {
    const text = [MERGE_LOG, '2026-10-19T17:00:00 [合併閘門] 開始｜target main｜分支 feat/0.5.0-W1-328｜commit 1'].join('\n')
    expect(mergeGateHolders(mergeGateEntries(text))).toEqual([{ branch: 'feat/0.5.0-W1-328', since: '17:00:00' }])
  })

  test('同分支連續兩筆開始而無結束時只列一次，取較晚的開始時間', () => {
    const text = [
      '2026-10-19T17:00:00 [合併閘門] 開始｜target main｜分支 feat/0.5.0-W1-500｜commit 1',
      '2026-10-19T17:01:00 [合併閘門] 開始｜target main｜分支 feat/0.5.0-W1-501｜commit 2',
      '2026-10-19T17:02:00 [合併閘門] 開始｜target main｜分支 feat/0.5.0-W1-500｜commit 3',
    ].join('\n')
    expect(mergeGateHolders(mergeGateEntries(text))).toEqual([
      { branch: 'feat/0.5.0-W1-501', since: '17:01:00' },
      { branch: 'feat/0.5.0-W1-500', since: '17:02:00' },
    ])
  })

  test('其他分支的結束行不算對應結束', () => {
    const text = [
      '2026-10-19T17:00:00 [合併閘門] 開始｜target main｜分支 feat/0.5.0-W1-500｜commit 1',
      '2026-10-19T17:00:05 [合併閘門] 結束｜target main｜分支 feat/0.5.0-W1-499｜commit 2｜結果 寫入',
    ].join('\n')
    expect(mergeGateHolders(mergeGateEntries(text))).toEqual([{ branch: 'feat/0.5.0-W1-500', since: '17:00:00' }])
  })
})
