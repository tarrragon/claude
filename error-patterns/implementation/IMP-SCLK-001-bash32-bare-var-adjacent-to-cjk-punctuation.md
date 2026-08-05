---
id: IMP-SCLK-001
title: macOS bash 3.2 在 UTF-8 locale 下將裸 $VAR 後緊鄰的全形標點併入變數名，set -u 時崩在只有錯誤路徑才走到的分支
category: implementation
severity: medium
created: 2026-08-01
source_ticket: 1.4.0-W2-033
---

# IMP-SCLK-001: bash 3.2 裸 `$VAR` 緊鄰全形標點在 `set -u` 下崩潰

## 症狀

shell 腳本平常執行正常，但在某條**錯誤處理分支**被觸發時，以 `<VARNAME>?: unbound variable` 之類的訊息中止。訊息指向的變數明明已在上方指派過值。

名稱尾端那個字元是被併入的高位元組，終端機多半渲染為 `?` 或亂碼；實際位元組值視標點所在的 Unicode 區塊而定（見根因表下方對照）。以 `od -c` 檢視 stderr 可看到真實位元組。

```bash
set -u
CODE=7
echo "失敗（exit $CODE）"
# → line 3: CODE?: unbound variable
```

## 根因

四個條件同時成立才觸發，缺一不會發生：

| 條件 | 說明 |
|------|------|
| bash 3.2 | macOS 內建 `/bin/bash` 停在 3.2.57，Apple 因 GPLv3 授權不再隨系統升級。**`#!/usr/bin/env bash` 不是逃生路**——未另裝新版時 `env bash` 解析到的仍是同一支 3.2 |
| UTF-8 locale | `C` / `POSIX` locale 下該位元組被判為非名稱字元、邊界正確落在 `CODE`，腳本正常執行；`en_US.UTF-8`、`zh_TW.UTF-8` 等 UTF-8 locale 才觸發 |
| 裸 `$VAR` 後緊鄰全形標點 | bash 3.2 在 UTF-8 locale 下判定變數名邊界時，把全形標點的首位元組併入名稱，`$CODE）` 解析為變數 `CODE\xef` 而非 `CODE` |
| `set -u` | 未定義變數由靜默展開為空字串，升級為中止執行 |

關鍵在於位元組是被**併入**名稱，不是終止名稱。若該位元組被判為邊界，名稱會停在 `CODE`（已定義），反而不會出錯——這正是 `C` locale 下的實際行為。方向若記反，會推導出「非 ASCII 一定是邊界所以安全」的相反結論。

被併入的位元組值依標點所屬區塊而不同，兩者都會觸發：

| 標點 | Unicode 區塊 | 併入的首位元組 |
|------|-------------|--------------|
| `（` `）` `：` `，` `；` `！` `？` | U+FF00 全形 ASCII 變體 | `0xEF` |
| `。` `、` `「` `」` | U+3000 CJK 標點 | `0xE3` |

以上四個條件與兩張對照表均為本機實測結果。至於「為何 UTF-8 locale 才發生」（bash 3.2 不完整的多位元組支援，或 locale 的字元分類差異）、bash 4.x/5.x 的行為、以及 Apple 停止升級的授權原因，屬引用或推論而非實測，此處只記錄觀測規則。

bash 4.x/5.x 已修正變數名的多位元組邊界判定，同一腳本不會重現。

## 為何難以複現與追查

**兩條獨立的環境軸**使同一支腳本在不同機器上表現不一致，任一條都足以讓人「怎麼試都複現不了」：

| 軸 | 觸發值 | 不觸發值 | 典型出現處 |
|----|-------|---------|----------|
| bash 版本 | 3.2 | 4.x / 5.x | 3.2 為 macOS 內建；4/5 需另裝（如 homebrew） |
| locale | UTF-8 系（`en_US.UTF-8`、`zh_TW.UTF-8`） | `C` / `POSIX` | UTF-8 為互動式 shell 常見預設；`C` / `POSIX` 為多數 CI |

「典型出現處」只是機率分佈，不是綁定——macOS CI 跑的同樣是 3.2，開發者在 `LANG=C` 下跑一樣安全。兩條軸各自獨立成立。

