---
id: IMP-GPD-009
title: zsh 把變數後的冒號加字母解析為修飾符，使 `$c:path` 的路徑首字母被吃掉
status: active
severity: 低
---

# IMP-GPD-009: zsh 把變數後的冒號加字母解析為修飾符，使 `$c:path` 的路徑首字母被吃掉

## 基本資訊

- **Pattern ID**: IMP-GPD-009
- **分類**: 實作 bug（implementation）
- **來源版本**: 0.5.0
- **發現日期**: 2026-10-20
- **風險等級**: 低
- **影響範圍**: Bash 工具在 zsh 下執行的命令（macOS 預設 shell），凡在不加大括號的變數後緊接 `:` 與字母者

---

## 問題描述

### 症狀

在迴圈中以 `git show $c:lib/l10n/x.dart` 逐一讀各 commit 的檔案，git 回報：

```
fatal: ambiguous argument '2f7305f42ib/l10n/x.dart': unknown revision or path not in the working tree.
```

路徑的 `l` 消失，冒號也消失。若命令外再包一層 `$(... | wc -c)` 之類的處理，錯誤可能只出現在 stderr，stdout 得到 0 或空字串，看起來像「該 commit 的檔案第 N 行是空的」——錯誤的結論與真實的空行在輸出上同形。

同源的第二個實例：`echo ======` 在 zsh 報 `===== not found`。

### 根因

zsh 的參數展開支援 csh 式修飾符：`$var:l`（轉小寫）、`:u`（轉大寫）、`:h`（取目錄）、`:t`（取檔名）、`:r`（去副檔名）、`:e`（取副檔名）等。變數名後緊接 `:` 與這些字母時，zsh 視為修飾符而非字面冒號。`$c:lib/...` 被解析為 `${c:l}` 加上 `ib/...`。bash 沒有這個語法，同一行在 bash 下照字面展開，所以沿用 bash 習慣寫法的命令在 zsh 下靜默變形。

`echo ======` 的成因是 zsh 的 `EQUALS` 選項：以 `=` 開頭的單字會展開為同名命令的完整路徑（`=ls` → `/bin/ls`），`======` 被當作查找名為 `=====` 的命令。

---

## 解決方案

變數後接冒號時一律加大括號並加引號：

```bash
for c in 2f7305f42 a63ef7b62; do
  git show "${c}:lib/l10n/app_localizations_en.dart" | sed -n 3p
done
```

分隔線改用不以 `=` 開頭的字串，或加引號：`echo '======'`。

---

## 預防措施

- 在 Bash 工具中寫 `git show <rev>:<path>`、`scp host:path` 這類「變數加冒號」的參數時，變數一律寫成 `"${var}:..."`。
- 迴圈輸出結果與預期不符（整列為 0、空字串）時，先看 stderr 有沒有 `ambiguous argument`，不要先下「資料本身為空」的結論；以單一 commit、不經迴圈的固定值命令重跑一次核對（`tool-output-trust-rules` 規則 3）。
- 不需新增 hook：修飾符字母集合大且合法用法存在，靜態偵測誤報率高。

---

## 關聯

- 發現情境：2026-10-20，PM 在 Flutter 專案中逐一比對多個 commit 的 l10n 生成檔，以找出某個空行是被哪個 commit 移除
- 相關：`IMP-056`（zsh chpwd hook 淹沒輸出，同屬 zsh 與 bash 行為差異）
