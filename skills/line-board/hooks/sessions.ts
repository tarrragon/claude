// 各 session：`~/.claude/sessions/` 狀態檔篩選與解析、pid 存活比對（含 pid 重複使用的辨識）、本 repo 判定、
// 排序，以及線列 session 名稱旁的狀態。
// 不碰 $（無檔案、無行程），讓 *.test.ts 能直接驗證；讀檔與執行命令由 readers.ts 負責。

import type { SessionState } from '../types'

/** 各 session 狀態檔所在目錄，相對家目錄。 */
export const SESSIONS_DIR = '.claude/sessions'

/** 狀態檔副檔名；同目錄的 `.key` 是金鑰，一律不讀。 */
const SESSION_FILE_SUFFIX = '.json'

/**
 * 「各 session」區塊的排序組：在等用戶的排最前；`shell`（session 正在執行 shell 命令，實測 2.1.303）屬執行中，與 busy 同組。
 * 不在此表的 status 排在最後；顯示一律保留原值。
 */
const SESSION_STATUS_RANK: Readonly<Record<string, number>> = { waiting: 0, busy: 1, shell: 1, idle: 2 }

/** 未列入排序組的 status 的組別：排在所有已知組之後。 */
const UNKNOWN_STATUS_RANK = 3

/**
 * `ps -o lstart=` 與狀態檔 procStart 的格式（正規化後）：`Mon Oct 19 09:09:02 2026`。
 * 日期為個位數時 ps 以空白補位（`Oct  5`），正規化會把連續空白壓成一個。
 */
const PROC_START_FORMAT = /^[A-Z][a-z]{2} [A-Z][a-z]{2} \d{1,2} \d{2}:\d{2}:\d{2} \d{4}$/

/** 線列的 session 名稱比對不到存活的 session 時顯示的狀態。 */
export const SESSION_OFFLINE = '離線'

/**
 * `~/.claude/sessions/` 中可讀的狀態檔名：只取副檔名為 `.json` 的一般檔案。
 * 同目錄的 `<pid>.<hash>.key` 是金鑰，不在回傳之列，呼叫端也就不會讀到它。
 */
export function sessionStatusFileNames(entries: readonly { name: string; kind: string }[]): string[] {
  return entries.filter(entry => entry.kind === 'file' && entry.name.endsWith(SESSION_FILE_SUFFIX)).map(entry => entry.name)
}

/**
 * 解析一個 session 狀態檔；JSON 無效或缺少 pid／name／cwd／status 時回傳 null。
 * 只取看板要的欄位，其他欄位（如 messagingSocketPath）不保存。
 */
export function parseSessionFile(text: string): SessionState | null {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    // 格式無效的檔案（例如 CC 寫到一半）視為不存在，下一輪重讀即可；呼叫端記 debug 日誌。
    return null
  }
  if (typeof value !== 'object' || value === null) return null
  const record = value as Record<string, unknown>
  const { pid, name, cwd, status, waitingFor, statusUpdatedAt, procStart, sessionId } = record
  if (typeof pid !== 'number' || typeof name !== 'string' || typeof cwd !== 'string' || typeof status !== 'string') {
    return null
  }
  return {
    pid,
    name,
    cwd,
    status,
    waitingFor: typeof waitingFor === 'string' ? waitingFor : null,
    statusUpdatedAt: typeof statusUpdatedAt === 'number' ? statusUpdatedAt : null,
    procStart: typeof procStart === 'string' ? procStart : null,
    sessionId: typeof sessionId === 'string' ? sessionId : null,
  }
}

/** 行程啟動時間字串的正規化：去頭尾空白、連續空白壓成一個；不符 lstart 格式時回傳 null（無從比對）。 */
export function normalizeProcStart(text: string | null): string | null {
  if (text === null) return null
  const normalized = text.trim().replace(/\s+/g, ' ')
  return PROC_START_FORMAT.test(normalized) ? normalized : null
}

/**
 * session 的 pid 是否仍是同一個行程：`ps -p <pid> -o lstart=`（以 TZ=UTC 執行）的結果與狀態檔 procStart 比對。
 * - ps exit 不為 0：pid 已結束
 * - 兩者正規化後相同：存活；不同：pid 已被其他行程重複使用，原 session 已結束
 * - 任一方缺少或格式不符（無從比對）：退回只看 exit code 的判定，視為存活
 * procStart 是 UTC（實測 2026-10-19，CC 2.1.303：與 `TZ=UTC ps -o lstart=` 逐字相同，與本機時區的輸出差 8 小時）。
 */
export function isSessionProcessAlive(exitCode: number, lstart: string, procStart: string | null): boolean {
  if (exitCode !== 0) return false
  const observed = normalizeProcStart(lstart)
  const recorded = normalizeProcStart(procStart)
  if (observed === null || recorded === null) return true
  return observed === recorded
}

/** cwd 是否屬於本 repo：等於任一 checkout 路徑，或位於其下。 */
export function isInRepo(cwd: string, checkoutPaths: readonly string[]): boolean {
  return checkoutPaths.some(path => cwd === path || cwd.startsWith(`${path}/`))
}

/** 依 waiting、busy 與 shell（同組）、idle、其他狀態排序，同組依名稱排序；不改動傳入陣列。 */
export function sortSessions(sessions: readonly SessionState[]): SessionState[] {
  const rank = (status: string) => SESSION_STATUS_RANK[status] ?? UNKNOWN_STATUS_RANK
  return [...sessions].sort((a, b) => rank(a.status) - rank(b.status) || a.name.localeCompare(b.name))
}

/**
 * 依名稱找 session：同名多筆時取 statusUpdatedAt 最新的一筆；找不到回傳 undefined。
 * 傳入的應是已確認 pid 存活的 session。
 */
export function findSessionByName(sessions: readonly SessionState[], name: string): SessionState | undefined {
  return sessions
    .filter(session => session.name === name)
    .sort((a, b) => (b.statusUpdatedAt ?? 0) - (a.statusUpdatedAt ?? 0))[0]
}

/** 線列 session 名稱旁的狀態：存活的同名 session 取其 status（waiting 附 waitingFor），找不到為「離線」。 */
export function laneSessionStatus(sessions: readonly SessionState[], name: string | null): string {
  if (name === null) return ''
  const session = findSessionByName(sessions, name)
  if (session === undefined) return SESSION_OFFLINE
  return session.waitingFor === null ? session.status : `${session.status}：${session.waitingFor}`
}
