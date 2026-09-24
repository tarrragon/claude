# broken-link-check 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.5.1 — 術語校正：「判準」全數改為「判斷標準」（「停止判準」改「停止條件」）。上一輪全站替換之後這個縮寫又回流，詞面在工程讀者端讀不出來

**Version**: 2.5.0 — 清掉 39 條可攜性閘門標的消費端路徑引用，一條不剩。分類與處置：**佔位符改寫 7 處**——路徑文法說明裡的中繼變數 `X` 改成角括號形態 `<路徑>`，閘門的字元類 `[A-Za-z0-9_./-]` 不含 `<` 因此不再命中，而角括號正是本庫既有的佔位符慣例（本檔第 115 行自己就把 `<name>` 列為它認得的佔位形態）；**示範路徑標記 12 處**（`broken-link-exempt`）——glob 形態、省略號縮寫、示範指令，路徑不存在是預期的；**合成測試夾具標記 9 處**（`broken-link-exempt`）——`tests/` 的路徑在 tmp_path 裡建出來，不解析到任何真實樹；**共通安裝位置標記 6 處**（`portability-allow`）——SKILL.md 的四條執行指令與模組自身位置，沿用 `spec` 與 `5w1h-decision` 既有的行尾註解寫法；**掃描對象目錄標記 3 處**（`portability-allow`）——`.claude/hooks/` 這類目錄存不存在由各專案決定；**格式示範表補標 2 處**——SKILL.md 解析基準表的前兩列漏標，同表第三列早已標著同一個理由。兩個標記語彙依它們的語意分用：`broken-link-exempt` 說路徑不存在是預期的，`portability-allow` 說這個消費端專屬引用是刻意保留的。147 passed。掃描器對本 repo 的 scanned_files 與 total_refs 不變（431 / 641），而 broken_count 由 8 降為 6——降的兩條是 SKILL.md 解析基準表的範例欄（`.claude/pm-rules/decision-tree.md`、`.claude/agents/incident-responder.md`），它們一直被算成真 broken 而實際上是格式示範值，同表第三列早已標為示範、前兩列漏標。這兩條先前被記為本 repo 的已知債務，成因是分類錯誤而不是真的失連。

**Version**: 2.4.0 — 排除清單與同步工具對齊，新增 `SYNC_EXCLUDED_DIRS`（`hook-logs/`、`project-integration/`）。`project-integration/` 是同步工具整個排除傳遞的目錄，也是 Layer 2 內容該住的地方（消費端專案自備自己的一份），所以裡面的消費端專屬路徑是刻意的、不是缺陷。先前只排除 `hook-logs/`，於是照規範把 Layer 2 內容放進 `project-integration/` 反而被報違規——唯一合法的住址變成每行都要標記的地方，等於取消這個目錄的用途。代價是該目錄內真正的失連不再被本掃描抓到，與同步工具的作用域一致。附測試（含突變驗證：把該目錄從清單拿掉後同一份輸入從 0 broken 變 1 broken）。

**Version**: 2.3.0
**Last Updated**: 2026-08-23
**Source**: broken links 後置預防機制；改路由至 scan_links.py 確定性 CLI 作權威 gate，手動流程降級為非權威 fallback；新增 documented-error 豁免 marker（excluded_documented 類別 + `--include-documented` 旋鈕），case-study 內刻意記錄的不存在路徑顯式 opt-in 豁免；新增 `--scan-root` 可疊加額外掃描子樹（如 `docs`），預設行為不變（向後相容）；新增 `--fence-audit` opt-in 稽核模式，`include_code_block` 預設維持 `False` 判定的配套承擔機制，恆 exit 0 非 gate，只輸出機器可靠分組訊號不做語意分類

**Version**: 2.2.1 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 2.2.0
**Last Updated**: 2026-08-18
