# PC-073: ANA 衍生 IMP Ticket 誤用 --parent 導致 children 關係，complete 時被 acceptance-gate 擋下

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-073 |
| 類別 | process-compliance |
| 風險等級 | 低（純操作問題，已知解法） |
| 首發時間 | 2026-04-17（W12-002 session） |
| 姊妹模式 | PC-061（ticket migrate CLI bugs） |

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

| 關係類型 | frontmatter 欄位 | 語意 | complete 行為 |
|---------|-----------------|------|--------------|
| 父子（children） | `parent_id` + `children[]` | 必須一起交付，子未完成父無法 complete | acceptance-gate 擋父 complete |
| 衍生（spawned） | `source_ticket` + `spawned_tickets[]` | 不同交付時機，衍生項獨立排程 | 不影響 source complete |

**關鍵認知**：
- ANA Ticket 的 Solution 建議「後續 IMP 實作」→ 這是**衍生**關係（ANA 完成後 IMP 可延後執行）
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

## 檢查清單（PM 建立 ANA 衍生工作前自我檢查）

- [ ] 這些衍生 Ticket 是否必須與 ANA 同時 complete？否 → 用 spawned 關係
- [ ] 衍生 Ticket 是否有獨立的執行時機 / 延後到後續版本的可能？是 → 用 spawned
- [ ] 若用 `--parent`，是否已確認會觸發 children 關係？是 → 改用手動 Edit frontmatter 的 source_ticket
- [ ] ANA complete 時是否希望衍生 Ticket 可獨立存在？是 → spawned

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

- `.claude/skills/ticket/SKILL.md` — ticket 工作流規範
- `.claude/pm-rules/ticket-lifecycle.md` — ticket 生命週期
- `.claude/config/ana-solution-schema.yaml` — ANA Solution Schema
- `.claude/hooks/acceptance-gate-hook.py` — 驗收閘門 Hook
- `.claude/error-patterns/process-compliance/PC-061-*.md` — 姊妹模式（migrate CLI bugs）

---

**Last Updated**: 2026-04-17
**Version**: 1.0.0 — 首發記錄（W12-002 session 事發當場）
**Source**: W12-002 建立 4 個 spawned IMP Ticket 時 CLI 誤設為 children 導致 ANA complete 被擋
