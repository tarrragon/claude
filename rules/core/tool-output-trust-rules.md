# 工具輸出信任規則（Tool Output Trust）

本文件固化反 confabulation（虛構工具結果）協議，規範「工具呼叫後的生成行為」與「工具輸出的信任判據」。

> 來源：confabulation 根因分析 ANA（四視角整合：認知機制 / 文件缺口 / hook 可行性 / 架構品味）。confabulation = LLM 在 tool-call 後、result 注入前的無 grounding 預設填補（自回歸生成的數學行為），**本質不可根除，但觸發路徑可阻斷**。
> 配套：PC-166（幻覺工具結果，含防護 A-E）、`bash-tool-usage-rules`（裸 cd 觸發鏈起點）、IMP-056（chpwd 淹沒）。

> **適用對象**：主線程 PM（高 tool-call 密度，主要發生場景）與子代理人皆適用。

---

## 規則 1：工具呼叫發出後該訊息即停止，不續寫該工具的預期結果

**工具呼叫發出後，當前訊息不得續寫該工具的「預期 stdout / 預期結果」。任何結果必須等下一回合真實 tool result 返回才能引用。**

**Why/Consequence**：工具呼叫後同訊息續寫是 confabulation 點火動作——模型無真實 result 可條件化，用預期分布填補成「看似真實的 result」，進入 context 後與真實 result 在 token 層無法區分，滾雪球成自洽假世界（不可逆相變點），虛構 result 被當事實推進需外部多次介入才揭穿（PC-166 L1）。

**Action**：發出工具呼叫 → 該訊息停止 → 等真實 result 返回 → 下一回合才基於真實 result 推論。

### 規則 1 邊界：禁的是「續寫結果」，不是「一訊息多工具並行」

| 行為 | 合法性 | 說明 |
|------|-------|------|
| 一訊息發多個獨立工具呼叫（並行 invoke） | **合法，鼓勵** | 無依賴的工具並行更高效（harness 系統指令明確鼓勵）。多個 invoke 連發本身不產生虛構，其 result 都會在下一回合返回 |
| 工具呼叫後在同訊息續寫該工具的預期結果 | **禁止** | confabulation 點火動作。禁的是「續寫 result」，非「多 invoke」 |

**Why/辨識**：「一訊息多工具」（能力，平台鼓勵）與「invoke 後續寫結果」（confabulation 虛構起點）生成行為同形易混淆，防護須精確禁後者不傷前者（Never break userspace）。發多個工具呼叫 = OK；發呼叫後接著寫「輸出會是 X」「結果顯示 Y」= 違規。

---

## 規則 2：只信 raw stdout，帶旁白者視為自己生成的雜訊

**真實工具 stdout 不會自帶 markdown 修飾、中文旁白、`System:` 訊息。輸出若夾帶這些「assistant 生成特徵」，視為自己虛構的 token，非真實 result。**

**Why/Consequence**：raw stdout 的形態特徵是 confabulation 鑑別判據（PC-166 防護 E）——真實 stdout 是程式輸出不會自我包裝 markdown 或寫旁白；把帶旁白的虛構輸出當真實 result 會基於不存在內容推進，並誤把自己的 confabulation 歸因為外部污染。

**Action**：工具 result 帶 code fence／中文旁白／`System:` 訊息時，警覺這是自己生成的雜訊；用規則 3 的固定值交叉驗證真相。

---

## 規則 3：關鍵事實用無法腦補的固定值交叉驗證

**關鍵唯讀事實（檔案是否存在、HEAD 是什麼、grep 是否命中）用「輸出格式固定、無法腦補」的命令確認，不靠預期推斷。**

**Why/Consequence**：固定值（40 字 hash／二元存在性／整數計數）無法被模型先驗分布生成，是打破「預期＝觀測」同構的唯一手段；靠預期推斷則預期分布與虛構觀測在 token 層同構，無從鑑別真偽，confabulation 不被攔截即滾雪球（PC-166 L1 + 防護 E）。

**Action**：

| 待確認 | 固定值命令 | 判據 |
|-------|----------|------|
| HEAD / commit 真實性 | `git rev-parse HEAD` / `git cat-file -t <hash>` | 40 字 hash / 二元 type |
| 檔案是否存在 | `ls <path>` / `test -f <path> && echo Y` | 二元有/無 |
| grep 是否命中 | `grep -c <pattern> <file>` | 整數計數 |
| working tree 狀態 | `git status --porcelain` | 有/無輸出 |

輸出可疑時，同命令重發一次，兩次 raw stdout 逐字一致才採信。

---

## 規則 4：用 git -C 取代裸 cd（觸發鏈源頭）

**需在特定目錄執行命令時，優先用 `git -C <abs>`（git 操作）或子 shell `(cd ... && ...)`，禁裸 cd。**

**Why/Consequence**：裸 cd 觸發 zsh chpwd hook 的 ls 淹沒（IMP-056），是 confabulation 觸發鏈第 1 環——輸出淹沒 → result 邊界模糊 → PM 退化為「用預期填補」（規則 1 點火動作），把虛構輸出當事實推進；`git -C` 不切換 cwd 從根本消除 chpwd 觸發。

**Action**：見 `bash-tool-usage-rules` 規則一（git -C 首選方案）。本規則與其交叉引用。

---

## 規則 5：記錄平面（含自己的對話記憶）不是 ground truth，重大狀態以世界平面為準

