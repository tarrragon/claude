// line-board：Pane 的組裝與群組的手動展開狀態（$.state 的 expanded，按下標題列寫入）。
// snapshot 的 atom 留在 register.tsx（刷新寫入；平台的靜態掃描要求 atom 定義在使用它的檔案內），
// 由 register.tsx 讀出後連同元素（$.ui.resolve(e)）傳入；各區塊的繪製在 *View.tsx。

import { atom, read, update } from 'claude-code'
import type { EngineInterface } from 'claude-code'

import type { BoardSnapshot } from '../types'
import { renderConfigNotice, renderGroup, renderLaneGroups, sectionFrame } from './lanesView'
import type { Elements, ToggleGroup } from './lanesView'
import { renderMergeLog } from './mergeGateView'
import { MERGE_GATE_GROUP_ID, SESSIONS_GROUP_ID, messageOf, toggledOverrides } from './parse'
import { renderSessions } from './sessionsView'
import { renderUserTodos } from './userTodosView'

/** 使用者按過的群組的展開狀態（群組 id → 是否展開）；與 snapshot 分開，資料刷新不覆寫。 */
const expanded = atom({ plugin: 'line-board', key: 'expanded' } as const, {})

/** 依 snapshot 與展開狀態組出 Pane 內容。 */
export async function renderBoardPane($: EngineInterface, elements: Elements, board: BoardSnapshot) {
  const { Box, Text } = elements
  const overrides = await read($, expanded)

  if (board.kind === 'unconfigured') return renderConfigNotice(elements, board)
  // hot reload 後 $.state 可能仍是舊版 snapshot（沒有 lanes、sessions、dispatches 欄，協調票結果沒有原文行與待辦，
  // 或閘門紀錄仍是整行原文），等下一輪讀取覆寫前先顯示讀取中。
  if (
    board.kind === 'loading' ||
    board.lanes === undefined ||
    (board.lanes.kind === 'ok' && (board.lanes.lines === undefined || board.lanes.todos === undefined)) ||
    board.sessions === undefined ||
    board.usages === undefined ||
    board.dispatches === undefined ||
    (board.mergeLog.kind === 'ok' && (board.mergeLog.entries === undefined || board.mergeLog.holders === undefined))
  ) {
    return <Text dimColor>讀取中…</Text>
  }

  // 按下標題列：onPress 寫入手動狀態後 Pane 重畫；失敗為 warning 級（$.ui.log 無級別，送 transcript 使畫面可見）
  const toggle: ToggleGroup = (id, isOpen) => {
    const onError = (error: unknown) => $.ui.log(`line-board 警告：切換群組 ${id} 失敗：${messageOf(error)}`, { to: 'transcript' })
    update($, expanded, map => toggledOverrides(map, id, isOpen)).catch(onError)
  }
  const bottom = (id: string, title: string) => sectionFrame(id, title, overrides)
  return (
    <Box flexDirection="column">
      <Text dimColor>
        更新 {board.updatedAt}
        {board.checkoutNote === null ? '' : `｜${board.checkoutNote}`}
      </Text>
      {renderUserTodos(elements, board, overrides, toggle)}
      {renderLaneGroups(elements, board, overrides, toggle)}
      {renderGroup(elements, bottom(SESSIONS_GROUP_ID, '各 session'), toggle, () => renderSessions(elements, board))}
      {renderGroup(elements, bottom(MERGE_GATE_GROUP_ID, '合併閘門最近紀錄'), toggle, () => renderMergeLog(elements, board))}
    </Box>
  )
}
