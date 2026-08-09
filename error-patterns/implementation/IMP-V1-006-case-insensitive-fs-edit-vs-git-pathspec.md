---
id: IMP-V1-006
title: 大小寫不敏感檔案系統上 Edit 工具寫入成功，但 git pathspec 以不同大小寫尋址失敗
category: implementation
severity: low
created: 2026-07-05
source_ticket: 1.5.0-W5-011.1
---

# IMP-V1-006: 大小寫不敏感檔案系統上 Edit 成功但 git pathspec 失敗

## 症狀

`git add <path>` 或 `git commit -- <path>` 回報 `error: pathspec '<path>' did not match any file(s) known to git`，但同一字面路徑的 Read / Edit / Write 全部成功，且檔案內容確實已被修改（`git status` 也列出該檔為 modified，只是大小寫不同）。

## 根因

兩層對「同一路徑」的判定標準不一致：

1. **檔案系統層**：macOS APFS 預設大小寫不敏感（case-insensitive, case-preserving）——以 `SKILL.md` 開啟實際名為 `skill.md` 的檔案會成功，工具層（Read/Edit/Write）完全無感。
2. **git 層**：pathspec 與 index 中記錄的實際檔名做大小寫敏感匹配——`SKILL.md` 對 index 內的 `skill.md` 不命中，直接報 pathspec 錯誤。

觸發條件通常是命名慣例混雜：目錄下多數檔案採一種大小寫慣例（如 skill 檔慣例 `SKILL.md`），個別歷史檔案實際為另一種（`skill.md`），操作者以慣例推斷檔名而未驗證。

## 偵測

pathspec 錯誤當下，以固定值命令確認實際大小寫（tool-output-trust 規則 3）：

```bash
git ls-files <目錄>   # index 中的權威檔名
ls <目錄>             # 檔案系統中的實際大小寫（case-preserving 會顯示原始命名）
```

## 解決方案

以 `git ls-files` 回報的實際檔名重下 git 命令。工具層先前的編輯不需重做（內容已正確落盤）。

## 防護措施

1. **git pathspec 以 `git ls-files` 實際檔名為準**：對 `.md` 等慣例命名檔案下 git 命令前，若曾以「慣例大小寫」而非「實測檔名」引用路徑，先 `git ls-files` 驗證。
2. **「Edit 成功」不保證 git 可以同字面路徑尋址**：大小寫不敏感檔案系統上兩者判定標準不同，工具層成功不可作為 git 層路徑正確的證據。
3. **命名慣例統一**：發現慣例外大小寫的歷史檔名時，依規則 5 建 ticket 追蹤重命名（`git mv` 需兩段式處理大小寫變更），不在當下任務內順手改。

## 二次觸發擴充：慣例外檔名使 case-sensitive 掃描器靜默漏樣本（2026-08-09）

同一根因的第二種後果面：受害者不只 git pathspec，還包括**任何以 case-sensitive glob 掃描該慣例檔名的產生器與稽核器**。

實例：某 skill 目錄下三個 skill 的檔案實際名為 `skill.md`（其餘 55 個為 `SKILL.md`）。skill 同步工具的 manifest 產生器以 `repo_dir.glob("*/SKILL.md")` 掃描，這三個不進入 manifest；手動補寫的記錄會被下一次重算抹除，形成「補齊後回退」的循環，潛伏 15 天。

**三種掃描寫法的漏掃條件不同，但都不告警**（2026-08-09 實測，同一 APFS 目錄下的 `foo/skill.md`）：

| 寫法 | 漏掃條件 | 實測 |
|------|---------|------|
| `glob("*/SKILL.md")` | **Python < 3.13 恆漏；>= 3.13 改為探測檔案系統**，故在 case-sensitive fs（Linux ext4）仍漏 | 3.12.11 → `[]`；3.13.7 / 3.14.4 → 命中 `skill.md` |
| `dir / "SKILL.md"`（stat） | case-sensitive fs 漏；與 Python 版本無關 | APFS 上 `.exists()` → True |
| 讀 dirent 名稱後 `== "SKILL.md"` | **恆漏**，與 fs 和 Python 版本皆無關 | `skill.md == "SKILL.md"` → False |

**Why 難以察覺（兩層）**：其一，稽核輸出把未進入比對的樣本列為一個數字（`分歧 0、無遠端雜湊 5`）——分歧會被列名並要求處置，數字不會，「分歧 0」讀起來像全面通過，但那 5 個從未進入分母。其二，glob 型的漏掃是 **Python 版本 × 檔案系統雙重相依**：開發機用新版 Python + APFS 時命中，換到舊版虛擬環境或 Linux CI 即漏，同一份程式碼在不同環境給出不同掃描集合，且兩邊都不報錯。

**Consequence**：這三個 skill 即使內容已漂移也不會被報出；且第一次修復把根因誤判為「manifest 記錄缺漏」，補記後看似修好，實則下次重算即回退。

**Action**（在既有防護 1-3 之外追加）：

4. **掃描慣例檔名時對大小寫變體發警告，不靜默略過**。判定須讀 `os.scandir` 的實際目錄項名稱——這是唯一與 Python 版本、檔案系統皆無關的判準。`(d / "SKILL.md").exists()` 在 case-insensitive fs 上對 `skill.md` 回 True，`glob()` 的結果隨 Python 版本與 fs 浮動，兩者當判準都等於沒判。修法是統一為慣例大小寫並對不符者告警，不是把 glob 放寬為 case-insensitive（放寬會讓兩種檔名長期並存並在同步時互相覆蓋）。
5. **驗證遠端 repo 的檔名不可用本地 clone 的 `ls`**：本地 case-insensitive fs 會把兩種大小寫折疊為一個檔案，`ls` 看到的不是遠端真實狀態。用 `git ls-tree` 或 `gh api "repos/<owner>/<repo>/git/trees/<branch>?recursive=1"`。（本節收窄上方「偵測」段：`ls` 僅在驗證本地單一檔案的實際命名時可用。）
6. **稽核輸出以「數量」呈現的未比對樣本，等同未驗證**：看到 `skipped` / `無雜湊` / `unmatched` 類計數非零時，先確認掃描前提是否失效，再讀其他計數。綠燈的分子不構成證據，除非分母涵蓋全體。

## 關聯

- `.claude/rules/core/tool-output-trust-rules.md` 規則 3 — 固定值交叉驗證（本 pattern 的偵測手段）
- `.claude/rules/core/bash-tool-usage-rules.md` — Bash 命令前置檢查
- 記憶 `guard-must-parse-ssot-with-consumer-parser` — 同族主張：稽核工具的掃描前提失效時，其綠燈不構成證據
