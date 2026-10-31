// 線與佇列：協調票 Solution 的現行佇列行與線目標行解析（每線取最後一行）、票序拆分與格式化。
// 不碰 $（無檔案、無行程），讓 *.test.ts 能直接驗證；讀檔與執行命令由 readers.ts 負責。

import type { Lane, LaneLine, QueueToken, TicketStatus } from '../types'

/** 現行佇列行掃描範圍的起點：協調票的 Solution 二級標題，讀到下一個二級標題前。 */
const SOLUTION_HEADING = '## Solution'

/**
 * 現行佇列行（協調票〈看板讀取約定〉）：行首即 `**L<n> 現行佇列**`，n 為數字，
 * 其後可帶全形括號的 session 名稱，再接全形冒號與票序。
 * 只比對行首：清單項（`- **L7 …`）與以反引號引用範本的說明行都不算。
 */
const LANE_LINE = /^\*\*L(\d+) 現行佇列\*\*(?:（([^）]*)）)?：(.*)$/

/** 票序寫此值表示這條線結束，看板不顯示；目標行寫此值表示清除目標。 */
export const LANE_ENDED = '（無）'

/** 票序整段等於其一即為收線（multi-session-orchestration 的 line-continuity.md §2：`（無）` 或 `（結束）`）。 */
const ENDED_MARKS: readonly string[] = [LANE_ENDED, '（結束）']

/** 收線但附說明的寫法：`無（…）`（沒有括號的「無」後接說明）。以收線記號開頭再接文字的寫法另由 ENDED_MARKS 判定。 */
const BARE_ENDED_WITH_NOTE = /^無（/

/**
 * 票序的收線寫法：exact 為合規的收線（看板不顯示該線）、with-note 為收線記號後還有文字（看板仍顯示，
 * line_status 列為過期項）、null 為沒有收線。看板與 line_status 共用此判定，收線的定義只有這一份。
 */
export function endedForm(queue: string): 'exact' | 'with-note' | null {
  if (ENDED_MARKS.includes(queue)) return 'exact'
  if (ENDED_MARKS.some(mark => queue.startsWith(mark)) || BARE_ENDED_WITH_NOTE.test(queue)) return 'with-note'
  return null
}

/**
 * 線目標行（協調票，UI 裁定）：行首即 `**L<n> 目標**`，n 為數字，接全形冒號與一句話目標。
 * 判定與現行佇列行相同：只比對行首，清單項、表格內與以反引號引用範本的行都不算。
 */
const GOAL_LINE = /^\*\*L(\d+) 目標\*\*：(.*)$/

/** 票序中的分隔符：`→` 依序、`∥` 並行；拆分時保留分隔符本身。 */
const QUEUE_SEPARATOR = /\s*(→|∥)\s*/

/** 一步的開頭短票號：三位數，可帶任意層 `.n` 子序號（如 `123.2.1`）；其後為註記。 */
const STEP_SERIAL = /^(\d{3}(?:\.\d+)*)(.*)$/

/** 一步的開頭完整票號：`<major.minor.patch>-W<n>-<序號>`（ticket-id-conventions 的版本為三段數字）；其後為註記。 */
const STEP_FULL_ID = /^(\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*)(.*)$/

/** 一步的開頭同版本異 wave 寫法：`W<n>-<序號>`，補上前綴的版本即為完整票號；其後為註記。 */
const STEP_WAVE_ID = /^(W\d+-\d+(?:\.\d+)*)(.*)$/

/** 短票號前綴的版本部分：`<版本>-W<n>-` 的 `<版本>`；前綴不是此形式時 W 寫法無法補成完整票號。 */
const PREFIX_VERSION = /^(.+)-W\d+-$/

/**
 * 一步的開頭票號換成 [顯示用寫法, 完整票號, 註記]：完整票號原樣、`W<n>-<序號>` 補前綴的版本、短票號補整個前綴；
 * 皆不符時為 null。顯示用寫法保留佇列行的原文。
 */
function stepTicket(part: string, prefix: string): [string, string, string] | null {
  const full = STEP_FULL_ID.exec(part)
  if (full !== null) return [full[1] ?? '', full[1] ?? '', full[2] ?? '']
  const wave = STEP_WAVE_ID.exec(part)
  if (wave !== null) {
    const version = PREFIX_VERSION.exec(prefix)
    return version === null ? null : [wave[1] ?? '', `${version[1]}-${wave[1]}`, wave[2] ?? '']
  }
  const short = STEP_SERIAL.exec(part)
  return short === null ? null : [short[1] ?? '', `${prefix}${short[1]}`, short[2] ?? '']
}

/** 取 Solution 段落的各行（自 `## Solution` 起到下一個 `## ` 標題前）；沒有該標題時回傳空陣列。 */
export function solutionLines(text: string): string[] {
  const lines = text.split('\n').map(line => line.trimEnd())
  const start = lines.findIndex(line => line === SOLUTION_HEADING || line.startsWith(`${SOLUTION_HEADING} `))
  if (start === -1) return []
  const rest = lines.slice(start + 1)
  const end = rest.findIndex(line => line.startsWith('## '))
  return end === -1 ? rest : rest.slice(0, end)
}

