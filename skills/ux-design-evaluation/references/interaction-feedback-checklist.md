# 互動回饋反模式速查、檢查清單、參考來源

本 reference 為「快速核對互動回饋設計是否有已知缺口」情境，供三份互動回饋內容檔共用查表。原內嵌於 `interaction-feedback.md`，因補齊範例後超出體量門檻獨立為本檔——反模式速查與檢查清單本身橫跨三份內容檔的主題，拆列或複製會讓兩張表各自漂移、讀者也不知道該開哪一檔查，因此整份移入本檔、不拆列、不複製（同組四檔，逐檔互指）：

| 檔案 | 內容 |
| --- | --- |
| `interaction-feedback.md`（入口） | 核心原則／三層回饋模型／按鈕級回饋（按鈕流程與六種按鈕狀態） |
| `interaction-feedback-waiting-and-notification.md` | 時間門檻與回饋策略／畫面級回饋／Spinner vs Skeleton／結果通知的形式選擇 |
| `interaction-feedback-component-semantics.md` | 元件語意與版面檢查（切換標籤／可點性／選中態／溢出／版面保障） |
| `interaction-feedback-checklist.md`（本檔） | 反模式速查／檢查清單／參考來源 |

適用：提交前快速核對按鈕、等待、通知、元件語意四類是否有已知反模式；作為三份內容檔的共用附錄查表。
不適用：判斷標準本身的設計依據與範例（各判斷標準的完整說明在對應內容檔，本檔只列查表結論）。

> **自包含聲明**：本檔的兩張表可獨立查閱，不需要先讀其他三檔；表中每一行的判斷標準來源見對應內容檔（下方表格已依主題分段落）。

---

## 反模式速查

| 反模式                           | 使用者後果                     | 修正                                   |
| -------------------------------- | ------------------------------ | --------------------------------------- |
| 按鈕無視覺回饋                   | 重複點擊、重複觸發 callback    | 補第一層點擊確認                       |
| 非同步不禁用按鈕                 | 重複提交（重複扣款 / 寫入）    | loading 自動帶 disabled + 後端冪等     |
| loading 結束不恢復按鈕           | 以為介面當掉                   | 完成 / 失敗 / 逾時三個出口都恢復       |
| 只有 loading 無結果通知          | 不確定是否成功                 | 補第三層                               |
| 同步按鈕無防連點                 | 導航堆疊混亂（push 多次）      | leading debounce 或導航鎖              |
| 每個操作都全螢幕 loading         | 打斷心流                       | 指示只覆蓋被等待的區域                 |
| spinner 閃爍                     | 視覺雜訊                       | 延遲顯示 + 最短顯示時間                |
| 假進度 / 0% 跳 100%              | 信任崩壞                       | 步驟計數或 indeterminate 動畫誠實表達  |
| 畫面中間狀態無退出路徑           | 卡在 connecting、只能殺 app    | 每個中間狀態補退出（取消 / 返回）      |
| 錯誤狀態只有重連沒有返回         | 鎖在錯誤迴圈                   | 重試 + 返回兩條路                      |
| 所有通知都用 Dialog              | 訓練出「不讀直接按確定」       | 依二軸降級                             |
| 需要操作的通知用 SnackBar        | 沒讀完就消失                   | 改 Dialog 或 action 可復得             |
| 持續狀態（離線）用 SnackBar      | 消失後使用者忘記、後續操作困惑 | 改 Banner                              |
| 成功誤報失敗（通知鏈路錯誤）     | 重做操作、資料重複、信任崩壞   | 端對端驗證 + 通道上明確宣告回應權      |
| 完成宣告只憑停滯訊號             | 帶著殘缺資料離開而不自知       | 窮盡證據、或降級為部分結果表達         |
| 切換鈕的名詞標籤被讀成現態       | 誤判目前所在模式               | 拆成狀態顯示 + 動作按鈕、或 switch     |
| 狀態圖示與動作按鈕同形混排       | 點指示沒反應、被讀成壞掉       | 指示改非按鈕形態、移出動作列           |
| 關鍵回饋文字被版面壓成省略號     | 回饋存在、使用者拿到零資訊     | 最小寬度保障、縮格式優於 ellipsis      |
| 佔位 handler 上線（toast / log） | 可點的假按鈕、被讀成壞掉       | 隱藏或 disabled + 說明、release 前掃描 |

