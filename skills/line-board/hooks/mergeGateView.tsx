// line-board Pane 的「合併閘門最近紀錄」區塊：閘門持有者與最近幾行開始／結束紀錄。
// 元素由 register.tsx 的 ui.render 以 $.ui.resolve(e) 取得後傳入；解析經 parse.ts 匯出。

import type { ElementConstructor, TextProps } from 'claude-code'

import type { MergeGateEntry, ReadyBoard } from '../types'
import type { Elements } from './lanesView'
import { MERGE_LOG_PATH, formatMergeGateEntry, formatMergeGateHolders, mergeGateResultColor } from './parse'

/** 閘門持有者各一行在最上方，其後為最近幾行紀錄；讀取失敗時只有一行錯誤。 */
export function renderMergeLog({ Text }: Elements, board: ReadyBoard) {
  const log = board.mergeLog
  if (log.kind === 'error') return <Text color="red">讀取 {MERGE_LOG_PATH} 失敗（{log.message}）</Text>
  const holders = formatMergeGateHolders(log.holders).map(line => (
    <Text color="yellow" bold wrap="truncate-middle">
      {line}
    </Text>
  ))
  if (log.entries.length === 0) return [...holders, <Text dimColor>（尚無紀錄）</Text>]
  return [...holders, ...log.entries.map(entry => renderMergeGateEntry(Text, entry))]
}

/**
 * 一行閘門紀錄：欄位行以 truncate-middle 截斷，寬度不足時時間與結果兩端都保留；
 * 結束行依結果上色。格式不符的行原樣換行顯示，不截斷。
 */
function renderMergeGateEntry(Text: ElementConstructor<TextProps>, entry: MergeGateEntry) {
  const text = formatMergeGateEntry(entry)
  if (entry.kind === 'raw') return <Text>{text}</Text>
  const color = entry.kind === 'end' ? mergeGateResultColor(entry.result) : undefined
  return (
    <Text color={color} wrap="truncate-middle">
      {text}
    </Text>
  )
}
