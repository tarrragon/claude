# error-pattern 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.6.0 — 步驟 8 補「順序要求（強制）」：欄位補齊須早於 sync（保守 upsert 使佔位符列無法事後更正）；建議程式碼片段改為先呼叫 `find_incomplete_new_rows` 把關；CLI `sync --write` 預設阻擋含缺漏欄位的新增列，逃生閥 `--allow-placeholder`，`--dry-run` 僅預警不阻擋
**Last Updated**: 2026-08-21

**Version**: 1.5.1 — 修正 1.5.0 新增段落的兩項失準：ARCH-001 錨點方向倒置（改引 15 檔分歧中 14 檔判定內文較準確的多數例，結論不變）；「不變式建立後新建檔案仍 100% 違規」改為實測值（現況違規率 40%、回溯建立時點 70%，兩種讀法皆非全數違規）。連帶調整資訊優先序：機械鏡射段由單一區塊拆為三個可掃讀單位並將限制提前至段首偽段標；增量問題移出三類分類清單改為清單後的範圍排除說明；適用範圍段首句補與前次覆核 381 檔的銜接。無流程或命令變更

**Version**: 1.5.0 — `severity` 不變式段落補「適用範圍」與「機械鏡射口徑」兩則加註：明示不變式為新建/修訂時的應然目標而非存量現況（全量掃描 420 檔僅 15.0% 合規），依 only_frontmatter/only_body/neither 三類記錄補值方向；就 only_frontmatter/only_body 兩類明訂機械鏡射可作第一手評估替代（neither 類不適用），並註明鏡射值仍屬待驗證資訊、不因已鏡射而排除後續人工覆核修正。無流程或命令變更

**Version**: 1.4.1 — 本 skill 的入口檔由 `skill.md` 更名為 `SKILL.md`（原小寫檔名使各消費端以 `*/SKILL.md` 掃描的產生器與稽核器永久漏掉本 skill）；`lib/severity_audit.py` 內指向該入口檔的路徑引用同步更正。無流程或命令變更

**Version**: 1.4.0 — 步驟 7 改接原子版入口 `allocate_and_reserve_pattern_id`（取代舊版 `allocate_pattern_id`），補佔位檔語意、接續 Edit 動作、非 POSIX 降級說明；步驟「輸出」補與步驟 8 `readme_index.sync` 的相容性提示（reserved 狀態下同步會產生空殼列，需先完成內容填寫再同步）（接續 allocator 原子化）

**Version**: 1.3.0 — 明訂 `severity` 權威來源與更新時機：內文「風險等級」為第一手來源，frontmatter 為同步鏡射；全量覆核修正 15 檔分歧中的 14 檔

**Version**: 1.2.0 — add 流程新增步驟 8：README 索引同步改由 `readme_index.sync` 保守 upsert CLI 化，取代「更新 README.md 統計資訊」文字指示（接線方式經更正）

**Version**: 1.1.0 — query 增強：--category 篩選、同義詞家族 5→11、frontmatter 摘要排序、命中數計數
