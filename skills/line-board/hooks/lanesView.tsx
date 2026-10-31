// line-board Pane 的線群組：每條線一個以框線框起的可折疊群組，標題分三行——標題列為 Button（▸／▾、線號、session 與狀態），
// 其下為目標、活動計數——展開後依序列出派發列、閘門票、佇列列與佇列細節（按鍵展開，逐張列出佇列票的狀態與 title）；
// 對不到線的派發歸最後的「其他」群組。標題列為主題鍵 suggestion 色粗體，派發列、閘門票、佇列列中的每張票與佇列細節各行依 statusColor.ts 的五種狀態上色。renderGroup 是各群組共用的
// 可折疊外框，register.tsx 的「各 session」「合併閘門」兩區塊也用它。元素由 register.tsx 以 $.ui.resolve(e) 取得後傳入；分組經 parse.ts 匯出。

import type { BoxProps, ButtonProps, ElementConstructor, RenderChildren, TextProps, ThemeKey } from 'claude-code'

import type {
  BoardSnapshot,
  DispatchRow,
  GroupOverrides,
  LaneGroup,
  LanesResult,
  ReadyBoard,
  SessionsResult,
  TicketStatus,
  UnsetProjectConfig,
} from '../types'
import { dispatchNotice, dispatchRowsOf } from './dispatchView'
import {
  GROUP_INDENT,
  OTHER_LANE_LABEL,
  UNKNOWN_STATUS,
  boardStateColor,
  dispatchStageState,
  formatActivity,
  formatGateTicket,
  formatGroupDispatchRow,
  formatGroupTitle,
  groupBodyKey,
  groupToggleKey,
  isDefaultExpanded,
  isGroupExpanded,
  laneContextLabel,
  laneGroups,
  laneSessionStatus,
  queueRowSegments,
  queueTicketState,
} from './parse'
import type { QueueSegment } from './parse'

/** 群組外框的框線樣式（Ink 的 borderStyle）。 */
export const GROUP_BORDER_STYLE = 'round'
/** 框線在左右兩側共占的欄數：內容可用的寬度為面板寬減去此數。 */
export const GROUP_BORDER_COLUMNS = 2
/**
 * 群組標題列的顏色（粗體）：主題鍵 suggestion，隨 Claude Code 主題變化（深色主題為淺藍、淺色主題為較深的藍）；
 * ANSI 藍在黑底終端機上不明顯。與內容各行的狀態色區分；五種狀態色不用藍（statusColor.ts）。
 */
export const GROUP_TITLE_COLOR: ThemeKey = 'suggestion'

/** 群組外框 Box 的 key。 */
export function groupFrameKey(id: string): string {
  return `frame:${id}`
}

/** 線群組的佇列細節 id：`<群組 id>:detail`（如 `lane:7:detail`），也是細節展開狀態的鍵（與群組共用 line-board.expanded）。 */
export function laneDetailId(id: string): string {
  return `${id}:detail`
}

/** 佇列細節按鍵的名稱；按鍵文字為 `▸ 佇列細節`（收合）或 `▾ 佇列細節`（展開）。 */
export const QUEUE_DETAIL_LABEL = '佇列細節'

/** 佇列細節中讀不到 title 的票（票檔讀不到、沒有 title 欄，或 hot reload 前的舊 snapshot）顯示的文字。 */
export const MISSING_TITLE = '（讀不到 title）'

/** 群組標題 Box 的 key：內含標題列與其下的目標、活動計數各行。 */
export function groupTitleKey(id: string): string {
  return `title:${id}`
}

/** 繪製群組所需的元素：由 register.tsx 以 $.ui.resolve(e) 取得。 */
export type Elements = {
  Box: ElementConstructor<BoxProps>
  Text: ElementConstructor<TextProps>
  Button: ElementConstructor<ButtonProps>
}

/** 按下群組標題列：isOpen 為按下當時的展開狀態。由 register.tsx 寫入 $.state 的手動狀態。 */
export type ToggleGroup = (id: string, isOpen: boolean) => void

/**
 * 一個可折疊群組的外框：群組 id、標題列的文字、標題列下方各行（空字串的行不畫）、是否展開、
 * 是否有活動（無活動時標題列下方各行以淡色顯示，標題列不變）。
 */
export type GroupFrame = { id: string; title: string; details: readonly string[]; isOpen: boolean; isActive: boolean }

/** 底部區塊（各 session、合併閘門）的外框：標題只有名稱一行，預設展開，使用者按過後依手動狀態。 */
export function sectionFrame(id: string, title: string, overrides: GroupOverrides): GroupFrame {
  return { id, title, details: [], isOpen: isGroupExpanded(id, true, overrides), isActive: true }
}

