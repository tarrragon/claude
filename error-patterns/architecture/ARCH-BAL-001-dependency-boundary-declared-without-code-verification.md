---
id: ARCH-BAL-001
title: 架構依賴方向底線未用程式碼 import 鏈驗證，導致底線與現況矛盾
severity: high
category: architecture
source_ticket: 0.1.0-W2-014
created: 2026-07-22
---

# ARCH-BAL-001：架構依賴方向底線未用程式碼 import 鏈驗證

## 症狀

架構規範文件（domain map / 分層規範 / 依賴方向底線）宣告一條「X 只依賴 Y」式的依賴方向規則，但該規則從未對照現有程式碼的實際 import / 呼叫鏈驗證。結果底線在文字上成立、在程式碼中被打臉——按底線拆檔或重構時，才發現實際存在底線禁止的依賴邊。

**本案具體樣態**（W2-014 domain map）：

- 底線寫「read-model bundle 僅依賴 `Ledger`」。
- 但 `leverageMultiple` / `stressNetWorth` / `allocation` / `netWorthChangePct` 全都消費 `Totals` / `totalsAt`（另一 read-model「Networth」的概念）。
- 按底線拆檔後 `leverage.dart` 必須 `import networth.dart`——這是底線明文禁止的 read-model → read-model 依賴。

## 根因

架構文件描述的是**目標邊界（intended design）**，撰寫者憑心智模型下筆，未執行「拿底線去 grep 現有程式碼 import / caller」這一步。目標狀態與現況狀態在文字層無法區分：底線讀起來像對現況的斷言，實際是對未來的期望。當共享 kernel（本案的 `Totals`）被多個 read-model 消費時，心智模型容易漏看它已是跨 bundle 的共同依賴，誤把它歸進某一個 read-model。

**一般化**：任何「A 層只依賴 B 層」的架構斷言，若未用工具驗證 A 的實際 import 集合，就有與現況矛盾的風險。共享工具函式、kernel、型別是最常見的漏看點。

## 解決方案

1. **抽共享 kernel**：把被多個同層模組消費的概念（本案 `Totals`/`totalsAt`/`_val`）抽為獨立 kernel（`domain/valuation.dart`），置於被依賴方（比 read-model 更底層）。
2. **底線改 DAG 措辭**：從「read-model 僅依賴 Ledger」改為「read-model 依賴 Valuation kernel + Ledger，彼此不互相依賴（允許共同依賴 kernel，不允許成環——DAG，非禁止共享）」。
3. 修正措辭而非改架構——原架構無循環依賴，只是底線把「共同依賴 kernel」誤述為「禁止」。

## 預防措施

**撰寫任何依賴方向底線前，先用工具驗證現有 import / caller 鏈**：

| 斷言形式 | 驗證指令 |
|---|---|
| 「X 只依賴 Y」 | `grep -n "import" <X 的檔案>` 或 codegraph callees(X)，確認 import 集合 ⊆ {Y} |
| 「A 不依賴 B」 | `codegraph_impact` / `grep -rl "B" <A 目錄>`，確認無命中 |
| 共享工具是否跨模組 | `codegraph_callers(<工具符號>)`，caller 跨 2+ 模組即為共享 kernel，須獨立分層 |

**區分目標 vs 現況**：架構文件描述「目標邊界」時明文標註（如「此為目標邊界，非現況；接線見 §X」），避免讀者把期望誤當現況斷言。

**多視角審查抓補**：本案由 parallel-evaluation 的 linux 常駐委員抓出。架構規範文件（含依賴底線）產出後應過一輪架構視角審查，用程式碼佐證每條底線。

## 相關

- 來源：`0.1.0-W2-014`（domain map 四視角審查，linux H1 發現）
- 產物：`docs/domain-map.md` §2 依賴方向底線、§4.1 目標 vs 現況標註
- 相關規則：`.claude/rules/core/tool-output-trust-rules.md`（記錄平面 vs 世界平面：架構文件是記錄平面，程式碼 import 鏈是世界平面，重大斷言以世界平面為準）
