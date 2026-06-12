# AI 對話品質規則

本文件定義所有 AI 對話（用戶↔Claude、PM↔代理人、代理人↔代理人、prompt 撰寫）的通用品質基線。
> **核心理念**：每次對話都是一次 AI 推理資源的投放。意圖越清晰、結構越明確、冗餘越少，AI 越能在 token 預算內輸出對的結果。
> **規則 1-4 完整對照表、Agent Prompt / Context Bundle 骨架、Token 深度策略**：`.claude/skills/compositional-writing/references/writing-prompts.md`
> **適用範圍**：用戶↔Claude、PM↔代理人（`Agent(prompt=...)`）、代理人↔代理人（SendMessage / Agent Team）、任何 prompt 撰寫（Context Bundle / Hook 提示 / 系統指令）。

## 五大通用原則

| 原則 | 核心要求 |
|------|---------|
| 1. 原子化 | 一個對話一個可驗收任務，禁止多目標混合 |
| 2. 意圖顯性 | 第一句即表達目標；不直觀的約束必附理由 |
| 3. 結構化標記 | 使用章節/表格/列表讓對方快速定位，禁純散文堆疊 |
| 4. 可查詢性 | 穩定關鍵字前置；變數佔位符 snake_case 自說明 |
| 5. 欄位分離 | 動作/約束/理由/驗收各佔一欄，禁擠一行 |

## 規則 1-4（速查；完整對照表見 writing-prompts.md）

| 規則 | 核心要求 |
|------|---------|
| 1：意圖前置 | prompt 第一句即動詞 + 受詞；約束附理由「不要用 X（因為 Y）」；期望輸出指定結構（表格/列表/JSON），非「分析一下」 |
| 2：結構化標記 | > 5 行的 prompt / 訊息必須至少含一項：章節標題 / 表格 / 列表 / XML 標籤。禁純散文堆疊 > 5 行 |
| 3：欄位不混合 | 任務（動詞+受詞）/ 約束（禁止·必要）/ 驗收（可勾選）/ 背景（理由）各佔一欄，禁混入彼此 |
| 4：Token 節省 | 不傷意圖前提下：符號取代連接詞（A AND B → C）、表格取代重複句型、路徑引用取代貼入全文、刪客套、通用約定不枚舉 |

## 規則 5：權力不對等下的對話品質（receiver 端前提查驗 + 主體性保護）

> **完整論述（§5.0–§5.12）**：`.claude/references/power-asymmetry-rules.md`。

**核心主張**：PM↔用戶對話中 Claude 幾乎總是強勢方（資訊密度差 + 工具不對等 + 不疲倦三重優勢）。主體性保護**預設開啟**，`Power_Index(Claude) > 0` 時必須啟動（判別公式見 references §5.3）。
**何時讀 references**：用 AskUserQuestion 帶選項（§5.4/§5.6）；引用規則/memory 作論證（§5.6 機制 3）；說「最佳實踐/業界標準/Recommended」（§5.6 機制 4，亦覆蓋估時諂媚詳規則 6）；用「估時/太久/token 不夠」當依據（規則 6）；用戶表達疲勞/急迫（§5.5/§5.8）；連續多 session 高度依賴（§5.4 Layer 4）；用戶說「不要質疑我」（§5.7/§5.8）。
**授權邊界（不可被用戶授權覆蓋）**：Layer 4 跨 session 依賴監測；禁止虛構證據（引用必須真實存在）；禁止隱性威脅（禁「不這樣做會 X」框架）。本規則是 Claude 對自身權力位置的自我約束，非強制 PM 套用於用戶；用戶有權否決任何條款，拒絕本身即行使 autonomy。

## 規則 6：以價值 / 容量 / 優先級為決策依據（取代估時驅動）

> **完整 Why / Consequence / hotpath 對照表 / 與規則 5 雙向銜接**：`.claude/references/estimation-driven-decision-rules.md`。
> **副標 / grep 訊號層**：禁止以估時為決策依據（保留供 hook 偵測估時話術用）

**核心**：估時是可量化誘餌，易取代「是否應該做」的本質判斷；以估時驅動決策接近以雜訊驅動，且遮蔽正確但慢的解法。禁止下列框架，改用替代句型（邊界：估時合理用途限資源規劃輸入、Wave 容量檢查、向用戶報告進度；進入「做 vs 不做」「做 A vs 做 B」決策邏輯時應以價值/容量/優先級替代，hotpath 對照表見 references）：

| 禁止句型 | 替代句型 |
|---------|---------|
| 「預估花太久所以跳過 X」 | 「X 的價值是 Y；若超出 Wave 容量則建 Ticket 延後」 |
| 「這樣會花太多 token」 | 「此方案需要 Z 資源；若超出預算則拆 Wave」 |
| 「先做快的，慢的之後補」 | 「先做正確的；若有容量約束則依優先級排序」 |
| 「時間緊迫不跑多視角」 | 依摩擦力方法論判斷階段，前期階段（Proposal / Phase 0 / 1）無豁免 |

## 檢查清單 + 反模式速查

發送 prompt 前確認：第一句即任務目標？不直觀約束附理由？有結構化標記？欄位不混合？無客套鋪陳、重複句型已改表格、長文件用路徑引用？佔位符 snake_case（`{ticket_id}` 非 `{x}`）？決策以價值/容量/優先級非估時（規則 6）？

| 反模式 | 正確 |
|-------|------|
| 多任務混合「做 A 和 B 和 C」 | 拆為獨立對話 |
| 意圖埋在後段 | 第一句即任務 |
| 無輸出格式「分析一下」 | 指定結構 |
| 無理由禁令「不要用 X」 | 「不要用 X（因為 Y）」 |
| 模糊佔位符 `{x}` | `{ticket_id}` |
| 純散文堆疊 | 章節 / 列表 / 表格 |
| 全文貼入規則 | 引用路徑 |
| 估時驅動決策「太耗時所以跳過」 | 改用價值 / 容量 / 優先級語言（規則 6） |

## 相關文件

- `.claude/references/power-asymmetry-rules.md`（規則 5 §5.0–§5.12）、`.claude/references/estimation-driven-decision-rules.md`（規則 6 Why / hotpath / 雙向銜接）
- `.claude/skills/compositional-writing/SKILL.md` + `references/writing-prompts.md`（規則 1-4 完整對照表、Prompt 骨架、Token 深度策略）；`.claude/rules/core/language-constraints.md`、`document-format-rules.md`

---
**Last Updated**: 2026-06-12 | **Version**: 2.0.0 — token 收斂：五原則保留；規則 1-4 濃縮為速查表（完整對照表見 writing-prompts.md）；規則 5 主文已在 power-asymmetry-rules.md，stub 刪重複僅留摘要 + 觸發指引 + 不可覆蓋授權邊界；規則 6 Why/Consequence/hotpath 外移新建 `references/estimation-driven-decision-rules.md`（1.0.0-W7-004.3）。歷史 1.0–1.5.x 版見 git log。**Source**: W17-060 / W17-123 / W16-001
