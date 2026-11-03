// 各線接續狀態（line_status 工具）：diagnostic.log 解析、每條線的接續狀態判定、過期偵測與工具輸出文字。
// 判讀規則的權威是 multi-session-orchestration 的 references/line-continuity.md §2；判讀只在本檔實作一份（等用戶偵測在 waiting.ts，看板與本檔共用）。
// 不碰 $（無檔案、無行程），讓 *.test.ts 能直接驗證；讀檔由 readers.ts 負責、組裝由 lineStatus.ts 負責。

import type {
  ContextUsageRecord,
  ContinuityState,
  LaneContinuity,
  LaneLine,
  LineStatusReport,
  SessionState,
  SourceLogEntry,
  StaleItem,
  TicketStatus,
  UserTodo,
  WaitingItem,
} from '../types'
import { type ContextUsageFailures, laneContextStatus } from './contextJudge'
import { LANE_ENDED, endedForm, parseQueue } from './lanes'
import { findSessionByName } from './sessions'
import { COMPLETED_STATUS } from './shared'
import { userTodoRows } from './userTodos'
import { lanesWaiting } from './waiting'

/** SessionStart 來源紀錄檔，相對各 checkout（worktree 內啟動的 session 寫入該 worktree 自己的檔）。 */
export const SOURCE_LOG_PATH = '.claude/hook-logs/session-source-diagnostic/diagnostic.log'

/** 來源紀錄的一行：`[<時間>] source=<值> session_id=<前 8 碼>`。 */
const SOURCE_LOG_LINE = /^\[([^\]]+)\] source=(\S+) session_id=([0-9a-f]+)/

/** sessionId 與紀錄比對用的前綴長度（紀錄只寫前 8 碼）。 */
const SESSION_PREFIX_LENGTH = 8

/** 來源紀錄的 source 對應的接續狀態；不在表中（如 resume）判為來源不明。 */
const SOURCE_STATES: Readonly<Record<string, ContinuityState>> = { clear: 'clear', compact: 'compact', startup: 'startup' }

/** 各接續狀態的顯示文字。 */
const STATE_LABELS: Readonly<Record<ContinuityState, string>> = {
  ended: '已收線',
  clear: '/clear 後繼續',
  compact: '/compact 後繼續',
  startup: '新 session 接手',
  orphan: '無人持有',
  unknown: '來源不明',
}

/** 各過期項的顯示文字。 */
const STALE_LABELS: Readonly<Record<StaleItem['kind'], string>> = {
  'ended-with-note': '收線寫法',
  orphan: '無人持有',
  'all-done': '佇列已完成未收線',
}

/** 解析來源紀錄：不符格式的行略過（例如手動註記）；保留原順序。 */
export function parseSourceLog(text: string): SourceLogEntry[] {
  const entries: SourceLogEntry[] = []
  for (const line of text.split('\n')) {
    const match = SOURCE_LOG_LINE.exec(line.trim())
    if (match !== null) entries.push({ time: match[1] ?? '', source: match[2] ?? '', sessionPrefix: match[3] ?? '' })
  }
  return entries
}

/** 未收線的線的佇列完整票號（去重、保留首次出現順序）：line_status 要讀這些票的 status 判斷「佇列已完成未收線」。 */
export function continuityTicketIds(lanes: readonly LaneLine[], prefix: string): string[] {
  const ids: string[] = []
  for (const lane of lanes) {
    if (endedForm(lane.queue) !== null) continue
    for (const token of parseQueue(lane.queue, prefix)) {
      if (token.kind === 'ticket' && !ids.includes(token.id)) ids.push(token.id)
    }
  }
  return ids
}

/**
 * 某個 sessionId 在來源紀錄中的最後一筆：多個 checkout 的紀錄合併後依時間取最晚的一筆（時間為 ISO 形式，字串序即時間序）；
 * 查無時為 undefined。
 */
export function lastSourceOf(log: readonly SourceLogEntry[], sessionId: string): SourceLogEntry | undefined {
  const prefix = sessionId.slice(0, SESSION_PREFIX_LENGTH)
  return log
    .filter(entry => entry.sessionPrefix === prefix)
    .reduce<SourceLogEntry | undefined>((latest, entry) => (latest === undefined || entry.time >= latest.time ? entry : latest), undefined)
}

