# Worktree 隔離詳細規則

> **定位**：本檔為 `.claude/pm-rules/parallel-dispatch.md`「Worktree 隔離（風險分級）」章節的完整 substance。主文保留該章節標題為 stub 並路由至本檔，內容原樣搬移未經改寫。
> **外移紀錄**：2026-09-01 外移（熱點檔案叢集拆分，依既有叢集邊界分析定案的叢集 B）。

---

## Worktree 隔離（風險分級）

派發代理人時，依任務風險等級決定隔離策略，非一律強制 worktree。

> **設計依據（多方案實驗結果的分段採納）**：低風險任務（ANA/DOC/唯讀，約 40-60%）免 worktree 是既有實務的明文化（hook 本來就不對分析/審核代理人強制 worktree）；高風險長 IMP 維持 worktree 強制。中風險短 IMP 共享 tree + PM 統一 commit 暫緩，待後續受控實驗結論。

### 風險分級表

| 風險等級 | 任務特徵 | 隔離策略 | 代理人範例 |
|---------|---------|---------|-----------|
| 低風險 | ANA/DOC/唯讀分析，不修改 `src/` `lib/` `test/` 產品程式碼 | 主 repo cwd（不需 worktree） | saffron, linux, bay, basil, thyme-documentation, lavender, Explore |
| 高風險 | IMP/重構/測試實作，修改 `src/` `lib/` `test/` 產品程式碼或測試 | `isolation: "worktree"` 強制 | parsley, fennel, thyme-python, cinnamon, pepper, mint |
| 中風險 | 短 IMP 共享 tree + PM 統一 commit | **暫緩**（blocked pending W5-033 受控實驗結論） | — <!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 --> |

> **Source of truth**：此風險分級表為 worktree 隔離需求的唯一定義來源。Hook `agent-dispatch-validation-hook.py` 的 `IMPLEMENTATION_AGENTS` 清單必須與高風險列的代理人範例同步。

### worktree 派發注意事項

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
> **worktree base 取 origin/main（可能 stale）**：cc runtime 的 `Agent(isolation: "worktree")` 以 `origin/main`（remote-tracking ref）為 worktree base，**而非** local main HEAD（W3-007 實證）。**Why**：cc runtime 取 remote-tracking ref 作 base；當 local main 領先 origin/main（有未 push 的本地 commit）時，worktree 建在 stale 基底上，缺少最新本地 commit。**Consequence**：agent 以缺 commit 的過時基底工作，產出與 local main 不相容，需 agent 手動 recovery（W2-013 實證 parsley 手動 checkout feat 分支救回）。**Action**：(1) **派發 worktree agent 前先 `git push origin main`**，使 origin/main 對齊 local main（消除根因分歧）；`worktree-commit-before-dispatch-hook.py` 會在 origin/main 落後時 stderr 警告。(2) 派發 prompt 開頭加 `git merge main` 指引作補強（worktree 共享 `.git`，main ref 一致）。完整說明與 prompt 範本見 `.claude/references/agent-dispatch-template.md`「worktree 派發 base 同步指引（W1-035）」。

> **worktree 為 fresh checkout，gitignored 生成產物須先確認就緒**：worktree 是全新 checkout，任何 gitignored 的建置生成產物（i18n 產物、序列化程式碼、DI 註冊等）若未同步存在，會造成連鎖編譯失敗且極易被誤判為高並行編譯器資源耗盡（實證與歸因陷阱見 `IMP-APP-003`）。**Why**：gitignore 排除生成產物是常見慣例，但該慣例假設「產物可即時重新生成」，worktree 派發若未確保生成步驟已執行，假設不成立。**Consequence**：全套件測試結果不可信，數十至上百項編譯失敗會被誤歸因為環境噪音而非缺產物。**Action**：(1) 派發跑全套件的 worktree agent 前，PM 先確認該 worktree 內含當前所有必要生成產物；(2) 對每個 gitignored 生成產物，評估納入版控，或於派發 prompt 中要求 agent 先執行對應 generation 指令（如 `flutter gen-l10n` / `dart run build_runner build`）；(3) 判斷「大量編譯失敗」是否為此類根因時，先查該產物是否 gitignored 且未納版控，勿逕自歸因並行資源耗盡。

