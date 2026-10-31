// line-board Pane 的「各 session」區塊。
// 元素由 register.tsx 的 ui.render 以 $.ui.resolve(e) 取得後傳入；解析經 parse.ts 匯出。

import type { ElementConstructor, TextProps } from 'claude-code'

import type { ReadyBoard, SessionState } from '../types'
import type { Elements } from './lanesView'
import { SESSIONS_DIR, boardStateColor, contextUsageSuffix, formatAge, sessionState } from './parse'

/**
 * 存活 session 各一行（依狀態排序）、已結束狀態檔的計數行；讀取失敗時只有一行錯誤。距今時間以 board 的讀取時刻計。
 * 有用量檔的 session 行尾加 `｜ctx <百分比>%（<量測距今>）`（contextJudge.ts），沒有用量檔不加。
 */
export function renderSessions({ Text }: Elements, board: ReadyBoard) {
  const { sessions, readAtMs, usages } = board
  if (sessions.kind === 'error') {
    return <Text color="red">讀取 ~/{SESSIONS_DIR} 失敗（{sessions.message}）</Text>
  }
  const rows = sessions.sessions.map(session => {
    const usage = session.sessionId === null ? null : (usages[session.sessionId] ?? null)
    return renderSession(Text, readAtMs, session, contextUsageSuffix(usage, readAtMs))
  })
  const ended =
    sessions.endedCount === 0 ? [] : [<Text dimColor>另有 {sessions.endedCount} 個狀態檔的 pid 已結束，未列出</Text>]
  if (rows.length === 0) return [<Text dimColor>（本 repo 沒有執行中的 session）</Text>, ...ended]
  return [...rows, ...ended]
}

function renderSession(Text: ElementConstructor<TextProps>, readAtMs: number, session: SessionState, usageSuffix: string | null) {
  const waitingFor = session.waitingFor === null ? '' : `：${session.waitingFor}`
  const usage = usageSuffix === null ? '' : `｜${usageSuffix}`
  const line = `${session.name}｜${session.status}${waitingFor}｜${formatAge(readAtMs, session.statusUpdatedAt)}${usage}`
  // waiting 為要人處理：洋紅粗體；其他狀態不上色
  const state = sessionState(session.status)
  return state === null ? (
    <Text>{line}</Text>
  ) : (
    <Text color={boardStateColor(state)} bold>
      {line}
    </Text>
  )
}