/**
 * 可折疊外框：整個群組畫在一個有框線的 Box 內。框內先是標題——標題列為 Button，按下切換，其下各行為 Text——
 * 展開時標題之後接縮排的內容 Box，收合時框內只有標題。
 */
export function renderGroup({ Box, Text, Button }: Elements, frame: GroupFrame, onToggle: ToggleGroup, body: () => RenderChildren) {
  const titleKey = groupTitleKey(frame.id)
  // 標題下方各行的 key 以序號：行數依資料而定（缺目標或活動計數時省略），同一群組內不重複即可
  const details = frame.details
    .filter(line => line !== '')
    .map((line, index) => (
      <Text key={`${titleKey}:${index}`} dimColor={!frame.isActive}>
        {line}
      </Text>
    ))
  const title = (
    <Box key={titleKey} flexDirection="column">
      {/* 標題列不隨無活動變淡：實機上淡色會把標題色換成灰色，標題列就與其下的淡色各行同色；無活動由其下各行的淡色與 ▸ 表達 */}
      <Button key={groupToggleKey(frame.id)} plain onPress={() => onToggle(frame.id, frame.isOpen)}>
        <Text color={GROUP_TITLE_COLOR} bold>
          {formatGroupTitle([frame.title], frame.isOpen)}
        </Text>
      </Button>
      {details}
    </Box>
  )
  const content = frame.isOpen
    ? [
        <Box key={groupBodyKey(frame.id)} flexDirection="column" paddingLeft={GROUP_INDENT}>
          {body()}
        </Box>,
      ]
    : []
  return (
    <Box key={groupFrameKey(frame.id)} flexDirection="column" borderStyle={GROUP_BORDER_STYLE}>
      {[title, ...content]}
    </Box>
  )
}

/** 線群組區：協調票與派發紀錄的提示行在最上方，其後依線號排列各線群組，「其他」最後。 */
export function renderLaneGroups(elements: Elements, board: ReadyBoard, overrides: GroupOverrides, onToggle: ToggleGroup) {
  const rows = dispatchRowsOf(board)
  const groups = laneGroups(board.lanes.kind === 'ok' ? board.lanes.lanes : [], rows, {
    sessions: board.sessions.kind === 'ok' ? board.sessions.sessions : [],
    tickets: board.tickets,
    holders: board.mergeLog.kind === 'ok' ? board.mergeLog.holders : [],
  })
  return [
    ...lanesNotice(elements.Text, board.lanes),
    ...dispatchNotice(elements, board, rows),
    ...groups.map(group => renderLaneGroup(elements, board, group, rows, overrides, onToggle)),
  ]
}

/** 協調票的兩種提示：讀不到為「解析失敗：協調票讀不到」（附票檔路徑與原因），讀得到但沒有現行佇列行為「協調票尚無現行佇列行」。 */
function lanesNotice(Text: ElementConstructor<TextProps>, lanes: LanesResult) {
  if (lanes.kind === 'error') return [<Text color="red">解析失敗：協調票讀不到（{lanes.message}）</Text>]
  return lanes.lanes.length === 0 ? [<Text color="yellow">協調票尚無現行佇列行</Text>] : []
}

/** 專案設定檔的格式說明，設定不成立時顯示在提示中。 */
export const PROJECT_CONFIG_FORMAT = '{ "coordinationTicket": "<協調票的完整票號>" }'

/** 設定不成立的原因文字，各原因可區分。 */
function unsetReason(config: UnsetProjectConfig): string {
  switch (config.kind) {
    case 'missing':
      return `設定檔讀不到（${config.message}）`
    case 'invalid-json':
      return `設定檔不是有效的 JSON（${config.message}）`
    case 'missing-field':
      return '設定檔缺少 coordinationTicket 欄位'
    case 'invalid-format':
      return `coordinationTicket 不是完整票號（${JSON.stringify(config.value)}）`
  }
}

/** 專案設定不成立時 Pane 的全部內容：原因、設定檔的絕對路徑與格式，不畫任何群組。 */
export function renderConfigNotice({ Box, Text }: Elements, board: Extract<BoardSnapshot, { kind: 'unconfigured' }>) {
  return (
    <Box flexDirection="column">
      <Text color="yellow">尚未設定協調票：{unsetReason(board.config)}</Text>
      <Text>設定檔：{board.configPath}</Text>
      <Text>格式：{PROJECT_CONFIG_FORMAT}</Text>
    </Box>
  )
}

