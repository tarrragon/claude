// line-board 的 context 用量檔讀取與清理：以 $ 讀用量檔、列目錄與刪檔，解析與路徑檢查經 parse.ts 匯出（contextJudge.ts）。
// register.tsx 的 refresh 讀用量與掃孤兒檔、lineStatus.ts 讀用量與解析失敗原因、usageWriter.ts 在 session.end 刪自己的檔。
// 失敗一律吸收並記 debug，不影響看板與 line_status 的其他項。

import type { EngineInterface } from 'claude-code'

import type { ContextUsageRecord, SessionsResult } from '../types'
import { CONTEXT_USAGE_DIR, contextUsagePath, isDeletableUsagePath, messageOf, orphanUsageFiles, parseContextUsageDetailed } from './parse'

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
