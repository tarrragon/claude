---
id: IMP-LLM-017
title: "安裝器寫入共用 bin 目錄的既有路徑時順著 symlink 寫進他方的安裝環境：對方狀態查詢仍顯示已安裝，一般重裝不修復"
severity: high
category: implementation
related:
  - id: PC-GPD-033
    kind: citation
  - id: PC-145
    kind: citation
created: 2026-11-20
---

# IMP-LLM-017: 安裝器寫入共用 bin 目錄時順著 symlink 寫進他方的安裝環境

## 基本資訊

- **風險等級**: 高
- **分類**: implementation（檔案寫入的 symlink 語意）
- **來源版本**: 3.5.0
- **首次觀測**: 2026-11（隔離目錄實測）

## 症狀

某安裝器每次執行都把自己的入口檔（shim）寫到共用 bin 目錄（例：`~/.local/bin/<cli>`）。同一台機器上，另一個工具（uv tool、pipx、brew 等）先在同一路徑建立了 symlink，指向它自己管理的安裝環境。安裝器執行後：

- `<bin>/<cli>` 仍是 symlink，外觀與安裝器執行前相同。
- symlink 指向的目標檔（位於對方工具的環境內）內容被換成安裝器的 shim。
- 以對方工具的方式使用該 CLI 時失敗，錯誤訊息來自 shim，不來自 CLI 本身。
- 對方工具的狀態查詢（如 `uv tool list`）仍顯示已安裝；不帶強制旗標的重裝回報「已安裝」並略過，不修復；只有強制重裝（如 `uv tool install --force`）才救回。

量測環境：macOS，scratchpad 隔離目錄，`UV_TOOL_DIR`、`UV_TOOL_BIN_DIR` 與安裝器的 bin 目錄變數皆指向隔離目錄。

| 步驟 | `<bin>/<cli>` | 在非安裝器管轄的目錄執行 |
|------|---------------|------------------------|
| A. `uv tool install <pkg>` | symlink → `<tools>/<pkg>/bin/<cli>` | rc=0 |
| A2. 執行安裝器 | 仍是 symlink，**目標檔內容已是 shim** | rc=1，shim 的錯誤訊息 |
| B. `uv tool install <pkg>`（無 `--force`） | 不修復，uv 認為已安裝 | — |
| C. `uv tool install --force <pkg>` | 修復 | rc=0 |

## 根因

`Path.write_text`、`open(path, "w")` 與 shell 的 `>` 重導向都會解析 symlink，寫入的是 symlink 的目標檔，不是 symlink 本身。安裝器作者的預期是「取代這個路徑上的東西」，實際行為是「改寫這個路徑最終指向的檔案」。

兩個條件同時成立時就會寫穿：

1. 安裝器不先判定目標路徑的現況（不存在／自己的產物／他方的 symlink／他方的一般檔），對任何既有路徑一律覆寫。
2. 共用 bin 目錄由多個安裝機制共同使用，其中一些機制以 symlink 指向自己的環境。

修壞的位置在對方的環境內，對方工具以自己的 metadata 判斷安裝狀態，不檢查入口檔內容，所以狀態查詢與一般重裝都看不出異常。

## 偵測方式

判定某 CLI 是否已被寫穿：

```bash
p="$(command -v <cli>)"
ls -l "$p"                    # 是否為 symlink，指向哪裡
head -5 "$(readlink -f "$p")" # 目標檔的內容是否為他方的 shim
```

- 正向對照：先在隔離目錄依上表 A、A2 重現一次，確認此檢查在已寫穿的入口上會看到 shim 內容。
- 判讀：`ls -l` 顯示 symlink、目標檔開頭卻是安裝器 shim 的內容 → 已寫穿。目標檔為對方工具產生的入口（如 uv 的 Python 啟動腳本）→ 未受影響。

## 防護

| 措施 | 說明 |
|------|------|
| 以 lstat 判定現況 | 寫入前用 `os.lstat`（不跟隨 symlink）分類目標：不存在、自己的產物、symlink、他方一般檔、判定失敗 |
| 不覆寫非本機制的產物 | 只有「不存在」與「自己的產物」可以寫入；symlink 與他方一般檔一律保留，並輸出可見警告與處置指令（如改用哪個工具卸載、如何以強制重裝復原） |
| 寫入不跟隨 symlink | 以 `os.open(path, O_WRONLY \| O_CREAT \| O_TRUNC \| O_NOFOLLOW)` 寫入；判定後目標被換成 symlink 時寫入失敗，不會寫穿 |
| 判定失敗不寫 | lstat 或讀檔出錯歸為「無法判定」，不寫入並警告；不退回一般寫入 |
| 自己的產物要可辨識 | shim 內放固定標記，判定「自己的產物」時讀標記，不憑檔名或位置 |
| 測試 | 以隔離目錄建立 symlink 指向另一個目錄的目標檔，執行安裝器後斷言目標檔內容不變（正向對照：移除防護時此斷言必須翻紅） |

同族：安裝器偵測到 `core.hooksPath` 已設定時，不把 git hook 寫進該目錄，改為跳過並警告——該目錄常由其他工具（如 husky）或專案版控管理。兩者的共同原則是：安裝器只寫自己管理的位置，他方管理的位置只讀不寫。

## 相關

- PC-GPD-033：守衛判定以 symlink 繞回受保護區的繞過形態；同屬「路徑字面與最終目標不同」。
- PC-145：已安裝 CLI 的實際內容與預期不同時，被讀成程式缺陷。
