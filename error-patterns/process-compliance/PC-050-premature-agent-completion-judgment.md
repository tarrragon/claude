# PC-050: PM 在代理人仍在工作時誤判完成

## 錯誤症狀

- PM 收到一個代理人的完成通知後，立刻開始驗收和 commit
- 實際上還有其他代理人在背景執行中
- 導致代理人工作結果被覆蓋、衝突、或遺漏

## 根因分析

PM 缺乏「代理人完成確認」的系統性流程。具體表現：

**模式 A — 未檢查分支就判定失敗**（W2-001/002）：
1. PM 派發代理人（背景）
2. 代理人在 feature 分支上 commit
3. PM 在 main 上看 `git status`，沒有變更
4. PM 誤判「代理人沒做事」，重新派發
5. 浪費一次代理人執行

**模式 B — 多代理人只看一個就行動**（W11-002）：
1. PM 派發代理人 A（回合耗盡，未完成）
2. PM 重新派發代理人 B（簡化版）
3. 代理人 B 完成，PM 立刻 commit
4. 代理人 A 仍在背景執行（或已完成但 PM 未確認）
5. 兩個代理人可能在同一個分支上產生衝突

**模式 C — 共用分支**（W11-001/003）：
1. PM 建了一個 feature 分支
2. 並行派發兩個代理人
3. 兩個代理人都在同一個分支上工作
4. 失去分支隔離的意義

## 防護措施

### PM 代理人完成確認 SOP（強制，已整合到決策樹）

**派發後**（dispatch-gate.md「派發後清點」）：
```bash
cat .claude/dispatch-active.json  # 確認派發數量正確
```

**收到完成通知時**（pm-role.md「代理人完成確認 SOP」）：
```bash
cat .claude/dispatch-active.json  # 確認剩餘活躍派發
```

**只有 dispatch-active.json 為空時，才能開始驗收和 commit。**

**完成 Checkpoint 中**（completion-checkpoint-rules.md「Checkpoint 1.85」）：
- 1.85 代理人清點：dispatch-active.json 非空 → 阻塞，禁止繼續

**判斷代理人失敗前**（pm-role.md「失敗判斷前置步驟」）：
1. `cat .claude/dispatch-active.json` — 代理人可能還在活躍派發中
2. `git branch | grep feat/` + `git worktree list` — 變更可能在其他分支
3. 只有 dispatch-active.json 為空且所有分支都無 commit 後，才判定失敗

### 並行派發分支隔離（強制，已整合到 dispatch-gate.md）

- 每個代理人使用獨立 feature 分支（N 個代理人 = N 個分支）
- 派發前切回 main 建新分支
- 或使用 `isolation: "worktree"` 自動隔離
- 禁止共用分支

## 實際案例

| Session | 場景 | 誤判類型 | 後果 |
|---------|------|---------|------|
| 2026-04-09 | W2-001 | 模式 A | 不必要的重新派發 |
| 2026-04-10 | W2-002 | 模式 A | 不必要的重新派發 |
| 2026-04-10 | W11-001/003 | 模式 C | 共用分支失去隔離 |
| 2026-04-10 | W11-002 | 模式 B | 代理人仍在執行時 commit |

## 關聯

- **Ticket**: 0.17.3-W12-001
- **相關模式**: PC-039（worktree 未合併不可見）
- **PM 規則**: .claude/rules/core/pm-role.md（代理人失敗判斷前置步驟）

---

**Created**: 2026-04-10
**Category**: process-compliance
**Severity**: P1（導致重複工作、潛在衝突、判斷錯誤）
**Key Lesson**: 派發時記錄數量，收到通知時比對，全部完成才行動
