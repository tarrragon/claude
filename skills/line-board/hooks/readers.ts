// line-board 的讀取：以 $ 讀檔與執行命令，取得一輪 snapshot 所需的各項資料，解析經 parse.ts 匯出。
// 每個讀取函式自行吸收失敗（回傳 error 結果、null 或 unknown，並記 debug log），只影響該項的顯示。
// register.tsx 的 refresh 先讀專案設定（協調票），成立時才依序呼叫本檔其餘函式並組成 snapshot。

import type { EngineInterface } from 'claude-code'

import type {
  ContextUsageRecord,
  DispatchesResult,
  LaneLine,
  LanesResult,
  MergeLogResult,
  ProjectConfigResult,
  SessionState,
  SessionsResult,
  SourceLogEntry,
  TicketStatus,
} from '../types'
import {
  CONTEXT_USAGE_DIR,
  DISPATCH_ACTIVE_PATH,
  MERGE_LOG_PATH,
  contextUsagePath,
  isDeletableUsagePath,
  orphanUsageFiles,
  parseContextUsageDetailed,
  SESSIONS_DIR,
  SOURCE_LOG_PATH,
  UNKNOWN_STATUS,
  isInRepo,
  isSessionProcessAlive,
  mergeGateEntries,
  mergeGateHolders,
  messageOf,
  parseDispatchFile,
  parseLaneLines,
  parseLanes,
  parseProjectConfig,
  parseSessionFile,
  parseSourceLog,
  parseUserTodos,
  parseWorktreePaths,
  ticketStatusOf,
  sessionStatusFileNames,
  sortSessions,
  ticketFileCandidates,
  ticketPrefixOf,
} from './parse'

/** 專案設定檔，相對主 checkout：協調票（coordinationTicket，完整票號）由此提供。 */
export const PROJECT_CONFIG_PATH = '.claude/project-integration/multi-session.json'

/**
 * 讀主 checkout 的專案設定檔，取協調票的完整票號。設定不成立時回傳可區分的原因（見 ProjectConfigResult）並記 debug log；
 * 看板只在 ok 時自動開 Pane 與讀其他各項，沒有使用多 session 協調的專案因此不受影響。
 */
export async function readProjectConfig($: EngineInterface, mainPath: string): Promise<ProjectConfigResult> {
  let text: string
  try {
    text = await $.fs.read(`${mainPath}/${PROJECT_CONFIG_PATH}`)
  } catch (error) {
    $.ui.log(`line-board: 讀取 ${PROJECT_CONFIG_PATH} 失敗：${messageOf(error)}，不讀協調票`, { to: 'debug' })
    return { kind: 'missing', message: messageOf(error) }
  }
  const config = parseProjectConfig(text)
  if (config.kind !== 'ok') $.ui.log(`line-board: ${PROJECT_CONFIG_PATH} 設定不成立（${config.kind}），不讀協調票`, { to: 'debug' })
  return config
}

/** 一張票的票檔讀取結果：ok 為內容；error 為讀不到時的票檔路徑（相對 repo root，不是票號時為票號本身）與原因。 */
type TicketFileRead = { kind: 'ok'; text: string } | { kind: 'error'; path: string; message: string }

/**
 * 依 ticketFileCandidates 的優先序讀主 checkout 的票檔，取第一個讀得到的（與 resolveTicketFile 同序：先 hierarchical、再 flat）；
 * 都讀不到時回傳第一個候選的路徑與錯誤（ticket 系統新建票檔的位置）。
 */
async function readTicketFile($: EngineInterface, mainPath: string, id: string): Promise<TicketFileRead> {
  const candidates = ticketFileCandidates(id)
  const first = candidates[0]
  if (first === undefined) return { kind: 'error', path: id, message: '不是票號' }
  let firstError: unknown = null
  for (const path of candidates) {
    try {
      return { kind: 'ok', text: await $.fs.read(`${mainPath}/${path}`) }
    } catch (error) {
      // 候選路徑不存在是正常情形（先試 hierarchical 再試 flat）；都讀不到時由呼叫端記 debug log
      firstError ??= error
    }
  }
  return { kind: 'error', path: first, message: messageOf(firstError) }
}

/** 合併閘門紀錄顯示的行數（只計開始與結束行）。 */
const MERGE_LOG_LINES = 8

/**
 * 以 `git worktree list --porcelain` 取本 repo 的所有 checkout：第一筆為主 checkout（看板 session 在 worktree 內啟動也指向它），
 * 全部用來判定哪些 session 屬於本 repo。失敗時只有 session root 一筆，並帶原因顯示。
 */
