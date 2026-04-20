# Claim 簡化 WRAP 三問 — 詳細指引

本文件為 `ticket track claim` 認領 ticket 時，簡化 WRAP 三問（W/A/P）的詳細範例和 ticket 類型差異指南。

> **與 SKILL.md 的關係**：SKILL.md 定義「簡化 WRAP 三問（Claim 版）」章節為規則層，本文件提供實作層的填答範例和場景適配。CLI 層由 `.claude/skills/ticket/ticket_system/lib/command_tracking_messages.py` 的 `ClaimWrapMessages` 類別輸出三問提示，三處必須保持文案一致。

---

## 為什麼需要簡化三問

完整 WRAP 流程（錨點 + W/R/A/P + 絆腳索）約需 15-30 分鐘。若每次 claim 都執行完整流程，每版本會累積 3-10 小時純儀式時間，品質保護反而被稀釋為形式主義。

簡化三問取 W/A/P 三個核心品質閘門，每次 claim 約 1-2 分鐘可完成，作為最低品質門檻。R（Reality Test）階段留給 ANA 類型和已升級情境。

| 模式 | 耗時 | 觸發情境 | 階段 |
|------|------|---------|------|
| 簡化三問 | 1-2 分鐘 | 每次 claim（所有類型強制） | W + A + P |
| 快速模式 | 5 分鐘 | 被困住、連續失敗 | 錨點 + W + R 核心 + A 核心 |
| 完整模式 | 15-30 分鐘 | ANA、提案評估、重大決策 | 全 6 階段 |

---

## 三問填答範本

### W（Widen）—— 有其他做法嗎？

**問題**：至少列 2 個候選方案（含目前方案），確認選擇非默認值。

**填答要點**：

- 目前方案必須明確列為其中一個候選，不能「默認就是這樣」
- 至少一個替代方案需具體到「替代手段」而非「不做」
- 若替代方案全部指向同一假設根因（偽 Widen），應升級至完整模式檢查

**範本**：

```
W：
1. 目前方案：[描述目前計畫的做法]
2. 替代方案 A：[完全不同的做法，例如換工具/換策略/換時機]
3. （可選）替代方案 B：[再一個不同方向]
→ 確認選擇目前方案的理由：[為何勝出]
```

### A（Attain distance）—— 機會成本是什麼？

**問題**：執行這個 ticket 會擠壓哪個更重要的目標？

**填答要點**：

- 必須指向**具體的其他 ticket 或核心目標**，不能只寫「影響進度」
- 若機會成本 > 本 ticket 價值，暫停 claim，回到版本規劃重新排序
- 若答案是「無擠壓」（例如並行派發後的閒置時段），也必須明確寫出

**範本**：

```
A：
- 本 ticket 預估耗時：X tool call / Y 小時
- 擠壓目標：[其他 ticket ID 或核心目標]
- 不做本 ticket 的代價：[若延後會發生什麼]
```

### P（Prepare to be wrong）—— 最可能失敗的原因是什麼？

**問題**：行前預想 1 條：12 小時後失敗最可能的原因，對應防護措施。

**填答要點**：

- 寫「最可能失敗」的單一原因，避免列出 3 個模糊風險
- 必須包含對應的防護措施（context bundle、reference 讀取、測試項）
- 若失敗可能性 > 50%，升級至完整模式補 Reality Test

**範本**：

```
P：
- 12 小時後最可能失敗原因：[具體場景，例如「代理人沒讀 X 文件導致措辭偏離」]
- 防護措施：[context bundle 內容 / 驗收條件 / 參考文件]
```

---

## Ticket 類型差異

不同 ticket 類型的三問重點差異如下：

### IMP（實作型）

| 問 | 重點 |
|----|------|
| W | 檢查是否有既有 API/工具可直接用，而非硬寫新程式碼 |
| A | 機會成本常為「擠壓其他 ticket 實作時間」 |
| P | 失敗常因為「誤改既有測試」「改錯檔案」「scope 蔓延」 |

**範例**（IMP ticket：修改 CLI 輸出文案）：

```
W：
1. 目前方案：修改 command_tracking_messages.py 新增 ClaimWrapMessages 類別
2. 替代方案：純字串常數散落在 track.py 內聯（較差，違反 DRY）
→ 選擇目前方案：與既有訊息常數化模式一致

A：
- 預估 1-2 hr TDD
- 擠壓 W10-029（SKILL 層對齊）和 W10-031（規則層）
- 不做代價：後續 claim 時缺少強制品質 checkpoint

P：
- 最可能失敗：thyme 測試設計偏離 W10-027 指定三問文字
- 防護：派發 prompt 明確貼出三問全文
```

### ANA（分析型）

