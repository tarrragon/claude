// 狀態配色：依「輪到誰處理」把佇列票、派發列與 session 歸成五種狀態，各狀態一色（用戶 UI 裁定，2026-10-20）。
// 不碰 $（無檔案、無行程），讓 *.test.ts 能直接驗證；各 *View.tsx 經 parse.ts 取用後設在 Text 的 color。

import type { DispatchStage } from '../types'

/**
 * 看板的五種狀態：待辦（pending，還沒開始）、進行中（in_progress 但沒有派發中的代理人，等子票或 PM 收尾）、
 * 代理人執行中（實作、審查、事故分析）、閘門（合併閘門中）、要人處理（派發階段為收尾，或 session 為 waiting）。
 */
export type BoardState = '待辦' | '進行中' | '代理人執行中' | '閘門' | '要人處理'

/**
 * 各狀態的顏色。進行中取綠：其餘四色與線群組標題列的藍、錯誤提示的紅都已占用，
 * 剩下的 ANSI 基本色中白與預設文字色無從分辨、黑在深色終端機上看不見。
 */
const BOARD_STATE_COLORS: Readonly<Record<string, string>> = {
  待辦: 'gray',
  進行中: 'green',
  代理人執行中: 'cyan',
  閘門: 'yellow',
  要人處理: 'magenta',
}

/** 狀態的顏色；不屬五種狀態的值與 null 不上色（回傳 undefined）。 */
export function boardStateColor(state: string | null): string | undefined {
  return state === null ? undefined : BOARD_STATE_COLORS[state]
}

/** 派發列的狀態：實作、審查、事故分析為代理人執行中，閘門為閘門，收尾為要人處理。 */
export function dispatchStageState(stage: DispatchStage): BoardState {
  if (stage === '閘門') return '閘門'
  return stage === '收尾' ? '要人處理' : '代理人執行中'
}

/**
 * 佇列票的狀態。stages 為所有群組中該票的派發列階段；閘門票列（同群組）以閘門計入。
 * 有派發列時依階段，同一張票有多個階段時依序取閘門、要人處理、代理人執行中；
 * 沒有時依票的 status：pending 為待辦、in_progress 為進行中，其他值（含讀不到、unknown）回傳 null。
 */
export function queueTicketState(status: string | undefined, stages: readonly DispatchStage[]): BoardState | null {
  const states = stages.map(dispatchStageState)
  for (const state of ['閘門', '要人處理', '代理人執行中'] as const) if (states.includes(state)) return state
  if (status === 'in_progress') return '進行中'
  return status === 'pending' ? '待辦' : null
}

/** session 的狀態：waiting（停下來等用戶）為要人處理，其他 status 回傳 null。 */
export function sessionState(status: string): BoardState | null {
  return status === 'waiting' ? '要人處理' : null
}
