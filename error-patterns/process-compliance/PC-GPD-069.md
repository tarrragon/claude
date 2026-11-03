---
id: PC-GPD-069
title: 研究腳本沿用廠商預設的 API key 變數名並寫入 shell profile，之後啟動的 Claude Code 偵測到同名變數而改用該 key 認證
category: process-compliance
severity: medium
status: active
created: 2026-11-01
related:
- PC-166
---

# PC-GPD-069：腳本與 agent harness 共用 API key 變數名

## 基本資訊

| 項目 | 內容 |
|------|------|
| Pattern ID | PC-GPD-069 |
| 分類 | process-compliance（實驗環境的憑證設定） |
| 風險等級 | 中 |
| 來源版本 | 0.5.0 |
| 首次觀測 | 2026-10-21 |
| 關聯 | PC-GPD-063（給用戶的憑證設定步驟覆蓋了 profile 已載入的值；同屬實驗憑證的提供方式）、[[PC-166]] 規則 5（以世界平面查證狀態） |

## 摘要

**自寫的腳本若用廠商 SDK 的預設變數名（如 `ANTHROPIC_API_KEY`）讀取 API key，而這個變數被全域匯出（寫進 shell profile），讀到它的不只腳本。** Claude Code 本身也讀同一個變數名：之後啟動的 session 會改用這把 key 認證，計費與額度改走 API 帳戶，而不是原本的登入方式。腳本與 agent harness 在同一台機器、同一個 shell 環境下執行，變數名就是兩者共用的命名空間。

## 症狀

- 設定變數後新開的 session 啟動時出現 `Both claude.ai and ANTHROPIC_API_KEY set` 類的警告；互動模式下會詢問是否改用該 key。
- session 隨後回報 `Credit balance too low`：key 已被接受，但 API 帳戶沒有額度，session 本身無法工作。
- 設定變數之前已開的 session 不受影響，問題只出現在之後啟動的 session，看起來像偶發。

實例（2026-10-21）：研究線的取樣腳本以 SDK 預設方式讀 key，用戶依約定把 key 寫進 `~/.zshrc`。重開研究線 session 時出現上述兩則訊息，session 改用該 key 認證後因額度不足無法運作。用戶把變數改名並重開 session；腳本改讀專屬變數名，並以 SDK 建構參數明確傳入 key。

## 根因

- **Why**：SDK 的預設變數名是為「單一程式讀單一 key」設計的。開發者沿用它，是因為 SDK 不需要額外參數就能讀到 key；但 agent harness 屬於同一家廠商的工具鏈，讀的是同一個名字。全域匯出讓變數對同一 shell 啟動的所有程序可見，腳本無法獨占它。
- **Consequence**：

| 層級 | 影響 |
|------|------|
| session 認證 | harness 改用實驗 key 認證，計費改走 API 帳戶；額度不足時 session 無法工作 |
| 費用歸屬 | 額度足夠時，agent 的日常用量會悄悄算在實驗 key 上，實驗費用與 session 用量混在一起 |
| 診斷 | 只有變數設定後啟動的 session 受影響，症狀與「何時開的終端機」相關，難以從錯誤訊息直接連到腳本的變數名 |

## 解決方案

- **Action**：

| 項目 | 做法 |
|------|------|
| 變數名 | 腳本改讀專屬變數名（如在預設名前加用途前綴），不與 harness 或其他工具的預設名相同 |
| 傳入方式 | 讀出後以 SDK 的建構參數明確傳入（如 `api_key=...`），不依賴 SDK 隱式讀預設變數；否則只改變數名時，SDK 仍會去讀預設名 |
| 防回歸測試 | 加一則正向對照：預設名存在、專屬名不存在時，腳本判定為缺 key 並結束 |
| 已受影響的 session | 從全域環境移除預設名的匯出，重開 session；互動詢問時選擇不使用該 key |

查證 key 是否存在時只做存在性檢查（`[ -n "$VAR" ]`），不讀取、不印出值。

## 預防措施

- 派發需要 API key 的實驗前，先確認腳本讀取的變數名不在 agent harness 會讀取的變數清單內（以 harness 的官方文件為準）。
- 實驗憑證的約定（變數名、放在哪裡、如何帶入）寫在協調票的固定段落，接手的 session 依該段落提供指令，不另起一套（見 PC-GPD-063）。
- 可評估只在執行實驗的那一條命令前帶入變數，而不寫進全域 profile，讓 harness 看不到它。

## 關聯 Ticket

- 本專案 2026-10-21 研究線取樣腳本改用專屬變數名的子票，與協調票〈研究線注意事項〉兩段紀錄
