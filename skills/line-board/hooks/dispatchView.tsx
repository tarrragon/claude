// line-board Pane 的派發中代理人：由 snapshot 推出派發列，以及讀取失敗、無法判定、沒有派發三種提示行。
// 派發列本身畫在 lanesView.tsx 的線群組內；元素由 register.tsx 的 ui.render 以 $.ui.resolve(e) 取得後傳入。

import type { DispatchRow, ReadyBoard } from '../types'
import type { Elements } from './lanesView'
import { DISPATCH_ACTIVE_PATH, dispatchRows } from './parse'

/**
 * 應列出的派發列，依線號排序、其他最後。派發紀錄讀取失敗時沒有派發列；sessions 讀不到時無從判定存活，同樣沒有。
 * 協調票或閘門紀錄讀不到時照樣列出：線一律歸其他、不判定閘門。
 */
export function dispatchRowsOf(board: ReadyBoard): DispatchRow[] {
  if (board.dispatches.kind === 'error' || board.sessions.kind === 'error') return []
  return dispatchRows(
    board.dispatches.records,
    {
      sessions: board.sessions.sessions,
      lanes: board.lanes.kind === 'ok' ? board.lanes.lanes : [],
      tickets: board.tickets,
      holders: board.mergeLog.kind === 'ok' ? board.mergeLog.holders : [],
    },
    board.ticketPrefix,
  )
}

/** 線群組上方的派發提示行：派發紀錄讀取失敗、session 狀態讀取失敗、沒有任何派發列；派發列照常時沒有提示。 */
export function dispatchNotice({ Text }: Elements, board: ReadyBoard, rows: readonly DispatchRow[]) {
  const { dispatches } = board
  if (dispatches.kind === 'error') return [<Text color="red">讀取 {DISPATCH_ACTIVE_PATH} 失敗（{dispatches.message}）</Text>]
  if (board.sessions.kind === 'error') return [<Text dimColor>（session 狀態讀取失敗，無法判定派發中的代理人）</Text>]
  if (rows.length === 0) return [<Text dimColor>（目前沒有派發中的代理人）</Text>]
  return []
}
