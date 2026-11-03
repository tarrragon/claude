// line-board：多線開發看板。
// 主 checkout 的專案設定（.claude/project-integration/multi-session.json）指定協調票；設定成立時 session 啟動即開 Pane，
// 定時讀協調票的現行佇列行（每條線取最後一行）、佇列票的 status、
// 本 repo 各 session 的狀態（~/.claude/sessions/*.json）、派發紀錄（.claude/dispatch-active.json）、
// 合併閘門的開始與結束紀錄，畫在 Pane。設定不成立時不自動開 Pane、不定時讀取，/board 開啟後顯示設定提示。
// 畫面資料與群組的手動展開狀態放 $.state（hot reload 不遺失）；讀檔與命令一律經 $，解析經 parse.ts 匯出（實作分在各 domain 模組）。
// 本檔負責 hook 註冊、定時刷新的協調與 snapshot 組裝；各項的讀取在 readers.ts，Pane 組裝在 boardPane.tsx，各區塊的繪製在 *View.tsx。
// 另以 session.measure 把本 session 的 context 用量寫到主 checkout 的用量檔（usageWriter.ts，記錄內容見 contextUsage.ts），
// 不論專案設定是否成立；恢復開工通知的流程在 resumeFlow.ts。

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { BoardSnapshot, UnsetProjectConfig } from '../types'
import { renderBoardPane } from './boardPane'
import { lineStatusText } from './lineStatus'
import { dispatchTicketIds, formatTime, isContextChanged, laneTicketIds, messageOf, ticketPrefixOf } from './parse'
import {
  findCheckouts,
  readDispatches,
  readLanes,
  readMergeLog,
  readProjectConfig,
  readSessions,
  readTicketStatus,
} from './readers'
import { applyResumeEvent, currentResumePhase, notifyResumed } from './resumeFlow'
import { readContextUsages, sweepOrphanUsageFiles } from './usageReaders'
import { removeOwnUsageFile, writeContextUsage, writePhase } from './usageWriter'

const PANE = 'line-board'
const PANE_TITLE = '多線看板'
/** 模型可呼叫的接續狀態工具：短名與完整名（mcp__<plugin>__<name>）。 */
const LINE_STATUS_TOOL = 'line_status'
const LINE_STATUS_TOOL_FULL = `mcp__line-board__${LINE_STATUS_TOOL}`
/** 工具說明（模型讀的）：用途、何時呼叫、輸出內容。 */
const LINE_STATUS_DESCRIPTION =
  '多 session 協調：回報協調票上每條線的接續狀態（已收線、/clear 後繼續、/compact 後繼續、新 session 接手、無人持有、來源不明）與判讀依據，並列出過期項（收線寫法不合規、名稱不在存活 session 中但仍有佇列、佇列的票全部 completed 但還沒收線）。主控在 /clear 或 /compact 後自我接續、每輪佇列更新前呼叫。唯讀，不需參數。'
/** 更新間隔：30 秒。 */
const REFRESH_MS = 30_000

/** 畫面資料：刷新寫入，Pane（boardPane.tsx）讀出繪製。 */
const snapshot = atom({ plugin: 'line-board', key: 'snapshot' } as const, { kind: 'loading' } as BoardSnapshot)

