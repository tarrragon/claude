---
id: IMP-LLM-019
title: zsh 內建 echo 預設展開反斜線跳脫，擷取的輸出顯示失真、手動送進 hook 的 JSON payload 損壞，兩者都與「內容本來就這樣」同形
severity: medium
category: implementation
status: active
created: 2026-11-20
related:
  - id: IMP-GPD-023
    kind: citation
  - id: IMP-GPD-025
    kind: citation
---

# IMP-LLM-019: zsh 的 echo 會改寫反斜線，用它顯示或轉送擷取的字串，看到的不是原值

## 基本資訊

- **Pattern ID**: IMP-LLM-019
- **分類**: 實作 bug（implementation）
- **來源版本**: 3.5.0
- **發現日期**: 2026-11-11
- **風險等級**: 中
- **影響範圍**: Bash 工具在 zsh 下執行的命令（macOS 預設 shell），凡以 `echo "$VAR"` 顯示擷取的 CLI 輸出，或以 `echo "$P" | <hook>` 手動餵 JSON payload 驗證 hook 者

---

## 問題描述

### 症狀

兩個實例，機制相同，失效形態不同。

**實例 1：顯示擷取的輸出失真。** PM 以 `out=$(ticket create ...); echo "$out"` 顯示建票結果，票面的 `D:\side\termchat` 顯示成 `D:\side<tab>ermchat`，看起來像 CLI 把反斜線轉成了 tab。以 `od -c` 檢查票檔，內容逐字正確；失真只發生在顯示這一步。

**實例 2：手動送進 hook 的 payload 損壞，結果與放行同形。** 驗證 Bash 寫入守衛的修正時，PM 以 `echo "$P" | <hook>` 餵入一個應被擋下的 payload。改前與改後兩版都沒有輸出，看起來像新版也照樣放行。改用 `printf '%s'` 後才得到改前放行、改後 deny 的預期對照。

### 根因

zsh 的內建 `echo` 預設解析跳脫序列（等同 bash 的 `echo -e`），即使參數放在雙引號內：`\t` 變成 tab，`\n` 變成換行，`\\` 變成單一反斜線。bash 的內建 `echo` 預設不解析，所以從 bash 習慣搬過來的寫法會在 zsh 靜默改變內容。

實例 2 的失效鏈多一層：JSON 字串值裡的 `\n` 被展開成真換行，字串內出現未跳脫的控制字元，payload 變成無效 JSON。hook 讀不到合法輸入，走空輸入的預設放行路徑，不輸出任何東西。「沒有輸出」同時符合「hook 判定放行」與「hook 根本沒讀到 payload」兩種成因，單看輸出分不出來。

### 最小重現（zsh 5.9 實測）

```bash
# 實例 1：顯示失真
out='D:\side\termchat'
echo "$out"            # D:\side<tab>ermchat
printf '%s\n' "$out"   # D:\side\termchat

# 實例 2：JSON payload 損壞
P='{"tool_input":{"command":"a\nb"}}'
echo "$P" | python3 -c 'import json,sys; json.load(sys.stdin); print("valid")'
#   json.decoder.JSONDecodeError: Invalid control character at: line 1 column 28 (char 27)
printf '%s' "$P" | python3 -c 'import json,sys; json.load(sys.stdin); print("valid")'
#   valid
```

hook 層的對照（同一個應被擋下的 payload，command 內含 `\n`，目標為受限路徑 `test/`）：

| 餵入方式 | Bash 寫入守衛的輸出 | rc |
|---------|-------------------|----|
| `echo "$P" \| <hook>` | 無輸出（payload 無效，走空輸入放行） | 0 |
| `printf '%s' "$P" \| <hook>` | `"permissionDecision": "deny"` | 0 |

兩者 rc 都是 0，只有輸出內容能區分，而前者的輸出與「判定放行」完全相同。

---

## 解決方案

- 顯示擷取的字串一律用 `printf '%s\n' "$VAR"`，不用 `echo`。
- 手動餵 payload 給 hook 時用 `printf '%s' "$P" | <hook>`，或把 payload 寫成檔案後以 `< file` 重導，不經 `echo`。
- 懷疑顯示結果時，以 `od -c` 或 `xxd` 檢查原始位元組，不以終端顯示為準。

## 預防措施

- 驗證 hook 時，先確認 payload 本身是合法 JSON（`printf '%s' "$P" | python3 -m json.tool >/dev/null && echo ok`），再看 hook 的輸出。「沒有輸出」只有在 payload 合法時才能讀成「放行」。
- 驗證守衛類 hook 一律附正向對照：同一餵入方式下，一個已知該被擋下的 payload 必須得到 deny；得不到時先懷疑餵入方式，不先懷疑 hook。
- 擷取輸出含 Windows 路徑、跳脫序列或 JSON 時，顯示與轉送都改用 `printf`。

## 發現情境

2026-11-11，實例 1：建票後顯示結果時發現 Windows 路徑的 `\t` 被顯示成 tab，以 `od -c` 確認票檔正確。

2026-11-18，實例 2：驗證 Bash 寫入守衛的 cd 目標展開修正時，echo 版對照兩版皆無輸出；改用 `printf '%s'` 後得到改前放行、改後 deny。

## 相關模式

- IMP-GPD-023：zsh 不對未加引號的變數做字詞拆分。同屬「bash 習慣的寫法在 zsh 靜默變質」，機制不同。
- IMP-GPD-025：zsh 把 `$var:` 後的字母當修飾詞。同屬 zsh 語意差異，機制不同。
