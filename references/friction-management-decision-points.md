# 摩擦力管理決策點參考表

> 本檔為 `.claude/methodologies/friction-management-methodology.md` 的詳細參考。
> 方法論主檔只保留判斷準則；具體 PM 決策點分類表在此。

---

## 象限 A：降低摩擦（高頻低風險，直接執行不詢問）

| 決策點 | 行為準則 | 來源規範 |
|--------|----------|---------|
| 驗證類子任務派發（跑測試/lint/覆蓋率/AC 實況） | 直接建子 Ticket + 背景派發，不詢問用戶。**例外**：驗證結果決定 Ticket 是否繼續或版本發布與否時，仍須詢問 | parallel-dispatch.md 規則 5 + askuserquestion-rules.md 規則 5 |
| `ticket track query/list/summary` 純查詢 | 直接執行，不記錄日誌 | ticket CLI 設計原則 |
| `ticket track append-log` 進度紀錄 | 階段轉換時強制執行 | completion-checkpoint-rules Checkpoint 0.5 |
| Worktree 建立（新開發任務） | 代理人派發時自動使用 `isolation: "worktree"`，無需預先確認 | parallel-dispatch.md Worktree 隔離強制表 |
| Worktree 合併（代理人完成後） | 立即 merge，不等 ticket complete | PC-039 + completion-checkpoint Checkpoint 1.9 |
| Context Bundle 準備（下一個 Ticket） | 派發後立即切換執行，不等代理人回來 | parallel-dispatch async-mindset |
| 執行期間發現技術債建立 Ticket | `/ticket create` 直接建立，不詢問確認 | quality-baseline 規則 5 |

## 象限 B：保留現狀（中頻中風險，維持既有 SOP）

| 決策點 | 行為準則 | 來源規範 |
|--------|----------|---------|
| Ticket complete 前 AC 勾選 | 主動 `check-acceptance`，禁止依賴 CLI 擋回才補勾 | completion-checkpoint-rules 第七層 |
| 驗收方式確認（P0 優先級 complete 前） | AskUserQuestion #1（非 P0 自動決定不觸發） | askuserquestion-rules #1 |
| Commit 後錯誤學習確認 | AskUserQuestion #16 雙通道記錄（error-pattern + memory） | askuserquestion-rules #16 |
| Handoff 方向選擇（多兄弟任務可選） | AskUserQuestion #9 確認方向 | askuserquestion-rules #9 |
| Ticket 認領後範圍確認 | 讀取 5W1H + 驗證 where.files 存在 | pm-rules/session-switching-sop.md |
| Error Pattern 記錄（場景 #16 後續追蹤） | ticket complete 時若有新增 error-pattern，AskUserQuestion #17 確認改進追蹤 | askuserquestion-rules #17 |

## 象限 C：增加摩擦（低頻高風險，強制 WRAP/多視角/阻擋）

| 決策點 | 行為準則 | 來源規範 |
|--------|----------|---------|
| ANA/Debug/提案評估 | **強制**套用 WRAP 框架 | feedback_wrap_mandatory_for_analysis / PC-051 |
| parallel-evaluation 強勢結論處置 | 含 Garbage/Acceptable with fatal smell 評分時，**強制** WRAP 後才能建執行 Ticket | PC-056（本次教訓） |
| Wave 收尾版本發布 | **強制**先做 `/parallel-evaluation` Wave 審查（含 linux 委員）再進入 #3 | completion-checkpoint Checkpoint 2-C |
| 破壞性 git 操作（`git reset --hard` / `git push --force` / `git branch -D` / `git worktree remove`） | 必須向用戶確認，無自動化豁免 | pm-role.md 核心原則 + pm-rules/askuserquestion-rules.md |
| 規則/方法論/代理人/Hook 檔案修改 | **強制**先建 Ticket 追蹤，無「太小」例外 | quality-baseline 規則 5/6 + PC-053 |
| Hook 失敗 / 測試失敗 / 編譯錯誤 → incident 派發 | **強制**派發 incident-responder 分析，禁止 PM 直接修復 | skip-gate.md Level 1 規則 1-3 |

## 刪除的象限 D

原 v1.0.0 的象限 D「臨時閒聊」只有 1 條目，屬硬湊四象限設計。已刪除——觸及決策時本就會升級到象限 A 或 C，無需獨立象限。

---

## AskUserQuestion 18 場景覆蓋對照

> **單一來源**（W5-008）：本表是 AUQ 場景與象限對照的唯一權威；`pm-rules/askuserquestion-rules.md` 場景表不再重複象限欄。

| 場景 | 所屬象限 | 備註 |
|------|---------|------|
| #1 驗收方式確認 | B | P0 觸發，其他自動 |
| #2 Complete 後下一步 | B | 路由性決策 |
| #3 Wave/任務收尾確認 | C | 含強制 parallel-evaluation 前置 |
| #4 方案選擇 | C | 多技術方案並存 |
| #5 優先級確認 | B | 多任務排序 |
| #6 任務拆分確認 | C | 認知負擔 > 10 |
| #7 派發方式選擇 | B | 三種派發模式 |
| #8 執行方向確認 | B | 並行/序列 |
| #9 Handoff 方向選擇 | B | 多兄弟/子任務 |
| #10 開始/收尾確認 | B | 執行前確認 |
| #11a/b Commit 後 Handoff | B | 情境 A/B |
| #12 流程省略確認 | C | 防止省略關鍵步驟 |
| #13 後續任務路由確認 | B | Phase 完成後 |
| #14 parallel-evaluation 觸發確認 | C | 階段完成後強制 |
| #15 Bulk 變更前備份確認 | C | 批量修改前 |
| #16 錯誤學習確認 | B | commit 後 |
| #17 錯誤經驗改進追蹤 | B | complete 時 |

## 決策點完整性檢查

本表共列 19 個決策點（7+6+6），**覆蓋**：
- AskUserQuestion 的 18 個場景（透過象限分類）
- Skip-gate 的 Level 1-3 防護（incident 派發、命令驗證、編輯限制）
- parallel-dispatch 的驗證類自動派發規則
- ticket-lifecycle 的關鍵轉換點

**未覆蓋**：日常純執行動作（編輯檔案、讀檔案、跑 CLI），這些屬「執行」非「決策」，不在本框架範圍。

---

**Last Updated**: 2026-04-12
**Version**: 1.0.0 - 從 friction-management-methodology.md v1.0.0 拆分並修復映射錯誤、補齊遺漏
