---
id: IMP-GPD-002
title: Hook 將 Bash 的 tool_response 整包字串化比對，誤把 bashEditDiff 中他人正在寫的程式碼當成命令輸出
status: active
severity: 高
---

# IMP-GPD-002: Hook 將 Bash 的 tool_response 整包字串化比對，誤把 bashEditDiff 中他人正在寫的程式碼當成命令輸出

## 基本資訊

- **Pattern ID**: IMP-GPD-002
- **分類**: 實作 bug（implementation）
- **來源版本**: 0.5.0
- **發現日期**: 2026-10-14
- **風險等級**: 高
- **影響範圍**: 任何在 PostToolUse 解讀 Bash 命令輸出的 hook（本案為測試後置 hook 的失敗評估）
- **姊妹模式**: PC-SCLK-007（讀錯 payload 欄位而靜默失效）。方向相反：PC-SCLK-007 讀到的範圍是空的，本模式讀到的範圍過大

---

## 問題描述

### 症狀

全綠的測試命令（結束碼 0、摘要全數通過）被 hook 判為「TEST FAILURE，必須開 Ticket」或「語法錯誤」。同一個命令有時誤報、有時不誤報，每次列出的錯誤項數也不同；以命令的 stdout 原文重跑錯誤分類，結果是空的。

多個 session 共用同一個 checkout 時頻繁發生，單獨工作時幾乎不出現。

### 根因

Claude Code 的 PostToolUse payload 中，Bash 的 `tool_response` 是 dict，頂層鍵為 `stdout`、`stderr`、`interrupted`、`isImage`、`noOutputExpected`、`bashEditDiff`。其中 `bashEditDiff` 是**命令執行期間工作區內被改動檔案的 diff**，與命令本身的輸出無關。

hook 以 `str(tool_response)` 把整個 dict 轉成字串再比對錯誤樣式，因此比對到的是共用工作區中他人正在寫的程式碼。測試檔中出現 `FAILED`、`Expected ')'` 這類字樣再正常不過，於是誤報。誤報與否取決於「命令執行期間誰在改什麼檔」，與測試結果無關，這也是症狀看起來隨機的原因。

`str(dict)` 另有一個副作用：換行被轉成字面的 `\n`，以 `^` 或 `\w` 錨定的樣式在 repr 字串上的行為與原始輸出不同。

### 為何難以發現

評估紀錄只保存「命中的樣式」，不保存「命中的原文」。真告警與假告警留下的紀錄完全同形，從紀錄看不出 `FAILED` 來自哪裡。只有在紀錄中加入命中位置前後的原文，才會看到命中點落在 `bashEditDiff` 內。

---

## 解決方案

1. **只取命令輸出欄位**：tool_name 為 Bash 且 tool_response 為 dict 時，只取 `stdout` 與 `stderr`，以真實換行串接後再比對。其他工具的回應結構不同，維持原行為，避免連帶破壞它們的判定
2. **欄位缺失時 fail-open**：Bash 回應缺 `stdout`／`stderr` 時不做評估，寫 debug 日誌
3. **評估紀錄保存證據**：每筆命中記下前後約 80 字元的原文，並記錄 tool_response 的型別與頂層鍵，日後任何誤報都能直接追到來源

---

## 延伸教訓：修誤報的過程中容易引入漏報

本案在修正過程中依序出現下列形態，每一種都要有對應的對照測試：

| 形態 | 方向 | 處置 |
|------|------|------|
| 一般文字（commit 標題、票面標題）中的 failed／FAILED 被命中 | 誤報 | 不要靠持續收緊錯誤樣式解決，一般文字可能含任何字樣；改以「辨識全綠摘要」為主要判據 |
| 全綠摘要不在行首（如 `rc=0 108 passed in 2s`）而未被辨識 | 誤報 | 綠燈摘要樣式不要求行首 |
| 綠燈捷徑「任一處命中即整段放行」，同一命令多次測試時一次全綠蓋掉其他次的失敗 | 漏報 | 綠燈判定前先排除：任一行出現失敗摘要即不走綠燈捷徑 |
| 綠燈前置排除與錯誤分類各維護一份失敗摘要樣式，兩份漂移 | 漏報 | 失敗摘要收斂為單一來源，兩處引用同一份 |
| 把錯誤樣式改為區分大小寫，使只靠小寫 failed 命中的框架摘要漏報 | 漏報 | 改動判定樣式前，先為每個支援的框架建立真實失敗輸出的正向對照 |

---

## 預防措施

- 在 PostToolUse 讀取 Bash 輸出時，只讀 `stdout`／`stderr`；不要把整個 `tool_response` 轉成字串使用
- 任何「判定命令結果」的 hook，其紀錄須保存命中原文，而不只保存規則名稱
- 修正判定樣式時，同時保留誤報方向（一般文字不應命中）與漏報方向（各框架真實失敗須命中）兩組對照，且以 stdin 餵入 payload 的端到端方式驗證，不只測內部函式

---

## 相關

- PC-SCLK-007：讀錯 payload 欄位而靜默失效（範圍過小）
- `.claude/rules/core/test-assertion-design-rules.md` 規則 E2：守衛的測試必須含正向對照輸入
