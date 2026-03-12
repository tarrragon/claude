# 背景派發詳細規則

> 核心入口：.claude/rules/core/decision-tree.md（派發模式選擇規則）

---

## 核心原則

派發代理人時**預設使用 `run_in_background: true`**，讓主線程保持靈活性。

---

## 派發決策

```
派發代理人
    |
    v
需要結果才能繼續? → 是 → 前景執行
    |
    +─ 否 → 背景派發（預設）
```

### 背景派發（預設）

| 類型 | 範例 |
|------|------|
| 開發/實作 | TDD Phase 1-4 代理人 |
| 分析/審查 | SA、acceptance-auditor、parallel-evaluation |
| 重構 | cinnamon-refactor-owl |
| 建立後審核 | acceptance-auditor + system-analyst 並行 |

### 前景執行（例外）

| 類型 | 範例 |
|------|------|
| Skill 查詢 | `/ticket track list`、`/ticket track query` |
| 即時驗證 | `dart analyze`、`go vet` |
| 結果驅動決策 | 需要代理人產出才能做 AskUserQuestion |

---

## 背景派發後跟蹤

### 被動通知（推薦）

代理人完成時，系統自動發送 TaskOutput 通知：
1. PM 收到通知
2. 執行 `/ticket track query {id}` 查看結果
3. 決定下一步（Checkpoint 流程）

### 主動查詢

PM 可隨時查詢進度：
```bash
ticket track list --status in_progress
```

---

## 多背景任務管理

同時派發多個背景任務時，PM 可：
1. 準備下一批 Ticket
2. 與用戶溝通討論
3. 檢查已完成的任務結果
4. 建立新的 Ticket

**禁止**：阻塞等待任何單一背景任務完成。

---

## 檔案衝突防護

背景派發不改變並行安全檢查要求。所有背景任務完成後，仍需執行：

```bash
git diff --stat  # 驗證實際變更
```

> 完整檢查清單：.claude/rules/guides/parallel-dispatch.md（並行派發後驗證章節）

---

## 相關文件

- .claude/rules/core/decision-tree.md - 派發模式選擇規則
- .claude/rules/guides/parallel-dispatch.md - 並行派發指南
- .claude/skills/manager/SKILL.md - 主線程管理哲學

---

**Last Updated**: 2026-03-12
**Version**: 1.0.0