export async function findCheckouts(
  $: EngineInterface,
  root: string,
): Promise<{ checkoutPaths: string[]; checkoutNote: string | null }> {
  try {
    const result = await $.process.run(['git', 'worktree', 'list', '--porcelain'], { cwd: root })
    if (result.exitCode !== 0) {
      const note = `git worktree list 失敗（exit ${result.exitCode}），改讀 session root`
      $.ui.log(`line-board: ${note}: ${result.stderr.trim()}`, { to: 'debug' })
      return { checkoutPaths: [root], checkoutNote: note }
    }
    const paths = parseWorktreePaths(result.stdout)
    if (paths.length === 0) return { checkoutPaths: [root], checkoutNote: 'git worktree list 無輸出，改讀 session root' }
    return { checkoutPaths: paths, checkoutNote: null }
  } catch (error) {
    const note = `git worktree list 無法執行（${messageOf(error)}），改讀 session root`
    $.ui.log(`line-board: ${note}`, { to: 'debug' })
    return { checkoutPaths: [root], checkoutNote: note }
  }
}

/**
 * 讀 `~/.claude/sessions/` 的狀態檔：只讀副檔名 `.json` 的檔案（`.key` 是金鑰，從不讀取），
 * 留下 cwd 屬於本 repo 的 session，再以 `ps -p <pid> -o lstart=` 對 procStart 確認存活；已結束者只計數不列出。
 */
export async function readSessions($: EngineInterface, checkoutPaths: readonly string[]): Promise<SessionsResult> {
  const home = await $.env.get('HOME')
  if (home === undefined || home === '') return { kind: 'error', message: 'HOME 未設定' }
  const dir = `${home}/${SESSIONS_DIR}`
  let names: string[]
  try {
    names = sessionStatusFileNames(await $.fs.list(dir))
  } catch (error) {
    $.ui.log(`line-board: 列出 ${dir} 失敗：${messageOf(error)}`, { to: 'debug' })
    return { kind: 'error', message: messageOf(error) }
  }
  const parsed = await Promise.all(names.map(name => readSessionFile($, `${dir}/${name}`)))
  const inRepo = parsed.filter((session): session is SessionState => session !== null && isInRepo(session.cwd, checkoutPaths))
  const isAlive = await Promise.all(inRepo.map(session => isSessionAlive($, session)))
  const alive = inRepo.filter((_, index) => isAlive[index])
  return { kind: 'ok', sessions: sortSessions(alive), endedCount: inRepo.length - alive.length }
}

/** 讀一個狀態檔；讀不到或格式無效（例如 CC 寫到一半）時回傳 null，下一輪再讀。 */
async function readSessionFile($: EngineInterface, path: string): Promise<SessionState | null> {
  try {
    const session = parseSessionFile(await $.fs.read(path))
    if (session === null) $.ui.log(`line-board: ${path} 格式無法辨識，略過`, { to: 'debug' })
    return session
  } catch (error) {
    $.ui.log(`line-board: 讀取 ${path} 失敗：${messageOf(error)}`, { to: 'debug' })
    return null
  }
}

/**
 * `ps -o lstart` 的執行環境：procStart 是 UTC，ps 須以 UTC 輸出才能逐字比對；
 * LC_ALL=C 固定星期與月份為英文縮寫，不隨使用者 locale 改變。
 */
const PS_ENV: Readonly<Record<string, string>> = { TZ: 'UTC', LC_ALL: 'C' }

/**
 * `ps -p <pid> -o lstart=` exit 0 且啟動時間與 procStart 相同為存活；時間不同表示 pid 已被其他行程重複使用。
 * 無從比對（procStart 缺少、輸出格式不符）時退回只看 exit code；ps 本身無法執行時視為存活，以免整個區塊被清空。
 */
async function isSessionAlive($: EngineInterface, session: SessionState): Promise<boolean> {
  const pid = String(session.pid)
  try {
    const result = await $.process.run(['ps', '-p', pid, '-o', 'lstart='], { env: { ...PS_ENV } })
    const isAlive = isSessionProcessAlive(result.exitCode, result.stdout, session.procStart)
    if (result.exitCode === 0 && !isAlive) {
      $.ui.log(`line-board: pid ${pid} 的啟動時間與 ${session.name} 的 procStart 不符，視為已結束（pid 重複使用）`, {
        to: 'debug',
      })
    }
    return isAlive
  } catch (error) {
    $.ui.log(`line-board: ps -p ${pid} 無法執行（${messageOf(error)}），視為存活`, { to: 'debug' })
    return true
  }
}

