// Pane 端到端測試共用的 harness：以 test 端 hook 代替 engine 的 repo stub、啟動看板並掛上 Pane、一組 session 狀態檔，
// 以及從畫出的描述樹取文字的輔助函式（titleOf、textsOf 等）。
// 由 6 個 Pane 測試檔（board*.test.ts）匯入；本檔不是測試檔，不含任何 test。

import type { On } from 'claude-code'
import { mock } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'

import { sessionJson } from './fixtures'
import { groupTitleKey } from '../hooks/lanesView'
import { groupToggleKey } from '../hooks/layout'
import { COORDINATION_CLI_PATH } from '../hooks/readers'
import { SESSIONS_DIR } from '../hooks/sessions'
import { ticketFileCandidates } from '../hooks/shared'

/** 家目錄與 session 狀態檔目錄（測試用的固定值）。 */
export const HOME = '/home/u'
export const SESSIONS = `${HOME}/${SESSIONS_DIR}`
/** 讀取當下的時間：2026-10-19 08:00:00 UTC（epoch 毫秒）。 */
export const NOW_MS = Date.UTC(2026, 9, 19, 8, 0, 0)

/**
 * Pane 端到端測試的逐測逾時（毫秒），6 個 Pane 測試檔（board*.test.ts）的每個 test 都以 `{ timeoutMs }` 傳入。
 *
 * 依據（2026-11-04 加壓取樣，N=30）：`claude plugin test` 預設 5000 ms 是隱含的計時門檻，Pane 測試的斷言本身不計時，
 * 但 pass／fail 取決於單測耗時是否在門檻內。load1 約 119 時單測最大 5157 ms，逾時重現；程式碼不變、只改負載
 * 就翻轉結果，屬 test-assertion-design-rules D1 的「機器負載」類不可靠斷言。取 15000 ms，約為該最大值的 3 倍。
 * 代價：真實的效能退化要到約 3 倍才會以逾時呈現；效能不由本門檻把關。
 * 餘裕會隨看板成長縮小（2026-11-04 量測）：非首測的單測耗時有 72–77% 是每個 test 一次的 plugin 冷啟動，冷啟動隨原始碼量成長，
 * 多引入約 215 KB 原始碼時非首測冷啟動多 77%。
 * 看板原始碼量明顯成長時（例如新增一個 domain 模組群），依同樣的加壓取樣方法重新量測單測最大耗時，確認本值仍有約 3 倍餘裕。
 */
export const PANE_TEST_TIMEOUT_MS = 15000

/** 預設的協調票：fixtures 的佇列票檔與 lanes.ts 的票檔路徑皆以它為準。 */
export const COORDINATION_TICKET = '0.5.0-W1-349'
/** 預設協調票的票檔（相對 repo root）：由票號推導，取 ticketFileCandidates 的第一個候選（hierarchical）。 */
export const COORDINATION_TICKET_FILE = ticketFileCandidates(COORDINATION_TICKET)[0] ?? ''
/** 與預設協調票同版本的票檔所在目錄（相對 repo root）。 */
export const TICKET_FOLDER = COORDINATION_TICKET_FILE.slice(0, COORDINATION_TICKET_FILE.lastIndexOf('/'))

/** 協調票解析 CLI --json 的輸出（欄位與 coordination_ticket.py 的 _result 一致）。 */
const cliResult = (kind: string, fields: Record<string, unknown>): string =>
  JSON.stringify({ kind, ticket: null, path: null, source: null, warnings: [], candidates: [], reason: null, ...fields })
/** CLI 解析出一張協調票。 */
export const cliOk = (ticket: string, warnings: string[] = []): string => cliResult('ok', { ticket, source: 'auto', warnings })
/** CLI 找不到協調票（0 張）。 */
export const cliNone = (): string => cliResult('none', {})
/** CLI 找到多張協調票。 */
export const cliMultiple = (tickets: string[]): string =>
  cliResult('multiple', { candidates: tickets.map(ticket => ({ ticket, path: `/x/${ticket}.md` })) })
