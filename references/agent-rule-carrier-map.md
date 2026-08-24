# 代理人規則載體對應表（Carrier Map）

本檔記錄 `.claude/agents/AGENT_PRELOAD.md` 12 條強制規則各自的**實際生效載體**與受眾範圍。

> **為何需要本檔**：`.claude/agents/*.md` 主文的 `@path` 引用經三探針實測確認不展開為內容，AGENT_PRELOAD.md 從未進入任何 subagent 的 context。12 條規則因此分散到不同載體——有的另有 `rules/core/` 自動載入路徑、有的靠 hook 在執行點強制、有的已寫入各 agent 定義檔。維護者要修改任一條時，必須先知道它現在住在哪。
>
> **維護要求**：新增或搬移任何條款後，同步更新本表。本表是**這 12 條條款**載體歸屬的 SSOT，不得只改條款而不改本表。
>
> **範圍界線**：載體**類型的選擇原則**（哪種知識該用哪類載體）見 `.claude/methodologies/knowledge-carrier-allocation-methodology.md`；`rules/core/` 載體的**形態規範**見 `.claude/references/auto-load-stub-conventions.md`。本表只記錄這 12 條的**實際歸屬現況**，不定義原則。

---

## 對應表

| # | 條款 | 受眾 | 實際生效載體 | 執行點強制 |
|---|------|------|------------|-----------|
| 1 | 語言規範 | 全體 | `rules/core/language-constraints.md`（自動載入） | `language-guard` / `homoglyph-guard` / `utf8-integrity-check` |
| 2.1 | 禁直接 Read ticket md，改用 CLI | 全體 | 無文字載體，由執行點承擔 | `skills/ticket/hooks/ticket-file-access-guard-hook.py`（deny + CLI 引導） |
| 2.2/2.3 | 進度更新 append-log | 實作類 agent | 各 agent 定義檔「Ticket 執行責任」章節 | 無 |
| 2.4 | 身份申報與收尾自律 | 實作類 agent | 同上；`--as` 身份對照另有 CLI 層 | `skills/ticket/ticket_system/lib/identity_guard.py`（complete/finish 未帶 `--as` 已轉強制 deny；其餘命令仍過渡期 warn-only） |
| 3 | 文件格式規範 | 全體 | `rules/core/document-format-rules.md`（自動載入） | `language-guard` |
| 4 | 5W1H 回應格式 | 全體 | Output Style（session 層） | `5w1h-compliance-check` |
| 5 | 查詢範圍限制（Phase 3b） | 編輯產品碼者 | 部分實作類 agent 定義檔「查詢範圍限制」章節（6 檔，未全覆蓋見下） | 無 |
| 6 | Git 操作限制 | 全體 | `rules/core/bash-tool-usage-rules.md`（自動載入） | 多個 git 相關 hook（口徑：`grep -l "git" .claude/hooks/*.py` 後逐一確認註冊） |
| 7 | 工具選擇規則 | 全體 | `rules/core/tool-selection.md`（自動載入） | `mcp-write-tool-on-text-file-guard` |
| 8 | 資源存在性驗證 | 規劃類 agent | AGENT_PRELOAD 原文（**未搬移，受眾未覆蓋**） | 無。事後偵測由 `skills/broken-link-check/scan_links.py` 承擔（掃描根待擴充至 `docs/`） |
| 9 | 嵌套派發資訊協議 | 會嵌套派發者 | AGENT_PRELOAD 原文 + `references/agent-dispatch-template.md`（派發端視角） | `skills/ticket/hooks/agent-ticket-validation-hook.py`：ticket 引用硬 deny；深度上限 deny 但 `depth` 模組 import 失敗時 fail-open，另有代理人類型豁免清單 |
| 10 | 忽略 `[PM-ONLY]` 前綴 | **待定（可能為空集合）** | AGENT_PRELOAD 原文（未搬移） | 生產端 `lib/hook_io.py` 已對帶 `agent_id` 事件過濾；消費端受眾待驗證 |
| 11 | 最小變更紀律 | 編輯既有碼者 | 部分實作類 agent 定義檔「最小變更紀律」章節（7 檔，未全覆蓋見下） | 無 |
| 12 | 框架檔案禁專案 ticket ID | 全體 | `rules/core/document-format-rules.md` 路由 | `reference-stability-rule8-guard`（exit 2 硬擋） |

---

## 載體類型與其特性

| 載體 | 送達範圍 | 成本 | 適用 |
|------|---------|------|------|
| `rules/core/` 自動載入 | 全體（PM + 所有 subagent），零受眾區分 | 每回合計入 45k 預算，乘以派發次數 | 全體適用且需理解的行為禁令 |
| 各 agent 定義檔 | 僅該 agent 執行時 | 單次載入，不乘派發次數 | 受眾限定的條款 |
| Hook 執行點強制 | 觸發該工具呼叫時 | 零 context 成本 | 可機械判定者；deny 訊息可自我教學 |
| `references/` 按需 | 主動 Read 時 | 零被動成本 | 完整論證、情境 SOP |
| AGENT_PRELOAD 原文 | **不送達任何 agent** | — | 尚未重分配者的暫存位置 |

---

## 未覆蓋條款

| 條款 | 狀態 |
|------|------|
| 5、11 的部分受眾 | 條款 5 覆蓋 6 檔、條款 11 覆蓋 7 檔。`pepper-test-implementer` 與 `sage-test-architect` 皆編輯既有測試碼，落在條款 11 受眾內但未覆蓋；`project-compliance-agent` 有 11 無 5 |
| 8 資源存在性驗證 | 受眾為規劃類 agent，尚未寫入其定義檔。事後偵測管道存在但掃描範圍不含 `docs/` |
| 10 PM-ONLY 前綴 | 受眾是否為空集合待驗證。若 Stop event 不在 subagent 情境觸發，正確處置為廢止而非分配載體 |

三者皆有對應 ticket 追蹤，不屬無 trigger 延後。條款 5、11 的部分受眾未覆蓋屬本次重分配的已知缺口，非遺漏——三個未覆蓋的 agent 皆為 Phase 1 至 3a 的規劃或測試設計角色，是否納入受眾需個別判斷。

---

## 相關文件

- `.claude/references/agent-preload-relocated-clauses.md` — 已重分配條款（5、11）的完整 substance；各 agent 定義檔的壓縮版由該處補齊判準表與門檻
- `.claude/agents/AGENT_PRELOAD.md` — 12 條規則原文；其 header 記載送達現況
- `.claude/references/auto-load-stub-conventions.md` — `rules/core/` 載體的形態規範與外移 SOP
- `.claude/methodologies/knowledge-carrier-allocation-methodology.md` — 知識載體頂層分配地圖

---

**Last Updated**: 2026-08-18
**Version**: 1.1.0 — 依 Layer 2 審查修正四項事實準確性問題：條款 9 的執行強度由「皆硬 deny」改述為 ticket 引用硬 deny、深度檢查 import 失敗時 fail-open 且有豁免清單；條款 6 移除無法復現的「等 5 個」計數改附可查口徑；條款 5、11 的載體欄由「各 agent 定義檔」改為標明實際覆蓋檔數並補入未覆蓋清單（原表述讀來像全覆蓋，與同檔未覆蓋章節的誠實標準不一致）；SSOT 宣告限定範圍為這 12 條並補與方法論、stub 規範的界線。
**Version**: 1.0.0 — 初始建立。記錄 12 條強制規則的實際生效載體、受眾範圍與執行點強制狀況。
