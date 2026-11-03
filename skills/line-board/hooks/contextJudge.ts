// context 用量的讀取端：解析各 session 的用量檔（contextUsage.ts 寫出）、判定待 compact／待 clear、
// 「各 session」列的用量字尾，以及用量檔清理的路徑檢查與孤兒檔挑選。看板（583.2、583.4）與 line_status（583.3）共用本檔的判定。
// 不碰 $；讀檔、刪檔由 usageReaders.ts、usageWriter.ts 與 register.tsx 負責。
//
// 判定（主控裁定，2026-10-31）：
// - 百分比依 auto-compact 狀態選分母：autoCompactThreshold 有值用 compactPercent，為 null 用 percent；選中值為 null 不判定
// - 一般線：持有 in_progress 票且達 LANE_T_COMPACT → 待 compact；未持有且達 LANE_T_CLEAR → 待 clear
// - 主控：達 COORDINATOR_T_COMPACT → 待 compact；不判待 clear（主控長駐，compact 是例外處理）
// - 存活的 session 一律判定，不因量測時間舊而停判：用量檔只在用量變動時寫入，閒置 session 最後一次的值仍準確

import type { ContextUsageRecord, QueueToken, ResumePhase, SessionState, TicketStatus } from '../types'
import { CONTEXT_USAGE_DIR } from './contextUsage'
import { COORDINATOR_SESSION_NAME } from './resumeNotice'
import { findSessionByName } from './sessions'
import { formatAge } from './shared'

/** 一般線的待 compact 門檻：583 盤點的兩次實際 compact 在 45% 與 33%，45 在最晚一次之前提醒。 */
export const LANE_T_COMPACT = 45
/** 一般線的待 clear 門檻：沒有進行中的票時，用量到 30% 就提醒 /clear。 */
export const LANE_T_CLEAR = 30
/** 主控的待 compact 門檻：主控長駐，套 45 會在正常運作時一直被標記。 */
export const COORDINATOR_T_COMPACT = 60
/** 孤兒用量檔的年齡下限：mtime 超過 24 小時且不屬於存活 session 才刪。 */
export const ORPHAN_AGE_MS = 24 * 60 * 60 * 1000
/** 恢復開工徽章的顯示時間：恢復開工後 10 分鐘內（含 10 分鐘）顯示，讓主控回頭看板時仍看得到。 */
export const RESUME_BADGE_MS = 10 * 60 * 1000
/** 佇列票持有中的狀態：線的佇列有這個狀態的票，即為持有 in_progress 票。 */
const IN_PROGRESS_STATUS = 'in_progress'

/** 用量檔檔名：sessionId（英數、連字號、底線）加 .json；與 contextUsagePath 的 sessionId 檢查一致。 */
const USAGE_FILE_NAME = /^[A-Za-z0-9_-]+\.json$/

/** 判定結果：compact 待 compact、clear 待 clear、null 不標。 */
export type ContextMark = 'compact' | 'clear' | null

/** session 在協調中的角色：coordinator 主控、lane 未收線的線、none 收線或不屬於任何線（不判定）。 */
export type ContextRole = 'coordinator' | 'lane' | 'none'

/** 解析用量檔；JSON 無效或缺 sessionId、window、measuredAt 時回傳 null。0.6.0 寫出的檔沒有 phase，以 null 讀入。 */
export function parseContextUsageFile(text: string): ContextUsageRecord | null {
  const parsed = parseContextUsageDetailed(text)
  return parsed.kind === 'ok' ? parsed.record : null
}

/** 用量檔解析結果：ok 為記錄；invalid 附原因（line_status 要寫出原因，不與「無用量檔」同形）。 */
export type ContextUsageParse = { kind: 'ok'; record: ContextUsageRecord } | { kind: 'invalid'; reason: string }

/** 解析用量檔並在失敗時回傳原因：JSON 無效（附解析器訊息）、不是物件、缺必要欄位。 */
export function parseContextUsageDetailed(text: string): ContextUsageParse {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch (error) {
    // session 寫到一半時讀到的半份檔也走這裡：看板視為不存在、下一輪重讀；line_status 照實寫出原因
    return { kind: 'invalid', reason: `JSON 無效（${error instanceof Error ? error.message : String(error)}）` }
  }
  if (typeof value !== 'object' || value === null) return { kind: 'invalid', reason: '內容不是 JSON 物件' }
  const raw = value as Record<string, unknown>
  if (typeof raw.sessionId !== 'string' || typeof raw.window !== 'number' || typeof raw.measuredAt !== 'number') {
    return { kind: 'invalid', reason: '缺 sessionId、window 或 measuredAt' }
  }
  return { kind: 'ok', record: usageRecordOf(raw, { sessionId: raw.sessionId, window: raw.window, measuredAt: raw.measuredAt }) }
}

