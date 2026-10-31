// line-board 的型別契約：$.state 內每個值的形狀（snapshot 與群組展開狀態 expanded），以及 hooks/parse.ts 純函式的輸入輸出。

/** 票序中的一段：ticket 為一張票（短票號、完整票號、其後的註記），sep 為 `→` 或 `∥`，text 為無法辨識為票號的文字。 */
export type QueueToken =
  | { kind: 'ticket'; serial: string; id: string; note: string }
  | { kind: 'sep'; text: '→' | '∥' }
  | { kind: 'text'; text: string }

/** 一條線的現行佇列：線號、session 名稱（行內未寫時為 null）、線目標（協調票沒有目標行或已寫（無）清除時為 null）、票序。 */
export type Lane = { lane: number; session: string | null; goal: string | null; tokens: QueueToken[] }

/** 協調票一條線最後一行現行佇列行的原文：線號、session 名稱（行內未寫時為 null）、票序原文（含收線寫法，未過濾）。 */
export type LaneLine = { lane: number; session: string | null; queue: string }

/** `.claude/hook-logs/session-source-diagnostic/diagnostic.log` 的一筆：時間原文、SessionStart 的 source、sessionId 前 8 碼。 */
export type SourceLogEntry = { time: string; source: string; sessionPrefix: string }

/**
 * 一條線的接續狀態（multi-session-orchestration 的 line-continuity.md §2）：
 * ended 已收線、clear／compact 為該 session 最近一次 SessionStart 的來源、startup 新 session 接手、
 * orphan 佇列行的名稱不在本 repo 存活的 session 中、unknown 來源不明（不猜測）。
 */
export type ContinuityState = 'ended' | 'clear' | 'compact' | 'startup' | 'orphan' | 'unknown'

/** 一條線的判讀結果：evidence 為判讀依據（sessionId 前 8 碼、log 時間與 source，或判不出的原因）。 */
/** context 為 line_status 的用量段（contextJudge.ts laneContextStatus）；已收線、持有者無從查起或未提供用量時缺席。 */
export type LaneContinuity = { lane: number; session: string | null; state: ContinuityState; evidence: string; context?: string }

/**
 * 過期項：ended-with-note 票序以收線記號開頭但後面還有文字（看板不視為收線）、
 * orphan 名稱不在存活 session 中但仍有佇列、all-done 佇列的票全部 completed 但還沒收線。
 */
export type StaleKind = 'ended-with-note' | 'orphan' | 'all-done'

export type StaleItem = { lane: number; kind: StaleKind; detail: string }

/**
 * 等用戶的訊號來源（line-continuity.md §2〈等用戶〉）：S1 票 Solution 段的等用戶標記、
 * S2 該線 session 的 status 為 waiting、S3 現行佇列行的註記或文字含「等用戶」。
 */
export type WaitingSource = 'S1' | 'S2' | 'S3'

/** 一項等用戶：所屬線、session 名稱、相關票號（S2 與佇列行的純文字沒有票號，為 null）、等待的事項、訊號來源。 */
export type WaitingItem = { lane: number; session: string | null; ticketId: string | null; item: string; source: WaitingSource }

/** 協調票的一項用戶待辦（U1）：鍵（待辦行未帶鍵時為 null，此時以事項全文配對完成行）與事項。 */
export type UserTodo = { key: string | null; item: string }

/** 「用戶待辦」群組的一行：顯示文字，與是否為 session 等待中（S2，以要人處理色顯示）。 */
export type UserTodoRow = { text: string; isSessionWaiting: boolean }

/** 恢復開工通知的來源：/compact（含 auto compact）或 /clear。 */
export type ResumeSource = 'compact' | 'clear'

/** 用量檔的 phase：compacted 為已完成 compact／clear 尚未開工、resumed 為已恢復開工；at 為進入該狀態的時間（毫秒）。 */
export type ResumePhase = { kind: 'compacted' | 'resumed'; source: ResumeSource; at: number }

/**
 * 一個 session 的 context 用量檔內容（`.claude/hook-logs/line-board/context/<sessionId>.json`）：
 * tokens／percent 以模型 window 為分母（同狀態列），compactWindow／compactPercent 以 compaction window 為分母；
 * 缺席的量測（compact 後下一次回應前、compaction window 未量到、auto-compact 關閉）為 null，不寫成 0。
 * measuredAt 為 $.clock.now() 的毫秒。
 */
export type ContextUsageRecord = {
  sessionId: string
  /** 恢復開工通知的輔管道（resumeNotice.ts）：最近一次 compact／clear 後的狀態；沒有發生過為 null。 */
  phase: ResumePhase | null
  tokens: number | null
  window: number
  percent: number | null
  compactWindow: number | null
  compactPercent: number | null
  autoCompactThreshold: number | null
  measuredAt: number
}

