# ux-design-evaluation 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.4.2 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 1.4.1 — 術語校正：判準全數改為判斷標準（動作修飾語縮為「X 標準」、狀態義改為「X 條件」）。判準的語域在哲學與教育評量、工程讀者解析不了——五份低階模型探針一致回報非通用

**Version**: 1.4.0 — 三輪 agent 審查（compliance / cadence 冷讀對齊 / self-application steelman outbound）修正：宣告層與內容層對齊（description / Triggers / 路由表症狀欄補 v1.2-1.3 新增檢查的入口、「不涵蓋」聲明修正為視覺風格 — WCAG 對比屬檢查範圍、元件語意段主標去半套）；steelman 修正（WCAG AA 分字級 4.5:1 / 3:1、觸控底線標派系 44pt HIG / 48dp Material、選中態補主題成對機制條件、溢出手段補捲軸指示、toggle 消歧補動詞標籤選項、完成證據補 API cursor + 全量場景邊界、debounce 慣例值去門檻化、跨平台適配補系統行為 / 視覺風格判斷標準、navigation 補參考來源）；快速自檢 3-in-1 拆分、佔位掃描補操作提示
**Version**: 1.3.0 — 元件語意與版面檢查加第六項「sizing 套件不驗證空間分配」（換算工具在常數層、空間分配在 layout 協商層，兩層獨立；版面擠壓先分換算錯 vs 分配錯、引入套件時記錄它不保證的層）；檢查標題去計數化（五個檢查 → 元件語意與版面檢查）；檢查清單同步
**Version**: 1.2.0 — 從一次 mobile app 驗收的六個實際發現補「元件語意與版面」檢查層（互動回饋 reference 加五項：切換元件標籤的現態 / 動作歧義、非互動指示與動作按鈕同形、選中態底色文字色成對設計、水平溢出捲動 affordance、關鍵回饋文字版面保障；反模式表加四行含佔位 handler 掃描）；快速自檢同步擴充
**Version**: 1.1.0 — 從一個 Chrome extension 專案的實際事故補 web / 多 context 維度（原案例庫全為 mobile app、系統性缺這一面）：狀態矩陣加 initializing 狀態（查詢對象獨立生命週期）、互動回饋加結果通知鏈路前提與完成宣告窮盡證據、gate 加破壞性操作確認與 fail-safe 預設、錯誤恢復加行動層級對位、導航加 hash SPA 路由辨識；跨維度快速自檢同步擴充
**Version**: 1.0.0 — 從單一模組的簡略版（ux-interaction-feedback：按鈕級 + 畫面級回饋）擴充為全維度 UX 設計評估 skill：新增畫面狀態矩陣、gate fallback、輸入機制、錯誤恢復、導航模式五份 reference，互動回饋 reference 併入通知模式選擇與延遲分布判讀；建立四支柱與事前 / 事後兩條評估流程