> **worktree 派發收尾用 `ticket track finish` 別名，避開 `complete` 誤判**：CC runtime 的 worktree isolation guard 對 argv 逐元素做 basename 比對其可處理的 shell 命令清單，`complete` 命中 bash builtin `complete`，使 `ticket track complete` 在 worktree 派發下條件性被誤判為「不可驗證的合併類操作」而阻擋（同一操作同一隔離環境下結果不穩定重現，五次派發兩擋三過）。**Why**：guard 的比對粒度是 argv 每個 token 的 basename，不區分命令位置與參數位置，故子命令名稱恰好撞上 shell builtin 名稱時才會誤判，其餘子命令（如 `claim`、`append-log`）不受影響。**Consequence**：代理人執行 `ticket track complete` 被拒時無法自行收尾，需 PM 在主 repo 代執行並代填 Layer 1 自檢，但代填的自檢在證據來源上與代理人自檢本質不同（PM 看不到代理人的執行過程）。**Action**：worktree 隔離派發的收尾指引一律使用 `ticket track finish <id> --as <agent-name>`（`finish` 為 `complete` 的別名，兩者行為完全等價，含 `--as` / `--force` 全旗標）；主 repo cwd 場景維持原名 `complete` 不變。`complete` 本身不動、不加棄用警告——它不是要被取代，只是在 worktree 環境有代稱。

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
### Redirect 派發反模式禁令（強制，W1-016）

**禁止 `isolation: worktree` + prompt 導向另一個既有外部 worktree 的組合派發。**

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
**Why**：`isolation: worktree` 建 auto-worktree（`.claude/worktrees/agent-*`），agent cwd 在 auto-worktree 內。若 prompt 又導向另一個外部 worktree 做檔案操作，ticket CLI（claim/append-log/Exit Status auto-commit）依 cwd 解析落在 auto-worktree 分支，code changes 落在外部 worktree 分支，形成 ghost commits——ticket metadata 與 code changes 分裂到不同分支，PM 需手動回收（W1-001/W1-003 實證：各 3 筆 ghost append-log commit 需 `-s ours` 回收）。

**Consequence**：(1) main 票面停在 pending（auto-worktree 的 ticket 變更未進 main）；(2) PM 需手動比對兩個分支確認超集關係；(3) auto-worktree 分支清理後 ghost commits 可能遺失。

**Action**：依需求選擇正確的單一隔離模式：

| 需求 | 正確派發模式 | 說明 |
|------|------------|------|
| agent 需要隔離 | `isolation: worktree` 單獨使用 | agent 在 auto-worktree 工作，ticket CLI 和 code changes 都落在 auto-worktree 分支，PM merge 時一併取回 |
| agent 需在特定分支/worktree 工作 | 不用 `isolation: worktree`，prompt 提供外部 worktree 路徑 | agent cwd 在 main repo，file ops 用絕對路徑，ticket CLI 落 main repo |
| agent 需在特定分支 + 隔離 | `isolation: worktree` + prompt 加 `git checkout <branch>` | auto-worktree 可 checkout 任何分支（共享 git object store），不需另一個 worktree |

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
> **根因分析**：paths.py 的 `_linked_worktree_root()` 偵測 auto-worktree 為 linked worktree 並回傳其根目錄是 W3-010 修復的**正確行為**。問題在於兩個不相容隔離機制疊加，不在路徑解析邏輯。完整分析見 0.38.1-W1-016 ANA。

### 並行場景路徑區分（`.claude/` vs `src/`）

> **兩個正交維度**：代理人類型（上表）決定是否需要 worktree 的一般規則；target 路徑（本小節）決定 worktree 可否使用的實體限制。**target 路徑限制優先於代理人類型**。

#### 規則表

