// 線 session 恢復開工通知：/compact 或 /clear 之後，第一個 prompt 送出時通知主控（multi-session-orchestration 的
// line-continuity.md〈恢復開工通知〉）。本檔是判定與文字，不碰 $；事件掛接與傳送由 register.tsx 負責。
//
// 判定來源是 plugin 事件，不是 settings hooks 的 SessionStart source（plugin 的 session.start 沒有 source，且 /clear 不觸發）：
// - compact 完成：session.compact 的 next 回傳無 skip，trigger 不是 precompute，且不帶 agentId（subagent 自己的 compact 不算）
// - clear 完成：session.end 的 reason 為 clear（行程繼續、換新 session id）
// - 恢復開工：上兩者之後第一個 prompt.submit；/compact、/clear 本身的 submit 不算
// 待通知狀態放在模組層變數，plugin 熱重載時會遺失（漏送由用量檔的 phase 兜底，不補救）。

import type { LaneLine, ResumePhase, ResumeSource } from '../types'
import { endedForm } from './lanes'

/** 已完成 compact 或 clear、尚未恢復開工：來源與完成時間（毫秒）。 */
export type PendingResume = { source: ResumeSource; at: number }

/** 恢復開工：來源、compact／clear 完成時間與恢復時間（毫秒）。 */
export type ResumedEvent = PendingResume & { resumedAt: number }

/** 判定用的事件，由 register.tsx 從 session.compact、session.end、prompt.submit 轉成。 */
export type ResumeEvent =
  | { kind: 'compact'; trigger: string; agentId?: string; isSkipped: boolean; at: number }
  | { kind: 'end'; reason: string; at: number }
  | { kind: 'submit'; command?: string; at: number }

/** 一步判定的結果：新的待通知狀態，與這一步是否恢復開工。 */
export type ResumeStep = { pending: PendingResume | null; resumed: ResumedEvent | null }

/** 通知對象：線號與 session 名稱。 */
export type ResumeNoticeTarget = { lane: number; name: string }

/** 長駐主控的 session 名稱：主控自身的 compact／clear 不送通知。 */
export const COORDINATOR_SESSION_NAME = '主控'

/** 不設待通知的 compact trigger：precompute 只預先計算，對話沒有被壓縮。 */
const NON_COMPACTING_TRIGGER = 'precompute'

/** 本身就是 compact／clear 的 slash command：它們的 prompt.submit 不算恢復開工。 */
const RESET_COMMANDS: readonly string[] = ['compact', 'clear']

/** 套用一個事件。 */
export function stepResume(pending: PendingResume | null, event: ResumeEvent): ResumeStep {
  switch (event.kind) {
    case 'compact': {
      const isMainCompaction = !event.isSkipped && event.trigger !== NON_COMPACTING_TRIGGER && event.agentId === undefined
      return { pending: isMainCompaction ? { source: 'compact', at: event.at } : pending, resumed: null }
    }
    case 'end':
      // clear 之外的結束（resume、exit 等）：這個 session 不會再開工，清掉待通知
      return { pending: event.reason === 'clear' ? { source: 'clear', at: event.at } : null, resumed: null }
    case 'submit': {
      const isResetCommand = event.command !== undefined && RESET_COMMANDS.includes(event.command)
      if (pending === null || isResetCommand) return { pending, resumed: null }
      return { pending: null, resumed: { ...pending, resumedAt: event.at } }
    }
  }
}

/** 不送通知的原因：取不到本 session 名稱、主控自身、名稱比對不到線、該線已收線。 */
export type ResumeNoticeSkipReason = 'no-session-name' | 'coordinator' | 'lane-not-found' | 'lane-ended'

/** 送或不送：送時帶通知對象，不送時帶原因（寫入送出紀錄檔）。 */
export type ResumeNoticeDecision = { kind: 'send'; target: ResumeNoticeTarget } | { kind: 'skip'; reason: ResumeNoticeSkipReason }

/** 判定送或不送：名稱比對到協調票上未收線的線才送。 */
export function resumeNoticeDecision(input: { sessionName: string | null; lines: readonly LaneLine[] }): ResumeNoticeDecision {
  const { sessionName, lines } = input
  if (sessionName === null) return { kind: 'skip', reason: 'no-session-name' }
  if (sessionName === COORDINATOR_SESSION_NAME) return { kind: 'skip', reason: 'coordinator' }
  const line = lines.find(candidate => candidate.session === sessionName)
  if (line === undefined) return { kind: 'skip', reason: 'lane-not-found' }
  if (endedForm(line.queue) !== null) return { kind: 'skip', reason: 'lane-ended' }
  return { kind: 'send', target: { lane: line.lane, name: sessionName } }
}

/** 主管道的通知文字：固定一行 `L<n>（<名稱>）已恢復開工：<時間>，來源 <compact|clear>`。 */
export function resumeNoticeText(target: ResumeNoticeTarget, time: string, source: ResumeSource): string {
  return `L${target.lane}（${target.name}）已恢復開工：${time}，來源 ${source}`
}

/** 用量檔的 phase：有待通知為 compacted；最近一次恢復開工為 resumed；都沒有為 null。待通知優先（之後又 compact）。 */
export function resumePhaseOf(pending: PendingResume | null, lastResumed: ResumedEvent | null): ResumePhase | null {
  if (pending !== null) return { kind: 'compacted', source: pending.source, at: pending.at }
  if (lastResumed !== null) return { kind: 'resumed', source: lastResumed.source, at: lastResumed.resumedAt }
  return null
}