/** 讀協調票（專案設定的 coordinationTicket）的現行佇列行（濾掉收線的、原文兩份）與用戶待辦行；票檔路徑由票號推導，讀不到時的訊息含票檔路徑。 */
export async function readLanes($: EngineInterface, mainPath: string, coordinationTicket: string): Promise<LanesResult> {
  const prefix = ticketPrefixOf(coordinationTicket)
  if (prefix === null) {
    // readProjectConfig 已以 ticketPrefixOf 驗過協調票，此分支只在呼叫端繞過設定判定時發生
    $.ui.log(`line-board: 協調票 ${coordinationTicket} 不是完整票號，推不出短票號前綴`, { to: 'debug' })
    return { kind: 'error', message: `${coordinationTicket}：不是完整票號` }
  }
  const file = await readTicketFile($, mainPath, coordinationTicket)
  if (file.kind === 'ok') {
    return { kind: 'ok', lanes: parseLanes(file.text, prefix), lines: parseLaneLines(file.text), todos: parseUserTodos(file.text) }
  }
  $.ui.log(`line-board: 讀取協調票 ${file.path} 失敗：${file.message}`, { to: 'debug' })
  return { kind: 'error', message: `${file.path}：${file.message}` }
}

/** 讀協調票每條線最後一行現行佇列行的原文（含收線的線），供 line_status 判讀；讀不到時的訊息含票檔路徑。 */
export async function readLaneLines(
  $: EngineInterface,
  mainPath: string,
  coordinationTicket: string,
): Promise<{ kind: 'ok'; lines: LaneLine[] } | { kind: 'error'; message: string }> {
  const file = await readTicketFile($, mainPath, coordinationTicket)
  if (file.kind === 'ok') return { kind: 'ok', lines: parseLaneLines(file.text) }
  $.ui.log(`line-board: 讀取協調票 ${file.path} 失敗：${file.message}`, { to: 'debug' })
  return { kind: 'error', message: `${file.path}：${file.message}` }
}

/**
 * 讀各 checkout 的 SessionStart 來源紀錄並合併（worktree 內啟動的 session 寫入該 worktree 的檔）。
 * 某個 checkout 沒有紀錄檔是正常情形（尚未有 session 在其中啟動），只記 debug log；readCount 為讀到的檔數，供輸出註明。
 */
export async function readSourceLog(
  $: EngineInterface,
  checkoutPaths: readonly string[],
): Promise<{ entries: SourceLogEntry[]; readCount: number }> {
  const texts = await Promise.all(
    checkoutPaths.map(async path => {
      try {
        return await $.fs.read(`${path}/${SOURCE_LOG_PATH}`)
      } catch (error) {
        $.ui.log(`line-board: 讀取 ${path}/${SOURCE_LOG_PATH} 失敗：${messageOf(error)}`, { to: 'debug' })
        return null
      }
    }),
  )
  const found = texts.filter((text): text is string => text !== null)
  return { entries: found.flatMap(parseSourceLog), readCount: found.length }
}

/**
 * 讀主 checkout 內票檔的 status 與 title（一次讀檔，路徑由票號推導）；讀不到或無 status 欄時 status 為 unknown，
 * 讀不到或無 title 欄時 title 為 null。
 */
export async function readTicketStatus($: EngineInterface, mainPath: string, id: string): Promise<TicketStatus> {
  const file = await readTicketFile($, mainPath, id)
  if (file.kind === 'ok') return ticketStatusOf(id, file.text)
  $.ui.log(`line-board: 讀取 ${file.path} 失敗：${file.message}`, { to: 'debug' })
  return { id, status: UNKNOWN_STATUS, title: null, waiting: null }
}

/**
 * 讀主 checkout 的派發紀錄：讀不到或格式錯誤（JSON 無效、dispatches 不是陣列）都回傳 error，只影響派發區塊。
 * 不讀各 worktree 的副本：派發紀錄由主 checkout 的 hook 維護，worktree 內的檔案是分支開出當下的舊副本。
 */
export async function readDispatches($: EngineInterface, mainPath: string): Promise<DispatchesResult> {
  try {
    const records = parseDispatchFile(await $.fs.read(`${mainPath}/${DISPATCH_ACTIVE_PATH}`))
    if (records === null) {
      $.ui.log(`line-board: ${DISPATCH_ACTIVE_PATH} 格式無法辨識`, { to: 'debug' })
      return { kind: 'error', message: '格式無法辨識' }
    }
    return { kind: 'ok', records }
  } catch (error) {
    $.ui.log(`line-board: 讀取 ${DISPATCH_ACTIVE_PATH} 失敗：${messageOf(error)}`, { to: 'debug' })
    return { kind: 'error', message: messageOf(error) }
  }
}

