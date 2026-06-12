# 知識載體責任分配方法論

## 核心概念

知識寫入框架前，依「**受眾 x 形態**」二軸決定載體。載體錯置有兩種代價：寫進自動載入層 → token 污染（attention 稀釋 + 45k 預算耗盡）；困在專案 memory → 跨專案失傳。本方法論是頂層地圖；各載體的細部規範路由至 Reference 所列文件。

**一句話判定**：代理人定義回答「你是誰、你能做什麼、你偏好怎麼做」；skill 回答「這件事怎麼做」。前者是人格與授權（換人即不同），後者是可重複流程（任何角色觸發應得到同一流程）。

## 載體地圖（受眾 x 載入時機 x 內容）

| 載體 | 受眾 | 載入時機 | 裝什麼 | 不裝什麼（→ 正確去處） |
|------|------|---------|--------|----------------------|
| `CLAUDE.md` | 所有角色 | 每回合自動 | 專案身份、開發指令、專案級技術選型、路由 | 框架通用知識（→ `.claude/`，否則無法 sync） |
| `rules/core/` | 所有角色 | 每回合自動 | 行為禁令速查 + 路由（受 45k 預算） | 論證 / 流程 / 案例（→ `references/`、`error-patterns/`） |
| `pm-rules/` | 僅 PM | 情境觸發按需 | 調度流程 SOP（派發、驗收、決策樹、skip-gate） | 代理人執行知識（→ agents / skills） |
| `agents/AGENT_PRELOAD.md` | 全體代理人 | 派發時 @ 注入 | 代理人通用行為禁令（ticket 操作、git 限制、工具選擇、嵌套協議） | 單一代理人偏好（→ 各 agent 定義）、PM 流程（→ pm-rules） |
| `agents/<name>.md` | 單一代理人 | 派發時載入 | 身份定位、三區塊（允許產出 / 禁止行為 / 適用情境）、設計偏好（命名習慣、技術手法傾向、文法語氣）、分工路由與升級條件 | 操作流程步驟（→ skills）、品質規則全文（→ references 路由）、錯誤案例全文（→ error-patterns 路由） |
| `skills/` | 觸發者（角色無關） | 觸發時漸進揭露 | 可重複執行的工作流、方法、CLI 工具（TDD、寫作、ticket、worktree） | 身份偏好（→ agents）、專案設定（→ CLAUDE.md） |
| `methodologies/` | 主動查閱者 | 按需 | 30 秒理念複習清單（核心概念 + 步驟 + 檢查清單） | 完整流程 / 範例 / 錯誤處理（→ skills） |
| `references/` | 執行特定動作者 | 按需 | 技術參考、規則 substance（auto-load stub 的完整版） | 每回合禁令（→ rules/core stub） |
| `error-patterns/` | ticket 前查詢者 | 按需 | 失敗案例（症狀 / 根因 / 解法 / 預防） | 規則正文（規則只放一行路由指向 PC/IMP） |
| memory（專案層） | 本專案 PM | MEMORY.md 每回合 | 專案特定活教訓的單行索引 | 已固化內容（升級即搬家）、跨專案原則（四問升級後外移） |

## 寫入決策步驟

1. **受眾是誰**？（所有角色 / 僅 PM / 全體代理人 / 單一代理人 / 動作觸發者 / 僅本專案）→ 縮小候選載體
2. **形態是什麼**？（行為禁令 / 調度流程 / 身份偏好 / 工作流方法 / 理念清單 / 技術參考 / 失敗案例 / 專案設定）→ 確定載體
3. 候選屬**自動載入層**（CLAUDE.md / rules/ / MEMORY.md）？→ 過預算閘門（「這是否每回合都需要？」）+ 形態降為「禁令 + 路由」
4. skill / methodology / rule 三選一拿不準 → `framework-meta-methodology.md` 決策樹
5. 寫完 grep 概念詞，盤點與既有規範的指令方向矛盾（PC-V1-006）

## 代理人定義內容規範

| 該裝 | 不該裝（外移路由） |
|------|------------------|
| 身份定位與核心使命 | — |
| 三區塊：允許產出 / 禁止行為 / 適用情境 | — |
| 設計偏好：命名習慣、技術手法傾向、文法語氣 | 專案級技術選型（→ CLAUDE.md；代理人帶多方案知識，依專案設定選用） |
| 分工路由與升級條件（與誰分工、何時上報） | 操作流程步驟（→ 對應 skill，流程與人格解耦） |
| 品質標準的章節路由（如 quality-common 指定章節） | 品質清單全文（複製即漂移，單一來源失效） |
| 錯誤模式的一行路由（「詳見 IMP-XXX」） | 錯誤案例全文（error-pattern 才是案例的家） |

## 檢查清單

- [ ] 受眾 x 形態二軸定位完成，不是「順手寫在打開的檔案」？
- [ ] 自動載入層寫入已過預算閘門，形態為禁令 + 路由？
- [ ] 代理人定義新增內容屬「偏好 / 邊界」而非「流程 / 方法」？
- [ ] 重複內容用路由取代複製（單一來源）？
- [ ] 概念詞 grep 矛盾盤點完成（PC-V1-006）？

## Reference

- `.claude/methodologies/framework-meta-methodology.md` — skill / methodology / rule 三分決策樹 + 30 秒標準（形態軸的細分）
- `.claude/references/framework-asset-separation.md` — 框架資產 vs 專案產物、專案設定 vs 代理人知識、Skill Hook 雙層
- `.claude/references/auto-load-stub-conventions.md` — 自動載入層 stub 構成 + 外移 SOP + 預算驗證
- `.claude/rules/core/agent-definition-standard.md` — 代理人三區塊結構標準
- `.claude/rules/README.md` — 自動載入預算原則（每回合必要性自問）
- `.claude/pm-rules/pm-quality-baseline.md` 規則 7 — memory 升級四問 + 升級目的地預算閘門 + 升級即搬家

---

**Last Updated**: 2026-06-12
**Version**: 1.0.0 — 初始建立：框架知識載體的頂層責任地圖（受眾 x 形態二軸），整合 W7 token 收斂三層防護與既有分離原則；代理人定義內容規範首次權威化（人格與授權 vs 可重複流程）
