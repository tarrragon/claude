---
id: IMP-065
title: CLI 單檔查詢依賴檔名約定，批量掃描用 field 比對，導致 naming-drift 時靜默失敗
category: implementation
severity: medium
related_tickets:
  - 0.18.0-W15-013
created: 2026-04-18
---

# IMP-065: CLI 單檔查詢檔名約定 vs 批量欄位比對不一致

## 症狀

- `xxx --list` 列表命令正常列出資源
- `xxx <id>` 單檔查詢報「找不到」
- 相同資源（ID 一致）卻出現兩種結果

## 根因

單檔查詢路徑（`f"{id}.json"` 之類）只比對檔名，批量掃描路徑（`glob + 讀取 ID 欄位`）忽略檔名只看內容。當歷史檔案用舊命名格式寫入（例：`v{id}-handoff.json`），兩條路徑出現分歧：

- 批量路徑：找得到（靠欄位）
- 單檔路徑：找不到（靠檔名）

這屬於「API 層命名約定與儲存層實際命名演進不同步」。寫入端改過格式後，讀取端單檔路徑沒更新、批量路徑因 glob 自然吸收而看不出問題。

## 影響範圍

- 任何兼具 list + query-by-id 的 CLI
- 儲存層歷經命名格式變更的系統
- 依賴檔名約定的單檔查詢實作

## 解決方案

查詢層統一為「讀取 ID 欄位」權威來源，檔名只作為 fast-path 優化：

1. **Fast-path**：直接檔名比對（命中即返回）
2. **Fallback-1**：業務反查（如 direction 指向目標）
3. **Fallback-2**：掃描所有檔案讀取 ID 欄位比對（兼容 legacy 命名）

範例：`.claude/skills/ticket/ticket_system/commands/resume.py:_find_handoff_file` W15-013 修復。

## 預防措施

- 新增「list vs query 行為一致性」測試：list 列出的 ID 必須能被 query 找到
- 命名格式變更時，讀取層同步提供 legacy fallback
- 寫入端與讀取端的檔名模式應集中管理（常數或 helper）

## 相關經驗

- 批量掃描成功可能隱藏單檔路徑 bug（靜默失敗）
- handoff.py 寫入 `{id}.json`，但 archive 存在 `v{id}-handoff.json` 等 legacy 格式，暗示早期曾用不同約定
