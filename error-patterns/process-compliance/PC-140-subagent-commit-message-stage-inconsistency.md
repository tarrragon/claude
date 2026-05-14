# PC-140: Subagent commit message 與 stage 內容不一致

## 基本資訊

- **Pattern ID**: PC-140
- **分類**: 流程合規（process-compliance）
- **來源版本**: v0.18.0
- **發現日期**: 2026-05-12
- **風險等級**: 中
- **相關 Pattern**: PC-076（cross-session uncommitted）、PC-105（subagent no complete after commit）

---

## 問題描述

### 症狀

Subagent 完成任務並執行 `git commit` 時，commit message 描述的檔案變更與實際 stage 的檔案不一致——message 提及 N 個檔案但 commit 實際只含 M (< N) 個檔案。

### 表現形式

| 表現 | 說明 |
|------|------|
| Commit message 提及檔案 A/B/C | 但 `git show --stat` 只顯示 A、B（漏 C）|
| Agent 報告「已修改 X 檔案」 | 但 git diff 顯示部分檔案仍未 stage |
| PM 看 commit message 信任 | 後續發現未 commit 變更，需 PM 補做收尾 |

---

## W10-106 案例

### 時序

1. thyme-documentation-integrator 派發處理 W10-106（td-status 同步到 SKILL.md + tech-debt.md + tdd-flow.md）
2. agent 修改 3 個檔案
3. agent 執行 commit（`d93877d7`），commit message 提及 3 檔案變更
4. PM session 結束驗收時發現 `.claude/skills/ticket/SKILL.md` 仍有未 stage 變更
5. `git show --stat d93877d7` 確認該 commit 只含 `tdd-flow.md` + `tech-debt.md`，**漏 SKILL.md**
6. PM 補 commit（`a292a5bd`）修補漏 stage 的 SKILL.md

### 根因推測

| 推測 | 描述 |
|------|------|
| A `git add` 漏 file path | agent 用 `git add file1 file2` 明示路徑時漏第 3 個 |
| B 工作目錄 staging confusion | agent 在多檔修改後 stage 部分檔案就 commit |
| C 並行寫入 vs commit 時序 | 改 file3 在 commit 後完成（不太可能，因 commit 已成功）|

最可能：A（明示路徑漏列）。

---

## 防護機制

### 已存在的相關防護

- `agent-dispatch-validation-hook`：派發前驗證 agent 能力
- `acceptance-gate-hook`：complete 時驗證 acceptance + body

### 缺口

無 hook 驗證 commit message 提及的檔案路徑是否在 stage 中。

### 規則建議

1. **Agent dispatch prompt 強化**：派發 prompt 提醒「commit 前確認 git diff --cached 與 commit message 描述一致」
2. **Commit hook validation**：在 commit-msg hook 解析 message 中的 `.md` / `.py` 路徑，與 `git diff --cached --name-only` 對照，不一致時提示
3. **PM 收尾驗證**：PM 看到 subagent commit 後執行 `git status --short` 確認無漏 stage

---

## 與 PC-076 / PC-105 的差異

| Pattern | 焦點 |
|---------|------|
| PC-076 | 跨 session 未提交變更，session-start hook 摘要遮蔽全 git status |
| PC-105 | Subagent commit 後未自律 complete ticket |
| PC-140 | Subagent commit message 與實際 stage 內容不一致 |

三者均涉及 subagent commit 行為的合規性，但角度不同：PC-076 是 session 邊界、PC-105 是 commit 後續步驟、PC-140 是 commit 本身的 atomicity。

---

**Last Updated**: 2026-05-12
**Version**: 1.0.0
**Source**: W10-106 thyme-documentation-integrator commit `d93877d7` message 提及 SKILL.md 但實際漏 stage（PM 補 `a292a5bd` 修補）