| Target 路徑 | 派發策略 | 並行 commit 安全模型 |
|-----------|---------|-------------------|
| `src/` / `test/` / `lib/` / `docs/` | worktree 隔離（預設） | 各 worktree 獨立 commit，PM 合併 |
| `.claude/` | 主 repo cwd（CC runtime 限制） | 精準 staging + Hook 偵測（見「派發 prompt 必含精準 git staging」章節） |

#### `src/` 預設 worktree 的業界證據（2026）

AI coding agent 並行工作預設 worktree 隔離已成業界共識：

| 來源 | 立場 |
|------|------|
| Anthropic Claude Code 官方文件 | 推薦 worktree for multi-session workflows |
| Cursor | "Parallel Agents" 功能建立在 worktree 基礎上 |
| Augment Code Intent | 每個 Space 專屬 worktree + branch |
| Upsun 開發者文件（2026 專文） | AI coding agents worktree 用法專題 |
| Worktrunk CLI（2026 初發布） | 專為並行 AI agent 設計的 worktree 管理工具 |
| JetBrains 2026.1 / VS Code 2025.7 | first-class worktree IDE 支援 |

worktree 解決並行 AI agent 的核心問題：shared git index 競爭（見 PC-092）。獨立 worktree 提供獨立 index，並行 commit 互不干擾。

#### `.claude/` 例外（CC runtime 硬編碼保護）

Claude Code runtime 對 subagent 操作 worktree 內 `.claude/` 有硬編碼保護（見 ARCH-015）。實測 v2.1.114：

- **Target 在主 repo 樹內 `.claude/`**：subagent Write/Edit 可成功（無論 cwd 是主 repo 或 worktree）
- **Target 在 worktree 樹內 `.claude/`**：subagent Write/Edit 被拒
- **分界線**：target 路徑是否在主 repo 樹內

因此 `.claude/` 不能用 worktree 隔離並行修改，改用精準 staging + Hook 偵測（PC-092 方案 A）。

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
#### `.claude/` 修改類並行數限 ≤ 2（W17-177 ANA 落地）

`.claude/` 修改類 ticket（含 hooks、pm-rules、error-patterns、agents、rules、methodologies、skills 等）並行派發數**限 ≤ 2**，禁止 3+ 並行。

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
**Why**：W17-177 saffron ANA 統計 — 7/7 歷史 deny 案例（W17-097.1-.4 + W17-174.2.1/.3/.4）皆發生於並行派發場景；18/18 非並行 Edit 全部 success。並行派發 + `.claude/` Edit 為新候選假設（中等證據）。

**Consequence**：3+ 並行派發 `.claude/` 修改類 ticket 預期觸發 runtime deny（無 hook stderr，無 hook-logs；診斷成本高）；deny 後需 PM 接手手動 Edit，併行收益被抹除。

**Action**：

| 並行數 | 處理方式 |
|-------|---------|
| 1 | 序列派發，無限制 |
| 2 | 允許並行；確認檔案邊界互斥 |
| 3+ | 拆 batch（每批 ≤ 2）或改序列；緊急情境豁免需在 dispatch-plan 註明並接受 deny 風險 |

**重啟條件**：若並行 ≤ 2 場景仍出現 `.claude/` Edit deny，需重啟調查並執行對照組實驗（非並行單發 Edit 對照），區辨「並行假設」vs 其他未識別變因（PC-115 trigger 計數歸零後重新累積；完整背景見 PC-137「觀察」章節）。

#### 實務落地對照

| 場景 | 派發位置 | 並行 commit 策略 |
|------|---------|----------------|
| 單一代理人改 `src/` | worktree | 代理人自 commit |
| 多代理人並行改 `src/` 不同檔案 | 各自 worktree | 各自 commit，PM 合併 |
| 單一代理人改 `.claude/` | 主 repo cwd | 代理人自 commit |
| 多代理人並行改 `.claude/` 不同檔案 | 主 repo cwd | 精準 staging（禁 `git add .` / `git add -A`），序列化 commit 或 PM 統一 commit |

