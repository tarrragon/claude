// 派發中代理人：`.claude/dispatch-active.json` 解析、流程階段推導、依線分組的派發列。
// 派發列的顯示文字由 layout.ts 的 formatGroupDispatchRow 組出（所屬線由群組標題表達）。
// 不碰 $（無檔案、無行程），讓 *.test.ts 能直接驗證；讀檔與執行命令由 readers.ts 負責。

import type { DispatchContext, DispatchRecord, DispatchRow, DispatchStage } from '../types'
import { COMPLETED_STATUS } from './shared'

/** 派發紀錄檔，相對 repo root；只讀主 checkout 的這一份。 */
export const DISPATCH_ACTIVE_PATH = '.claude/dispatch-active.json'

/** 審查類代理人（dispatches 的 name）：未結束時流程階段為「審查」。新增審查類代理人時加在此處。 */
export const REVIEW_AGENTS: readonly string[] = [
  'linux',
  'basil-writing-critic',
  'acceptance-auditor',
  'bay-quality-auditor',
  'clove-security-reviewer',
]

/** 事故分析代理人：未結束時流程階段為「事故分析」。 */
const INCIDENT_AGENT = 'incident-responder'

/** worktree 代理人的分支為 `worktree-agent-<agent_id>`；dispatches 的 branch_name 只記 `worktree`，分支名須由 agent_id 組出。 */
const AGENT_BRANCH_PREFIX = 'worktree-agent-'

/** 沒有票號也沒有派發描述的條目，任務欄顯示的文字。 */
const NO_DESCRIPTION = '（無描述）'

/** 派發列對不到任何線時的分組名稱。 */
export const OTHER_LANE_LABEL = '其他'

/** 字串且非空時回傳該值，其餘（空字串、null、非字串）為 null。 */
function nonEmptyString(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null
}

/** dispatches 的一筆；不是物件，或 agent_id、session_id、name 任一缺少或為空時回傳 null。 */
function parseDispatchEntry(entry: unknown): DispatchRecord | null {
  if (typeof entry !== 'object' || entry === null) return null
  const record = entry as Record<string, unknown>
  const agentId = nonEmptyString(record.agent_id)
  const sessionId = nonEmptyString(record.session_id)
  const name = nonEmptyString(record.name)
  if (agentId === null || sessionId === null || name === null) return null
  return {
    agentId,
    name,
    sessionId,
    ticketId: nonEmptyString(record.ticket_id),
    description: typeof record.agent_description === 'string' ? record.agent_description : '',
    dispatchedAt: nonEmptyString(record.dispatched_at),
    turnEndedAt: nonEmptyString(record.turn_ended_at),
  }
}

/**
 * 解析 `.claude/dispatch-active.json`：取 dispatches 陣列中可辨識的條目（tombstones 不讀）。
 * JSON 無效、頂層不是物件或 dispatches 不是陣列時回傳 null（格式錯誤）；個別條目缺欄位時略過該筆。
 */
export function parseDispatchFile(text: string): DispatchRecord[] | null {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    // 格式無效（例如寫到一半）回傳 null，由呼叫端顯示讀取失敗並記 debug 日誌；下一輪重讀。
    return null
  }
  if (typeof value !== 'object' || value === null) return null
  const dispatches = (value as Record<string, unknown>).dispatches
  if (!Array.isArray(dispatches)) return null
  return dispatches.map(entry => parseDispatchEntry(entry)).filter((record): record is DispatchRecord => record !== null)
}

/** 派發紀錄的時間格式：`YYYY-MM-DDTHH:MM:SS`，可帶任意位數小數秒，結尾為 `Z` 或 `±HH:MM`。 */
const ISO_TIME = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$/

