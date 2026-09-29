---
id: TEST-GPD-001
title: 同 bundle id 的多份 .app 使系統依 bundle id 啟動錯的那一份，實機觀測被第二實例污染
severity: high
category: test
related:
 - PC-166
 - TEST-BAL-002
---

# TEST-GPD-001：同 bundle id 多份 .app 污染實機觀測

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 高 |
| 來源版本 | 0.3.1 |
| 發現時機 | macOS 桌面 App 的系統通知實機驗證，點擊通知後觀察導向結果 |
| 發現日期 | 2026-09-29 |

## 症狀

實機驗證中，一個由系統依 bundle id 喚起 App 的動作（點擊系統通知、開啟 URL scheme、Dock 或 Launchpad 啟動）產生的畫面結果，與程式碼邏輯推不出來的狀態一致——例如「點擊通知後畫面停在預設頁，而非通知應導向的頁面」。同時：

- 驗證者自己的除錯管道（DevTools、`flutter run` 的 VM Service）看不到該次互動之後的任何日誌。
- 接著在畫面上操作，結果像是「狀態被保留」或「沒有觸發預期的副作用」，與正在觀測的那個實例的日誌對不上。
- 事後才發現 Dock 上有兩個相同圖示。

**本案具體樣態**：通知送達後點擊，前景出現的 App 停在預設頁。被誤判為「點擊導向缺陷」，並一度建議列為發版阻擋項。實際上前景化的是**另一份 `.app` 新啟動的第二個實例**（新實例的預設頁就是那一頁）；正在觀測的實例始終留在隱藏狀態，而且那個實例根本不會自行前景化（這才是真缺陷）。

## 根因

**系統以 bundle id 定位 App，但同一 bundle id 可能登記了多份 `.app`**。macOS 的 LaunchServices 會登記每一個建置出來的 `.app`；每個 git worktree 的 `flutter build`／`xcodebuild` 都會產生一份新登記，刪除 worktree 後的失效路徑仍殘留在資料庫。當系統依 bundle id 喚起 App 時，選中的未必是正在執行、正在觀測的那一份——可能是最近建置的另一份，於是啟動第二個實例。

**觀測層面的失效**：驗證者只盯著自己啟動的那個行程（它的日誌、它的除錯連線），對「另一個行程接手了使用者看到的畫面」完全沒有訊號。畫面結果與日誌之間的落差，被解讀成程式邏輯缺陷，而不是觀測對象錯了。「單一實例」的前置檢查通常只在啟動當下做一次（`pgrep` 為 1），而第二實例是在互動**之後**才被系統啟動的，所以啟動時的檢查攔不住它。

**一般化**：凡是由作業系統依識別碼（bundle id、URL scheme、檔案類型關聯、Windows AppUserModelID、Linux `.desktop` 檔）代為啟動或喚起 App 的互動，在「同一識別碼有多份可執行檔」的開發環境下，都可能交給錯的那一份處理。並行開發（多個 worktree、多個 session 各自建置）會讓份數持續增加。

## 解決方案

1. **量測前確認登記只剩一份**（macOS）：
   ```bash
   LS=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
   $LS -dump | awk '/^path:/{sub(/^path: +/,""); sub(/ \(0x[0-9a-f]+\)$/,""); p=$0} /<bundle-id>/{print p}' | sort -u
   ```
   逐一檢查路徑是否仍存在；除了要量測的那一份，其餘現存的 `.app` 一律刪除（或移除所屬 worktree）。失效路徑不影響選擇，但可用 `lsregister -u <path>` 清掉。
2. **互動之後再查一次實例數**：每次由系統喚起 App 的操作之後，以 `NSRunningApplication.runningApplications(withBundleIdentifier:)` 或 `pgrep -f '<App>.app/Contents/MacOS'` 取實例數與各自的路徑；大於 1 時，該次觀測作廢。
3. **worktree 內建置後刪除產物**：派發給 worktree 代理人的任務若包含 `flutter build macos`，要求 build 驗收通過後 `rm -rf build/macos`，不讓 `.app` 留在磁碟上。
4. **以日誌而非畫面判定行為**：點擊路徑的每一步都記錄結果值（切頁目標、捲動後可見性、下一幀的焦點狀態），並用原生端日誌記錄前景化前後的 `isHidden`／`isActive`。畫面結果與日誌不一致時，先查觀測對象，不先改程式。

## 預防措施

- 實機驗證的前置檢查清單固定包含兩項：實例數為 1、同識別碼的現存可執行檔只有一份。兩項都在**互動之後**複查，不只在啟動時查一次。
- 並行開發環境（多 worktree、多 session）預設視為「同識別碼多份」的高風險環境；需要實機驗證時，先清理其他份，再建置、再量測。
- 非權限類的行為一律改以測試或日誌查詢機械驗證，把人工目視限縮在權限類平台事實（授權對話框、系統設定狀態），縮小觀測被污染的面積。

## 相關模式

- PC-166（記錄平面與世界平面）：驗證者自己的除錯管道是記錄平面，系統實際把畫面交給哪個行程是世界平面；兩者不一致時以後者為準。
- TEST-BAL-002（測試替身的建構路徑與正式環境分歧）：同樣是「觀測或測試的對象不是正式執行的那一個」，本模式發生在實機層。
