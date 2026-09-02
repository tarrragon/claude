# tdd 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.2.7 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 2.2.6 — 術語校正：判準全數改為判斷標準（動作修飾語縮為「X 標準」、狀態義改為「X 條件」）。判準的語域在哲學與教育評量、工程讀者解析不了——五份低階模型探針一致回報非通用

**Version**: 2.2.5 - `references/phase1-split-methodology.md` 檔尾的 `**Source**` 指向已併入本 skill 的 `tdd-phase1-split/SKILL.md`，該檔不再存在故被判為斷鏈。此為歷史遷移軌跡（記錄本文件的來源），加 `broken-link-exempt` marker 並在行內註明原檔已併入，保留可追溯性。
**Version**: 2.2.4 - 多輪審查鏈路實證修正：v2.2.3 宣稱的「Phase 0 讀取」在檔案層並不存在——覆寫是三處互相引用、零處有執行載體的宣稱、且新專案起手模式的 Phase 0 豁免讓它在 proposal 最完整的路徑上必然不發生（本 skill 自己的 document-coherence 所批評的「被期待卻沒有機制」形態）。修法：doc-handoff v1.1.2 補 Phase 0 映射列與豁免不豁免覆寫的規則、document-coherence v1.0.4 補執行點指涉與跨 skill 條件語。
**Version**: 2.2.3 - 「程度決策歸提案階段」對齊：document-coherence v1.0.3 分級表明示為預設值、proposal 有「文件維護到什麼程度」決策時以 proposal 覆寫（決策由 saas-tech-selection v1.1.0 的 reliability 訪談問出、經決策記錄流入 proposal 驗收條件、Phase 0 讀取）；doc-handoff v1.1.1 對 saas-tech-selection 的引用加條件語（未安裝非死鏈）。
**Version**: 2.2.2 - 多輪審查第二、三輪修正。phase2/rules v2.3.0：讀者分層指引與轉換條件的 DQ 範圍補上 Q12-Q14（原停在 Q7-Q11、執行者可合法跳過新組——雙處複製當天漂移的實證）、組 4 補恆觸發宣告與擴充指引註解、Q12 補防護型測試定義、防呆補 protocol integration 指涉、檔級版本記錄補上（原停在 2026-06-14）。document-coherence v1.0.2：測試權威兩個限定（現狀 vs 正確性、覆蓋範圍界線）、Phase 4 比對要落成腳本否則依分級降級、archive 前置確認（增量決策先回活載體）、scaffold 標記防護範圍宣告、表格 cell 收短與表下註、宣告本表自成權威以消滅跨 surface 無機制同步期待。test-naming-conventions：例句補批次合併情境（v2.2.1 漏報：該檔與 layered-test-strategy 在 2.2.1 批已各有 gloss 修正與死鏈移除、此處補記）。layered-test-strategy：「語意級 vs 回放級」對比前移、移除不存在的 `專案方法論目錄的 ` 死鏈。
**Version**: 2.2.1 - 多輪審查修正三處：(1) Q13 的 flaky 分類改回教材四類原名（計時依賴 / 環境差異 / 資源競爭 / 非確定性輸出）——v2.2.0 曾未標示地重切成三類、環境差異被誤併進外部服務、資源競爭無落點；計時依賴主策略同步改為事件驅動取代固定等待、clock 注入降為補充。(2) document-coherence v1.0.1：Spec/UC 與 domain-map 的機制欄改條件式——原寫法指名 spec skill 的工具、單獨安裝 tdd 時這兩格機制不存在、Spec/UC 靜默落入本文件自己定義的錯配格；活文件機制枚舉補 lint 與來源對齊。(3) 檢查清單第 12 項同步四類措辭。
**Version**: 2.2.0 - 測試設計理念對齊上游 testing 教材的現行水位。對照盤點發現本 skill 的測試 references 是 2026-06 從教材提煉的快照、之後教材長出的內容沒有跟上（快照漂移、正是 document-coherence 講的錯配）。四處補強：(1) phase2/rules.md 新增組 4「防護視角與訊號品質」（Q12 每條測試答「未來哪種改壞要被擋」、TDD 紅燈是破壞實測的制度化、綠燈後補的防護型測試要手動故意破壞驗一次；Q13 flaky 三源自查——計時 / 執行順序 / 外部服務、非確定約束不掛提交閘門；Q14 手寫測試資料是真實環境的乾淨子集、parser / 驗證類補錄製或生成資料）+ 檢查清單三項、phase2-test-design.md 以 blockquote 指涉不複寫；(2) test-naming-conventions v1.1.0 加「名稱承載意圖」（失敗輸出只給症狀、名稱回答為什麼這是刻意的、名稱失職時防護會被紅燈的人親手解除）與「名稱之外的測試文字」（reason / skip / 註解 / 分析詞彙的落點表）；(3) layered-test-strategy v1.1.0 加「分層之外的兩個補位形態」（stub 盲區與語意級假後端、characterization test）；(4) 已知議題記錄：phase2-test-design.md 與 phase2/rules.md 存在金字塔 / GWT / 場景設計的重複段落、屬雙活文件錯配、本次以指涉止血、結構收斂留待下輪。
**Version**: 2.1.0 - 新增 `references/document-coherence.md` 文件連貫性紀律 + 核心理念補「文件連貫性原則」。依《人月神話》多文件必漂移的論點對本 skill 文件鏈盤點出四個錯配（UC 場景複製進種子包與 feature-spec 形成四份行為敘述副本、traceability 的 covered 狀態是人工宣稱、feature-spec 無生命週期定義、邊界回補不及於已複製副本），落成三條紀律：文件分級（活文件要機制、scaffold 標消費時點、append-only 不回改）、資訊住址（每類資訊唯一權威載體、行為的權威載體是測試）、各 Phase 連貫性檢查點（Phase 4 用實際測試檔驗 traceability、feature-spec 標 archived、註解逐則過商業邏輯判斷標準）。doc-handoff v1.1.0 同步（種子包標記 scaffold 身分）。
**Version**: 2.0.0 - 全面重整：消滅孤立文件、統一 scripts/、集中 cases、子命令加入 Read 指示
**Specialization**: TDD 全流程指導（Phase 0-4）
