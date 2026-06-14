# Hook 系統方法論

> **30 秒核心**：本專案以完全自動化的 Hook 系統執行 CLAUDE.md 定義的開發規範。每個 hook 有明確觸發條件、執行邏輯與強制機制。設計遵循三大鐵律自動執行 + 六大設計原則；Hook 密度依開發階段平衡（前期主動設計、後期降級觀察）；每個 Hook 有生命週期階段與降級條件，避免摩擦力倒置。
>
> **本檔保留**：系統架構、Hook catalog、六大設計原則、階段平衡 4 原則、生命週期與降級機制、觀察類工具雙重身份。
> **衛星檔（operations 詳解）**：`.claude/references/hook-system-operations.md`（per-hook 程式碼、模組化規範、跨平台部署、完整決策樹、反模式）。
> **衛星檔（降級追蹤）**：`.claude/references/hook-system-downgrade-tracking.md`（降級追蹤表、Rollback SOP、觀察期評估結果）。

---

## 概述

Hook 系統是專案品質保證的核心基礎設施。每個 hook 在開發流程的特定時機自動觸發，將 CLAUDE.md 的開發規範從「人工記憶」轉為「自動強制」，確保每個開發決策都符合專案品質標準。

---

## 系統架構

### Hook 執行時機圖

```text
SessionStart / InstructionsLoaded
     |
UserPromptSubmit
     |
PreToolUse -> PermissionRequest / PermissionDenied -> Tool Execution
     |                                              |
PostToolUse / PostToolUseFailure                    Elicitation / ElicitationResult
     |
SubagentStart / SubagentStop / TaskCreated / TaskCompleted
     |
Stop / StopFailure
     |
PreCompact / PostCompact / SessionEnd

Standalone async events:
Notification / TeammateIdle / ConfigChange / CwdChanged / FileChanged / WorktreeCreate / WorktreeRemove
```

### 三大鐵律自動執行

| 鐵律 | 對應 Hook event |
|------|----------------|
| 測試通過率鐵律 | UserPromptSubmit Hook + PreToolUse Hook |
| 永不放棄鐵律 | Task Avoidance Detection Hook + Block Check Hook |
| 架構債務零容忍鐵律 | Architecture Debt Detection + Code Smell Detection + PostToolUse Hook |

---

## Hook 清單（Catalog）

各 Hook 的觸發時機與職責摘要如下。per-hook 程式碼細節、演算法、阻止機制見衛星檔 `.claude/references/hook-system-operations.md`「Hook 清單 per-hook 詳解」章節。

| Hook | event | 職責摘要 |
|------|-------|---------|
| SessionStart Hook | SessionStart | 確保每個 session 在已知良好狀態開始（Git 狀態、檔案載入、開發環境、版本一致性、LSP 環境）；失敗給修復指引不阻止 |
| UserPromptSubmit Hook | UserPromptSubmit | 問題發生前攔截（ESLint 錯誤、技術債累積、任務逃避偵測）；關鍵問題記錄追蹤，逃避行為完全阻止 |
| PreToolUse Hook | PreToolUse | 防禦性檢查（阻止狀態 -> 工具特定安全檢查 -> 允許）；任何阻止狀態完全禁止操作 |
| PostToolUse Hook | PostToolUse | 即時品質檢查與問題追蹤（程式異味偵測、文件更新提醒）；非阻塞記錄追蹤 |
| Stop Hook | Stop | 自動化版本推進建議（檔案變更量、工作日誌狀態、TodoList 完成度）；建議不強制 |
| SubagentStop Hook | SubagentStop | 代理人完成時清理派發記錄、驗證 commit、廣播完成、handoff 提醒、累積執行統計 |
| Performance Monitor Hook | PreToolUse/PostToolUse 前後 | 持續效能監控，預防 hook 系統成為瓶頸（< 1s 理想 / 2-5s 警告 / > 5s 立即優化） |
| Auto-Documentation Update Hook | PostToolUse | 程式碼變更後主動文件同步提醒（依變更類型對應目標文件 + High/Medium/Low 優先級） |

