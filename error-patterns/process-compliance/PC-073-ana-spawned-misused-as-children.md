# PC-073: ANA 衍生 IMP Ticket 誤用 --parent 導致 children 關係，complete 時被 acceptance-gate 擋下

> **[DEPRECATED 部分內容]** 本檔對「ANA 衍生 IMP 應用 spawned 而非 children」的指引已於 2026-05-03 W17-120 多視角審查共識中被 PC-091 取代。**ANA 結論的執行延伸（IMP/DOC 落地）統一用 children（`--parent <ANA-ID>`）**，不再使用 spawned。
>
> 本檔保留的有效範圍：「執行 IMP/DOC 過程中發現的獨立技術債 / bug」應用 spawned（`--source-ticket`）。
>
> 權威語意：`.claude/skills/ticket/references/field-semantics.md`「用戶情境對照表」。

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-073 |
| 類別 | process-compliance |
| 風險等級 | 低（純操作問題，已知解法） |
| 首發時間 | 2026-04-17（W12-002 session） |
| 範圍變更 | 2026-05-03 W17-120 — 「ANA 衍生 IMP 用 spawned」段落 deprecated；現定位於「執行中發現獨立技術債」 |
| 姊妹模式 | PC-061（ticket migrate CLI bugs）、PC-091（ANA 落地用 children，取代本檔對 ANA 場景的指引） |

---

## 症狀

PM 執行 ANA 類型 Ticket 完成後，為其調查結論建立後續防護工作的 IMP Ticket 時：

1. 使用 `ticket create --parent {ANA-ID} ...` 建立衍生子 Ticket
2. CLI 將衍生 Ticket 設定為 ANA 的 `children`（父子關係）而非 `spawned_tickets`（衍生關係）
3. PM 執行 `ticket track complete {ANA-ID}` 時被 `acceptance-gate-hook` 擋下
4. 錯誤訊息：「子任務未全部完成：...（status: pending）請先完成所有子任務後再執行 complete」
5. PM 必須手動 Edit 5+ 個 ticket 檔案，清除 `parent_id`/`children` 並填 `source_ticket`，才能 complete ANA

---

## 與 PC-061 的區別

| 維度 | PC-061 migrate bugs | PC-073 spawned 誤用 |
|------|---------------------|---------------------|
| 觸發命令 | `ticket migrate` | `ticket create --parent` |
| 問題類型 | CLI 產生 typo / 未同步依賴 | CLI 將衍生關係誤設為父子關係 |
| 偵測時機 | 執行命令當下 | 後續 complete 時才發生 |
| 根因 | migrate 邏輯 bug | CLI 缺少 `--source-ticket` 參數，PM 只能用 `--parent` |

---

## 概念模型區分

權威定義見 `.claude/skills/ticket/references/field-semantics.md`「六欄位定義」與「阻擋語意對照表」。本節僅作快速對照。

| 關係類型 | frontmatter 欄位 | 語意 | complete 行為 |
|---------|-----------------|------|--------------|
| 父子（children） | `parent_id` + `children[]` | 必須一起交付，子未完成父無法 complete | acceptance-gate 擋父 complete（永遠） |
| 衍生（spawned） | `source_ticket` + `spawned_tickets[]` | 獨立排程的副產品 | 不影響非 ANA source 的 complete；對 ANA source 暫時阻擋（W15-003 升級，IMP 收斂後將回到「不阻擋」） |

**關鍵認知**（2026-05-03 修訂）：

- ANA Ticket 的 Solution 建議「後續 IMP 實作」→ **用 children（`--parent <ANA-ID>`）**，由 PC-091 規範
- 執行 ticket 過程中發現獨立 bug / 技術債 → **用 spawned（`--source-ticket <CURRENT>`）**，本檔保留範圍
- 父子關係應用於「功能拆分的 atomic sub-task」（必須一起交付完整功能）

---

## 根本原因

### 已驗證事實

1. **`ticket create --help` 無 `--source-ticket` 參數**：只有 `--parent`、`--blocked-by`、`--related-to`
2. **W12-002 實測**：用 `--parent 0.18.0-W12-002` 建立 W12-002.1~.4，CLI 自動設為 children
3. **Hook 攔截驗證**：acceptance-gate-hook 檢查 children 全部 completed 才允許 complete

### 真根因

1. **CLI 設計缺口（主因）**：`ticket create` 缺少 `--source-ticket` 參數對應 frontmatter 的 spawned 關係；PM 只能用 `--parent` 作為「關聯已建立 ticket」的手段
2. **命名混淆（次因）**：`--parent` 參數名暗示階層關係，但 ANA 衍生工作應為平行關係
3. **規則覆蓋缺失（連帶）**：ticket-lifecycle 或 skill 文件未明確指引「ANA 衍生 IMP 應用 spawned_tickets 而非 children」