/** 已確認型別的必要欄位加上原物件的選填欄位，組成用量記錄；選填欄位缺席或型別不符時為 null。 */
function usageRecordOf(
  raw: Record<string, unknown>,
  required: { sessionId: string; window: number; measuredAt: number },
): ContextUsageRecord {
  return {
    sessionId: required.sessionId,
    phase: phaseOf(raw.phase),
    tokens: numberOrNull(raw.tokens),
    window: required.window,
    percent: numberOrNull(raw.percent),
    compactWindow: numberOrNull(raw.compactWindow),
    compactPercent: numberOrNull(raw.compactPercent),
    autoCompactThreshold: numberOrNull(raw.autoCompactThreshold),
    measuredAt: required.measuredAt,
  }
}

/** 判定用的百分比：auto-compact 開啟用 compactPercent，關閉用 percent；選中值缺席為 null。 */
export function selectedPercent(record: ContextUsageRecord): number | null {
  return record.autoCompactThreshold === null ? record.percent : record.compactPercent
}

/** 待 compact／待 clear 判定；沒有用量檔、選中值缺席或 role 為 none 時不標。 */
export function contextMarkOf(input: { record: ContextUsageRecord | null; role: ContextRole; holdsInProgress: boolean }): ContextMark {
  const { record, role, holdsInProgress } = input
  const percent = record === null ? null : selectedPercent(record)
  if (percent === null || role === 'none') return null
  if (role === 'coordinator') return percent >= COORDINATOR_T_COMPACT ? 'compact' : null
  if (holdsInProgress) return percent >= LANE_T_COMPACT ? 'compact' : null
  return percent >= LANE_T_CLEAR ? 'clear' : null
}

/** 「各 session」列的用量字尾：`ctx <百分比>%（<量測距今>）`；用量缺席寫「ctx 未量測」；沒有用量檔為 null。 */
export function contextUsageSuffix(record: ContextUsageRecord | null, nowMs: number): string | null {
  if (record === null) return null
  const percent = selectedPercent(record)
  const value = percent === null ? '未量測' : `${percent}%`
  return `ctx ${value}（${formatAge(nowMs, record.measuredAt)}）`
}

/** 線標題的標記：`［待 compact］`、`［待 clear］`；不標為空字串。 */
export function contextMarkLabel(mark: ContextMark): string {
  return mark === null ? '' : `［待 ${mark}］`
}

/** 恢復開工徽章的判定：phase 為 resumed 且距今不超過 RESUME_BADGE_MS 時回傳該 phase；compacted（尚未開工）不顯示。 */
export function recentResume(record: ContextUsageRecord | null, nowMs: number): ResumePhase | null {
  const phase = record?.phase ?? null
  if (phase === null || phase.kind !== 'resumed') return null
  return nowMs - phase.at <= RESUME_BADGE_MS ? phase : null
}

/** 恢復開工徽章：`［/<來源> 後已恢復 HH:MM］`，時間為本機時間。 */
export function resumeBadgeText(phase: ResumePhase): string {
  return `［/${phase.source} 後已恢復 ${localHourMinute(phase.at)}］`
}

/** line_status 的 phase 段：`phase <compacted|resumed>（<來源>，HH:MM）`，本機時間；不受徽章的 10 分鐘限制。 */
export function phaseText(phase: ResumePhase): string {
  return `phase ${phase.kind}（${phase.source}，${localHourMinute(phase.at)}）`
}