> **SubagentStop 識別碼**：代理人完成 Hook 匹配狀態檔案（如 `dispatch-active.json`）時，以 `agent_id`（runtime 提供，唯一）為 source of truth，不用 PM 自填的 `agent_description`（可能碰撞）。
> **Event 選擇強制規則**：「代理人完成」相關 Hook 一律掛 SubagentStop，禁止掛 PostToolUse(Agent)（後者在 background 派發時於啟動時觸發，與「完成」語意不符，詳見 ARCH-019）。

---

## Hook 系統設計原則

### 原則 0：Event 選擇與識別碼（強制）

選擇 Hook event 前必須完成以下檢查，避免時機錯位（ARCH-019）：

| 檢查項 | 要求 |
|-------|------|
| 不憑名稱推論觸發時機 | `PostToolUse(Agent)` 在 background 派發時於啟動時觸發；必須查 hook-spec 確認真實時機 |
| 啟動 vs 完成分掛兩 event | 啟動邏輯用 `PreToolUse(Agent)`；完成邏輯用 `SubagentStop`；主線程結束用 `Stop` |
| 識別碼選 source of truth | 狀態匹配用 `agent_id` 而非 `agent_description` |
| Handler 選擇 | 預設順序 `command` -> `http` -> `prompt` -> `agent`，越右成本越高需說明理由 |
| `if` 條件粗篩 | `if` 用於避免不相關工具觸發（如 `if: "Bash(git *)"`）；詳細判斷交給 handler，不硬塞進 `if` |

> Event 選擇完整決策流程、handler 對照表、`if` 條件情境表見衛星檔「Event 選擇決策流程」章節。
> 完整錯誤模式：`.claude/error-patterns/architecture/ARCH-019-hook-event-timing-mismatch.md`；Event input/output 規範：`.claude/references/hook-architect-technical-reference.md`。

### 原則 1-5：核心設計守則

| 原則 | 核心要求 |
|------|---------|
| 1. 分離關注點 | 每個 hook 專注特定檢查範圍，避免單一 hook 承擔過多責任，清晰的輸入輸出介面 |
| 2. 非阻塞優先 | 大部分檢查採記錄追蹤；只有關鍵違規才阻止；保持開發流程流暢 |
| 3. 漸進式強制 | 警告 -> 記錄 -> 追蹤 -> 阻止；給予理解修正機會；關鍵問題零容忍 |
| 4. 自動化決策 | 基於歷史資料與趨勢；上下文感知的檢查邏輯；自動優化調整 |
| 5. 可觀測性 | 詳細日誌記錄、效能指標追蹤、問題追蹤與報告生成 |

---

## Hook 階段平衡

> **核心主張**：從「錯誤發生才補 Hook」轉為「依階段特性主動設計 Hook」。前期階段主動設計、後期階段設定降級觀察期，防止 Hook 被動累積導致摩擦力倒置。

### 問題：被動防禦反射弧導致 Hook 分佈倒置

Hook 系統常呈現「錯誤發生 -> 補 Hook -> 觸發頻率上升 -> 誤報累積 -> 降級延後」的反射弧。此反射弧只對「錯誤立即可見」的階段有效，對「錯誤延遲顯現」的階段無效，結果是後期執行階段 Hook 高密度累積、前期決策階段 Hook 長期缺席。依摩擦力管理方法論，理想摩擦力應前期高、後期低，但 Hook 分佈卻前期低、後期高，這是摩擦力倒置的 Hook 層落地。

### 階段平衡 4 原則

| 原則 | 核心要求 |
|------|---------|
| 1. 依階段特性主動規劃 | 每個新功能/規則納入時主動問三題：錯誤會立即可見嗎（是則 Hook 可後補）？錯誤會延遲到後續 Phase 顯現嗎（是則 Hook 必須前置設計）？這是決策點還是執行點（決策點則 Hook 優先度提升）？ |
| 2. 前期階段 Hook 先行 | 前期（Proposal/Phase 0/Phase 1）的新增工作預設附帶 Hook 設計；反模式為「先上線，錯誤出現再補 Hook」 |
| 3. 後期階段設降級觀察期 | 後期（Phase 3b 實作）Hook 從一開始就設降級條件（連續 N 次無錯降級為提醒、連續 Wave 無錯進入廢除評估） |
| 4. Hook 本身受摩擦力約束 | Hook 加入/降級時依摩擦力方法論判斷象限與頻率；反模式為「Hook 疊加 Hook」（偵測誤報再加 Hook 的 Hook，無限遞迴） |

