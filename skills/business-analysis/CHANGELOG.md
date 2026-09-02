# business-analysis 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.4.1 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 1.4.0 — value-investing-assessment 補 steelman 審查修正：Three-Gate 的 veto 範圍明確化（否決的是複利機器分類、非一切學派下的可投資性、前向引用 School Routing）；School Routing 補殘餘桶的顯式標籤（轉機投機 / 治理陷阱排除）——未定義的「皆非」會把觀察名單、投機、永久排除三種不同狀態壓平
**Version**: 1.3.1 — value-investing-assessment 的 Holding-company numerator bullet 拆為兩條（numerator discipline / holding-layer dilution）、對齊 Capital Efficiency Screen 清單的顆粒度（cadence 審查 finding）
**Version**: 1.4.0 — 從八方雲集 / 揚秦加盟餐飲比較的實作提煉「value-chain span 解釋毛利、且限制可比性」概念：value-chain-analysis reference 新增 Value-Chain Span 段（全製程 / 轉售 / 外部代工三 span × 毛利涵蓋範圍、36% vs 27% 的 9pp 差是結構不是效率、不同 span 的毛利不可當效率直接比較的 guardrail、跟 transfer-pricing 紅旗的正反面互補）；Key Analytical Patterns 表加第 9 個模式 Value-chain span；Step 3 peer group 篩選加 value-chain span 維度（全製程producer 與 reseller 不是 margin peer）。這是既有 line 「margin depends on processing depth」一句帶過的展開
**Version**: 1.3.0 — value-investing-assessment reference 補「當下判定」實測維度：控股公司 ROE 分子紀律（歸母淨利、EPS sanity check、控股層結構性稀釋——實測誤用讓品質閘門判定反轉）、估值帶 derating vs 便宜的判讀表（帶連年壓縮時帶下緣是新常態不是折價）、學派分流（複利機器 vs 資產折價特殊情境、無催化劑的折價論述是希望不是論述）、當下判定的翻轉條件必為輸出（價格觸發 + 結構觸發、待決二元事件先寫兩張劇本）；Output Addition 加第 5/6 項。從四大超商股權層 + 2026Q3 七標的當下判定的實作提煉
**Version**: 1.2.0 — 新增 `references/value-investing-assessment.md`：把「企業分析」與「投資分析」的邊界明確化（無估值帶與市值序列不可下投資結論）、三閘門篩選（護城河耐久性看衰退期定價權而非好年毛利率 / 管理層看資本配置紀錄而非敘事 / 安全邊際基於正常化盈餘與歷史估值帶百分位）、10 年 ROE + 杜邦拆解的資本效率篩選、台灣治理訊號（董監質押 / 關係人交易量級 / 經營權爭奪）、價值窗口四分類（受壓轉型 / 被擊垮 / 週期高點 / 結構遮蔽）、價值陷阱三型（護城河受損 / 治理失效 / 結構衰退）。從肉品油品零售 20+ 家公司分析的回顧性缺口盤點提煉
**Version**: 1.1.0 — Step 6 加入國際原物料供應鏈維度（進口依賴比、來源集中度、傳導路徑、採購策略矩陣）；value-chain-analysis reference 加入 Import Dependency Assessment 表、Transmission Path Mapping 五步驟、Procurement Strategy Matrix（含電子業對應欄）；分析模式速查表加第 8 個模式 Import dependency。從 procurement-planning 的 commodity-import-dependency 和 commodity-price-shock-response 兩篇新文章提煉
**Version**: 1.0.0 — Initial version extracted from 18-article business analysis teaching series built around a franchise breakfast store case study, expanded through real company analysis (八方雲集, 揚秦/麥味登, 卜蜂, 大成, 超秦) with prediction-validation cycles
