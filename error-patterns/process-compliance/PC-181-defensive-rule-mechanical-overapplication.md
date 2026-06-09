> **編號溯源**：本 pattern 在上游框架 repo（tarrragon/claude.git）編號為 PC-177。因本專案 PC-177 已被既有 pattern 佔用，於本專案重新編號為 PC-181。下次 sync-pull 仍會帶回上游 PC-177，屆時應辨識為同一 pattern 並去重。

# PC-181: 防護規則機械套用反噬（對有界列舉截斷致資訊遺失）

## 摘要

為情境 A（巨量 / 串流輸出）設計的防護手段（`head` / `tail` 截斷），被無差別套到情境 B（有界列舉命令，如 `git remote -v` / `git branch -a` / `git status --porcelain`）時，防護手段本身變成新失效源——截斷砍掉的恰是決策關鍵行，造成資訊遺失與錯誤判斷。根因是「主動預防大輸出」規則只建模「防洪」（防巨量輸出淹沒 context），未涵蓋反向風險：對小型有界清單的截斷會隱藏每一行皆關鍵的決策資訊。修正方向：先判別輸出是否「可能巨量 / 串流」，是則截斷防洪，否（有界列舉，每行皆決策關鍵）則完整讀，要算筆數改用 `wc -l`。

## 症狀

- 對 `git remote -v` / `git branch -a` / `git status --porcelain` 等有界列舉命令加 `head` / `tail`，理由是「主動預防大輸出」
- 截斷後基於殘缺清單做判斷（推錯 remote、誤判工作區乾淨、誤判當前分支）
- 截斷上限選得比實際內容小（如 `head -2` 套在 4 行輸出上），且砍掉哪幾行與輸出順序耦合，不可預測
- 事後重跑完整命令才發現被截掉的行是決策關鍵（如隱藏的 `origin` remote）

## 根因（防護手段的適用情境錯配）

防護手段（截斷）對兩種輸出有相反效果，套用者未先判別輸出屬哪種：

| 輸出類型 | 截斷效果 | 是否該截斷 |
|---------|---------|----------|
| 情境 A：可能巨量 / 串流（test log、build log、大檔 `cat`、`find` 大樹、`grep` 大範圍） | 防洪——避免淹沒 context，保留尾段摘要即可判斷 | 是 |
| 情境 B：有界列舉（`git remote -v` / `git branch -a` / `git status --porcelain` / `git tag` / `ls`） | 反噬——砍掉決策關鍵行，每行都影響判斷 | 否 |

「主動預防大輸出」規則的心智模型只涵蓋情境 A（防洪），未對情境 B 設 carve-out。規則無例外條款時，面對 `git remote -v` 仍會機械套用截斷——這是 guidance 缺口（quality-baseline 規則 6：寫好的規則本應阻止此行為）為主、行為層機械套用為輔的混合根因（W8-032 ANA 判定約 70% guidance / 30% 行為）。

截斷對有界列舉的危害與內容順序耦合：`git remote -v` 字母序排列（`claude-shared` < `origin`），`head -2` 剛好砍掉排在後面的 `origin`，但套用者無法事先預測哪幾行會被砍。

## 案例：git remote -v | head -2 隱藏 origin 的 near-miss（2026-06-05）

PM 在 W8-026 Phase 1 派發後、push 前，執行 `git remote -v | head -2` 想確認推送目標。`git remote -v` 每 remote 輸出 fetch + push 兩行，本案 2 remote 共 4 行；`head -2` 僅保留字母序在前的 `claude-shared`（`.claude` 配置 repo），砍掉 `origin`（專案 repo）的 2 行，產生「唯一 remote 是配置 repo、推送會污染」的誤判。

重現實驗（W8-032 ANA 實證）：

```bash
git remote -v | wc -l            # → 4（有界，2 remote × fetch+push）
git remote -v | head -2          # → 只顯示 claude-shared（字母序在前）
git remote -v | grep -c origin   # → 2（origin 的 fetch+push 兩行全被 head -2 截掉）
```

雙重錯誤：
1. 對有界列舉命令（輸出 = 2 × remote 數，通常 2–12 行）套用截斷，本身無必要——它不是可能巨量的串流輸出。
2. 截斷上限（2）選得比實際內容（4 行）小，且該命令每一行都是決策關鍵（少一個 remote = 推錯目標）。

