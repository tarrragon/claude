# Ticket Skill 行為變更同步檢查規則

本文件規範 ticket skill 源碼（`.claude/skills/ticket/ticket_system/`）發生行為變更時，必須同步掃描決策層文件，防止行為層與決策層脫節。

> **來源**：本規則為 ANA 結論「採三層防護組合」中的 B 路徑（rules/core 規則補強），與 PC-118（A 路徑：error-pattern 描述層）+ commit-level sync-check hook（C 路徑：強制層）三者互補。

---

## 適用範圍

| 對象 | 是否觸發本規則 |
|------|--------------|
| PM 或代理人修改 `.claude/skills/ticket/ticket_system/*.py` | 是 |
| 修改 `.claude/skills/ticket/SKILL.md`、`.claude/rules/`、`.claude/pm-rules/` | 否（反向同步：若內容涉及 ticket CLI 行為，須人工確認與 src 一致） |

---

## 行為變更定義（規則 1 / 3 共同引用）

「行為變更」單一定義表：

| 改動類型 | 屬行為變更？ | 範例 |
|---------|------------|------|
| 新增 / 移除 / 重命名子命令 | 是 | `runqueue` 取代 `next` / `schedule` / `resume-hint`、`show` 子命令引入 |
| 變更 flag 必填性 / 預設值 / 語意 | 是 | `append-log` 加入 `--section` 必填 |
| 修改 `complete` / `claim` 條件 | 是 | type-aware body schema（IMP/ANA/DOC 各有必填章節） |
| 改變命令副作用（隱式前提） | 是 | Context Bundle 自動抽取（claim 時自動填入） |
| 純 bug fix（commit type=fix，不涉上述項目） | 否 | YAML 解析 None guard 補強、狀態轉移邏輯修正 |
| 輸出格式 / 對齊 / log level 調整 | 否 | terminal 對齊、欄位對齊（命令語意不變） |
| 測試程式碼改動 | 否 | 路徑不在 `ticket_system/` 下 |

**判別準則**：改動後依舊有流程文件中的命令形式操作，能得到等效結果 → 否；命令形式或語意改變 → 是。

---

## 強制規則

### 規則 1：行為變更必須觸發同步掃描

**觸發路徑**：對 `.claude/skills/ticket/ticket_system/*.py` 進行 Write / Edit，且改動命中上方「行為變更定義表」第 1-4 列。

**待掃描目標**：

| 目標文件 | 同步重點 |
|---------|---------|
| `.claude/skills/ticket/SKILL.md` | 子命令清單、flag 說明 |
| `.claude/pm-rules/decision-tree.md` | PM 決策路由（claim / complete / Re-center） |
| `.claude/pm-rules/*.md` | 情境 SOP（ticket-lifecycle / session-switching / handoff 等） |

**Why**：ticket skill 是 PM 操作 ticket 的唯一介面。子命令語意、flag 行為、complete 條件改變後，決策層引用若未同步，PM 執行既有流程會「靜默失效」——命令仍可執行但語意已不同。歷史已多次出現此類事後補償案例：原則性規則本應在行為設計階段建立，實際卻是事後補上。

**Consequence**：跳過同步掃描會讓決策層累積過時引用。過時引用不會直接報錯，後人照 SOP 操作會得到錯誤結果。補償成本隨時間遞增。

**Action**：

1. 完成 ticket skill src 改動後、commit 前，執行 `grep -rln "ticket track\|/ticket" .claude/skills/ticket/SKILL.md .claude/pm-rules/` 取得引用清單。
2. 對每個含 ticket CLI 引用的文件，依下表處理：

   | 文件狀態 | 動作 |
   |---------|------|
   | 引用仍對應現行行為（grep 命中項與 src 一致） | 無需改動 |
   | 引用舊命令名稱 / 舊 flag / 舊條件 | 當場更新，納入同一 commit |

3. 若同步更新跨越 ticket skill src + 多個 pm-rules 檔且預期 commit 體量過大，建立獨立 DOC Ticket 追蹤後再繼續。**禁止只口頭記錄「之後再更新」而不建立 Ticket**（違反 `quality-baseline.md` 規則 5）。

