---
id: IMP-GPD-023
title: zsh 不對未加引號的變數做字詞拆分，把檔案清單存進變數再傳給掃描命令時，整串被當成一個不存在的路徑，掃描結果與零命中同形
status: active
severity: 中
---

# IMP-GPD-023: zsh 不拆分變數裡的檔案清單，掃描命令的「零命中」其實是「沒掃到」

## 基本資訊

- **Pattern ID**: IMP-GPD-023
- **分類**: 實作 bug（implementation）
- **來源版本**: 0.5.0
- **發現日期**: 2026-10-31
- **風險等級**: 中
- **影響範圍**: Bash 工具在 zsh 下執行的命令（macOS 預設 shell），凡把多個路徑存進一個變數、再以 `$VAR` 傳給 grep／cat／ls 者；以及在變數之後接 glob 限定詞（`$D/*.json(N)`）者

---

## 問題描述

### 症狀

complete 前的自檢要掃描變更檔裡的禁用詞，命令寫成：

```bash
FILES="$L/hooks/a.ts $L/hooks/b.ts"
echo banned=$(grep -c "數據\|代碼" $FILES | awk -F: '{s+=$2} END{print s}')
```

輸出是 `banned=`（空值），stderr 另有一行 `No such file or directory`，裡面列的是兩個路徑以空白相連的整串字。若只讀 stdout，或 stderr 被 `2>/dev/null`、`| tail` 濾掉，空值與 0 看起來都是「沒有命中」，自檢就以「通過」收尾，實際上一個檔案也沒讀。

同一 session 的第二個實例：背景取樣器以 `for f in $D/*.json(N)` 列檔，zsh 回報 `no matches found: .../*.json(N)`，迴圈在第一輪就以 exit 1 中止，取樣檔 0 行。

### 根因

bash 對未加引號的 `$VAR` 依 IFS 做字詞拆分，所以 `grep pat $FILES` 會收到多個參數。zsh 預設關閉 `SH_WORD_SPLIT`，`$FILES` 永遠展開成一個參數，含空白的整串字被當成一個檔名。沿用 bash 習慣的命令在 zsh 下不會報語法錯誤，只會在執行期得到「檔案不存在」，而這個錯誤走 stderr。

第二個實例的 `(N)`（NULL_GLOB 限定詞）在 Bash 工具的執行環境中沒有生效，未命中時仍觸發 `NOMATCH` 錯誤。

兩者的共同點：命令在 bash 下正確，在 zsh 下靜默改變語意，而且錯誤輸出的形狀和「確實沒有東西」相同。

---

## 解決方案

把清單交給位置參數，再以 `"$@"` 展開，每個路徑各自成為一個參數：

```bash
set -- "$L/hooks/a.ts" "$L/hooks/b.ts"
ls "$@" | wc -l          # 先確認檔案數符合預期
cat "$@" | grep -c "數據\|代碼"
```

列目錄時改用 `find`，不依賴 glob 限定詞：

```bash
find "$D" -name '*.json' -type f | while read -r f; do ...; done
```

---

## 預防措施

- 掃描、計數類命令先證明「有掃到」：以 `ls "$@" | wc -l` 印出實際讀到的檔案數，數字和預期一致，零命中才算數（`tool-output-trust-rules` 規則 3：用固定值交叉驗證）。
- 計數結果是空字串而非 0 時，視為命令失敗，不當作零命中；先讀 stderr。
- 多個路徑不存進單一字串變數；需要重複使用時用 `set --` 或 zsh 陣列 `files=(a b)` 再以 `"${files[@]}"` 展開。
- 不需新增 hook：未加引號的變數展開有大量合法用法，靜態偵測誤報率高。

---

## 關聯

- 發現情境：2026-10-31，主線程在 complete 前自檢與背景取樣 context 用量檔時，兩次各自觸發
- 相關：`IMP-GPD-009`（zsh 把變數後的冒號加字母解析為修飾符，同屬 bash 寫法在 zsh 下靜默變形）、`IMP-056`（zsh chpwd hook 淹沒輸出）
- 相關：`.claude/references/agent-self-check-template.md`〈為何「掃描手段」是必要欄位〉（零 finding 可能是沒掃到）