緩解因子：PM 當下隨即跑完整 `git remote -v` 自我修正，未真推錯，屬 near-miss（近失）而非實害。本 PC 固化規則，防止未察覺時的實害。

## 防護

| 步驟 | 動作 | 目的 |
|------|------|------|
| 1 | 加 `head` / `tail` 前，先判別輸出是否「可能巨量 / 串流」 | 區分情境 A（該截斷）與情境 B（禁截斷） |
| 2 | 屬有界列舉（每行皆決策關鍵）→ 完整讀，禁用 `head` / `tail` | 避免砍掉決策關鍵行 |
| 3 | 要確認筆數 → 改用 `wc -l`（不損失內容判斷） | 算數量無需犧牲完整內容 |
| 4 | 屬巨量 / 串流 → 用 `head` / `tail` 防洪（保留規則二大輸出防護） | 防巨量輸出淹沒 context |

**Why**：截斷防護是為情境 A（巨量輸出）設計，對情境 B（有界列舉）的每一行都是決策關鍵（少一個 remote = 推錯目標）。無差別套用會反向造成決策關鍵資訊遺失，且截斷砍掉哪幾行與輸出順序耦合，不可預測。

**Consequence**：對有界列舉誤用截斷會隱藏決策關鍵行，導致基於殘缺清單的錯誤判斷（推錯 remote、誤判工作區乾淨、誤判當前分支）。防護手段本身（截斷）成為新失效源，且因「自我修正前未察覺」可能釀成實害（本案因 PM 即時重跑完整命令而僅止於 near-miss）。

**Action**：加 `head` / `tail` 前先判別輸出類型——巨量 / 串流則截斷防洪；有界列舉（每行皆決策關鍵）則完整讀，算筆數改用 `wc -l`。對照清單見 `.claude/rules/core/bash-tool-usage-rules.md` 規則二「有界列舉命令禁截斷（carve-out）」。

## 識別訊號表

| 訊號 | 判讀 |
|------|------|
| 對 `git remote -v` / `git branch -a` / `git status --porcelain` 加 `head` / `tail` | 機械套用大輸出防護於有界列舉，禁截斷 |
| 截斷上限（`head -N`）選得比實際輸出行數小 | 砍掉決策關鍵行的高風險訊號 |
| 截斷後做出「推錯目標 / 工作區乾淨 / 當前分支」判斷 | 基於殘缺清單判斷，須重跑完整命令核對 |
| 想知道「有幾個 remote / 分支 / 變更檔」卻用 `head` | 算筆數應用 `wc -l`，非截斷 |

## 與其他規則 / PC 的關係

| 對象 | 關係 |
|------|------|
| `bash-tool-usage-rules.md` 規則二「主動預防大輸出」 | 本 PC 是規則二「有界列舉命令禁截斷（carve-out）」的觸發案例與根因；規則二提供正向 guidance，本 PC 描述反模式 |
| PC-076（session-start 全量清點） | 共振——對 `git status --porcelain` 誤用截斷會隱藏變更檔，使 session 清點失準，誤判工作區乾淨 |
| IMP-009（taskoutput 混淆） | 不同——IMP-009 是輸出機制混淆（背景任務 vs 暫存檔），本 PC 是對有界列舉截斷致資訊遺失 |
| PC-081（self-check 過嚴） | 不同主題——PC-081 是檢查過嚴，本 PC 是防護手段套錯情境 |
| quality-baseline.md 規則 6（失敗案例學習原則） | 同源——near-miss 暴露 guidance 缺口（規則無 carve-out），提煉教訓固化為規則而非回退 |

## 案例文件來源

W8-032 ANA（`git remote -v | head -2` 截斷隱藏 origin 的 near-miss，2026-06-05）。根因分類判定 guidance 缺口為主（~70%）+ 行為機械套用為輔（~30%），決定補強 `bash-tool-usage-rules.md` 規則二並 spawn W8-033 執行。重現實驗實證 `git remote -v` 共 4 行（有界）、`head -2` 隱藏 `origin` 2 行。
