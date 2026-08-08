---
name: compositional-writing
description: "Composes atomic, intent-revealing, grep-friendly writing (Zettelkasten) for code comments, docs, logs, prompts, schema/ticket fields, external-analysis transformation, and long-form technical articles. Use when cognitive load and token cost matter. **Also triggers during multi-round review / batch review / 寫作 audit** — provides the keyword bank (正向陳述 / 口語修辭 / 地區用語 / 廢話前綴 / 裝飾符號 / 對讀者喊話 / 自評誇飾 / 必然性框架 / 澄清式框架 / 敘事姿態) and frame-specific check lists that multi-round-review reviewer agents need. Triggers: 寫註解, 寫文件, 寫日誌, 寫 prompt, 寫文章, 技術文章, 商業分析, 外部分析文章, 經驗談轉教學, 訪談整理, 機制重建, post-mortem, 架構決策, 除錯復盤, 檢討報告, 欄位設計, atomic, reusable, 多輪審查, multi-round review, batch review, 寫作 audit, 正向陳述, 口語修辭, 問句標題, 敘事視角, 字句層 grep, SOLID, 文章拆分, 結構決策, 擴充點, 依賴方向, 讀者分流."
license: MIT
metadata:
  version: 0.50.1
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

**讀者定位聲明（生成端前置步驟）**：每個教學模組在第一篇文章生成前，顯式聲明讀者定位——一段話描述目標讀者的背景、已有能力、缺的經驗。這份聲明是後續所有生成和 review 的可檢查基準。缺少顯式聲明時，LLM 預設用「教外行人」的姿態寫教學內容，這個預設不被 review 挑戰（reviewer 共享同一個預設），導致宣導語氣通過多輪審查。per [outside-in reader frames](references/principles/review-lacks-outside-in-reader-frames.md)

**讀者定位：缺經驗的專業人士、不是外行人**：技術教材的讀者是在特定領域缺乏經驗的專業人士，不是完全不懂的外行人。寫法是補足經驗缺口（直接描述情境與操作需求），不是從零科普（故事線導入、比喻堆疊、宣導語氣）。宣導式語氣（「你可能沒注意到」「把 X 想成 Y」「跑得好好的」）預設讀者無能、降低教材可信度。詳見 [audience-is-professional-not-layperson](references/principles/audience-is-professional-not-layperson.md)。

**跨專業溝通用情境遞進、不用比喻堆疊**：向非本領域的專業人士（管理層、決策者）解釋技術議題時，減少術語並從簡單情境遞進到複雜情境。比喻傳遞形狀但不傳遞嚴重性、在細節處崩解、且隱含「對方聽不懂」的預設。用決策者熟悉的維度（影響範圍、恢復時間、成本量級）表達。詳見 [cross-expertise-scenario-not-analogy](references/principles/cross-expertise-scenario-not-analogy.md)。

**技術教材內嵌管理層可彙報的資訊**：技術段落旁嵌入成本量級、時程估算、進度指標與決策簽核點（各 1-2 句），讓讀者學完技術做法的同時拿到向上彙報的素材。成本用量級不用精確數、時程用範圍不用單點、進度用可查詢指標。詳見 [management-reportable-info-in-technical-content](references/principles/management-reportable-info-in-technical-content.md)。

**斷言清單要過重建測試、重建不了展開成讀者走查**：條列式斷言（「拆開來看有三個毛病：1、2、3」）是作者走完推導後只輸出結論；判定用重建測試——讀者只憑文中已給的材料能不能自己得出每一條，不能就展開成讀者位置的走查：把讀者放到使用產物的位置、每條斷言換成動作加材料（缺的材料補進文中、那正是清單藏住的缺口）、可重用的檢查方式放在走完之後浮現。摘要位置的條列（前文已推導、條列是回收）與每條自帶證據的清單合規。詳見 [assertion-list-needs-reader-walkthrough](references/principles/assertion-list-needs-reader-walkthrough.md)。

**教學與檢討內容的敘事姿態：寫給帶問題來的讀者**：教學與檢討內容的讀者由搜尋或路由帶來、自帶問題與動機；演講技巧（問句標題、懸念段標、三幕劇遞進、第一人稱事件敘事）服務的是注意力會流失的聽眾，搬進教學內容時代價全部落在資訊結構上——問句標題把檢索錨用來提問、懸念弧把判準壓到文末、個人時間線把可重用的判斷包在一次性經歷裡。標題與段標是承載結論的直述句；檢討內容以客觀條件視角組織（「reviewer 問了 X」改成「若對這個做法問 X 而答不出來、就該重新檢討」）、「來自實際事件」的宣告開頭一句話帶過。**修懸念不是把結論搬到開頭**：灌輸與懸念是同一個缺陷的兩個方向、都讓結論與推導脫節——未經推導的開頭結論摘要（含「觸發場景 / 整理目的 / 本文邊界」欄位組）讀者只能硬記、同樣要抽掉；分工是標題承載結論、開頭承載情境定位、判準在推導走完的位置浮現。判別線是位置：操作型自問句（判準的執行步驟）合規、標題 / 段標 / 結論位的問句是懸念型。這類問題是生成端高頻默認、審查是逆風、防線主力在生產側。詳見 [write-for-readers-not-audiences](references/principles/write-for-readers-not-audiences.md)。

**檢視註解的最高原則是商業邏輯**：檢視一則註解時第一個評估是它有沒有解釋到這個行為、這個事件、或這個 flag 的商業邏輯——有、才進入文字層的修法；沒有、不修文字、先重新檢討寫它的動機。這一條決定註解該不該存在、其餘原則決定它該怎麼寫、順序顛倒會把力氣花在修一則不該存在的註解的文字上。詳見 `references/writing-code-comments.md` 的最高原則節。

**註解的動機先於註解的文字**：準備寫一則程式碼註解時，先問寫它的動機是「說明這裡在做什麼」還是「怕有人改壞它」。後者不是註解問題——散文型註解不參與執行、改壞的當下不產生任何訊號，而做批次整理與自動化重構的人不會經過那一行。處置是先問那個約束能不能被消除（它通常是某個結構選擇的產物），不能消除才交給會發聲的機制；判準是問這段資訊有沒有對應的斷言（存不存在一條會紅的斷言，不是造不造得出句子），驗證是當場把約束破壞掉、跑測試、把輸出貼出來。詳見 [protective-comment-signals-missing-enforcement](references/principles/protective-comment-signals-missing-enforcement.md)。

