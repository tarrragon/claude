---
name: compositional-writing
description: "Composes atomic, intent-revealing, grep-friendly writing (Zettelkasten) for code comments, docs, logs, prompts, schema/ticket fields, external-analysis transformation, and long-form technical articles. Use when cognitive load and token cost matter. **Also triggers during multi-round review / batch review / 寫作 audit** — provides the keyword bank (正向陳述 / 口語修辭 / 地區用語 / 廢話前綴 / 裝飾符號 / 對讀者喊話 / 自評誇飾 / 必然性框架) and frame-specific check lists that multi-round-review reviewer agents need. Triggers: 寫註解, 寫文件, 寫日誌, 寫 prompt, 寫文章, 技術文章, 商業分析, 外部分析文章, post-mortem, 架構決策, 除錯復盤, 欄位設計, atomic, reusable, 多輪審查, multi-round review, batch review, 寫作 audit, 正向陳述, 口語修辭, 字句層 grep."
license: MIT
metadata:
  version: 0.18.0
  category: writing-methodology
---

# Compositional Writing

以 Zettelkasten（卡片盒筆記法）為核心的寫作方法論。將每段文字視為可重複組合的原子卡片，讓人類讀者與 AI 代理人都能以最小認知負擔找到答案。

---

## Core Pillars（核心支柱）

| 支柱                                   | 意義                                                       |
| -------------------------------------- | ---------------------------------------------------------- |
| **Atomization** 原子化                 | 一段文字只承載一個概念，可獨立閱讀與重用                   |
| **Explicit Intent** 意圖顯性與層級貼合 | 讀者第一眼就看懂「為什麼在這裡、屬哪個抽象層級、該做什麼」 |
| **Searchability** 可查詢性             | 人和 AI 都能用關鍵字 / grep / regex 快速定位               |

---

## Core Principles（核心原則速查）

讀者能在本區塊完成快速複習；需要具體應用時，依下方「觸發路由」讀對應情境 reference。

### 1. 原子化（Atomization）

一張卡一個概念：能獨立理解、可跨情境重用。拆分依據是**認知負擔與情境匹配度** — 讀者要同時記住的概念數、以及這張卡是否符合讀者當下的情境需求。常見的誤判依據是「行數」（卡太長就拆）、行數只反映表面字數、不反映概念數：一張 200 行的卡可能只講一個概念、一張 30 行的卡可能塞了三個概念。判別問題是「讀者要同時 hold 幾個概念才讀得懂這張卡」、超過 7 個就要拆。

**拆分判準的核心問題**：「這張卡聚焦在什麼問題、議題切完整了嗎？」— 判準是 **focus 完整度**。常見的次級訊號是「卡之間是否衝突」「邊界是否清晰」、兩者都不夠：兩張卡互不衝突、仍可能各切了一半同樣議題；一張卡邊界清晰、仍可能塞了兩個獨立議題。focus 完整度問的是「這張卡有沒有把它聲稱要解決的議題講完」、是 contrast 上面那兩個訊號抓不到的死角。

### 2. 索引建立（Indexing）

用 MOC（Map of Content）、tag 層級與反向索引把卡片串成可導航的網。入口文件**只做路由**、把細節留給目標卡；引用深度**最多一層**、讓讀者一跳就到答案（避免 A→B→C 的多層跳躍）。

**引用錨點用語意標題、不用位置編號**：引用另一個章節 / 階段 / 條列項時寫「見核心問題」、不寫「見 Stage 3」— 編號是結構排列的 derivation、結構重排時引用句字面完好、語意 silent 指向錯的內容（比 broken link 難偵測：連結斷掉會報錯、編號錯位會成功解析到錯的東西）。對應要求是每個結構單位的標題要承載核心意義（「Stage 3：核心問題」、編號只作排序前綴）、引用取語意半邊；發布方凍結的編號（RFC 段號 / 法條）是 fact、可引用。詳見 [reference-by-semantic-title-not-number](references/principles/reference-by-semantic-title-not-number.md)。

**語意錨用單一字串、引用他卡用對方的詞彙**：同一個結構單位的語意名稱只能有一個 canonical 字串（取標題語意半邊）— 同義雙名（標題「決策記錄 + scaffold 建議」、引用「決策收斂階段」）讓 grep 掃 A 漏 B、重排修復退回人腦對應。引用另一張卡並描述它的內容時、寫之前把被引卡重新打開、用它自己的分類詞彙轉述 — 記憶存概念不存 taxonomy、憑印象轉述會把對方明確分開的類別併掉、每條關係宣告要找得到被引卡的支撐句。

**集合命名用角色、不內嵌數量**：標題要當穩定錨、就得先是純 fact —「核心七問」「成長六階段」「四大支柱」把成員數烤進名字、數量是成員清單的 derivation、加一問名稱先失真、所有複製過名稱的地方跟著過期。命名只承載角色與層級（核心問題 / 撞牆階段 / 支柱）、數量讓清單自己呈現；外部凍結品牌（SOLID 五原則 / OWASP Top 10）跟概念閾值（兩次門檻）的數字是 fact、可留。詳見 [name-collections-by-role-not-count](references/principles/name-collections-by-role-not-count.md)。

### 3. 意圖顯性與層級貼合（Explicit Intent & Layer Alignment）

**寫作前先標記本文所在抽象層級（實作 / 工具 / 協作 / 認知 / 架構）、論述停在該層**。素材取自哪個層級、論述就收斂在哪個層級 — 因為跨層提升等於用 X 層的詞彙描述 Y 層的議題、讀者拿到規則但對不到自己當下的情境。要把實作層素材抽象到認知層、先補對應抽象層的支撐文件（讓論述有對應層的詞彙跟 case 可引用）、再做跨層提升。

