// 用戶待辦：協調票 Solution 的用戶待辦行（U1，主控寫）與完成行配對，以及看板「用戶待辦」群組的各行（U1 + 各線等用戶 U2）。
// U2 的判定沿用 waiting.ts（與 line_status 的「等用戶」段同一份），本檔只負責組成顯示列。
// 格式權威：multi-session-orchestration 的 references/line-continuity.md〈用戶待辦〉。
// 不碰 $（無檔案、無行程），讓 *.test.ts 能直接驗證；讀檔由 readers.ts 負責、繪製由 userTodosView.tsx 負責。

import type { UserTodo, UserTodoRow, WaitingItem } from '../types'
import { unfencedSolutionLines } from './lanes'

/** 「用戶待辦」群組的 id，也是展開狀態的鍵。 */
export const USER_TODOS_GROUP_ID = 'userTodos'

/**
 * 待辦行與完成行：行首即 `**用戶待辦**` 或 `**用戶待辦完成**`，其後可帶全形括號的鍵，再接全形冒號與內容。
 * 只比對行首：縮排行、清單項與以反引號引用範本的說明行都不算。
 */
const TODO_LINE = /^\*\*用戶待辦(完成)?\*\*(?:（([^）]*)）)?：(.*)$/

/** 配對用的內部鍵前綴：帶鍵的項以鍵、不帶鍵的項以全文配對，兩者分屬不同命名空間。 */
const KEY_PREFIX = 'key:'
const TEXT_KEY_PREFIX = 'text:'

/** 不帶鍵的待辦行在看板上的來源標示：待辦由主控寫入。 */
const KEYLESS_SOURCE = '主控'

/**
 * 協調票 Solution 段中仍待用戶處理的待辦，依各鍵最後一次寫入待辦行的順序。
 * 鍵為括號內文字；不帶鍵時以冒號後全文為鍵（完成行須逐字相同才配對），兩種鍵各自配對、互不影響。
 * 空括號的行略過；鍵含全形右括號的行不符格式，不列。同一個鍵以最後一行為準：
 * 完成行把該鍵移除，之後再寫待辦行即重新列出。完成行配不到任何待辦時不影響其他項。
 */
export function parseUserTodos(text: string): UserTodo[] {
  const pending = new Map<string, UserTodo>()
  for (const line of unfencedSolutionLines(text)) {
    const match = TODO_LINE.exec(line)
    if (match === null) continue
    const key = match[2] === undefined ? null : match[2].trim()
    const content = (match[3] ?? '').trim()
    // 空括號（`（）`）不是合法的鍵，也不退回全文配對：略過，避免靜默改變配對語意
    if (key === '' || (key === null && content === '')) continue
    // 帶鍵與不帶鍵分開配對：不帶鍵的完成行內容恰等於某個鍵時，不得刪除該帶鍵項，反之亦然
    const matchKey = key === null ? `${TEXT_KEY_PREFIX}${content}` : `${KEY_PREFIX}${key}`
    pending.delete(matchKey)
    if (match[1] === undefined) pending.set(matchKey, { key, item: content })
  }
  return [...pending.values()]
}

/** 完整票號去掉協調票的短票號前綴；不帶此前綴的票號原樣回傳。 */
function shortTicket(id: string, prefix: string): string {
  return prefix !== '' && id.startsWith(prefix) ? id.slice(prefix.length) : id
}

/**
 * 「用戶待辦」群組的各行：U1 在前（`事項｜鍵`，不帶鍵寫「主控」），U2 在後（`事項｜L<n> 短票號（S#）`，沒有票號時只有線號）。
 * U2 中只有 S2（session 停下來等用戶，用戶要到該 session 處理）標為要人處理。
 */
export function userTodoRows(todos: readonly UserTodo[], waiting: readonly WaitingItem[], prefix: string): UserTodoRow[] {
  const u1 = todos.map(todo => ({ text: `${todo.item}｜${todo.key ?? KEYLESS_SOURCE}`, isSessionWaiting: false }))
  const u2 = waiting.map(item => {
    const ticket = item.ticketId === null ? '' : ` ${shortTicket(item.ticketId, prefix)}`
    return { text: `${item.item}｜L${item.lane}${ticket}（${item.source}）`, isSessionWaiting: item.source === 'S2' }
  })
  return [...u1, ...u2]
}
