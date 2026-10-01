---
id: TEST-GPD-003
title: 以 monkeypatch 替換全域 time.sleep 作假時鐘，被 subprocess 的等待輪詢呼叫而使推進量不固定
severity: 中
---

# TEST-GPD-003: 以 monkeypatch 替換全域 time.sleep 作假時鐘，被 subprocess 的等待輪詢呼叫而使推進量不固定

## 基本資訊

| 項目 | 內容 |
|------|------|
| 風險等級 | 中 |
| 分類 | test |
| 來源版本 | 0.4.1 |
| 來源事件 | 提交重試預算改用假時鐘後，新測試整檔連跑 11 次失敗 5 次 |
| 首次觀測 | 2026-10-01 |

## 症狀

為了讓重試預算的判定不受機器負載影響，測試以假時鐘取代真實等待：`monkeypatch.setattr(module.time, "sleep", fake_sleep)`，`fake_sleep` 推進假時鐘而不真的等待。單獨執行該測試每次通過，整檔一起跑卻間歇失敗，斷言的重試次數時多時少（實例：預期較寬鬆的設定應重試 5 次，實際只有 3 次）。失敗與負載無關。

## 根因

1. **`module.time` 就是全域的 `time` 模組**。`monkeypatch.setattr(module.time, "sleep", ...)` 改寫的是 `time.sleep` 本身，不是該模組自己的等待點；同一程序內所有呼叫 `time.sleep` 的程式碼都被換掉。
2. **`subprocess` 在等待子程序時會呼叫 `time.sleep`**。帶 `timeout` 的 `Popen.wait`（`_wait`）以 `time.sleep` 輪詢子程序狀態，間隔從 0.0005 秒起逐步加長。被測程式碼每次呼叫外部命令（例如 git）都會走到這段輪詢。
3. **兩者疊加，假時鐘的推進量取決於子程序實際跑多久**。輪詢的 sleep 不再真的睡，變成忙迴圈，每一圈都推進假時鐘；子程序跑得越久、圈數越多，假時鐘一次可跳過數十到上百秒，提前觸發預算上限。本來為了「與負載無關」而引入的假時鐘，反而把子程序耗時這個非決定因素帶了回來。

## 解決方案

1. 在被測模組建立模組層的等待接縫（例如 `_sleep = time.sleep`），產品程式碼的退避等待一律呼叫 `_sleep`。
2. 測試只替換該接縫：`monkeypatch.setattr(module, "_sleep", fake_sleep)`，不碰全域 `time.sleep`。
3. 斷言精確的重試次數，並保留一個正向對照：改回替換全域 `time.sleep` 時，推進量確實不固定（證明測試能分辨兩者）。

## 預防措施

| 層級 | 措施 |
|------|------|
| 撰寫測試 | 假時鐘只替換被測模組自己的接縫；看到 `monkeypatch.setattr(<mod>.time, "sleep", ...)` 或 `setattr(time, "sleep", ...)` 即視為改寫全域 |
| 程式設計 | 有退避或重試的程式碼，等待點經模組層接縫呼叫，讓測試有不波及標準庫的替換點 |
| 驗收 | 用假時鐘的測試須整檔連跑 N>=10，不只單獨跑該項；單獨通過而整檔間歇失敗即為本模式的訊號 |

## 關聯

- `.claude/rules/core/test-assertion-design-rules.md` D 系列（斷言結果不得依賴程式以外的可變因素）：本模式是「為了消除可變因素而引入的替身，反而接上另一個可變因素」