/** line_status 工具的判讀結果：各線接續狀態（依線號）、過期項、等用戶（與過期項分列，等用戶不代表過期）。 */
export type LineStatusReport = { lanes: LaneContinuity[]; stale: StaleItem[]; waiting: WaitingItem[] }

/**
 * 主 checkout 專案設定檔（.claude/project-integration/multi-session.json）的讀取結果：ok 為協調票的完整票號；
 * 其餘為設定不成立的原因——missing 讀不到檔案、invalid-json JSON 無效、missing-field 不是物件或缺 coordinationTicket、
 * invalid-format 值不是完整票號（value 為原值）。
 */
export type ProjectConfigResult =
  | { kind: 'ok'; coordinationTicket: string }
  | { kind: 'missing'; message: string }
  | { kind: 'invalid-json'; message: string }
  | { kind: 'missing-field' }
  | { kind: 'invalid-format'; value: unknown }

/** 設定不成立的讀取結果。 */
export type UnsetProjectConfig = Exclude<ProjectConfigResult, { kind: 'ok' }>

/** 協調票現行佇列的讀取結果：ok 為解析出的線（可能為空），error 為讀檔失敗原因（含票檔路徑）。 */
export type LanesResult =
  | {
      kind: 'ok'
      /** 未收線的線（parseLanes，收線記號整段相符的線已濾掉）。 */
      lanes: Lane[]
      /** 各線最後一行現行佇列行的原文（parseLaneLines，含收線的線）：判各線等用戶（U2）用。 */
      lines: LaneLine[]
      /** 仍待用戶處理的待辦（U1，parseUserTodos）。 */
      todos: UserTodo[]
    }
  | { kind: 'error'; message: string }

/**
 * 佇列中一張票在主 checkout 的狀態與 title（同一次讀檔解析）；票檔讀不到或沒有 status 欄時 status 為 'unknown'，
 * 讀不到或沒有 title 欄時 title 為 null。title 為選填：hot reload 前的舊 snapshot 沒有此欄（undefined），視同讀不到。
 * waiting 為 Solution 段最後一行等用戶標記的事項（S1）；沒有標記、最後一行是解除行、或讀不到時為 null，選填理由同 title。
 */
export type TicketStatus = { id: string; status: string; title?: string | null; waiting?: string | null }

/**
 * 一行 `[合併閘門] 開始／結束` 的欄位：time 為 `HH:MM:SS`，branch 為完整分支名（顯示時才縮短），
 * result 為結束行的結果（寫入、中止等）；raw 為格式不符、原樣保留的整行。
 */
export type MergeGateEntry =
  | { kind: 'start'; time: string; branch: string }
  | { kind: 'end'; time: string; branch: string; result: string }
  | { kind: 'raw'; text: string }

/** 一個持有閘門的分支：最後一筆開始行之後沒有同分支結束行的分支（完整名稱）與該開始行的時間 `HH:MM:SS`。 */
export type MergeGateHolder = { branch: string; since: string }

/**
 * 合併閘門紀錄：ok 為最近幾行開始／結束與目前所有持有者（以整份紀錄判定，依開始順序，沒有時為空陣列），
 * error 為讀檔失敗原因。
 */
export type MergeLogResult =
  | { kind: 'ok'; entries: MergeGateEntry[]; holders: MergeGateHolder[] }
  | { kind: 'error'; message: string }

/**
 * 一個 session 的狀態，取自 `~/.claude/sessions/<pid>.json`（CC 內部檔案，格式無官方承諾）。
 * status 原樣保存，已知值為 waiting／busy／shell／idle，其他值照樣顯示；waitingFor、statusUpdatedAt、procStart 缺少時為 null。
 */
export type SessionState = {
  pid: number
  name: string
  cwd: string
  status: string
  waitingFor: string | null
  /** epoch 毫秒。 */
  statusUpdatedAt: number | null
  /** 行程啟動時間，UTC 的 `ps -o lstart` 格式（如 `Mon Oct 19 09:09:02 2026`）；用來辨識 pid 是否被重複使用。 */
  procStart: string | null
  /** session 的 UUID；派發紀錄的 session_id 以此對應 session。缺少時為 null。 */
  sessionId: string | null
}

/**
 * 主 checkout `.claude/dispatch-active.json` 的 dispatches 一筆（只取看板要的欄位）。
 * name 為代理人類型（linux、general-purpose 等）；ticketId 在紀錄寫空字串時為 null；
 * dispatchedAt 與 turnEndedAt 為原樣的 ISO 時間字串，turnEndedAt 為 null 表示代理人尚未結束。
 */
