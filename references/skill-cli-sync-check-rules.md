# Skill CLI 行為變更同步檢查規則

本文件規範專案內具 CLI 入口點的 skill 源碼發生行為變更時，必須同步掃描該 skill 的決策層文件，防止行為層與決策層脫節。

> **來源**：本規則前身為 ticket 專屬版本（ANA 結論「採三層防護組合」中的 B 路徑），0.2.1-W3-239 依 0.2.1-W3-136 ANA 結論泛化涵蓋範圍，與 PC-118（A 路徑：error-pattern 描述層）+ commit-level sync-check hook（C 路徑：強制層）三者互補。

---

## 適用範圍

**涵蓋 skill 清單**（0.2.1-W3-136 ANA 盤點，共 7 個具 CLI 入口點的 skill）：

| Skill | Src prefix | 決策層同步目標 |
|-------|-----------|---------------|
| ticket | `.claude/skills/ticket/ticket_system/` | `.claude/pm-rules/`、`.claude/skills/ticket/SKILL.md` |
| doc | `.claude/skills/doc/doc_system/` | `.claude/skills/doc/SKILL.md` |
| skill-sync | `.claude/skills/skill-sync/skill_sync/` | `.claude/skills/skill-sync/SKILL.md` |
| worktree | `.claude/skills/worktree/scripts/` | `.claude/skills/worktree/SKILL.md` |
| version-release | `.claude/skills/version-release/scripts/` | `.claude/skills/version-release/SKILL.md` |
| project-init | `.claude/skills/project-init/project_init/` | `.claude/skills/project-init/SKILL.md` |
| mermaid-ascii | `.claude/skills/mermaid-ascii/mermaid_ascii/` | `.claude/skills/mermaid-ascii/SKILL.md` |

> ticket 額外含 `.claude/pm-rules/` 為同步目標，因其為 PM 操作的決策層唯一介面；其餘 skill 僅以自身 `SKILL.md` 為同步目標。清單以 hook 內 `SKILL_CLI_REGISTRY` 為 single source of truth，本表為易讀鏡像，新增 CLI skill 時兩處需同步更新。

| 對象 | 是否觸發本規則 |
|------|--------------|
| PM 或代理人修改任一表列 skill 的 src prefix 下檔案 | 是 |
| 修改對應的 `SKILL.md`、`.claude/rules/`、`.claude/pm-rules/` | 否（反向同步：若內容涉及該 skill CLI 行為，須人工確認與 src 一致） |

---

## 行為變更定義（規則 1 / 3 共同引用）

「行為變更」單一定義表：

| 改動類型 | 屬行為變更？ | 範例 |
|---------|------------|------|
| 新增 / 移除 / 重命名子命令 | 是 | ticket `runqueue` 取代 `next` / `schedule`；skill-sync `pull-all` 行為調整 |
| 變更 flag 必填性 / 預設值 / 語意 | 是 | `append-log` 加入 `--section` 必填 |
| 修改核心動作條件（如 `complete` / `claim`） | 是 | type-aware body schema（IMP/ANA/DOC 各有必填章節） |
| 改變命令副作用（隱式前提） | 是 | Context Bundle 自動抽取（claim 時自動填入） |
| 純 bug fix（commit type=fix，不涉上述項目） | 否 | YAML 解析 None guard 補強、狀態轉移邏輯修正 |
| 輸出格式 / 對齊 / log level 調整 | 否 | terminal 對齊、欄位對齊（命令語意不變） |
| 測試程式碼改動 | 否 | 路徑不在該 skill src prefix 下 |

**判別準則**：改動後依舊有流程文件中的命令形式操作，能得到等效結果 → 否；命令形式或語意改變 → 是。

---

## 強制規則

### 規則 1：行為變更必須觸發同步掃描

**觸發路徑**：對任一表列 skill 的 src prefix 下檔案進行 Write / Edit，且改動命中上方「行為變更定義表」第 1-4 列。

**待掃描目標**：依「適用範圍」表該 skill 對應的「決策層同步目標」欄位；ticket 額外含 `.claude/pm-rules/*.md`（決策路由與情境 SOP）。

**Why**：CLI skill 是操作者（PM 或其他代理人）與該功能互動的唯一介面。子命令語意、flag 行為、核心動作條件改變後，決策層引用若未同步，操作者執行既有流程會「靜默失效」——命令仍可執行但語意已不同。0.2.1-W3-131 skill-sync 案例已實證：`cmd_pull_all` 行為變更後 `SKILL.md` 描述過期，全程無提示。

**Consequence**：跳過同步掃描會讓決策層累積過時引用。過時引用不會直接報錯，後人照 SOP 操作會得到錯誤結果。補償成本隨時間遞增。

**Action**：

1. 完成 skill src 改動後、commit 前，依變更的 skill 執行：
   ```bash
   grep -rln "<skill CLI 關鍵字>" <該 skill 的 SKILL.md> [.claude/pm-rules/ 如為 ticket]
   ```
2. 對每個含該 skill CLI 引用的文件，依下表處理：

   | 文件狀態 | 動作 |
   |---------|------|
   | 引用仍對應現行行為（grep 命中項與 src 一致） | 無需改動 |
   | 引用舊命令名稱 / 舊 flag / 舊條件 | 當場更新，納入同一 commit |

3. 若同步更新跨越 skill src + 多個決策層檔且預期 commit 體量過大，建立獨立 DOC Ticket 追蹤後再繼續。**禁止只口頭記錄「之後再更新」而不建立 Ticket**（違反 `quality-baseline.md` 規則 5）。