寫「為什麼」和「要達成什麼」、把「程式碼在做什麼」留給程式碼自身（程式碼讀一次就知道做什麼、寫進註解只是冗餘）。主詞與動詞直接、段落開頭即表達意圖。TODO / placeholder 留給 inline 註解、文件本體只放當前契約 — 因為文件常被當成「契約 SSoT」引用、混入未完成事項會讓讀者誤判契約範圍。同一篇文字貼合它在系統裡的抽象層級、把下層實作藏在介面後面。

**機會成本語氣優先**：程式設計大多是多目標取捨、討論的是「在什麼情境下哪個選項較划算」。把絕對二元語氣（「正確概念是 X / 替代方案不足 / 應該這樣做」）翻成情境化敘述：「比較好的做法是 A、因為 [情境] / B 在 [其他情境] 合理 / D 的成本特別高、只在 [極端情境] 才划算」。機會成本教讀者「思考方式」（能套用到新情境）、絕對主義教讀者「規則」（壓力下會忘）— 所以前者是預設語氣。例外保留給物理 / 法律 / 數學事實（安全性、數據完整性、合規、雜湊必有碰撞）。絕對二元語氣有兩種形式：**命令式**（「應該做 X」）讀者聽得出是主張、會審；**必然式**（「X 天生就是 Y / 本質就是 / 必然」）偽裝成事實陳述、更隱形 — 把設計選擇講成自然法則時尤其要 catch、還原成「在選了某前提後 X 才以此形式成立」。判別線：這個必然有沒有上游設計選擇當前提（有=條件性、要講前提；無=真必然、可斷言）。詳見 [teaching-prose-neutral-register](references/principles/teaching-prose-neutral-register.md)。

**選項數由議題本身的合理選項數決定**：機會成本的精神是「教思考方式」 — 議題有幾個合理選項就寫幾個（2 個寫 A/B、3 個寫 A/B/C、4 個寫 A/B/C/D）。強湊到固定數量會把「教思考」退化成「填格式」、生出「實務上幾乎不存在」的低品質假反模式。真正的反模式直接標「D：反模式 — 違反 X 原則」、給讀者明確的「為什麼這條路該避開」、保持誠實。

**讀者定位聲明（生成端前置步驟）**：每個教學模組在第一篇文章生成前，顯式聲明讀者定位——一段話描述目標讀者的背景、已有能力、缺的經驗。這份聲明是後續所有生成和 review 的可檢查基準。缺少顯式聲明時，LLM 預設用「教外行人」的姿態寫教學內容，這個預設不被 review 挑戰（reviewer 共享同一個預設），導致宣導語氣通過多輪審查。per [outside-in reader frames report](/report/review-lacks-outside-in-reader-frames/)

**讀者定位：缺經驗的專業人士、不是外行人**：技術教材的讀者是在特定領域缺乏經驗的專業人士，不是完全不懂的外行人。寫法是補足經驗缺口（直接描述情境與操作需求），不是從零科普（故事線導入、比喻堆疊、宣導語氣）。宣導式語氣（「你可能沒注意到」「把 X 想成 Y」「跑得好好的」）預設讀者無能、降低教材可信度。詳見 [audience-is-professional-not-layperson](references/principles/audience-is-professional-not-layperson.md)。

**跨專業溝通用情境遞進、不用比喻堆疊**：向非本領域的專業人士（管理層、決策者）解釋技術議題時，減少術語並從簡單情境遞進到複雜情境。比喻傳遞形狀但不傳遞嚴重性、在細節處崩解、且隱含「對方聽不懂」的預設。用決策者熟悉的維度（影響範圍、恢復時間、成本量級）表達。詳見 [cross-expertise-scenario-not-analogy](references/principles/cross-expertise-scenario-not-analogy.md)。

**技術教材內嵌管理層可彙報的資訊**：技術段落旁嵌入成本量級、時程估算、進度指標與決策簽核點（各 1-2 句），讓讀者學完技術做法的同時拿到向上彙報的素材。成本用量級不用精確數、時程用範圍不用單點、進度用可查詢指標。詳見 [management-reportable-info-in-technical-content](references/principles/management-reportable-info-in-technical-content.md)。

**知識卡建卡判準用「最不熟悉的讀者」**：知識卡的建卡判準是「目標讀者群裡最不熟悉的那端能不能理解這個術語」，不是「作者覺得夠不夠常見」。常識是相對於背景的——.htaccess 對 PHP 工程師是常識、對 Node.js 工程師完全陌生。跨背景讀者群的教材裡，幾乎所有領域特定術語都需要建卡。建卡的邊際成本低（40-50 行）、讀者缺卡的代價高（離開教材去 Google、可能找到不一致的解釋）。per [常識是相對於讀者背景的](/report/common-knowledge-is-relative-to-reader-background/)。

**操作步驟帶環境專屬工具路徑**：操作型文章的每一步至少帶一條工具路徑（用什麼軟體、輸入什麼指令）。同一個動作在不同環境（container / VM / 共享主機）的工具路徑可能完全不同——「拍下現況」在 container 是 `docker commit`、在 VM 是 AMI 快照、在共享主機是 FTP mirror + phpinfo。文章涵蓋多種環境時、每一步要按環境分列工具、或標明適用環境。自測問題：「讀者坐在電腦前，下一個動作是打開什麼軟體？」答不出來就是缺口。per [操作指引要帶環境專屬工具路徑](/report/operational-how-needs-environment-specific-tooling/)。

**Case 引用段落的三段式結構**：三段式是案例引用段落的順序紀律 — 把「概念 → 案例 → 操作」三層分開承擔（段首給概念定義、case 引用居中、通用工程知識展開）、讓段落結構跟讀者學習新概念的認知順序對齊。LLM 從 case 反推內容容易把 case 揭露當概念出發點、實證觀察 11/12 段都犯這個錯。詳見 [case-citation-three-part-structure](references/principles/case-citation-three-part-structure.md)。