---

## 常見陷阱模式

| 陷阱表述 | 為何仍構成違規或誤用 |
|---------|-------------------|
| 「ANA 產出的 IMP 也是子任務啊，用 --parent 直觀」 | 子任務 vs 衍生在 complete 語意上關鍵區別 |
| 「反正都是 W12 底下的，關係不重要」 | acceptance-gate 用 children 判定 complete 條件，關係決定流程 |
| 「complete 被擋了就手動 Edit frontmatter 吧」 | 可修但未記錄會反覆踩同一坑 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| CLI | 補 `--source-ticket {ANA-ID}` 參數，建立時直接設 source_ticket 關係 | 建議實施（另建 Ticket） |
| Hook | `ticket create --parent` 搭配 IMP-on-ANA 組合時警告：「衍生 IMP 應用 source_ticket，不應用 parent」 | 建議實施 |
| 規則 | pm-rules/ticket-lifecycle.md 新增章節「ANA 衍生工作的關係類型選擇」 | 建議實施 |
| 自檢 | 建 ANA 衍生 IMP 前自問：「這些 IMP 必須與 ANA 同時 complete 嗎？」否 → 用 spawned | 行為準則 |
| Memory | 原則保留 memory 作跨 session 索引 | 已實施（配對本檔） |

---

## 檢查清單（建立衍生 Ticket 前自我檢查）

> **2026-05-03 更新**：本清單適用於「執行中發現獨立技術債」場景。ANA 衍生 IMP/DOC 落地請改參考 PC-091 與 `.claude/skills/ticket/references/field-semantics.md`「欄位選擇決策樹」。

- [ ] 此衍生項是否為「執行當前 ticket 過程中發現的獨立 bug / 技術債」？是 → 用 spawned（`--source-ticket`）
- [ ] 此衍生項與當前 ticket 有獨立排程需求（不需同時 complete）？是 → spawned
- [ ] 若答案是「ANA 結論要求落地」→ 改用 children（`--parent <ANA-ID>`，遵 PC-091）
- [ ] 若答案是「功能拆分子任務必同時交付」→ 改用 children（`--parent`）

---

## 緊急修復步驟（已遇到此問題時）

1. Edit ANA Ticket 的 frontmatter：
   - `children: []` 清空
   - `spawned_tickets: [W{N}-XXX.1, ...]` 填入衍生 Ticket ID
2. Edit 每個衍生 Ticket 的 frontmatter：
   - `parent_id: null`
   - `source_ticket: {ANA-ID}`
3. 重試 `ticket track complete {ANA-ID}`

---

## 教訓

1. **CLI 能力缺口暴露時立即記錄，不是每次繞路**：本問題可能早已發生多次但未結構化記錄
2. **acceptance-gate Hook 的錯誤訊息是規則教學的機會**：應在訊息中指引「用 spawned 而非 children」的選項
3. **ticket CLI 改進 Ticket 分類**：PC-061（migrate）+ PC-073（create）提示 CLI 整體需要一次強化

---

## 象限歸類

本模式的防護屬 **摩擦力管理 A 象限（自動護欄）**：CLI 新增 `--source-ticket` 參數讓 spawned 關係一步到位，免去 PM 事後手動 Edit 5+ 檔案的代價。代價（單次 CLI 改進）遠低於收益（免去每個 ANA session 的反覆踩坑）。

---

## 相關文件

- `.claude/skills/ticket/references/field-semantics.md` — 六欄位語意 SSOT（含用戶情境對照表與決策樹）
- `.claude/error-patterns/process-compliance/PC-091-ana-followup-as-siblings-not-children.md` — ANA 落地用 children 規則（取代本檔對 ANA 的指引）
- `.claude/skills/ticket/SKILL.md` — ticket 工作流規範
- `.claude/pm-rules/ticket-lifecycle.md` — ticket 生命週期（「ANA Ticket 落地下游血緣選擇」章節）
- `.claude/config/ana-solution-schema.yaml` — ANA Solution Schema
- `.claude/hooks/acceptance-gate-hook.py` — 驗收閘門 Hook
- `.claude/error-patterns/process-compliance/PC-061-*.md` — 姊妹模式（migrate CLI bugs）

---

**Last Updated**: 2026-05-03
**Version**: 2.0.0 — W17-120 多視角審查共識：ANA 衍生 IMP 段落 deprecated，本檔範圍縮限為「執行中發現獨立技術債」。新增 deprecated 標註、姊妹模式 PC-091 引用、相關文件指向 field-semantics.md SSOT。
**Version**: 1.0.0 — 首發記錄（W12-002 session 事發當場）
**Source**: W12-002 建立 4 個 spawned IMP Ticket 時 CLI 誤設為 children 導致 ANA complete 被擋（v1.0）；W17-120 ANA 多視角審查（v2.0）
