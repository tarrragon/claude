# 知識載體責任分配方法論

## 核心概念

知識寫入框架前，依「**受眾 x 形態**」二軸決定載體。載體錯置有兩種代價：寫進自動載入層 → token 污染（attention 稀釋 + 45k 預算耗盡）；困在專案 memory → 跨專案失傳。本方法論是頂層地圖；各載體的細部規範（如有）路由至 Reference 所列文件。

**Scope**：本地圖涵蓋 LLM context 載體（人與 AI 閱讀的知識）；專案產物層（`docs/` / `src/`）不屬本地圖，劃分見 `framework-asset-separation.md`；機器讀取層（`config/*.yaml`、hook 引用的凍結錨點）另計。memory 行由受眾軸「僅本專案」唯一決定，不需形態軸。

**代理人定義 vs skill 的歸屬判準**：一段知識可能落在代理人定義或 skill、不易區分時，以「該知識是否隨執行者改變」為判準，不憑直覺擇一。

- 屬**代理人定義**的知識回答「你是誰、你能做什麼、你偏好怎麼做」——身份定位、授權邊界、設計偏好。識別測試：換一個代理人來執行，這段內容就應該不同。本質是人格與授權。
- 屬 **skill** 的知識回答「這件事怎麼做」——可重複執行的流程步驟。識別測試：任何角色觸發都應得到同一份流程，與執行者是誰無關。本質是可重複流程。

兩者衝突時，對該知識套用識別測試「換一個代理人，內容會不會變」：會變則歸代理人定義；不會變、任何角色執行都應一致則歸 skill。

## 載體地圖（受眾 x 載入時機 x 形態）

| 載體 | 受眾 | 載入時機 | 裝什麼（形態） | 不裝什麼（→ 正確去處） |
|------|------|---------|--------|----------------------|
| `CLAUDE.md` | 所有角色 | 每回合自動 | 專案身份、開發指令、專案級技術選型、路由 | 框架通用知識（→ `.claude/`，否則無法 sync） |
| `rules/core/` | 所有角色 | 每回合自動 | 行為禁令速查 + 路由（與 CLAUDE.md 同屬 file-size-guardian 45k 量測集合；MEMORY.md 每回合注入但不在量測集合內） | 論證 / 流程 / 案例（→ `references/`、`error-patterns/`） |
| `pm-rules/` | 僅 PM | 情境觸發按需 | 調度流程 SOP（派發、驗收、決策樹、skip-gate） | 代理人執行知識（→ agents / skills） |
| `agents/AGENT_PRELOAD.md` | 全體代理人 | 派發時 @ 注入 | 代理人通用行為禁令（ticket 操作、git 限制、工具選擇、嵌套協議） | 單一代理人偏好（→ 各 agent 定義）、PM 流程（→ pm-rules） |
| `agents/<name>.md` | 單一代理人 | 派發時載入 | 身份定位、三區塊（允許產出 / 禁止行為 / 適用情境）、設計偏好（命名習慣、技術手法傾向、文法語氣）、分工路由與升級條件 | → 見「代理人定義內容規範」節 |
| `skills/` | 觸發者（角色無關） | 觸發時漸進揭露 | 可重複執行的工作流、方法、CLI 工具（TDD、寫作、ticket、worktree） | 身份偏好（→ agents）、專案設定（→ CLAUDE.md） |
| `methodologies/` | 主動查閱者與 AI | 按需 | 框架判斷標準 / 核心規則（判準 + 步驟 + 檢查清單，明確且可直接套用） | 完整流程 / 範例 / 錯誤處理（→ skills） |
| `references/` | 執行特定動作者 | 按需 | 技術參考、規則 substance（auto-load stub 的完整版） | 每回合禁令（→ rules/core stub） |
| `error-patterns/` | ticket 前查詢者 | 按需 | 失敗案例（症狀 / 根因 / 解法 / 預防） | 規則正文（規則只放一行路由指向 PC/IMP） |
| memory（專案層） | 本專案 PM | MEMORY.md 每回合 | 專案特定活教訓的單行索引 | 已固化內容（升級即搬家）、跨專案原則（四問升級後外移） |
| `templates/`、`.claude/` root 歷史遺留檔 | （未分類） | 不自動載入 | — | 依本地圖二軸重分配（templates 內容須與對應規範同步，否則新實例從模板長出舊形態）；盤點另由 ticket 追蹤 |
| `.claude/README.md` | 框架瀏覽者 | 不自動載入 | 框架頂層導覽：目錄結構、各載體用途、入口索引 | 規範 substance（→ rules / references）、流程方法（→ skills） |
| `.claude/CHANGELOG.md` | 框架維護者 | 不自動載入 | 框架變更記錄（sync 歷史、版本演進） | 當前規範內容（→ 對應載體；CHANGELOG 只記「變了什麼」不記「規範是什麼」） |
| `.claude/README-subtree-sync.md` | 執行 sync-pull / sync-push 者 | 不自動載入 | 同步機制操作說明：設計原理、方案比較、衝突處理 | 同步以外的框架知識（→ 對應載體） |
| `.claude/terminology-dictionary.md` | 所有角色（撰寫文字時） | 經 `.claude/rules/core/language-constraints.md` 的 `@` 引用實質載入 | 用語規範對照表：禁用詞 / 正確用語 / 台灣用語 | 語言規則正文（→ `.claude/rules/core/language-constraints.md`，本檔僅承載對照資料） |

