# 背景派發詳細規則

> 核心入口：.claude/pm-rules/decision-tree.md（派發模式選擇規則）

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

## 驗證類任務自動派發

> **核心規則位置**：.claude/pm-rules/parallel-dispatch.md（驗證類任務自動派發章節）
> **適用原則**：驗證類任務預設直接背景派發，PM 不詢問用戶。

### 驗證類任務清單

| 類型 | 具體範例 |
|------|---------|
| 測試執行 | `npm test`、`npm run test:unit`、`npm run test:integration`、跑覆蓋率 |
| 靜態掃描 | `npm run lint`、ESLint、型別檢查、掃描硬編碼字串 |
| 建置驗證 | `npm run build:dev`、`npm run build:prod`、`npm run validate:build:prod` |
| 打包驗證 | 產生可分發產物、驗證 manifest.json |
| AC 實況驗證 | 實測 Ticket AC 是否在當前 codebase 通過 |
| 統計資料收集 | 測試通過率、覆蓋率、lint 錯誤數、檔案行數 |

### 識別關鍵詞（從 Ticket what / how 判斷）

| 關鍵詞 | 判斷為驗證類 |
|-------|------------|
| 「執行 X 並產出報告」「跑 Y 並整理結果」 | 是 |
| 「驗證 AC 實況」「實測通過率」「確認是否仍達成」 | 是 |
| 「跑測試」「全量掃描」「建置」「打包」 | 是 |
| 「統計 X 數量」「列出所有 Y」「量測 Z」 | 是 |
| 「設計 X 架構」「實作 Y 功能」「重構 Z 模組」 | 否（屬於開發/分析類） |

### 派發 SOP（六步驟）

```
1. PM 識別驗證類任務
    |
    v
2. PM 建 5W1H 完整的子 Ticket
    - 序號：{parent_id}.{n}（父子關係命名，如 `{parent_id}.1`）
    - type: IMP 或 TST（依驗證對象）
    - what/how/acceptance 完整填寫
    |
    v
3. PM 寫 Context Bundle 到父 Ticket Problem Analysis
    - 驗證目標
    - 執行指令
    - 預期產出格式
    - 成功/失敗判斷標準
    |
    v
4. PM 背景派發代理人（run_in_background: true）
    - Prompt 僅含 Ticket ID + 必要執行指示
    - 禁止在 prompt 複述 Context Bundle 內容
    |
    v
5. PM 立即切換其他準備工作
    - 不等代理人完成
    - 去準備其他 Ticket 的 Context Bundle、規格分析、Wave 規劃等
    |
    v
6. 收到完成通知後驗收
    - 讀取代理人寫入的執行日誌
    - 確認 AC 勾選
    - 決定下一步（commit / 補派 / 記錄）
```

### 流程禁止事項

| 禁止 | 原因 |
|------|------|
| 詢問用戶「要派代理人還是自己做」 | 驗證類有明確 SOP，已預先決策為派發 |
| PM 自己在主線程執行驗證指令 | 耗回合、阻礙其他準備工作 |
| 派發前省略 Context Bundle | 違反 dispatch-gate.md 第二關 |
| 把 Context Bundle 塞進 prompt 而非父 Ticket | 違反 PC-040 長度限制 |

### 例外條件（回頭詢問用戶）

驗證結果會**直接影響派發策略的根本決策**時：

| 情境 | 必須詢問的問題 |
|------|-------------|
| 驗證結果決定 Ticket 是否繼續 | 「這個 Ticket 是否仍值得做？」 |
| 驗證結果決定版本發布 | 「打包失敗，是否重排版本？」 |
| 根因不明且影響其他 Wave | 「驗證顯示問題擴散到其他 Wave，如何調整優先級？」 |

一般的資料收集型驗證（AC 實況、覆蓋率、lint 掃描）**不屬於例外**。

### 完整範例（流程示意）

以「驗證 AC 實況」為例（`{parent}` / `{parent}.1` 為佔位符，實際帶入 Ticket ID）：

```
父 Ticket {parent}（要求驗證 AC 在 codebase 上實況）
    |
    v
PM 建子 Ticket {parent}.1
    - type: TST
    - what: 執行 npm test 並統計測試通過率
    - how: 逐項比對父 Ticket 的 AC 與實測結果
    - acceptance:
        - [ ] npm test 執行完成
        - [ ] 測試通過/失敗數量記錄
        - [ ] AC 逐項對照表產出
    |
    v
PM 寫父 Ticket Problem Analysis：
    「驗證目標：父 Ticket 的 N 項 AC；指令：npm test；
     預期產出：AC 對照表；通過判準：所有 AC 狀態明確」
    |
    v
PM 背景派發代理人（prompt: Ticket: {parent}.1 + 執行指示）
    |
    v
PM 立刻切去做下一個 Ticket 的 Context Bundle 準備
    |
    v
代理人完成通知到達 → PM 讀取 {parent}.1 執行日誌
    → 驗收通過 → commit → 回父 Ticket 繼續
```

---

---

## 相關文件

- .claude/pm-rules/decision-tree.md - 派發模式選擇規則
- .claude/rules/guides/parallel-dispatch.md - 並行派發指南
- .claude/rules/core/pm-role.md - 主線程管理哲學

---

**Last Updated**: 2026-04-12
**Version**: 1.1.0 - 新增「驗證類任務自動派發」詳細 SOP（六步驟、禁止事項、例外條件、完整範例）