/** 讀取中旗標：避免上一輪尚未結束時重疊讀取。屬執行期控制，非畫面資料，reload 時歸零即可。 */
let isRefreshing = false
/** 定時讀取已啟動：設定成立的 session 啟動時或第一次執行 /board 時啟動一次。屬執行期控制，同 isRefreshing。 */
let isTimerStarted = false
/** 孤兒用量檔的掃描間隔：每小時一次（refresh 每 30 秒，不每輪掃）。 */
const ORPHAN_SWEEP_MS = 60 * 60 * 1000
/** 上次掃孤兒用量檔的時間（毫秒）；0 表示本行程尚未掃過，第一輪 refresh 就掃。 */
let lastOrphanSweepAt = 0

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'board',
      description: '開啟多線看板（協調票各線現行佇列、佇列票即時狀態、派發中代理人、各 session 狀態、合併閘門紀錄）',
    })
    // 工具註冊失敗不影響看板與 session 啟動；送 transcript 使使用者可見（否則與「工具不存在」同形）
    await $.tool
      .register({
        name: LINE_STATUS_TOOL,
        description: LINE_STATUS_DESCRIPTION,
      })
      .catch(error => $.ui.log(`line-board 警告：註冊 ${LINE_STATUS_TOOL} 失敗：${messageOf(error)}`, { to: 'transcript' }))
    void openIfConfigured($)

    return next(e)
  })

  // 只觀察：context 用量變動時寫本 session 的用量檔；失敗不影響量測結果的傳遞
  on('session.measure', async ($, e, next) => {
    if (isContextChanged(e.changed)) await writeContextUsage($, e.context, currentResumePhase)
    return next(e)
  })

  // 恢復開工通知：compact 在 next 回來後才知道是否真的壓縮了（skip 為否決）
  on('session.compact', async ($, e, next) => {
    const result = await next(e)
    const at = await $.clock.now()
    applyResumeEvent({ kind: 'compact', trigger: e.trigger, agentId: e.agentId, isSkipped: result.skip !== undefined, at })
    void writePhase($, currentResumePhase)
    return result
  })

  // /clear 是舊 session 的結束：只更新模組層狀態，不做 I/O（session.end 共用一個很短的時限）
  on('session.end', async ($, e, next) => {
    applyResumeEvent({ kind: 'end', reason: e.reason, at: await $.clock.now() })
    // 刪自己的用量檔（任何 reason；/clear 刪的是舊 id 的檔，新 id 之後重寫）。主 checkout 只用快取，不在時限內跑 git
    await removeOwnUsageFile($, e.sessionId)
    return next(e)
  })

  // 第一個 prompt 視為恢復開工；通知不阻擋 prompt 進入
  on('prompt.submit', async ($, e, next) => {
    const resumed = applyResumeEvent({ kind: 'submit', command: e.command?.name, at: await $.clock.now() })
    if (resumed !== null) void notifyResumed($, resumed)
    return next(e)
  })

  // 讀取失敗時回傳說明文字（不 deny）：模型要讀得到「為何判不出」，否則與工具壞掉同形
  on('tool.call', { tool: LINE_STATUS_TOOL_FULL }, async $ => {
    try {
      return { result: await lineStatusText($, formatTime(new Date(await $.clock.now()))) }
    } catch (error) {
      $.ui.log(`line-board 警告：${LINE_STATUS_TOOL} 判讀失敗：${messageOf(error)}`, { to: 'debug' })
      return { result: `line_status 判讀失敗：${messageOf(error)}` }
    }
  })

  on('command.run', { command: 'board' }, async $ => {
    startTimer($)
    await $.ui.open({ id: PANE, title: PANE_TITLE })
    void refresh($)

    return { text: '多線看板已開啟。' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    return renderBoardPane($, { Box, Text, Button }, await read($, snapshot))
  })
}

/** 啟動定時讀取（只啟動一次）。 */
function startTimer($: EngineInterface): void {
  if (isTimerStarted) return
  isTimerStarted = true
  $.clock.every(REFRESH_MS, () => refresh($))
}

/**
 * session 啟動時：專案設定成立才啟動定時讀取並開 Pane；不成立時只把設定提示寫入 $.state（/board 開啟後顯示），
 * 不定時讀取。先讀 session root 的設定，成立即開 Pane，不等 git（主 checkout 的 session 不需找主 checkout）；
 * root 讀不到才以 git worktree list 找主 checkout 再讀（worktree 內的 session）。
 * 失敗送 transcript（使用者可見，否則 Pane 沒開與無設定在畫面上同形），不影響 session 啟動。
 */
