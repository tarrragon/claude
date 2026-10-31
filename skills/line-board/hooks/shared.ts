// 各 domain 共用的小工具：票號前綴與票檔位置、專案設定檔內容的判定、票狀態常數、票檔 frontmatter 的狀態與 title 解析、checkout 路徑判定、距今時間的顯示、例外的訊息文字。
// 不碰 $（無檔案、無行程），讓 *.test.ts 能直接驗證；讀檔與執行命令由 readers.ts 負責。

import type { ProjectConfigResult } from '../types'

/** 票號拆成版本與 wave 之後的部分：`<版本>-W<wave>-<序號>`，序號可帶任意層 `.n` 子序號。版本只要求不為空，major.minor 的解析交給呼叫端。 */
const TICKET_ID = /^(.+?)-(W\d+-)\d+(?:\.\d+)*$/

/** 票目錄的根，相對 repo root；與 ticket_system/lib/paths.py 的 WORK_LOGS_DIR 一致。 */
const WORK_LOGS_DIR = 'docs/work-logs'

/**
 * 票號對應的票檔路徑候選（相對 repo root），依優先序排列，對齊 paths.py get_tickets_dir_under_root：
 * 版本可解析 major.minor 時為 hierarchical `v{major}/v{major}.{minor}/v{version}/tickets/` 再 flat `v{version}/tickets/`，
 * 否則只有 flat；不是票號時為空陣列。版本前的 `v` 去掉後再加回。
 */
export function ticketFileCandidates(ticketId: string): string[] {
  const match = TICKET_ID.exec(ticketId)
  if (match === null) return []
  const version = (match[1] ?? '').replace(/^v+/, '')
  const file = `v${version}/tickets/${ticketId}.md`
  const flat = `${WORK_LOGS_DIR}/${file}`
  const [major, minor] = version.split('.')
  if (minor === undefined) return [flat]
  return [`${WORK_LOGS_DIR}/v${major}/v${major}.${minor}/${file}`, flat]
}

/**
 * 票號對應的票檔路徑：取第一個 exists 判定存在的候選，皆不存在時取第一個候選（paths.py 新版本一律 hierarchical）；
 * 不是票號時為 null。檔案存在性由呼叫端以 exists 注入，本函式不碰檔案系統。
 */
export function resolveTicketFile(ticketId: string, exists: (path: string) => boolean): string | null {
  const candidates = ticketFileCandidates(ticketId)
  return candidates.find(exists) ?? candidates[0] ?? null
}

/** 協調票 ID 去掉序號（含子序號）得短票號前綴，如 `1.2.0-W3-045` 得 `1.2.0-W3-`；不是票號時為 null。 */
export function ticketPrefixOf(coordinatorId: string): string | null {
  const match = TICKET_ID.exec(coordinatorId)
  return match === null ? null : `${match[1]}-${match[2]}`
}

/**
 * 專案設定檔內容的判定：須為 JSON 物件，coordinationTicket 為可推導出短票號前綴的完整票號（ticketPrefixOf）。
 * 只判定已讀到的文字；讀不到檔案（missing）由 readers.ts readProjectConfig 判定。
 */
export function parseProjectConfig(text: string): ProjectConfigResult {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch (error) {
    return { kind: 'invalid-json', message: messageOf(error) }
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed) || !('coordinationTicket' in parsed)) {
    return { kind: 'missing-field' }
  }
  const value: unknown = parsed.coordinationTicket
  if (typeof value !== 'string' || ticketPrefixOf(value) === null) return { kind: 'invalid-format', value }
  return { kind: 'ok', coordinationTicket: value }
}

/** 票檔讀不到或沒有 status 欄時顯示的狀態。 */
export const UNKNOWN_STATUS = 'unknown'

/** 票已完成的 status 值：派發條目不列（dispatch.ts）、不算排隊票（layout.ts）皆以此判定。 */
export const COMPLETED_STATUS = 'completed'

/** 票檔 frontmatter（檔首第一個 `---` 區塊）的各行，不含前後的 `---`；檔首不是 `---` 時為空陣列。 */
function frontmatterLines(text: string): string[] {
  const lines = text.split('\n')
  if (lines[0]?.trim() !== '---') return []
  const rest = lines.slice(1)
  const end = rest.findIndex(line => line.trim() === '---')
  return end === -1 ? rest : rest.slice(0, end)
}

/** 讀票檔 frontmatter 的 `status:` 值；沒有 frontmatter 或沒有該欄時回傳 null。 */
export function parseFrontmatterStatus(text: string): string | null {
  for (const line of frontmatterLines(text)) {
    const match = /^status:\s*['"]?([\w-]+)['"]?\s*$/.exec(line)
    if (match !== null) return match[1] ?? null
  }
  return null
}

/**
 * 讀票檔 frontmatter 的 `title:` 值（單行）：單引號包住時去掉引號、`''` 還原為 `'`，雙引號包住時去掉引號、`\"` 還原為 `"`；
 * 沒有 frontmatter、沒有該欄或值為空時回傳 null。票檔的 title 由 ticket CLI 寫成單行（實測 0.5.0 票檔無多行 title）。
 */
export function parseFrontmatterTitle(text: string): string | null {
  for (const line of frontmatterLines(text)) {
    const match = /^title:\s*(.*?)\s*$/.exec(line)
    if (match !== null) return unquoteYamlScalar(match[1] ?? '') || null
  }
  return null
}

/** 單行 YAML 純量去引號：只處理整個值被同一種引號包住的情形，其他原樣回傳。 */
function unquoteYamlScalar(value: string): string {
  if (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) return value.slice(1, -1).replaceAll("''", "'")
  if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) return value.slice(1, -1).replaceAll('\\"', '"')
  return value
}

/**
 * 從 `git worktree list --porcelain` 取所有 checkout 路徑：第一筆為主 checkout，其後各 worktree；空輸出回傳空陣列。
 * 票狀態只讀主 checkout：ticket CLI 在 linked worktree 執行時也把票務寫回主 repo，
 * worktree 內的票檔是分支開出當下的舊副本，讀它會顯示過時的狀態。全部路徑用來判定 session 是否屬於本 repo。
 */
export function parseWorktreePaths(porcelain: string): string[] {
  return porcelain
    .split('\n')
    .filter(line => line.startsWith('worktree '))
    .map(line => line.slice('worktree '.length).trim())
}

/** 距上次更新的時間：未滿 1 分鐘以秒計，其後依序以分、小時、天計；未來時間視為 0 秒；缺少時間為「時間不明」。 */
export function formatAge(nowMs: number, thenMs: number | null): string {
  if (thenMs === null) return '時間不明'
  const seconds = Math.max(0, Math.floor((nowMs - thenMs) / 1000))
  if (seconds < 60) return `${seconds} 秒前`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小時前`
  return `${Math.floor(hours / 24)} 天前`
}

/** 例外的訊息文字：Error 取 message，其他值轉字串。readers.ts 的讀取失敗日誌與 register.tsx 的刷新、切換失敗日誌都用它。 */
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