/** CLI 自己回報 error（結束碼 1，stdout 仍是 JSON）。 */
export const cliError = (reason: string): string => cliResult('error', { reason })

/** 解析 CLI 的非常規回應：exit 與輸出照給，或呼叫本身拒絕（python3 不存在等）。 */
export type CliFailure = { exitCode: number; stdout: string; stderr: string } | { throws: string }

export type Stub = {
  files: Record<string, string>
  /** 主 checkout `/repo` 的協調票解析 CLI stdout；未給時為以 COORDINATION_TICKET 為協調票的 ok，null 表示 0 張。session root `/wt` 一律 0 張。 */
  projectConfig?: string | null
  /** 給定時取代解析 CLI 的回應（CLI 不可用等情形）。 */
  cliFailure?: CliFailure
  /** `~/.claude/sessions/` 內的檔名；undefined 表示該目錄無法列出。 */
  sessionEntries?: string[]
  /** `ps -p` 回報已結束的 pid。 */
  deadPids?: number[]
  /** `ps -p <pid> -o lstart=` 對各 pid 的輸出；未列者輸出為空（看板退回只看 exit code）。 */
  lstart?: Record<number, string>
  /** session root；未給時為 worktree `/wt`，`/repo` 表示 session 在主 checkout 啟動。 */
  sessionRoot?: string
  /** 給定時 session.root 以此訊息拒絕（啟動檢查丟例外）。 */
  rootError?: string
}

/**
 * 以 test 端 hook 代替 engine：看板 session 預設在 worktree `/wt` 內啟動（session root 為 `/wt`，stub.sessionRoot 可改為 `/repo`），
 * git 列出主 checkout `/repo` 與 `/wt`。$ 呼叫的 hook 回 `{ value }` 或 `{ deny }`（deny 即 reject，代表檔案不存在）。
 * 專案設定檔只在 `/repo` 內，依 stub.projectConfig 提供（見 Stub）。
 * 回傳 fs.read 被呼叫過的所有路徑（供斷言 `.key` 從未被讀取）、ps 的呼叫、ui.open 開過的 Pane id、註冊的指令名稱、
 * ui.log 寫出的行，以及 git 與 ui.open 的呼叫序（`git <引數>`、`ui.open <id>`，供斷言開 Pane 是否先於 git）。
 */
