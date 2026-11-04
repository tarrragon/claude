---
id: PC-GPD-082
title: 在 .claude/skills/ 新建專案專用的 skill，沒有同時宣告不隨框架同步推送，下一次 sync-push 會把它帶進 canonical
category: process-compliance
severity: medium
status: active
created: 2026-11-04
related:
- PC-GPD-077
---

# PC-GPD-082：專案專用的 skill 放在共用目錄，沒有擋住推送

## 基本資訊

| 項目 | 內容 |
|------|------|
| Pattern ID | PC-GPD-082 |
| 分類 | process-compliance（框架資產與專案產物的分離） |
| 風險等級 | 中（推出去後，其他 consumer pull 下來會拿到寫死本專案環境的 skill） |
| 來源版本 | 0.6.0 |
| 首次觀測 | 2026-11-04 |
| 關聯 | [[PC-GPD-077]]（同屬 skill 變更的發佈前檢查） |

## 摘要

**`.claude/skills/` 底下的每個目錄，預設都會隨 sync-push 推到共用的框架 repo。** 為本專案寫的 skill（例如寫死本專案 App、平台服務或路徑的驗證配方）如果直接放進這個目錄，又沒有同時宣告排除，下一次 sync-push 就會把它推出去。建立 skill 的票只驗收 skill 本身能不能用，不會問「它該不該被推出去」。

## 症狀

- sync-push 預演的 skill 變更摘要中出現一個新 skill，它的內容寫死本專案的 App 名稱、設定鍵或平台服務。
- 專案沒有 skill 過濾設定，所以沒有任何機制會攔下它。
- 首例是主控準備推送前盤點變更時才發現，當時這個 skill 已經合併進 main。

## 根因

1. **目錄位置決定推送範圍。** skill 放在哪裡，就決定它會不會被同步；建立者選目錄時，想的是「skill 要放哪裡才能被載入」，不是「它會被推到哪裡」。
2. **建立 skill 的驗收不含推送範圍。** 驗收只看功能與發佈前檢查清單，沒有一條問這個 skill 是框架資產還是專案產物。
3. **推送前沒有逐項確認新 skill。** 預演會列出新 skill，但沒有要求逐項判斷。

## 防護

| 情境 | 做法 |
|------|------|
| 建立新 skill 的票 | 驗收列一條：判定它是框架資產還是專案專用；專案專用的，同批宣告不推送（skill 過濾設定或專案整合目錄） |
| sync-push 之前 | 預演列出的每個新 skill 逐項判定；專案專用而沒有排除的，先排除再推 |
| 判定標準 | 替換專案名稱、App 名稱與路徑之後，skill 還有沒有意義；沒有，就是專案專用 |

## 檢查問句

建立 skill 時問：其他 consumer pull 到這個 skill，用得上嗎？用不上，就同批把它排除在推送之外。

## 實例

- 2026-11-04，一個 Flutter 專案為了檔案監看的實機驗證，在 `.claude/skills/` 新建一個驗證配方 skill，內容寫死該 App 的設定鍵與 macOS 的 fseventsd。專案沒有 skill 過濾設定。主控在下一次 sync-push 預演前盤點時發現，用戶裁定先建票排除、再推送。