**原子筆記要有向上的議題入口**：承載知識的原子筆記（Zettelkasten 卡 / glossary / 術語條目）不是字典條目 — 字典答「這個詞是什麼」、承載知識答「你在討論什麼、撞到什麼問題、才需要這知識」。撰寫者有預設情境讀者沒有、所以每張卡（或其上層）要從情境進入而非劈頭給定義：建議題 hub（以讀者遇到的問題為題）討論再分流到原子卡、卡頂回指議題、讓搜尋直接落地者也有回路。沒這層卡淪字典、讀者沒有觸發點、不知何時用。詳見 [atomic-note-needs-situational-entry](references/principles/atomic-note-needs-situational-entry.md)。

### 4. 可查詢性（Searchability）

關鍵字前置、使用可 grep 的分隔符（`:` `|` `→` `==`）、欄位名稱使用 regex 友善格式。命名讓 AI 能以單次 grep 命中，不需要語意推理。

### 5. 欄位設計（Field Design）

同一份文件的不同欄位，從不同角度觀察同一件事，不重複撰寫。`what` 描述動作、`why` 陳述動機、`acceptance` 定義可驗證條件；混淆欄位會讓讀者在多處讀到相同內容。

### 6. 多輪 Re-read Pass（Multi-pass Review）

完稿即進入 review 階段。一次寫對全部維度違反 working memory、實際結果是「每維度都做一半」。設計 N 輪 re-read、每輪用不同 frame：

| 輪  | Frame                                                                                                         | 抓什麼                                                                            |
| --- | ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 1   | 生成                                                                                                          | idea → 字、預期會有錯                                                             |
| 2   | 對意圖（[ease-of-writing-vs-intent-alignment](references/principles/ease-of-writing-vs-intent-alignment.md)） | 正文、title、description、MOC hook 都跟原意對齊                                   |
| 3   | 機會成本語氣                                                                                                  | 全 surface 的絕對詞翻成 trade-off                                                 |
| 4   | Grep-ability / 命名 / 術語                                                                                    | title、slug、link label、段首關鍵字可單次 grep 命中；術語保留原文錨點與完整名詞頭 |
| 5   | 反例 / 邊界                                                                                                   | 「何時不適用」段、反模式列表                                                      |

Surface enumeration 是 multi-pass 的固定前置步驟。寫作產物包含 body surface 與 metadata / navigation surface：`title`、`description`、`tags`、heading、link label、MOC / index entry、slug / filename。每輪 frame 都掃這份 surface 清單，讓正文與讀者入口共用同一個概念錨點。description / hook 對規則做壓縮時、**可以丟細節、不可以改模態** — 把本體的「條件允許（可延後但要記錄）」壓成「絕對禁止（不可跳過）」、讀者依摘要行動就會偏離本體；摘要讀起來比本體「更有力、更乾脆」就是失真訊號、模態詞跟主詞動詞同級、最後砍。實測一批七份文檔有四份的 description 出現模態漂移 — 這個檢查每批都要跑。

**核心**：「再仔細一次」≠ multi-pass — 同 frame 重看 catch 不到新問題。每輪換 frame、才能 catch 不同層。各 reference（writing-articles / writing-code-comments / writing-documents / writing-prompts）依 output 類型有特化的輪次組合。

Naming 是這條原則最容易跳的子場景 — 第一版命名幾乎不對、四輪 review（第一版 / grep / cross-call-site / impl 洩漏）才收斂、見 [naming-as-iterated-artifact](references/principles/naming-as-iterated-artifact.md) 跟 writing-code-comments 的 naming review 段。術語是 naming 的高歧義子場景：翻譯術語第一次出現保留原文錨點，中文壓縮術語保留完整名詞頭，中文名詞頭要保留來源中的概念角色，見 [terminology-keeps-original-anchor](references/principles/terminology-keeps-original-anchor.md)、[compressed-chinese-terms-need-head-noun](references/principles/compressed-chinese-terms-need-head-noun.md) 與 [translation-must-preserve-concept-role](references/principles/translation-must-preserve-concept-role.md)。

**高 stakes 內容追加輪 E（epistemic rigor、conditional opt-in）**：reader 照做後錯誤不可逆的內容（資安 / concurrency 正確性 / distributed consistency / financial / medical）在 5 輪基本 frame 之外、追加 stakes 軸的 epistemic rigor pass——比照學術 peer review 跑 claim / evidence / method / threats / citation 五個 sub-check、加上 audit recommendation tier（accept / minor / major / withdraw）。一般內容 5 輪夠、不跑輪 E；高 stakes 內容兩軸都跑。詳見 `references/auditing-articles.md` 跟 `references/principles/writing-multi-pass-review.md` 的「stakes-conditional 追加輪」段。