**知識卡建卡判準用「最不熟悉的讀者」**：知識卡的建卡判準是「目標讀者群裡最不熟悉的那端能不能理解這個術語」，不是「作者覺得夠不夠常見」。常識是相對於背景的——.htaccess 對 PHP 工程師是常識、對 Node.js 工程師完全陌生。跨背景讀者群的教材裡，幾乎所有領域特定術語都需要建卡。建卡的邊際成本低（40-50 行）、讀者缺卡的代價高（離開教材去 Google、可能找到不一致的解釋）。per [常識是相對於讀者背景的](references/principles/common-knowledge-is-relative-to-reader-background.md)。

**操作步驟帶環境專屬工具路徑**：操作型文章的每一步至少帶一條工具路徑（用什麼軟體、輸入什麼指令）。同一個動作在不同環境（container / VM / 共享主機）的工具路徑可能完全不同——「拍下現況」在 container 是 `docker commit`、在 VM 是 AMI 快照、在共享主機是 FTP mirror + phpinfo。文章涵蓋多種環境時、每一步要按環境分列工具、或標明適用環境。自測問題：「讀者坐在電腦前，下一個動作是打開什麼軟體？」答不出來就是缺口。per [操作指引要帶環境專屬工具路徑](references/principles/operational-how-needs-environment-specific-tooling.md)。

**Case 引用段落的三段式結構**：三段式是案例引用段落的順序紀律 — 把「概念 → 案例 → 操作」三層分開承擔（段首給概念定義、case 引用居中、通用工程知識展開）、讓段落結構跟讀者學習新概念的認知順序對齊。LLM 從 case 反推內容容易把 case 揭露當概念出發點、實證觀察 11/12 段都犯這個錯。詳見 [case-citation-three-part-structure](references/principles/case-citation-three-part-structure.md)。

**知識目標決定文章結構**：文章寫完後讀者帶走的是判斷能力（面對新情境能自己評估）還是操作步驟（照做能解決特定問題）——兩者需要不同的結構。判斷力導向把機制理解當主線、操作當自然推導的結果；流程導向把步驟當主線。多數教學文章應走判斷力導向——文章的價值在於提供判斷力、這是官方文件不做的事。詳見 [teach-judgment-not-procedure](references/principles/teach-judgment-not-procedure.md)。

**判準寫到條件層**：判準有三個成熟度——口訣（無推導的結論）、維度清單（「判斷看 A / B / C」）、條件映射（「A 成立 → 做 X；A 破 → 切 Y」加失效情境）——教學要交付到第三層。維度清單是判準的空殼：有判準動詞、每個維度都有機制支撐、通過字句與機制審查，卻在讀者要做決定的那一刻斷線；且機制重建完成後它仍會殘留（機制正確與判準到位是兩個獨立檢查）。驗收用重算測試：讀者帶自己的參數進來能不能走出行動。條件不可窮舉的決策，用自查問句組（把變數轉成讀者可自答的問題）＋排序規則，同樣算第三層。詳見 [criteria-need-condition-action-mapping](references/principles/criteria-need-condition-action-mapping.md)。

**教學模組要有推導源頭**：分析導向的教學模組（判準密集、讀者要帶走判斷力），模組級結構要是推導體系、不是主題集合——一個源頭機制（成本結構 / 約束 / 生命週期，各篇判準能折算回去的基準）、每篇承擔一條展開、模組入口能一句話說出推導起點。源頭買到：判準同尺、跨篇矛盾現形、擴篇有掛載點、推導式閱讀路線成立。目錄型模組與異質 case 記錄不適用；源頭是折算基準、不是開場模板。詳見 [teaching-module-needs-derivation-anchor](references/principles/teaching-module-needs-derivation-anchor.md) 與 `references/managing-article-collections.md` 的對應段。

**複合問題先拆機制再談交互**：問題由多個概念交互導致時、先各自教 A / B / C 的機制、再談 A×B×C 交互。讀者理解各元件後交互作用是自然推導的。各概念獨立成篇、文章之間用連結而非重複來串接。判讀訊號是文章裡出現「另外還有一個原因是...」的堆疊式展開。詳見 [compound-problem-decompose-then-interact](references/principles/compound-problem-decompose-then-interact.md)。

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

