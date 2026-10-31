---
id: TEST-GPD-1008
title: "integration_test 的 App 進入 hidden 時 framesEnabled 為 false，pumpAndSettle 一次 pump 即返回使正向對照假綠，未受保護的 pump 則卡到案例逾時"
severity: medium
related:
 - PC-168
---

# TEST-GPD-1008: integration_test 的 App 進入 hidden 時 framesEnabled 為 false，pumpAndSettle 一次 pump 即返回使正向對照假綠，未受保護的 pump 則卡到案例逾時

## 基本資訊

| 項目 | 值 |
|------|-----|
| 分類 | test |
| 來源版本 | 0.5.0 |
| 風險等級 | 中 |
| 首次觀察 | 2026-10-31 |

## 症狀

Flutter 桌面 App 的 integration_test 在合併閘門偶發紅燈，本機單跑取樣全綠。紅燈有兩種形態，同一套件內位置不固定：

1. **正向對照假綠（守衛失效方向為放行）**：一則「永不收斂的畫面必須在逾時內失敗」的對照測試，掛上無限進度動畫後呼叫帶逾時的 settle helper，預期拋錯。紅燈時 helper 不到 1 秒正常返回，斷言得 `Actual <null>`。正常時約 2 秒內逾時拋錯。
2. **等幀卡住**：某個案例停在 `pumpWidget` 或 `pump`，直到案例的總逾時（例如 20 秒）才判紅，訊息只有 `Test timed out after 20 seconds`，不含步驟名。

`Failed to foreground app` 在綠燈與紅燈的 log 都會出現，不能用來區分。負載、swap、記憶體壓力在紅綠兩組沒有差異。

## 根因

**macOS 會在測試途中把 App lifecycle 送到 hidden**（前面先有 inactive，相隔數十毫秒）。`SchedulerBinding` 在 hidden／paused／detached 時把 `framesEnabled` 設為 false；inactive 與 resumed 時仍為 true。所以「App 不在前景」（inactive）本身不會出事，必須是 hidden。

hidden 之後分兩條路徑：

- **引擎還送來一幀**：`LiveTestWidgetsFlutterBinding.handleDrawFrame` 在略過非預期的幀後，直接呼叫 `platformDispatcher.scheduleFrame()`，不檢查 `framesEnabled`，所以 pump 仍可能等到一幀。這一幀內動畫 ticker 要重排下一幀，`scheduleFrame` 因 `!framesEnabled` 直接 return，不設 `hasScheduledFrame`。`pumpAndSettle` 的迴圈條件是 `while (binding.hasScheduledFrame)`，因此只 pump 一次就判定「已靜止」並正常返回。
- **引擎不再送幀**：pump 等的幀永遠不來，卡到外層逾時。

test binding 在每個案例開始時 `resetInternalState`，把 `framesEnabled` 重設為 true。所以 hidden 只影響當下那個案例：落在案例之間就無害，落在案例正在等幀時才會紅。這就是位置不固定、取樣難重現的原因。

## 解決方案

1. **settle helper 返回後檢查前提**：`pumpAndSettle` 正常返回後，若 `tester.binding.framesEnabled` 為 false，拋出指名步驟的 TestFailure，訊息帶固定字串（例如 `framesEnabled=false`），讓閘門可以辨識並歸類為已知 flaky。「已靜止」只有在幀能被排程時才有意義。
2. **所有 pump 都帶步驟逾時**：`pumpWidget`／`pump` 包一層 `Future.timeout` 並指名步驟，讓等幀卡住能說出卡在哪一步，而不是等案例的總逾時。
3. **消除根源**：在 integration binding 初始化時註冊 lifecycle observer，收到 hidden（或 paused）時依序送 inactive、resumed，把 lifecycle 拉回 resumed，並提供可關閉的開關，供需要測 lifecycle 行為的案例關掉。代價是測試環境的 lifecycle 序列與真實 App 不同：App 端反應 resumed 的邏輯（撤除提示、顯示通知等）可能在案例中途被觸發。
   - 「只強制送幀、lifecycle 不動」的做法實測不可行，有兩個原因：
     - `flutter test` 在呼叫測試檔的 `main()` 之前就已初始化 `IntegrationTestWidgetsFlutterBinding`，無法改用覆寫 `scheduleFrame` 的子類，建構時會觸發 `Binding is already initialized` 斷言
     - 在 observer 裡呼叫一次 `scheduleForcedFrame` 不夠，之後每次 pump 仍走 `scheduleFrame`，照樣被 `framesEnabled` 擋下

## 預防措施

- 寫依賴 `pumpAndSettle` 判定的正向對照（E2 型）時，同時寫一個「無幀可排」的對照：在 flutter_tester 下用 `binding.handleAppLifecycleStateChanged` 注入 inactive→hidden，斷言 helper 仍然失敗。只用正常 lifecycle 跑，測不出守衛在 hidden 時放行。
- 判讀 integration flaky 時，在入口 `main()` 註冊 `WidgetsBindingObserver` 記錄 lifecycle 轉換與時間戳。每個案例開頭讀到的 `lifecycleState` 會被重設成 null，不能當成當下狀態，只能用轉換事件判讀。

## 驗證方式（本次）

- flutter_tester 下注入 lifecycle，每種變體 N=5：不注入、inactive、hidden 後回到 resumed 皆約 2 秒拋錯；inactive→hidden 5/5 在約 108ms 正常返回（一次 pump 加一幀）。套用解決方案 1 後，該變體 5/5 改為指名失敗，其他變體不變。
- macOS integration 照閘門順序取樣 5 輪：hidden 出現 3 次，只有 1 次落在案例等幀中而紅燈（等幀卡住形態），另外 2 次落在案例之間或非等幀階段，綠燈。