**Production 教學文章追加輪 8-10（字句層 catch、跑 N 輪仍漏時觸發）**：跑了 5 輪基本 frame 仍系統性漏 catch 字句層問題（口語修辭 / 廢話前綴 / 地區漂移 / 依賴 code / **裝飾符號 emoji** / 對讀者喊話 / 自評誇飾 / 必然性框架 / 恐嚇式語氣 / 歸因語氣）時、追加三個換軸機制——輪 8 keyword bank（換工具、含 emoji / 裝飾 unicode 掃描）、輪 9 reader simulation（換視角、四 lens：自包含性 + register/stance + meta 殘留 + AI 歸因過度）、輪 10 self-criticism（換層次、審視 framework 本身覆蓋度）。短文 / 即時 note 不需要、production 教學文章在跑 5 輪後仍漏同類問題時 opt-in。**keyword bank 命中是候選、不是判決**——grep 命中後仍要一個語意判定步驟（這個命中是建立概念的違規、還是合規的反例對照 / hook），reviewer 容易把違規合理化放行；偵測（bank）跟判定（語意）是兩個認知步驟。**register/stance 類（喊話 / 誇飾 / 必然）無穩定關鍵詞、keyword bank 抓不到、輪 9 reader-sim 是主 keyword bank 是輔、且最依賴 external cold-read**。漏抓後補機制前先分 **design gap**（框架缺 frame、改框架）vs **execution gap**（框架有 frame 但只跑了臨時子集、改執行不是改框架）——「加 keyword」對 execution gap 跟無關鍵詞的類都無效。詳見 [multi-pass-review-frame-granularity](references/principles/multi-pass-review-frame-granularity.md)、[decorative-symbols-keyword-bank](references/principles/decorative-symbols-keyword-bank.md)、[teaching-prose-neutral-register](references/principles/teaching-prose-neutral-register.md) 跟 `references/writing-articles.md` 輪 8-10 段。

**批量 sibling 寫作的生成端輪替**：一次寫多份同類文檔時、cadence 同質化會在六個層發生（title 形式 / 開場句式 / 章節標題 / 敘事骨架 / 條目形態 / 跨檔引用句）、單份 review 全部抓不到、且 review 端抓過的同骨會在下一批復發 — 同類 finding 第二次出現、就把規則升到生成端：寫之前排好開場 frame 輪替（規則先行 / 後果先行 / 動作先行 / 反差先行）、條目形態輪替、敘事視角輪替、引用句去重。詳見 [cadence-homogenization](references/principles/cadence-homogenization.md)。

**Instance 軸：跨 reviewer instance 隔離**：Instance 軸是 multi-pass review 的另一條擴展軸 — N 個獨立 reviewer instance 各自獨立 context、各自跑 background、解「單一 reviewer 同時看多維度容易維度盲點 + context 污染」的問題。Instance 指獨立 reviewer 程式實體（如 agent tool spawn 出的 subagent）、跟同一 reviewer 換輪次 frame（frame 軸）正交可疊加。適用 production 教學文章 / 高 stakes 內容 / 跨章節教學模組這類維度複雜度高的審查場景。詳見 [agent-team-context-isolation](references/principles/agent-team-context-isolation.md)。

詳見 [Writing 的 multi-pass review](references/principles/writing-multi-pass-review.md)、[Methodology 的 multi-pass 該 embed 在 pillar](references/principles/methodology-multi-pass-embedding.md)、[Metadata surface 要納入寫作 review 範圍](references/principles/metadata-surface-in-writing-review.md)、[False sense of security 是高 stakes 寫作的主要失敗模式](references/principles/false-sense-of-security-as-primary-failure.md)、[Risk-asymmetric audit standard](references/principles/risk-asymmetric-audit-standard.md)、[colloquial-rhetoric-erodes-technical-precision](references/principles/colloquial-rhetoric-erodes-technical-precision.md)、[prose-self-contained-without-code-reference](references/principles/prose-self-contained-without-code-reference.md)、[regional-terminology-alignment](references/principles/regional-terminology-alignment.md)、[multi-pass-review-frame-granularity](references/principles/multi-pass-review-frame-granularity.md)、[design-flaw-by-current-axes-not-hindsight](references/principles/design-flaw-by-current-axes-not-hindsight.md)、[agent-team-context-isolation](references/principles/agent-team-context-isolation.md)、[decorative-symbols-keyword-bank](references/principles/decorative-symbols-keyword-bank.md)、[teaching-prose-neutral-register](references/principles/teaching-prose-neutral-register.md)。

---

## When to Consult This Skill（觸發路由）

| 觸發情境                                                                                                                                                                    | 讀哪份 reference                                                                                                   |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 要寫或改一段程式碼註解 / doc comment                                                                                                                                        | `references/writing-code-comments.md`                                                                              |
| 要起草 / 改寫一份文件（worklog、spec、README）                                                                                                                              | `references/writing-documents.md`                                                                                  |
| 要設計 log / 錯誤訊息 / 結構化輸出                                                                                                                                          | `references/writing-logs.md`                                                                                       |
| 要撰寫給 AI 的 prompt / instruction / Agent 派發 / Ticket Context Bundle                                                                                                    | `references/writing-prompts.md`（為 `.claude/rules/core/ai-communication-rules.md` 的詳細版庫，portability-allow） |
| 要撰寫完整長篇技術文章（blog post / post-mortem / 架構決策 / 除錯復盤 / 技術評估）                                                                                          | `references/writing-articles.md`                                                                                   |
| 要把外部分析文章 / 產業評論 / 投資人備忘錄 / 高密度研究材料轉成教學型分析文章，或把 AI 改寫稿從摘要升級成可遷移框架                                                         | `references/source-to-teaching-analysis.md`                                                                        |
| 要翻譯 / 轉譯文章、把英文材料改寫成中文、檢查術語誤譯或中文譯名放回句子後是否成立                                                                                           | `references/translation-review.md`                                                                                 |
| 要管理多篇相關文章的結構（系列、文集、知識庫、素材庫比例、MOC、跨篇引用、何時抽抽象層 / Pattern 卡片）                                                                      | `references/managing-article-collections.md`                                                                       |
| 要對既有高 stakes 內容（資安 / concurrency / distributed / financial / medical）做 reviewer-style audit、找 false sense of security / 對位失效 / context 缺 / citation 過時 | `references/auditing-articles.md`                                                                                  |
| 要設計 ticket 欄位 / schema frontmatter / 表單欄位                                                                                                                          | `references/designing-fields.md`                                                                                   |
| 想驗證寫作品質（認知負擔、獨立理解率）                                                                                                                                      | `references/meta-metrics.md`                                                                                       |
| 要新增或修改一份 Skill reference（撰寫品質規範、結構標準）                                                                                                                  | `references/reference-authoring-standards.md`                                                                      |
| 要驗收 Skill 發布品質（語意層驗收、Phase 2 dry-run）                                                                                                                        | `references/dry-run-guide.md`                                                                                      |

