// 恢復開工通知的送出紀錄檔（multi-session-orchestration 的 line-continuity.md §4〈送出紀錄檔〉）：
// 每次恢復開工在主 checkout 的 `.claude/hook-logs/line-board/resume-notice.log` 寫一行，記錄走到哪一步、為何沒送、
// session.send 的回傳或例外。用途是主管道沒收到通知時能定位原因（原本這些分支只 return 或只記 debug，事後無從查起）。
// 本檔是紀錄行的格式與上限截斷，不碰 $；讀寫由 register.tsx 負責。

import type { ResumeSource } from '../types'
import type { ResumeNoticeSkipReason } from './resumeNotice'

/** 送出紀錄檔：主 checkout 下的相對路徑。 */
export const RESUME_NOTICE_LOG_PATH = '.claude/hook-logs/line-board/resume-notice.log'

/** 送出紀錄檔保留的行數上限：每次恢復開工一行，超過時只留最後這麼多行。 */
export const RESUME_NOTICE_LOG_MAX_LINES = 500

/** sessionId 在紀錄行中保留的字元數。 */
const SESSION_ID_PREFIX_LENGTH = 8

/**
 * 一次恢復開工走到的步驟與結果：
 * - send-disabled：主管道開關關閉（IS_RESUME_NOTICE_SEND_ENABLED）
 * - config-unavailable：專案設定讀不到或不成立
 * - state-unavailable：session 狀態檔或協調票讀不到
 * - skipped：判定不送（resumeNoticeDecision 的原因）
 * - sent：已呼叫 session.send，帶回傳
 * - error：過程中丟出例外
 */
export type ResumeNoticeOutcome =
  | { step: 'send-disabled' }
  | { step: 'config-unavailable'; detail: string }
  | { step: 'state-unavailable'; detail: string }
  | { step: 'skipped'; reason: ResumeNoticeSkipReason }
  | { step: 'sent'; isDelivered: true }
  | { step: 'sent'; isDelivered: false; reason: string }
  | { step: 'error'; detail: string }

/** 紀錄行：`<時間>\tsession=<前 8 碼>\tsource=<compact|clear>\tstep=<步驟>[\t<結果欄位>]`，原因中的換行壓成空白。 */
export function resumeNoticeLogLine(input: { time: string; sessionId: string; source: ResumeSource; outcome: ResumeNoticeOutcome }): string {
  const { time, sessionId, source, outcome } = input
  const fields = [time, `session=${sessionId.slice(0, SESSION_ID_PREFIX_LENGTH)}`, `source=${source}`, `step=${outcome.step}`, ...outcomeFields(outcome)]
  return fields.map(oneLine).join('\t')
}

/** 接上新的一行，只留最後 maxLines 行；結果以換行結尾。 */
export function appendCappedLog(existing: string, line: string, maxLines: number): string {
  const lines = existing.split('\n').filter(text => text !== '')
  lines.push(line)
  return `${lines.slice(-maxLines).join('\n')}\n`
}

function outcomeFields(outcome: ResumeNoticeOutcome): string[] {
  switch (outcome.step) {
    case 'send-disabled':
      return []
    case 'skipped':
      return [`reason=${outcome.reason}`]
    case 'sent':
      return outcome.isDelivered ? ['isDelivered=true'] : ['isDelivered=false', `reason=${outcome.reason}`]
    case 'config-unavailable':
    case 'state-unavailable':
    case 'error':
      return [`detail=${outcome.detail}`]
  }
}

/** 換行與 tab 改為空白：一次恢復開工只占一行，欄位分隔不被原因中的 tab 打亂。 */
function oneLine(text: string): string {
  return text.replace(/\r?\n|\t/g, ' ')
}
