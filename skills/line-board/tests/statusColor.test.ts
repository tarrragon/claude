// statusColor.ts 的測試：五種狀態的顏色、派發階段與佇列票與 session 狀態歸到哪一種狀態。

import { describe, expect, test } from 'claude-code/testing'

import { boardStateColor, dispatchStageState, queueTicketState, sessionState } from '../hooks/statusColor'

describe('boardStateColor', () => {
  test('五種狀態各一色：待辦灰、進行中綠、代理人執行中青、閘門黃、要人處理洋紅', () => {
    expect(boardStateColor('待辦')).toBe('gray')
    expect(boardStateColor('進行中')).toBe('green')
    expect(boardStateColor('代理人執行中')).toBe('cyan')
    expect(boardStateColor('閘門')).toBe('yellow')
    expect(boardStateColor('要人處理')).toBe('magenta')
  })

  test('五色互不相同，且「進行中」避開標題列的主題鍵 suggestion、紅（錯誤）', () => {
    const colors = (['待辦', '進行中', '代理人執行中', '閘門', '要人處理'] as const).map(boardStateColor)
    expect(new Set(colors).size).toBe(5)
    expect(['suggestion', 'red', 'yellow', 'magenta', 'cyan']).not.toContain(boardStateColor('進行中'))
  })

  test('對照：不屬五種的輸入與 null 不上色', () => {
    expect(boardStateColor('unknown')).toBeUndefined()
    expect(boardStateColor(null)).toBeUndefined()
  })
})

describe('dispatchStageState', () => {
  test('實作、審查、事故分析為代理人執行中；閘門為閘門；收尾為要人處理', () => {
    expect(dispatchStageState('實作')).toBe('代理人執行中')
    expect(dispatchStageState('審查')).toBe('代理人執行中')
    expect(dispatchStageState('事故分析')).toBe('代理人執行中')
    expect(dispatchStageState('閘門')).toBe('閘門')
    expect(dispatchStageState('收尾')).toBe('要人處理')
  })
})

describe('queueTicketState', () => {
  test('沒有派發列也不在閘門：pending 為待辦、in_progress 為進行中', () => {
    expect(queueTicketState('pending', [])).toBe('待辦')
    expect(queueTicketState('in_progress', [])).toBe('進行中')
  })

  test('有派發列時依階段：代理人未結束為代理人執行中、收尾為要人處理、閘門為閘門，票的 status 不影響', () => {
    expect(queueTicketState('in_progress', ['實作'])).toBe('代理人執行中')
    expect(queueTicketState('pending', ['審查'])).toBe('代理人執行中')
    expect(queueTicketState('in_progress', ['收尾'])).toBe('要人處理')
    expect(queueTicketState('in_progress', ['閘門'])).toBe('閘門')
  })

  test('同一張票有多個階段時：閘門優先，其次要人處理，再其次代理人執行中', () => {
    expect(queueTicketState('in_progress', ['實作', '收尾'])).toBe('要人處理')
    expect(queueTicketState('in_progress', ['收尾', '閘門', '審查'])).toBe('閘門')
    expect(queueTicketState('in_progress', ['事故分析', '審查'])).toBe('代理人執行中')
  })

  test('對照：狀態讀不到、unknown 或其他值且沒有派發列時不歸任何狀態', () => {
    expect(queueTicketState(undefined, [])).toBeNull()
    expect(queueTicketState('unknown', [])).toBeNull()
    expect(queueTicketState('blocked', [])).toBeNull()
  })
})

describe('sessionState', () => {
  test('waiting 為要人處理；對照：busy、idle、shell 不歸任何狀態', () => {
    expect(sessionState('waiting')).toBe('要人處理')
    expect(sessionState('busy')).toBeNull()
    expect(sessionState('idle')).toBeNull()
    expect(sessionState('shell')).toBeNull()
  })
})