## 執行步驟

1. **受眾是誰**？（所有角色 / 僅 PM / 全體代理人 / 單一代理人 / 動作觸發者 / 僅本專案）→ 縮小候選載體。「動作觸發者」統括地圖表受眾欄的按需情境詞（觸發者 / 主動查閱者 / 執行特定動作者 / 任務前查詢者）
2. **形態是什麼**？（行為禁令 / 調度流程 / 身份偏好 / 工作流方法 / 理念清單 / 技術參考 / 失敗案例 / 專案設定）→ 確定載體
3. 候選屬**自動載入層**（CLAUDE.md / rules/ / MEMORY.md）？→ 過預算閘門；規範類知識的閘門是必要性否決（「這是否每回合都需要？」否則外移按需層）+ 形態降為「禁令 + 路由」，專案設定 / 指令等事實類的閘門是體積與專案特定性約束（精簡陳述、不含框架通用知識），不適用必要性否決
4. skill / methodology / rule 三選一拿不準 → `framework-meta-methodology.md` 決策樹
5. 寫完 grep 概念詞，盤點與既有規範的指令方向矛盾，並對齊執法強度（PC-V1-006）

## 代理人定義內容規範

| 該裝 | 不該裝（外移路由） |
|------|------------------|
| 身份定位與核心使命 | — |
| 三區塊：允許產出 / 禁止行為 / 適用情境 | — |
| 設計偏好：命名習慣、技術手法傾向、文法語氣 | 專案級技術選型（→ CLAUDE.md；代理人帶多方案知識，依專案設定選用） |
| 多方案技術知識庫（framework-asset-separation §1 的「框架寫法」，深度以支撐選用傾向為度） | 步驟化操作流程（→ 對應 skill，流程與人格解耦）；知識庫展開成教學長文（→ references/） |
| 分工路由與升級條件（與誰分工、何時上報） | 操作流程步驟（→ 對應 skill） |
| 品質標準的章節路由（如 quality-common 指定章節，語意錨點） | 品質清單全文（複製即漂移，單一來源失效） |
| 錯誤模式的一行路由（「詳見 IMP-XXX」） | 錯誤案例全文（error-pattern 才是案例的家） |

## 檢查清單

- [ ] 受眾 x 形態二軸定位完成，不是「順手寫在開啟中的檔案」？
- [ ] 自動載入層寫入已過預算閘門；規範類形態已降為禁令 + 路由（事實類過閘門即可）？
- [ ] 代理人定義新增內容屬「偏好 / 邊界」而非「流程 / 方法」？
- [ ] 重複內容用路由取代複製（單一來源）？
- [ ] 概念詞 grep 矛盾盤點 + 執法強度對齊完成（PC-V1-006）？

## Reference

- `.claude/methodologies/framework-meta-methodology.md` — skill / methodology / rule 三分決策樹 + 方法論判斷標準定位（形態軸的細分）
- `.claude/references/framework-asset-separation.md` — 框架資產 vs 專案產物、專案設定 vs 代理人知識、Skill Hook 雙層
- `.claude/references/auto-load-stub-conventions.md` — 自動載入層 stub 構成 + 外移 SOP + 預算驗證
- `.claude/rules/core/agent-definition-standard.md` — 代理人三區塊結構標準
- `.claude/rules/README.md` — 自動載入預算原則（每回合必要性自問）
- `.claude/pm-rules/pm-quality-baseline.md` 規則 7 — memory 升級四問 + 升級目的地預算閘門 + 升級即搬家
- `.claude/README.md`「同步機制」章 — 寫作類 skill（compositional-writing / multi-round-review）內容 SSOT 在 blog repo，框架端為回流副本；依地圖判定「寫作方法 → skills/」後，內容修改應到上游 repo 執行
- `.claude/skills/skill-design-guide/SKILL.md` — skills 載體的細部規範（官方規格、frontmatter、漸進揭露結構）