/** 毫秒時間的本機 `HH:MM`。 */
function localHourMinute(at: number): string {
  const date = new Date(at)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/**
 * 線標題列 `［狀態］` 之後的文字：待 compact／待 clear 標記接恢復開工徽章，皆無時為空字串。
 * 依 session 名稱找存活 session 與其用量檔；名稱為主控以主控門檻判定，其他為一般線（收線的線不在看板上，不會呼叫）。
 * 持有 in_progress 票＝佇列中有票在主 checkout 為 in_progress。
 */
export function laneContextLabel(input: {
  sessionName: string | null
  tokens: readonly QueueToken[]
  tickets: readonly TicketStatus[]
  sessions: readonly SessionState[]
  usages: Readonly<Record<string, ContextUsageRecord>>
  nowMs: number
}): string {
  const { sessionName, tokens, tickets, sessions, usages, nowMs } = input
  if (sessionName === null) return ''
  const sessionId = findSessionByName(sessions, sessionName)?.sessionId ?? null
  const record = sessionId === null ? null : (usages[sessionId] ?? null)
  const role: ContextRole = sessionName === COORDINATOR_SESSION_NAME ? 'coordinator' : 'lane'
  const inProgress = new Set(tickets.filter(ticket => ticket.status === IN_PROGRESS_STATUS).map(ticket => ticket.id))
  const holdsInProgress = tokens.some(token => token.kind === 'ticket' && inProgress.has(token.id))
  const resumed = recentResume(record, nowMs)
  return contextMarkLabel(contextMarkOf({ record, role, holdsInProgress })) + (resumed === null ? '' : resumeBadgeText(resumed))
}

/** 用量檔存在但解析不成立的 session：以 sessionId 為鍵，值為原因（usageReaders.ts 的 readContextUsageStates 產生）。 */
export type ContextUsageFailures = Readonly<Record<string, string>>

/**
 * line_status 一條未收線的線的 context 段（接在依據之後）：
 * - 有用量檔：`ctx <百分比>%（<距量測>）` 接看板線標題同一份的標記與徽章（laneContextLabel），有 phase 再接 `｜phase …`
 * - 用量檔存在但解析失敗：`ctx 用量檔解析失敗：<原因>`
 * - 沒有用量檔：`ctx 無用量檔`
 * 名稱未寫、名稱不在存活 session 中、session 檔沒有 sessionId 時為 null：持有者無從查起，依據段已說明。
 */
export function laneContextStatus(input: Parameters<typeof laneContextLabel>[0] & { failures: ContextUsageFailures }): string | null {
  const { sessionName, sessions, usages, failures, nowMs } = input
  if (sessionName === null) return null
  const sessionId = findSessionByName(sessions, sessionName)?.sessionId ?? null
  if (sessionId === null) return null
  const failure = failures[sessionId]
  if (failure !== undefined) return `ctx 用量檔解析失敗：${failure}`
  const record = usages[sessionId] ?? null
  if (record === null) return 'ctx 無用量檔'
  const usage = `${contextUsageSuffix(record, nowMs)}${laneContextLabel(input)}`
  return record.phase === null ? usage : `${usage}｜${phaseText(record.phase)}`
}

/** 刪除前的路徑檢查：必須直接位於主 checkout 的用量檔目錄下，檔名符合 sessionId 格式；不符就不刪。 */
export function isDeletableUsagePath(mainPath: string, path: string): boolean {
  const dir = `${mainPath}/${CONTEXT_USAGE_DIR}/`
  if (!path.startsWith(dir)) return false
  return USAGE_FILE_NAME.test(path.slice(dir.length))
}

/** 孤兒用量檔：一般檔、檔名符合格式、不屬於存活 session，且 mtime 超過 ORPHAN_AGE_MS。回傳檔名。 */
export function orphanUsageFiles(
  entries: readonly { name: string; kind: string; mtimeMs: number }[],
  liveSessionIds: ReadonlySet<string>,
  nowMs: number,
): string[] {
  return entries
    .filter(entry => entry.kind === 'file' && USAGE_FILE_NAME.test(entry.name))
    .filter(entry => !liveSessionIds.has(entry.name.slice(0, -'.json'.length)))
    .filter(entry => nowMs - entry.mtimeMs > ORPHAN_AGE_MS)
    .map(entry => entry.name)
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' ? value : null
}

/** phase 欄位：形狀不符（含舊版沒有此欄）一律為 null。 */
function phaseOf(value: unknown): ResumePhase | null {
  if (typeof value !== 'object' || value === null) return null
  const raw = value as Record<string, unknown>
  const isKind = raw.kind === 'compacted' || raw.kind === 'resumed'
  const isSource = raw.source === 'compact' || raw.source === 'clear'
  if (!isKind || !isSource || typeof raw.at !== 'number') return null
  return { kind: raw.kind as ResumePhase['kind'], source: raw.source as ResumePhase['source'], at: raw.at }
}