function stubRepo(on: On, stub: Stub) {
  const readPaths: string[] = []
  const psCalls: { argv: readonly string[]; env: unknown }[] = []
  const opened: string[] = []
  const registered: string[] = []
  const logs: { text: string; to: string }[] = []
  const callOrder: string[] = []
  const cliCwds: string[] = []
  const coordinationStdout = (cwd: string | undefined): string => {
    if (cwd !== '/repo' || stub.projectConfig === null) return cliNone()
    return stub.projectConfig ?? cliOk(COORDINATION_TICKET)
  }
  mock.env(on, { HOME })
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('session.root', () => (stub.rootError === undefined ? { value: stub.sessionRoot ?? '/wt' } : { deny: stub.rootError }))
  on('process.run', (_$, e) => {
    if (e.argv[1] === COORDINATION_CLI_PATH) {
      cliCwds.push(e.init?.cwd ?? '')
      if (stub.cliFailure !== undefined) {
        if ('throws' in stub.cliFailure) return { deny: stub.cliFailure.throws }
        return { value: { ...stub.cliFailure, isStdoutTruncated: false, isStderrTruncated: false } }
      }
      const stdout = coordinationStdout(e.init?.cwd)
      return { value: { exitCode: stdout.includes('"kind":"error"') ? 1 : 0, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    }
    const isPs = e.argv[0] === 'ps'
    if (e.argv[0] === 'git') callOrder.push(e.argv.join(' '))
    const pid = Number(e.argv[2])
    if (isPs) psCalls.push({ argv: e.argv, env: e.init?.env })
    const isDead = isPs && (stub.deadPids ?? []).includes(pid)
    return {
      value: {
        exitCode: isDead ? 1 : 0,
        stdout: isPs ? (isDead ? '' : (stub.lstart?.[pid] ?? '')) : 'worktree /repo\nHEAD a\nbranch refs/heads/main\n\nworktree /wt\nHEAD b\nbranch refs/heads/feat\n',
        stderr: '',
        isStdoutTruncated: false,
        isStderrTruncated: false,
      },
    }
  })
  on('fs.list', (_$, e) => {
    if (e.path !== SESSIONS || stub.sessionEntries === undefined) return { deny: `ENOENT: ${e.path}` }
    return { value: stub.sessionEntries.map(name => ({ name, kind: 'file' as const, size: 1, mtimeMs: 0, isLink: false })) }
  })
  on('fs.read', (_$, e) => {
    readPaths.push(e.path)
    const text = stub.files[e.path]
    return text === undefined ? { deny: `ENOENT: ${e.path}` } : { value: text }
  })
  on('command.register', (_$, e) => {
    registered.push(e.name)
    return { value: { command: e.name } }
  })
  on('ui.open', (_$, e) => {
    opened.push(e.id)
    callOrder.push(`ui.open ${e.id}`)
    return { value: { isPlaced: true } }
  })
  on('ui.log', (_$, e) => {
    logs.push({ text: e.text, to: e.to })
    return { value: undefined }
  })
  return { readPaths, psCalls, opened, registered, logs, callOrder, cliCwds }
}

const PANE = {
  component: 'Pane',
  requestId: 'line-board',
  props: {
    title: '多線看板',
    isFocused: false,
    bodyColumns: 100,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 40 },
    view: {},
  },
} as const

/** bodyColumns：面板內容寬（欄），預設 100；停靠在側邊的窄面板以 60 測。 */
export async function startBoard($: Engine, on: On, stub: Stub, bodyColumns: number = PANE.props.bodyColumns) {
  const clock = mock.clock(on, { now: NOW_MS })
  const { readPaths, psCalls, opened, registered, logs, callOrder, cliCwds } = stubRepo(on, stub)
  await $.session.start({ cwd: stub.sessionRoot ?? '/wt', surface: 'terminal', isInteractive: true })
  await clock.advance(1)
  const ui = await $.ui.mount({
    plugin: 'line-board',
    surface: 'terminal',
    ...PANE,
    props: { ...PANE.props, bodyColumns },
  })
  return { ui, readPaths, psCalls, opened, registered, logs, callOrder, cliCwds, clock }
}

/** 掛上的 Pane。 */
export type Ui = Awaited<ReturnType<typeof startBoard>>['ui']

/** 描述節點：子節點在 children 或 props.children；key、color 等在 props。 */
export type Described = { type?: unknown; children?: unknown; props?: { children?: unknown; color?: unknown; bold?: unknown } }

/** 描述節點的子節點；子節點只有一個字串時也包成陣列。 */
export function childrenOf(node: unknown): unknown[] {
  if (typeof node !== 'object' || node === null) return []
  const element = node as Described
  const children = element.children ?? element.props?.children
  if (Array.isArray(children)) return children
  return children === undefined ? [] : [children]
}

/** 一個 Text 的文字：字串子節點與內嵌 Text（佇列列的各票分段）的文字依序相接。 */
export function textOf(node: unknown): string {
  return childrenOf(node)
    .map(child => (typeof child === 'string' ? child : (child as Described).type === 'Text' ? textOf(child) : ''))
    .join('')
}

/** 描述節點內所有 Text 的文字，依文件順序（Text 包在縮排的 Box 內時往下找）；Button 的文字不在其中。 */
export function textsOf(nodes: readonly unknown[]): string[] {
  const texts: string[] = []
  for (const node of nodes) {
    if (typeof node !== 'object' || node === null) continue
    // 標題列（Button）的文字由 headerOf 另取，不在其中
    if ((node as Described).type === 'Text') texts.push(textOf(node))
    else if ((node as Described).type !== 'Button') texts.push(...textsOf(childrenOf(node)))
  }
  return texts
}

/** 群組標題列（Button）的文字；群組未畫出時為 undefined。 */
export async function headerOf(ui: Ui, id: string): Promise<string | undefined> {
  return (await ui.find({ type: 'Button', key: groupToggleKey(id) }))?.text
}

/** 群組標題的各行：標題列（Button），其後依序為標題 Box 內各 Text 的文字（目標、活動計數，缺者不畫）；群組未畫出時為 undefined。 */
export async function titleOf(ui: Ui, id: string): Promise<string[] | undefined> {
  const header = await headerOf(ui, id)
  const title = await ui.find({ type: 'Box', key: groupTitleKey(id) })
  return header === undefined || title === undefined ? undefined : [header, ...textsOf(title.children)]
}

/** 使用者在終端機輸入 `/board`；回傳指令的輸出文字。 */
export async function runBoardCommand($: Engine): Promise<string | undefined> {
  const result = await $.command.run({
    command: 'board',
    args: '',
    origin: { kind: 'composer' },
    presentation: { isFullscreen: true, columns: 120 },
  })
  return result.text
}

/**
 * 一組 session 狀態檔：本 repo 主 checkout 的 waiting／busy／idle／未知狀態、worktree 內的一個、
 * 其他專案的一個、pid 已結束的一個；每個 .json 旁都有 .key（內容故意放 JSON，讀到也能被解析，才分辨得出有沒有被讀）。
 */
const SESSION_FILES: Record<string, Record<string, unknown>> = {
  '101': { pid: 101, name: 'graph-project-docs-manager-f9', cwd: '/repo', status: 'busy', statusUpdatedAt: NOW_MS - 90_000 },
  '102': {
    pid: 102,
    name: 'graph-project-docs-manager-1b',
    cwd: '/repo',
    status: 'waiting',
    waitingFor: 'input needed',
    statusUpdatedAt: NOW_MS - 12_000,
  },
  '103': { pid: 103, name: 'graph-project-docs-manager-d7', cwd: '/repo', status: 'idle', statusUpdatedAt: NOW_MS - 7_200_000 },
  '104': { pid: 104, name: 'graph-project-docs-manager-q1', cwd: '/wt/lib', status: 'compacting', statusUpdatedAt: NOW_MS },
  '105': { pid: 105, name: 'blog-ea', cwd: '/home/u/blog', status: 'waiting', statusUpdatedAt: NOW_MS },
  '106': { pid: 106, name: 'graph-project-docs-manager-3e', cwd: '/repo', status: 'busy', statusUpdatedAt: NOW_MS },
  '107': { pid: 107, name: 'graph-project-docs-manager-a2', cwd: '/repo', status: 'shell', statusUpdatedAt: NOW_MS - 30_000 },
}

/** SESSION_FILES 各狀態檔的 sessionId 為 `sid-<pid>`，派發紀錄的 session_id 以此對應。 */
export const sessionStub = (files: Record<string, string>): Stub => {
  const all = { ...files }
  const entries: string[] = []
  for (const [pid, fields] of Object.entries(SESSION_FILES)) {
    all[`${SESSIONS}/${pid}.json`] = sessionJson({ sessionId: `sid-${pid}`, ...fields })
    all[`${SESSIONS}/${pid}.deadbeef.key`] = sessionJson({ ...fields, name: `KEY-${pid}`, status: 'waiting' })
    entries.push(`${pid}.json`, `${pid}.deadbeef.key`)
  }
  return { files: all, sessionEntries: entries, deadPids: [106] }
}
