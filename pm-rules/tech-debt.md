# 技術債務處理流程

本文件定義 Phase 4 發現技術債務後的標準處理流程。

---

## 流程總覽

```
Phase 4 發現技術債務
    |
    v
記錄到工作日誌
    |
    v
執行 /tech-debt-capture
    |
    v
自動建立 Ticket
    |
    v
分配到適當版本
    |
    v
提交當前版本
```

---

## 步驟詳解

### Step 1：識別技術債務

在 Phase 4 重構評估中，識別以下類型的技術債務：

| 債務類型 | 識別特徵 | 範例 |
|---------|---------|------|
| 設計債務 | 架構不一致、違反設計原則 | 依賴方向錯誤、命名不一致 |
| 程式碼債務 | 重複程式碼、過長函式 | Copy-paste 程式碼、100+ 行函式 |
| 測試債務 | 測試覆蓋不足、測試品質差 | 缺少邊界測試、測試耦合實作 |
| 文件債務 | 文件過時、缺少文件 | 過時的 README、缺少 API 文件 |

---

## TD 清單即時校準（td-status）

> **來源**：PC-094 TD 清單即時校準缺失。W10-083 實作 `ticket track td-status` 子命令提供自動化校準工具。

### 問題背景

TD 清單視為 Phase 1 一次性產物，未隨 Phase 演進即時更新，導致 Phase 4 評估時將「已完成項」誤認為「待處理項」（PC-094 W10-017.8 案例）。後果：誤判已完成 TD 會造成重複建立 follow-up Ticket 或多視角分析在無效項目上消耗 token。

### 呼叫時機

PM 在以下三個節點主動執行 `ticket track td-status <ticket-id>`：

| 節點 | 呼叫時機 | 說明 |
|------|---------|------|
| Phase 3a 完成後 | 策略文件落地、準備派發 3b 前 | 確認策略階段已處理的 TD 已標記 |
| Phase 3b commit 前 | 代理人回報成功後、PM 驗收時 | 對齊 commit 訊息中的 TD 引用 |
| Phase 4 派發前 | 派發多視角分析（4a）或直接派發重構（4b）前 | 最終校準，防止 4 視角浪費 token 在已完成項 |

### 使用方式

```bash
# 校準指定 ticket 的 TD 清單
ticket track td-status 0.18.0-W10-017

# 明確指定版本（當自動偵測失敗時）
ticket track td-status 0.18.0-W10-017 --version 0.18.0
```

### 輸出說明

| 狀態 | 說明 | 訊號來源 |
|------|------|---------|
| `[已處理]` | TD 已完成 | body 含「已處理 / 已修正 / 已完成」或 commit 訊息引用 TD 編號 |
| `[無需處理]` | TD 豁免 | body 含「無需處理 / 無需 / 豁免 / N/A」 |
| `[仍待處理]` | 仍有未見處理訊號 | 以上訊號皆無，附 PC-094 提示 |

### 校準後動作

| 發現 | 動作 |
|------|------|
| pending TD 數量符合預期（如 Phase 3a 後仍有 TD 待 Phase 4 處理） | 記錄到 ticket Solution，說明預計處理節點 |
| pending TD 實際已處理但未標記 | 於 ticket body 補標「已處理：[原因]」，或下一個 commit 訊息引用該 TD 編號 |
| pending TD 確認無需處理 | 於 ticket body 補標「無需處理：[原因]」（符合 PC-094 防護規則 2） |

---

### Step 2：記錄到工作日誌

```markdown
## 技術債務記錄

| ID | 描述 | 風險等級 | 建議處理時機 |
|----|------|---------|------------|
| TD-001 | [描述] | 高/中/低 | [時機] |
| TD-002 | [描述] | 高/中/低 | [時機] |
```

### Step 3：執行 /tech-debt-capture

```bash
/tech-debt-capture
```

此指令會：
1. 解析工作日誌中的技術債務記錄
2. 為每個 TD 建立 Atomic Ticket
3. 根據風險等級分配版本

### Step 4：版本分配規則

| 風險等級 | 版本分配 | 說明 |
|---------|---------|------|
| 高 | 下個 Patch 版本 | 必須在 v0.x.{n+1} 處理 |
| 中 | 下個 Minor 版本 | 排入 v0.{x+1}.0 |
| 低 | 技術債務清理版本 | 累積後統一處理 |

---

## 風險等級判定標準

| 等級 | 判定標準 |
|------|---------|
| **高** | 影響系統穩定性、可能導致生產問題、阻礙後續開發 |
| **中** | 降低開發效率、增加維護成本、可能在未來造成問題 |
| **低** | 程式碼風格問題、輕微重複、文件不完整 |

---

## 技術債務 Ticket 格式

```yaml
---
id: {目標版本}-TD-{序號}
title: "[TD] {描述}"
type: IMP
status: pending
priority: {根據風險等級}
created: {日期}
source: tech-debt-capture
original_version: {發現版本}
---

# {Ticket ID}: [TD] {描述}

## 來源
- 發現於: v{版本} Phase 4
- 工作日誌: {工作日誌連結}
- 原始 TD ID: {TD-ID}

## 目標
修復技術債務：{描述}

## 驗收條件
- [ ] 債務已修復
- [ ] 相關測試通過
- [ ] 無新增技術債務
```

---

## 相關指令

| 指令 | 用途 |
|------|------|
| `/tech-debt-capture` | 自動捕獲並建立 Ticket |
| `/ticket track summary` | 查看所有 Ticket 包含 TD |
| `/version-release check` | 檢查是否有未處理的高風險 TD |

---

## 禁止行為

| 禁止行為 | 正確做法 |
|---------|---------|
| 忽略技術債務 | 記錄到工作日誌 |
| 直接修復（超出當前範圍） | 建立 Ticket 排入後續版本 |
| 將高風險 TD 延後太久 | 必須在下個 Patch 版本處理 |

---

## 相關文件

- @.claude/agents/cinnamon-refactor-owl.md - Phase 4 代理人
- @.claude/rules/core/quality-baseline.md - 品質基線
- @.claude/pm-rules/ticket-lifecycle.md - Ticket 生命週期

---

**Last Updated**: 2026-05-12
**Version**: 2.1.0 — 新增「TD 清單即時校準（td-status）」章節：Phase 3a/3b/4 三節點呼叫時機、輸出說明表、校準後動作表（W10-083 / PC-094 落地）
