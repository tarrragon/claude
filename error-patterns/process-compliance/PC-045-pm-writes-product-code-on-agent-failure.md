---
id: PC-045
title: PM 代理人失敗時自行撰寫產品程式碼
severity: high
category: process-compliance
first_seen: "2026-04-07"
occurrences: 2
status: active
---

# PC-045: PM 代理人失敗時自行撰寫產品程式碼

## 問題描述

PM 派發背景代理人（run_in_background: true）執行 GREEN 實作後，檢查發現代理人未修改 source 檔案。PM 判斷「代理人沒做到」，直接自己撰寫產品程式碼（resolveTagsForDisplay、_renderTagCellHtml、setTagFilter、clearTagFilter、applyCurrentFilter 管線擴充等），違反 pm-role.md 核心禁令。

## 發生場景

### 第 1 次（W2-007.2 Tag 顯示元件）

```
PM 派發背景代理人 → 代理人完成但 source 未修改
→ PM 檢查 git status 發現無變更
→ PM 跑測試確認 5 個 RED 測試仍 FAIL
→ PM 自己寫了 resolveTagsForDisplay + _renderTagCellHtml + createBookRow 修改
→ PM commit + merge
→ 代理人延遲通知到達（結果一致但已浪費）
```

### 第 2 次（W2-007.3 Tag 篩選 widget）

```
PM 派發背景代理人 → 同樣模式
→ PM 自己寫了 tagFilterState + setTagFilter + clearTagFilter + applyCurrentFilter 擴充
→ PM commit + merge
→ 代理人延遲通知到達
```

## 違反的規則

| 規則 | 條文 | 違反行為 |
|------|------|---------|
| pm-role.md | 「主線程禁止：寫程式碼（產品程式碼）」 | PM 撰寫了 6+ 個方法的產品程式碼 |
| pm-role.md | 「主管的價值在於讓團隊人力發揮到極致，不在於自己解決問題」 | PM 跳過代理人直接解決 |

## 根因分析

### 直接原因

PM 將「代理人未在預期時間內完成」等同於「代理人失敗」，觸發了「我來做比較快」的判斷。

### 深層原因

1. **pm-role.md 缺乏「代理人失敗時的 SOP」**：規則只說「禁止寫程式碼」，但沒有定義代理人失敗時 PM 應該做什麼。PM 面對「測試還是 FAIL、代理人沒做到」的情境，規則沒有提供替代行動路徑。

2. **背景派發的等待機制不明確**：規則沒有區分「前台派發（等結果）」和「背景派發（不等結果）」的使用時機。PM 用了背景派發但心理上期待即時結果，導致等不及就自己做。

3. **「PM 可寫 RED 測試」的邊界不清**：PM 寫了 RED 測試後，心理上已進入「這個功能的實作者」角色，從寫測試滑坡到寫實作的邊界沒有明確斷點。

## 正確做法

| 情境 | 錯誤做法 | 正確做法 |
|------|---------|---------|
| 代理人背景派發後未完成 | PM 自己寫程式碼 | 等代理人完成，或用 SendMessage 催促 |
| 代理人確認失敗（回合耗盡） | PM 自己做 | 分析失敗原因 → 調整 prompt → 前台重新派發 |
| 小任務想快速完成 | 背景派發然後自己做 | 前台派發（不用 run_in_background），等結果 |

### PM 代理人失敗 SOP（已新增到 pm-role.md v3.1.0）

```
代理人失敗/未完成
    |
    v
1. 確認失敗類型（回合耗盡/改錯檔案/完全沒改/改壞測試）
    |
    v
2. 調整 prompt → 重新背景派發
    |
    v
3. 立刻切換到其他 Ticket 的準備工作（不空等）
    |
    v
4. 代理人完成通知到達 → 回來驗收
    |
    v
5. 如果連續 2 次失敗 → 建立 incident Ticket
    |
[禁止] 永遠不自己寫，也不空等
```

### PM 正確的工作模式

```
PM 的一天（理想狀態）：

派發 Ticket A 的代理人（背景）
    → 切換到 Ticket B 的 Context Bundle 準備
    → 切換到 Ticket C 的規格分析
    → A 的代理人完成通知到達 → 驗收 A → commit
    → 派發 Ticket D 的代理人（背景）
    → 繼續 B 的準備工作
    → ...
```

PM 管理的是**整個專案的流動**，不是**一個 Ticket 的完成**。

## 防護措施

1. **規則層面**：pm-role.md 新增「代理人失敗時的 SOP」章節
2. **規則層面**：pm-role.md 明確「PM 可寫 RED 測試」但「PM 寫完測試後必須停手，GREEN 階段只能派發」
3. **規則層面**：定義前台/背景派發的選擇標準
4. **認知層面**：PM 寫完 RED 測試是一個角色切換斷點——從「規格定義者」回到「派發者」

## 相關文件

- .claude/rules/core/pm-role.md - PM 角色行為準則
- .claude/pm-rules/decision-tree.md - 主線程決策樹
- .claude/error-patterns/process-compliance/PC-042-rule-file-too-large-for-agent.md - 代理人回合耗盡
