---
id: PC-GPD-085
title: 框架功能的本體隨 sync 擴散，啟用設定卻寫在 sync 排除檔，consumer 拿到功能卻從未啟用
category: process-compliance
severity: medium
status: active
created: 2026-11-05
related:
- PC-GPD-082
---

# PC-GPD-085：功能隨 sync 擴散，啟用開關沒有跟著擴散

## 基本資訊

| 項目 | 內容 |
|------|------|
| Pattern ID | PC-GPD-085 |
| 分類 | process-compliance（框架資產的發佈範圍） |
| 風險等級 | 中（不會出錯，但功能在 consumer 端等於不存在，而且沒有任何訊號） |
| 來源版本 | 0.6.0 |
| 首次觀測 | 2026-11-05 |
| 關聯 | [[PC-GPD-082]]（PC-GPD-082 是不該推的被推出去；本則是該推的推出去了，但啟用設定沒有推出去） |

## 摘要

**框架功能若由設定檔啟用，啟用設定必須放在 sync 範圍內的檔案。** 功能本體（腳本、skill）隨 sync-push 擴散到所有 consumer，但啟用設定若寫在 `settings.local.json` 這類 sync 排除檔，就只有原開發專案會啟用。consumer 端檔案都在，功能卻從未生效；在用戶比較兩個專案之前，沒有任何訊號。

## 症狀

- 同一個功能在開發專案可用，在其他 consumer 看不到，但 consumer 的 `.claude/` 裡確實有該腳本。
- 啟用方式只寫在 reference 文件，寫法是「在 `settings.local.json` 設定」。
- 本機掃描所有專案，只有開發專案有該設定。

## 根因

1. **開發時選的是「只影響本專案」的設定檔。** 試用期間這樣做是對的，因為可以避免影響其他專案；但功能定案之後，沒有人把設定搬到 sync 範圍內的檔案。
2. **sync 預演只列出檔案變更。** 預演會列出新腳本，但不會問「這個腳本在 consumer 端由誰啟用」。
3. **啟用失敗沒有訊號。** 功能沒有啟用時不會報錯，只是不出現。

## 防護

| 情境 | 做法 |
|------|------|
| 新增需要設定才會生效的框架功能 | 驗收列一條：說明 consumer 端靠什麼啟用；預設啟用的功能，啟用設定放在 `settings.json` 等 sync 範圍內的檔案 |
| 功能刻意只讓 consumer 自選啟用 | 文件寫明這是自選，並在 sync-pull 後的提示中列出 |
| sync-push 之前 | 預演中新增的可執行腳本，逐一確認在 consumer 端的啟用路徑 |

## 檢查問句

新增框架功能時問：consumer 執行 sync-pull 之後，這個功能會自己生效嗎？不會的話，是刻意的嗎？

## 實例

- 2026-11-05，一個 Flutter 專案的多線協調狀態列腳本已隨 sync 到其他專案，但啟用設定只寫在開發專案的 `settings.local.json`。用戶發現另一個專案的狀態列沒有顯示 session 名稱，主控查證後確認原因，並建票把設定移到 `settings.json`。
