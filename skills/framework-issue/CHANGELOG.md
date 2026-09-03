# framework-issue 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.4.0 — `section_comment.py` 六個子命令（init/update/observe/show/check/dedup）落地，取代 1.3.0 記載的介面規格。init 前查重必填 `--dedup-keywords`（跨 comment 分佈詞彙以 token 聯集查詢後回顯命中清單，人工標註重複／切分／引用關係，不自動判定不阻擋）；`--sections-file` 為 JSON 陣列 `[{"name": "區段名", "content": "內容"}, ...]`；update 以 comment id 精準 PATCH 單一區段；observe 附加觀測 comment 不需 owner；show 依區段標記區分「當前結論區段」與「觀測流」；check 唯讀輸出當前結論時效（主警訊）、comment 數閾值（輔助）、body 區段索引一致性三項警訊，exit 0 不阻擋；dedup 唯讀，共用 init 查重邏輯供獨立核對關鍵字涵蓋範圍

**Version**: 1.3.0 — 新增「Comment-as-Section 協作協定」章節：五操作（init/update/observe/show/check）用法、區段與觀測標記格式、init 前查重三種關係處置（併入／建新張互標分工／單向指向）、check 三項警訊、增長與 close 語意。與既有 fix-matrix 命令集（軸 C/D）並存，不取代。命令實作另行進行中，本章節為介面規格

**Version**: 1.2.0 — 新增「框架問題升級流程」章節：介入判斷、兩條路徑（延後接手 / 當下接手）、issue 關閉協議（sync-push → fix-version → close）、回報前查重 SOP（承接既有命令實作）

**Version**: 1.1.0 — 新增 fix-version（軸 D：修復版本號註記）與 close（包裝 `gh issue close`，前置檢查版本號註記存在）命令
