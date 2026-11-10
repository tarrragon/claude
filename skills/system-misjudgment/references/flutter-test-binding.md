# Flutter 測試 binding（widget test／integration_test 的幀與時鐘）

測試設計規範見 `dart-test-async-guardian` skill；本檔只收「讀測試結果」的誤判。

## FTB-1 on-device 測試 finder 找不到元件，被讀成元件改名或 finder 過時

| 欄位 | 內容 |
|------|------|
| 症狀 | integration_test（on-device）首次 `pumpAndSettle` 後，finder 找不到目標元件（`findsNothing`、讀容器時 `StateError: No element`）；同一測試不改程式碼連跑，時紅時綠 |
| 常見誤判 | 元件改名或 finder 過時；`pumpAndSettle` 返回就代表畫面已穩定 |
| 實際機制 | App 等待真實平台 I/O（資料庫、檔案、平台 channel）時沒有排程中的幀，`pumpAndSettle` 立即返回，畫面仍在 loading；真實 I/O 不受測試 binding 的 fake-async 時鐘驅動，多 pump 也不會完成 |
| 檢查方法 | 在失敗的 finder 前加一行 `debugPrint('FTB1 loading=${find.byType(<Loading 元件>).evaluate().length} target=${find.byType(<目標元件>).evaluate().length}');`，連跑 5 次：`for i in 1 2 3 4 5; do flutter test integration_test/<檔名>.dart -d <裝置> 2>&1 \| grep -E "FTB1\|passed\|failed"; done`；另以 `grep -rn "class <目標元件>" lib/` 確認類別仍存在 |
| 正向對照 | 在首次 `pumpAndSettle` 後加有界輪詢（`tester.runAsync` 讓出真實時間再 `pumpAndSettle`，直到目標元件出現或達上限），同樣連跑 5 次：每次都應印出 `target=1`、全綠 |
| 判讀標準 | 紅燈那幾次印出 `loading>0 target=0`，且類別仍在 `lib/` → I/O 尚未完成，不是改名；類別已不在 `lib/` → 才是 finder 過時。取樣少於 5 次的綠燈不採計 |
| 來源 | `TEST-LLM-001`（tarrragon/claude#126）；同類機制對照見 `TEST-GPD-1000`、`TEST-GPD-1008` |
