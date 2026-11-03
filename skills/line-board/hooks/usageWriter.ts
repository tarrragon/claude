// line-board：本 session 的 context 用量檔寫入端（記錄內容見 contextUsage.ts）。
// register.tsx 的 session.measure、session.compact、session.end 與 resumeFlow.ts 呼叫本檔；phase 由呼叫端傳入取值函式
// （resumeFlow.ts 的 currentResumePhase），在組記錄的當下才取值，與寫入前的各次 await 之後的狀態一致。
// 模組層狀態每個行程一份，plugin 熱重載時歸零後重取。

import type { EngineInterface } from 'claude-code'

import type { ResumePhase } from '../types'
import { contextUsagePath, contextUsageRecord, messageOf, serializeContextUsage } from './parse'
import type { CompactionWindow, ContextFill } from './parse'
import { findCheckouts } from './readers'
import { removeUsageFile } from './usageReaders'

/** 用量檔所在的主 checkout：第一次寫用量檔時以 findCheckouts 取得後沿用（每輪回應都寫，不每次跑 git）。reload 時重取即可。 */
let usageMainPath: string | null = null
/** compaction window 的快取：以模型 window 為鍵，換模型（window 變了）才重量；量測失敗不快取，下次重試。 */
let compactionCache: { window: number; compaction: CompactionWindow | null } | null = null
/** 用量檔寫入失敗已送 transcript：只送第一次（每輪回應都寫，連續失敗不洗版），之後只記 debug。 */
let hasReportedUsageWriteFailure = false

/**
 * 把本 session 的 context 用量寫到主 checkout 的用量檔（看板與 line_status 據以判定待 compact／待 clear）。
 * 不看專案設定：用量檔只在主 checkout 的 hook-logs 下，沒有協調票的專案也無害。
 * 失敗第一次送 transcript（使用者可見，否則與「用量檔沒人寫」同形），之後記 debug，不影響 session。
 */
export async function writeContextUsage($: EngineInterface, context: ContextFill, phaseOf: () => ResumePhase | null): Promise<void> {
  try {
    const sessionId = await $.session.id()
    const path = contextUsagePath(await mainCheckoutForUsage($), sessionId)
    if (path === null) {
      $.ui.log(`line-board: sessionId 含不允許的字元（${sessionId}），不寫用量檔`, { to: 'debug' })
      return
    }
    const compaction = await compactionWindowOf($, context.window)
    const phase = phaseOf()
    const record = contextUsageRecord({ sessionId, context, compaction, phase, measuredAt: await $.clock.now() })
    await $.fs.write(path, serializeContextUsage(record))
  } catch (error) {
    const message = `line-board 警告：寫 context 用量檔失敗：${messageOf(error)}`
    $.ui.log(message, { to: hasReportedUsageWriteFailure ? 'debug' : 'transcript' })
    hasReportedUsageWriteFailure = true
  }
}

/** phase 改變時立即重寫用量檔（不等下一次 measure）；context 取 $.session.usage() 不帶 breakdown，不計費。 */
export async function writePhase($: EngineInterface, phaseOf: () => ResumePhase | null): Promise<void> {
  try {
    await writeContextUsage($, (await $.session.usage()).context, phaseOf)
  } catch (error) {
    $.ui.log(`line-board: 寫入恢復開工 phase 失敗：${messageOf(error)}`, { to: 'debug' })
  }
}

/** 刪本 session 的用量檔（session.end）：主 checkout 只用快取，不在 session.end 的時限內跑 git；尚未寫過用量檔時不動作。 */
export async function removeOwnUsageFile($: EngineInterface, sessionId: string): Promise<void> {
  const path = usageMainPath === null ? null : contextUsagePath(usageMainPath, sessionId)
  if (usageMainPath !== null && path !== null) await removeUsageFile($, usageMainPath, path)
}

/** 用量檔所在的主 checkout：第一次以 findCheckouts 取得後快取（失敗時 findCheckouts 退回 session root）。 */
export async function mainCheckoutForUsage($: EngineInterface): Promise<string> {
  if (usageMainPath !== null) return usageMainPath
  const root = await $.session.root()
  const { checkoutPaths } = await findCheckouts($, root)
  usageMainPath = checkoutPaths[0] ?? root
  return usageMainPath
}

/**
 * compaction window（/context 的 rawMaxTokens 與 auto-compact 門檻）：以 summary breakdown 量測（本機估算，不送 API），
 * 依模型 window 快取。量不到時回傳 null 並記 debug，用量檔的 compact 欄位為 null。
 */
async function compactionWindowOf($: EngineInterface, window: number): Promise<CompactionWindow | null> {
  if (compactionCache !== null && compactionCache.window === window) return compactionCache.compaction
  try {
    const { breakdown } = (await $.session.usage({ breakdown: 'summary' })).context
    const compaction = breakdown === undefined ? null : { rawMaxTokens: breakdown.rawMaxTokens, autoCompactThreshold: breakdown.autoCompactThreshold }
    compactionCache = { window, compaction }
    return compaction
  } catch (error) {
    $.ui.log(`line-board: 量測 compaction window 失敗：${messageOf(error)}，用量檔的 compact 欄位為 null`, { to: 'debug' })
    return null
  }
}
