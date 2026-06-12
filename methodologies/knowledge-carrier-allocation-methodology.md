# 知識載體責任分配方法論

## 核心概念

知識寫入框架前，依「**受眾 x 形態**」二軸決定載體。載體錯置有兩種代價：寫進自動載入層 → token 污染（attention 稀釋 + 45k 預算耗盡）；困在專案 memory → 跨專案失傳。本方法論是頂層地圖；各載體的細部規範（如有）路由至 Reference 所列文件。

**Scope**：本地圖涵蓋 LLM context 載體（人與 AI 閱讀的知識）；專案產物層（`docs/` / `src/`）不屬本地圖，劃分見 `framework-asset-separation.md`；機器讀取層（`config/*.yaml`、hook 引用的凍結錨點）另計。memory 行由受眾軸「僅本專案」唯一決定，不需形態軸。

**一句話判定**：代理人定義回答「你是誰、你能做什麼、你偏好怎麼做」；skill 回答「這件事怎麼做」。前者是人格與授權（換人即不同），後者是可重複流程（任何角色觸發應得到同一流程）。

## 載體地圖（受眾 x 載入時機 x 形態）

| 載體 | 受眾 | 載入時機 | 裝什麼（形態） | 不裝什麼（→ 正確去處） |
|------|------|---------|--------|----------------------|
| `CLAUDE.md` | 所有角色 | 每回合自動 | 專案身份、開發指令、專案級技術選型、路由 | 框架通用知識（→ `.claude/`，否則無法 sync） |
| `rules/core/` | 所有角色 | 每回合自動 | 行為禁令速查 + 路由（與 CLAUDE.md 同屬 file-size-guardian 45k 量測集合；MEMORY.md 每回合注入但不在量測集合內） | 論證 / 流程 / 案例（→ `references/`、`error-patterns/`） |
| `pm-rules/` | 僅 PM | 情境觸發按需 | 調度流程 SOP（派發、驗收、決策樹、skip-gate） | 代理人執行知識（→ agents / skills） |
| `agents/AGENT_PRELOAD.md` | 全體代理人 | 派發時 @ 注入 | 代理人通用行為禁令（ticket 操作、git 限制、工具選擇、嵌套協議） | 單一代理人偏好（→ 各 agent 定義）、PM 流程（→ pm-rules） |
| `agents/<name>.md` | 單一代理人 | 派發時載入 | 身份定位、三區塊（允許產出 / 禁止行為 / 適用情境）、設計偏好（命名習慣、技術手法傾向、文法語氣）、分工路由與升級條件 | → 見「代理人定義內容規範」節 |
| `skills/` | 觸發者（角色無關） | 觸發時漸進揭露 | 可重複執行的工作流、方法、CLI 工具（TDD、寫作、ticket、worktree） | 身份偏好（→ agents）、專案設定（→ CLAUDE.md） |
| `methodologies/` | 主動查閱者 | 按需 | 30 秒理念複習清單（核心概念 + 步驟 + 檢查清單） | 完整流程 / 範例 / 錯誤處理（→ skills） |
| `references/` | 執行特定動作者 | 按需 | 技術參考、規則 substance（auto-load stub 的完整版） | 每回合禁令（→ rules/core stub） |
| `error-patterns/` | ticket 前查詢者 | 按需 | 失敗案例（症狀 / 根因 / 解法 / 預防） | 規則正文（規則只放一行路由指向 PC/IMP） |
| memory（專案層） | 本專案 PM | MEMORY.md 每回合 | 專案特定活教訓的單行索引 | 已固化內容（升級即搬家）、跨專案原則（四問升級後外移） |
| `templates/`、`.claude/` root 歷史遺留檔 | （未分類） | 不自動載入 | — | 依本地圖二軸重分配（templates 內容須與對應規範同步，否則新實例從模板長出舊形態）；盤點另由 ticket 追蹤 |

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

- `.claude/methodologies/framework-meta-methodology.md` — skill / methodology / rule 三分決策樹 + 30 秒標準（形態軸的細分）
- `.claude/references/framework-asset-separation.md` — 框架資產 vs 專案產物、專案設定 vs 代理人知識、Skill Hook 雙層
- `.claude/references/auto-load-stub-conventions.md` — 自動載入層 stub 構成 + 外移 SOP + 預算驗證
- `.claude/rules/core/agent-definition-standard.md` — 代理人三區塊結構標準
- `.claude/rules/README.md` — 自動載入預算原則（每回合必要性自問）
- `.claude/pm-rules/pm-quality-baseline.md` 規則 7 — memory 升級四問 + 升級目的地預算閘門 + 升級即搬家
- `.claude/README.md`「同步機制」章 — 寫作類 skill（compositional-writing / multi-round-review）內容 SSOT 在 blog repo，框架端為回流副本；依地圖判定「寫作方法 → skills/」後，內容修改應到上游 repo 執行
- `.claude/skills/skill-design-guide/SKILL.md` — skills 載體的細部規範（官方規格、frontmatter、漸進揭露結構）

---

**Last Updated**: 2026-06-12
**Version**: 1.4.0 — multi-round-review Round 4（實例分配演練）修正：步驟 1 補受眾詞彙映射橋（六選項 vs 地圖表受眾欄斷層）、步驟 3 事實類閘門判準明文化（體積與專案特定性約束，非必要性否決）。8 條盲跑 6 條乾淨落點，停止訊號達成收斂
**Version**: 1.3.0 — multi-round-review Round 3 修正：Scope 句（LLM context 載體限定 + 機器讀取層另計 + memory 受眾軸唯一決定）、rules/core 列量測集合精確化（MEMORY.md 不在 guardian 集合）、規範表補「多方案技術知識庫」劃界列（與 framework-asset-separation §1 對齊）、地圖補 templates / root 遺留行、Reference 補 skill-design-guide
**Version**: 1.2.0 — multi-round-review Round 2 修正：檢查清單與步驟 3/5 的 R1 劃界同步（清單漂移）、步驟 5 拆動作解歧義、地圖欄名補形態軸、定位句「（如有）」、Reference 補寫作 skill SSOT 例外路由
**Version**: 1.1.0 — multi-round-review Round 1 修正：步驟 3 形態約束劃界（規範類 vs 事實類）、步驟 5 補執法強度對齊、章名對齊 methodology 標準結構、rules/core 列預算範圍精確化、agents 列改路由至專節
**Version**: 1.0.0 — 初始建立：框架知識載體的頂層責任地圖（受眾 x 形態二軸），整合 W7 token 收斂三層防護與既有分離原則；代理人定義內容規範首次權威化（人格與授權 vs 可重複流程）