| 觸發情境                                                                                                                                                                              | 讀哪份 reference                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 要寫或改一段程式碼註解 / doc comment                                                                                                                                                  | `references/writing-code-comments.md`                                                                              |
| 要起草 / 改寫一份文件（worklog、spec、README）                                                                                                                                        | `references/writing-documents.md`                                                                                  |
| 要設計 log / 錯誤訊息 / 結構化輸出                                                                                                                                                    | `references/writing-logs.md`                                                                                       |
| 要撰寫給 AI 的 prompt / instruction / Agent 派發 / Ticket Context Bundle                                                                                                              | `references/writing-prompts.md`（為 `.claude/rules/core/ai-communication-rules.md` 的詳細版庫，portability-allow） |
| 要撰寫完整長篇技術文章（blog post / post-mortem / 架構決策 / 除錯復盤 / 技術評估）                                                                                                    | `references/writing-articles.md`                                                                                   |
| 要把外部分析文章 / 產業評論 / 投資人備忘錄 / 高密度研究材料轉成教學型分析文章，把從業者經驗談（訪談 / 社群貼文 / 口述）轉成分析教學（機制重建），或把 AI 改寫稿從摘要升級成可遷移框架 | `references/source-to-teaching-analysis.md`                                                                        |
| 要翻譯 / 轉譯文章、把英文材料改寫成中文、檢查術語誤譯或中文譯名放回句子後是否成立                                                                                                     | `references/translation-review.md`                                                                                 |
| 要管理多篇相關文章的結構（系列、文集、知識庫、素材庫比例、MOC、跨篇引用、何時抽抽象層 / Pattern 卡片）                                                                                | `references/managing-article-collections.md`                                                                       |
| 要做文章 / 模組 / 系列的結構決策（該不該拆篇、擴充點設計、方法論與案例的依賴方向、多讀者分流）、或用結構原則 review 既有文集                                                          | `references/structuring-with-solid.md`                                                                             |
| 要對既有高 stakes 內容（資安 / concurrency / distributed / financial / medical）做 reviewer-style audit、找 false sense of security / 對位失效 / context 缺 / citation 過時           | `references/auditing-articles.md`                                                                                  |
| 要寫或檢查判讀 / 選型 / 決策類內容（回答「該怎麼判斷」那一層），或讀者提問「什麼情況會需要這個」「什麼樣的系統會這樣做」「沒有範例看不懂」                                            | `references/judgment-content-needs-scenarios.md`                                                                   |
| 要設計 ticket 欄位 / schema frontmatter / 表單欄位                                                                                                                                    | `references/designing-fields.md`                                                                                   |
| 想驗證寫作品質（認知負擔、獨立理解率）                                                                                                                                                | `references/meta-metrics.md`                                                                                       |
| 要新增或修改一份 Skill reference（撰寫品質規範、結構標準）                                                                                                                            | `references/reference-authoring-standards.md`                                                                      |
| 要驗收 Skill 發布品質（語意層驗收、Phase 2 dry-run）                                                                                                                                  | `references/dry-run-guide.md`                                                                                      |

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
  - **正向陳述優先 grep**：`rg "不[行可是要能該支對符夠必]|無法|沒[做有]|而非|而不是"`、加上**否定起手定義句**（原 pattern 漏「而是」、抓不到「不是 X、而是 Y」的後半）：`rg "不是.{0,30}而是|不是.{0,20}、是|不是.{0,25}，\s*是|與其.{0,20}不如|不只.{0,15}更"` — 主要敘述要正向、反例對照的少量負向可保留；判別在「核心概念第一次正面出現在句首、還是被擠到『而是』之後」
  - **口語修辭 grep**：`rg "其實|實務上|真的|碰巧|立刻撞牆|沒事"`
  - **地區用語 grep**：單詞層 `rg "集群|默認|質量|視頻|函數|文件夾|接口"`（封閉集合、掃得到）；慣用語層 `rg "拍腦袋|拍板|靠譜|給力|接地氣|一波|死磕|躺平|內卷"`（已知個案、**非窮舉**——慣用語是開放集合、grep 追不完、新個案要靠目標地區讀者冷讀，同源 reviewer 回報「地區用語 clean」對慣用語層不可當真，見 [`regional-idioms-evade-keyword-bank`](references/principles/regional-idioms-evade-keyword-bank.md)）
  - **廢話前綴 grep**：`rg "值得注意的是|需要說明的是|實際上|基本上|事實上"`
  - **裝飾符號 grep**：`rg "✅|❌|⚠️|🚨|🟡|🟢|⭐|📌|✓|✗"`
  - **對讀者喊話 grep**：`rg "很多人|大家|不少人|你的|你在|你把|你正在|你補|你天天|你會|你可能|先讀懂|先釐清|別搞混|別被"`（**裸「你」非窮舉**：實測過 `你正在`、`你補完` 這類「你 + 一般動詞」逃過原 pattern，回報 clean 前另跑一次裸 `rg "你"` 逐處判定） — 教材中性陳述、不安撫情緒 / 不第二人稱代入 / 不祈使控制閱讀（hook / narrative 段落輕度第二人稱可留）。**裸所有格 / 主詞（你的 X / 你在 X）也算、不限「你 + 動詞」的祈使 / 預測句型**；grep 對裸『你』非窮舉、真防線是 reader-simulation 冷讀（同源 grep 抓不到 register、見 [multi-pass-review-frame-granularity](references/principles/multi-pass-review-frame-granularity.md)）
  - **自評誇飾 grep**：`rg "教科書級|堪稱|可謂|完美|經典|範本級|大師級|漂亮地|優雅地|最佳實踐|best practice"` — 品質 verdict 頂替技術理由、換成機制 / 條件
  - **必然性框架 grep**：`rg "天生|與生俱來|本質就是|本來就是|必然|唯一|註定|理所當然"` — 把設計選擇講成自然法則、還原成條件性（物理 / 法律 / 數學事實除外）
  - **澄清式框架 grep**：`rg "最容易誤|容易誤判|常見的?誤判|要點破|直覺會?帶偏|抵抗.*的直覺|你以為|會困惑|值得記"` — 把「讀者會誤解」當敘事中心是知識缺口訊號、不是澄清時機；補正向模型與機制讓誤解無從發生、不提醒讀者一個他本不需要有的困惑。界線是具體第一人稱實測敘事跟真實診斷區分（逾時 vs 被拒、症狀層 vs 根因層）保留、只有把假想誤會當主題句起手的才改；同義變體多、grep 抓不全、靠 reader-simulation 語意判定（「這段在補正向知識、還是在提醒讀者會犯錯？」）。見 [fill-knowledge-gap-not-center-misconception](references/principles/fill-knowledge-gap-not-center-misconception.md)
  - **歸因語氣 grep**：`rg "承認|暴露了|證明了失敗|被迫"` — 描述系統行為用「信號」「反映」「顯示」等中性觀測詞、避免「承認」「暴露」等責任歸因詞；「被迫」在描述外部強制約束時可保留
  - **宣導語氣 grep**：`rg "你可能沒注意|你可能不知道|想像一下|把.{1,5}想成|跑得好好的|聽起來很|其實很簡單|說穿了就是|等於拆未爆彈|乾瞪眼|延遲引爆"` — 預設讀者無知或用情緒管理取代事實陳述；讀者是專業人士、直接描述情境與後果
  - **泛用詞濫用 grep**：`rg "坑|東西|搞|弄|處理一下|情況"` — 同一個泛用詞蓋過不同具體情境時、依情境換精確詞（意外 / 陷阱 / 出問題 / 發生狀況）；命中密集且各指不同事才算違規、真泛指 / 引號引用 / 輕度 hook 合規；「坑」另有地區偏移面（某些地區高頻、某些少用）。見 [avoid-overused-generic-words](references/principles/avoid-overused-generic-words.md)
  - **敘事姿態 grep**：問句標題 `rg "^title:.*[？?]"`、問句段標 `rg "^#{2,} .*[？?]"`、敘事轉折詞 `rg "才想清楚|還是被退|我到底|我於是"`、輔助訊號是檢討類文章的「我」密度顯著高於同類其他篇 — 教學與檢討內容寫給帶問題來的讀者、標題承載結論、判準由推導交付（不設懸念、也不把結論抽到開頭灌輸）、檢討用客觀條件視角；操作型自問句（判準的執行步驟）與「」內引用合規、標題 / 段標 / 結論位扣住答案的問句違規、未經推導的開頭結論摘要與欄位組同屬違規；這類是生成端高頻默認、審查是補位、防線主力在生產側規範與模板。見 [write-for-readers-not-audiences](references/principles/write-for-readers-not-audiences.md)
  - **用詞搭配錯位 grep**：`rg "說完的話|背後.{0,8}的話|想告訴|潛台詞|訊號很直接|訊號.{0,4}很直接"` — 把抽象概念（角度 / 框架 / 訊號 / 數字）配上不貼合屬性的謂語：擬人化錯配（角度不會「說」、數字不會「想告訴」）與形容詞錯配（訊號的可辨識度是「清晰 / 明確」不是「直接」）。無穩定關鍵詞、grep 只抓已知形態、真防線是異源冷讀（跟 register 類同屬同源盲區）。見 [word-choice-fits-concept-attributes](references/principles/word-choice-fits-concept-attributes.md)
  - **這些 grep 曝光候選、不做自動判定**：命中後要不要算違規有品味核心；且 LLM reviewer 跟作者共享文體、同源自審對 register 類（否定起手 / 喊話 / 誇飾 / 概念前置）有結構上限 ——「不是 X、而是 Y」這種 LLM 高頻自產句型最容易全員放水。grep + 同源判定只負責曝光候選、register 層的真防線是文體異源視角（human cold-read 或 prompt 採「挑剔否定起手 / 概念後置」對抗姿態的 reviewer）、同源回報的「clean」不可當真