### 規則 2：歷史案例作為判別錨點

**Why**：「行為變更」概念抽象，需具體歷史案例作判別錨點，降低誤判（既有案例可直接對照新改動是否同類）。

**Consequence**：缺案例參考時，操作者易誤判某次修改為純修復而跳過掃描，事後補償成本高。

**Action**：歷史案例已併入「行為變更定義表」第 1-4 列範例欄位。看到類似性質改動時，依規則 1 觸發同步掃描。

### 規則 3：純修復型豁免

**Why**：純 bug fix 不影響命令形式或語意，全量掃描成本過高且無實際收益。

**Consequence**：無豁免會讓操作者對小型修復產生規則疲勞，反而降低關鍵變更的掃描遵循度。

**Action**：依「行為變更定義表」第 5-7 列判別豁免；不確定時保守觸發掃描（規則 1）。豁免判別欄位分層：

| 判別維度 | 訊號 |
|---------|------|
| 實質判別（必要） | 命令形式 / 語意 / 副作用未改變（依行為變更定義表） |
| 輔助訊號（參考） | commit msg type 為 `fix`、改動範圍限 `tests/` 或輸出格式 |

實質判別優先，輔助訊號僅作快速分類提示。

### 規則 4：新增 CLI skill 須同步更新 registry

**Why**：hook 的偵測範圍以 `SKILL_CLI_REGISTRY`（顯式清單）為準，非自動推導（0.2.1-W3-136 ANA 已排除 pyproject.toml 自動推導方案，因 src layout 不統一）。新增具 CLI 入口點的 skill 若未同步登記，該 skill 將不受本規則與 hook 保護。

**Consequence**：registry 與實際 CLI skill 清單脫節時，防護語意雖成立但實作不覆蓋，重演 0.2.1-W3-136 發現的落差。

**Action**：新增 skill 的 `pyproject.toml` 含 `[project.scripts]` 入口點且 `SKILL.md` 含命令行為描述時，同步在 `.claude/hooks/skill-cli-sync-check-hook.py` 的 `SKILL_CLI_REGISTRY` 新增一條（name / src_prefix / sync_targets），並同步更新本文件「適用範圍」表。

---

## 同步掃描快速指令

```bash
# 確認某 skill src 改動範圍（以 ticket 為例，代入其他 skill 的 src prefix 亦可）
git diff --name-only | grep ".claude/skills/ticket/ticket_system/"

# 找出該 skill 對應決策層文件中含 CLI 引用者（規則 1 Action 第 1 步，ticket 範例）
grep -rln "ticket track\|/ticket" .claude/skills/ticket/SKILL.md .claude/pm-rules/
```

---

## 與其他規則邊界

| 規則 | 聚焦 | 與本規則差異 |
|------|------|------------|
| `decision-trigger-binding.md` | 決策合法狀態（已決策 / 綁 ticket trigger 延後） | 聲明層；本規則為執行面同步機制 |
| `quality-baseline.md` 規則 5 | 所有發現必須追蹤（建 Ticket） | 本規則 Action 第 3 步直接援引 |
| `PC-118`（A 路徑） | 反模式描述（為何發生、歷史案例，原以 ticket 為例） | 事後描述層；本規則為事前規範 |
| `skill-cli-sync-check-hook.py`（C 路徑） | commit-level 自動偵測 + 提醒，涵蓋 registry 內全部 skill | 強制層；本規則為自律層；兩者互補，hook 兜底 |

---

## 檢查清單

修改任一表列 skill 的 src 前後確認：

- [ ] 改動性質依「行為變更定義表」分類（行為變更 vs 豁免）？
- [ ] 若屬行為變更，已執行同步掃描快速指令（代入對應 skill 的路徑與關鍵字）？
- [ ] 引用舊命令 / flag / 條件的文件已更新（或已建 DOC Ticket 追蹤）？
- [ ] commit msg type 正確反映性質（`feat` / `refactor` 行為變更 vs `fix` 純修復）？
- [ ] 若新增具 CLI 入口點的 skill，已同步登記 `SKILL_CLI_REGISTRY` 與本文件「適用範圍」表（規則 4）？

---

## 相關文件

- `.claude/rules/core/decision-trigger-binding.md` — 決策合法狀態規則
- `.claude/rules/core/quality-baseline.md` 規則 5 — 所有發現必須追蹤
- `.claude/error-patterns/process-compliance/PC-118-ticket-skill-behavior-decision-tree-sync.md` — 反模式描述（原以 ticket 為例，語意適用全部 CLI skill）
- `.claude/hooks/skill-cli-sync-check-hook.py` — commit-level 自動偵測 hook（C 路徑，含 7-skill registry）

---

**Last Updated**: 2026-08-04
**Version**: 2.0.0 — 依 0.2.1-W3-136 ANA 結論泛化涵蓋範圍由 ticket 單一 skill 擴至 7 個具 CLI 入口點的 skill；新增規則 4（新增 CLI skill 須同步登記 registry）；改名自 `ticket-skill-sync-check-rules.md`（0.2.1-W3-239）
**Version**: 1.1.0 — 套用 multi-view review 修正：合併規則 1/3 重複條款為「行為變更定義表」單一來源、規則 2/3 補三明示、規則 1 觸發情境拆分為觸發路徑 + 定義引用、grep 指令去特定 keyword、刪「使用方式」廢話段、改 >5 文件閾值為定性條件、適用範圍第三列改為反向同步條款、Action 第 2 步條件分支表格化、規則 3 判別欄位分為實質 / 輔助雙層
**Version**: 1.0.0 — 初始建立（B 路徑落地）
