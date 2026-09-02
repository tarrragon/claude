# spec 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.6.2 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 1.6.1
**Last Updated**: 2026-08-08
**Source**: Phase 3b context 耗盡案例 → 需求完善度品質閘門
**Changes**: v1.6.1 - 審查修正兩處：(1) 生命週期段對 tdd skill 的引用改為條件式選讀——原寫法是跨 skill 硬路徑、單獨安裝 spec 的專案是死鏈、且抵觸本檔「/spec 不呼叫 /tdd、兩者完全解耦」的定位宣告；段內原則已自足、引用降為「同專案若也安裝 tdd 時的延伸閱讀」。(2) 「維度 4 skipped」示例塊的語言標從閉合 fence 移回開啟 fence（v1.6.0 誤打在閉合線上）。v1.6.0 - /spec init 輸出節新增 feature-spec 生命週期（scaffold 文件）：消費者是 Phase 2 測試設計、Phase 3 綠燈後權威轉移到測試與程式碼、文件標記 `status: archived (superseded by tests)`；引用 domain spec 用指涉不整段複寫、只有本 ticket 的增量決策是固有資訊。動機：feature-spec 原無生命週期定義、實作完成後長得像權威規格、實際從 Phase 3 起每個實作決策都讓它漂移——依《人月神話》多文件必漂移論點與文件分級原則（tdd skill `references/document-coherence.md`）明示降級、消滅同步期待。v1.5.0 - 定位與分工節新增「適用範圍限制（防誤用聲明）」：`subdomain: data-contract` 文件（A/B 兩區結構）不適用 `/spec validate`，機械驗證改由 `doc validate` 承接 落地前人工檢查）；維度 4 補降級條款：CLAUDE.md 無「教學模組對應表」時跳過並標註「維度 4 skipped：無教學模組對應表」，不視為失敗，動機：/spec validate 對 SPEC-002 誤報結構失敗 + flutter_balance 專案無教學模組對應表）。v1.4.0 - Layer 1 新增 domain-map 覆蓋檢核（`scripts/check_domain_coverage.py` + `tests/test_check_domain_coverage.py`，11 測試綠）：驗證 domain map 覆蓋 spec 全部 FR，FR token 支援逗號續列/範圍展開，落地 ANA domain 規劃整合；動機 domain map 曾漏 FR-25/26）。v1.3.0 - Layer 1 新增 API surface 完整性檢查（Full only），`scripts/check_api_surface.py` 機械掃描 FR 段落 API 行為訊號與 endpoint 路徑定義的對應性，動機：SPEC-014 FR-04 analytics endpoint 路徑缺口）。v1.2.0 - 新增維度 4 教學一致性（Full 模式），比對 spec 設計決策與教學對應模組（防護教學×實作偏移）。v1.1.0 - 三人組共識簡化：刪除核心抽象/反向提問策略、原維度 4-7 降級為提示、精簡迭代機制、init 條件簡化為 2 個
