# 共用 bin 目錄的 CLI 入口（uv tool／pipx／brew 的 symlink）

`~/.local/bin` 這類共用 bin 目錄由多個安裝機制共同寫入。uv tool、pipx、brew 在這裡放的入口通常是 symlink，指向自己管理的安裝環境；這些工具判斷「已安裝」時讀自己的 metadata，不讀入口檔內容。

## SBIN-1 安裝工具顯示已安裝、CLI 卻執行失敗，被讀成 CLI 本身的缺陷

| 欄位 | 內容 |
|------|------|
| 症狀 | 以 uv tool（或 pipx、brew）安裝的 CLI 執行失敗，錯誤訊息不像該 CLI 的輸出；`uv tool list` 仍列出該套件；不帶 `--force` 的重裝回報已安裝並略過，問題不變 |
| 常見誤判 | 安裝狀態正常，所以是 CLI 程式或其相依的缺陷；或認定重裝過就排除了安裝問題 |
| 實際機制 | 另一個安裝器以會跟隨 symlink 的方式（`write_text`、`open(w)`、`>`）寫入同一路徑，改寫的是 symlink 目標，也就是對方環境內的入口檔；對方的 metadata 未變，所以狀態查詢與一般重裝都看不到 |
| 檢查方法 | `p="$(command -v <cli>)"; ls -l "$p"; head -5 "$(readlink -f "$p")"` |
| 正向對照 | 在隔離目錄（`UV_TOOL_DIR`、`UV_TOOL_BIN_DIR` 指向暫存目錄）`uv tool install` 一個套件，再以 `printf 'X\n' > <bin>/<cli>` 寫入其入口；同一檢查必須看到 symlink 與被改寫的目標內容 |
| 判讀標準 | `ls -l` 為 symlink、目標檔開頭不是該安裝工具產生的啟動腳本（例如是另一機制的 shim）→ 入口已被寫穿，以 `uv tool install --force <pkg>` 復原後再判斷 CLI 本身；目標檔是該工具產生的啟動腳本 → 入口正常，再往 CLI 本身查 |
| 來源 | IMP-LLM-017 |
