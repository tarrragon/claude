// Pane 端到端測試共用的 harness：以 test 端 hook 代替 engine 的 repo stub、啟動看板並掛上 Pane、一組 session 狀態檔。
// 由 board.test.ts 與 boardDispatch.test.ts 匯入；本檔不是測試檔，不含任何 test。

import type { On } from 'claude-code'
import { mock } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'

import { sessionJson } from './fixtures'
import { PROJECT_CONFIG_PATH } from '../hooks/readers'
import { SESSIONS_DIR } from '../hooks/sessions'

/** 家目錄與 session 狀態檔目錄（測試用的固定值）。 */
export const HOME = '/home/u'
export const SESSIONS = `${HOME}/${SESSIONS_DIR}`
/** 讀取當下的時間：2026-10-19 08:00:00 UTC（epoch 毫秒）。 */
export const NOW_MS = Date.UTC(2026, 9, 19, 8, 0, 0)

/** 預設專案設定的協調票：fixtures 的佇列票檔與 lanes.ts 的票檔路徑皆以它為準。 */
export const COORDINATION_TICKET = '0.5.0-W1-349'
/** 主 checkout `/repo` 內的專案設定檔。 */
export const PROJECT_CONFIG = `/repo/${PROJECT_CONFIG_PATH}`
/** 專案設定檔內容：fields 原樣寫成 JSON。 */
export const configJson = (fields: Record<string, unknown>): string => JSON.stringify(fields)

export type Stub = {
  files: Record<string, string>
  /** 專案設定檔的內容；未給時為以 COORDINATION_TICKET 為協調票的有效設定，null 表示設定檔不存在。 */
  projectConfig?: string | null
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
  const fileOf = (path: string): string | undefined => {
    if (path !== PROJECT_CONFIG) return stub.files[path]
    if (stub.projectConfig === null) return undefined
    return stub.projectConfig ?? configJson({ coordinationTicket: COORDINATION_TICKET })
  }
  mock.env(on, { HOME })
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('session.root', () => (stub.rootError === undefined ? { value: stub.sessionRoot ?? '/wt' } : { deny: stub.rootError }))
  on('process.run', (_$, e) => {
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
    const text = fileOf(e.path)
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
  return { readPaths, psCalls, opened, registered, logs, callOrder }
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
  const { readPaths, psCalls, opened, registered, logs, callOrder } = stubRepo(on, stub)
  await $.session.start({ cwd: stub.sessionRoot ?? '/wt', surface: 'terminal', isInteractive: true })
  await clock.advance(1)
  const ui = await $.ui.mount({
    plugin: 'line-board',
    surface: 'terminal',
    ...PANE,
    props: { ...PANE.props, bodyColumns },
  })
  return { ui, readPaths, psCalls, opened, registered, logs, callOrder, clock }
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