每份 reference 自包含：以該情境為核心，把核心原則翻譯成可直接套用的檢查項與範例。閱讀任一 reference 不需要回來看其他 reference。

---

## Success Criteria（M1-M2 認知負擔類）

| Metric                        | 定義                                                  | 目標 |
| ----------------------------- | ----------------------------------------------------- | ---- |
| **M1 — 找到答案路徑**         | 讀者從 SKILL.md 出發，需要開啟幾個檔案才能解決問題    | ≤ 2  |
| **M2 — reference 獨立理解率** | 隨機挑一份 reference，不讀其他 reference 能否獨立套用 | 100% |

詳細量測方式與自評表見 `references/meta-metrics.md`。M3-M5（token 類）保留未定，待實際範例累積後補足。

---

## 跟特化寫作流程的分工

本 skill 是 *單篇* 寫作的基礎方法、覆蓋 articles / comments / logs / prompts / fields 等 surface。當寫作對象是 *跨多章節的教學模組*（5+ 章、有案例庫支撐、跨章引用密集）、屬特化情境、有專屬的 *跨章節生產流程*：案例庫 audit 抽 findings、SSoT 對應規劃、agent team 平行 review、跨檔修正循環、跨章 polish pass。

兩類流程的分工：

| 流程                                  | 適用                                                      | 核心紀律                                                                                                                                                  |
| ------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **本 skill（compositional-writing）** | 單篇文字（articles / comments / logs / prompts / fields） | 6 原則（原子化 / 索引 / 意圖顯性 / 可查詢 / 欄位 / 多輪 review）+ 各 surface 特化 reference                                                               |
| 跨章節教學模組生產流程                | 跨 5+ 章、有 case 庫的教學模組                            | case-first 流程：案例 audit → 基於 findings 寫稿 → agent team 平行 review → 修正循環 → polish pass、加 case 引用四 axis 紀律（深度 / 分層 / 合成 / 結構） |

兩類流程互補疊加 — 教學模組的每章內部寫作仍套本 skill 6 原則、case 引用段落用 [case-citation-three-part-structure](references/principles/case-citation-three-part-structure.md)、agent team review 用 [agent-team-context-isolation](references/principles/agent-team-context-isolation.md)。當下游專案沒有跨章節教學模組需求、本 skill 即可獨立運作；當有需求、教學模組生產流程是本 skill 的擴展層、不取代本 skill。

## 跟 multi-round-review 的協同

寫多篇章節 / report 卡 / knowledge card 後做**多輪 agent reviewer audit** 時、本 skill 應該跟 multi-round-review skill 同時啟動。觸發詞「多輪審查 / Round 1/2/3 / batch review / 寫作 audit」會同時啟動兩個 skill：

- **multi-round-review** 規劃 frame 切換結構（Round 1 compliance / Round 2 cadence / Round 3 self-application）跟跨輪 finding 整合工作流
- **本 skill（compositional-writing）** 提供每輪 frame 的字句層 keyword bank — Round 1-A 寫作規範 reviewer 必須跑：
  - **正向陳述優先 grep**：`rg "不[行可是要能該支對符夠必]|無法|沒[做有]|而非|而不是"`、加上**否定起手定義句**（原 pattern 漏「而是」、抓不到「不是 X、而是 Y」的後半）：`rg "不是.{0,30}而是|不是.{0,20}、是|與其.{0,20}不如|不只.{0,15}更"` — 主要敘述要正向、反例對照的少量負向可保留；判別在「核心概念第一次正面出現在句首、還是被擠到『而是』之後」
  - **口語修辭 grep**：`rg "其實|實務上|真的|碰巧|立刻撞牆|沒事"`
  - **地區用語 grep**：`rg "集群|默認|質量|視頻|函數|文件夾|接口"`
  - **廢話前綴 grep**：`rg "值得注意的是|需要說明的是|實際上|基本上|事實上"`
  - **裝飾符號 grep**：`rg "✅|❌|⚠️|🚨|🟡|🟢|⭐|📌|✓|✗"`
  - **對讀者喊話 grep**：`rg "很多人|大家|不少人|你天天|你會|你可能|先讀懂|先釐清|別搞混|別被"` — 教材中性陳述、不安撫情緒 / 不第二人稱代入 / 不祈使控制閱讀（hook / narrative 段落輕度第二人稱可留）
  - **自評誇飾 grep**：`rg "教科書級|堪稱|可謂|完美|經典|範本級|大師級|漂亮地|優雅地|最佳實踐|best practice"` — 品質 verdict 頂替技術理由、換成機制 / 條件
  - **必然性框架 grep**：`rg "天生|與生俱來|本質就是|本來就是|必然|唯一|註定|理所當然"` — 把設計選擇講成自然法則、還原成條件性（物理 / 法律 / 數學事實除外）
  - **歸因語氣 grep**：`rg "承認|暴露了|證明了失敗|被迫"` — 描述系統行為用「信號」「反映」「顯示」等中性觀測詞、避免「承認」「暴露」等責任歸因詞；「被迫」在描述外部強制約束時可保留
  - **宣導語氣 grep**：`rg "你可能沒注意|你可能不知道|想像一下|把.{1,5}想成|跑得好好的|聽起來很|其實很簡單|說穿了就是|等於拆未爆彈|乾瞪眼|延遲引爆"` — 預設讀者無知或用情緒管理取代事實陳述；讀者是專業人士、直接描述情境與後果
  - **這些 grep 曝光候選、不做自動判定**：命中後要不要算違規有品味核心；且 LLM reviewer 跟作者共享文體、同源自審對 register 類（否定起手 / 喊話 / 誇飾 / 概念前置）有結構上限 ——「不是 X、而是 Y」這種 LLM 高頻自產句型最容易全員放水。grep + 同源判定只負責曝光候選、register 層的真防線是文體異源視角（human cold-read 或 prompt 採「挑剔否定起手 / 概念後置」對抗姿態的 reviewer）、同源回報的「clean」不可當真