/** allRows 為所有群組的派發列：佇列票的上色依該票所有的派發列，派發列不一定在同一群組（session 與線不一定對應）。 */
function renderLaneGroup(
  elements: Elements,
  board: ReadyBoard,
  group: LaneGroup,
  allRows: readonly DispatchRow[],
  overrides: GroupOverrides,
  onToggle: ToggleGroup,
) {
  const { Text } = elements
  const isDefaultOpen = isDefaultExpanded(group.activity)
  const isOpen = isGroupExpanded(group.id, isDefaultOpen, overrides)
  const frame = { id: group.id, ...groupTitle(board, group), isOpen, isActive: isDefaultOpen }
  const segments = group.lane === null ? null : queueRowSegments(group.lane.tokens, board.tickets)
  const colorOf = queueColorOf(group, board.tickets, allRows)
  // 各行的 key：派發列以序號（同一張票可能有多個代理人），閘門票以票號，佇列列每群組一行
  return renderGroup(elements, frame, onToggle, () => [
    ...group.dispatches.map((row, index) => (
      <Text key={`${group.id}:dispatch:${index}`} wrap="truncate-middle" color={boardStateColor(dispatchStageState(row.stage))}>
        {formatGroupDispatchRow(row, board.readAtMs)}
      </Text>
    )),
    ...group.gateTickets.map(gate => (
      <Text key={`${group.id}:gate:${gate.serial}`} color={boardStateColor('閘門')}>
        {formatGateTicket(gate)}
      </Text>
    )),
    ...queueRow(Text, group.id, segments, colorOf),
    ...queueDetail(elements, group.id, segments, board.tickets, colorOf, { overrides, onToggle }),
  ])
}

/** 佇列票的顏色：以完整票號與短票號查詢。 */
type TicketColorOf = (id: string, serial: string) => string | undefined

/**
 * 佇列票的顏色，佇列列與佇列細節共用：依該票所有的派發列階段（不限同一群組，以短票號比對任務欄）、
 * 同群組的閘門票列與主 checkout 的狀態，經 queueTicketState 判定。
 */
function queueColorOf(group: LaneGroup, tickets: readonly TicketStatus[], allRows: readonly DispatchRow[]): TicketColorOf {
  const statusById = new Map(tickets.map(ticket => [ticket.id, ticket.status]))
  return (id, serial) => {
    const stages = [
      ...allRows.filter(row => row.task === serial).map(row => row.stage),
      ...(group.gateTickets.some(gate => gate.serial === serial) ? (['閘門'] as const) : []),
    ]
    return boardStateColor(queueTicketState(statusById.get(id), stages))
  }
}

/**
 * 線群組的標題三行：標題列為線號、session 名稱與狀態，其後接 context 用量的標記與恢復開工徽章
 * （`L<n> <session>［狀態］［待 compact］［/compact 後已恢復 HH:MM］`，contextJudge.ts laneContextLabel），
 * 其下為目標、活動計數各一行；「其他」群組的標題列只有名稱，其下為活動計數。缺目標或活動計數時該行為空字串，由 renderGroup 略過。
 */
function groupTitle(board: ReadyBoard, group: LaneGroup): Pick<GroupFrame, 'title' | 'details'> {
  const activity = formatActivity(group.activity)
  if (group.lane === null) return { title: OTHER_LANE_LABEL, details: [activity] }
  const { lane, session, goal, tokens } = group.lane
  const { sessions, tickets, usages, readAtMs } = board
  const context = laneContextLabel({
    sessionName: session,
    tokens,
    tickets,
    sessions: sessions.kind === 'ok' ? sessions.sessions : [],
    usages,
    nowMs: readAtMs,
  })
  const title = `L${lane} ${session ?? '（未標 session）'}${laneStatusLabel(sessions, session)}${context}`
  return { title, details: [laneGoalLabel(goal), activity] }
}

/**
 * 佇列列：線有未完成的票時一行（completed 的票不列，segments 為 null 時沒有佇列列）；「其他」群組沒有佇列列。
 * 每張票為一段內嵌 Text，依佇列票的狀態上色；分隔符不上色。
 */
function queueRow(Text: ElementConstructor<TextProps>, groupId: string, segments: readonly QueueSegment[] | null, colorOf: TicketColorOf) {
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
function queueDetail(
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
      <Text>{formatGroupTitle([QUEUE_DETAIL_LABEL], isOpen)}</Text>
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

/** 標題的目標行 `目標：<文字>`；沒有目標時為空字串（不畫該行）。hot reload 後舊 snapshot 的線沒有 goal 欄（undefined），同樣為空字串。 */
function laneGoalLabel(goal: string | null | undefined): string {
  return goal === null || goal === undefined ? '' : `目標：${goal}`
}

/** 標題列 session 名稱旁的 `［狀態］`；沒標 session 時不顯示，session 狀態讀取失敗時標「狀態不明」。 */
function laneStatusLabel(sessions: SessionsResult, name: string | null): string {
  if (name === null) return ''
  if (sessions.kind === 'error') return '［狀態不明］'
  return `［${laneSessionStatus(sessions.sessions, name)}］`
}