> 業界證據連結：
> - Augment Code — https://www.augmentcode.com/guides/git-worktrees-parallel-ai-agent-execution
> - Upsun — https://developer.upsun.com/posts/2026/git-worktrees-for-parallel-ai-coding-agents
> - Worktrunk — https://worktrunk.dev/

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
### bgIsolation: none 並行安全建議（W3-034.4 驗證落地）

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
Claude Code v2.1.143+ 提供 `worktree.bgIsolation: "none"` 設定，讓 subagent 直接在主 repo working copy 操作（不建 worktree）。W3-034.4 並行受控實驗驗證後，本設定已從「並行情境未驗證」升級為「並行 3 已驗證 success（W3-034.4 3/3）」；2026-08-22 session 追加驗證擴大至並行 5 success，仍受 git index 競爭與並行 6+ 未測限制。 <!-- PC-093-exempt: history:0.19.0-W3-034.4 為實驗驗證歷史錨點 -->

**模式判別方法**：套用本節與下方任一表格前，先確認當前 session 實際處於哪個模式，完整判準（`git worktree list` + settings 檢查兩項）見 `.claude/error-patterns/process-compliance/PC-137-parallel-subagent-claude-dir-edit-deny.md`「如何判別自己處於哪個模式」章節。

**風險矩陣**：

| 風險類型 | bgIsolation: worktree（預設） | bgIsolation: none |
|---------|-----------------------------|------------------|
| Git index 競爭 | 各自隔離，安全 | **共享 index**；2026-08-22 session 11 組並行批次實測：index.lock 競爭可重試通過、跨票 staged 污染需 `git restore --staged` 卸除，見下方「已驗證情境」 |
| `.claude/` 並行 Edit | 限並行 ≤ 2（PC-137 worktree 模式規則） | 並行 5 已驗證 success（W3-034.4 起始驗證 3，2026-08-22 session 追加至 5）；6+ 未驗證 <!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 --> |
| 殭屍 worktree 累積 | 有，已有 GC hook | 無此問題 |
| 合併成本 | 每次需合併 | 無 |

**目前建議（v0.19.x）**：採策略 C 條件式採用（與 worktree-operations.md 一致）。

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
**Why**：W3-034.4 並行受控實驗驗證 bgIsolation: none + 並行 3 subagent + `.claude/` Edit 達 3/3 success（PC-137 v1.1.0 落地）；2026-08-22 session 追加驗證至並行 5（PC-137 v1.2.0 落地）。PC-137 並行 ≤ 2 規則僅在 worktree 模式下有效；bgIsolation: none 下未受並行數限制（已驗證至 5）。

**Consequence**：誤外推 worktree 模式並行限制到 bgIsolation: none 會放棄已驗證的並行解鎖；反之誤外推 none 模式解鎖到 worktree 模式則違反 PC-137 規則。模式判別錯誤直接決定派發成敗。

**Action**：

| 場景 | bgIsolation 設定 | 並行限制 |
|------|------------------|---------|
| 單一 subagent + `.claude/` 修改 | none 可選 per-dispatch override | 無並行（W3-034.1 驗證 success） <!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 --> |
| 並行 2 subagent + `.claude/` 修改 | worktree（預設）或 none 皆可 | 允許並行（PC-137 worktree 模式上限 = 2；none 模式同等可用） |
| 並行 3+ subagent + `.claude/` 修改 | **none 必用**（worktree 模式禁止 3+） | 允許並行 Edit（已驗證至 5）；commit 由 PM 統一執行或依精準 staging 紀律各自提交 |
| 全面切換 bgIsolation: none | **暫不採用** | 並行 6+ 未驗證；對 src/ 失去 worktree 隔離保護。當前正向路徑：採策略 C 條件式採用（per-dispatch override），待出現 6+ 並行需求時，建 ANA ticket 對照實驗 |

**未驗證情境（仍受限）**：

| 情境 | 風險 |
|------|------|
| bgIsolation: none + 並行 6+ subagent | 更高並行度未測，採並行 ≤ 5 為觀察上限 |