| 問 | 重點 |
|----|------|
| W | **必須升級至完整 WRAP**，簡化三問不足以保證分析品質 |
| A | 機會成本常為「擠壓實作時間」，但分析品質偏差代價更大 |
| P | 失敗常因為「假設根因未驗證」「Reality Test 流於形式」 |

**ANA 類型專屬要求**：CLI 層的 `ClaimWrapMessages.ANA_EXTRA_BODY` 會額外提示執行完整 /wrap-decision。不要只答簡化三問就開始分析，必須跑完 R 階段的 Reality Test（參考 PC-063 偽 Widen 防護）。

**範例**（ANA ticket：分析代理人失敗根因）：

```
W（升級至完整）：
- 列出當前接受的根因假設
- 三層質疑（質疑根因、質疑問題框架、質疑場景）
- Reality Test 每個假設
- 基於驗證後的根因列方案
→ 詳見 SKILL.md「偽 Widen vs 真 Widen」章節

A：
- 分析預估 2-4 hr，擠壓 W10-XXX 實作
- 不做代價：誤判根因導致後續修復全部脫靶（PC-063 教訓）

P：
- 最可能失敗：跳過重現實驗即列方案
- 防護：Ticket 內明確要求「重現實驗結果」章節
```

### DOC（文件型）

| 問 | 重點 |
|----|------|
| W | 檢查是否已有類似文件可改寫，而非新建 |
| A | 機會成本常為「擠壓程式碼實作」，但文件債務會累積跨版本 |
| P | 失敗常因為「與既有 CLI/程式碼文案不對齊」「規則衝突未檢查」 |

**範例**（DOC ticket：新增 SKILL 章節）：

```
W：
1. 目前方案：SKILL.md 新增「簡化三問」章節 + reference 詳細範例
2. 替代方案：只在 reference 加內容不改 SKILL（較差，觸發條件表會失真）
3. 替代方案：合併到主流程章節（較差，違反簡化版獨立識別）
→ 選擇目前方案：規則層與 CLI 層雙錨點

A：
- 預估 8-12 tool call
- 擠壓 W10-009 Phase 3b 派發空間，但本 ticket 短，可序列接續

P：
- 最可能失敗：簡化三問措辭與 CLI 輸出不一致
- 防護：context bundle 要求先讀 W10-028 ticket 確認 CLI 文案
```

---

## 文案來源對照（三處一致性）

簡化三問在三個位置必須保持文字一致，修改任一處時必須同步更新其他兩處：

| 位置 | 內容 | 維護責任 |
|------|------|---------|
| `.claude/skills/ticket/ticket_system/lib/command_tracking_messages.py` 的 `ClaimWrapMessages` | CLI 層輸出文字（Source of Truth） | ticket skill 維護 |
| `.claude/skills/wrap-decision/SKILL.md`「簡化 WRAP 三問（Claim 版）」章節 | 規則層對照 | wrap-decision skill 維護 |
| 本文件（`references/claim-quick-wrap.md`） | 實作層範例 | wrap-decision skill 維護 |

**驗證方式**：三處的「W（Widen）—— 有其他做法嗎？」「A（Attain distance）—— 機會成本是什麼？」「P（Prepare to be wrong）—— 最可能失敗的原因是什麼？」三問主標題文字必須逐字一致。

---

## 常見反模式

| 反模式 | 症狀 | 正確做法 |
|-------|------|---------|
| 假答題 | W 只寫「目前方案 vs 不做」當作兩個候選 | 替代方案必須是「不同做法」，而非「做或不做」 |
| 偽 Widen | W 的候選方案全部改同一檔案/指向同一根因 | 升級完整模式檢查假設層級多元性 |
| 機會成本空白 | A 只寫「無擠壓」但實際有並行 ticket | 明確寫出具體 ticket ID 或核心目標 |
| P 流於形式 | P 寫「可能有 bug」「可能失敗」 | 必須寫具體場景 + 防護措施 |
| 跳過三問 | 直接 claim 開始工作，事後補答 | 三問必須在 claim 後、執行前寫入 Problem Analysis 或 commit message |

---

## 與其他 Skill 的銜接

| 銜接場景 | 操作 |
|---------|------|
| 三問答不出來 | 升級至快速/完整模式 WRAP |
| ANA 類型 | 直接走完整 WRAP（CLI 會額外提示） |
| 答題發現需拆分 ticket | 釋放 ticket → 執行 /tdd split 或 task splitting |
| 答題發現有歷史經驗 | 查詢 `/error-pattern query` 確認既有防護 |
| 答題發現需多方評估 | 升級至 DDF（/design-decision-framework）|

---

**Last Updated**: 2026-04-15
**Version**: 1.0.0 — 初始建立，對應 W10-029 Claim 層簡化三問規則落地
**Source**: W10-027 Atomic Ticket Claim Checkpoint 分析 + W10-028 CLI 文案
