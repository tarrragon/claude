# .claude 配置同步機制使用指引

本文件說明 `.claude/` 框架配置與中央獨立 repo 之間的雙向同步機制，涵蓋 pull/push 使用時機、base SHA 與三方合併的關係、full overlay fallback 風險與處理、以及 preserve 清單維護時機。

> **核心理念**：同步是「雙向有狀態」操作而非「單向覆蓋」。理解 base SHA 與三方合併的關係，才能在本地演化與上游更新之間安全收斂，避免靜默覆蓋、孤兒複製與誤刪。
>
> **適用對象**：任何需要 pull/push `.claude/` 框架配置的角色（PM 與代理人）。本指引為框架共用資產，內容不綁定特定專案類型。

---

## 1. 同步系統概觀

| 項目 | 說明 |
|------|------|
| 中央 repo | `https://github.com/tarrragon/claude.git`（所有採用此框架的專案共享的單一上游） |
| 同步範圍 | 本專案 `.claude/` 目錄全部檔案（hook、agent、規則、方法論、skill、project-templates） |
| 不覆蓋 | 倉庫根目錄 `CLAUDE.md`（保留各專案特定配置） |
| pull 指令 | `/sync-pull`（從中央 repo 拉取最新配置到本專案） |
| push 指令 | `/sync-push`（將本專案 `.claude/` 演化推送回中央 repo） |
| 狀態檔 | `.claude/.sync-state.json`（記錄上次 push hash、版本、time，與 `last_synced_base_sha`） |
| preserve 清單 | `.claude/sync-preserve.yaml`（本地特化檔案，pull 時原地保留不被覆蓋或刪除） |

**Why（為何是雙向有狀態）**：中央 repo 是多專案共享的框架來源。各專案會在本地演化框架（新增 hook、修訂規則），同時中央 repo 也會被其他專案推送更新。雙向同步必須以「上次同步點」（base SHA）為基準做三方合併，才能區分「本地新增」與「上游新增」。

**Consequence（不理解的代價）**：把同步當成單向覆蓋會在兩個方向都出錯——pull 時用上游舊版蓋掉本地演化，push 時用本地版蓋掉上游其他專案的貢獻。

**Action**：執行任何 pull/push 前，先確認 `.sync-state.json` 的 `last_synced_base_sha` 狀態（見 §3），再依 §2 判斷該 pull 還是 push。

---

## 2. pull vs push 使用時機

**核心原則：本地演化超前於中央 repo 時應 push，不應 pull。**

| 情境 | 該執行 | 理由 |
|------|--------|------|
| 新 clone 專案、本地 `.claude/` 為空或過舊 | `/sync-pull` | 取得中央 repo 最新框架基線 |
| 中央 repo 有其他專案推送的更新，本地未改框架 | `/sync-pull` | 拉取上游新增，本地無演化可覆蓋 |
| 本地剛修訂規則 / 新增 hook / 重組 skill（演化超前） | `/sync-push` | 將本地演化貢獻回中央，避免下次 pull 被舊版回灌 |
| 同時有本地演化 + 上游更新 | 先 `/sync-push` 再 `/sync-pull` | 先讓本地貢獻入庫成為新 base，再以三方合併收斂上游 |

**Why（演化超前該 push）**：若本地框架已超前但執行 pull，中央 repo 的舊版會被當成「上游狀態」帶入；在 full overlay fallback 下（見 §4）甚至直接覆蓋本地演化，使剛完成的框架改善消失。

**Consequence**：把「演化超前」誤判為「需要更新」而 pull，會讓本地辛苦累積的框架改善被上游舊版靜默回灌，且難以察覺（diff 反向，像是「退版」）。

**Action**：判斷方向前先問「我這次改過 `.claude/` 嗎？」改過 → 預設 push；沒改過且想取得他人更新 → pull。不確定時用 `git log --oneline` 對照本地 `.claude/` 最近 commit 與 `.sync-state.json` 的 `last_push_time`。

---

## 3. base SHA 與三方合併 vs full overlay

