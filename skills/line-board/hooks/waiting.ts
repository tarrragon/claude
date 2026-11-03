// 等用戶偵測：票面標記（S1）、session 等待中（S2）、佇列行註記（S3）與佇列票狀態的組成。
// 看板「用戶待辦」群組（userTodosView.tsx）與 line_status（continuity.ts 的 lineStatusReport）共用同一份判定；
// 訊號定義的權威是 multi-session-orchestration 的 references/line-continuity.md §2〈等用戶〉。
// 不碰 $（無檔案、無行程），讓 *.test.ts 能直接驗證；讀票檔由 readers.ts 負責。

import type { LaneLine, SessionState, TicketStatus, WaitingItem } from '../types'
import { endedForm, parseQueue, unfencedSolutionLines } from './lanes'
import { findSessionByName } from './sessions'
import { COMPLETED_STATUS, UNKNOWN_STATUS, parseFrontmatterStatus, parseFrontmatterTitle } from './shared'

/** S1 等用戶標記行與解除行的開頭（票的 Solution 段，行首；格式權威見 line-continuity.md §2〈等用戶〉）。 */
const WAITING_MARK = '**等用戶**：'
const WAITING_RELEASE = '**等用戶解除**：'

/** S3：現行佇列行的票註記或文字含此字面即判為等用戶。 */
const WAITING_KEYWORD = '等用戶'

/** S2：session 檔的 status 為此值表示停下來等用戶（AskUserQuestion、權限詢問）。 */
const WAITING_STATUS = 'waiting'

/** S2 的 session 檔沒有 waitingFor 時的事項文字。 */
const WAITING_FOR_MISSING = 'session 等待中，未附原因'

/** S1 標記冒號後沒寫事項時的事項文字：照樣列出，只有解除行能清除標記。 */
const WAITING_MARK_EMPTY = '標記未附事項'

/**
 * 票 Solution 段最後一行等用戶標記（S1）的事項：最後一行是解除行、或沒有任何標記行時為 null。
 * 只認嚴格行首（不容前導空白）且不在 fenced code block 內的固定格式，
 * 所以縮排行、格式示例、其他段落的引用與自由文字（「待用戶」）都不算。
 */
export function parseWaitingMark(text: string): string | null {
  let waiting: string | null = null
  for (const line of unfencedSolutionLines(text)) {
    if (line.startsWith(WAITING_MARK)) waiting = line.slice(WAITING_MARK.length).trim() || WAITING_MARK_EMPTY
    else if (line.startsWith(WAITING_RELEASE)) waiting = null
  }
  return waiting
}

/**
 * 票檔原文解析為佇列票的狀態：status（缺欄為 unknown）、title、S1 等用戶標記。readers.ts 讀到票檔後一律經此函式，
 * 所以看板與 line_status 取得的欄位只在這裡組成一次。
 */
export function ticketStatusOf(id: string, text: string): TicketStatus {
  return { id, status: parseFrontmatterStatus(text) ?? UNKNOWN_STATUS, title: parseFrontmatterTitle(text), waiting: parseWaitingMark(text) }
}

/** 佇列票註記去掉外層全形括號（`（等用戶開 --debug）` → `等用戶開 --debug`）；不是整段括號時原樣回傳。 */
function unwrapNote(note: string): string {
  return note.startsWith('（') && note.endsWith('）') ? note.slice(1, -1).trim() : note
}

/**
 * 一條未收線的線的等用戶項，依 S1（票面標記）、S3（佇列行註記）、S2（session 等待中）的順序。
 * S1 與 S3 只看現行佇列行裡未 completed 的票；S3 的純文字片段沒有票號，照列。
 */
function liveLaneWaiting(
  lane: LaneLine,
  sessions: readonly SessionState[],
  tickets: ReadonlyMap<string, TicketStatus>,
  prefix: string,
): WaitingItem[] {
  const base = { lane: lane.lane, session: lane.session }
  const marks: WaitingItem[] = []
  const notes: WaitingItem[] = []
  for (const token of parseQueue(lane.queue, prefix)) {
    if (token.kind === 'text' && token.text.includes(WAITING_KEYWORD)) {
      notes.push({ ...base, ticketId: null, item: token.text, source: 'S3' })
    }
    if (token.kind !== 'ticket') continue
    const ticket = tickets.get(token.id)
    if (ticket?.status === COMPLETED_STATUS) continue
    if (ticket?.waiting != null) marks.push({ ...base, ticketId: token.id, item: ticket.waiting, source: 'S1' })
    if (token.note.includes(WAITING_KEYWORD)) notes.push({ ...base, ticketId: token.id, item: unwrapNote(token.note), source: 'S3' })
  }
  const session = lane.session === null ? undefined : findSessionByName(sessions, lane.session)
  const sessionWaiting =
    session?.status === WAITING_STATUS ? [{ ...base, ticketId: null, item: session.waitingFor ?? WAITING_FOR_MISSING, source: 'S2' as const }] : []
  return [...marks, ...notes, ...sessionWaiting]
}

/**
 * 各條未收線的線的等用戶項（依線號，各線內 S1、S3、S2）：看板「用戶待辦」群組的 U2。
 * 與 lineStatusReport 的等用戶段同一份判定；收線（含附說明的收線寫法）的線不判。
 */
export function lanesWaiting(input: {
  lanes: readonly LaneLine[]
  sessions: readonly SessionState[]
  tickets: readonly TicketStatus[]
  prefix: string
}): WaitingItem[] {
  const tickets = new Map(input.tickets.map(ticket => [ticket.id, ticket]))
  return input.lanes
    .filter(lane => endedForm(lane.queue) === null)
    .flatMap(lane => liveLaneWaiting(lane, input.sessions, tickets, input.prefix))
}
