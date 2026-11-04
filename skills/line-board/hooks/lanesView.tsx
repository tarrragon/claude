// line-board Pane 的線群組：每條線一個以框線框起的可折疊群組，標題分三行——標題列為 Button（▸／▾、線號、session 與狀態），
// 其下為目標、活動計數——展開後依序列出派發列、閘門票、佇列列與佇列細節（按鍵展開，逐張列出佇列票的狀態與 title；兩者的繪製在 queueView.tsx）；
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
  UnsetProjectConfig,
} from '../types'
import { dispatchNotice, dispatchRowsOf } from './dispatchView'
import {
  COORDINATION_HOWTO,
  COORDINATION_NONE,
  GROUP_INDENT,
  OTHER_LANE_LABEL,
  boardStateColor,
  dispatchStageState,
  formatActivity,
  formatGateTicket,
  formatGroupDispatchRow,
  formatGroupToggle,
  groupBodyKey,
  groupToggleKey,
  isDefaultExpanded,
  isGroupExpanded,
  isQueueWithoutTicket,
  laneContextLabel,
  laneGroups,
  laneSessionStatus,
  queueRowSegments,
} from './parse'
import { queueColorOf, queueDetail, queueRow } from './queueView'

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

/**
 * 佇列行只含非票號文字（lanes.ts isQueueWithoutTicket，與 line_status 的 no-ticket 過期項同一判定）時，標題列在 `［狀態］` 之後的標示。
 * 這類線沒有佇列列（layout.ts queueRowSegments 回傳 null），沒有此標示時看板上只剩標題列、看不出佇列寫錯。
 */
export const QUEUE_NO_TICKET_LABEL = '［佇列無票號］'

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
          {formatGroupToggle(frame.title, frame.isOpen)}
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

/** 協調票不成立的原因文字，0 張、多張、解析失敗可區分。 */
function unsetReason(config: UnsetProjectConfig): string {
  switch (config.kind) {
    case 'none':
      return COORDINATION_NONE
    case 'multiple':
      return '有多張標記 coordination: true 的進行中票，不自行擇一，請用戶裁定'
    case 'error':
      return `協調票解析失敗（${config.message}）`
  }
}

/** 協調票不成立時 Pane 的全部內容：原因，加上 0 張的補法或多張的候選清單，不畫任何群組。 */
export function renderConfigNotice({ Box, Text }: Elements, board: Extract<BoardSnapshot, { kind: 'unconfigured' }>) {
  const { config } = board
  return (
    <Box flexDirection="column">
      <Text color="yellow">尚未設定協調票：{unsetReason(config)}</Text>
      {config.kind === 'none' && <Text>{COORDINATION_HOWTO}</Text>}
      {config.kind === 'multiple' && config.candidates.map(ticket => <Text key={ticket}>候選：{ticket}</Text>)}
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

/**
 * 線群組的標題三行：標題列為線號、session 名稱與狀態，佇列無票號時接 QUEUE_NO_TICKET_LABEL，其後接 context 用量的標記與恢復開工徽章
 * （`L<n> <session>［狀態］［佇列無票號］［待 compact］［/compact 後已恢復 HH:MM］`，contextJudge.ts laneContextLabel），
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
  const noTicket = isQueueWithoutTicket(tokens) ? QUEUE_NO_TICKET_LABEL : ''
  const title = `L${lane} ${session ?? '（未標 session）'}${laneStatusLabel(sessions, session)}${noTicket}${context}`
  return { title, details: [laneGoalLabel(goal), activity] }
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