詳細各維度的判讀規則跟修法、見對應 reference（writing-articles / writing-documents 等）跟 `references/principles/` 內的 cadence-homogenization / colloquial-rhetoric / regional-terminology / decorative-symbols / multi-pass-review-frame-granularity 等卡。

協同要點：

- 單獨用 multi-round-review、容易漏字句層 — reviewer prompt 列「規範遵循」但漏 grep 具體 pattern
- 單獨用本 skill、容易漏跨輪 frame 規劃 — 知道要檢查字句層、但缺「Round N+1 用什麼新 frame」結構
- 兩個 skill 一起啟動 — multi-round-review 給結構、本 skill 給每輪的 grep checklist

寫作對象是「單篇 + 完稿前自己 review」時、用本 skill 第 6 原則（多輪 Re-read Pass）的 5 輪 frame 即可；寫作對象是「跨多篇 + agent reviewer 平行 audit」時、multi-round-review 接手結構規劃、本 skill 在 reviewer prompt 內被引用作為檢查清單。

---

## Directory Index

```text
compositional-writing/
├── SKILL.md                              # 本檔：核心原則速查 + 觸發路由
└── references/
    ├── writing-code-comments.md          # 情境 1：程式碼註解
    ├── writing-documents.md              # 情境 2：文件撰寫
    ├── writing-logs.md                   # 情境 3：log 輸出
    ├── writing-prompts.md                # 情境 4：prompt 撰寫
    ├── writing-articles.md               # 情境 5：完整長篇技術文章
    ├── source-to-teaching-analysis.md     # 情境 5a：外部分析材料 → 教學型分析文章
    ├── translation-review.md             # 情境 5b：文章翻譯 / 轉譯的句內邏輯 review
    ├── managing-article-collections.md   # 情境 5c：跨多篇文章的結構（三層、素材庫比例、MOC、Pattern 卡片）
    ├── designing-fields.md               # 情境 6：欄位設計（含六欄位角度總表）
    ├── designing-fields-ticket-6w.md     # 六欄位詳細範例：正確 + 混淆共 12 項（按需讀取）
    ├── meta-metrics.md                   # 品質量化驗收（M1-M5）
    ├── reference-authoring-standards.md  # Skill reference 撰寫品質規範
    ├── dry-run-guide.md                  # Skill 發布前語意層驗收（Phase 2 dry-run 流程）
    └── principles/                       # Skill 內部支撐型原則卡（含 terminology / naming / review / case-citation / agent-team 等原則）
```

---

## Reading Order（建議閱讀順序）

1. 第一次接觸 → 從本 SKILL.md 的「核心支柱 + 核心原則」讀起
2. 進入實際寫作情境 → 依觸發路由讀對應 reference（只讀一份）
3. 想驗證成果 → 讀 `meta-metrics.md` 做自評

---

**Last Updated**: 2026-06-25
**Version**: 0.18.0 — 輪 9 reader-sim 加第四 lens「AI 歸因過度」（AI 生成內容系統性把通用 pattern 框為 AI 特有、縮窄適用範圍且背上無法證實的舉證負擔；判準：「AI」換成「作者」論點仍成立 → 改通用觀察）；提交自檢清單加第 4 個生成端自問句（AI 歸因測試）。

**Version**: 0.17.0 — keyword bank 新增歸因語氣 grep + 否定起手定義句 pattern；輪 8-10 描述補恐嚇式語氣 / 歸因語氣；移除 comment-qa-hook / worklog-format-check hook（職責已由其他機制覆蓋）；references 更新（atomic-note / teaching-prose / writing-articles / writing-documents）。

**Version**: 0.16.0 — 從工具 opinion 文章的三輪審查 + 使用者回饋回流 6 張 report 卡（WRAP 分析後選混合方案）：(1) keyword bank 加歸因語氣 grep（`承認|暴露了|證明了失敗|被迫`）— 唯一有穩定關鍵詞的新 design gap；(2) `teaching-prose-neutral-register` 加第四類「恐嚇式語氣」（把讀者放在被警告位置、判別線是「你→我們」替換測試）；(3) writing-articles 輪 9 reader-sim 加第三 lens「meta 資訊 vs 內容」（涵蓋 meta-commentary 殘留 + 主題偏移兩個 gap）；(4) writing-articles 提交自檢清單加 3 個生成端自問句（恐嚇式 hook / meta 刪除測試 / 歸因語氣）。不新增 principle 卡（27 張已夠、新議題融入現有卡）、不增 SKILL.md 主體段落（密度飽和、改動集中在 keyword bank 一行 + 下游 reference）。

