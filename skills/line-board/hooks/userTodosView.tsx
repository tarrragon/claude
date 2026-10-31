// line-board Pane 的「用戶待辦」群組：畫在各線群組之上，集中列出需要用戶操作或回應的事項——
// 協調票的用戶待辦行（U1）在前，各線等用戶（U2，與 line_status 同一份判定）在後；S2 以要人處理色（洋紅粗體）顯示。
// 元素由 register.tsx 以 $.ui.resolve(e) 取得後傳入；解析經 parse.ts 匯出。

import type { GroupOverrides, ReadyBoard } from '../types'
import { renderGroup, sectionFrame } from './lanesView'
import type { Elements, ToggleGroup } from './lanesView'
import { USER_TODOS_GROUP_ID, boardStateColor, lanesWaiting, userTodoRows } from './parse'

/** 「用戶待辦」群組的標題名稱；標題列為 `用戶待辦（N）`。 */
export const USER_TODOS_TITLE = '用戶待辦'

/** 沒有任何一項時的單行文字（不畫群組外框）。 */
export const USER_TODOS_EMPTY = `${USER_TODOS_TITLE}：無`

/** 沒有任何一項、但 session 狀態讀不到（S2 判不出）時的單行文字。 */
export const USER_TODOS_EMPTY_UNSURE = `${USER_TODOS_EMPTY}（session 狀態讀不到，S2 未判）`

/**
 * 有待辦時為可折疊群組（預設展開，使用者按過後依手動狀態），沒有時為一行「用戶待辦：無」。
 * 協調票讀不到時不畫（線群組區的「解析失敗」提示已說明，此時判不出有沒有待辦，寫「無」會誤導）。
 */
export function renderUserTodos(elements: Elements, board: ReadyBoard, overrides: GroupOverrides, onToggle: ToggleGroup) {
  const { Text } = elements
  if (board.lanes.kind !== 'ok') return []
  const waiting = lanesWaiting({
    lanes: board.lanes.lines,
    sessions: board.sessions.kind === 'ok' ? board.sessions.sessions : [],
    tickets: board.tickets,
    prefix: board.ticketPrefix,
  })
  const rows = userTodoRows(board.lanes.todos, waiting, board.ticketPrefix)
  // session 狀態讀不到時 S2 判不出：不寫「無」，註明未判
  if (rows.length === 0) return [<Text dimColor>{board.sessions.kind === 'ok' ? USER_TODOS_EMPTY : USER_TODOS_EMPTY_UNSURE}</Text>]
  const frame = sectionFrame(USER_TODOS_GROUP_ID, `${USER_TODOS_TITLE}（${rows.length}）`, overrides)
  return [
    renderGroup(elements, frame, onToggle, () =>
      rows.map(row =>
        row.isSessionWaiting ? (
          <Text color={boardStateColor('要人處理')} bold>
            {row.text}
          </Text>
        ) : (
          <Text>{row.text}</Text>
        ),
      ),
    ),
  ]
}