export async function readMergeLog($: EngineInterface, mainPath: string): Promise<MergeLogResult> {
  try {
    const entries = mergeGateEntries(await $.fs.read(`${mainPath}/${MERGE_LOG_PATH}`))
    return { kind: 'ok', entries: entries.slice(-MERGE_LOG_LINES), holders: mergeGateHolders(entries) }
  } catch (error) {
    $.ui.log(`line-board: 讀取 ${MERGE_LOG_PATH} 失敗：${messageOf(error)}`, { to: 'debug' })
    return { kind: 'error', message: messageOf(error) }
  }
}

/**
 * 讀存活 session 的 context 用量檔：以 readSessions 的 sessionId 逐一讀 `<id>.json`，不列目錄，所以已結束 session 留下的檔不會被讀到。
 * 讀不到（尚未寫過、plugin 未載入）或格式不符的不列入，回傳以 sessionId 為鍵的記錄。sessions 讀不到時為空。
 */
export async function readContextUsages(
  $: EngineInterface,
  mainPath: string,
  sessions: SessionsResult,
): Promise<Record<string, ContextUsageRecord>> {
  return (await readContextUsageStates($, mainPath, sessions)).usages
}

/**
 * readContextUsages 的完整版：另回傳「用量檔存在但解析不成立」的 sessionId 與原因，供 line_status 寫出原因
 * （看板只取 usages，解析失敗與沒有檔同樣不加字尾）。檔案讀不到仍視為沒有用量檔，不列入 failures。
 */
export async function readContextUsageStates(
  $: EngineInterface,
  mainPath: string,
  sessions: SessionsResult,
): Promise<{ usages: Record<string, ContextUsageRecord>; failures: Record<string, string> }> {
  const usages: Record<string, ContextUsageRecord> = {}
  const failures: Record<string, string> = {}
  if (sessions.kind !== 'ok') return { usages, failures }
  const ids = new Set(sessions.sessions.map(session => session.sessionId).filter((id): id is string => id !== null))
  for (const id of ids) {
    const path = contextUsagePath(mainPath, id)
    if (path === null) continue
    let text: string
    try {
      text = await $.fs.read(path)
    } catch {
      // 用量檔不存在是正常情形（session 尚未回應過、plugin 尚未載入 0.6.0 以上）：不列入，看板該列沒有用量字尾
      continue
    }
    const parsed = parseContextUsageDetailed(text)
    const reason =
      parsed.kind === 'invalid' ? parsed.reason
      : parsed.record.sessionId !== id ? `檔內 sessionId 為 ${parsed.record.sessionId}，與檔名不符`
      : null
    if (parsed.kind === 'ok' && reason === null) {
      usages[id] = parsed.record
      continue
    }
    $.ui.log(`line-board: 用量檔 ${id}.json 不成立（${reason}），略過`, { to: 'debug' })
    failures[id] = reason ?? '不明'
  }
  return { usages, failures }
}

/**
 * 刪除孤兒用量檔：context 目錄下 mtime 超過 24 小時且不屬於存活 session 的檔。每個路徑刪除前再以 isDeletableUsagePath 檢查，
 * 不符就不刪。$.fs 沒有刪除操作，以 `rm -f` 刪除。目錄不存在時直接結束；失敗記 debug，不影響看板。
 */
export async function sweepOrphanUsageFiles(
  $: EngineInterface,
  mainPath: string,
  liveSessionIds: ReadonlySet<string>,
  nowMs: number,
): Promise<void> {
  const dir = `${mainPath}/${CONTEXT_USAGE_DIR}`
  let entries
  try {
    entries = await $.fs.list(dir)
  } catch {
    // 目錄不存在：還沒有任何 session 寫過用量檔，沒有東西要清
    return
  }
  for (const name of orphanUsageFiles(entries, liveSessionIds, nowMs)) {
    await removeUsageFile($, mainPath, `${dir}/${name}`)
  }
}

/** 刪一個用量檔：路徑檢查不通過就不刪並記 debug；rm 失敗記 debug。session.end 刪自己的檔也經此。 */
export async function removeUsageFile($: EngineInterface, mainPath: string, path: string): Promise<void> {
  if (!isDeletableUsagePath(mainPath, path)) {
    $.ui.log(`line-board: 拒絕刪除不在用量檔目錄或檔名不符的路徑：${path}`, { to: 'debug' })
    return
  }
  try {
    const result = await $.process.run(['rm', '-f', path])
    if (result.exitCode !== 0) $.ui.log(`line-board: 刪除用量檔失敗（exit ${result.exitCode}）：${path}`, { to: 'debug' })
  } catch (error) {
    $.ui.log(`line-board: 刪除用量檔失敗：${path}：${messageOf(error)}`, { to: 'debug' })
  }
}
