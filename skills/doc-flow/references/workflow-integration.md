# 工作流程整合指南

本文件說明如何在開發流程中整合五重文件系統的各項指令。

---

## 開始新版本

```
1. /doc-flow worklog init v0.26.0
   - 建立版本企劃
   - 定義目標和策略

2. /ticket create
   - 建立具體任務 tickets
   - worklog 自動索引 tickets

3. 執行開發
   - 更新 ticket 進度
   - 查詢/新增 error-patterns
```

---

## 執行任務前

```
1. /doc-flow check
   - 確認文件同步狀態

2. /error-pattern query <關鍵字>
   - 查詢既有經驗

3. /ticket track claim <ticket-id>
   - 開始執行任務
```

---

## 完成版本

```
1. /doc-flow worklog update
   - 更新版本狀態為完成

2. /doc-flow changelog preview
   - 預覽 CHANGELOG 更新

3. /version-release
   - 發布版本
   - 自動更新 CHANGELOG
```

---

## 與現有 SKILL 整合

| 現有 SKILL           | 整合方式                        |
| -------------------- | ------------------------------- |
| `/ticket create`     | worklog 自動索引新建的 tickets  |
| `/ticket track`      | 追蹤 ticket 狀態同步到 worklog  |
| `/tech-debt-capture` | 捕獲的 TD 同步到 todolist.yaml  |
| `/version-release`   | 發布時更新 CHANGELOG 和 worklog |
| `/error-pattern`     | 經驗學習系統整合                |

---

## 相關文件

上節整合表列的各項指令由對應 skill 提供，皆為選配——doc-flow 的五重文件系統本身可獨立運作，未安裝時失去的是自動同步，不是文件系統本身：

- 若專案已採用 `ticket` skill：worklog 自動索引新建的 ticket、並追蹤其狀態同步回 worklog，詳見 ticket skill 的說明（若已安裝）。若未採用，worklog 仍可建立與維護，但 ticket 區段需人工填寫與更新
- 若專案已採用 `error-pattern` skill：經驗學習系統與文件流程整合，詳見 error-pattern skill 的說明（若已安裝）。若未採用，失敗案例仍可記錄於 worklog，只是不會累積為可跨版本查詢的模式庫
- 若專案已採用 `version-release` skill：發布時自動更新 CHANGELOG 與 worklog 狀態，詳見 version-release skill 的說明（若已安裝）。若未採用，CHANGELOG 與 worklog 收尾需人工執行，本文件「開始新版本」章節的流程不受影響