### 階段 Hook 密度表

| 階段 | 現況密度 | 理想密度 | 設計原則 |
|------|---------|---------|---------|
| Proposal 評估 | 低（近零） | 中高 | 分級檢查、章節完備、狀態綁 ticket |
| Phase 0 SA | 低 | 中 | 衝突檢查報告驗證 |
| Phase 1 規格 | 低 | 中高 | 規格存在、多視角審查、AC 完備 |
| Phase 1.5 多視角 | 低 | 中 | 審查記錄驗證 |
| Phase 2 測試 | 中 | 中 | 測試檔案存在、命名規範 |
| Phase 3a 策略 | 中 | 中 | 虛擬碼/流程圖驗證 |
| Phase 3b 實作 | 高（75+ Hook） | 中低 | 核心防護保留 + 連續無錯降級 |
| Phase 4 重構 | 中高 | 中 | 多視角審查驗證 |

**密度判定維度**：錯誤可逆性（不可逆/延遲顯現 -> 高密度）、錯誤放大範圍（跨 Phase/版本 -> 高密度）、決策 vs 執行（決策點 -> 高密度）、頻率 vs 嚴重（低頻高嚴重 -> 高密度）。

> **何時讀衛星檔**：需要完整 Hook 設計決策樹（前期主動設計分支 + 後期被動防禦分支的 ASCII 流程圖）或 5 條反模式清單時，讀 `.claude/references/hook-system-operations.md`「Hook 設計決策樹與反模式」章節。

---

## Hook 生命週期與降級觀察

> **核心**：每個 Hook 必須明示所處生命週期階段與降級條件。後期階段 Hook 降級後設 2 Wave 觀察期，確保未察覺風險可快速 rollback。

### 生命週期階段

| 階段 | 觸發行為 | 降級條件 |
|------|---------|---------|
| Active（活躍） | 正常攔截 | 連續 5 次無錯 -> Observing |
| Observing（觀察中） | 正常攔截但統計觸發 | 2 Wave 無錯 -> Deprecating |
| Deprecating（退役準備） | 降為提醒（warn -> info） | 3 Wave 無錯 -> Archived |
| Archived（封存） | 移除但保留歷史 | 回歸事件 -> 恢復 Active |

Hook 目錄下建議維護 `hook-lifecycle.yaml`，記錄各 Hook 的 stage、entered_stage_at、consecutive_no_error、downgrade_criteria。降級執行流程：自動統計（每次觸發記錄 action / no-action）-> 週期檢查（每 Wave 盤點）-> 降級決策 -> 快速恢復（觀察期發生回歸立即恢復 Active）。

### 降級機制：觸發消除 vs 處理降級

降級策略分為兩類，削減上限不同，預估削減比時必須分開計算。

| 機制 | 定義 | 削減上限 | 適用條件 |
|------|------|---------|---------|
| 觸發消除 | 從 settings.json 完全移除 hook 註冊 | 100% | Action 比 = 0% 且 False-negative 風險可接受 |
| 處理降級 | 保留註冊，內部邏輯加 fast-path / sampling / matcher 限縮 | 73-80%（實測） | Action 比 < 1% 但仍有監測價值；或完全移除的 False-negative 風險不可接受 |

> **Why**：「降級 ≈ 消除」的隱含假設未區分處理降級仍需 Python 進程啟動 + log 寫入的固定成本，會系統性高估削減效果，使後續降級計畫預估失準。
> **Action**：預估削減比用修正公式 `削減 % = Sum(觸發消除 hook 佔比 × 100% + 處理降級 hook 佔比 × 75%) / 總觸發`，觸發消除以 100%、處理降級以 75% 分別計算。

### 觀察期啟動與結束標準

降級後設 2 Wave 觀察期。觀察期結束時依三項判斷收斂或延長：