詳細各維度的判讀規則跟修法、見對應 reference（writing-articles / writing-documents 等）跟 principles 目錄內的 cadence-homogenization / colloquial-rhetoric / regional-terminology / decorative-symbols / multi-pass-review-frame-granularity 等原則卡。

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
    ├── writing-code-comments.md          # 情境 1：程式碼註解（含「動機先於文字」前置分岔）
    ├── writing-documents.md              # 情境 2：文件撰寫
    ├── writing-logs.md                   # 情境 3：log 輸出
    ├── writing-prompts.md                # 情境 4：prompt 撰寫
    ├── writing-articles.md               # 情境 5：完整長篇技術文章
    ├── source-to-teaching-analysis.md     # 情境 5a：外部分析材料 → 教學型分析文章
    ├── translation-review.md             # 情境 5b：文章翻譯 / 轉譯的句內邏輯 review
    ├── managing-article-collections.md   # 情境 5c：跨多篇文章的結構（三層、素材庫比例、MOC、Pattern 卡片）
    ├── structuring-with-solid.md         # 情境 5d：結構決策判準（SOLID 寫作映射：拆分 / 擴充點 / 依賴方向 / 讀者分流）
    ├── judgment-content-needs-scenarios.md # 情境 5e：判讀 / 選型類內容補情境與後果（形態 / 觸發事件 / 微案例、含正反例四組）
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

**Last Updated**: 2026-08-08
**Version**: 0.50.1 — `writing-documents.md` 的 Cross-reference format 表格：同目錄示範路徑被 broken-link 掃描判為斷鏈（原檔以自然語言註解說明「這是佔位路徑」，掃描器不解析自然語言）。改用 `broken-link-exempt` 行內 marker 顯式 opt-in 豁免（marker 僅作用於所在行），說明文字保留。
**Version**: 0.50.0 — 兩項、皆由使用者對 v0.49.0 改寫成品的判定觸發。(1) 新增 `assertion-list-needs-reader-walkthrough` principle 卡 + 原則三「斷言清單要過重建測試」段：「三個毛病」式條列讀者只能硬記或盲信（正文沒給能重建結論的材料）、改寫成讀者位置的走查（讀者位置、動作加材料、結論後置）被判定「說得清楚非常多」、固化成寫作模式；含 before / after 對照範例、重建測試判準、審查 grep（拆開來看 / N 個毛病）。(2) `writing-code-comments.md` 頂端新增「最高原則：先評商業邏輯、再談文字」節 + 自檢清單首題：檢視註解的第一個評估是它有沒有解釋到這個行為 / 事件 / flag 的商業邏輯、沒有就不修文字、先重新檢討動機——這條決定註解該不該存在、其餘原則決定怎麼寫；SKILL.md 原則三同步加對應段。

**Version**: 0.49.0 — 敘事姿態原則補「灌輸與懸念是同一個缺陷的兩個方向」：v0.48.0 立規範時把修懸念寫成「判準放開頭」、實際套用被使用者指出正是另一個方向的錯——把結論抽成開頭一段（或「觸發場景 / 整理目的 / 本文邊界」欄位組）直接給、推導擺後面、讀者沒有推導可依附只能硬記；概念要由讀者沿著推導自己長出來、不是被交付。分工修正為：標題承載結論（檢索錨）、開頭承載情境定位、判準在推導走完的位置浮現。principle 卡與 keyword bank 同步、徵兆表加「開頭有未經推導的結論摘要或欄位組」一列。同時示範性修正：把「三個毛病」式的斷言清單改成給讀者推導材料（例：「入口是自創行話」要附上實際進入點的程式碼對照、讓讀者自己看出註解與程式斷線）。

