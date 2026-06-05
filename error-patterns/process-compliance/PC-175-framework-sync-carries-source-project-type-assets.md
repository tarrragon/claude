# PC-175: 框架跨專案 sync 攜帶來源專案類型專屬資產漏入目標專案

## 摘要

`.claude/` 框架經跨專案 sync 傳遞時，會把**來源專案類型專屬**的資產（Flutter 的 dart MCP 工具引用、Flutter monorepo 三層同步測試、Flutter Bloc hook 預設）一併帶入**不同類型**的目標專案（如 Chrome Extension / JS）。這些資產在目標專案類型下或為失效死碼（import 不存在函式、collection error）、或為誤導性指引（讀者照抄呼叫不存在的工具）。正確收斂方向是 project-type-generic：移除/skip 來源專屬資產，保留語言/平台無關的通用資產；reimplement 來源專屬功能是反模式（會復活目標專案不需要的能力）。

## 症狀

- 測試 import 不存在的函式造成 pytest collection error，全套件需 `--ignore` 排除某檔（W1-038：`test_monorepo_version_sync.py` import 已被 W4-002 移除的 `get_monorepo_version`）
- 工具使用指南 / 速查表硬編碼某語言專屬 MCP 工具名，對目標專案類型不適用（W1-035：dart MCP `l*` 引用集中於 Flutter agent，對 Chrome Extension 專案無對應 server）
- hook / detector 內建來源框架預設（Flutter Bloc 的 `test/*.dart`、Layer 1-5），跨 sync 後對目標專案類型誤判（feedback_hook_flutter_preset_assumption）
- 同一 session 跨多個 ticket 重複遇到「Flutter 資產在非 Flutter 專案」的變體

## 根因

框架資產分兩類，但 sync 機制不區分：

| 類別 | 範例 | 跨專案 sync 後 |
|------|------|---------------|
| project-type-generic（語言/平台無關） | ticket CLI、rg 用法、WRAP 框架、文件明示性規則 | 直接可用 |
| project-type-specific（來源專案類型專屬） | dart MCP 工具、Flutter monorepo pubspec 三層同步、Flutter Bloc test layer 預設 | 對不同類型目標專案失效或誤導 |

framework 設計目標是跨專案重用，但「重用」只對 generic 類成立；specific 類被 sync 帶走後，在目標專案沒有對應的 runtime（無 dart MCP server）、檔案（無 `ui/pubspec.yaml`）或語言（非 Dart），成為死碼或誤導。延續 PC-173（MCP 工具名漂移）與 PC-083（framework footer 污染）的同源主題：靜態框架資產與目標 runtime 環境無自動對齊機制。

## 案例：version-release 與 search-tools-guide 的 Flutter 殘留（2026-06-04）

| 資產 | 來源專案類型 | 目標（本專案）狀態 | 處理（W1-035 / W1-038） |
|------|------------|------------------|----------------------|
| `test_monorepo_version_sync.py` | Flutter monorepo（L2 `ui/pubspec.yaml`） | 無 pubspec；import 函式已 W4-002 移除 | 移除（替代 API `check_version_sync_dual` 已有覆蓋） |
| search-tools-guide 速查表 dart MCP 引用 | Flutter（dart MCP server） | 無 dart MCP server | 保留（project-type-generic 框架資產，對 Flutter 專案正確）+ 速查表版本無關化 |

兩者方向不同的關鍵：dart MCP 引用本身是**正確的 Flutter 工具名**（保留供 Flutter 專案用），而 monorepo 測試 import 的函式**已被刪除**（死碼，移除）。判別準則見下方防護表。

## 防護（判別與處理決策表）

遇到「疑似來源專案類型專屬資產」時，依下表決策：

| 條件 | 處理 | Why |
|------|------|-----|
| 資產引用的符號/檔案在當前 runtime 不存在（import error / collection error / 函式已移除） | **移除**（或 `pytestmark.skip` + try/except import，若需保留歷史，TEST-007 慣例） | 死碼無覆蓋價值，徒增維護面與假性紅燈 |
| 資產是**正確**的來源平台工具名/設定，僅本專案類型不啟用 | **保留**（屬 project-type-generic 框架資產） | 對來源類型專案正確；移除會破壞其他專案的 sync |
| 資產為硬編碼指引且會誤導讀者（照抄呼叫不存在工具） | **改版本/平台無關描述**（能力分類 + 發現指引取代硬編碼名） | 從源頭杜絕漂移與誤導（PC-173 收斂方向） |

**Why**：未區分「死碼」與「他類型正確資產」會導致兩種錯誤——把 generic 資產誤刪（破壞其他專案 sync），或把死碼 reimplement（復活目標專案不需要的能力）。

**Consequence**：reimplement 來源專屬功能會在目標專案引入永久維護負債（如為 Chrome Extension 復活 Flutter pubspec 同步）；保留死碼會持續造成 collection error 遮蔽該檔測試覆蓋並需 `--ignore` workaround 累積。

**Action**：先 `git log -S '<symbol>'` / `grep -c 'def <symbol>'` 確認符號存廢與移除來源 commit；確認屬死碼則移除（替代 API 有覆蓋時）；屬他類型正確資產則保留；屬誤導性指引則版本/平台無關化。

## 與其他規則 / PC 的關係

| 對象 | 關係 |
|------|------|
| PC-173（MCP 工具名漂移） | 本 PC 的特例（MCP 名面向）；本 PC 為通用化（涵蓋測試 / hook / 文件） |
| PC-083（framework footer 污染） | 同源——框架資產與專案/環境耦合 |
| memory `feedback_hook_flutter_preset_assumption` | 本 PC 的 hook 面向跨對話記憶對應 |
| quality-baseline 規則 5 | 跨 sync 發現的死碼/誤導資產必須建 ticket 追蹤 |

## 案例文件來源

W1-035（MCP 工具名漂移盤點 ANA）+ W1-037（search-tools-guide 版本無關化）+ W1-038（移除 Flutter monorepo 過時測試），2026-06-04，commits `7cc669d5` / `42464335` / `6c536002`。
