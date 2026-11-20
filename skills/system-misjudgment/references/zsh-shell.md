# zsh shell（macOS 預設 shell）

Bash 工具在 macOS 上由 zsh 執行。zsh 對變數展開與內建 `echo` 的語意和 bash 不同，從 bash 習慣搬過來的寫法會靜默改變值，而且多半不報錯。

## ZSH-1 變數後接冒號被當修飾詞，值被截斷但全程無錯誤

| 欄位 | 內容 |
|------|------|
| 症狀 | 驗證命令全程無錯誤，受測腳本卻表現為判斷不成立（例：shim 預驗證不命中） |
| 常見誤判 | 受測對象的修正無效或有缺陷 |
| 實際機制 | zsh 對未加大括號的 `$var` 後接 `:a`／`:h`／`:t`／`:r`／`:e` 套用修飾詞，即使在雙引號內；值被截斷但不報錯（IMP-GPD-009、IMP-GPD-025） |
| 檢查方法 | `printf '%s\n' "$VAR"` 印出組好的值；或 `sh -x <受測腳本>` 看實際收到的參數與環境變數 |
| 正向對照 | `O=abc; printf '%s\n' "$O:refs"` 在 zsh 輸出被截斷的 `abcefs`；`printf '%s\n' "${O}:refs"` 輸出 `abc:refs` |
| 判讀標準 | 印出值與預期逐字一致，才把失效歸給受測對象；不一致即為驗證命令錯誤 |
| 來源 | IMP-GPD-009、IMP-GPD-025 |

## ZSH-2 echo 展開反斜線，顯示失真或 hook payload 損壞

| 欄位 | 內容 |
|------|------|
| 症狀 | 以 `echo "$out"` 顯示的 CLI 輸出中，反斜線路徑出現 tab 或換行；或以 `echo "$P" \| <hook>` 餵 payload，hook 沒有任何輸出 |
| 常見誤判 | CLI 把反斜線寫壞了；或 hook 判定放行（守衛修正沒有生效） |
| 實際機制 | zsh 內建 `echo` 預設解析 `\t`、`\n` 等跳脫序列，即使在雙引號內。JSON 字串值裡的 `\n` 變成真換行後 payload 成為無效 JSON，hook 走空輸入的預設放行路徑，輸出與真實放行相同（IMP-LLM-019） |
| 檢查方法 | 顯示：`printf '%s\n' "$out"`，或 `printf '%s' "$out" \| od -c` 看原始位元組。payload：`printf '%s' "$P" \| python3 -m json.tool >/dev/null && echo ok` 確認合法後，再以 `printf '%s' "$P" \| <hook>` 餵入 |
| 正向對照 | `P='{"a":"x\ny"}'; echo "$P" \| python3 -m json.tool` 在 zsh 報 JSON 解析錯誤，`printf '%s' "$P" \| python3 -m json.tool` 通過；守衛類 hook 另以一個已知該被擋下的 payload 用 `printf` 餵入，必須得到 deny |
| 判讀標準 | payload 經 json.tool 確認合法、且正向對照得到 deny 之後，「沒有輸出」才能讀成放行；顯示內容以 `printf` 或 `od -c` 的結果為準 |
| 來源 | IMP-LLM-019 |
