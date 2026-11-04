// line-board Pane 線群組內的佇列列與佇列細節：佇列列一行列出線上未完成的票，其下的細節按鍵展開後逐張列出佇列票的狀態與 title；
// 兩者共用 queueColorOf 依 statusColor.ts 的五種狀態上色。由 lanesView.tsx 的 renderLaneGroup 呼叫，排在派發列與閘門票之後。
// Elements、ToggleGroup 只以 import type 取自 lanesView.tsx（編譯後移除），兩檔之間沒有執行期的循環匯入。

import type { ElementConstructor, TextProps } from 'claude-code'

import type { DispatchRow, GroupOverrides, LaneGroup, TicketStatus } from '../types'
import type { Elements, ToggleGroup } from './lanesView'
import {
  GROUP_INDENT,
  UNKNOWN_STATUS,
  boardStateColor,
  formatGroupToggle,
  groupBodyKey,
  groupToggleKey,
  isGroupExpanded,
  queueTicketState,
} from './parse'
import type { QueueSegment } from './parse'

/** 線群組的佇列細節 id：`<群組 id>:detail`（如 `lane:7:detail`），也是細節展開狀態的鍵（與群組共用 line-board.expanded）。 */
export function laneDetailId(id: string): string {
  return `${id}:detail`
}

/** 佇列細節按鍵的名稱；按鍵文字為 `▸ 佇列細節`（收合）或 `▾ 佇列細節`（展開）。 */
export const QUEUE_DETAIL_LABEL = '佇列細節'

/** 佇列細節中讀不到 title 的票（票檔讀不到、沒有 title 欄，或 hot reload 前的舊 snapshot）顯示的文字。 */
export const MISSING_TITLE = '（讀不到 title）'

/** 佇列票的顏色：以完整票號與短票號查詢。 */
export type TicketColorOf = (id: string, serial: string) => string | undefined

/**
 * 佇列票的顏色，佇列列與佇列細節共用：依該票所有的派發列階段（不限同一群組，以完整票號比對派發列的 ticketId，
 * 沒有票號的派發不參與）、同群組的閘門票列與主 checkout 的狀態，經 queueTicketState 判定。
 */
export function queueColorOf(group: LaneGroup, tickets: readonly TicketStatus[], allRows: readonly DispatchRow[]): TicketColorOf {
  const statusById = new Map(tickets.map(ticket => [ticket.id, ticket.status]))
  return (id, serial) => {
    const stages = [
      ...allRows.filter(row => row.ticketId === id).map(row => row.stage),
      ...(group.gateTickets.some(gate => gate.serial === serial) ? (['閘門'] as const) : []),
    ]
    return boardStateColor(queueTicketState(statusById.get(id), stages))
  }
}

/**
 * 佇列列：線有未完成的票時一行（completed 的票不列，segments 為 null 時沒有佇列列）；「其他」群組沒有佇列列。
 * 每張票為一段內嵌 Text，依佇列票的狀態上色；分隔符不上色。
 */
export function queueRow(
  Text: ElementConstructor<TextProps>,
  groupId: string,
  segments: readonly QueueSegment[] | null,
  colorOf: TicketColorOf,
) {
  if (segments === null) return []
  const parts = segments.map((segment, index) => {
    if (segment.ticket === null) return segment.text
    return (
      <Text key={`${groupId}:queue:${index}`} color={colorOf(segment.ticket.id, segment.ticket.serial)}>
        {segment.text}
      </Text>
    )
  })
  return [<Text key={`${groupId}:queue`}>排隊：{parts}</Text>]
}

/**
 * 佇列細節：有佇列列時，佇列列之下一個細節按鍵，預設收合，按過後依 line-board.expanded 的手動狀態（鍵為 laneDetailId），
 * 每 30 秒的資料刷新不覆寫。展開時按鍵之下縮排，逐張列出佇列列中的票（同一張票只列一次，completed 不列），
 * 每張一行 `<短票號>｜<status>｜<title>`，依佇列票的狀態上色、以 truncate-end 截斷；title 讀不到時為 MISSING_TITLE。
 */
export function queueDetail(
  { Box, Text, Button }: Elements,
  groupId: string,
  segments: readonly QueueSegment[] | null,
  tickets: readonly TicketStatus[],
  colorOf: TicketColorOf,
  toggle: { overrides: GroupOverrides; onToggle: ToggleGroup },
) {
  if (segments === null) return []
  const id = laneDetailId(groupId)
  const isOpen = isGroupExpanded(id, false, toggle.overrides)
  const button = (
    <Button key={groupToggleKey(id)} plain onPress={() => toggle.onToggle(id, isOpen)}>
      <Text>{formatGroupToggle(QUEUE_DETAIL_LABEL, isOpen)}</Text>
    </Button>
  )
  if (!isOpen) return [button]
  const byId = new Map(tickets.map(ticket => [ticket.id, ticket]))
  const queued = segments.flatMap(segment => (segment.ticket === null ? [] : [segment.ticket]))
  const rows = queued
    .filter((ticket, index) => queued.findIndex(other => other.id === ticket.id) === index)
    .map(({ id: ticketId, serial }) => {
      const ticket = byId.get(ticketId)
      return (
        <Text key={`${id}:${serial}`} wrap="truncate-end" color={colorOf(ticketId, serial)}>
          {`${serial}｜${ticket?.status ?? UNKNOWN_STATUS}｜${ticket?.title ?? MISSING_TITLE}`}
        </Text>
      )
    })
  return [
    button,
    <Box key={groupBodyKey(id)} flexDirection="column" paddingLeft={GROUP_INDENT}>
      {rows}
    </Box>,
  ]
}