前 8 行對應 `interaction-feedback.md`〈按鈕級回饋〉與 `interaction-feedback-waiting-and-notification.md`〈時間門檻與回饋策略〉〈Spinner vs Skeleton〉；中段 6 行對應 `interaction-feedback-waiting-and-notification.md`〈畫面級回饋〉〈結果通知的形式選擇〉；末 4 行對應 `interaction-feedback-component-semantics.md`〈八項判斷標準〉。

## 檢查清單

按鈕級（見 `interaction-feedback.md`）：

- [ ] 點擊有視覺回饋（100ms 內）？
- [ ] 非同步：loading + disabled + 完成恢復 + timeout？
- [ ] 結果有通知（成功 / 失敗 / 空 / 部分成功）？
- [ ] 同步按鈕有 leading-edge 防連點？

畫面級（見 `interaction-feedback-waiting-and-notification.md`）：

- [ ] 每個中間狀態能被區辨、有退出路徑？
- [ ] 等待狀態可取消、有 timeout 兜底？
- [ ] 錯誤 / 中斷同時提供重試和返回？

等待與通知（見 `interaction-feedback-waiting-and-notification.md`）：

- [ ] 對表用 p90 / p95 而非平均延遲？
- [ ] spinner 有延遲顯示 + 最短顯示時間？
- [ ] spinner vs skeleton 按形狀 > 觸發 > 時長裁決？
- [ ] 通知形式對照二軸 + 操作頻率？
- [ ] 批次操作結果有彙整、無 SnackBar 成串 / Dialog 堆疊？
- [ ] 跨 context（extension / 多 process）的結果通知有端對端驗證？
- [ ] 批次 / 遍歷操作的完成宣告有窮盡證據（總數對照 / 終止標記）？

語意與版面（見 `interaction-feedback-component-semantics.md`）：

- [ ] 切換型元件的標籤是動作語意（或已依值數與結構連動依序判定拆成狀態顯示 + 動作按鈕、或改用 switch）？
- [ ] 非互動指示與動作按鈕形態可區分、圖示無撞名？
- [ ] Selected 態底色與文字色成對設計、對比達 WCAG AA？
- [ ] 水平溢出清單有捲動 affordance（或已消除溢出）？
- [ ] 關鍵狀態文字有版面保障（窄幕不被壓成省略號）？
- [ ] 版面擠壓的診斷分過層（換算錯 vs 分配錯）、沒把 sizing 套件當空間分配的保證、設計層空間競爭規格已路由至 `component-contract-design`〈空間不足策略〉欄？
- [ ] 靠顏色區分的語意，顏色之外另有訊號或文字？
- [ ] 無佔位 handler（dev toast / log-only）殘留（統一佔位標記 + release 前 grep 掃描）、未接線功能已隱藏或 disabled + 說明？

## 參考來源

- Nielsen Norman Group (1994) — 十大可用性啟發法（#1 系統狀態可見性）
- Doherty & Thadani (1982) — IBM 技術報告、400ms 生產力門檻
- Nielsen (1993) — Usability Engineering、100ms / 1s / 10s 三門檻
- Miller (1968)、Card, Moran & Newell (1983) — 感知門檻的認知心理學基礎
- Material Design 3 — Interaction States / Loading Indicator / Snackbar / Dialogs / Bottom Sheets
- Apple HIG — Feedback / Alerts / Action Sheets
- WCAG 2.1 — SC 2.4.7（焦點可見）、SC 2.2.1（自動消失內容可延長）
- Laws of UX（lawsofux.com）— Doherty Threshold 現代整理
