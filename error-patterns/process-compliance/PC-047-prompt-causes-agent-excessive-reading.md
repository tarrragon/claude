---
id: PC-047
title: PM prompt 導致代理人大量讀取而非直接實作
severity: medium
category: process-compliance
first_seen: "2026-04-08"
occurrences: 3
status: active
---

# PC-047: PM prompt 導致代理人大量讀取而非直接實作

## 問題描述

PM 派發代理人實作新功能時，prompt 包含「參考 X 檔案」「先讀取 Y」「grep 確認 Z」等指引，導致代理人花光所有 tool call 在讀取上，從未進入寫入階段就回合耗盡。

## 發生場景

某 Ticket 新增 `ticket track snapshot` 子命令，連續 3 次派發都失敗：
- 第 1 次：「參考 track_board.py 的模式」→ 代理人讀 728 行 track_board.py
- 第 2 次：提供完整程式碼但「先 grep 確認 list_versions」→ 代理人 grep + 讀取
- 第 3 次：「讀取 track_board.py 前 50 行」→ 代理人再次讀取

## 根因

PM 的 prompt 把「探索」和「實作」混在一起。PM 應該自己完成探索，只給代理人「實作」指令。

## 正確做法

PM 在派發前完成所有分析，prompt 只包含：

| prompt 應包含 | prompt 不應包含 |
|-------------|---------------|
| 完整的新檔案程式碼 | 「參考 X 檔案」 |
| 確切的修改位置（行號 + old/new） | 「先讀取 Y」 |
| 所有必要的 API 資訊 | 「grep 確認 Z」 |
| 驗證命令 | 「了解模式後...」 |

**原則**：代理人收到 prompt 就能直接 Write/Edit，第一個 tool call 就是寫入，不是讀取。

## 防護措施

### PM 端（派發前防護）

1. **Prompt 自查**：「這個 prompt 中有沒有要求代理人讀取/探索？如果有，我應該自己先做完，把結論寫入 Context Bundle。」
2. **TDD 導向**：PM 提供測試路徑+API 簽名+常數+修改檔案清單，不提供實作程式碼。代理人依測試自行設計實作。
3. **禁止探索指令**：prompt 中不出現「參考 X」「先讀取 Y」「grep 確認 Z」。

### 代理人端（執行時防護）

1. **查詢範圍限制**：實作代理人只允許查詢測試碼、目標 model/DTO、domain 邏輯、介面定義四類。
2. **5 次讀取上限**：如果需要超過 5 次 Read/Grep 才能開始寫入，代表 Context Bundle 不完整，停止查詢並回報 PM。
3. **拒絕探索**：如果 prompt 要求「參考其他檔案」「先了解模式」等探索行為，代理人應拒絕並回報 PM 補充資訊。

### 規範更新（已完成）

| 文件 | 新增內容 |
|------|---------|
| `AGENT_PRELOAD.md` v1.5.0 | 規則 5：實作代理人查詢範圍限制 |
| `phase3b-prompt-template.md` v1.2.0 | 禁止行為新增 3 項 PC-047 防護 |
| `context-bundle-spec.md` v2.2.0 | 代理人中間進度更新規範 |
