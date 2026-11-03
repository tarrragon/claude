// line_status 工具的組裝：每次呼叫都重讀（不取 Pane 的 snapshot：Pane 只在設定成立時定時刷新，且最多落後 30 秒），
// 讀取經 readers.ts（用量檔經 usageReaders.ts），判讀與輸出文字經 parse.ts 匯出的 continuity.ts。

import type { EngineInterface } from 'claude-code'

import type { ProjectConfigResult } from '../types'
import { findCheckouts, readLanes, readProjectConfig, readSessions, readSourceLog, readTicketStatus } from './readers'
import { readContextUsageStates } from './usageReaders'
import { COORDINATION_HOWTO, COORDINATION_NONE, continuityTicketIds, formatLineStatus, lineStatusReport, ticketPrefixOf } from './parse'

/**
 * 產生 line_status 的輸出文字。設定不成立、協調票或 session 讀不到時，回傳說明原因的文字而不是拋出，
 * 讓模型讀得到「為何判不出」，不會與「沒有線」同形。readAt 為呼叫端格式化的讀取時間。
 */
export async function lineStatusText($: EngineInterface, readAt: string): Promise<string> {
  const root = await $.session.root()
  const { checkoutPaths, checkoutNote } = await findCheckouts($, root)
  const mainPath = checkoutPaths[0] ?? root
  // checkout 清單取不到時 mainPath 可能是 worktree：每個提前回傳都附上原因，否則模型看不出讀錯了位置
  const cannot = (reason: string) => withNotes(`line_status 無法判讀：${reason}`, [checkoutNote])
  const config = await readProjectConfig($, mainPath)
  if (config.kind !== 'ok') return cannot(coordinationUnavailable(config))
  const prefix = ticketPrefixOf(config.coordinationTicket)
  const laneLines = await readLanes($, mainPath, config.coordinationTicket)
  if (laneLines.kind !== 'ok') return cannot(`協調票讀取失敗（${laneLines.message}）`)
  const sessions = await readSessions($, checkoutPaths)
  if (sessions.kind !== 'ok') return cannot(`~/.claude/sessions 讀取失敗（${sessions.message}）`)
  const log = await readSourceLog($, checkoutPaths)
  // readProjectConfig 已確認前綴推導得出；推不出時短票號無從補全，佇列已完成的偵測因此不可靠，須註明
  const ids = continuityTicketIds(laneLines.lines, prefix ?? '')
  const tickets = await Promise.all(ids.map(id => readTicketStatus($, mainPath, id)))
  // 用量檔只在主 checkout（contextUsage.ts 寫入位置）；每次呼叫重讀，與看板的 snapshot 無關
  const { usages, failures } = await readContextUsageStates($, mainPath, sessions)
  const context = { usages, failures, nowMs: await $.clock.now() }
  const report = lineStatusReport({ lanes: laneLines.lines, todos: laneLines.todos, sessions: sessions.sessions, log: log.entries, tickets, prefix: prefix ?? '', context })
  const text = formatLineStatus(report, { coordinationTicket: config.coordinationTicket, readAt })
  return withNotes(text, [
    checkoutNote,
    sourceLogNote(log.readCount, checkoutPaths.length),
    ...config.warnings.map(warning => `協調票解析警告：${warning}`),
    prefix === null ? `協調票 ${config.coordinationTicket} 推不出短票號前綴，「佇列已完成未收線」的偵測不可靠` : null,
  ])
}

/** 協調票不成立的說明（0 張、多張、CLI 失敗）；0 張的用語與看板 /board 共用。 */
function coordinationUnavailable(config: Exclude<ProjectConfigResult, { kind: 'ok' }>): string {
  switch (config.kind) {
    case 'none':
      return `${COORDINATION_NONE}；${COORDINATION_HOWTO}`
    case 'multiple':
      return `active 版本有多張標記 coordination: true 的進行中票，不自行擇一，請用戶裁定：${config.candidates.join('、')}`
    case 'error':
      return `協調票解析失敗：${config.message}`
  }
}

/**
 * 來源紀錄的讀取註記：有 checkout 讀不到紀錄時，該 checkout 內啟動的 session 會顯示「來源紀錄查無此 id」，
 * 與真的沒有紀錄同形，所以註明讀到幾份；全部讀到時不註記。
 */
function sourceLogNote(readCount: number, checkoutCount: number): string | null {
  if (readCount === checkoutCount) return null
  if (readCount === 0) return '各 checkout 都讀不到 SessionStart 來源紀錄，接續狀態一律為來源不明'
  return `SessionStart 來源紀錄只讀到 ${readCount}／${checkoutCount} 個 checkout，其餘 checkout 內啟動的 session 會顯示查無此 id`
}

/** 在文字後附上「注意：」行（略過 null）；沒有註記時原樣回傳。 */
function withNotes(text: string, notes: readonly (string | null)[]): string {
  const kept = notes.filter((note): note is string => note !== null)
  return kept.length === 0 ? text : `${text}\n注意：${kept.join('；')}`
}
