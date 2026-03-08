---
id: DOC-008
title: 同一文件內定義替換遺漏（局部替換）
category: documentation
severity: medium
discovered: 2026-03-08
source_ticket: 0.1.0-W21-002
detected_by: parallel-evaluation（W22 Consistency 視角掃描）
---

# DOC-008：同一文件內定義替換遺漏（局部替換）

## 症狀

修復文件中的定義不一致問題時，只修改了其中一處，同一文件的其他位置仍保留舊定義。
事後由多視角掃描（parallel-evaluation）發現遺漏。

**典型症狀**：

- 修改一個定義（如豁免條件描述）後，grep 掃描發現同一文件仍有舊字串殘留
- 並行評估的 Consistency 視角報告「不一致問題仍然存在」，但主 Ticket 已 complete

## 根因分析

### 問題行為

執行文件定義替換時，採用**精準定位（Find + Edit 特定行）**策略，而非**全局替換（global replace）**：

1. 問題分析階段用 grep 找到「最明顯」的一處
2. 只對那一行執行 Edit（old_string → new_string）
3. 沒有驗證同一文件是否還有其他相同字串

### 為何容易發生

- 文件長度超過 200 行時，grep 結果只顯示第一個 hit 就停止掃描
- 問題描述為「位置 X 有問題」→ 修改 X → 完成，未問「是否還有其他地方？」
- Edit 工具的 `replace_all` 參數預設為 false，不提醒是否有多個匹配

## 解決方案

### 修復步驟

1. 執行全局搜尋確認所有殘留位置：
   ```bash
   grep -n "舊定義文字" 目標文件.md
   ```
2. 逐一修復或使用 `replace_all: true` 執行一次性替換

### 預防措施

#### 原則：替換前後都要 grep

做任何定義替換時，強制執行：

```
1. 替換前：grep -n "舊字串" 文件 → 確認所有位置
2. 執行替換（replace_all: true 或逐一 Edit）
3. 替換後：grep -n "舊字串" 文件 → 確認 0 個結果
```

#### 使用 replace_all 的判斷標準

| 情境 | 建議 |
|------|------|
| 替換純文字定義（無上下文差異） | 使用 `replace_all: true` |
| 替換有細微上下文差異的文字 | 先 grep 確認所有位置，再逐一 Edit |
| 不確定是否有多處 | 先 grep，再決定策略 |

## 相關 Pattern

- DOC-005: cross-document-principle-desync（跨文件不一致）
- IMP-003: refactoring-scope-regression（重構遺漏影響範圍）

## 防護

**檢查點**：修改文件定義後，執行 `grep -n "舊字串" 文件` 確認 0 個結果再關閉 Ticket。

**parallel-evaluation 角色**：Consistency 視角是此類問題的自動防護網，可以在 post-wave 掃描中發現遺漏點。

---

**Last Updated**: 2026-03-08
**Version**: 1.0.0
