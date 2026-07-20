---
name: multi-round-review
description: "寫多篇章節後做多輪 agent reviewer audit 的標準操作流程。每輪用不同 frame 切換、跨輪 finding 互不重疊、停止訊號是 frame 涵蓋而非 finding 數遞減。Round 1-A 寫作規範 reviewer 必須同步 invoke `compositional-writing` skill 的字句層 keyword bank（正向陳述 / 口語修辭 / 地區用語 / 廢話前綴 / 裝飾符號 / 對讀者喊話 / 自評誇飾 / 必然性框架）、且命中後要做語意判定（命中是候選不是判決）。觸發詞：多輪審查、Round 1/2/3、frame 切換、跨輪審查、reviewer 規劃、何時停止 review、寫作 audit、batch review、cadence 同骨化、enumeration 不窮盡、正向陳述、self-application sweep。Trigger when reviewing multiple writings via successive rounds of agent reviewers."
license: MIT
metadata:
  version: 1.10.1
  category: writing-methodology
---

# Multi-Round Review

寫多篇章節後做多輪 agent reviewer audit 的標準操作流程。每輪用不同 frame、跨輪 finding 互不重疊、至少三輪是硬底線、停止判讀從 Round 3 結束後才開始。已在 backend 5 章（3 輪 9 reviewer 38 finding）和 dotfile 31 篇（3 輪 8 reviewer 43 finding）兩次驗證，Round 3 每次都找出 14 項全新類型的問題。

## 適用情境

- **多篇相關章節**：3+ 章一起寫完、需要跨稿件 audit
- **品質高於速度**：每輪 30-60 分鐘 reviewer + 30-120 分鐘 fix、3 輪約 4-8 小時
- **章節品質敏感**：教學模組、規範文件、長期累積的內容
- **主 context 容量敏感**：reviewer 平行 background 是節省 context 的關鍵設計

不適用：

- **單篇短文**：固定成本（規劃 frame + 跑 reviewer + 整合 finding）對短文 ROI 低
- **快速迭代原型**：流程偏向「寫一次寫好」、不是「快速修改」
- **低風險文件**：個人筆記、草稿、不需要外部 review

## 四大基本原則