> 上表屬規則檔擴充性說明（依 `.claude/rules/core/decision-trigger-binding.md` 規則 1.5，rules/方法論可述未來考量，不需綁 ticket trigger）。實際出現 6+ 並行需求時，建 ANA ticket 執行對照實驗。

**已驗證情境：bgIsolation: none + 並行 git add / commit（2026-08-22 session 實測）**：

原「PC-092 共享 index 競爭未測」情境已由 11 組並行批次（全程共用主 repo git index 提交）的實測取代：

| 觀察 | 內容 |
|------|------|
| index.lock 競爭 | 確實發生（PM 側至少 2 次、代理人側數次），但重試即通過，無資料損失 |
| 跨票 staged 檔案污染 | 確實發生且頻繁；提交前以 `git diff --cached --name-only` 核對時發現他票檔案已在 index 中，以 `git restore --staged` 卸除後才提交 |
| 三步驟串接致誤提交 | 一次實際誤提交發生於 PM 側，成因是把「精確 add → 核對 → 裸 commit」三步驟以 `&&` 串接，使核對輸出在 commit 之後才可見；已由後續 commit 補正，無資料遺失 |
| 高衝突路徑的替代方案 | 隔離索引 CAS（`GIT_INDEX_FILE` + `read-tree`/`write-tree`/`commit-tree`/`update-ref`，完全不觸碰共用 index）已有可行實作，見 `.claude/rules/core/bash-tool-usage-rules.md` 規則七「隔離索引 CAS」段 |

**結論**：風險真實存在且會顯現，但以既有紀律（規則七三步驟不串接 + 提交前核對 index + 高衝突路徑改用隔離索引）可管理。**不因此收緊並行數**——問題出在提交紀律，不在並行度。

**Git index 競爭警告（bgIsolation: none 下強化）**：

bgIsolation: none 下所有 subagent 共享主 repo git index。並行派發若任一 subagent 執行 `git add` 或 `git commit`，會與其他 subagent 競爭 index.lock，可能造成：

- Index corruption（多個 process 同時寫 index）
- Commit 邊界混亂（git add 範圍超出該 subagent 工作範圍）
- Index.lock 殘留（process 異常結束未釋放）

對應防護：派發 prompt 必含精準 git staging（禁 `git add .` / `git add -A`），或由 PM 統一 commit，見本文件「派發 prompt 必含精準 git staging」章節。

**對照 PC-137 v1.2.0 規則**：

| 並行數 | bgIsolation: worktree | bgIsolation: none |
|-------|----------------------|------------------|
| 1 | 序列派發，無限制 | 序列派發，無限制 |
| 2 | 允許並行（檔案邊界互斥） | 允許並行（檔案邊界互斥） |
| 3+ | 拆 batch（每批 ≤ 2）或改序列 | 允許並行 Edit（已驗證至 5）；commit 由 PM 統一執行或依精準 staging 紀律各自提交 |

<!-- rule8-exempt: relocation:自 .claude/pm-rules/parallel-dispatch.md 逐字搬移 -->
PC-137 並行 ≤ 2 規則為 worktree 模式下的觀察結論（W17-097.1-.4 + W17-174.2.1/.3/.4 7/7 deny 證據）；bgIsolation: none 模式並行行為由 W3-034.4 受控實驗驗證為不同模式，並經 2026-08-22 session 追加驗證，並行 ≤ 5 已 success。模式判別應依「模式判別方法」段所列兩項判準為準（`git worktree list` + settings 檢查），per-dispatch override 機制由 CC runtime 提供，當前 v0.19.x 採全域 settings + 特定情境派發近似實現。

**參考**：

- worktree-operations.md「bgIsolation 策略選擇」子節（策略對照表與決策樹）
- PC-092（並行 commit 邊界混亂）
- PC-137 v1.2.0（並行 ≤ 2 規則 + bgIsolation: none 例外章節 + 模式判別方法）

---

**Last Updated**: 2026-09-01
**Version**: 1.0.0 — 從 `.claude/pm-rules/parallel-dispatch.md`「Worktree 隔離（風險分級）」章節整段外移（熱點檔案叢集拆分），內容未經改寫，僅位置搬移。