| 判斷項 | 收斂條件 | 延長條件 |
|--------|---------|---------|
| False-negative 案例 | 0 件 | >= 1 件 |
| Action 比變化 | 全 hook < baseline × 2 | 任一 hook >= baseline × 2 |
| 用戶體感 | 無劣化回報 | >= 2 件回報 |

**收斂行為**：建立降級驗證完成 ticket，標記降級為長期生效。**延長行為**：依觸發條件啟動對應 rollback SOP，建新 ticket 處理。

> **何時讀衛星檔**：需要 8 Hook 降級觀察期完整追蹤表（每 Wave 觸發次數與 Action 比）、Rollback 觸發條件表、快速恢復 SOP（場景 A 整批 / B 單一 hook / C 抽樣 N 調整）或歷史觀察期評估結果時，讀 `.claude/references/hook-system-downgrade-tracking.md`。

### 漸進落地

本階段平衡與降級方法論自公布日起作為新 Hook 設計的前置參考。既有 75+ Hook 依降級計畫逐批處理，不要求立即全面套用；既有 Hook 納入生命週期管理需透過「Hook 分類盤點」後批次升級。

---

## 觀察類工具的雙重身份設計

設計觀察類 Hook（diagnostic hook、telemetry collector、性能 monitor）時，應主動讓工具能在「日常使用」中持續產出資料，而非只在「實驗模式」下啟動。觀察類工具預設長期 telemetry 身份，非實驗一次性身份。

> **Why**：實驗模式下的觀察只覆蓋設計者預期的場景；日常使用觸發提供「非預期但真實」的對照基底。W3-028.2 案例：diagnostic hook 在實驗開始前的當下 session `/clear` 啟動時就被觸發，這筆「非實驗目的」紀錄證實了 hook 對工作流的零侵入性。
> **Consequence 不遵守**：實驗工具僅在實驗模式啟動會失去日常情境對照、被視為一次性而累積為技術債、無法驗證工具本身對工作流的侵入性。

| 設計階段 | 動作 |
|---------|------|
| Hook event registration | 不設「only experiment mode」flag，全域註冊到所有相關 event |
| 副作用控制 | 工具設計為「純觀察 0 副作用」（exit 0、不阻擋、append-only log），避免日常觸發造成干擾 |
| 報告書寫 | 實驗報告明示「日常 vs 實驗」資料來源差異，提升證據透明度 |
| 工具命名 | 名稱透露「diagnostic / telemetry」而非「experiment / test」，暗示長期身份 |
| 移除策略 | 默認保留為長期資產（除非有具體成本），不在實驗結束自動移除 |

---

## 相關文件

| 文件 | 用途 |
|------|------|
| `.claude/references/hook-system-operations.md` | per-hook 程式碼詳解、模組化開發規範、跨平台部署、完整決策樹、反模式（衛星檔） |
| `.claude/references/hook-system-downgrade-tracking.md` | 8 Hook 降級觀察追蹤表、Rollback SOP、觀察期評估結果（衛星檔） |
| `.claude/references/hook-architect-technical-reference.md` | Hook event input/output 規範、技術參考 |
| `.claude/methodologies/friction-management-methodology.md` | Hook 降級的上位摩擦力管理理論（開發流程階段摩擦力曲線） |
| `.claude/error-patterns/architecture/ARCH-019-hook-event-timing-mismatch.md` | Event 時機錯位完整錯誤模式 |
| `.claude/pm-rules/proposal-evaluation-gate.md` | 前期主動設計案例（proposal gate Hook） |

---

**Last Updated**: 2026-06-14
**Version**: 2.0.0 — 整併 hook 家族 3 檔為 1 主檔 + 2 衛星檔（W8-020.6）：折入 hook-stage-balance-methodology（階段平衡 4 原則 + 密度表）與 hook-downgrade-observation（生命週期 + 降級機制 + 觀察期標準）核心；operations 詳解外移 `hook-system-operations.md`、降級追蹤外移 `hook-system-downgrade-tracking.md`；emoji 全數清理為純文字（document-format-rules 規則 1）。歷史版本見 git log