/** ISO 時間字串轉 epoch 毫秒：小數秒截到毫秒（紀錄寫的是微秒）；null 或格式不符時回傳 null。 */
export function parseIsoMs(text: string | null): number | null {
  if (text === null) return null
  const match = ISO_TIME.exec(text.trim())
  if (match === null) return null
  const millis = (match[2] ?? '').padEnd(3, '0').slice(0, 3)
  const ms = Date.parse(`${match[1]}.${millis}${match[3]}`)
  return Number.isNaN(ms) ? null : ms
}

/**
 * 一筆派發的流程階段；回傳 null 表示不列出。依序判定：
 * 1. 有票號且票已 completed：不列
 * 2. 分支 `worktree-agent-<agent_id>` 在閘門持有者中：閘門（代理人是否已結束皆同）
 * 3. 未結束（turnEndedAt 為 null）：審查類代理人為審查、incident-responder 為事故分析，其餘為實作
 * 4. 已結束且有票號（票未 completed，含狀態讀不到）：收尾；已結束且沒有票號：不列（沒有票可收尾）
 * ticketStatus 為該票在主 checkout 的 status，沒有票號或未讀到時傳 undefined。
 */
export function dispatchStage(
  record: DispatchRecord,
  ticketStatus: string | undefined,
  holderBranches: readonly string[],
): DispatchStage | null {
  if (record.ticketId !== null && ticketStatus === COMPLETED_STATUS) return null
  if (holderBranches.includes(`${AGENT_BRANCH_PREFIX}${record.agentId}`)) return '閘門'
  if (record.turnEndedAt === null) {
    if (REVIEW_AGENTS.includes(record.name)) return '審查'
    return record.name === INCIDENT_AGENT ? '事故分析' : '實作'
  }
  return record.ticketId === null ? null : '收尾'
}

/** 完整票號去掉短票號前綴（如 `1.2.0-W3-`），與票序的短票號一致；不帶該前綴的票號原樣。 */
function shortTicketId(id: string, prefix: string): string {
  return id.startsWith(prefix) ? id.slice(prefix.length) : id
}

/** 派發紀錄中有票號的條目的完整票號，保留首次出現順序並去重。 */
export function dispatchTicketIds(records: readonly DispatchRecord[]): string[] {
  const ids: string[] = []
  for (const record of records) {
    if (record.ticketId !== null && !ids.includes(record.ticketId)) ids.push(record.ticketId)
  }
  return ids
}

/**
 * 派發區塊的列：session_id 對不到存活 session（sessionId）的條目不列；dispatchStage 為 null 的不列。
 * 以 session 的名稱對到協調票現行佇列行括號內的 session 名稱取線號，對不到為 null（其他）。
 * 依線號排序、其他最後，同線保留紀錄中的順序。任務欄為短票號（完整票號去掉 ticketPrefix），沒有票號時為派發描述。
 * ticketPrefix 為協調票推導的短票號前綴（shared.ts ticketPrefixOf），由 snapshot 的 ticketPrefix 傳入。
 */
export function dispatchRows(
  records: readonly DispatchRecord[],
  context: DispatchContext,
  ticketPrefix: string,
): DispatchRow[] {
  const statusById = new Map(context.tickets.map(ticket => [ticket.id, ticket.status]))
  const holderBranches = context.holders.map(holder => holder.branch)
  const rows: DispatchRow[] = []
  for (const record of records) {
    const session = context.sessions.find(item => item.sessionId === record.sessionId)
    if (session === undefined) continue
    const status = record.ticketId === null ? undefined : statusById.get(record.ticketId)
    const stage = dispatchStage(record, status, holderBranches)
    if (stage === null) continue
    const task = record.ticketId === null ? record.description || NO_DESCRIPTION : shortTicketId(record.ticketId, ticketPrefix)
    const lane = context.lanes.find(item => item.session === session.name)?.lane ?? null
    rows.push({ lane, name: record.name, task, stage, dispatchedAt: record.dispatchedAt })
  }
  const rank = (row: DispatchRow) => row.lane ?? Number.MAX_SAFE_INTEGER
  return rows.sort((a, b) => rank(a) - rank(b))
}
