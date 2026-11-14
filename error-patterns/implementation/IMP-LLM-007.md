---
id: IMP-LLM-007
title: 以目標檔案的上層目錄作為 git 子行程的 cwd，寫入新目錄時查詢失敗；fixture 預先建好目錄使測試抓不到
status: active
severity: 中
---

# IMP-LLM-007: 目標檔案上層目錄當子行程 cwd → 寫入尚未建立的目錄時判定失敗

## 基本資訊

- **Pattern ID**: IMP-LLM-007
- **分類**: 實作 bug（implementation）
- **來源版本**: 3.3.0
- **發現日期**: 2026-11-13
- **風險等級**: 中
- **影響範圍**: 任何對「即將被寫入的檔案路徑」做判定、且以 `dirname(file_path)` 作為 git（或其他）子行程 cwd 的 hook／守衛／工具

---

## 問題描述

### 症狀

守衛對「既有目錄下的檔案」判定正確，對「寫到尚未建立的目錄」判定錯誤（誤擋或誤放），沒有錯誤訊息：子行程以不存在的 cwd 啟動失敗，查詢函式回傳 None，呼叫端把 None 當成「條件不成立」。

實例：主線程編輯守衛的開發分支放行改為「限 linked worktree」時，第一版以 `get_current_branch(cwd=dirname(file_path))` 查分支。在 worktree 內以 Write 建立一個位於尚不存在目錄下的新檔，git 子行程啟動失敗 → 分支為 None → 不放行 → 被 path_permission 擋下。同一函式內，判定「所屬 checkout 根」的 `owning_checkout_root` 已自行向上找第一個存在的祖先，所以 worktree 判定正確，只有分支查詢錯。

### 根因

Edit/Write 的目標路徑是「將要存在」的路徑，不是「已存在」的路徑。Write 可以建立新目錄下的新檔；把目標路徑的上層目錄當成必然存在的工作目錄，等於假設寫入只發生在既有目錄。

### 為什麼測試抓不到

測試 fixture 為了讓 git repo 有內容，通常會先建立目錄與檔案再 commit。被測路徑全落在已存在的目錄下，`dirname(file_path)` 永遠可用；「目錄不存在」這條路徑在 fixture 裡從未出現。本例由實地觸發（以 stdin 餵 payload 給 hook，目標路徑指向 worktree 內不存在的目錄）才發現。

## 解決方案

- 子行程的 cwd 改用已解析出的、確定存在的根目錄（checkout 根），不用目標檔案的上層目錄。
- 或沿用「向上找第一個存在的祖先」的處理（如 `checkout_identity.owning_checkout_root` 的第一段迴圈），再以該祖先為 cwd。

## 預防措施

- 寫守衛時，把「目標路徑的上層目錄不存在」列為產生路徑盤點表的一列（Write 建新目錄是常態操作）。
- 測試至少含一個目標落在尚未建立目錄的案例，且分別在放行側與阻擋側各一案（E2 正向對照）。
- 實地觸發時，刻意選一個不存在的目錄作為目標，而非沿用 fixture 的既有路徑。

## 相關模式

- PC-165（測試綠燈不等於 runtime 正確）：本例 fixture 結構遮蔽 runtime 路徑，屬該家族的「fixture 前提」變體。
- IMP-LLM-006：同屬「檢查器的測試只餵了一種形態的輸入」，該例是模板原樣，本例是既有目錄。
