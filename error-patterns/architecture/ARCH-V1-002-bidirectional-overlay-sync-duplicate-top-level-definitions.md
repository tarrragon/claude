# ARCH-V1-002: 雙向 overlay sync 製造重複 top-level 定義（死碼 shadow 活碼）

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | ARCH-V1-002 |
| 類別 | architecture |
| source_ticket | 1.0.0-W1-085（parallel-evaluation 發現） |
| 發現日期 | 2026-06-16 |
| 風險等級 | 高 |

## 症狀

- 單一模組檔案內出現**同名 top-level 定義（函式 / 類別）重複兩次以上**，且實作不一致（例：一套基於新後端、一套基於舊後端，回傳型別都不同）。
- 直譯式語言（Python 等）取**最後一個定義**，先出現的同名定義從第一行起即為死碼，被靜默 shadow。
- 模組實際執行的是後出現的版本；「修復」可能只讓被執行的那版能跑，卻沒察覺另一版死碼並存。
- 文字層 diff / merge 無衝突（重複是 append 性質的新區塊），CI 若無「重複定義偵測」則綠燈通過。

## 根因分析

### 行為模式

兩條 sync 分支各自修改同一檔案：分支 A 把某函式在原位置改寫為新實作，分支 B 在檔案他處新增同名函式的另一版本。雙向 overlay sync 以**文字層合併**縫合兩者——因為兩段落在不同行區段、無文字衝突，合併器把兩個版本都保留，於是同名定義並存。語言的「後定義覆蓋前定義」語意使其中一版成為死碼。

### 結構性原因

1. **overlay sync 是文字層合併，非語意層合併**：它不理解「同名 top-level 定義只能有一個」這個語言語意，無衝突不代表語意正確。
2. **append 性質的變更不觸發文字衝突**：兩版分處不同行，merge 視為互不相干的兩段新增。
3. **無「重複定義」完整性閘門**：缺少 push/CI 前的 import smoke test 或 linter（如 pyflakes F811 redefinition），死碼可長期潛伏。

### 具體案例（說明用）

某 ticket 系統的 `file_lock.py` 內 `reap_stale_locks` / `_try_acquire_create_lock` / `create_id_allocation_lock` 三函式各定義兩次：一套基於 `filelock.FileLock`（後端遷移後的新版）、一套基於原生 `fcntl.flock`（舊版），回傳型別不同。直譯器取最後 def，故新版 FileLock 實作全為死碼，模組實跑舊 fcntl 版。一次不完整重構移除 `import fcntl` 後，舊版觸發 `NameError` 並透過 overlay-push 零審查傳染所有 consumer。

## 解決方案

### 事後處理

逐一收斂重複定義為單一一致實作（明確選定後端），刪除死碼，補回歸測試鎖定「同名定義唯一」。

### 預防措施

| 措施 | 說明 |
|------|------|
| **push/CI 前 import smoke test** | 同步前在 staging 樹 import 全模組 + 跑關鍵測試，import 殘留 / 載入即炸類缺陷就地攔下（見 [[PC-V1-009-mechanical-defect-misdiagnosed-as-process-defect]]） |
| **重複定義 linter** | 納入 pyflakes F811（redefinition of unused name）或等價檢查，重複 top-level 定義紅燈 |
| **語意層而非文字層合併意識** | 認知 overlay/文字 merge 無衝突 ≠ 語意正確；同檔大幅 append 後應人工或工具複查同名定義 |

## 防護建議

同步機制（overlay / subtree / 文字 merge）的設計與審查須假設「文字無衝突仍可能語意破壞」，並以自動完整性閘門（import smoke test + 重複定義 linter）兜底，而非依賴文字 merge 的無衝突作為正確性保證。

## 相關文件

- `.claude/error-patterns/process-compliance/PC-V1-009-mechanical-defect-misdiagnosed-as-process-defect.md` — 機械缺陷應以自動閘門消除而非人工流程攔截
- `.claude/scripts/sync-claude-push.py` — overlay push 同步腳本（import smoke test 落點）

---

**Last Updated**: 2026-06-16
**Version**: 1.0.0 — 初始建立，源於 parallel-evaluation 對框架治理策略的多視角審查（Evidence + linux 委員獨立確認重複定義）
