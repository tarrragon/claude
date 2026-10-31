// 合併閘門：worktree-merge.log 的開始／結束行篩選與欄位解析、短分支名、目前持有閘門的分支、顯示文字與結果顏色。
// 不碰 $（無檔案、無行程），讓 *.test.ts 能直接驗證；讀檔與執行命令由 readers.ts 負責。

import type { MergeGateEntry, MergeGateHolder } from '../types'

/** 合併閘門紀錄檔，相對 repo root。 */
export const MERGE_LOG_PATH = '.claude/logs/worktree-merge.log'

/** 合併閘門紀錄中要顯示的行：`[合併閘門] 開始` 與 `[合併閘門] 結束`；預檢、驗收、測試等其他行濾掉。 */
const MERGE_GATE_LINE = /\[合併閘門\] (開始|結束)(｜|$)/

/** 合併閘門紀錄中最後 count 個 `[合併閘門] 開始／結束` 行，保留原順序。 */
export function mergeGateLines(text: string, count: number): string[] {
  return text
    .split('\n')
    .map(line => line.trimEnd())
    .filter(line => MERGE_GATE_LINE.test(line))
    .slice(-count)
}

/**
 * 一行開始／結束的完整格式：`<YYYY-MM-DD>T<HH:MM:SS> [合併閘門] <開始|結束>`，其後為以 `｜` 分隔的欄位
 * （`target main`、`分支 <branch>`、`commit <sha>`，結束行另有 `結果 <result>`）。
 */
const MERGE_GATE_FIELDS = /^\d{4}-\d{2}-\d{2}T(\d{2}:\d{2}:\d{2}) \[合併閘門\] (開始|結束)((?:｜[^｜]*)*)$/

/** 欄位中以 `<label> ` 開頭者的值；沒有該欄或值為空時回傳 null。 */
function gateField(fields: readonly string[], label: string): string | null {
  const field = fields.find(item => item.startsWith(`${label} `))
  const value = field?.slice(label.length + 1).trim()
  return value === undefined || value === '' ? null : value
}

/**
 * 解析一行 `[合併閘門] 開始／結束`：開始行需有分支，結束行需有分支與結果；
 * 時間戳、分支或結果任一缺少時回傳 raw，原樣保留整行，畫面照樣顯示而不丟棄。
 */
export function parseMergeGateLine(line: string): MergeGateEntry {
  const raw: MergeGateEntry = { kind: 'raw', text: line }
  const match = MERGE_GATE_FIELDS.exec(line)
  if (match === null) return raw
  const time = match[1] ?? ''
  const fields = (match[3] ?? '').split('｜').slice(1)
  const branch = gateField(fields, '分支')
  if (branch === null) return raw
  if (match[2] === '開始') return { kind: 'start', time, branch }
  const result = gateField(fields, '結果')
  return result === null ? raw : { kind: 'end', time, branch, result }
}

/** 整份紀錄中所有 `[合併閘門] 開始／結束` 行的解析結果，保留原順序；預檢、驗收、測試等其他行不在其中。 */
export function mergeGateEntries(text: string): MergeGateEntry[] {
  return mergeGateLines(text, Number.POSITIVE_INFINITY).map(parseMergeGateLine)
}

/**
 * 目前持有閘門的所有分支：各分支最後一筆開始行之後沒有同一分支的結束行者，依開始行的順序回傳分支與開始時間；
 * 沒有時回傳空陣列。開始與結束以分支欄配對，不以相鄰行配對：免跑測試的合併不佔 heavy 名額，
 * 可與其他分支的合併重疊，因此持有者可能同時有多個。格式不符的行不參與判定。
 */
export function mergeGateHolders(entries: readonly MergeGateEntry[]): MergeGateHolder[] {
  const open = new Map<string, string>()
  for (const entry of entries) {
    if (entry.kind === 'raw') continue
    // 先刪再設，使同分支重新開始時排到最後，與其最新開始行的位置一致
    open.delete(entry.branch)
    if (entry.kind === 'start') open.set(entry.branch, entry.time)
  }
  return [...open].map(([branch, since]) => ({ branch, since }))
}

/** worktree 代理人分支 `worktree-agent-<id>` 的 id 只顯示前幾碼。 */
const AGENT_ID_PREFIX_LENGTH = 6

/**
 * 分支的短名：`worktree-agent-<id>` 縮成 `agent-<id 前 6 碼>`，`feat/<票號>` 縮成票號，其他分支原樣。
 * 面板停靠在側邊時寬度有限，完整分支名會把結果欄擠出畫面。
 */
export function shortBranch(branch: string): string {
  const agent = /^worktree-agent-(\w+)$/.exec(branch)
  if (agent !== null) return `agent-${(agent[1] ?? '').slice(0, AGENT_ID_PREFIX_LENGTH)}`
  const feature = /^feat\/(.+)$/.exec(branch)
  if (feature !== null) return feature[1] ?? branch
  return branch
}

/** 閘門紀錄一行的顯示文字：`時間｜開始｜短分支` 或 `時間｜結束｜短分支｜結果`；格式不符的行為原文。 */
export function formatMergeGateEntry(entry: MergeGateEntry): string {
  if (entry.kind === 'raw') return entry.text
  const head = `${entry.time}｜${entry.kind === 'start' ? '開始' : '結束'}｜${shortBranch(entry.branch)}`
  return entry.kind === 'start' ? head : `${head}｜${entry.result}`
}

/** 閘門持有者的提示，每個持有者一行：`閘門使用中：<短分支>（自 HH:MM:SS）`；沒有持有者時為空陣列。 */
export function formatMergeGateHolders(holders: readonly MergeGateHolder[]): string[] {
  return holders.map(holder => `閘門使用中：${shortBranch(holder.branch)}（自 ${holder.since}）`)
}

/** 結束行的結果與顏色；結果值取自真實 worktree-merge.log（寫入、中止、拒絕、紅燈）。 */
const MERGE_GATE_RESULT_COLORS: Readonly<Record<string, string>> = {
  寫入: 'green',
  中止: 'yellow',
  拒絕: 'red',
  紅燈: 'red',
}

/** 結束行依結果上色：寫入為綠、中止為黃、拒絕與紅燈為紅；其他結果不上色（回傳 undefined）。 */
export function mergeGateResultColor(result: string): string | undefined {
  return MERGE_GATE_RESULT_COLORS[result]
}