1. **每輪用不同 frame**（per [#114 multi-pass frame 顆粒度盲點](references/principles/multi-pass-frame-granularity.md)）：同 reviewer / 同 frame 跑多輪 catch 高度相同。多輪價值在 frame 切換、不在重複加深。
2. **跨輪 finding 互不重疊**：若新一輪 finding 跟上一輪重疊、代表 frame 沒換、再跑無增益。
3. **停止訊號是 frame 涵蓋、不是 finding 遞減**（per [#148 跨輪 review 停止訊號](references/principles/cross-round-stopping-signal.md)）：多輪 review 通常 finding 不遞減、Round 3 可能比 Round 1 / 2 多。停止判讀看「想不出新 frame」。
4. **至少三輪是硬底線**（per [#202 多輪審查至少三輪](references/principles/minimum-three-rounds.md)）：Round 3 的 steelman / outbound frame 覆蓋 Round 1-2 結構性盲區（漏選項、反向引用、搜尋落點、知識卡缺口），歷次實測每輪都找出 10+ 項。Round 1-2 從「已寫的內容」裡找錯，Round 3 從「沒寫的東西」出發——這類問題在前兩輪的 frame 下結構性不可見。「要不要跑 Round 3」不是判讀問題、是執行紀律。停止判讀從 Round 3 結束後才開始。

## 標準流程

### Round 1：Compliance / 基線 audit

最先用「規範遵循」frame、抓 surface 層問題。**Round 1-A 寫作規範 reviewer 啟動時、必須同步 invoke `compositional-writing` skill 的字句層 grep keyword bank**（正向陳述優先 / 口語修辭 / 地區用語 / 廢話前綴 / 裝飾符號）— 寫作規範 audit 漏這層、會把字句層問題推到 Round 2 才被 catch。常見三個 reviewer 平行 background：

- **A: 寫作規範 audit** — 專案寫作規範（如 AGENTS.md / markdown-writing-spec）/ compositional-writing 規範遵循
  - **字句層 grep（必跑）**：
    - 正向陳述優先：`rg "不[行可是要能該支對符夠必]|無法|沒[做有]|而非|而不是" <files>` — 不主導段落的少量負向（反例對照）可保留、主要敘述要正向
    - 口語修辭（#111）：`rg "其實|實務上|真的|碰巧|立刻撞牆|沒事" <files>`
    - 地區用語（#112）：單詞層 `rg "集群|默認|質量|視頻|函數|文件夾|接口" <files>`；慣用語層 `rg "拍腦袋|拍板|靠譜|給力|接地氣|一波|死磕|躺平|內卷" <files>`（已知個案、**非窮舉**——慣用語是開放集合、同源 reviewer 對這層有結構盲區、回報「clean」不可當真、新個案要靠目標地區讀者冷讀；見 compositional-writing 的 `regional-idioms-evade-keyword-bank` principle）
    - 廢話前綴：`rg "值得注意的是|需要說明的是|實際上|基本上|事實上" <files>`
    - 裝飾符號：`rg "✅|❌|⚠️|🚨|🟡|🟢|⭐|📌|✓|✗" <files>`
    - 對讀者喊話：`rg "很多人|大家|不少人|你的|你在|你把|你天天|你會|你可能|先讀懂|先釐清|別搞混|別被" <files>` — 教材中性陳述、不安撫 / 不第二人稱 / 不祈使（hook / narrative 輕度第二人稱可留）；裸所有格 / 主詞（你的 X / 你在 X）也算、grep 對裸『你』非窮舉、register 類真防線是異源冷讀
    - 自評誇飾：`rg "教科書級|堪稱|可謂|完美|經典|範本級|大師級|漂亮地|優雅地|最佳實踐|best practice" <files>` — 品質 verdict 頂替技術理由
    - 必然性框架：`rg "天生|與生俱來|本質就是|本來就是|必然|唯一|註定|理所當然" <files>` — 把設計選擇講成自然法則（物理 / 法律 / 數學事實除外）
    - 泛用詞濫用：`rg "坑|東西|搞|弄|處理一下|情況" <files>` — 同一個泛用詞蓋過不同具體情境時、依情境換精確詞（意外 / 陷阱 / 出問題 / 發生狀況）；命中密集且各指不同事才違規、真泛指 / 引號引用合規；「坑」繁中少用
  - **命中是候選、不是判決**：grep 命中後仍要一個語意判定步驟——這個命中是「建立核心概念的違規」（段首 / 小節開場）、還是「合規的反例對照 / hook / 真必然」。reviewer 容易把違規合理化成「可接受對照」放行（偵測成功、判定失敗）；判定用「概念位置」、不用「有沒有對照意味」。回報「字句層 clean」前先確認 clean 不是判定放水。**register 違規（否定起手 / 概念前置 / 喊話 / 誇飾）有判定上限**：它的偵測可機械化（grep 抓得到句型）、但判定要讀懂「讀起來對不對」、無法 regex 化；而且 LLM reviewer 跟作者共享文體直覺 ——「不是 X、而是 Y」這種 LLM 高頻自產的定義句型全員讀起來「自然」、同源自審對這類有結構上限、加再多輪都跨不過。register 層的真防線是文體異源視角：external human cold-read、或 prompt 明確採「挑剔否定起手 / 概念後置」對抗姿態的 reviewer。同源 reviewer 回報的「register 層 clean」不可當真、要標「未經異源抽查」。但要分清子集：「重點優先 / 否定起手」（不是 X 而是 Y、與其 X 不如 Y）有可操作判準 —— 逐句問「核心概念第一次正面出現在句首、還是被擠到『而是』之後」、強制執行這個機械步驟就抓大部分、異源只補殘餘；真正主要靠異源的是喊話 / 誇飾這類無單一重點位置的 register。別把「有可操作判準卻沒執行」（execution gap）誤當「判定不可機械化」（design 上限）。
  - 詳細 grep keyword bank 跟 frame 路由見 [`compositional-writing` skill](../compositional-writing/SKILL.md)。
- **B: 案例 / fact-check audit** — 案例引用準確性、編號 mis-cite、跨章節引用；**教學層 case 引用的敘事重量**（per [教學層引用剝離身分與規模](references/principles/teaching-cite-strips-identity-and-scale.md)）——教學文引用 case 的段落逐句掃事件帳目（票數 / 案例數 / 版本號）、規模鋪陳、產品身分與領域功能詞、這些的住址在 case 記錄原文；finding 的建議修法先給「刪」、刪不動才泛化成無身分載體（「一個專案」「一筆資料」）、通用化帳目（113 張 → 上百張）是半吊子修法——前情提要仍在、只是變模糊；判定用「拿掉後論證還成立嗎」的機械測試、不用「規模感幫論證」的直覺（作者與同源 reviewer 共享此直覺、準確性審查攔不到——數字是準確的、只是不該在教學層）
- **C: 跨章一致性 audit** — 編號、學習路線、模組整合、frontmatter 一致（含 description recall trigger 檢查：description 是否回答「什麼情境下需要回來讀」而非只摘要內容，per [description-as-recall-trigger](references/principles/description-as-recall-trigger.md)）
- **D: Downstream-task audit（outside-in）** — 讀者讀完後的下一個動作是什麼？他需要什麼素材才能完成那個動作？技術文章的讀者常見的下游任務是「向管理層提案」「估算時程」「選型決策」——文章如果只講技術做法、缺成本量級 / 時程估算 / 進度指標 / 決策簽核點，讀者學會了做法卻推不動。操作型文章的下游任務是「照做」——如果步驟停在 WHAT 層沒到 HOW WITH WHAT（具體工具 / 指令），讀者知道該做什麼但不知道用什麼做。per [outside-in reader frames report](/report/review-lacks-outside-in-reader-frames/)
- **E: 斷言支撐 / 知識類型 audit** — 字句、cadence、讀者旅程、steelman 都在文字表面與結構層操作、對「整個模組是錯的知識類型」結構性不可見：一個模組可以每句合規、每個結構到位、整體卻是結論都在 / 支撐全缺的經驗談。兩層檢查：**斷言層**——每篇抽 3-5 個承擔判準的核心斷言、問「靠什麼成立：機制推導 / 量化 / 可驗來源 / 實機驗證、還是口吻與權威（『厲害的人都這樣』『經驗上如此』）」；數字閾值（「不超過七成」）要問「推導在哪、讀者換情境能重算嗎」——標了約數不等於有支撐、這是斷言支撐跟 steelman「閾值有無源頭」的差別（句子層誠實 vs 判準層可推導）。斷言層還要驗**判準成熟度**：判準句停在維度清單（「判斷看 A / B / C」、動詞是看 / 考慮 / 取決於而沒有「→ 就」的映射）是判準的空殼——有機制支撐仍可能空殼（機制正確與判準到位是獨立檢查）、驗收用重算測試（讀者帶自己的參數能不能走出行動）。**模組層**——模組的知識類型（分析 / 敘事 / 操作）跟所在分類的定位與 sibling house style 一致嗎（分類有算式與結構分析、新模組全篇敘事即失配）；分析模組另問**推導源頭**存不存在：模組入口能不能一句話說出推導起點、任選一篇的核心判準能不能折算回共同機制——答不出來是主題集合訊號、跨篇判準矛盾在這種結構下不可見。素材來源是經驗談 / 訪談 / 口述的 batch 為高風險、此 frame 必排第一輪——知識類型錯位的修法是重寫、越晚抓字句層打磨全作廢。支撐類型依知識目標判定（操作型=實機驗證、分析型=機制與量化）、心態 / 生態類內容標明定位分離即可、此 frame 不適用。per [claim-support frame](references/principles/review-needs-claim-support-frame.md)

預期 finding 類型：編號錯、broken link、案例 mis-citation、規範違反、字句層負向 / 口語 / 廢話、cadence 散點、**成本 / 時程 / 工具缺口**、**斷言支撐缺失（訴諸權威 / 無推導閾值）、模組級知識類型失配**。

### Round 2：Cadence / 讀者旅程 frame

修完 Round 1 後、改用「字句層 + 讀者體驗」frame：

- **A: Cadence + 字句層** — 句型同骨化（per [#122 cadence 同質化](references/principles/cadence-homogenization.md)）、廢話前綴、口語修辭、地區用語。**修 cadence 時警惕反噬**：為破舊模具而立的生成端規則（如「段首一律目標詞先行」）若均勻套整批、會複製出比原模具更密的新模具、且同源自審在「已修」錯覺下看不到——修法要輪替多個 framing、修完把修法產物納入整組重掃（per [均勻修法複製新模具](references/principles/uniform-remediation-recreates-homogenization.md)）
- **B: Reader simulation 旅程審查** — 假裝特定讀者類型（如「剛從入門影片進來的開發者」）、實際走學習路線、看入口判讀 / 內容門檻 / 跳出訊號。**Reader-persona register 適配**：指定具體讀者角色後，額外問「這個人讀到這段會覺得被低估嗎」。**術語知識卡覆蓋**：假裝讀者群裡最不熟悉的那端（如 Node.js 工程師讀 PHP 教材），逐一掃描文中術語——任何讓該讀者需要去 Google 的術語都是知識卡缺口。常識是相對於讀者背景的、作者和同源 reviewer 共享的「常識」盲區需要這個 frame 才能 catch。per [常識是相對於讀者背景的](/report/common-knowledge-is-relative-to-reader-background/)——宣導語氣（故事帶入、比喻堆疊、「你可能不知道」）對專業讀者是 register 失配，keyword bank 抓不到（字面合規）、同源 reviewer 容易放行（共享「故事帶入是好教學」的直覺）。per [outside-in reader frames report](/report/review-lacks-outside-in-reader-frames/)
- **B″: Executable walkthrough（操作型文章專用、outside-in）** — 假裝讀者從零照做、每一步問「下一個動作是打開什麼軟體、輸入什麼指令」。任何一步答不出來就是工具缺口。操作步驟在邏輯層正確（fact-check 通過）但缺工具指引（讀者無法執行）是 inside-out review 的結構性盲區。**環境分支**：同一個動作（「拍下現況」「匯出資料庫」「建立備份」）在不同執行環境（container / VM / 共享主機）對應完全不同的工具路徑，只寫一種環境的做法會讓另一種環境的讀者卡住。如果文章涵蓋多種環境、每一步要按環境分列工具或標明「本篇適用 X 環境、Y 環境見另一篇」。同根因容易被指出兩次——第一次補了工具名稱、第二次才補環境替代路徑。per [操作指引要帶環境專屬工具路徑](/report/operational-how-needs-environment-specific-tooling/)。非操作型文章（概念型 / 溝通型）不需要跑此 frame
- **B′: 冷讀 / 零脈絡單卡落地審查** — 假裝讀者**經搜尋或直連落在單一篇章**、毫無 section 與前後文脈絡，逐篇冷讀。專抓「洩漏撰寫者預設前提的行話」（如未定義就出現的「家族」「上述框架」「如前所述」）與「缺『為何讀這篇 / 何時會用到』的進入動機」。與 B 的關鍵差別：**B 是讀完全部、走路線的知情讀者，會自動腦補脈絡而看不見行話洩漏；B′ 是零脈絡冷讀者，才會立刻問「這裡突然冒出的 X 是什麼」**。原子化 / Zettelkasten / glossary / 任何可被直連或搜尋單獨抵達的內容，B′ 為必備 frame，不可只靠 B。
- **C: Title commitment + cross-surface** — body 是否對齊 title 承諾、跨 surface（章節 ↔ report 卡 ↔ knowledge card）三角對齊

預期 finding 類型：cadence 同骨化（多篇同位置同句型）、影片詞彙橋斷裂、enumeration 模板化、**行話洩漏（預設脈絡未對冷讀者交代）、單篇缺進入動機**。

> **B vs B′ 盲點（til/terms 實證）**：一組 14 張互連術語卡，知情 reviewer（讀完全部）判讀「讀者旅程」全 A，卻沒抓到每張卡都用「連到家族 / 概念家族」這個只有撰寫者懂的詞——冷讀者落在單卡會立刻卡住。教訓：知情 reviewer 的腦補正是盲點來源；原子內容必跑 B′ 冷讀 frame。

### Round 3：Self-application / Steelman / Outbound frame

修完 Round 2 後、改用「meta / 知識淵博讀者 / 跨章影響」frame：

- **A: Self-application sweep** — 用本 batch 寫的 report 卡 / 規範 self-grep 同 batch 稿件、catch 規範化後仍犯的同義變體（per [#147 規範化跟自審](references/principles/rule-codification-self-audit.md)）
- **B: Steelman / Reality test** — 知識淵博讀者視角、檢查判讀訊號 / 取捨表 enumeration 是否窮盡、有無稻草人、數字 / 閾值有無源頭
- **C: Outbound impact audit** — 既有章節應該但沒引用新章節的反向引用、knowledge card 缺口、跨章節整合段缺位
- **D: Persona coverage（outside-in）** — 列出目標讀者可能進入這套教材的情境（新專案從零開始、接手別人的環境、救火後正規化、被要求稽核合規……），檢查每個情境是否有對應的入口文章。inside-out review 在既有結構內找問題，persona coverage 質疑結構本身的覆蓋範圍
- **E: Search landing 粒度（outside-in）** — 列出讀者可能搜尋的 5-10 個具體問題（如「怎麼輪替 AWS access key」「FTP 站台怎麼做自動備份」），檢查每個問題能不能落在一篇聚焦的文章上、還是被埋在綜述的某個段落裡。跟 B′ cold-read 的差別：B′ 看「落地後讀不讀得懂」、search landing 看「能不能落地到足夠聚焦的內容」

預期 finding 類型：同義變體（grep pattern 漏抓）、enumeration 不窮盡、反向引用斷裂、新概念缺卡、**讀者情境缺入口、搜尋問題缺聚焦文章**。

## Round N 規劃判讀

Round 1-3 是硬底線、直接跑不問。Round 3 結束後才進入「是否需要 Round 4」的判讀。四個停止訊號齊備、停：

1. **新 frame 想不出來**：team 腦力激盪 30 分鐘想不出「能 catch 新東西」的 frame
2. **七軸動完**：per [#126](references/principles/review-seven-axes.md)、frame / instance / surface / scope / cadence / timing / granularity 七軸都用過
3. **Finding 性質退化**：新 frame catch 到的 finding 又退回 surface 層
4. **修法成本反轉**：修一個 finding 成本超過讀者實際感受價值

任二齊備、可以判定「真的夠了」。任一齊備、繼續但要主動規劃 frame 切換。

## Reviewer prompt 結構

每個 reviewer 用 background agent、prompt 結構：

```text
你是 [frame 名稱] 審查員。任務是用 [frame 描述] 對 N 篇稿件做 audit。

# 必讀規範
- [規範檔案清單]

# 審查目標
- [章節 / 報告卡完整路徑清單]

# 審查維度
[3-6 個具體維度、每個帶 grep pattern 或檢查方式]

# 不要做
[排除已被前面 round 覆蓋的維度、避免 finding 重疊]

# 輸出格式
- 嚴重（必修）：違反 [規範]
- 建議（可改）：可優化但非阻塞
最後給「整體評估」分級。
報告 1500 字內、不修檔案。
```

關鍵設計：

- **「不要做」段必填**：排除已被前面 round 覆蓋的 frame、強制 reviewer 進入新維度、避免 finding 重疊
- **平行 background 跑**：3 個 reviewer 同時跑、主 context 節省 ~80% token
- **輸出限長**（1500 字）：避免報告自我膨脹、強制 reviewer 精煉
- **輸出格式是欄位契約**：每個 finding 帶固定欄位（位置、問題描述、嚴重度、建議修法）、下游的整合 punch list 靠欄位運作 — 漏欄位的 finding 整合時只能退回原報告重讀、平行 reviewer 省 context 的效益就被吃掉。位置欄用「檔案 + 段落語意標題」、行號在多 reviewer 平行修復中會漂移
- **SRP 違反要標路由目的地**：reviewer 標記「這段不屬於這篇」時要同時標「建議的目的地」— 只標前者不標後者，修改者容易選最省力的動作（刪除），而不是最正確的動作（路由）。詳見 [misplaced-content-routing](references/principles/misplaced-content-routing.md)

## 整合 finding 跟 fix 工作流

每輪結束後：

1. **跨 reviewer convergence**：3 個 reviewer 報告中重疊的 finding 優先序最高（per [#138 cross-reviewer convergence](references/principles/cross-reviewer-convergence.md)）
2. **整合 punch list**：列嚴重 / 建議 / 不修三層、估每項修法成本。轉述 reviewer 報告進 punch list 時、保留原報告的嚴重度與義務模態 — 「必修」在摘要裡降級成「可改」、後續的修法範圍確認就建立在失真清單上；摘要壓縮要保留模態、不只保留內容
3. **跟用戶確認修法範圍**：「修必修 + 建議全部修 / 只修必修 / 全部 backlog」用 AskUserQuestion 取得方向
4. **拆 commit**：按 frame 拆 2-3 個 commit（如 commit 1 處理規範 frame finding、commit 2 處理 cadence frame）
5. **驗證 + commit**：專案 markdown 工具鏈（如 mdtools lint / cards / fmt）跑過、各 commit 帶清楚的修法描述

### 跨 batch 的 finding 升級

同類 finding 第二次出現、代表 review 端攔截已證明不夠、把規則往上游升一級。升級階梯：

1. **Review 端**（第一次出現）：寫進 reviewer prompt 的審查維度、由 reviewer 掃
2. **生成端**（第二次出現）：寫進生成前的輪替表 / 檢查清單、寫的時候就避開（per [cadence 同質化](references/principles/cadence-homogenization.md)的生成端輪替）
3. **工具鏈**（偵測 pattern 穩定後）：規則的偵測面若能用 regex 表達、進專案 lint 的警告層。警告層的設計沿用「命中是候選、不是判決」— 自動掃描只負責曝光候選、語意判定留給人；自動化的價值是存量 debt 持續可見、不再依賴 review 記憶

升級判準兩條：偵測規則已穩定（同一 pattern 連兩個 batch 有效）、誤判可控（有明確的豁免形態、如引號內的反例引用）。register / stance 類規則（喊話 / 誇飾 / 必然性框架）的判定無法 regex 化、停在生成端、不硬升工具鏈。

## register 違規的異源複核操作

register 違規（重點後置、喊話、誇飾）的同源自審有上限（見「命中是候選、不是判決」段）。對這類要做窮盡複核時、跑一套「降低同源慣性 + 交接異源」的操作、而不是再疊一輪同源 reviewer（加再多輪都跨不過同源盲區）：

1. **機械候選曝光**：先用工具鏈（lint 警告層 / grep keyword bank）對 review 範圍跑、得一份客觀候選池。這層不靠 LLM 判斷、不受同源盲區影響、確保「偵測」不漏 —— 判定才是同源弱點，偵測交給機械最可靠。
2. **對抗文體 agent**：指派 reviewer agent、prompt 明確採對抗姿態 ——「挑剔否定起手 / 概念後置、預設違規除非能證明合規（核心概念在句首 / 明示反例段 / 「」內引用）」。對抗姿態抵銷「讀起來自然就放行」的同源慣性、但它仍是 LLM、不是真異源。
3. **複核清單分層交接**：agent 回報不當定論。把結果分兩層 ——「機械可確認」（pattern / keyword 命中、客觀）跟「register 判定」（這個命中是不是違規、同源判斷）。前者可信、後者標「需異源複核」。
4. **人異源定奪**：把「register 判定」那層攤成清單、交給作者以外的眼睛（人類冷讀）定奪。這是唯一真異源、register 違規的最後一關。

關鍵紀律：agent 回報的 register 層「clean」不可當真。這套操作降低同源慣性、提高候選曝光率、但不取代人異源 —— 它的產出是「給人複核的清單」、不是「已複核乾淨」。

## 跟既有 skill 的關係

- `case-first-module-workflow`（若專案已採用此 skill）的 Stage 4 含「agent team review」但偏 case-driven 單輪。Multi-round-review 補完跨輪 frame 切換維度、可以接在 case-first 的 Stage 5 之後或同時使用。
- [`compositional-writing`](../compositional-writing/SKILL.md) 提供寫作原則（intent-revealing、grep-friendly）+ 字句層 grep keyword bank（正向陳述 / 口語修辭 / 地區用語 / 廢話前綴 / 裝飾符號）。**本 skill 啟動時應同步 invoke compositional-writing** — Round 1-A 寫作規範 reviewer 必須跑 compositional-writing 的字句 grep（見上）、Round 2-A cadence reviewer 引用其 multi-pass review 第 6 原則跟 cadence-homogenization 原則卡。兩個 skill 是垂直協同：multi-round-review 給 frame 切換結構、compositional-writing 給每輪 frame 的具體檢查清單。
- **協同觸發**：用戶說「多輪審查 / 寫作 audit / batch review」時、兩個 skill 都該 surface — multi-round-review 規劃 frame、compositional-writing 提供每 frame 的 keyword bank。單獨用 multi-round-review 容易漏字句層、單獨用 compositional-writing 容易漏跨輪 frame 規劃。

## 反模式

- **用 finding 數遞減當停止訊號**：上一輪修完、下一輪 finding 變少就停 — 會錯過「更深層 frame 仍有 finding 待 catch」的時機
- **同 reviewer 跑多輪**：per #114、同 frame 多輪 catch 高度重複、無增益
- **跳過 frame 規劃直接派 reviewer**：「再來一輪 audit」沒指定 frame 切換、reviewer 用同方向掃同類問題、是 #114 的具體實例
- **單跑字面 grep 修法**：修完字面層（編號、broken link）就以為到位、漏掉結構層（cadence）跟同義變體（per #147）
- **用單一模板修 cadence 同質化**：為破一個模具立「一律 X」的生成端規則、均勻套整批、會收斂出比原模具更密的新模具；「套了破模具規則」的自我感覺遮住「規則本身是單一模板」、同源逐張自審全 clean。修法要輪替多個 framing（不換統一模板）、且把修法產物納入整組跨卡異源 cadence 重掃（per [均勻修法複製新模具](references/principles/uniform-remediation-recreates-homogenization.md)）
- **跑臨時子集卻當成跑完整框架**：只派幾個臨時擬的 reviewer frame + 一次 grep、就回報「review 完成 / clean」—— 漏抓後容易誤判成「框架不足」（design gap）而去加 frame / keyword、實際是「沒跑完該跑的輪」（execution gap）。漏抓先分 design gap（改框架）vs execution gap（改執行、別只加 keyword）；register/stance 類（喊話 / 誇飾 / 必然）尤其要靠 reader simulation + external cold-read、不是加 keyword（per compositional-writing 的 multi-pass-review-frame-granularity 原則）
- **把「多輪全過」當成「知識類型對」**：歷輪 finding 全部落在字句與結構層時、「三輪全過」的語意只是「已覆蓋層全過」——斷言支撐與知識類型層若沒有 frame 負責、錯的知識類型（披著教學結構的經驗談）會全數通過。finding 類型分佈本身是訊號：全部集中表面層 = 深層無人在看、下一輪排斷言支撐 frame（per [claim-support frame](references/principles/review-needs-claim-support-frame.md)）

---

**Version**: 1.10.1 — Round 1-A 對讀者喊話 grep 補裸第二人稱（`你的|你在|你把`）：原 `你天天|你會|你可能` 只抓「你 + 明顯動詞」的祈使 / 預測句型、抓不到裸『你的』『你在』；同步 compositional-writing v0.29.0；register 類 grep 非窮舉、真防線是異源冷讀
**Version**: 1.10.0 — Round 1-B 補「教學層 case 引用敘事重量」檢查（審查事故觸發：reviewer 偵測到帳目搬運、修法停在通用化「113 張 → 上百張」、使用者兩次指正才補完階梯——規模鋪陳整句刪、產品身分與領域詞泛化為無身分載體）：帳目 / 規模鋪陳 / 產品身分逐句掃、修法階梯「先刪、刪不動才泛化」、泛化有下限（論證要留具象載體）、判定用「拿掉後論證還成立嗎」機械測試取代「規模感幫論證」直覺；新增 `teaching-cite-strips-identity-and-scale` principle 卡
**Version**: 1.9.0 — Round 1-E 補兩個檢查點（教學模組重寫 retrospective 觸發）：斷言層加「判準成熟度」——維度清單（判斷看 A / B / C、無條件→行動映射）是判準的空殼、機制正確仍可能空殼、驗收用重算測試（實證：重寫 batch 機制全數重建後仍有一段停在維度清單、Round 3 才抓到——此檢查點讓它在 Round 1 現形）；模組層加「推導源頭」——分析模組入口要能一句話說出推導起點、各篇判準能折算回共同機制、主題集合結構下跨篇判準矛盾不可見（實證：跨篇矛盾「免費選擇權 vs 訂單信用」的可見性建立在兩篇同屬一個推導體系上）
**Version**: 1.8.0 — Round 1 新增 E reviewer「斷言支撐 / 知識類型 audit」（漏抓事故觸發：採購 planning 模組三輪全過、merge 後仍被使用者判定「講故事不是商業分析教學」——歷輪 finding 全落在字句與結構層、無任何 frame 負責斷言支撐與模組級知識類型）：斷言層抽 3-5 個承擔判準的斷言問「靠什麼成立」（機制 / 量化 / 來源 vs 口吻與權威）、模組層對照分類 house style；跟 steelman「閾值有無源頭」的差別是句子層誠實 vs 判準層可推導；經驗談 / 訪談素材的 batch 此 frame 必排第一輪；反模式加「把多輪全過當知識類型對」（finding 類型分佈全集中表面層 = 深層無人在看）；新增 `review-needs-claim-support-frame` principle 卡
**Version**: 1.7.0 — Reviewer prompt 關鍵設計補「SRP 違反要標路由目的地」：reviewer 標記「不屬於」時同時標建議目的地（已有文章 / 新文章 / 新分類 / 留原處加標記）、避免修改者選最省力的刪除而非最正確的路由；新增 `misplaced-content-routing` principle 卡
**Version**: 1.6.0 — Round 2-A cadence + 反模式段補「均勻修法複製新模具」：為破舊 cadence 模具立的單一生成端規則（如「段首一律目標詞先行」）均勻套整批會收斂出更密的新模具、同源自審在「已修」錯覺下看不到、修法要輪替 framing + 修法產物進整組跨卡異源重掃；新增 `uniform-remediation-recreates-homogenization` principle 卡
**Version**: 1.5.1 — changelog cross-reference 修正：1.5.0 條同步對象版號筆誤 v0.11.0 改 v0.24.0、1.4.1 條的 v0.18.0 依 compositional-writing changelog 重編（0.18.0 重號整理）改 v0.23.0
**Version**: 1.5.0 — Round 1-A 地區用語 grep 加慣用語層（`rg "拍腦袋|拍板|靠譜|給力|接地氣|一波|死磕|躺平|內卷"`）：慣用語直譯是開放集合、同源 reviewer 對這層有結構盲區、回報「clean」不可當真、需目標地區讀者冷讀；同步 compositional-writing v0.24.0 的 `regional-idioms-evade-keyword-bank` principle
**Version**: 1.4.1 — Round 1-A 字句層 bank 加「泛用詞濫用」grep（`rg "坑|東西|搞|弄|處理一下|情況"`）：同一泛用詞蓋不同具體情境、依情境換精確詞、「坑」繁中少用；同步 compositional-writing v0.23.0 的新 frame
**Version**: 1.4.0 — 三輪硬底線：「三大基本原則」升為「四大」、新增第四條「至少三輪」；Round N 判讀段改為 Round 3 結束後才開始；evidence 補 dotfile 31 篇 43 finding 實證
**Version**: 1.3.0 — Round 2-B reader-persona 加「術語知識卡覆蓋」維度（常識是相對於讀者背景的）
**Version**: 1.2.0 — B″ executable-walkthrough 加環境分支強調（同根因二次返工的防護）
**Version**: 1.1.0 — 新增五個 outside-in reader frame：Round 1 加 downstream-task、Round 2 加 reader-persona register + executable-walkthrough、Round 3 加 persona-coverage + search-landing；從 infra 模組生產週期 retrospective 抽出（6 個由使用者而非 reviewer 發現的盲點）
**Version**: 1.0.0
