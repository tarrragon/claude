---
id: IMP-GPD-004
title: 提醒類 hook 以 stderr 加 exit 0 輸出，提醒對模型不可見
severity: 中
status: active
---

# IMP-GPD-004: 提醒類 hook 以 stderr 加 exit 0 輸出，提醒對模型不可見

## 基本資訊

- **Pattern ID**: IMP-GPD-004
- **分類**: 實作（implementation）
- **風險等級**: 中（提醒靜默失效，hook 日誌顯示正常執行，無任何錯誤訊號）
- **來源版本**: 0.5.0
- **相關 Pattern**: IMP-055（方向相反但相鄰：stdout 純文字破壞 JSON 驗證；本模式為 stderr 對模型不可見）、IMP-048（stderr 顯示為 hook error）、IMP-003（Hook 失敗必須對用戶可見）

---

## 問題描述

### 症狀

- hook 的提醒句已寫入 stderr，日誌確認分支已執行，但模型的行為不受提醒影響
- 模型被問及 context 中是否有該提醒時回報沒有
- 提醒的設計受眾是模型（要它改行為），實際只有終端可能看到

### 根因

品質基線規則 4 只定義「Hook 失敗對用戶可見」，對應 stderr。hook 作者把它當成唯一輸出規則，連「提醒模型」的訊息也寫 stderr 並 exit 0。平台上 exit 0 的 stderr 不進模型 context。

實測（2026-10，`claude -p` 探針 hook，各事件註冊多支探針，每支以不同管道輸出唯一標記，再請模型列出 context 中的標記；探針另寫日誌確認分支實際執行）：

| 結論 | 內容 |
|------|------|
| 模型可見管道 | 僅四條：exit 2 的 stderr、decision block 的 reason、`additionalContext`、UserPromptSubmit／SessionStart 的純文字 stdout |
| 模型不可見 | exit 0 的 stderr、`systemMessage`、非標準欄位（`message`、無 decision 的 `reason`、`suppressOutput`） |
| 事件範圍 | UserPromptSubmit、PreToolUse、PostToolUse、PostToolUseFailure、Stop、SessionStart 的 exit 0 stderr 皆不可見 |

完整對照表見 `.claude/references/hook-architect-technical-reference.md`「事件類型與輸出管道的可見性對照表」。

### 與 IMP-055 的關係

| 項目 | IMP-055 | 本模式 |
|------|---------|--------|
| 錯誤管道 | stdout 純文字 | stderr 加 exit 0 |
| 失敗形態 | CLI 報 JSON validation failed（可見） | 無任何錯誤（靜默） |
| 修法交集 | 提醒內容走 `hookSpecificOutput.additionalContext` | 同左 |

兩者的共同正確解是 JSON 的 `additionalContext`；差別在於 IMP-055 有錯誤訊號，本模式沒有，所以更難被發現。

### 讀取側同型

PostToolUse 的 Bash `tool_response.stderr` 恆為空字串，stderr 併入 stdout；失敗命令改走 PostToolUseFailure，payload 帶 `error` 欄位而無 `tool_response`。依 `tool_response.stderr` 判斷失敗的分支恆不成立。

## 解決方案

1. 寫提醒類 hook 前先宣告受眾：模型、用戶、營運日誌，三者擇一或並列
2. 受眾含模型：經 `.claude/lib/hook_io.py` 的 `emit_hook_output` 輸出 `additionalContext`；需要使模型停手時用 exit 2 或 decision block
3. 受眾是用戶：stderr 加非零結束碼，或 SessionStart 純文字 stdout，符合規則 4 原意
4. PM-only 的訊息依「受眾評估 checklist」加受眾過濾（`emit_hook_output` 的 `audience="pm_only"`）

## 預防措施

1. 品質基線規則 4 的「提醒類輸出須宣告受眾」段（自動載入層）
2. 新建 hook 的測試加一條：受眾含模型時，斷言輸出走可見管道，而不是只斷言 hook 有執行
3. 驗證可見性靠真實 session 探針，hook 日誌與 exit code 都無法證明模型看得到

## 行為模式

作者讀到「失敗要寫 stderr」就把 stderr 當成對外輸出的通用管道。stderr 對用戶有效，對模型無效，兩種受眾共用同一個字面寫法而管道不同。規則只講一種受眾，是缺陷的來源。