`.sync-state.json` 的 `last_synced_base_sha` 是同步機制的關鍵狀態，決定 pull 走「安全的三方合併」還是「危險的 full overlay fallback」。

### 3.1 兩條路徑的判定

| `last_synced_base_sha` 狀態 | pull 走的路徑 | 安全性 |
|---------------------------|--------------|--------|
| 存在且該 commit 在上游 clone 可達 | 三方合併（base / local / remote 逐檔 merge） | 安全：保留本地與上游各自的新增 |
| 缺失（`None`）或不可達 | full overlay fallback（全量覆蓋 + stale 清理） | 危險：本地修改可能被靜默覆蓋（見 §4） |

判定邏輯（`sync-claude-pull.py` 的 `should_use_full_overlay`）：base SHA 為 `None` 或不可達時回傳 `True`，退化為全量 overlay。

### 3.2 base SHA 如何初始化

| 情境 | base SHA 狀態 | 說明 |
|------|-------------|------|
| 從未成功 pull 過（只 push 過） | 可能缺失 | 只有 push 記錄（`last_push_hash`）不會寫入 `last_synced_base_sha`；首次 pull 仍會退化 full overlay |
| 成功完成一次 pull | 寫入 | pull 成功後將本次同步點寫入 `last_synced_base_sha`，下次 pull 即可三方合併 |
| 上游 force-push 使原 base commit 不可達 | 變為不可達 | base SHA 雖在但 clone 取不到該 commit，退化 full overlay |

**Why（為何首次 pull 必退化）**：三方合併需要「上次同步點」作為共同祖先。本地只有 push 記錄而無 pull 記錄時，沒有可用的共同祖先，機制只能退化為全量 overlay。

**Consequence**：誤以為「機制有三方合併就一定安全」，在 base SHA 缺失時執行 pull，三方合併形同未啟用，full overlay 的三類風險（§4）全數暴露。

**Action**：pull 前先檢視 `.sync-state.json` 是否含 `last_synced_base_sha`。缺失時，預期本次走 full overlay，務必先完成 §4 的前置確認（git status 乾淨 + 覆蓋預覽）再執行。

---

## 4. full overlay fallback 風險與處理

當 base SHA 缺失或不可達，pull 退化為 full overlay fallback。此路徑有三類風險，執行前必須知情。

### 4.1 三類風險

| 風險 | 成因 | 後果 |
|------|------|------|
| 本地修改靜默覆蓋 | 全量 `copy` 上游檔案到本地，無逐檔 merge | 本地未 push 的演化被上游版本蓋掉 |
| 孤兒複製 | 上游殘留「本地已遷移走的舊位置檔案」被複製進來 | 同一邏輯檔案在新舊兩處並存（例：扁平層與 skill 自包含層同名） |
| stale 誤刪 | stale 清理掃描「本地有 + 上游無 + 不在 preserve」的檔案 | 本專案特有防護若未登錄 preserve，可能被刪除 |

### 4.2 既有防護（已內建於機制）

| 防護 | 行為 |
|------|------|
| stale 清理 git 追蹤感知 | 本地獨有且受 git 追蹤的檔案**不靜默刪除**，改移至 `.sync-conflicts/`（需手動取回） |
| full overlay 覆蓋預覽 | full overlay 路徑提供 will-overwrite / will-delete 清單供確認 |
| pull 前覆蓋確認 | `/sync-pull` 流程強制以 AskUserQuestion 顯示即將覆蓋內容，知情同意後才執行 |

### 4.3 安全處理流程

1. **pull 前**：確認 `git status` 工作區乾淨（本地未提交變更先 commit 或 stash），避免覆蓋遺失。
2. **pull 前**：檢視 `.sync-state.json` 的 `last_synced_base_sha`；缺失即預期 full overlay，提高警覺。
3. **執行時**：詳閱覆蓋預覽（will-overwrite / will-delete）與 AskUserQuestion 清單，逐項確認非預期覆蓋。
4. **pull 後**：執行 `git diff` 比對本次同步引入的變更；特別檢查是否有孤兒複製（新舊位置同名檔案並存）與非預期刪除。
5. **發現本地演化被覆蓋**：改用 `/sync-push` 將本地版本推回中央，使本地成為新 base，而非反覆 pull。