---

**Last Updated**: 2026-06-15
**Version**: 1.9.0 — W8-041 標籤同步：methodologies 地圖列「30 秒理念複習清單」改為「框架判斷標準 / 核心規則（明確且可直接套用）」、受眾補 AI，Reference 對 framework-meta 描述「30 秒標準」改為「方法論判斷標準定位」，對齊 W8-040 新定位
**Version**: 1.8.0 — 「代理人定義 vs skill 歸屬判準」改寫：去除「一句話判定」總結框架，改為含明確識別測試（換一個執行者內容是否改變）的判準段落。方法論作為框架核心規則供 AI 開發時判斷，內容須明確而可套用，不採壓縮式總結（避免單句總結遮蔽判準細節導致 AI 判斷失準）
**Version**: 1.7.0 — root 錯置檔重分配（1.0.0-W8-023.2，第 2/4 批）：4 檔（`agent-collaboration.md` 794 / `decision-workflows.md` 116 / `quick-ref-agent-dispatch-recovery.md` 202 / `thinking-process.md` 271）逐檔讀內容後**全數 flag superseded/obsolete**（campaign 規則 3，零搬移零連結手術）：`agent-collaboration` 與 `analyses/archived/` 同名 794 行副本 near-identical 且內容已被 `methodologies/tdd-collaboration-flow.md` + agent 定義覆蓋；`decision-workflows` 五情境已被 `pm-rules/skip-gate`+`incident-response`+`decision-tree` 覆蓋；`quick-ref-agent-dispatch-recovery` 所述 `agent_dispatch_recovery.py` hook 已不存在；`thinking-process` 為 2025-12-01 一次性 session 快照非知識載體。本批 0 檔搬移，故不加 map 行，留 PM follow-up 清理（inbound 連結多在 .3/.4 批檔群）
**Version**: 1.6.0 — root 錯置檔重分配（1.0.0-W8-023.1，第 1/4 批）：`hook-system-reference.md`（Hook 事件索引 / 技術參考）、`code-smell-checklist.md`（Code Smell 檢測清單 / 技術參考）依二軸（受眾＝動作觸發者、形態＝技術參考）歸入既有 `references/` 載體列（line 22），故不另加 map 行；superseded 副本 `code-quality-examples.md`（已遷 `docs/`，DOC-010 W10-102）與 `document-responsibilities.md`（DEPRECATED，已被 `five-document-system-methodology.md` + `doc-flow/references/document-responsibilities.md` 取代）flag 不併入，留 PM follow-up
**Version**: 1.5.0 — 載體地圖補列 4 個 legit root 資產各一行歸屬（README 框架導覽 / CHANGELOG 變更記錄 / README-subtree-sync 同步機制 / terminology-dictionary 用語規範表，後者經 language-constraints `@` 引用實質載入）（1.0.0-W8-022）
**Version**: 1.4.0 — multi-round-review Round 4（實例分配演練）修正：步驟 1 補受眾詞彙映射橋（六選項 vs 地圖表受眾欄斷層）、步驟 3 事實類閘門判準明文化（體積與專案特定性約束，非必要性否決）。8 條盲跑 6 條乾淨落點，停止訊號達成收斂
**Version**: 1.3.0 — multi-round-review Round 3 修正：Scope 句（LLM context 載體限定 + 機器讀取層另計 + memory 受眾軸唯一決定）、rules/core 列量測集合精確化（MEMORY.md 不在 guardian 集合）、規範表補「多方案技術知識庫」劃界列（與 framework-asset-separation §1 對齊）、地圖補 templates / root 遺留行、Reference 補 skill-design-guide
**Version**: 1.2.0 — multi-round-review Round 2 修正：檢查清單與步驟 3/5 的 R1 劃界同步（清單漂移）、步驟 5 拆動作解歧義、地圖欄名補形態軸、定位句「（如有）」、Reference 補寫作 skill SSOT 例外路由
**Version**: 1.1.0 — multi-round-review Round 1 修正：步驟 3 形態約束劃界（規範類 vs 事實類）、步驟 5 補執法強度對齊、章名對齊 methodology 標準結構、rules/core 列預算範圍精確化、agents 列改路由至專節
**Version**: 1.0.0 — 初始建立：框架知識載體的頂層責任地圖（受眾 x 形態二軸），整合 W7 token 收斂三層防護與既有分離原則；代理人定義內容規範首次權威化（人格與授權 vs 可重複流程）
