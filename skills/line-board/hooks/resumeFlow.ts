// line-board：恢復開工通知的流程（判定狀態機與通知文字在 resumeNotice.ts，紀錄行格式在 resumeNoticeLog.ts）。
// 本檔持有判定的模組層狀態，串接寫 phase（usageWriter.ts）→ session.send 給主控 → 寫送出紀錄檔；
// register.tsx 的 session.compact、session.end、prompt.submit 餵事件，session.measure 取目前的 phase。

import type { EngineInterface } from 'claude-code'

import type { ResumePhase } from '../types'
import {
  COORDINATOR_SESSION_NAME,
  RESUME_NOTICE_LOG_MAX_LINES,
  RESUME_NOTICE_LOG_PATH,
  appendCappedLog,
  formatTime,
  messageOf,
  resumeNoticeDecision,
  resumeNoticeLogLine,
  resumeNoticeText,
  resumePhaseOf,
  stepResume,
} from './parse'
import type { PendingResume, ResumeEvent, ResumedEvent, ResumeNoticeOutcome } from './parse'
import { findCheckouts, readLanes, readProjectConfig, readSessions } from './readers'
import { mainCheckoutForUsage, writePhase } from './usageWriter'

/**
 * 恢復開工通知的主管道（session.send 給主控）開關，預設關閉。
 * 實測 auto mode 下 plugin 在事件中主動送訊沒有對應的使用者請求，classifier 不給判定而拒送；
 * 與「接收端權限模式不同時被暫扣」同類，依「暫扣就關」關閉，不設法讓 classifier 放行。
 * 關閉時仍寫 resume-notice.log（step=send-disabled），主控以用量檔 phase、線標題徽章、line_status 為準。
 */
const IS_RESUME_NOTICE_SEND_ENABLED = false
/**
 * 恢復開工判定的待通知狀態與最近一次恢復開工（resumeNotice.ts）。放在模組層：/clear 換新 session id 但行程繼續，
 * 狀態必須跨 session id 保留。限制：plugin 熱重載時遺失，該次漏送，由 phase 兜底不補救（line-continuity.md）。
 */
let pendingResume: PendingResume | null = null
let lastResumed: ResumedEvent | null = null

/** 套用一個恢復開工判定事件到模組層狀態；這一步恢復開工時回傳該事件（同時記為最近一次）。 */
export function applyResumeEvent(event: ResumeEvent): ResumedEvent | null {
  const step = stepResume(pendingResume, event)
  pendingResume = step.pending
  if (step.resumed !== null) lastResumed = step.resumed
  return step.resumed
}

/** 目前要寫進用量檔的 phase（由模組層狀態推出）。 */
export function currentResumePhase(): ResumePhase | null {
  return resumePhaseOf(pendingResume, lastResumed)
}

/**
 * 恢復開工：先寫 phase（輔管道，一定執行），再以 session.send 傳一行給主控（主管道，開關見 IS_RESUME_NOTICE_SEND_ENABLED），
 * 最後把走到的步驟與結果寫一行到送出紀錄檔（resumeNoticeLog.ts）。送不出去不重試（phase 已寫）。
 */
export async function notifyResumed($: EngineInterface, resumed: ResumedEvent): Promise<void> {
  await writePhase($, currentResumePhase)
  const outcome = await sendResumeNotice($, resumed)
  await appendResumeNoticeLog($, resumed, outcome)
}

/**
 * 主管道：本 session 的名稱以 sessionId 比對 ~/.claude/sessions 的狀態檔取得，線號以名稱比對協調票的現行佇列行；
 * 比對不到、是主控自身或已收線時不送。每個提早結束的分支都回傳原因，由呼叫端寫入紀錄檔。
 */
async function sendResumeNotice($: EngineInterface, resumed: ResumedEvent): Promise<ResumeNoticeOutcome> {
  if (!IS_RESUME_NOTICE_SEND_ENABLED) return { step: 'send-disabled' }
  try {
    const sessionId = await $.session.id()
    const root = await $.session.root()
    const { checkoutPaths } = await findCheckouts($, root)
    const mainPath = checkoutPaths[0] ?? root
    const config = await readProjectConfig($, mainPath)
    if (config.kind !== 'ok') return { step: 'config-unavailable', detail: 'message' in config ? `${config.kind}：${config.message}` : config.kind }
    const sessions = await readSessions($, checkoutPaths)
    if (sessions.kind !== 'ok') return { step: 'state-unavailable', detail: `session 狀態：${sessions.message}` }
    const lanes = await readLanes($, mainPath, config.coordinationTicket)
    if (lanes.kind !== 'ok') return { step: 'state-unavailable', detail: `協調票：${lanes.message}` }
    const sessionName = sessions.sessions.find(state => state.sessionId === sessionId)?.name ?? null
    const decision = resumeNoticeDecision({ sessionName, lines: lanes.lines })
    if (decision.kind === 'skip') return { step: 'skipped', reason: decision.reason }
    const text = resumeNoticeText(decision.target, formatTime(new Date(resumed.resumedAt)).slice(-8), resumed.source)
    const sent = await $.session.send({ to: COORDINATOR_SESSION_NAME, text })
    return sent.isDelivered ? { step: 'sent', isDelivered: true } : { step: 'sent', isDelivered: false, reason: String(sent.reason) }
  } catch (error) {
    return { step: 'error', detail: messageOf(error) }
  }
}

/** 寫一行到主 checkout 的送出紀錄檔（保留最後 RESUME_NOTICE_LOG_MAX_LINES 行）；寫不進去送 transcript（恢復開工才寫，不洗版）。 */
async function appendResumeNoticeLog($: EngineInterface, resumed: ResumedEvent, outcome: ResumeNoticeOutcome): Promise<void> {
  try {
    const path = `${await mainCheckoutForUsage($)}/${RESUME_NOTICE_LOG_PATH}`
    const line = resumeNoticeLogLine({ time: formatTime(new Date(resumed.resumedAt)), sessionId: await $.session.id(), source: resumed.source, outcome })
    // 檔案不存在（第一次寫）讀取會拒絕，視為空檔
    const existing = await $.fs.read(path).catch(() => '')
    await $.fs.write(path, appendCappedLog(existing, line, RESUME_NOTICE_LOG_MAX_LINES))
  } catch (error) {
    $.ui.log(`line-board 警告：寫恢復開工送出紀錄檔失敗：${messageOf(error)}`, { to: 'transcript' })
  }
}