/** 未收線的線的接續狀態：依佇列行的名稱找存活的 session，再以其 sessionId 查來源紀錄的最後一筆。 */
function liveLaneState(lane: LaneLine, sessions: readonly SessionState[], log: readonly SourceLogEntry[]): LaneContinuity {
  const base = { lane: lane.lane, session: lane.session }
  if (lane.session === null) return { ...base, state: 'unknown', evidence: '現行佇列行未寫 session 名稱' }
  const session = findSessionByName(sessions, lane.session)
  if (session === undefined) return { ...base, state: 'orphan', evidence: `名稱「${lane.session}」不在本 repo 存活的 session 中` }
  if (session.sessionId === null) return { ...base, state: 'unknown', evidence: `pid ${session.pid} 的 session 檔沒有 sessionId` }
  const prefix = session.sessionId.slice(0, SESSION_PREFIX_LENGTH)
  const entry = lastSourceOf(log, session.sessionId)
  if (entry === undefined) return { ...base, state: 'unknown', evidence: `sessionId ${prefix}，來源紀錄查無此 id` }
  const state = SOURCE_STATES[entry.source] ?? 'unknown'
  return { ...base, state, evidence: `sessionId ${prefix}，log ${entry.time} source=${entry.source}` }
}

/** 一條線的過期項（收線寫法另判，不在此）：無人持有、佇列的票全部 completed。 */
function liveLaneStale(lane: LaneLine, state: LaneContinuity, tickets: ReadonlyMap<string, TicketStatus>, prefix: string): StaleItem[] {
  const stale: StaleItem[] = []
  // 佇列行沒寫名稱的線同樣沒有可定址的持有者，一併列為無人持有（狀態仍為來源不明，因為持有者無從查起）
  if (state.state === 'orphan' || lane.session === null) {
    stale.push({ lane: lane.lane, kind: 'orphan', detail: `${state.evidence}，佇列仍有內容` })
  }
  const ids = parseQueue(lane.queue, prefix).flatMap(token => (token.kind === 'ticket' ? [token.id] : []))
  if (ids.length > 0 && ids.every(id => tickets.get(id)?.status === COMPLETED_STATUS)) {
    stale.push({ lane: lane.lane, kind: 'all-done', detail: `佇列的 ${ids.length} 張票都已 completed，現行佇列行尚未寫（無）` })
  }
  return stale
}

/** line_status 用量段的輸入：存活 session 的用量檔、解析失敗的原因與判定時間（毫秒）。 */
export type LineStatusContextInput = {
  usages: Readonly<Record<string, ContextUsageRecord>>
  failures: ContextUsageFailures
  nowMs: number
}

/**
 * 判讀每條線的接續狀態與過期項。收線（含附說明的收線寫法）判為已收線，不再判持有者；
 * 附說明的收線寫法另列過期項，因為看板只認整段為收線記號的寫法，否則仍把該線顯示為離線。
 * 提供 context 時，未收線的線另帶用量段，判定取看板線標題同一個函式（laneContextLabel，經 laneContextStatus）。
 */
export function lineStatusReport(input: {
  lanes: readonly LaneLine[]
  /** 協調票仍待用戶處理的待辦（U1，parseUserTodos）；省略視為無。 */
  todos?: readonly UserTodo[]
  sessions: readonly SessionState[]
  log: readonly SourceLogEntry[]
  tickets: readonly TicketStatus[]
  prefix: string
  context?: LineStatusContextInput
}): LineStatusReport {
  const tickets = new Map(input.tickets.map(ticket => [ticket.id, ticket]))
  const lanes: LaneContinuity[] = []
  const stale: StaleItem[] = []
  for (const lane of input.lanes) {
    const form = endedForm(lane.queue)
    if (form !== null) {
      lanes.push({ lane: lane.lane, session: lane.session, state: 'ended', evidence: `票序「${lane.queue}」` })
      if (form === 'with-note') {
        stale.push({
          lane: lane.lane,
          kind: 'ended-with-note',
          detail: `票序「${lane.queue}」以收線記號開頭但後面還有文字，看板不視為收線；已收線請只寫${LANE_ENDED}，說明移到其他段落`,
        })
      }
      continue
    }
    const state = liveLaneState(lane, input.sessions, input.log)
    const context = input.context === undefined ? null : liveLaneContext(lane, input, input.context)
    lanes.push(context === null ? state : { ...state, context })
    stale.push(...liveLaneStale(lane, state, tickets, input.prefix))
  }
  // 等用戶直接取看板用的同一個函式，「line_status 與看板同一份判定」由呼叫結構保證
  return { lanes, stale, todos: [...(input.todos ?? [])], waiting: lanesWaiting(input) }
}

