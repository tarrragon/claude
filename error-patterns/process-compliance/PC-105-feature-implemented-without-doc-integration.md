# PC-105: 新功能實作後缺乏文件引導整合

**Category**: process-compliance
**Severity**: High
**Status**: Active
**Created**: 2026-04-20
**Source**: W17-011 scheduler runqueue CLI + hook 實作後，SKILL.md / references / pm-rules 全無引導，用戶質疑「系統怎麼知道怎麼使用？」才發現。

---

## 症狀

新功能（CLI 子命令、Hook、Skill、方法論、代理人）實作完成且測試綠燈後，用戶或代理人仍不知此功能存在或該如何觸發。典型訊號：

- 用戶問「這個工具有文件引導嗎？」
- `grep <新功能名稱> .claude/skills/ .claude/pm-rules/` 零命中（除了實作檔本身）
- 新 session 啟動後用戶/代理人仍用舊做法解決新功能已處理的問題
- 功能被遺忘，下一個相似需求被視為「缺口」重新實作

## 根因

**Lib 層完成 ≠ 使用者可見 ≠ 系統可用**。TDD Phase 3b 綠燈聚焦「程式碼正確執行」，不保證「人 / 代理人知道呼叫方式」。引導整合是獨立產物，須顯式追蹤。

**結構性偏見**：

| 偏見 | 成因 |
|------|------|
| 完成即 complete | AC 通常只驗功能正確，不驗「引導是否更新」 |
| 實作代理人職責邊界窄 | thyme/parsley 實作 CLI 時不主動改 SKILL.md（非其檔案範圍） |
| PM 派發時未列引導檔 | where.files 只列實作檔 + 測試檔，漏引導檔 |
| Hook 自動引導誤認充分 | session-hint hook 只顯示部分情境，其他情境仍需人工查文件 |

## 案例（W17-011 系列）

**實作**：
- `track_runqueue.py` + 17 tests（W17-011.1 commit 19bea58f）
- `session-start-scheduler-hint-hook.py` + 9 tests（W17-011.4 commit edc78a20）
- `handoff --auto`（W17-011.5 commit b8f9c564）

**引導缺失**（2026-04-20 用戶質疑前）：
- `.claude/skills/ticket/SKILL.md` 無 runqueue 章節
- `.claude/skills/ticket/references/track-command.md` 無 runqueue 說明
- `.claude/pm-rules/session-switching-sop.md` 未引用 runqueue
- `.claude/rules/core/pm-role.md` Re-center Protocol 未含 runqueue
- `docs/` 用戶文件零提及

**後果**：功能全綠但「系統不知道怎麼使用」——PM 迷失方向時仍手工組合 `list + blockedBy filter + priority 排序` 五步驟，不知 `runqueue` 一命令搞定。

**修復**：bc159ade commit 補 4 檔引導。

## 防護措施

### 1. Ticket AC 強制含「引導更新」條款（ticket 模板）

實作類 ticket（IMP + 含新 CLI / Hook / Skill）AC 必含：

```yaml
acceptance:
- '[ ] 引導文件已更新（至少 2 處）：SKILL.md / references / pm-rules / rules/core 擇 2'
- '[ ] 新 session 啟動可自動看到引導（hook / default）或 grep 到使用範例'
```

### 2. 派發 where.files 強制含引導檔

PM 派發前建 Context Bundle 時，where.files 不得僅列實作檔，必須包含：
- SKILL.md（如功能屬某 Skill）
- references/ 對應章節
- pm-rules/（如涉及 PM 流程）

### 3. 完成時 Acceptance Gate 檢查

`complete` 命令檢查：若 ticket 新增檔案 `.py` / `.md`（非 test），自動 grep 新功能名稱在 `.claude/skills/ .claude/pm-rules/ .claude/rules/` 的命中數。命中 < 2 → 警告（非阻擋，因人工豁免情境存在）。

### 4. 多視角審查加入「文件 / 引導」視角

parallel-evaluation 情境 A / C（程式碼 / 架構審查）加一視角：**Integration（整合可見度）**——功能是否被文件系統看見？用戶如何發現？

## 相關

- `W17-010` NeedsContext 協議類比（PM 無法看到 agent 狀態 vs 用戶無法看到工具存在）
- PC-053「所有規則修改都需要 Ticket」（結構類似：實作有 ticket，文件更新常漏）
- PC-066「decision-quality autopilot」（缺指引時 PM 回退到熟悉舊路徑）

## 關鍵教訓

> **實作完成只是起點，不是終點**。新功能要進入系統的工作流，需要三層整合：
> 1. **程式碼層**（實作 + 測試綠）— 已由 TDD Phase 3b 覆蓋
> 2. **引導層**（文件 + SKILL + 規則）— 需顯式 AC 覆蓋（本 PC 防護）
> 3. **自動觸發層**（hook / default path）— 提升使用率天花板

任一層缺失，功能會被遺忘或被誤認為缺口。PM 派發時 where.files 必須覆蓋三層所有檔案。