**Why（為何 pull 後必比對）**：full overlay 的覆蓋與刪除即使有預覽，仍可能在大量檔案中夾帶非預期變更；`git diff` 是最後一道人工防線。

**Consequence**：略過 pull 後比對，孤兒複製與靜默覆蓋會進入工作區並可能被一起 commit，污染後續 diff 責任歸屬，回溯成本高。

**Action**：將「pull 後 `git diff` 比對」固化為流程步驟，發現異常立即處理（孤兒清理 / 從 `.sync-conflicts/` 取回 / 改 push）。

---

## 5. sync-preserve.yaml 維護時機

`.claude/sync-preserve.yaml` 的 `preserve` 清單列出「本地特化檔案」，pull 時原地保留不被覆蓋或刪除。

### 5.1 何時登錄

| 觸發時機 | 動作 |
|---------|------|
| 新增本專案特有防護（hook / error-pattern / 其 test） | 同步在 `preserve` 登錄該檔相對 `.claude/` 的路徑 |
| 新增本地特化的 runtime state 或 local-only 設定 | 登錄以免 full overlay 時被 stale 清理移除 |
| 移除某項本地特化 | 同步從 `preserve` 移除該項，保持清單與現實一致 |

### 5.2 哪些該登錄

| 類別 | 是否登錄 | 範例性質 |
|------|---------|---------|
| 本專案獨有、中央 repo 沒有的防護檔 | 登錄 | 專案特有 hook 及其 test、專案特有 error-pattern |
| 中央 repo 共有的框架檔 | 不登錄 | 共用 hook、共用規則（由同步機制正常管理） |
| 本地 runtime state / local-only 設定 | 登錄 | 不應被上游覆蓋的本地狀態檔 |

**Why（為何需手動登錄）**：stale 清理無法自動判斷「本地獨有檔案」是「該保留的特化」還是「該清掉的殘留」。preserve 清單是人工提供的「保留意圖」。

**Consequence**：本專案持續新增特有防護卻忘記登錄 preserve，在 full overlay 的 stale 清理時這些防護會被移至 `.sync-conflicts/` 甚至刪除（git 追蹤感知防護是安全網，但 preserve 原地保留才是正解）。

**Action**：將「新增本專案特有防護時同步登錄 preserve」綁定為提交前檢查項。git 追蹤感知（§4.2）是兜底，不可取代主動登錄——依賴兜底會讓特化檔反覆進 `.sync-conflicts/` 需手動取回。

---

## 檢查清單

執行 sync 前後對照：

- [ ] 方向判斷：本次改過 `.claude/` 嗎？改過預設 push，沒改且要更新才 pull（§2）
- [ ] pull 前：`git status` 工作區乾淨，未提交變更已 commit / stash（§4.3）
- [ ] pull 前：已檢視 `.sync-state.json` 的 `last_synced_base_sha`，缺失即預期 full overlay（§3.2）
- [ ] pull 執行時：已詳閱覆蓋預覽與 AskUserQuestion 確認清單（§4.2）
- [ ] pull 後：已 `git diff` 比對，確認無孤兒複製與非預期刪除（§4.3）
- [ ] 新增本專案特有防護時，已同步登錄 `sync-preserve.yaml`（§5）

---

## 相關文件

- `.claude/scripts/sync-claude-pull.py` — pull 實作（三方合併、full overlay fallback、stale 清理）
- `.claude/scripts/sync-claude-push.py` — push 實作（結構感知遞迴覆蓋 hook 目錄）
- `.claude/sync-preserve.yaml` — preserve 清單
- `.claude/commands/sync-pull.md` / `.claude/commands/sync-push.md` — 指令入口
- `.claude/references/framework-asset-separation.md` — 框架資產 vs 專案產物分離原則（含 hook 雙層架構歸屬規則）

---

**Last Updated**: 2026-06-07
**Version**: 1.0.0 — 初版：pull/push 時機、base SHA 與三方合併、full overlay fallback 風險與處理、preserve 維護時機
