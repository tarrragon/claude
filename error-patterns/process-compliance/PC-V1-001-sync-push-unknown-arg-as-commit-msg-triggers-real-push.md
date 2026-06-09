---
id: PC-V1-001
title: sync-push 無 --help，未知參數當 commit 訊息觸發真實不可逆推送
category: process-compliance
severity: high
status: active
related:
  - PC-005
  - PC-105
---

# PC-V1-001: sync-push 無 --help，未知參數當 commit 訊息觸發真實不可逆推送

## 摘要

想對高槓桿不可逆腳本（`sync-claude-push.py`）做 dry-run / preview 而執行 `--help`，但該腳本不支援 `--help`、未用 argparse，把第一個 positional arg 一律當作 commit 訊息——結果觸發了真實的跨專案推送（v1.44.4，commit 訊息字面為 `--help`）。根因是「`--help` 是通用安全查詢」的假設，套用到一個未驗證 arg 解析方式的破壞性腳本上。修正方向：探測不熟悉的 CLI 介面前，先讀 SKILL.md / grep 原始碼確認 arg 解析；對 sync/push/deploy 等不可逆腳本，禁止用未驗證旗標探測。

## 症狀

- 為「先看會推什麼」而跑 `python3 .claude/scripts/sync-claude-push.py --help`
- 輸出未顯示 usage，而是 `使用用戶指定的 commit 訊息: --help` 接著一路 `成功推送`
- 遠端共享 repo 出現 commit 訊息為 `--help` 的版本
- 凡是「以為在查詢、實際在執行」的破壞性操作皆屬此症狀

## 根因

1. `sync-claude-push.py` 以 `sys.argv[1]` 作 commit 訊息，無 argparse、無 `--help` 攔截，未知旗標不報錯而被當資料吞入。
2. PM 將「`--help` 在多數 CLI 是安全且不執行主邏輯」的慣例，無驗證地外推到此腳本。
3. 對象是高槓桿不可逆操作（跨 5 專案共享 repo 推送），探測成本與真實執行成本相同——探測本身即是執行。

## 防護

| 場景 | 反模式 | 正確做法 |
|------|-------|---------|
| 想預覽不可逆腳本行為 | 直接跑 `script --help` 假設安全 | 先 `grep -n "argparse\|sys.argv\|--help" script` 確認 arg 解析方式 |
| 不確定 CLI 是否支援 dry-run | 用 `--help` / `--dry-run` 試探 | 先讀對應 SKILL.md / README 確認支援的旗標清單 |
| sync / push / deploy / clean 類操作 | 用未驗證旗標探測介面 | 視「任何呼叫」為真實執行；介面不明時先讀碼，不試探 |

**Why**：對不可逆腳本，「探測」與「執行」無安全邊界——未被 argparse 攔截的旗標會降級為資料或被忽略，主邏輯照跑。

**Consequence**：一次「無害查詢」即造成跨專案共享 repo 的真實狀態變更（本例 commit 訊息污染 + 版本 bump），且已 push 至遠端無法乾淨撤回，只能再推一次補正訊息。

**Action**：呼叫任何不熟悉的破壞性 CLI 前，先 `grep argparse/sys.argv` 或讀 SKILL.md 確認 (a) 是否支援 `--help` 且 `--help` 不執行主邏輯、(b) 是否有真正的 `--dry-run`。兩者皆不確定時，禁止試探，改為靜態讀碼理解行為。

## 與既有 pattern 關係

- **PC-005**（cli-failure-assumption-attribution）：本 pattern 是其變體——PC-005 處理「CLI 失敗後的歸因」，本 pattern 處理「CLI 未失敗、靜默成功但效果非預期」，兩者共通根因為「對 CLI 行為的未驗證假設」。
- **PC-105**（pm-cli-syntax-autopilot）：同屬 PM 對 CLI 的自動駕駛慣性；PC-105 是語法層，本 pattern 是「safe-probe 假設」層。

## 觸發案例

2026-06-09（1.0.0-W1-019.5 → sync-push 收尾）：PM 為 preview sync-push 內容而跑 `--help`，觸發 v1.44.4 真實推送（commit 訊息 `--help`），隨後以正確訊息重推 v1.44.5 補正。內容正確、僅訊息瑕疵，屬 near-miss（quality-baseline 規則 6：流程瑕疵不回退，提煉教訓固化）。