複現失敗時第一個該查的是 locale，其次才是 bash 版本：macOS 預設就是 3.2，bash 版本是兩軸中較少變動的那一條。

**觸發時機本身也是隱蔽的**：含全形標點的字串最常出現在錯誤訊息裡（「失敗（exit $CODE）」「錯誤：$MSG」），這些行只在失敗分支執行，正常路徑永遠碰不到。結果是：

- 所有測試通過時，腳本看起來完全正常
- 真正有東西失敗、最需要看清楚失敗原因時，腳本自己先崩，且退出碼與訊息都與真正的失敗無關

錯誤處理路徑本身有錯誤，是這個 pattern 的核心危害——它把診斷工具變成第二個故障源。

## 偵測

```bash
# 掃描裸 $VAR 緊鄰全形標點，涵蓋 U+FF00 與 U+3000 兩區塊
grep -rnE '\$[A-Za-z_][A-Za-z0-9_]*[（）：，。、；！？「」]' --include='*.sh' .

# 確認 locale：C / POSIX 不觸發，UTF-8 才觸發
locale | head -3

# 確認執行期的 bash 版本，別假設 env bash 是新版
/bin/bash --version | head -1
"$(command -v bash)" --version | head -1
```

兩處刻意的寫法：

- **`grep` 用 `-E` 而非 `-P`**：macOS 內建 `/usr/bin/grep` 為 BSD grep，不支援 `-P`（回報 `invalid option -- P`）。上述 pattern 無 PCRE 專屬構造，ERE 完全等價，無功能損失。
- **bash 路徑用 `"$(command -v bash)"` 而非 `xargs -I{}`**：BSD xargs 只在參數位置做 replstr 置換，不在工具名稱位置置換，`command -v bash | xargs -I{} {} --version` 會失敗於 `xargs: {}: No such file or directory`——該訊息容易被誤讀為找不到 bash。

此 pattern 本身在論證「別假設本機工具等於別人的工具」，偵測指令不應犯同一個假設。

## 修正

一律用 `${VAR}` 大括號界定變數名邊界：

```bash
echo "失敗（exit ${CODE}）"   # 正確
echo "失敗（exit $CODE）"     # 3.2 + UTF-8 locale 下崩潰
```

大括號使變數名邊界顯式，與後續任何字元都無歧義，且對所有 bash 版本與 locale 行為一致。

## 預防

| 措施 | 說明 |
|------|------|
| 腳本內變數展開一律加大括號 | 不逐處判斷「後面接的是不是全形字元」——判斷成本高於一律加，且漏判只在錯誤路徑顯形 |
| 錯誤路徑必須被實際執行過 | 以 mock 或注入失敗替身跑過每一條失敗分支，不能只驗證 happy path 就宣稱腳本可用 |
| 將偵測段的 grep 掃描接進 pre-commit 或 CI | 專案語言規則要求輸出繁體中文時，全形標點會出現在幾乎每一條錯誤訊息裡，觸發面遠大於英文專案，靠人工留意不可靠 |
| CI 綠燈不等於本機安全 | CI 常用 `C` locale 而不觸發，開發者本機的 UTF-8 locale 才會炸。若專案僅以 CI 綠燈為準，此類缺陷會一路留到使用者手上 |

## 適用範圍

在 macOS 上以 `/bin/bash` 或 `env bash`（解析到 3.2 時）執行、於 UTF-8 locale 下運行、且訊息含 CJK 全形標點的 shell 腳本。與專案語言、框架無關；替換專案名稱與檔案路徑後仍成立。

## 相關

- `.claude/rules/core/language-constraints.md` 規則 1 要求輸出繁體中文，直接構成本 pattern 的觸發條件之一——採用該規則的專案，全形標點會密集出現在錯誤訊息中
- `.claude/rules/core/observability-rules.md` 規則 1 要求錯誤路徑必須有可見輸出，本 pattern 使該輸出反而成為故障源，兩者需一併考量

---

**Source**: 1.4.0-W2-033（建立 `scripts/run-tests.sh` 時於實測失敗分支發現並修正）