async function openIfConfigured($: EngineInterface): Promise<void> {
  try {
    const root = await $.session.root()
    const rootConfig = await readProjectConfig($, root)
    if (rootConfig.kind === 'ok') {
      await openConfiguredPane($)
      return
    }
    const { checkoutPaths } = await findCheckouts($, root)
    const mainPath = checkoutPaths[0] ?? root
    const config = mainPath === root ? rootConfig : await readProjectConfig($, mainPath)
    if (config.kind !== 'ok') {
      await update($, snapshot, () => unconfiguredSnapshot(config))
      return
    }
    await openConfiguredPane($)
  } catch (error) {
    $.ui.log(`line-board 啟動檢查失敗：${messageOf(error)}`, { to: 'transcript' })
  }
}

/** 設定成立：啟動定時讀取、開 Pane，並讀第一輪資料。先發出開 Pane 再讀，Pane 不等第一輪讀取；開 Pane 失敗由呼叫端 catch。 */
async function openConfiguredPane($: EngineInterface): Promise<void> {
  startTimer($)
  const opening = $.ui.open({ id: PANE, title: PANE_TITLE })
  void refresh($)
  await opening
}

/** 協調票不成立時的 snapshot：0 張、多張或解析失敗的原因。 */
function unconfiguredSnapshot(config: UnsetProjectConfig): BoardSnapshot {
  return { kind: 'unconfigured', config }
}

/**
 * 讀一輪資料並寫入 $.state：先讀專案設定，不成立時只寫設定提示；成立時讀其他各項，
 * 任何一項失敗只影響該項的顯示（各讀取函式自行吸收失敗，見 readers.ts）。
 */
async function refresh($: EngineInterface): Promise<void> {
  if (isRefreshing) return
  isRefreshing = true
  try {
    const readAtMs = await $.clock.now()
    const root = await $.session.root()
    const { checkoutPaths, checkoutNote } = await findCheckouts($, root)
    const mainPath = checkoutPaths[0] ?? root
    const config = await readProjectConfig($, mainPath)
    if (config.kind !== 'ok') {
      await update($, snapshot, () => unconfiguredSnapshot(config))
      return
    }
    const lanes = await readLanes($, mainPath, config.coordinationTicket)
    const dispatches = await readDispatches($, mainPath)
    const laneIds = lanes.kind === 'ok' ? laneTicketIds(lanes.lanes) : []
    const dispatchIds = dispatches.kind === 'ok' ? dispatchTicketIds(dispatches.records) : []
    const ids = [...laneIds, ...dispatchIds.filter(id => !laneIds.includes(id))]
    const tickets = await Promise.all(ids.map(id => readTicketStatus($, mainPath, id)))
    const sessions = await readSessions($, checkoutPaths)
    const usages = await readContextUsages($, mainPath, sessions)
    if (sessions.kind === 'ok' && readAtMs - lastOrphanSweepAt >= ORPHAN_SWEEP_MS) {
      lastOrphanSweepAt = readAtMs
      const liveIds = new Set(sessions.sessions.map(session => session.sessionId).filter((id): id is string => id !== null))
      void sweepOrphanUsageFiles($, mainPath, liveIds, readAtMs)
    }
    const mergeLog = await readMergeLog($, mainPath)
    const next: BoardSnapshot = {
      kind: 'ready',
      updatedAt: formatTime(new Date(readAtMs)),
      readAtMs,
      mainPath,
      checkoutNote,
      // readProjectConfig 已確認協調票推導得出前綴，?? 只為型別收窄；空字串表示不去前綴
      ticketPrefix: ticketPrefixOf(config.coordinationTicket) ?? '',
      lanes,
      tickets,
      sessions,
      usages,
      mergeLog,
      dispatches,
    }
    await update($, snapshot, () => next)
  } catch (error) {
    $.ui.log(`line-board refresh 失敗：${messageOf(error)}`, { to: 'debug' })
  } finally {
    isRefreshing = false
  }
}