**Last Updated**: 2026-06-11
**Version**: 0.15.0 — 對七張同批 report 卡（#157-#163 主題：語意錨 / 決策表 / 入口分流 / 跨 surface / 摘要模態 / 引用詞彙 / 欄位契約）跑三 reviewer audit 後的回饋：(1) 新增 principle 卡 [cadence-homogenization](references/principles/cadence-homogenization.md)（同時修復 SKILL.md 長期 dangling 的引用）— 六個同骨層實測清單 + 生成端輪替規則 + 「同類 finding 第二次出現升生成端」的升級原則（觸發：上一輪抓過的「判準句同模」在本批復發、擴到 4/7）；(2) 原則 6 surface enumeration 補 description 模態檢查（實測 4/7 份 description 模態漂移、其中一份把同批另一張卡才立的「候選」壓成「證據」）；(3) 原則 6 補批量 sibling 生成端輪替段；(4) 原則 2 補「語意錨單一字串 + 引用他卡用對方詞彙」段（關係宣告 28 條核對抓到 2 條：被引卡沒漏的宣稱成漏、對方的 navigation surface 被轉述成 metadata surface）。

**Last Updated**: 2026-06-11
**Version**: 0.14.0 — multi-round review Round 1 的 self-application 修正：兩個 reviewer 從不同 frame 獨立抓到本 skill 自身殘留 count-bearing 名稱（convergence 訊號）。(1) 「Core Pillars（三大支柱）」→「（核心支柱）」、「Six Principles（六大原則速查）」→「Core Principles（核心原則速查）」、「五階段流程」→「case-first 流程」；(2) references 內「五大原則」全改「核心原則」— 這批字串在原則從 5 個長到 6 個之後就已經全部過期（SKILL.md 寫六大、references 寫五大）、是 name-collections-by-role-not-count 卡描述的失效模式在本 skill 的實證；(3) reference-by-semantic-title-not-number 卡的 ISO 邊界限定到版本年份（跨版改版會重編條款）。後續 Round 3 self-application sweep 抓到本條宣稱的漏網（writing-code-comments 的「五大寫作原則」）與另兩處 count 殘留（「五大 surface」「三大正交 axis」）、已一併清除；兩張新 principle 卡依 steelman 補強（#155 卡補「標題改名 vs 編號位移」斷裂等級差、#156 卡補數字記憶價值的誠實對沖與「內部宣告凍結」邊界）。

**Last Updated**: 2026-06-11
**Version**: 0.13.0 — 0.12.0 的同日延伸：使用者指出「核心七問」「成長六階段」是另一層問題 — 引用端修好了、但錨點名稱本身內嵌成員數（七 / 六 是 membership 的 derivation）、加一問名稱先失真、所有複製過名稱的地方跟著過期；0.12.0 的原則 2 新段自己就用「見核心七問」當正面範例而未察覺、證明命名端與引用端是獨立檢查維度。(1) 原則 2 補「集合命名用角色、不內嵌數量」段；(2) 新增 principle 卡 [name-collections-by-role-not-count](references/principles/name-collections-by-role-not-count.md)（self-contained、含三種可留數字的邊界：外部凍結品牌 / 概念閾值 / 緊鄰清單行內計數、含命名端掃描 regex）；(3) reference-by-semantic-title-not-number 卡補 sibling 連結、0.12.0 三處「核心七問」範例全改「核心問題」；(4) writing-documents Principle 2 補命名端段落。

**Last Updated**: 2026-06-11
**Version**: 0.12.0 — 從一份多階段訪談 skill 的階段重編號事故回流：跨檔引用寫成「Stage 3」「Stage 1-3」、流程從四階段改六階段後十多處引用 silent 錯位（字面完好、語意指向錯的階段）、grep 只能抓字面、人工逐處判讀仍漏修兩處。(1) 原則 2（索引建立）補「引用錨點用語意標題、不用位置編號」段 — 編號是結構排列的 derivation、misdirected 比 dangling 難偵測、標題要承載可被引用的語意、凍結編號（RFC / 法條）是 fact 例外；(2) 新增 principle 卡 [reference-by-semantic-title-not-number](references/principles/reference-by-semantic-title-not-number.md)（self-contained、含重排 commit 的引用面掃描 regex）；(3) writing-documents Principle 2 cross-reference 段補同主題小節 + anti-pattern 表加「See Stage 3 指向活文件」列。同一問題第二次出現（v0.9.1 曾修過「Stage 1-5」→「五階段流程」的 portability leak）、符合兩次門檻立卡。

**Last Updated**: 2026-06-01
**Version**: 0.11.0 — 從一篇技術教材 review 抽出三類字句層 register/framing 問題回流：(1) keyword bank 加 3 類（對讀者喊話 / 自評誇飾 / 必然性框架）、同步 description、協同段 grep、輪 8-10 段、writing-articles 輪 8；(2) 原則三補「絕對二元語氣的命令式 vs 必然式」subtype（必然式偽裝成事實、更隱形）；(3) 新增 principle 卡 [teaching-prose-neutral-register](references/principles/teaching-prose-neutral-register.md)（涵蓋三類、self-contained）；(4) multi-pass-review-frame-granularity 補「偵測之後：keyword bank 命中是候選不是判決」判定層段（偵測 vs 判定兩步驟、clean 可能是判定放水）。跟 multi-round-review Round 1-A 同步加 3 grep + 判定指引。

