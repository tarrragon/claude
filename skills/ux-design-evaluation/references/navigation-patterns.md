# 導航模式：畫面之間怎麼跳、back 回到哪

本 reference 為「設計或審查畫面間導航」情境。

適用：選擇 app 的導航架構（堆疊 / tab / drawer）；決定單次導航用 go 還是 push；使用者按 back 的行為不符預期（直接離開 app、回到不該回的畫面）；deep link 設計；跨平台 app 的導航慣例取捨。
不適用：單一畫面內部的狀態轉換（狀態矩陣範疇）；導航後畫面的載入回饋（互動回饋範疇）。

> **自包含聲明**：閱讀本文件不需要先讀其他 reference。

---

## 核心概念

導航設計的核心提問是使用者的心理模型：**使用者按 back 時，期望回到哪裡？** 每種導航模式和每個導航操作都對應一種期望；實作選擇偏離期望時，使用者會迷路（回到不該回的畫面）或意外離開 app（堆疊已空）。

## 導航模式分類

| 模式               | 心理模型               | 適用                                            | 限制                                 |
| ------------------ | ---------------------- | ----------------------------------------------- | ------------------------------------ |
| Push/pop stack     | 深入 → 返回的線性路徑  | 層級式資訊（列表 → 詳細 → 編輯）、步驟式流程    | 只有深度一條軸、無法橫向切換平行功能 |
| Declarative router | URL 表示畫面狀態       | 需要 deep link、URL 驅動、複雜條件式導航        | 需要集中管理路由定義                 |
| Tab bar            | 平行功能橫向切換       | 3-5 個平行主功能、切換頻繁；每個 tab 是獨立堆疊 | 超過 5 個 tab 過度擁擠               |
| Drawer             | 隱藏的選單、打開才看到 | 頂層功能超過 5 個、切換頻率低、放帳號設定       | 可見性低 — 核心功能不該藏在 drawer   |

多數 app 組合使用：tab bar 做頂層橫向、每個 tab 內部 push/pop 縱向深入、drawer 放次要功能。組合時 back 行為要一致 — 在 tab 內第三層按 back 回第二層（堆疊行為）、而非切到上一個 tab。

## go vs push vs pushReplacement 語意

以 declarative router 的三種導航操作為例（名稱取自 Flutter GoRouter、語意跨框架通用）：

| 方法              | 堆疊行為     | 按 back 回到   | 使用者意圖                 |
| ----------------- | ------------ | -------------- | -------------------------- |
| `go(path)`        | 替換整個堆疊 | 無（離開 app） | 切換到另一個工作區         |
| `push(path)`      | 推入堆疊頂端 | 前一個畫面     | 暫時離開，做完回來         |
| `pushReplacement` | 替換堆疊頂端 | 更早的畫面     | 流程中的下一步（不可回退） |

**go — 切換工作區**：登入成功後到首頁、登出後到登入畫面、onboarding 完成到主畫面 — 共通點是使用者不應該按 back 回到之前的畫面。

**push — 暫時離開做完回來**：列表到詳細頁、首頁到設定頁、主畫面到一次性配對流程。最常用 — 多數導航都是這個模式。

**pushReplacement — 流程中前進**：步驟式流程（步驟 1 → 2 → 3，在步驟 3 按 back 回到流程開始前、不回步驟 2）、結果頁替換條件頁。語意是「這一步完成後使用者不需要回到這裡」。

**決策方法**：對每個導航操作問「使用者按 back 期望回哪裡」— 回前一個畫面 → push；離開 app 或回根畫面 → go；跳過當前畫面回更早 → pushReplacement。這個決策在 UX 設計階段做、記錄在畫面狀態矩陣的退出路徑欄，實作時對照選擇。

**常見誤用**：

- 該 push 用了 go：「首頁 → 配對畫面」用 go，配對完按 back 直接離開 app 而非回首頁。實例：一個 app 補配對入口時刻意選 `push('/enrollment')` 而非 `go`，讓使用者配對完成後能按 back 回首頁 — 配對是「暫時去做一件事」、不是切換工作區。
- 該 go 用了 push：「登入 → 首頁」用 push，使用者在首頁按 back 回到登入畫面 — 已登入的使用者不該再看到登入頁。
- 該 pushReplacement 用了 push：不可逆流程（已提交資料）按 back 回到上一步、但回去沒有意義。

## iOS HIG vs Material Design 慣例差異

跨平台 app 需要決定遵循哪套慣例。主要差異：

