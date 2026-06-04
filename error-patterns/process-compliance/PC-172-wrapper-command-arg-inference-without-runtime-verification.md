# PC-172: Wrapper command 參數推斷未經 runtime 驗證

## 摘要

診斷 wrapper command（node / shell / python script 包裝底層 binary）的正確 CLI args 時，只讀底層 binary 的 `--help` 推斷，忽略 wrapper 可能自動注入 / 改寫 / 過濾參數，導致設定錯誤且啟動失敗。修正方向：先用 `file` 確認 command 是否為 wrapper，讀其轉發邏輯，並實機啟動驗證，不以 `--help` 作為 wrapper 的參數契約。

## 症狀

- 依 `--help` 推斷的 args 設定後，server / CLI 啟動報 `argument X cannot be used multiple times` 或 `unexpected argument Y`
- 設定看似符合官方文件 / help，但實機啟動立即崩潰
- 同一設定檔內已有能運作的同類 entry，但新 entry 沿用 help 推斷卻失敗

## 根因（兩層介面錯位）

wrapper 與底層 binary 是兩層獨立介面：

| 層 | 角色 | `--help` 反映誰 |
|----|------|----------------|
| wrapper（設定檔的 `command`） | 實際被呼叫的入口 | 否（除非 wrapper 自己印 help） |
| 底層 binary | wrapper 內部 spawn 的對象 | 是 |

`--help` 反映的是**底層 binary** 的參數表，但設定檔 `command` 實際呼叫的是 **wrapper**。wrapper 的轉發邏輯（自動注入旗標、改名子命令、過濾參數）不在 `--help` 中，只存在於 wrapper 原始碼或實機行為。當診斷者把 `--help` 當成 wrapper 的契約，就會把底層 binary 接受的參數重複傳給已自動注入該參數的 wrapper。

## 案例：.mcp.json codegraph MCP server 設定（2026-06-03）

設定 `command: codegraph-mcp`，該 command 為 node wrapper，內部：

```javascript
// Pass --mcp plus all user args to the binary
const args = ["--mcp", ...process.argv.slice(2)];
```

診斷第一版判斷 args 應為 `["--mcp"]`（讀底層 `codegraph-server` binary 的 `--help`，其中 `--mcp` 是合法 flag）。實機啟動報：

```
error: the argument '--mcp' cannot be used multiple times
```

讀 wrapper 原始碼才發現 wrapper 已自動注入 `--mcp`，正確 args 為 `[]`（與同檔 `codebase-memory-mcp` 的 `args: []` 一致）。錯誤的原始設定 `args: ["serve", "--mcp"]` 中 `serve` 亦非合法子命令，同樣是只憑推斷未實機驗證的產物。

## 防護（四步診斷流程）

| 步驟 | 動作 | 目的 |
|------|------|------|
| 1 | `file $(which <cmd>)` | 確認 command 是 native binary 還是 wrapper script |
| 2 | 若是 script，讀其轉發邏輯（grep `spawn` / `exec` / `process.argv` / `"$@"`） | 找出自動注入 / 改名 / 過濾的參數 |
| 3 | 實機啟動驗證（背景 process + 餵協定 init 請求看 log） | 確認 runtime 行為，非僅靠 `--help` |
| 4 | 對照同設定檔已運作的同類 entry | 借用已驗證的正確形式 |

**Why**：wrapper 的真實參數契約只在原始碼與 runtime 行為中可見，靜態文件不足採信。

**Consequence**：跳過四步直接以 `--help` 推斷，會在啟動階段才崩潰；若該設定屬不常重啟的 server（如 MCP），錯誤可能潛伏數個 session 無人察覺（本案例 codegraph 連線失敗即長期未被診斷）。

**Action**：修改任何 wrapper command 的 args 前，至少完成步驟 1（`file` 確認類型）與步驟 3（實機啟動驗證）。

## 識別訊號表

| 訊號 | 判讀 |
|------|------|
| `argument X cannot be used multiple times` | wrapper 已注入 X，args 不應再給 |
| `unexpected argument Y` | Y 非合法子命令，或 wrapper 不轉發 Y |
| command 路徑指向 `.js` / `.sh` / `.py`，shebang 非 binary | 是 wrapper，需讀轉發邏輯 |

## 與其他規則 / PC 的關係

| 對象 | 關係 |
|------|------|
| quality-baseline.md「測試綠燈不等於 Runtime 正確」 | 本 PC 是其在「設定診斷」面向的延伸——`--help` 推斷不等於 runtime 啟動成功 |
| PC-159（安裝指令 fresh shell 驗證） | 同源——靜態推斷 / 文件不足採信，需實機驗證 |
| PC-165（false positive fix chain） | 同類「表層證據綠燈但根本未生效」 |

## 案例文件來源

`.mcp.json` codegraph MCP server 設定修復（2026-06-03，commit `61b0c006`）。診斷者第一版誤判 args、實機啟動暴露錯誤、讀 wrapper 原始碼修正的完整過程。
