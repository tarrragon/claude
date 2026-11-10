# 版本發布前檢討流程（Version Retrospective）

本文件定義版本發布前的標準化開發經驗回收機制。

---

## 目的

每個版本開發過程中累積的經驗教訓（error patterns、工作流程改善、規範缺漏）應在發布前結構化地整合回專案規範和代理人設定，避免同類問題反覆出現。

---

## 觸發時機

在執行期的結束點、`/version-release check`（Pre-flight 檢查）之前執行。major、minor、patch 每個版本都執行。觸發條件以 `.claude/pm-rules/version-progression.md`〈兩期：規劃期與執行期〉與〈版本生命週期〉為正本：

| 條件 | 說明 |
|------|------|
| 版本契約必要的票已全部終態 | 帶 `scope_blocker` 的票全部 completed 或 closed。發版判準是契約阻擋而非 pending 池清空，不帶 `scope_blocker` 的未完成票不阻擋檢討 |
| 其餘未完成票的去向已定 | 前移目標由 minor 完成後的分診指定；分診未指定者，以最近的開放後繼為預設，目標版本須已登記（〈版本生命週期〉〈minor 完成後的分診與去向〉前移列） |

**Why**：版本在執行期已凍結，「功能是否達標」不再由 PM 臨場判斷，而由契約票的終態決定；以「所有 Ticket 完成」為條件，會讓不屬於契約的前移票擋住檢討與發版。**Consequence**：條件與發版判準不一致時，檢討不是遲遲不觸發，就是在契約未完成時提前進行。**Action**：以上兩項成立即執行本流程；minor 的檢討產出同時作為〈minor 完成後的分診〉的輸入。

---

## 檢討流程（5 步驟）

### Step 1: 收集經驗素材

| 素材來源 | 收集方式 | 重點 |
|---------|---------|------|
| Error Patterns | `ls .claude/error-patterns/` | 本版本新增的模式 |
| Ticket 執行日誌 | `ticket track list --version X.Y.Z` | 失敗、阻擋、重試記錄 |
| Session 教訓 | Memory 系統 | 跨 session 累積的教訓 |
| 測試結果 | 區塊測試記錄 | 重複失敗的測試類型 |

### Step 2: 分類和評估

將收集到的經驗分為三類：

| 分類 | 目標文件 | 範例 |
|------|---------|------|
| **專案規範** | CLAUDE.md | 技術選型、測試指令、架構決策 |
| **代理人設定** | `.claude/agents/` 定義 | 代理人觸發條件調整、職責釐清 |
| **流程規則** | `.claude/pm-rules/`、`.claude/rules/` | 新增防護規則、檢查清單 |

**評估原則**：
- 發生 2 次以上的問題 → 必須寫入規範
- 發生 1 次但影響大（阻擋 > 1 小時）→ 建議寫入規範
- 純一次性問題 → 記錄在 error-pattern 即可

### Step 3: 多視角審查檢討結論

以 `/parallel-evaluation` 情境 F（結論審查）審查 Step 2 的分類與評估結果，審查三問聚焦：證據是否支撐「重複發生」的判定、是否漏列本版的經驗素材、目標文件的分類是否正確。

**產出位置**：審查結論寫入版本工作日誌主檔 `docs/work-logs/v{major}/v{major.minor}/v{version}/v{version}-main.md` 的〈版本檢討〉段，連同 Step 2 的分類表。審查發現依 `.claude/rules/core/quality-baseline.md` 規則 5 建票。

**Why**：檢討結論決定哪些經驗被固化為規則，單一視角容易把一次性事件判成重複、或漏掉跨票的同根問題。**Consequence**：未經審查的檢討結論直接寫進規範，錯誤的歸納會在後續版本以規則的形式被執行。**Action**：Step 4 只對審查後保留的項目建票。

### Step 4: 產出改善 Ticket

本版已在執行期，改善項不進本版（`.claude/pm-rules/version-progression.md`〈兩期〉），依〈版本生命週期〉的凍結分流決定目標版本後建票：

```bash
ticket create --version {目標版本} \
  --action "更新" --target "{具體規範文件名}" --type DOC
```

| 改善項性質 | 目標版本 |
|-----------|---------|
| 承諾未達成 | 下一個 patch |
| 改善、技術債 | 下一個 minor 的候選池 |
| 框架問題（consumer 專案） | canonical framework issue，不建本地票 |

### Step 5: 執行和驗證

- 改善 Ticket 在目標版本的規劃期裁決、執行期執行，不回頭修改本版
- 唯一例外：檢討中發現讓本版跑不起來的問題，於本版建票並帶 `--scope-blocker <理由>`，處理完才進入 `/version-release check`

---

## 檢討檢查清單

每次版本檢討時確認：

- [ ] 本版本新增的 error-patterns 是否都有對應的防護規則？
- [ ] 本版本重複出現的問題是否已寫入規範？
- [ ] 代理人定義是否需要調整（觸發條件、職責邊界）？
- [ ] CLAUDE.md 是否反映最新的技術選型？
- [ ] 測試策略是否需要根據失敗模式調整？

---

## 與現有流程的關係

```
版本契約必要的票（scope_blocker）全部終態
    |
    v
[Version Retrospective] ← 本文件定義的流程（含 parallel-evaluation）
    |
    v
/version-release check（Pre-flight 檢查）
    |
    v
文件更新 → Git 操作 → 發布
```

---

## 相關文件

- .claude/skills/version-release/SKILL.md - 版本發布流程
- .claude/pm-rules/version-progression.md - 版本進程規劃
- .claude/error-patterns/ - 錯誤模式知識庫
- .claude/rules/core/quality-baseline.md - 品質基線（規則 5：所有發現必須追蹤）

---

**Last Updated**: 2026-11-09
**Version**: 1.1.0 - 觸發時機改以 version-progression〈兩期〉〈版本生命週期〉為正本：條件改為版本契約必要的票（scope_blocker）全部終態、其餘未完成票去向已定，取代「所有功能 Ticket 完成」；流程新增 Step 3 parallel-evaluation 情境 F 審查檢討結論，產出寫入版本工作日誌主檔〈版本檢討〉段；改善 Ticket 改依凍結分流建在目標版本，不在本版完成（讓本版跑不起來者除外）。
**Version**: 1.0.0 - 初版