### 規則 2：歷史案例作為判別錨點

**Why**：「行為變更」概念抽象，需具體歷史案例作判別錨點，降低誤判（既有案例可直接對照新改動是否同類）。

**Consequence**：缺案例參考時，PM 易誤判某次修改為純修復而跳過掃描，事後補償成本高。

**Action**：歷史案例已併入「行為變更定義表」第 1-4 列範例欄位。看到類似性質改動時，依規則 1 觸發同步掃描。

### 規則 3：純修復型豁免

**Why**：純 bug fix 不影響命令形式或語意，全量掃描成本過高且無實際收益。

**Consequence**：無豁免會讓 PM 對小型修復產生規則疲勞，反而降低關鍵變更的掃描遵循度。

**Action**：依「行為變更定義表」第 5-7 列判別豁免；不確定時保守觸發掃描（規則 1）。豁免判別欄位分層：

| 判別維度 | 訊號 |
|---------|------|
| 實質判別（必要） | 命令形式 / 語意 / 副作用未改變（依行為變更定義表） |
| 輔助訊號（參考） | commit msg type 為 `fix`、改動範圍限 `tests/` 或輸出格式 |

實質判別優先，輔助訊號僅作快速分類提示。

---

## 同步掃描快速指令

```bash
# 確認 ticket skill src 改動範圍
git diff --name-only | grep ".claude/skills/ticket/ticket_system/"

# 找出所有含 ticket CLI 引用的決策層文件（規則 1 Action 第 1 步）
grep -rln "ticket track\|/ticket" .claude/skills/ticket/SKILL.md .claude/pm-rules/
```

---

## 與其他規則邊界

| 規則 | 聚焦 | 與本規則差異 |
|------|------|------------|
| `decision-trigger-binding.md` | 決策合法狀態（已決策 / 綁 ticket trigger 延後） | 聲明層；本規則為執行面同步機制 |
| `quality-baseline.md` 規則 5 | 所有發現必須追蹤（建 Ticket） | 本規則 Action 第 3 步直接援引 |
| `PC-118`（A 路徑） | 反模式描述（為何發生、歷史案例） | 事後描述層；本規則為事前規範 |
| `ticket-skill-sync-check-hook.py`（C 路徑，待實作） | commit-level 自動偵測 + 提醒 | 強制層；本規則為自律層；兩者互補，hook 兜底 |

---

## 檢查清單

修改 `.claude/skills/ticket/ticket_system/*.py` 前後確認：

- [ ] 改動性質依「行為變更定義表」分類（行為變更 vs 豁免）？
- [ ] 若屬行為變更，已執行同步掃描快速指令？
- [ ] 引用舊命令 / flag / 條件的文件已更新（或已建 DOC Ticket 追蹤）？
- [ ] commit msg type 正確反映性質（`feat` / `refactor` 行為變更 vs `fix` 純修復）？

---

## 相關文件

- `.claude/rules/core/decision-trigger-binding.md` — 決策合法狀態規則
- `.claude/rules/core/quality-baseline.md` 規則 5 — 所有發現必須追蹤
- `.claude/error-patterns/process-compliance/PC-118-ticket-skill-behavior-decision-tree-sync.md` — 反模式描述
- `.claude/hooks/ticket-skill-sync-check-hook.py` — commit-level 自動偵測 hook（C 路徑，待實作）

---

**Last Updated**: 2026-05-03
**Version**: 1.1.0 — 套用 multi-view review 修正：合併規則 1/3 重複條款為「行為變更定義表」單一來源、規則 2/3 補三明示、規則 1 觸發情境拆分為觸發路徑 + 定義引用、grep 指令去特定 keyword、刪「使用方式」廢話段、改 >5 文件閾值為定性條件、適用範圍第三列改為反向同步條款、Action 第 2 步條件分支表格化、規則 3 判別欄位分為實質 / 輔助雙層
**Version**: 1.0.0 — 初始建立（B 路徑落地）