export type DispatchRecord = {
  agentId: string
  name: string
  sessionId: string
  ticketId: string | null
  description: string
  dispatchedAt: string | null
  turnEndedAt: string | null
}

/** 派發紀錄的讀取結果：ok 為 dispatches 中可辨識的條目，error 為讀檔失敗或格式錯誤的原因。 */
export type DispatchesResult =
  | { kind: 'ok'; records: DispatchRecord[] }
  | { kind: 'error'; message: string }

/** 派發中代理人的流程階段。 */
export type DispatchStage = '實作' | '審查' | '事故分析' | '閘門' | '收尾'

/** 派發列的判定依據：存活的 session、協調票的線、主 checkout 的票狀態、閘門持有者。 */
export type DispatchContext = {
  sessions: readonly SessionState[]
  lanes: readonly Lane[]
  tickets: readonly TicketStatus[]
  holders: readonly MergeGateHolder[]
}

/** 派發區塊的一列：所屬線（對不到為 null，顯示為「其他」）、代理人名稱、任務（票號或派發描述）、流程階段、派發時間。 */
export type DispatchRow = {
  lane: number | null
  name: string
  task: string
  stage: DispatchStage
  dispatchedAt: string | null
}

/**
 * 一個群組標題列的活動計數，與展開後的內容一一對應：dispatching 為派發列數；inGate 為派發列中階段為閘門者加上 gateTickets 數；
 * isWaiting 為該線的 session 狀態是 waiting（等你處理）；queued 為佇列列中狀態不是 completed 的票數。
 */
export type GroupActivity = { dispatching: number; inGate: number; isWaiting: boolean; queued: number }

/** 佇列中一張正持有合併閘門的票（閘門持有者為其 `feat/<票號>` 分支）：短票號與開始時間 `HH:MM:SS`。 */
export type GateTicket = { serial: string; since: string }

/**
 * 以線分組的一個群組：id 為展開狀態的鍵（`lane:<n>` 或 `other`）；lane 為 null 表示「其他」群組（收容對不到線的派發）。
 * 展開後依序列出 dispatches、gateTickets（派發列已標閘門的票不重複列）與該線的佇列列。
 */
export type LaneGroup = {
  id: string
  lane: Lane | null
  dispatches: DispatchRow[]
  gateTickets: GateTicket[]
  activity: GroupActivity
}

/** 使用者按過的群組的展開狀態，以群組 id 為鍵；沒有的鍵依預設判定。 */
export type GroupOverrides = Record<string, boolean>

/** 各 session 狀態的讀取結果：ok 為本 repo 內 pid 仍存活的 session 與已結束的檔數，error 為讀取失敗原因。 */
export type SessionsResult =
  | { kind: 'ok'; sessions: SessionState[]; endedCount: number }
  | { kind: 'error'; message: string }

/**
 * 一次讀取的完整結果。loading 表示 session 啟動後尚未完成第一次讀取；
 * unconfigured 表示專案設定不成立（設定檔的絕對路徑與原因），此時不讀其他各項。
 */
export type BoardSnapshot =
  | { kind: 'loading' }
  | { kind: 'unconfigured'; configPath: string; config: UnsetProjectConfig }
  | {
      kind: 'ready'
      updatedAt: string
      /** 讀取當下的 epoch 毫秒，用來算各 session 距上次狀態更新的時間。 */
      readAtMs: number
      mainPath: string
      /** 無法以 `git worktree list` 判定主 checkout 時的原因；此時退回 session root。 */
      checkoutNote: string | null
      /** 短票號前綴（如 `1.2.0-W3-`）：由專案設定的協調票推導（shared.ts ticketPrefixOf），派發列以它去掉票號前綴。 */
      ticketPrefix: string
      lanes: LanesResult
      tickets: TicketStatus[]
      sessions: SessionsResult
      /** 存活 session 的 context 用量檔（readContextUsages），以 sessionId 為鍵；讀不到的 session 不在其中。 */
      usages: Record<string, ContextUsageRecord>
      mergeLog: MergeLogResult
      dispatches: DispatchesResult
    }

/** 已完成第一次讀取的 snapshot：Pane 各區塊繪製時的輸入。 */
export type ReadyBoard = Extract<BoardSnapshot, { kind: 'ready' }>

declare module 'claude-code' {
  interface PluginState {
    'line-board': { snapshot: BoardSnapshot; expanded: GroupOverrides }
  }
  /**
   * 本 plugin 以 $.tool.register 註冊的工具。平台型別根的 MCP 條目只列已連線 server 的工具，
   * 列了之後 tool.call 的過濾名稱就收窄為那些名稱；自己註冊的工具須在此補上，過濾器才接受。
   */
  interface McpToolInputs {
    'mcp__line-board__line_status': Record<string, never>
  }
}
