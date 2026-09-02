# wrap-decision 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 2.11.0 — `pseudo-widen-guard.md`、`source-verification.md` 因內容通用（實讀後判定不含專案特定耦合）由 `references/project-integration/` 提升至正規 references 層；「假設層級多元性」「清單類答案的來源核對」兩節補上直接引用；「參考文件」通用表新增兩檔條目；合併發佈庫的 lint 基線清理（v2.10.1）：4 個純文字 code fence 補上 `text` 語言標示（MD040）、「假設層級多元性」的粗體命題併入下一段（MD036）

**Version**: 2.10.3 — 版本紀錄搬到同目錄的 `CHANGELOG.md`。skill 是 runtime 整份載入的檔案，而沒有任何規則要求任何人讀版本紀錄，留在 SKILL.md 等於每次叫用都付一次無效讀取。SKILL.md 末尾留一行指過去，版號的兩個住址改成「CHANGELOG.md 最上面那一條 + frontmatter 的 metadata.version」。skill 的指令內容一個字都沒改。

**Version**: 2.10.2 — 術語校正：判準全數改為判斷標準（動作修飾語縮為「X 標準」、狀態義改為「X 條件」）。判準的語域在哲學與教育評量、工程讀者解析不了——五份低階模型探針一致回報非通用

**Version**: 2.10.1 — lint 基線清理：7 個純文字 code fence（決策樹、檢查清單、反向搜尋表模板）補上 text 語言標示（MD040）；「假設層級多元性」的粗體命題併入下一段，不再是獨立的粗體段落（MD036）；爬梯子法的「教訓」改用表格自己的語意層名（身邊 / 同領域）取代「第 N 層」編號（REF1）。

**Version**: 2.10.0 — 「二元處置取捨」項識別特徵擴充至涵蓋設計選型類的副作用取捨（候選方案在不同維度上代價方向相反，如強度高者風險亦高），未新增第二列判斷標準；新增「適用對象不限處置類」子節說明處置類與設計選型類共享同一失效機制；Why/Consequence/Action 三明示同步擴寫；新增設計選型類實證段（案例敘事改描述性標籤，不引用專案層級 ticket ID，依規則 8 全禁原則）

**Version**: 2.9.0 — 「二元處置取捨」節補一則權威標註：本節為該判斷標準的 substance 權威來源，專案端提問規則的「選項空間檢查」節為對應落地版本，消除兩節間逐字重複的 Why/Consequence/實證段

**Version**: 2.8.0 — 移植 blog 分支獨有演化（來源：blog 分支 2.4.0 + 2.5.0 合併）：觸發條件表新增「不可逆 / 時間壓力」「利害關係人衝突」兩項；新增「快速+模式」定義（原僅見於觸發條件表值，未定義語意）；參考文件表補 `claim-quick-wrap.md`（原 canonical 已有該檔但未被引用，至今 orphan）；絆腳索類型表新增「基礎設施累積型」（escalation 連續 2+ 次、每次加一層工具 / 檔案 / 流程而 anchor 未曾明說時，亮 anchor 一次按其重定 apparatus 份量）。
**Version**: 2.7.0 — 觸發條件表新增「二元處置取捨」項（入場閘門：處置類選項未經 W 階段產出即不得呈現），並補與既有結論錨定（3.2）的邊界說明——3.2 是 WRAP 內部自我檢查，本項是 WRAP 之前的入場閘門。
**Version**: 2.6.0 — Step 0 資料充足度閘門新增「與 requirement-protocol 的分工邊界」子節：三機制（WRAP Step 0 / premortem context 閘門 / requirement-protocol）受眾與問題對照表 + 共用原則（一次一問、互為前置不重複），requirement-protocol 反向交叉引用同步（源自外部 premortem skill context 充足度閘門）。
**Version**: 2.5.0 — P 階段「行前預想」新增「每個預想失敗原因配早期警訊」條款：可觀測訊號（非模糊感覺）+ 需跨 session 監測時包裝為監測 ticket 綁 trigger（決策 trigger 綁定規則：合法 trigger 限 ticket ID）（源自外部 premortem skill early warning signals）。
**Version**: 2.4.0 — 新增完整 premortem 流程（`references/premortem-workflow.md`）：failure-reason 並行深挖 + 三分綜合報告，銜接 P 階段簡化三問與理論依據 `principles/premortem-klein.md`；description 補觸發詞（premortem/事前驗屍/壓力測試計畫等）。
**Version**: 2.3.0 — 觸發條件新增 4 項決策路徑層干擾（CLI 自動駕駛（autopilot） / 既有結論錨定（Anchor） / 草率改規則 / 多步驟成功率盲點）；既有觸發條件不變動（向後相容）。
**Version**: 2.2.0 — 觸發條件新增反思深度質疑（reflection_depth_challenge）說明，含與被困住語意的差異。
**Version**: 2.1.0 — 新增多輪迭代查詢方法論（W）+ 反向驗證範本（R）+ 悖論識別檢查清單（A）+ 自我暴露偏好實踐（P）+ 2 個新 references（iterative-research / anti-paternalism）。
**Source**: 《零偏見決斷法》(Decisive) — Chip Heath & Dan Heath
