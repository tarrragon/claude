---
id: PC-LLM-010
title: UI 功能測試綠但 runtime 不可達（按鈕落在孤兒 widget / callback 未被 production 接線）
category: process-compliance
severity: medium
status: active
created: 2026-06-07
---

# PC-LLM-010: UI 功能測試綠但 runtime 不可達（按鈕落在孤兒 widget / callback 未被 production 接線）

> **來源**：本檔於 v3.4.0 依 canonical issue #63 從 git 歷史復原。曾用編號：canonical 原號 `PC-178-ui-test-green-but-runtime-unreachable`；某 consumer 本地重編號 `PC-182-ui-test-green-but-runtime-unreachable`。2026-06 兩次未宣告的 sync-push `--clean` 先刪 182 副本、再刪 178 原檔（推送方都從未擁有該檔）。flat 號屬凍結核心，PC-178 另有 consumer 本地原生 pattern 使用，復原改用前綴號。仍保有 `PC-182-ui-test-...` 副本的 consumer，可刪除該副本改用本檔。

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | process-compliance |
| 來源版本 | 3.4.0 |
| 風險等級 | 中 |
| 首次觀察 | 2026-06-07 |

## 摘要

驗收 UI 入口 / 導航 / 可見性類功能時，「相關 widget 測試綠」不等於「使用者實際看得到 / 點得到」。Widget 測試常以 ProviderScope override、stub ViewModel、測試自帶 callback 隔離元件，這使「把 UI 元素加在 production 從未渲染的孤兒 widget」或「採 callback 模式但無 production 父層傳入 callback」的實作仍測試全綠——但實機畫面完全沒有該功能。修正方向：驗收 UI 可達性類功能時，追查 production 渲染鏈（page → builder/extension → 實際渲染的 widget），grep 確認目標 widget 真的被 production 實例化、callback / 依賴真的被 production 父層傳入，勿只看測試綠燈。

## 症狀

- 實作代理人回報「功能完成，相關測試全綠（如 +27）」，PM 若僅核對測試結果即放行。
- 元件層 widget 測試在隔離環境（override / stub / 測試自帶 callback）下全綠。
- 實機操作該畫面，使用者看不到 / 點不到該 UI 入口或功能。
- 目標 widget 在 lib/ 中僅有定義 + 測試引用（grep production 無實例化），即孤兒 widget。
- 或元件採 callback 模式（`onX` 回調），但所有 `onX:` 傳值都在 test/，production 父層從未傳入。

## 根因（隔離測試遮蔽 production 接線缺口）

UI 元件測試的本意是隔離驗證單一元件行為，因此會自行提供依賴（override provider、stub VM、傳入測試用 callback）。這層隔離正是遮蔽源：

| 接線缺口 | 元件測試是否會綠 | runtime 是否可達 |
|---------|----------------|----------------|
| UI 元素加在孤兒 widget（production 不渲染該 widget） | 綠（測試直接 pump 該 widget） | 不可達（使用者看不到該 widget） |
| 元件 callback 無 production 父層傳入 | 綠（測試自帶 callback） | 不可達（按鈕 onPressed 為 null 或元件 gated 不渲染） |
| 元件加在正確 widget 且 production 接線 | 綠 | 可達 |

三種情況元件測試都可能綠，只有第三種 runtime 可達。測試綠燈無法區分三者——必須追查 production 渲染鏈與接線才能判別。此為 test-green≠runtime-correct（PC-165 / quality-baseline 規則 1 邊界）在「UI 可達性」面向的具體變體。

## 案例：資訊入口按鈕落在孤兒 widget（2026-06-07）

某用例需在書庫卡片右上角加一個資訊入口按鈕，導航至補充資訊頁。實作代理人（v1）將按鈕加在一個管理用卡片 widget，並採 callback 模式（`onSupplementInfo`），元件測試 +27 全綠。PM 二次驗收追查 production 渲染鏈發現：

- production 書庫列表實際渲染路徑為 page body → extension 方法 → `ListView.separated` → item builder 回傳的 inline `ListTile`。
- 該卡片 widget 與另外兩個卡片 widget 皆為孤兒 widget（grep lib/ 僅定義 + 測試引用，production 不渲染）。
- `onSupplementInfo` 所有傳值都在 test/，production 無父層傳入。

結論：按鈕落在 production 從未渲染的孤兒 widget + callback 無 production 接線 → 測試綠但實機書庫卡片完全無此入口。修正版本將按鈕移至 production item builder 的 ListTile + 直接 `Navigator.push`，並新增「點擊導航至補充資訊頁」整合測試（走實際書庫渲染路徑），實測通過才確認 runtime 可達。

## 防護（UI 可達性驗收順序）

| 步驟 | 動作 | 目的 |
|------|------|------|
| 1 | 確認目標 widget 是否被 production lib 實例化（`grep -rn "TargetWidget(" lib/`，排除定義檔與 test/） | 排除孤兒 widget——加在孤兒 widget 的 UI 使用者永遠看不到 |
| 2 | 追查 production 渲染鏈（page → builder / extension → 實際 widget），確認 UI 落在真正渲染的元件 | 確認落點正確 |
| 3 | 若採 callback 模式，grep `onX` 傳值是否存在於 production lib（非僅 test/） | 排除「callback 永不被 production 傳入」 |
| 4 | 驗收測試須含「走 production 渲染路徑」的整合 / widget 測試（pump 真實 page，而非僅 pump 孤立元件） | 讓測試本身覆蓋 runtime 可達性，而非只測隔離元件 |

**Why**：UI 元件測試的隔離設計（override / stub / 自帶 callback）會讓接線缺口（孤兒 widget、callback 未接線）測試全綠，測試綠燈無法區分「可達」與「不可達」。

**Consequence**：PM 僅核對測試綠燈即放行，會讓「使用者看不到 / 點不到」的功能被當成已完成，commit 進主線後直到實機操作或下游整合才暴露，回溯與補做成本高（本案因此需 v1 → 二次驗收 → v2 兩輪派發 + PM 手動整合）。

**Action**：驗收 UI 入口 / 導航 / 可見性類功能時，依上表 4 步追查 production 渲染鏈與接線；對「UI 可達性」類 acceptance，要求驗收測試走 production 渲染路徑（pump 真實 page），不接受僅 pump 孤立元件的測試作為 runtime 可達性證據。

## 相關

- `.claude/error-patterns/process-compliance/PC-165-false-positive-fix-chain.md` — test-green≠runtime-correct 上位模式（訊息 / 日誌 / 跨模組面向）
- `.claude/rules/core/quality-baseline.md` 規則 1「邊界：測試綠燈不等於 Runtime 正確」
- `.claude/rules/core/test-assertion-design-rules.md`「延伸路由」