**transcript / context /「我記得做過」屬記錄平面，與 filesystem / git / ticket 的世界平面語意不對稱。重大狀態轉換（claim / complete / commit / spawn）的判斷必須以世界平面為準，不以對話記憶為準。**

**Why/Consequence**：世界副作用是 at-least-once（重試／分叉／並行可重複執行），記錄寫入是 at-most-once（同 prompt 多執行體只有一個 transcript 留存），兩者必然雙向漂移：記錄有而世界無（規則 1-3 confabulation），世界有而記錄無（ghost branch 真實副作用但本執行體零記憶）。把記錄平面當 ground truth 會雙向出錯——虛構記憶當真，或把 ghost branch 真實 commit／ticket 變更誤判為「我沒做過」而當污染 revert，造成真實工作遺失。

**Action**：

| 情形 | 世界平面查證（ground truth） | 禁止 |
|------|---------------------------|------|
| 「我記得 commit 了」 | `git log --oneline -1` / `git cat-file -t <hash>` | 憑記憶斷言 commit 成功 |
| 「我記得 complete 了 ticket」 | `ticket track query <id>` 讀真實 status | 憑記憶斷言已 complete |
| 「git status 有我沒印象的變更」 | 先查 ghost 痕跡（subagents 目錄／無主 commit／birth time）再決定對帳或 revert | 直接當污染 revert（可能丟失 ghost 真實副作用） |

**與規則 3 銜接**：固定值是查證世界平面的手段；本規則是「為何必須查世界平面」的原則——記錄平面 at-most-once，不可作為唯一事實來源。雙向鑑識判據見 PC-166 防護 D 延伸（同 prompt 異執行體）。

**與規則 6 銜接**：規則 5 處理「記錄平面不可信」（自身對話記憶／transcript 與世界平面的不對稱）；規則 6 處理「工具輸出真實但過期」（驗證器警告與建立端定義的權威落差）。兩者對象不同（前者是自身記憶，後者是外部工具輸出），但同屬「不預設輸出即為最新真相，遇衝突先查權威來源」家族。

---

## 規則 6：驗證器警告與工具自動產出衝突時，先查建立端定義

**工具自動產出的內容（CLI 產生的 ticket 章節、Hook 自動填入的欄位等）收到驗證器 warning 時，不可預設「產出有誤」；須先查建立端（產出來源的權威定義）確認警告本身是否為驗證器過期所致。**

**Why/Consequence**：驗證器與建立端可能各自獨立維護清單或規則，建立端更新（如新增 canonical 章節）未必同步驗證端（PC-BAL-001 實證：canonical 清單新增成員後 5 處下游定義潛伏 15 天未同步，且因誤報僅為 warning、對象是自動產生的內容，看似 agent 違規而非驗證器過期）。若對「真實但過期」的警告（驗證器輸出本身無誤，但其判準已落後建立端）直接信任並反向修改工具自動產出的內容，等於把過期判準當事實執行修正，產生「修好一個原本沒壞的東西」的反效果，同時掩蓋驗證器真正該修的過期問題。

**Action**：

| 情境 | 判定順序 | 反例 |
|------|---------|------|
| Hook/CLI warning 指出「自動產出的章節/欄位不符合 schema」 | 先查建立端權威定義（如 `constants.py` 的 canonical 常數），非驗證器清單 | 直接刪除或改寫工具自動產出的內容以消除警告 |
| 建立端與驗證端清單不一致 | 以建立端為準；驗證端視為待同步的下游定義 | 以驗證端「多數決」（如 3 份驗證端一致）反過來判定建立端錯誤 |
| 無法判斷何者為建立端 | 查該欄位/章節的產生機制（誰寫入、誰讀取驗證）決定權威方 | 憑警告文字語氣或出現頻率猜測 |

**判定順序**（PC-BAL-001）：canonical 常數（建立端）＞ 驗證端清單 ＞ 文件描述。三者不一致時以建立端為準；`canonical-schema-consistency-check-hook.py`（SessionStart，0.0.1-W1-006）自動比對建立端與下游清單並輸出具體差異項，可作為快速查證管道，不需人工逐檔比對。

**與規則 3 銜接**：規則 3 要求「關鍵事實用固定值交叉驗證」；本規則的固定值查證對象特化為「建立端權威定義」，補上規則 3 未涵蓋的情境——規則 1-3 聚焦真實 vs 虛構輸出，本規則聚焦真實但過期的驗證輸出 vs 建立端現況，兩者判別依據不同（前者用固定值命令，後者用建立端定義溯源）。

> **邊界**：本規則 1-4 是 PC-166「生成自律」的規則層固化（防護 E 無法 hook 的部分）；規則 5 二相性對應 PC-166 防護 D 延伸；規則 6 對應 PC-BAL-001（驗證端清單過期）。規則 4 與 `bash-tool-usage-rules` 規則一交叉引用（觸發鏈源頭），chpwd 淹沒機制見 IMP-056；規則 1 邊界與 `ai-communication-rules` 對話品質互補。

---

**Last Updated**: 2026-07-20 | **Version**: 1.3.0 — 新增規則 6「驗證器警告與工具自動產出衝突時先查建立端定義」，含可操作判定表；規則 5 補交叉引用（0.0.1-W1-006，承接 0.0.1-W1-004 成因分析）。歷史 1.0–1.2 版見 git log。**Source**: confabulation 根因 ANA（四視角整合）；PC-166；PC-BAL-001。
