---
id: IMP-BAL-002
title: sync-claude-pull.py 未知參數不報錯，推進 base SHA 卻不套 delta，破壞三方合併基準
severity: high
category: implementation
related: [PC-V1-001]
created: 2026-07-25
---

# IMP-BAL-002: sync-claude-pull.py 未知參數不報錯，推進 base SHA 卻不套 delta，破壞三方合併基準

## 症狀

- 對 `sync-claude-pull.py` 傳入未知參數（如 `--help`）：腳本不報錯、輸出「成功拉取」，但「已套用 0 個 delta 變更」且同時「已記錄 base SHA: <遠端 HEAD>」
- 後續無參數重跑 pull：因 base SHA 已被推進到遠端 HEAD，三方合併只看到極小 delta 集，跨越多版本的更新被靜默跳過；本地與 base 的天然差異被誤判為「本地修改」，產生多個假衝突存入 `.sync-conflicts/`
- 最終狀態：`.claude/VERSION` 顯示最新版本，但部分框架檔（hook / skill）仍為舊版內容——半更新狀態，且 `.sync-conflicts/` 檔案本身含未解決的 `<<<<<<<` merge 標記

## 根因

腳本無 argparse 嚴格參數驗證，未知參數被靜默吞掉或誤解析（與 PC-V1-001「sync-push 未知參數被當 commit message」同家族根因：手寫 `sys.argv` 解析對未知輸入 fail-open）。

狀態寫入（`write_base_sha`）與 delta 套用未綁定為原子單元：異常路徑下 base SHA 照樣推進，違反「狀態標記必須反映實際完成的工作」——base SHA 是三方合併的信任錨點，錨點先行推進等於謊報同步進度。

## 解決方案

事後修復（consumer 端）：

1. 從 `.claude/.sync-state.json` 移除 `last_synced_base_sha` → 觸發全量 overlay fallback；或
2. 淺 clone 框架 repo 作 canonical，逐檔覆蓋假衝突檔（先以 git log 鑑識該檔是否有本地客製：最後修改全是 `chore(sync)` commit 即無客製，可整檔覆蓋；有客製則以 canonical 為底重疊本地 diff），清除 `.sync-conflicts/`，將 base SHA 校正為 canonical clone 的 HEAD

根本修復（框架端）：
1. sync 腳本統一改 argparse 並對未知參數 exit 非零（`0.2.1-W3-164` 已完成）。
2. base SHA 寫入移到 delta 套用成功之後，失敗路徑不推進（`0.2.1-W3-165` 已完成）。查證範圍收斂：套用過程硬失敗（例外）本就安全，未曾抵達寫入點；真正成立的缺口僅三方合併「軟失敗」——衝突檔 `conflicts` 清單是已產出但未消費的診斷資訊，衝突未解仍無條件寫入 base，即本 pattern 症狀的實際觸發路徑。修復後：有未解衝突時不推進 base SHA（對齊 git merge 語意），full overlay 路徑不受影響。

## 預防措施

- 對 sync 腳本永遠不傳猜測性參數；查用法先 Read 腳本 docstring，不用 `--help` 試探（此家族腳本無 argparse）
- pull 後驗證三固定值：`.claude/VERSION` 內容、關鍵新檔存在性（`ls`）、`git status` 變更數與預期 delta 規模相符——「成功拉取」訊息不可作為唯一判據（tool-output-trust 規則 3）
- 撰寫有狀態標記的同步工具時：狀態推進必須在工作實際完成之後，異常路徑禁止推進

## 關聯

- PC-V1-001：sync-push 未知參數被當 commit message（同家族：手寫參數解析 fail-open）
- 實證：monitor 專案 2.20.1→2.20.7 更新（2026-07-25），假衝突 5 檔 + 半更新狀態，依上述事後修復程序復原
