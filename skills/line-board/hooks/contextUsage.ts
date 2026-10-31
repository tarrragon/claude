// context 用量檔：每個 session 以 session.measure 把自己的 context 用量寫到主 checkout 的
// `.claude/hook-logs/line-board/context/<sessionId>.json`，看板與 line_status 讀檔判定「待 compact／待 clear」，
// 不依賴 AI 回報。本檔決定何時寫、寫到哪、寫什麼；不碰 $，讀檔寫檔由 register.tsx 負責。
//
// 兩個分母：
// - window／percent：模型的 context window，與狀態列的 context_window_size／used_percentage 相同。
// - compactWindow／compactPercent：/context 量測所用的 compaction window（breakdown.rawMaxTokens），
//   可能小於 window；auto-compact 以它為準。兩者都記，門檻採哪一個由實測後寫在票面。
// compact 剛完成、下一次回應前 tokens 與 percent 缺席：記為 null，不寫成 0（0 會被讀成幾乎沒用）。

import type { ContextUsageRecord, ResumePhase } from '../types'

/** 用量檔目錄，相對主 checkout。 */
export const CONTEXT_USAGE_DIR = '.claude/hook-logs/line-board/context'

/** sessionId 的合法字元：只允許英數、連字號與底線，確保檔名不會跳出用量檔目錄。 */
const SESSION_ID_PATTERN = /^[A-Za-z0-9_-]+$/

/** session.measure 的 changed 單位；只有 context 變動才寫檔（rateLimits、cost 與 context 用量無關）。 */
const CONTEXT_UNIT = 'context'

/** 狀態列的 context 用量（SessionContextUsage 中本檔用到的欄位）。 */
export type ContextFill = { tokens?: number; window: number; percent?: number }

/** compaction window 的量測（SessionContextBreakdown 中本檔用到的欄位）；auto-compact 關閉時沒有門檻。 */
export type CompactionWindow = { rawMaxTokens: number; autoCompactThreshold?: number }

/** 這次 measure 是否該寫用量檔：changed 含 context。 */
export function isContextChanged(changed: readonly string[]): boolean {
  return changed.includes(CONTEXT_UNIT)
}

/** 用量檔的絕對路徑；sessionId 不合法時回傳 null（呼叫端不寫檔並記 debug log）。 */
export function contextUsagePath(mainPath: string, sessionId: string): string | null {
  if (!SESSION_ID_PATTERN.test(sessionId)) return null
  return `${mainPath}/${CONTEXT_USAGE_DIR}/${sessionId}.json`
}

/**
 * 組一筆用量記錄：缺席的量測一律為 null；compactPercent 只在 tokens 與 compaction window 都有時計算。
 * phase 是恢復開工通知的輔管道（resumeNotice.ts 的 resumePhaseOf），每次寫檔都帶上，未給為 null。
 */
export function contextUsageRecord(input: {
  sessionId: string
  context: ContextFill
  compaction: CompactionWindow | null
  phase?: ResumePhase | null
  measuredAt: number
}): ContextUsageRecord {
  const { sessionId, context, compaction, measuredAt } = input
  const tokens = context.tokens ?? null
  const compactWindow = compaction?.rawMaxTokens ?? null
  return {
    sessionId,
    phase: input.phase ?? null,
    tokens,
    window: context.window,
    percent: context.percent ?? null,
    compactWindow,
    compactPercent: tokens === null || compactWindow === null || compactWindow <= 0 ? null : Math.round((tokens / compactWindow) * 100),
    autoCompactThreshold: compaction?.autoCompactThreshold ?? null,
    measuredAt,
  }
}

/** 用量檔內容：整份 JSON（null 欄位保留，讀者據以區分「量測過但缺席」與「欄位遺失」），結尾換行。 */
export function serializeContextUsage(record: ContextUsageRecord): string {
  return `${JSON.stringify(record)}\n`
}
