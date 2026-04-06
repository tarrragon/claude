# Agent 失敗標準除錯 SOP

Agent 派發失敗時的標準化追溯和修復流程。

> 來源：W2-014 分析結論（P0）、PC-042（回合耗盡）、PC-043（PM 直接執行）

---

## 失敗模式分類表

| 失敗模式 | 識別特徵 | 嚴重度 | 處理方式 |
|---------|---------|--------|---------|
| **回合耗盡** | response 異常短 / 結論截斷 / 無 Write 操作 | 高 | 檢查目標檔案體量 → 拆分檔案或任務 |
| **Worktree 衝突** | response 含 "merge conflict" / git 操作失敗 | 高 | 手動解決衝突 → 清理 worktree → 重新派發 |
| **路徑找不到** | response 含 "file not found" / "No such file" | 中 | 檢查 prompt 中的路徑是否正確 |
| **測試失敗** | response 含 "test failed" / "FAILED" | 中 | 派發 incident-responder 分析 |
| **靜默失敗** | 有 commit 但內容不符預期 / AC 未覆蓋 | 高 | 對比 prompt 和 git diff → 調整 prompt 重新派發 |

---

## 3 步追溯流程

### Step 1：確認失敗（收集證據）

```
Agent 回傳結果
    |
    v
結果是否完整？（AC 全部覆蓋？）
    |
    +-- 是 → 正常完成，無需追溯
    |
    +-- 否 → 進入 Step 2
```

**確認手段**（方案一 Hook 實作前的臨時手段）：

| 手段 | 指令 | 檢查內容 |
|------|------|---------|
| 閱讀 Agent 回傳文字 | 直接看 conversation 中的 Agent tool result | response 是否被截斷 |
| 檢查 commit | `git log --all --oneline -10` | 是否有代理人的 commit |
| 檢查 worktree | `git worktree list` | 是否有殘留未合併的 worktree |
| 檢查 diff | `git diff main..{branch}` | commit 內容是否符合預期 |

### Step 2：分類失敗原因

依 response 特徵對照上方「失敗模式分類表」，判定屬於哪種失敗模式。

**回合耗盡的特殊判斷**（PC-042）：

```
response 異常短或截斷？
    |
    v
檢查目標檔案體量
    |
    +-- 有 > 300 行的檔案 → 體量問題（行數超標是症狀，domain 混合是病因）
    |     → 分析 domain 邊界，建立拆分 Ticket
    |
    +-- 均 < 200 行 → 任務複雜度問題
          → 拆分任務為更小的子 Ticket
```

### Step 3：修復後重新派發

| 失敗模式 | 修復動作 | 重新派發方式 |
|---------|---------|------------|
| 回合耗盡（體量） | 拆分目標檔案 → 降低 Read 成本 | 重新派發，prompt 指向拆分後的檔案 |
| 回合耗盡（複雜度） | 拆分任務為子 Ticket | 每個子 Ticket 獨立派發 |
| Worktree 衝突 | `git worktree remove` + 解決衝突 | 清理後重新派發 |
| 路徑找不到 | 更正 prompt 中的路徑 | 修正後重新派發 |
| 測試失敗 | 派發 incident-responder 分析根因 | 根因修復後重新派發 |
| 靜默失敗 | 分析 prompt 是否足夠明確 | 補充 prompt context → 重新派發 |

**禁止行為**：

| 禁止 | 原因 |
|------|------|
| 無限重試同一 prompt | 每次重試必須調整策略 |
| PM 代替代理人直接修復（IMP 類型） | 應修正派發條件後重新派發 |
| 忽略失敗繼續下一個任務 | 必須記錄失敗原因和處理結果 |

---

## 相關文件

- .claude/pm-rules/incident-response.md - 回合耗盡應對流程
- .claude/rules/core/cognitive-load.md - 認知負擔閾值（含檔案體量維度）
- .claude/error-patterns/process-compliance/PC-042*.md - 回合耗盡錯誤模式
- .claude/error-patterns/process-compliance/PC-043*.md - PM 跳過階段轉換

---

**Last Updated**: 2026-04-06
**Version**: 1.0.0 - 初始建立（W2-014 P0 結論，0.17.2-W3-001）