/** fenced code block 的界線行開頭：區間內的行是示例。 */
const CODE_FENCE = '```'

/**
 * Solution 段落中不在 fenced code block 內的行（界線行本身也去掉）。票面的固定格式行（等用戶標記、用戶待辦行）
 * 一律經此過濾，所以說明段裡以 fence 引用的格式範例不會被判為該行；判定只在這裡實作一份。
 */
export function unfencedSolutionLines(text: string): string[] {
  const lines: string[] = []
  let inFence = false
  for (const line of solutionLines(text)) {
    if (line.startsWith(CODE_FENCE)) inFence = !inFence
    else if (!inFence) lines.push(line)
  }
  return lines
}

/**
 * 票序拆成票號、分隔符與無法辨識的文字，保留原順序。票號接受三種寫法：短票號（補 prefix）、完整票號、
 * `W<n>-<序號>`（補 prefix 的版本）；serial 為佇列行的原寫法。prefix 為短票號前綴（見 shared.ts ticketPrefixOf）。
 */
export function parseQueue(queue: string, prefix: string): QueueToken[] {
  const tokens: QueueToken[] = []
  for (const part of queue.trim().split(QUEUE_SEPARATOR)) {
    if (part === '') continue
    if (part === '→' || part === '∥') {
      tokens.push({ kind: 'sep', text: part })
      continue
    }
    const ticket = stepTicket(part, prefix)
    if (ticket === null) {
      tokens.push({ kind: 'text', text: part })
      continue
    }
    const [serial, id, note] = ticket
    tokens.push({ kind: 'ticket', serial, id, note: note.trim() })
  }
  return tokens
}

/**
 * 掃協調票 Solution 的線目標行，每條線只取最後一行；最後一行寫 `（無）` 或為空的線不在結果中（目標已清除）。
 */
export function parseLaneGoals(text: string): Map<number, string> {
  const goals = new Map<number, string>()
  for (const [lane, match] of lastMatchPerLane(text, GOAL_LINE)) {
    const goal = (match[2] ?? '').trim()
    if (goal !== '' && goal !== LANE_ENDED) goals.set(lane, goal)
  }
  return goals
}

/**
 * 逐行以 pattern 比對 Solution 段落，每條線只留最後一個符合的行；pattern 的第一個群組須為線號。
 * 現行佇列行與線目標行共用此規則：同一條線較早的行是歷史，一律被較晚的行取代。
 */
function lastMatchPerLane(text: string, pattern: RegExp): Map<number, RegExpExecArray> {
  const latest = new Map<number, RegExpExecArray>()
  for (const line of solutionLines(text)) {
    const match = pattern.exec(line)
    if (match !== null) latest.set(Number(match[1]), match)
  }
  return latest
}

/**
 * 掃協調票的 Solution，每條線只取最後一次出現的現行佇列行，依線號排序；各線附上 parseLaneGoals 的目標（沒有時為 null）。
 * 最後一行票序為 `（無）` 的線不回傳；歷史行（同線較早的行）的票號不進結果。
 * prefix 為協調票推導的短票號前綴（shared.ts ticketPrefixOf），原樣傳給 parseQueue 補全短票號。
 */
export function parseLanes(text: string, prefix: string): Lane[] {
  const goals = parseLaneGoals(text)
  return parseLaneLines(text)
    .filter(({ queue }) => endedForm(queue) !== 'exact')
    .map(({ lane, session, queue }) => ({ lane, session, goal: goals.get(lane) ?? null, tokens: parseQueue(queue, prefix) }))
}

/**
 * 掃協調票的 Solution，每條線只取最後一次出現的現行佇列行，依線號排序，保留票序原文（含收線的線）。
 * parseLanes 以此濾掉收線的線；接續判讀（continuity.ts）要看收線與收線寫法，直接用此結果。
 */
export function parseLaneLines(text: string): LaneLine[] {
  return [...lastMatchPerLane(text, LANE_LINE)]
    .map(([lane, match]) => ({ lane, session: match[2] ?? null, queue: (match[3] ?? '').trim() }))
    .sort((a, b) => a.lane - b.lane)
}

/** 所有線的佇列完整票號，保留首次出現順序並去重。 */
export function laneTicketIds(lanes: readonly Lane[]): string[] {
  const ids: string[] = []
  for (const lane of lanes) {
    for (const token of lane.tokens) {
      if (token.kind === 'ticket' && !ids.includes(token.id)) ids.push(token.id)
    }
  }
  return ids
}

/** 票序文字：每張票為 `短票號〔status〕註記`，分隔符前後各一空白；查不到狀態的票只顯示短票號。 */
export function formatQueue(tokens: readonly QueueToken[], tickets: readonly TicketStatus[]): string {
  const byId = new Map(tickets.map(ticket => [ticket.id, ticket.status]))
  return tokens
    .map(token => {
      if (token.kind === 'sep') return ` ${token.text} `
      if (token.kind === 'text') return token.text
      const status = byId.get(token.id)
      return `${token.serial}${status === undefined ? '' : `〔${status}〕`}${token.note}`
    })
    .join('')
}