**Version**: 0.48.0 — 新增 `write-for-readers-not-audiences` principle 卡、原則三加「教學與檢討內容的敘事姿態」段、keyword bank 加「敘事姿態」grep（問句標題 / 問句段標 / 敘事轉折詞 / 「我」密度）。從一篇檢討文章的事故抽出：問句標題、懸念段標、第一人稱事件敘事、判準壓在全文後半，經過多輪 reviewer audit 零 finding、由異源讀者指出。根因三層——規範缺位（規則不存在時 compliance reviewer 產生不了 finding）、frame 射程（keyword bank 枚舉不含懸念與第一人稱、persona 檢查掛在批次流程而單篇不進）、同源文風默認（問句標題與三幕劇是生成端高頻默認）。防線主力放生產側（本段與模板）、審查 grep 是補位；判別線是位置——操作型自問句合規、標題 / 段標 / 結論位扣住答案的問句違規。

**Version**: 0.47.0 — 新增 `protective-comment-signals-missing-enforcement` principle 卡，並在 `writing-code-comments.md` 的自檢清單之前插入「動機先於文字」節。補的是該 reference 的結構性缺口：五條原則、十列禁止模式、八題自檢清單的問法全是「這則註解寫了什麼」，沒有一處問「為什麼要寫」——於是一行動機是防護的註解可以通過全部檢查而仍然是錯的窗口，而 skill 會把那個循環複製到每個裝了它的專案。實測來源是同一行 doc 被 review 退兩次、第二版寫的是真實存在的跨函式讀寫順序約束仍被退，兩次的判斷對象都是文字。卡片含動機判準的三個弱點（回溯建構、混合動機、防衛性回答）、二元判準掛在斷言存在性而非造句能力、破壞實測作為收斂條件與各步驟的痕跡設計、以及四條邊界。禁止模式清單加一列（防護意圖寫成註解）、自檢清單加一題（動機是說明還是防護、且排在最前）。

**Version**: 0.46.0 — `judgment-content-needs-scenarios` 新增「第六種產出：共同前提沒有住址」。前五種都對單篇操作，第六種只在把幾篇並置之後才出現——同一個判斷被三篇以上當前提引用而沒有任何一篇承接。它在單篇視角下不落空（每篇都給了自己那一角、讀者當下走得下去），所以逐篇檢查看不到；前置段是最常見的藏身處，因為它確實是本篇的適用性閘門，「撞到不屬於這篇的內容」那條不觸發，辨識訊號是那一段回答的問題比本篇主題更早發生且對別篇同樣成立。含缺卡與缺章的分界（定義重複＝術語、判斷的各角重複＝缺章，因為取捨需要並置）、三篇門檻的理由、以及處置（新開一篇、各篇那一角壓成一兩句加路由留著當閘門、新篇要標明自己是誰的上游）。

**Version**: 0.45.0 — 依 #245（原則層與操作層會漂移）規定的反向核對，從本 skill 出發逐條回查對應原則卡的現況，抓到兩處漂移並修正：微案例的挑選規則補「一兩個是上限而非配額、有兩個以上只寫一個要就地寫出漏選理由」（卡片 Round 1 就加了、skill 停在原版，導致實測九則微案例零套用）；出口盤點的單位從「三種」改成規則（卡片 Round 3 已改——判讀表的列、風險邊界的條、out-of-scope 每一項宣告都算，只有微案例末端要等第二階段）。兩處都是四輪十四個 reviewer 沒抓到的，因為沒有任何一輪被要求並排比對兩個 surface。

**Version**: 0.44.0 — 多輪審查 Round 1 修正 `judgment-content-needs-scenarios` 的出口盤點段：原本主張「盤點要排在補範例之後、先盤會盤不出東西」，reviewer 用該段自己的定義推翻——三種盤點單位裡有兩種（判讀表每一列 / 風險邊界每一條）在任何範例存在之前就存在，只有第三種（微案例末端的止血句）依附於範例。改成**跨兩個階段各跑一次**：讓缺口現形的是換視角這個動作本身（既有維度都在驗已寫內容對不對），範例的貢獻是多出一類單位而非解鎖整個盤點。同批實測另證：七處缺口裡只有兩處依附微案例。

**Version**: 0.43.0 — `judgment-content-needs-scenarios` 新增「出口盤點：補完範例之後才做得了」段，把補寫程序從三步（形態 / 觸發事件 / 微案例）延長成四步、補上閉環：補完範例後改用「讀者知道這是問題了他去哪解決」掃全文。順序不可顛倒——分析型句子不會產生「所以呢」這個追問，段落寫得越好讀者越認同問題、而認同的下一步是想知道怎麼解；沒有範例時讀者與作者都停在理解層，範例把讀者推到行動、而只有行動這一端會撞到出口不存在。檢查單位是每個被提出的問題（判讀表每一列 / 風險邊界每一條 / 微案例末端那句「補起來要……」）而非每篇文章——文末路由段回答不了段落層級的問題。四種狀態各有處置，其中「不存在且需完整推導」要明說它不存在（讀者找不到時的預設歸因是自己沒找到）。另補反模式：替換微案例前先掃第四拍，止血代價常是全篇唯一寫出止血路徑的地方、而替換理由只評估前三拍。從 7.28 / 7.29 補完範例後盤出七處缺出口的實測抽出。

**Version**: 0.42.0 — `judgment-content-needs-scenarios` 新增「補形態會暴露出這一列沒有解法落點」段（逐篇檢查的第五種產出）：補形態要回答「讀者對號入座之後去哪」、而判讀表不問這個問題，缺落點的列因此在補形態時才現形；辨識訊號是同一張表的列與深化段不對稱（實測五列的表只有四列有深化段），而欄位齊全正是遮住它的原因；與「撞到錯置內容」方向相反（那是多了不該有的、這是少了該有的），處置用最小可行答案判準——能一段話加連結讓讀者繼續走就當場補判讀層那一節、需要完整推導的只登記待辦並明說目前沒有對應章節（讀者找不到時的預設歸因是自己沒找到）。從 7.2 補形態時發現「授權範圍擴張過快」五列中唯一沒有深化段的實測抽出。

