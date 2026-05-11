---
id: IMP-071
title: ticket track append-log 在章節已有 placeholder 時建立重複內容
category: implementation
severity: low
created: 2026-05-11
related:
 - W17-190
 - W17-191
---

# IMP-071: ticket track append-log 在章節已有 placeholder 時建立重複內容

## 症狀

`ticket track append-log <id> --section "Problem Analysis" "<新內容>"` 執行後，ticket md 出現：

```markdown
## Problem Analysis
<!-- Schema[ANA/Problem Analysis]: 必填（.claude/pm-rules/ticket-body-schema.md） -->

### 問題根因

（待填寫：問題發生的直接原因是什麼？）

### 影響範圍

（待填寫：哪些檔案、模組或功能受影響？）

---

### 問題根因

<新內容...>
```

原有 placeholder + 新內容並存，且中間插入 `---` 分隔符。

## 觸發情境

| 條件 | 說明 |
|------|------|
| ticket create 時 body 含 schema 模板（含預設 placeholder 子標題） | ANA / IMP / DOC create 預設行為 |
| 後續用 append-log 補章節內容 | 預設操作 |
| append-log 不會清理原 placeholder | CLI 設計選擇 |

## 根因

### 根因一：append-log 是「附加」語意，不是「替換」

`ticket track append-log` 命名意圖明確是附加。但 schema 模板帶 placeholder 的場景，作者期望是「填入」而非「附加」。命名與作者直覺有 gap。

### 根因二：append-log 不檢測章節既有內容是否為 placeholder

CLI 直接定位 section header 後在末尾追加，不評估該 section 既有內容類型。若既有為 placeholder，理應替換而非追加。

### 根因三：分隔符 `---` 來自 schema 模板，與 PC-110 雙層共振

新追加內容 + 原 placeholder 之間出現 `---`（schema 模板章節分隔符），與 PC-110「`---` 切斷 schema section 擷取範圍」雙層共振：

- W17-071 已修 validator 不再把 `---` 當邊界（一定程度）
- 但作者視覺上看到「兩個區塊」會混淆任務狀態

## 案例

### W17-190 ANA（2026-05-11）

PM 寫 Problem Analysis：

```bash
ticket track append-log 0.18.0-W17-190 --section "Problem Analysis" "$(cat <<EOF
### 問題根因
...
EOF
)"
```

執行後 ticket md 出現：

```markdown
## Problem Analysis
<!-- Schema -->

### 問題根因  <- 原 placeholder
（待填寫：...）

### 影響範圍  <- 原 placeholder
（待填寫：...）

---  <- schema 模板分隔符

### 問題根因  <- 新內容
<實質分析...>
```

PM 需手動 Edit 移除前半 placeholder 區塊。

## 防護

### Layer 1：作者端（短期）

撰寫 ticket schema 模板章節後：

1. 用 append-log 前先 Read 該 section 確認既有內容類型
2. 若既有為 placeholder，改用 Edit 工具直接覆寫該 section
3. append-log 適用於：(a) 既無 placeholder 的空 section / (b) 在已有實質內容後遞增式 append

### Layer 2：CLI 端（根本，需 spawn IMP）

修改 `ticket track append-log` 邏輯：

- 加 `--replace-placeholder` flag：偵測既有內容若為 placeholder，整段替換而非附加
- 或讓 append-log 預設行為：先檢測 `_is_placeholder(existing_section_content)`，命中則替換
- 或新增 `ticket track fill-log <id> --section ...` 明確語意「填入而非附加」

### Layer 3：規則層（書面教學）

於 `.claude/skills/ticket/SKILL.md` 或 `.claude/pm-rules/ticket-lifecycle.md` 補：

- append-log 設計語意明確為「附加」，schema 模板場景應改用 Edit 或新 fill-log 命令
- 寫 ticket 章節前先 Read 該 section 確認既有內容

## 相關規則 / 文件

- PC-110：body-check-false-negative-via-schema-separator（同源根因之一）
- W17-071：validator 不再把 `---` 當 schema section 邊界（部分修復）
- ticket_skill：`/ticket track append-log` 子命令設計

## 範本：發現後的處理

1. 撞牆當下：用 Edit 工具清理重複區塊
2. 記錄 IMP-071（本文）+ 用戶 memory（雙通道）
3. spawn IMP 改 CLI（trigger：本 IMP 累積 ≥ 3 案例，或 PM 評估認知負擔成本後立即 spawn）

## 預估影響

- 觸發頻率：每張 ANA/IMP/DOC ticket 用 append-log 第一次填章節時都可能撞
- 修補成本（作者端）：每次 ~2-3 次額外 Edit 操作
- 累積成本：高頻 ticket 工作流下，每 session 多消耗 ~5-10K token 在清理
