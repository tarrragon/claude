---
id: ARCH-APP-002
title: uv tool install 全域同名 CLI 跨 consumer 專案 namespace 碰撞（last-write-wins）
type: architecture
severity: medium
status: active
source: 0.37.0-W7-001 ANA（saffron）
canonical_issue: tarrragon/claude#12
related:
  - get_project_root_dual_impl_type_divergence
  - cognitive-load
---

# ARCH-APP-002: uv tool install 全域 namespace 跨 consumer 碰撞

## 摘要

跨多個 consumer 專案共用同一份框架 skill（`ticket` / `doc` / `worktree`）時，以
`uv tool install <path>` 安裝為全域 CLI 會產生跨專案 namespace 碰撞。`uv tool
install` 以 package name 為全域唯一 key（`~/.local/bin/<name>` 與
`~/.local/share/uv/tools/<package>/` 各只有一個 slot），7 個 consumer 各有 package
name 相同（`ticket-system` 等）的 skill 副本，安裝任一專案即覆蓋全域 bin，最後
reinstall 者勝（last-write-wins）。本案實證：`doc` / `worktree` 的 receipt
`directory` 曾指向 `Projects/monitor`，在 `book_overview_app` session 內 reinstall
後才改回本專案。

## 症狀

| 症狀 | 觀察點 |
|------|--------|
| 全域 CLI 的 receipt `directory` 指向他專案絕對路徑 | `~/.local/share/uv/tools/<pkg>/uv-receipt.toml` |
| SessionStart 反覆提示 CLI OUTDATED 需 reinstall | uv-tool-staleness-check-hook |
| mid-session 自動 reinstall 搶回 ownership | uv-tool-ownership-guard-hook |
| 跨專案併發 session 互相 clobber 全域 bin | 兩 session 交替後 CLI 行為跳動 |

## 根因

兩個獨立面向：

1. **全域 namespace 同名碰撞**：`uv tool install` 以 package name 為全域唯一 key，無
   per-project 區分。多 consumer 共用同名 package → 共用唯一 slot。
2. **receipt 綁定絕對路徑、非 cwd-relative**：copy install（非 editable），源碼變更需
   `--force --reinstall`，receipt 寫死單一專案絕對路徑。

**重要緩和事實**：runtime 路徑解析（`get_project_root`）用 `git rev-parse
--show-toplevel` 依 cwd 決定操作哪個專案，故實際危害是**源碼版本不一致**（執行到他
專案的 skill 版本，可能缺本專案已修的 bug / 新功能），**非**跨專案資料污染。既有兩個
guard hook（staleness-check + ownership-guard）皆為症狀緩解，未解根因。

## 防護

1. **根治方案**：改用 `uv run --directory <project>/.claude/skills/<skill> <cmd>` 取代
   全域 install（路徑用 `git rev-parse --show-toplevel` 動態構造），每專案用自己源碼、
   無全域 slot；可移除兩個 guard hook。已實測可行（見 source ticket）。
2. **暫時緩解**：session 啟動時依 staleness/ownership hook reinstall 搶回本專案
   ownership（現狀）。
3. **跨 repo 性質**：修復須在上游 `tarrragon/claude` 統一變更後 sync-pull 至各
   consumer，單 consumer 修改會被 sync-pull 回歸。

## 來源

0.37.0-W7-001 ANA（saffron，4 方案評估，建議方案 1）→ 升級為 framework issue
tarrragon/claude#12（含 fix-matrix 跨 consumer 修復追蹤）。
