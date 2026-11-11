---
id: TEST-LLM-003
title: "在 POSIX 主機上以反斜線字串模擬 Windows 路徑，驗證只涵蓋字串層，下游以 \"/\" 比對的判定在 Windows 上靜默放行"
severity: high
status: active
related:
 - TEST-LLM-002
---

# TEST-LLM-003: 在 POSIX 主機上以反斜線字串模擬 Windows 路徑，驗證只涵蓋字串層，下游以 "/" 比對的判定在 Windows 上靜默放行

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | test |
| 來源版本 | 3.2.1 |
| 風險等級 | 高 |
| 首次觀察 | 2026-11-11 |

**判準**：驗證路徑處理的跨平台行為時，要換掉的是被測模組使用的 `os.path` 實作（ntpath），不是只把輸入字串改成反斜線。

## 症狀

- 修正 Windows 路徑問題後，在 macOS／Linux 上以反斜線字串（如 `D:\side\termchat`）實測：不崩潰，判定看似正確，測試全綠。
- 實際在 Windows 上，守衛對範圍內的寫入放行；放行與「輸入本來就合法」在輸出上同形，沒有任何訊號。

## 根因

- POSIX 主機上的 `os.path` 是 posixpath。它把反斜線當成檔名的一般字元：`realpath` 把 `D:\x` 當成相對檔名接到 cwd 後面，`dirname`／`join` 也不在反斜線處切分。
- 所以以反斜線字串餵入的實測，只驗證了「字串替換不出錯」這一層。路徑經 `realpath` 之後，在 POSIX 上仍是正斜線前綴的形式，下游 `startswith(root + "/")`、`split("/")` 照常命中。
- 在 Windows 上，`os.path` 是 ntpath，`realpath`、`dirname` 回傳反斜線；同一批下游比對全數不命中，判定落到「範圍外」而放行（fail-open）。
- 驗證環境與目標環境的差異不在輸入，而在被測程式自己呼叫的路徑函式；只改輸入無法重現。

## 解決方案

1. 在測試中把被測模組的 `os` 換成代理物件：`path` 指向 ntpath（逐一複製函式到 SimpleNamespace），其餘屬性轉交真正的 `os`。
2. `exists`／`isdir` 改為假實作，以一組 Windows 形式的路徑（如 `C:\proj\.git`）模擬檔案系統。
3. 先跑紅燈：確認範圍內寫入在修正前被判為放行。
4. 修正：在判定鏈的路徑來源（`realpath`、`dirname` 的回傳值）統一換算為正斜線，並統一磁碟機代號大小寫；POSIX 上換算函式原樣回傳。
5. 綠燈須包含正向對照：該擋的 Windows 路徑確實被擋，範圍外路徑仍放行。

## 預防措施

- 審查跨平台路徑修正時，問一句「這次實測用的是哪一個 `os.path`？」答案是主機原生的，就不算驗證過目標平台。
- 路徑判定鏈只在入口處換算一次分隔符；下游所有比對都假設已換算，避免逐點修補。
- 守衛類程式的 Windows 測試要附正向對照（`test-assertion-design` E2）：修正後的失效方向是放行，只測「不崩潰」分辨不出守衛是否還在工作。

## 案例

- 2026-11-11，Windows 路徑使兩支 PreToolUse hook 失效的修正（framework issue #132）：`bash-write-boundary-guard` 第一輪只修 `re.sub` 替換值，在 macOS 以反斜線專案根實測通過；協調方以 Windows 語意指出 `_relative_to_roots` 放行，第二輪以 ntpath 測試重現後修正。