/** 一條未收線的線的用量段：佇列 token 與票狀態交給 laneContextStatus 判定是否持有 in_progress 票。 */
function liveLaneContext(
  lane: LaneLine,
  input: { sessions: readonly SessionState[]; tickets: readonly TicketStatus[]; prefix: string },
  context: LineStatusContextInput,
): string | null {
  return laneContextStatus({
    sessionName: lane.session,
    tokens: parseQueue(lane.queue, input.prefix),
    tickets: input.tickets,
    sessions: input.sessions,
    usages: context.usages,
    failures: context.failures,
    nowMs: context.nowMs,
  })
}

/** 線的標示：`L<n>（名稱）`，佇列行未寫名稱時只有線號。 */
function laneLabel(lane: { lane: number; session: string | null }): string {
  return lane.session === null ? `L${lane.lane}` : `L${lane.lane}（${lane.session}）`
}

/** 等用戶項的標示：線的標示後直接接票號；佇列行未寫名稱時以空白分隔，沒有票號時只有線的標示。 */
function waitingLabel(item: WaitingItem): string {
  if (item.ticketId === null) return laneLabel(item)
  return item.session === null ? `${laneLabel(item)} ${item.ticketId}` : `${laneLabel(item)}${item.ticketId}`
}

/**
 * line_status 的輸出文字：標題、未收線各線一行（狀態｜依據）、已收線合併為一行、過期項逐條、等用戶逐條（與過期項分列）。
 * 讀者是主控的模型，判讀規則路由放在最後一行，讓它知道各狀態該怎麼接續。
 */
export function formatLineStatus(report: LineStatusReport, header: { coordinationTicket: string; readAt: string }): string {
  const live = report.lanes.filter(lane => lane.state !== 'ended')
  const ended = report.lanes.filter(lane => lane.state === 'ended')
  const lines = [`各線接續狀態（協調票 ${header.coordinationTicket}，讀取 ${header.readAt}）`]
  if (live.length === 0) lines.push('未收線的線：無')
  for (const lane of live) {
    const context = lane.context === undefined ? '' : `｜${lane.context}`
    lines.push(`${laneLabel(lane)}：${STATE_LABELS[lane.state]}｜${lane.evidence}${context}`)
  }
  if (ended.length > 0) lines.push(`已收線：${ended.map(lane => `L${lane.lane}`).join('、')}`)
  if (report.stale.length === 0) {
    lines.push('過期項：無')
  } else {
    lines.push(`過期項（${report.stale.length}）：`)
    for (const item of report.stale) lines.push(`- L${item.lane} ${STALE_LABELS[item.kind]}：${item.detail}`)
  }
  // U1 與 U2 分段：行格式取看板同一個函式（userTodoRows），這裡只傳 U1
  const todoRows = userTodoRows(report.todos, [], '')
  if (todoRows.length === 0) {
    lines.push('用戶待辦：無')
  } else {
    lines.push(`用戶待辦（${todoRows.length}）：`)
    for (const row of todoRows) lines.push(`- ${row.text}`)
  }
  if (report.waiting.length === 0) {
    lines.push('等用戶：無')
  } else {
    lines.push(`等用戶（${report.waiting.length}）：`)
    for (const item of report.waiting) lines.push(`- ${waitingLabel(item)}：${item.item}（${item.source}）`)
  }
  lines.push('判讀規則與各狀態的接續動作：.claude/skills/multi-session-orchestration/references/line-continuity.md §2')
  return lines.join('\n')
}