**Version**: 0.41.0 — 多輪審查 Round 3 回饋修正 `judgment-content-needs-scenarios`：新增「四拍要有來源」硬條款——四拍要出自親歷 / 案例庫已記形態 / 機制上必然，第三拍是唯一推不出來的那一拍、推不出來就代表無經驗的作者或生成工具只能發明它、而模板不會擋下發明，寫不出來時留白比杜撰好（編造的盲區比沒有微案例更難被後續審查推翻）；連帶排程後果「一輪之後所有章節都有微案例＝照模板填的訊號」。地基斷言從二元改成單峰：可用程度中段最高、零經驗端缺的是術語入口而非情境（單峰模型解釋得了「判定不需補時改查卡連結」那一段的存在，單調模型解釋不了）。情境與實作的分界從內容類型改成解析度（判讀層取到成本可感的粒度就停、用內容類型會把成本量級誤判成實作而裁掉）。微案例挑選補「挑選在寫之前做」。

**Version**: 0.40.0 — 多輪審查 Round 1 回饋修正：H1 從「要給系統形態與觸發事件」改成「要給情境與後果」（涵蓋三種補法）；標題去計數（六步程序 → 程序、兩個修法副作用 → 修法的副作用，該檔正在擴充期、步數會變）；補母詞邊界（前兩種是情境／回答進入條件、第三種是後果的敘事化，**不合稱「三種情境」**——避免與上游卡的「情境有兩種」對撞）；第 2 步補可執行 handle（形態句的起手詞有 grep 特徵、本篇找不到樣本時取同分類另一篇）；卡連結落差補機制（絕對數量隨篇幅與術語密度變動、同分類內這兩個變因相近所以落差排除干擾項）；「必然副產物」改「常見副產物」（原句從 n=1 推必然）；四拍第三拍的「最有價值」改成可推導的「最不可省略」（其餘三拍讀者能從機制自行推得、第三拍取決於組織的監控與責任配置）；微案例長度上限兩三句改三四句（與實際試寫對齊）。keyword bank 補兩個實測 pattern 變體：否定起手的全形逗號形式（`不是 X，是 Y`）與裸「你」（`你正在`、`你補完` 這類逃過原 pattern、回報 clean 前要另跑一次裸 `rg "你"`）。
**Version**: 0.39.0 — `judgment-content-needs-scenarios` 補第三種要補的東西：**微案例**（無身分短敘事、兩三句、不帶公司名年份帳目）。原本只有系統形態與觸發事件，兩者都是分類語言、讀者用它們定位自己；沒有經驗的讀者卡在定位之後——知道自己中了但不知道會怎樣，而有經驗的人能自己補這段，所以純分類的內容對資深讀者看起來已完整。四拍寫法（當初為什麼這樣做／什麼時候開始出問題／為什麼沒被及時發現／止血的代價），第三拍最有價值因為它解釋「為什麼不會有人提早警告你」，缺第一拍讀者會覺得是別人才會犯的蠢錯；只挑後果最不直觀的一兩個寫、長度超過兩三句就該進案例庫。與真實案例的分工：剝離身分的原則禁的是搬運帳目、不是禁具體敘事，微案例在章節內讓形態可想像、真實案例在案例庫承擔可查證。六步程序第 4 步從兩個問題改成三個。觸發路由補「沒有範例看不懂」這個讀者提問形態。對應 report 卡 #242。
**Version**: 0.38.0 — `judgment-content-needs-scenarios` 新增「形態的軸取決於讀者當下的變數」：形態不等於架構長相，軸至少三條——**系統架構軸**（讀者已有系統、正決定要不要改）、**團隊狀態軸**（選型類，系統可能還不存在、變數是組織現況）、**關係人約束軸**（對外契約類，變數是對方的能力）；判定「缺形態」前先問這篇用的是哪條軸，只找架構軸會把用其他軸寫成的形態誤判成缺，而誤判成本高於漏抓（漏抓少補一篇、誤判會補出與既有形態並存的冗餘內容、讀者拿到兩套互不相干的分類法）；軸選錯也讓補出的內容不可用。從選型類分類的試作抽出——該篇形態早已存在、只是用團隊狀態當軸，而先前三個分類補的形態全是架構軸、框架因此隱含假設了形態等於架構。
**Version**: 0.37.0 — `judgment-content-needs-scenarios` 新增「逐節讀會撞到錯置內容」：第 3 步逐節讀的必然副產物是發現某節不屬於這篇，辨識訊號由弱到強是「節標題主題不同 → 同分類已有更專門的落點 → **錯置內容篇幅與主體相當或更長**」（實測遇過主體三十餘行、錯置近四十行＝兩篇擠在一起）；處置三規則——標路由目的地不刪（只標「不屬於這裡」會讓修改者選最省力的刪除而非最正確的路由）、登記待辦不當場搬（搬遷要驗證兩端、尺度大於補情境，混做會破壞逐篇檢查可隨時中斷的價值）、前置條件寫明先驗證目的地涵蓋度（目的地已有同主題內容時搬過去是製造重複、比留在原地更糟）。從第三個分類試作抽出。
**Version**: 0.36.0 — `judgment-content-needs-scenarios` 依分類級試作回饋補兩點：第 1 步「判定適用」加**讀者時刻**維度（讀者若已有系統在跑、手上有現象可觀察，給訊號就夠、補形態是冗餘；設計階段的讀者才需要形態；同分類內不同篇可落在不同時刻、逐篇判定），以及新增「判定不需補時，檢查換一個維度」一節（缺形態與缺術語入口是同一問題的兩種形式——讀者都得自己補一塊才能用；判定不需補形態時改查卡連結覆蓋，**同分類內的卡連結數落差是比絕對數量更可靠的偵測訊號**）。從一個三篇分類的完整試作抽出：三篇判定為不需補／不需補／不適用，真缺口卻出現在卡連結上（核心章節的主線術語出現 19 次、連卡 0 次、全篇卡連結數只有同分類其他篇的兩成）。
**Version**: 0.35.0 — Portable 收尾：三張 principle 卡末尾的溯源標註從連結降為純文字 slug（`對應的 blog report 卡 slug 是 \`xxx\``）。這類標註記的是「這張卡從哪抽出來」、不是內容依賴（不點過去也能用卡），但寫成 blog 絕對路徑後複製到別的專案就是死鏈；降成 slug 文字後溯源資訊保留、portable scan 全 clean。
**Version**: 0.34.0 — Portable 修正兩處：三個指向外部 report 路徑的連結（outside-in reader frames / 常識是相對於讀者背景的 / 操作指引要帶環境專屬工具路徑）抽成 `references/principles/` 內的原則卡改相對連結——絕對路徑複製到別的專案後是死鏈，違反 skill 的 portable 邊界，鏡像工具會把相對連結轉回 blog 的 report 路徑、所以公開鏡像不受影響；「跟 multi-round-review 的協同」段的 principles 指路改成不帶路徑的寫法：原本的 inline code 路徑會被鏡像工具的寬鬆比對命中、卻因為後面接的是卡名清單而非 `.md` 檔名而提取不到 slug，每次同步都產生一則 unresolved 警告；且該路徑在公開鏡像上不存在、對鏡像讀者是死指引。
**Version**: 0.33.0 — 新增 `judgment-content-needs-scenarios.md`（情境 5e）：判讀 / 選型 / 決策類內容要給系統形態（服務設計階段）與觸發事件（服務維運階段），只給機制屬性時讀者必須自己補情境、而能補的人本來就會判斷了；關鍵區分是情境不等於實作（判讀層宣告不展開實作是對的、但情境屬判讀層自己）；含六步程序與四組正反例（機制屬性缺觸發事件 / 分類缺對號入座入口 / 判讀表缺系統形態 / 三種不需要補的情況），以及兩個實測到的修法副作用（補情境會引入第二人稱、原本的封閉計數會失準）；檢查單位是「內容」而非「段落」——分散在別節也算有。從兩篇判讀類章節的實作驗證抽出。同步修正 frontmatter version 欄位與末尾版本紀錄脫節（停在 0.30.0）。
**Version**: 0.32.0 — keyword bank 新增「用詞搭配錯位」grep（擬人化謂語 + 形容詞誤搭：分析角度不會「說」、訊號的可辨識度是「清晰」不是「直接」）、新增 principle 卡 [word-choice-fits-concept-attributes](references/principles/word-choice-fits-concept-attributes.md)；從一次多輪審查中兩處搭配錯位由人類冷讀 catch（agent 同源多輪 register / cadence / 冷讀全漏）抽出，是 register 同源盲區需異源的實例
**Version**: 0.31.0 — `writing-articles.md` 規則二後新增「分析型文章的開頭：定位問題先行、不放敘事或寫作動機」：分析文章開頭第一段直接進定位問題（對象在什麼結構位置、什麼特徵值得判讀），是規則二「商業邏輯先於 CASE」在開頭層的具體形式；抓兩種失焦——敘事性引言（創辦人故事 / 沿革當暖場、對認識有用對判讀沒用）與寫作動機框架（「我們為什麼分析」是編輯層資訊、不是內容層、洩漏編輯決策給讀者）；自檢是拿掉來歷句與動機句後開頭還能不能給出判讀錨點。從商業分析文章的多輪審查回流
**Version**: 0.30.0 — 新增 `structuring-with-solid.md` reference（情境 5d：結構決策判準）：SOLID 五原則的寫作映射——S 一篇一變動理由（拆分測試：變動理由 / 刪除）、O 擴充點設計（管結構骨架、不管敘事內容——顯式劃界避免模板化滑坡）、L 介面承諾 vs 實作履行（title / description / index hook 對內文、同分類功能契約）、I 讀者分流三層（模組路線表 / 文章視角分段 / 術語卡外移）、D 具體依賴抽象（案例引方法論、方法論不反向依賴）；含結構同構表、每原則錯對範例、結構檢查清單（條件 → 行動）、類比邊界三聲明（review 是執行機制 / L 最弱 / 模板化滑坡）。定位在組合層、跟原子化原則分層分工（S 是兩層接縫）。從一次「個體案例 vs 跨個體比較」的實際 SRP 拆分經驗抽出。觸發詞加 SOLID / 文章拆分 / 結構決策 / 擴充點 / 依賴方向 / 讀者分流；metadata.version 同步修正漂移（0.28.0 → 0.30.0）
**Last Updated**: 2026-07-15
**Version**: 0.29.0 — 對讀者喊話 keyword bank 補裸第二人稱（使用者冷讀觸發：一張 report 卡整篇用「你的環境」「你在一台機器」通過作者自審）：grep 加 `你的|你在|你把`、SKILL.md + multi-round-review mirror 同步、principle 卡 teaching-prose-neutral-register 的「第二人稱代入」段補裸所有格 / 主詞例；根因是原 grep `你天天|你會|你可能` 只抓「你 + 明顯動詞」的祈使 / 預測句型、抓不到裸『你的』『你在』——這正是 multi-pass-review-frame-granularity 講的同源盲區（register 類 grep 非窮舉、真防線是異源冷讀），作者自審的同源 grep 漏掉、人類冷讀一眼抓到
**Last Updated**: 2026-07-10
**Version**: 0.28.0 — 從一次教學模組重寫的 before / after retrospective 抽出建構端兩原則（重寫前為經驗談攤平結構、重寫後為推導體系，對比揭露主題集合與空殼判準兩個結構缺陷）：(1) 原則 3 加「判準寫到條件層」——口訣 / 維度清單 / 條件映射三成熟度、重算測試驗收、機制重建完成後空殼仍會殘留（同 batch 兩個版本各踩一次的實證）、自查問句組是條件不可窮舉時的合法變體，新增 principle 卡 [criteria-need-condition-action-mapping](references/principles/criteria-need-condition-action-mapping.md)；(2) 原則 3 加「教學模組要有推導源頭」＋ managing-article-collections 新增對應段——推導體系 vs 主題集合、源頭買到判準同尺 / 矛盾現形 / 擴篇掛載 / 推導式路線四件事、目錄型模組豁免、源頭是折算基準不是開場模板，新增 principle 卡 [teaching-module-needs-derivation-anchor](references/principles/teaching-module-needs-derivation-anchor.md)
**Version**: 0.27.0 — source-to-teaching-analysis 加「Source Type Gate + 經驗談機制重建 pass」（使用者判定觸發：採購 planning 模組被判定「講故事不是商業分析教學」）：轉換第一步判別 source 類型——分析文自帶分析層、走拆層；經驗談（訪談 / 社群貼文 / 口述）只有事實 + 判讀、分析層要重建。機制重建對承擔判準的斷言問四個問題（成本結構 / 閾值反推 / 設計者誘因 / 既有分析語言）、三層分工表（事實保留 / 判讀當 hypothesis / 機制補建）、停止線（氛圍性敘述降 hook、心態內容路由成篇）；自檢清單 + 反模式表同步；新增 principle 卡 [anecdotal-source-needs-mechanism-reconstruction](references/principles/anecdotal-source-needs-mechanism-reconstruction.md)；觸發詞加「經驗談轉教學 / 訪談整理 / 機制重建」；metadata.version 同步修正長期漂移（0.18.0 → 與 changelog 對齊）
**Version**: 0.26.0 — 新增「澄清式框架」字句層 frame（使用者回饋觸發：教材把「讀者會誤解」當敘事中心）：keyword bank 加 `rg "最容易誤|容易誤判|常見的?誤判|要點破|直覺會?帶偏|抵抗.*的直覺|你以為|會困惑|值得記"`、同步 description bank 清單、新增 principle 卡 [fill-knowledge-gap-not-center-misconception](references/principles/fill-knowledge-gap-not-center-misconception.md)（「容易誤會」是知識缺口訊號、補正向模型而非澄清警告、界線是具體實測敘事與真實診斷區分保留）；是 teaching-prose-neutral-register 的 stance 軸之外的知識供給軸 sibling；從遠端 agent 工作機教材三輪 review catch 6 處同構框架抽出（對應 report #215）
**Version**: 0.25.0 — 原則 3 加文章結構上游決策：(1) 新增 principle 卡 [teach-judgment-not-procedure](references/principles/teach-judgment-not-procedure.md)（知識目標決定文章結構、判斷力導向 vs 流程導向、多數教學文章走判斷力導向）；(2) 新增 principle 卡 [compound-problem-decompose-then-interact](references/principles/compound-problem-decompose-then-interact.md)（複合問題先拆機制再談交互、各概念獨立成篇用連結串接）；(3) teaching-prose-neutral-register 補「壓縮結論」共同根因段（喊話/誇飾/必然/恐嚇/威脅/命令/教訓共享「作者走完推導但只輸出最後一步」機制、命名四類違反的統一解釋）
**Version**: 0.24.0 — 地區用語 keyword bank 加慣用語層：新增 `regional-idioms-evade-keyword-bank` portable principle（地區慣用語直譯是開放集合、grep 列舉不完、同源讀得懂會放行、跟 register 同源盲區同構、需目標地區讀者異源冷讀）；地區用語 grep 拆單詞層（封閉、掃得到）+ 慣用語層（拍腦袋/靠譜/給力… 已知個案、非窮舉）；從 devops 容量規劃多輪審查漏抓「拍腦袋」的 self-case 抽出（三輪 agent reviewer 都沒抓到、使用者在地冷讀點出）
**Version**: 0.23.0 — 新增「泛用詞濫用」字句層 frame（讀者回饋觸發：反覆用「坑」把不同情境壓成同一模糊標籤、繁中少用）：keyword bank 加 `rg "坑|東西|搞|弄|處理一下|情況"`、新增 principle 卡 [avoid-overused-generic-words](references/principles/avoid-overused-generic-words.md)（依情境換精確詞、跟 colloquial/regional/cadence 三卡的軸區分）、writing-articles 輪 8 清單同步；命中密集且各指不同事才違規、真泛指 / 引號 / 輕度 hook 合規

