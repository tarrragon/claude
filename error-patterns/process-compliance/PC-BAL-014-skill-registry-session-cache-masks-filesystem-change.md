---
id: PC-BAL-014
title: Skill 註冊表 session 快取遮蔽檔案系統變更 — 同 session 驗證得出假陰性
category: process-compliance
severity: medium
created: 2026-07-28
related:
 - PC-145
 - PC-166
 - 0.2.1-W3-123
---

# PC-BAL-014: Skill 註冊表 session 快取遮蔽檔案系統變更

## 基本資訊

- **分類**: 流程合規（process-compliance）
- **來源版本**: v0.2.1
- **發現日期**: 2026-07-28
- **風險等級**: 中

---

## 症狀

刪除或修改 `~/.claude/skills/<name>/` 或專案 `.claude/skills/<name>/` 後，於同一 session 呼叫該 skill 作驗證，Skill tool 回報的 `Base directory` 仍是變更前的路徑，且成功送出完整內容——即使該目錄經 `test -d` 確認已不存在。

輸出形態完全正常：沒有錯誤訊息、沒有降級提示、內容完整。採信它會得出「變更未生效」或「刪除失敗」的結論。

## 觸發情境

| 條件 | 說明 |
|------|------|
| 對 skill 目錄做檔案系統層變更（新增／刪除／改路徑） | 主要觸發點 |
| 在同一個 CC session 內以呼叫該 skill 作為驗證手段 | 讀到的是啟動時快取 |
| 變更涉及 personal（`~/.claude/skills/`）與 project 兩層的優先序 | fallback 行為同受快取影響 |

## 根因

Claude Code 於 session 啟動時載入 skill 註冊表，並快取路徑與內容。檔案系統的後續變更不會使該快取失效。

由此產生兩個平面：檔案系統是世界平面，skill 註冊表是 session 啟動瞬間的快照。同 session 內查詢後者，得到的是歷史狀態而非現況；兩者在變更後必然分歧，直到下個 session 才收斂。

這與 PC-145（stale CLI install）同屬「執行載體持有源碼快照」家族，但機制不同：PC-145 的快照由 `uv tool install` 產生、以 reinstall 使其失效；本模式的快照由 CC runtime 在 session 啟動時建立，**沒有 session 內的失效手段**。

## 解決方案

驗證 skill 檔案變更時，區分兩個問題並用對應手段：

| 問題 | 手段 |
|------|------|
| 變更是否已落盤 | `test -d` / `ls` 等檔案系統指令（二元固定值，無法被腦補，不受快取影響） |
| 變更是否已對 CC 生效 | 必須在新 session 執行，同 session 內無法回答 |

禁止以 Skill tool 的回報作為「檔案是否存在」的判準。

分辨真相的關鍵是 `tool-output-trust-rules` 規則 3 的固定值交叉驗證：Skill tool 的輸出在形態上與正常回報無異，只有二元回傳值能穿透。

## 反向推論：操作時點與損害時點分離

同一機制使跨專案的 skill 覆寫事故難以歸因。以 `rsync` 覆寫全域 skill 為例，對其他專案的損害並非在 rsync 當下開始，而是從**該專案的下一個 session** 才顯現。

受害端察覺行為異常時，那次操作已經是「上次」甚至「上上次」的事，時間線上不相鄰，歸因成本因此陡增。評估此類操作的影響面時，須以「所有 consumer 的下個 session」為損害起算點，不以操作當下為準。

## 預防措施

| 層級 | 措施 |
|------|------|
| 規則層 | `.claude/references/sync-mechanism-guide.md` §6.4 固化驗證時機要求 |
| 驗證設計 | 涉及 skill 檔案變更的 ticket，acceptance 應預先聲明「驗證須跨 session」，避免執行者誤判為疏漏 |
| 判準 | 任何「工具回報 vs 檔案系統」衝突，一律以檔案系統為準，再問工具端何時刷新 |

## 相關案例

`0.2.1-W3-123`（移除 personal 遮蔽副本）：移除當下 session 的 `/zellij` 探針回報 personal 路徑，`test -d` 回報 GONE，兩者矛盾。隔一個 session 同探針回報 project 路徑，構成對照組坐實快取假說，同時驗證 personal 缺席時 CC fallback 至 project 版。

該票的 acceptance 因此拆成兩個 session 執行，並將無法從本專案觸發的部分（另一個 consumer 專案的實地載入）切為獨立 ticket 綁定。
