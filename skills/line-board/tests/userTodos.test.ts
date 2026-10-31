// userTodos.ts 的測試：協調票的用戶待辦行（U1）解析、完成行配對，以及看板「用戶待辦」群組的各行（U1 + 各線等用戶 U2）。

import { describe, expect, test } from 'claude-code/testing'

import { parseUserTodos, userTodoRows } from '../hooks/userTodos'
import type { WaitingItem } from '../types'

const PREFIX = '0.5.0-W1-'

/** 協調票：Solution 段以 lines 為內容，前後各有一段非 Solution 的二級標題。 */
const coordination = (lines: readonly string[]): string =>
  ['## Problem Analysis', '**用戶待辦**（pa）：Solution 段以外的待辦', '', '## Solution', ...lines, '', '## Test Results', '**用戶待辦**：Test Results 段的待辦'].join('\n')

describe('parseUserTodos', () => {
  test('正向對照：帶鍵與不帶鍵的待辦行各一，都列出；不帶鍵的行鍵為 null', () => {
    const todos = parseUserTodos(coordination(['**用戶待辦**（560）：裁定 SPEC 內文的出處型票號標注', '**用戶待辦**：開 L44 session']))
    expect(todos).toEqual([
      { key: '560', item: '裁定 SPEC 內文的出處型票號標注' },
      { key: null, item: '開 L44 session' },
    ])
  })

  test('完成行配對成功的項目不列出：帶鍵以鍵配對、不帶鍵以事項全文逐字配對', () => {
    const todos = parseUserTodos(
      coordination([
        '**用戶待辦**（560）：裁定 SPEC 內文的出處型票號標注',
        '**用戶待辦**：開 L44 session',
        '**用戶待辦**（sync-push）：授權 sync-push',
        '**用戶待辦完成**（560）：用戶裁定採方案 A',
        '**用戶待辦完成**：開 L44 session',
      ]),
    )
    expect(todos).toEqual([{ key: 'sync-push', item: '授權 sync-push' }])
  })

  test('完成行的鍵配不到任何待辦時，不刪除其他項（含不帶鍵的完成行只差一字）', () => {
    const lines = ['**用戶待辦**（560）：裁定標注', '**用戶待辦**：開 L44 session']
    const before = parseUserTodos(coordination(lines))
    const after = parseUserTodos(coordination([...lines, '**用戶待辦完成**（561）：無關的鍵', '**用戶待辦完成**：開 L44 session。']))
    expect(before).toHaveLength(2)
    expect(after).toEqual(before)
  })

  test('帶鍵與不帶鍵分開配對：不帶鍵的完成行內容恰等於某個鍵，或帶鍵的完成行鍵恰等於某個不帶鍵的事項，都不刪除對方', () => {
    const todos = parseUserTodos(
      coordination([
        '**用戶待辦**（560）：裁定標注',
        '**用戶待辦**：sync-push',
        '**用戶待辦完成**：560',
        '**用戶待辦完成**（sync-push）：無關',
      ]),
    )
    expect(todos).toEqual([
      { key: '560', item: '裁定標注' },
      { key: null, item: 'sync-push' },
    ])
  })

  test('空括號的行略過：不列為待辦，也不當作全文配對的完成行', () => {
    const todos = parseUserTodos(coordination(['**用戶待辦**：開 L44 session', '**用戶待辦**（）：空鍵待辦', '**用戶待辦完成**（）：開 L44 session']))
    expect(todos).toEqual([{ key: null, item: '開 L44 session' }])
  })

  test('同一個鍵以最後一行為準：完成後再寫待辦行即重新列出，並排到最後', () => {
    const todos = parseUserTodos(
      coordination([
        '**用戶待辦**（560）：第一版',
        '**用戶待辦**（562）：另一項',
        '**用戶待辦完成**（560）：已處理',
        '**用戶待辦**（560）：第二版',
      ]),
    )
    expect(todos).toEqual([
      { key: '562', item: '另一項' },
      { key: '560', item: '第二版' },
    ])
  })

  test('不算待辦：縮排行、清單項、fence 內的範例、Solution 段以外的行', () => {
    const todos = parseUserTodos(
      coordination([
        '  **用戶待辦**（a）：縮排行',
        '- **用戶待辦**（b）：清單項',
        '```',
        '**用戶待辦**（c）：fence 內的格式範例',
        '```',
        '**用戶待辦**（d）：唯一該列的',
      ]),
    )
    expect(todos).toEqual([{ key: 'd', item: '唯一該列的' }])
  })

  test('fence 內的完成行不解除待辦', () => {
    const todos = parseUserTodos(coordination(['**用戶待辦**（560）：裁定', '```', '**用戶待辦完成**（560）：範例', '```']))
    expect(todos).toEqual([{ key: '560', item: '裁定' }])
  })

  test('沒有 Solution 段或沒有待辦行時為空陣列', () => {
    expect(parseUserTodos('## Problem Analysis\n**用戶待辦**：x')).toEqual([])
    expect(parseUserTodos(coordination(['**L7 現行佇列**：100']))).toEqual([])
  })
})

describe('userTodoRows', () => {
  const waiting = (fields: Partial<WaitingItem> & Pick<WaitingItem, 'source' | 'item'>): WaitingItem => ({
    lane: 7,
    session: 'L7（文件）',
    ticketId: null,
    ...fields,
  })

  test('U1 在前、U2 在後；U1 為「事項｜鍵」，不帶鍵寫「主控」；U2 為「事項｜L<n> 短票號（S#）」，沒有票號時只有線號', () => {
    const rows = userTodoRows(
      [
        { key: '560', item: '裁定標注' },
        { key: null, item: '開 L44 session' },
      ],
      [
        waiting({ source: 'S1', item: '實測 --debug', ticketId: '0.5.0-W1-575' }),
        waiting({ source: 'S2', item: 'input needed', lane: 13 }),
      ],
      PREFIX,
    )
    expect(rows.map(row => row.text)).toEqual(['裁定標注｜560', '開 L44 session｜主控', '實測 --debug｜L7 575（S1）', 'input needed｜L13（S2）'])
  })

  test('只有 S2 標為要人處理（洋紅），U1 與 S1、S3 不上色', () => {
    const rows = userTodoRows(
      [{ key: 'a', item: 'x' }],
      [waiting({ source: 'S1', item: 'p' }), waiting({ source: 'S3', item: 'q' }), waiting({ source: 'S2', item: 'r' })],
      PREFIX,
    )
    expect(rows.map(row => row.isSessionWaiting)).toEqual([false, false, false, true])
  })

  test('票號不帶前綴時原樣顯示', () => {
    const rows = userTodoRows([], [waiting({ source: 'S3', item: 'q', ticketId: '0.6.0-W2-010' })], PREFIX)
    expect(rows.map(row => row.text)).toEqual(['q｜L7 0.6.0-W2-010（S3）'])
  })
})