**Version**: 0.22.0 — 原則 3 加「知識卡建卡判準用最不熟悉的讀者」；常識是相對於讀者背景的、跨背景讀者群幾乎所有領域特定術語都需要建卡
**Version**: 0.21.0 — 原則 3 加「操作步驟帶環境專屬工具路徑」（同動作在 container/VM/共享主機的工具不同）
**Version**: 0.20.0 — 原則 3 加「讀者定位聲明」生成端前置步驟；從 infra 模組 retrospective 抽出（讀者定位未預設導致宣導語氣通過三輪審查）
**Version**: 0.19.0 — 新增三張 principle 卡（audience-is-professional-not-layperson / cross-expertise-scenario-not-analogy / management-reportable-info-in-technical-content）、原則 3 加讀者定位與跨專業溝通子原則、keyword bank 加宣導語氣 grep；從 infra 教學模組的寫作 retrospective 抽出

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
**Version**: 0.7.0 — Phase B1 結構升級：加第 6 原則「多輪 Re-read Pass」（明示 5 輪 frame）、引用 #83 / #84 / #85 multi-pass 系列。後續 Phase B2 會把各 reference 結尾加「第 2 輪 review checklist」段
**Version**: 0.6.0 — 從 references 過載的反思：writing-articles.md 從 780 行瘦身到 ~530 行（拆分判準 / 三類 structure 模板搬到 managing-article-collections.md、focus 集中在「單篇文章內部」）；新增規則八「自我應用 (dogfooding)」（教某條規則的段落本身遵守該規則）；managing-article-collections.md 整合「拆分判準」+「三層 structure 詳細對照 + 模板」；meta-metrics.md M2 加 dogfooding 失敗訊號
**Version**: 0.5.0 — 從批量改寫 35 篇的經驗回流：原則 3 補「選項數由議題決定、不強湊」（避免 A/B/C/D 強迫症與「實務上幾乎不存在」的假反模式）；writing-articles.md 新增規則九（三類文章 structure 模板）；managing-article-collections.md 新增「跨篇引用 idiom 庫」與「三層 structure 對照」
**Version**: 0.4.0 — 新增 `managing-article-collections.md`（跨多篇文章結構：三層、MOC、Pattern 卡片）；強化原則 1「原子化」（focus 是議題完整度、不是邊界清晰）；強化原則 3「意圖顯性」（機會成本語氣、不用絕對主義）
**Version**: 0.3.0 — 新增 `dry-run-guide.md` 於 Directory Index 與觸發路由（Skill 發布前語意層驗收 Phase 2 dry-run）
