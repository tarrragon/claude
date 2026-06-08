---
id: PC-180
title: 雙專案共用 sync 時混淆「共享 repo 納入範圍」與「本地保留範圍」致框架調整誤失
category: process-compliance
severity: medium
status: active
created: 2026-06-08
related:
- PC-166
- PC-175
- PC-109
---

# PC-180: 雙專案共用 sync 時混淆「共享 repo 納入範圍」與「本地保留範圍」致框架調整誤失

## 摘要

兩個專案共用一套 `.claude/` sync 機制（full overlay pull）時，「某檔該不該推回共享 repo」與「某檔本地專案該不該保留」是**兩個獨立決策維度**。PM 在處理 sync 衝突時容易把它們耦合成單一決策——「不納入共享 repo」被錯誤推導為「本地該刪除」，導致本地專案合法的框架調整（error-pattern 知識、專屬 hook、skill 落地層）在「採納遠端版」時被一併丟棄。正解不是「採納遠端 vs 還原本地」二選一，而是用 sync-preserve 清單（first-line 原地保留）讓 pull 自動保留本地框架調整。

## 症狀

- 處理 sync-pull 後的 `.sync-conflicts/`（本地特有檔暫存區）時，PM 把「不推回共享 repo 的檔」直接歸類為「本地可失去」
- 準備 commit「採納遠端版」，commit 範圍含本地框架調整的刪除（git status 顯示為 `D`）
- 本地專案的 error-pattern 知識 / 專屬 hook / 專案落地層被當作「同步衝突的犧牲品」
- 決策表面合理（「這些不該進共享 repo」為真），但結論（「所以本地刪除」）是錯誤跳躍

## 觸發案例

### 1.0.0-W1-009 round-trip 驗證（2026-06-08）

**情境**：V1 與 APP（book_overview_app）共用 `tarrragon/claude.git`。round-trip 驗證中 APP pull 後，20 個 APP 特有檔被修復版 pull 轉至 `.sync-conflicts/`（second-line 保護，正確）。

**PM 錯誤**：階段 3 規劃「APP push 推回 2 檔，其餘 18 檔不推共享 repo」。WRAP 分析正確判定「18 檔不該推回共享 repo」（PC 編號碰撞、hook 架構分歧、外移方向），但 PM 把這個結論錯誤延伸為「APP commit 採納遠端版，失去這 18 檔（已備份）」——將「共享層決策」耦合成「本地層決策」。

**用戶反饋糾正**：用戶質疑「合理來說那些內容應該是框架的調整」，迫使 PM 重新檢視 18 檔內容。檢視後確認 12 個是 APP 合法框架調整（PC-177/178/179 知識、pre-fix-evaluation-hook、wrap-decision project-integration 8），只有 6 個是垃圾（過時 V1 conventions、build 產物、runtime lock）。

**第二次反饋揭穿假解**：PM 一度推薦「還原 APP 到 pull 前」，用戶反問「還原不是一樣要先跑 sync-pull 嗎？」——揭穿還原是逃避（下次 pull 框架調整又會跑進 `.sync-conflicts`，無限循環），導向 `sync-preserve.yaml`（first-line）根本解。

## 根本原因

### 表層原因

| 維度 | 說明 |
|------|------|
| 決策耦合 | 「共享 repo 納入範圍」與「本地保留範圍」是正交的兩軸，PM 用單一 WRAP 分析同時下兩個結論，未區分軸別 |
| .sync-conflicts 語意誤讀 | `.sync-conflicts/` 是「待人工決定保留哪些回主樹」的暫存區，PM 誤讀為「待丟棄區」 |

### 深層原因

| 維度 | 說明 |
|------|------|
| full overlay sync 的隱含張力 | 「採納上游」與「保留本地演化」本質衝突，PM 預設「sync = 向上游對齊」，忽略「本地專案有合法的獨立演化」 |
| preserve 機制認知缺失 | sync-pull 的兩層防護（preserve first-line 原地保留 / .sync-conflicts second-line 不誤刪）中，PM 只看到 second-line，未想到 first-line 才是「本地框架調整自動保留」的正解 |

## 正確做法

### 分離兩個決策維度

| 決策軸 | 問題 | 與另一軸的關係 |
|--------|------|--------------|
| 共享 repo 納入 | 此檔該不該進共享框架供所有專案 pull？ | 「否」不蘊含本地該刪除 |
| 本地保留 | 此檔是本地專案的合法框架調整嗎？ | 「是」則本地必須保留，無論是否納入共享 repo |

**判別準則**：一個檔可以是「本地該保留」但「不納入共享 repo」（如專案專屬 error-pattern、與上游同編號不同內容的知識、專案落地層）。這類檔用 preserve 清單原地保留，不推共享 repo。

### preserve 清單（first-line 根本解）

本地專案的框架調整路徑登錄 `sync-preserve.yaml`，pull 時自動原地保留（不被 overlay、不轉 .sync-conflicts）：

```yaml
preserve:
  - error-patterns/process-compliance/PC-XXX-專案專屬.md
  - hooks/專案專屬-hook.py
  - skills/<skill>/references/project-integration/*.md
```

**為何 preserve 優於「還原 pull 前」**：還原是逃避——下次 pull 框架調整又轉 .sync-conflicts，需反覆手動還原。preserve 讓「pull 自動保留本地演化」成為 first-class 行為。

## 預防措施

### PM 處理 sync 衝突時的檢查

| 檢查項 | 動作 |
|--------|------|
| `.sync-conflicts/` 內每個檔 | 先問「這是本地合法框架調整嗎？」（看內容，非看是否推共享 repo） |
| 準備 commit「採納遠端版」含 `D` 刪除 | 逐一確認被刪的是垃圾，不是本地框架調整 |
| 本地框架調整確認後 | 登錄 `sync-preserve.yaml`，未來 pull 自動保留，而非每次手動還原 |

### 與既有機制的關係

- 修復版 sync-pull 已提供 second-line 防護（`.sync-conflicts/` 不誤刪），但 first-line（preserve 清單）需專案各自維護
- 專案專屬框架調整與共享 repo 的編號/架構衝突，屬獨立議題（見 1.0.0-W1-019 PC 編號碰撞分析）

## 相關規則 / 經驗

- PC-166（PM 敘事幻覺 / git ground truth）— 本案 PM 一度用錯誤路徑格式驗證 `.sync-conflicts/`（扁平命名 `/`→`__`）產生 19 個 false negative，差點誤報 BUG 復發，靠「先看實際檔案結構」救場
- PC-175（framework sync 攜帶專案類型資產）— 反向情境：本案是「本地框架調整不該因 sync 丟失」，PC-175 是「他專案資產不該污染本地」，同屬「sync 邊界」家族
- PC-109（claude runtime state 缺 sync 排除）— 同屬 sync 邊界判定
- quality-baseline 規則 5（所有發現必須追蹤）— 本案 spawn 1.0.0-W1-019（PC 編號碰撞）+ W1-020（blocker 整合）
- ai-communication-rules 規則 5（權力不對等下的 receiver-end 前提查驗）— 本案兩次用戶反饋糾正 PM 的決策耦合與假解，體現 receiver 端質疑的價值

---

**Last Updated**: 2026-06-08
**Source**: 1.0.0-W1-009（V1↔APP sync round-trip 驗證，用戶兩次反饋糾正 PM 決策維度耦合 + 揭穿「還原」假解，導向 sync-preserve.yaml first-line 根本解）