| 面向  | iOS                                           | Android / Material                                       |
| ----- | --------------------------------------------- | -------------------------------------------------------- |
| Back  | 無系統 back 鍵；導航列左上按鈕 + 左緣右滑手勢 | 系統 back 鍵（可被 app 覆寫：離開確認、放棄編輯確認）    |
| Tab   | 固定底部、永遠可見                            | 底部為主、另支援 app bar 下方的 top tabs（同類內容視角） |
| Modal | 底部滑上的 sheet、下滑 dismiss                | bottom sheet 與 dialog 為主、full-screen dialog 左上關閉 |

選擇策略：

| 策略                 | 適合                      | 代價                   |
| -------------------- | ------------------------- | ---------------------- |
| 統一用 Material      | Android 為主、快速開發    | iOS 體驗不原生         |
| 統一用 iOS HIG       | iOS 為主                  | Android 體驗不原生     |
| 各平台各自慣例       | 重視兩平台原生體驗        | 開發測試成本翻倍       |
| 共用核心、差異點適配 | 多數跨平台 app 的實際選擇 | 需判斷哪些差異值得適配 |

「共用核心、差異點適配」的常見切法：底部 tab bar、push/pop 導航兩平台一致；back 手勢（iOS edge swipe + Android 系統鍵都要支援）、modal 呈現按平台適配。適配與否的判準：系統行為類差異（back 手勢、系統鍵、modal dismiss 手勢）必適配 — 違反會直接打破使用者的肌肉記憶；視覺風格類差異（轉場動畫、圖示風格）可不適配 — 適配成本高於體驗增益時保持統一。

## Deep link

Deep link 讓外部來源（網頁連結、推播、其他 app）直接導航到特定畫面。三個設計問題：

**機制選擇**：

- Custom URL scheme（`myapp://`）：無 ownership 驗證（任何 app 可註冊同 scheme）、只在已安裝時有效、不適合 web 分享。
- Universal Link（iOS）/ App Link（Android）：標準 HTTPS URL + domain ownership 驗證（`.well-known` 檔案），未安裝時 fallback 到網頁 — 對外分享場景的正解。
- Deferred deep link：點擊時未安裝 → 引導安裝 → 首次開啟導航到目標。需要第三方服務或自建參數傳遞。

**URL 結構**：和 router 的路由定義一致（URL path 即 route path）、query parameters 傳畫面資料。參數避免敏感資訊 — URL 會被系統日誌、分析工具、中間節點記錄。

頁面資訊不一定在 path — hash-based SPA 的路由在 fragment（`/#/library`）、pathname 永遠是 `/`，只讀 pathname 的辨識邏輯會把所有頁面靜默塌縮成根路徑。自家 app 用哪套慣例由 router 決定；讀取別人的 URL 時（browser extension 讀宿主頁面、工具讀目標站），對方的路由形態是輸入規格 — 辨識邏輯要涵蓋 path-based 與 hash-based 兩套，取完整路由用 pathname + hash 組合（組合前確認 fragment 承載的是路由還是頁內錨點 — path-based 站的 `#section` 是錨點、不是頁面）。

**堆疊重建**：從 deep link 直接進入內頁時堆疊裡沒有首頁，按 back 回首頁還是離開 app？目標畫面是日常使用的一部分 → 重建完整堆疊（back 回到 app 正常入口）；一次性操作（掃碼 → 顯示結果 → 離開）→ 只放目標畫面。

**測試項目**：每個路由的 deep link 能打開、參數正確傳遞、app 在前景 / 背景 / 未啟動三種狀態都能處理、無效 URL 有 fallback（導首頁或錯誤頁）、domain verification 正確。

## 檢查清單

- [ ] 每個導航操作對照過「按 back 期望回哪裡」選擇 go / push / pushReplacement？
- [ ] 登入 / 登出 / onboarding 完成用 go（清堆疊），暫時性任務用 push？
- [ ] Tab 數量 ≤ 5、核心功能不藏在 drawer？
- [ ] 組合導航下 back 行為一致（tab 內 back 走堆疊、不切 tab）？
- [ ] 跨平台策略明確（統一 / 各自 / 核心共用），back 手勢兩平台都支援？
- [ ] 對外分享的 deep link 用有 ownership 驗證的機制？
- [ ] Deep link 的堆疊重建策略明確、無效 URL 有 fallback？
- [ ] Deep link 在 app 前景 / 背景 / 未啟動三態都測過？
- [ ] 依 URL 辨識頁面的邏輯涵蓋 hash-based SPA（不只讀 pathname）？

## 參考來源

- Apple HIG — Tab Bars / Navigation（tab 上限、back 手勢慣例）
- Material Design — Navigation bar / Navigation drawer（3-5 個目的地建議、系統 back 行為）