**Last Updated**: 2026-05-27
**Version**: 0.10.0 — 從 13 張 knowledge cards 批量改寫負向表述的經驗回流：(1) description 加觸發詞「多輪審查 / multi-round review / batch review / 寫作 audit / 正向陳述 / 口語修辭 / 字句層 grep」、明示「也在 multi-round-review 啟動時觸發」；(2) 新增「跟 multi-round-review 的協同」段、列出 Round 1-A 寫作規範 reviewer 必須跑的 5 個 grep pattern（正向陳述 / 口語修辭 / 地區用語 / 廢話前綴 / 裝飾符號）、明示兩 skill 垂直協同關係；(3) 修正 multi-round-review 漏抓字句層的盲區、跟 multi-round-review v1.1 同步 cross-trigger 設計
**Version**: 0.9.2 — 從 business case-analyses 演變回流：新增 `source-to-teaching-analysis.md` 路由，處理外部分析文章 / 產業評論 / 投資人備忘錄到教學型分析文章的轉換；新增三張 principle（external-analysis-source-layering / cross-domain-reader-level-alignment / analysis-rewrite-delivers-transferable-framework），把 source 分層、跨領域讀者降層、可遷移框架交付從 blog report 抽成 portable 規則。
**Version**: 0.9.1 — Stage 4 修正 3-reviewer 抓的 33 issue：(1) #120 mirror 縮 scope 解過載（移除四 axis 表 / 句構分流 / polish pass 段、聚焦三段式結構 axis）+ 結論段首改概念定義句解 dogfooding 失敗；(2) #121 mirror 結論表三欄重設計（設計選擇 / 解決問題 / 失敗模式）+ 實作 pattern 縮成 abstract pattern；(3) 兩 mirror 角色段引用點改措辭（移除虛假引用宣告）；(4) SKILL.md 原則 3/6 兩補強段段首改概念定義句、原則 6「詳見」list 補新 mirror、Directory Index 補；(5) Portability leak 修：「Stage 2 自查清單」→「寫稿後段落自查清單」、「Stage 1-5」→「五階段流程」；(6) 五大 / 六大原則 drift 對齊（line 105 / 160）；(7) 既有 principles（writing-multi-pass-review / multi-pass-review-frame-granularity / ease-of-writing-vs-intent-alignment）補回引新 mirror、形成雙向 cross-link
**Version**: 0.9.0 — 從跨章節教學模組生產經驗回流：原則 3 補「Case 引用段落三段式結構」段（詳見 case-citation-three-part-structure）；原則 6 補「Instance 軸：跨 reviewer instance 隔離」段（詳見 agent-team-context-isolation、跟 frame 軸正交可疊加）；新增「跟特化寫作流程的分工」段（明示本 skill 是單篇基礎方法、跨章節教學模組生產流程是擴展層）；principles/ 新增兩張 mirror 卡（case-citation-three-part-structure / agent-team-context-isolation）、自包含、不引用外部 skill 或 blog content
**Version**: 0.8.1 — 第 6 原則同步 writing-articles v0.8.1：補「Production 教學文章追加輪 8-10」段（換工具 / 換視角 / 換層次三機制處理「跑 N 輪仍漏」字句層問題）；「詳見」連結加 5 張新 principle（colloquial-rhetoric / prose-self-contained / regional-terminology / multi-pass-review-frame-granularity / design-flaw-by-current-axes）
**Version**: 0.7.4 — 新增 `translation-review.md` 路由：翻譯 / 轉譯文章時，用句內邏輯檢查譯名是否跟主詞、動詞、修飾語、因果與讀者追問方向對位。
**Version**: 0.7.3 — managing-article-collections 補「素材庫比例」路由：多篇文章需要案例 / source / scenario / pattern 支撐時，主文章情境維持少量、素材庫保留 2-3 倍來源做反向驗證
**Version**: 0.7.2 — 補 multi-pass 的 surface 軸：review 先列 body / metadata / navigation surface（title、description、tags、heading、link label、MOC hook、slug / filename），每輪 frame 都掃同一份 surface 清單；新增內部 principle `metadata-surface-in-writing-review.md`
**Version**: 0.22.0 — 原則 3 加「知識卡建卡判準用最不熟悉的讀者」；常識是相對於讀者背景的、跨背景讀者群幾乎所有領域特定術語都需要建卡
**Version**: 0.21.0 — 原則 3 加「操作步驟帶環境專屬工具路徑」（同動作在 container/VM/共享主機的工具不同）
**Version**: 0.20.0 — 原則 3 加「讀者定位聲明」生成端前置步驟；從 infra 模組 retrospective 抽出（讀者定位未預設導致宣導語氣通過三輪審查）
**Version**: 0.19.0 — 新增三張 principle 卡（audience-is-professional-not-layperson / cross-expertise-scenario-not-analogy / management-reportable-info-in-technical-content）、原則 3 加讀者定位與跨專業溝通子原則、keyword bank 加宣導語氣 grep；從 infra 教學模組的寫作 retrospective 抽出
**Version**: 0.7.0 — Phase B1 結構升級：加第 6 原則「多輪 Re-read Pass」（明示 5 輪 frame）、引用 #83 / #84 / #85 multi-pass 系列。後續 Phase B2 會把各 reference 結尾加「第 2 輪 review checklist」段
**Version**: 0.6.0 — 從 references 過載的反思：writing-articles.md 從 780 行瘦身到 ~530 行（拆分判準 / 三類 structure 模板搬到 managing-article-collections.md、focus 集中在「單篇文章內部」）；新增規則八「自我應用 (dogfooding)」（教某條規則的段落本身遵守該規則）；managing-article-collections.md 整合「拆分判準」+「三層 structure 詳細對照 + 模板」；meta-metrics.md M2 加 dogfooding 失敗訊號
**Version**: 0.5.0 — 從批量改寫 35 篇的經驗回流：原則 3 補「選項數由議題決定、不強湊」（避免 A/B/C/D 強迫症與「實務上幾乎不存在」的假反模式）；writing-articles.md 新增規則九（三類文章 structure 模板）；managing-article-collections.md 新增「跨篇引用 idiom 庫」與「三層 structure 對照」
**Version**: 0.4.0 — 新增 `managing-article-collections.md`（跨多篇文章結構：三層、MOC、Pattern 卡片）；強化原則 1「原子化」（focus 是議題完整度、不是邊界清晰）；強化原則 3「意圖顯性」（機會成本語氣、不用絕對主義）
**Version**: 0.3.0 — 新增 `dry-run-guide.md` 於 Directory Index 與觸發路由（Skill 發布前語意層驗收 Phase 2 dry-run）
