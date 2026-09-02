# requirement-protocol 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 0.8.3 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 0.8.2 — 術語校正：判準全數改為判斷標準（動作修飾語縮為「X 標準」、狀態義改為「X 條件」）。判準的語域在哲學與教育評量、工程讀者解析不了——五份低階模型探針一致回報非通用

**Version**: 0.8.1 — 數量命名收斂與 lint 基線清理：標題「Core Pillars（四大支柱）」「Seven Principles（七大原則速查）」改成「核心支柱」「Core Principles（核心原則速查）」（REF2），與 compositional-writing 已採用的慣例一致。改名的觸發不只是規則命中——同一個檔裡已經漂移成「四大支柱」與「三大支柱」、「七大原則」與「六大原則」並存，正是 name-collections-by-role-not-count 描述的失效模式的實證。正文、目錄樹與 principles 卡的反向引用一併改成角色命名，原則的交叉引用改用語意標題取代編號；「與 wrap-decision 的邊界」段的條件句改成核心概念前置（POS-negation-lead）。

**Version**: 0.8.0 — 觸發路由段新增「與 wrap-decision 的邊界」註記：指令模糊屬本 skill，當事人條件不足 / premortem 計畫輪廓不清屬 wrap-decision Step 0 與 context 閘門，三者互為前置不重複問
**Version**: 0.7.0 — Phase B1 結構升級：加第 4 pillar「Multi-pass Refinement」+ 第 7 原則、明示 multi-pass 在「需求協議」場景的展開、串連 #82 / #83 / #85
**Version**: 0.6.0 — 補 #82 (字面攔截 vs 行為精煉)：點出 hook 對行為錯誤無能為力、本 skill 的 reference + self-check + dogfood examples 就是 multi-pass 設計、不是「再補一條 hook 規則」
**Version**: 0.5.0 — 補 #80 (yes/no collapse) + #81 (卡片迭代浮現)、reference 加 dogfood examples 段（4 個 Bad/Good 對照）、#75 加 selector stacking 跨連 #46-#50
**Version**: 0.4.0 — 接入 #74-#79 決策協議系列：新增第 6 份 reference `decision-dialogue.md`（五維度：呈現 / 策略 / 批次 / 時間 / 選項類型）；觸發路由加 3 條入口（呈現決策 / 開放問 / 反省題）；相關抽象層原則段補 #69-#79
**Version**: 0.3.0 — 接入 #69-#73：相關抽象層原則段補 Test-First (#69)、URL state (#70)、tab order (#71)、外部觸發 meta (#72)、search 匹配模式 (#73)
**Version**: 0.2.0 — 接入 #55-#68 系列：clarifying-ambiguous-instructions 加第 5 類「篩選類」（呼應 #58）；觸發路由加篩選類入口；SKILL.md 加「相關抽象層原則」段（#42-45 + #67-68）
**Version**: 0.1.0 — 從 50+ 篇事後檢討萃取「需求 → 實作對話協議」這條主軸；五份 references 對應「模糊指令 / 失敗轉折 / 成本與 checkpoint / 漸進驗證 / 工具切換」五個情境
