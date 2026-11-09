# 驗證責任分配框架

本文件定義系統性的「驗證責任分配」框架，明確各層級的驗證職責，防止未來類似的功能缺口和職責混亂。

> **核心理念**：驗證是多層級、多角色的責任分工。不同階段有不同的驗證者，確保完整的檢查覆蓋。

---

## 框架總覽

```
Level 1 入口層 → Level 2 執行層 → Level 3 完成層 → Level 4 驗收層 → 任務完成
```

| 層級 | 驗證時機 | 驗證者 | 目標 |
|------|---------|-------|------|
| Level 1 入口層 | 命令入口（用戶輸入時） | Hook 系統 | 防止無計畫工作（Ticket 存在 + 認領 + 品質審核） |
| Level 2 執行層 | 任務開始時、階段切換時 | 代理人 | 確保前置條件滿足、無隱藏依賴 |
| Level 3 完成層 | 階段完成時、Ticket 標記完成前 | Hook + 代理人 | 確保產出物完整、文件記錄齊全 |
| Level 4 驗收層 | Ticket complete 後 | acceptance-auditor + PM | 最終品質確認 |

> 各層級驗證內容表格、責任分工、Hook 實作細節、驗收流程圖：.claude/references/verification-framework-details.md

---

## 統一責任對照表

| 驗證項 | 驗證者 | 所屬層級 | 無法通過時 | 最終決策 |
|-------|-------|--------|-----------|--------|
| Ticket 存在 | Hook | Level 1 | 提示建立 | 用戶決定 |
| Ticket 認領 | Hook | Level 1 | 提示認領 | 用戶決定 |
| Ticket 內容品質 | PM | Level 1 | 建議補充 | PM 決定 |
| Solution 並行化 | PM | Level 1 | 建議評估 | PM 決定 |
| 建立後品質審核 | acceptance-auditor + system-analyst | Level 1 | 派發審核代理人 | PM 決定 |
| 前置依賴 | 代理人 | Level 2 | 升級 PM | PM 決定 |
| 環境正常 | 代理人 | Level 2 | 派發 SE | SE 處理 |
| 產出物完整 | Hook | Level 3 | 提示補充 | 代理人決定 |
| 工作日誌 | Hook | Level 3 | 提示更新 | 代理人決定 |
| 驗收條件主動勾選 | PM | Level 3 | complete 前執行 check-acceptance | PM 決定 |
| 並行派發後驗證 | PM | Level 3 | 補派代理人 | PM 決定 |
| 驗收條件 | acceptance-auditor | Level 4 | 要求補充 | PM 決定 |
| 建議追蹤 | acceptance-auditor | Level 4 | 要求處理 | PM 決定 |
| 品質標準 | acceptance-auditor | Level 4 | 建立修正 Ticket | PM 決定 |
| 測試通過 | acceptance-auditor | Level 4 | 派發 incident | PM 決定 |

---

## 驗收三項固定檢查

**決定一張票收或退，只看三項檢查，其他一律不審。** 退件會一直拖，是因為沒有寫清楚審什麼；把範圍縮小到三項，就不會來回退件。

| # | 檢查 | 判準 | 不通過的例子 |
|---|------|------|------------|
| 1 | 能不能跑 | 本票相關測試全綠；合併前由閘門跑全套件並讀結束碼；建置與分析無新增 error | 測試紅燈、編譯失敗、執行時崩潰、資料損壞 |
| 2 | 有沒有動到不該動的檔案 | 變更的檔案都在票面 `where.files` 宣告的範圍內（以 `git diff --name-only` 對照） | 改了票面沒宣告的檔案、順手重構其他模組 |
| 3 | 輸出格式對不對 | 產出符合派發時票面寫定的產出形態：acceptance 列的項目都有對應產出，格式（檔案類型、schema、章節、欄位）與宣告一致 | 少了 acceptance 列的產出、schema 不符、宣告要表格卻交散文 |

**三項以外不構成退件理由**：命名、寫法、架構偏好、可讀性、Phase 4 重構評估與多視角審查的建議、派發時票面沒寫的要求，都不退件。這些發現照常記錄，依 `.claude/pm-rules/version-progression.md`〈兩期：規劃期與執行期〉排進後續版本。

**Phase 4 與多視角審查照跑**：品質基線規則 2 的 Phase 4 評估仍然必做，parallel-evaluation 依原觸發條件執行，但產出只用來記錄後續版本的待辦，不影響本票收退。

**檢查 3 的範圍以派發時的票面為準**：驗收時才想到的要求，不能回頭加進本票的 acceptance。票面 acceptance 本身寫得不清楚時，照字面最寬鬆的合理解讀收件，改進寫法的工作排進後續版本。

**檢查 2 的 where 擴充程序**：本票 acceptance 以全文 grep 驗收某個概念（概念替換類，見 `.claude/error-patterns/documentation/DOC-008-partial-definition-replacement-in-same-file.md`〈變體：驗收條件以位置界定範圍〉），執行中在 `where.files` 以外的檔案 grep 到同一概念的命中時，依下表處理。

| 步驟 | 執行者 | 動作 |
|------|-------|------|
| 1 | 執行者 | 停手，不修改 where 以外的檔案；把命中清單（檔案、行、命中字樣）回報 PM |
| 2 | PM | 判定命中是否屬本票 grep 驗收的同一概念。屬於的，以 `ticket track set-where` 加入 where，並在票面記下每個加入檔案的理由；不屬於的，依兩期規則記成後續版本的票 |
| 3 | 執行者 | 在擴充後的 where 內繼續修改 |
| 4 | 驗收者 | 以擴充後的 `where.files` 機械比對，判定方式不變；擴充條目沒有理由紀錄時，該檔案視為範圍外 |

只有 PM 能擴充 where，而且只限本票 grep 驗收的命中；其他理由（順手修正、相關改善）不適用本程序。PM 同時是執行者時，步驟 1 與 3 合併，理由紀錄仍要寫。

**Why**：檢查 2 要求變更只落在 where 內，概念替換卻要求同一概念在全文都改完。命中在 where 以外時，兩者會互相衝突：照 grep 驗收改，會被檢查 2 退件；照檢查 2 停手，同一概念的新舊寫法會並存發佈。**Consequence**：沒有擴充程序，執行者只能二選一，選哪一邊都會讓驗收結果取決於執行者的判斷，而不是票面。**Action**：規劃期先 grep，把已知命中放進 where（減少執行中擴充）；執行中仍有新命中時，走上表四步。

**Why**：驗收範圍不固定時，每一輪審查都能找到新的意見，同一張票來回退件，執行期跟著變成第二輪規劃。**Consequence**：退件理由一旦超出三項，代理人無法預先知道怎樣算完成，版本的終點會一直往後推。**Action**：驗收報告只列三項的結果；其他觀察寫成後續版本的票或 issue，不寫成退件理由。

---

## 驗證失敗處理

| 失敗類型 | 恢復方式 | 時限 |
|---------|--------|------|
| Level 1（Ticket 問題） | 建立或認領 Ticket | 立即 |
| Level 2（前置條件） | 升級 PM 或派發協助代理人 | 立即升級 |
| Level 3（產出物缺陷） | 屬三項檢查不通過時退回補齊；其餘記錄為後續版本的票 | 同日內 |
| Level 4（品質問題） | 建立修正 Ticket，排進後續維護版本（讓本版跑不起來的除外） | 後續版本 |

> 失敗流程圖和詳細恢復規則：.claude/references/verification-framework-details.md

---

## 與現有規則的整合

### 與 Skip-gate 的關係

**Skip-gate 防護機制對應**：

| Skip-gate 層級 | 防護機制 | 驗證框架對應 |
|---------------|--------|------------|
| Level 2 | 命令入口防護 | Level 1 入口層驗證 |
| Level 3 | 階段完成防護 | Level 3 完成層驗證 |

### 與決策樹的關係

驗證框架在決策樹的多個層級提供支撐：

| 決策樹層級 | 驗證層級 | 驗證者 |
|-----------|--------|-------|
| 第零層（明確性檢查） | Level 1 | Hook + 代理人 |
| 第四層（Ticket 執行） | Level 1 | Hook |
| 第五層（TDD 階段） | Level 2 + Level 3 | 代理人 + Hook |
| 第七層（完成判斷） | Level 4 | PM |

### TDD 階段驗證檢查點

每個 TDD 階段都有對應的驗證要點：

| Phase | Level 2 前置條件 | Level 3 驗收條件 |
|-------|---------------|----------------|
| SA | - | 架構評估完成 |
| Phase 1 | SA 審查通過 | API 定義完整 |
| Phase 2 | Phase 1 完成 | 測試案例設計完成 |
| Phase 3a | Phase 2 完成 | 策略文件完整 |
| Phase 3b | Phase 3a 完成 | 本票相關測試檔 100% 通過（全套件交合併閘門，見下方〈合併前全綠與實機驗證票〉） |
| Phase 4 | Phase 3b 完成 | 評估報告完成 |

---

## 驗證檢查清單與操作指引

> 各層級完整檢查清單（Level 2/3/4）、場景範例、Hook 實作規範、驗證指標：.claude/references/verification-framework-details.md
> 場景範例：.claude/references/verification-scenario-examples.md
> Hook 實作細節：.claude/references/verification-hook-implementation.md

### Runtime-surface ticket 的實機驗證 AC 要求

**規則**：ticket 的 `where.files` 觸及 runtime surface（`lib/presentation/`、`lib/main.dart`、平台整合層）時，acceptance 必須含一項實機驗證——可自動化者指 on-device 測試（如 `integration_test/` 於釘住裝置執行全綠），不可自動化者（探索性、硬體相依、觀感）指 PM 手動 verify（`.claude/references/pm-role-details.md`「實機驗證屬 PM 職責」條款）。

**Why**：host 測試以替身隔離接縫，全綠仍可能實機起不來、點不到、沒回應；acceptance 缺實機項時此類失效直到發版冒煙才暴露（quality-baseline 規則 1 邊界）。**Action**：PM 建票時對照 `where.files`；漏帶時於驗收前補 AC。判準句與紅燈層級順序節的豁免判準為同一句（「場景有無可駕駛的執行面」，權威見 `.claude/skills/tdd/references/phase2/rules.md`「紅燈層級順序」節）。Hook 強制層暫不建立（決策：現階段由 PM 建票時對照攔截即足）；若發生 runtime-surface ticket 漏帶實機 AC 且未被 PM 攔截，依 quality-baseline 規則 5 當下建 ANA 評估 hook 化。

---

## 合併前全綠與實機驗證票

**原則**：測試驗證分兩個時點——本機提交前驗「本票相關測試檔」，合併 main 前驗「全套件」；全套件只在合併閘門內跑一次，不由各開發票各自重跑。

**Why**：全套件在每張開發票各跑一次，N 張並行即 N 份重複負載，且彼此排擠名額。**Consequence**：若 Phase 3b 驗收仍要求全套件，代理人會繞過合併閘門自行跑全套件，重複負載回來，閘門的序列化失去意義。**Action**：依下表分工驗收。

### 時點分工

| 時點 | 驗證範圍 | 執行者 | 判定依據 |
|------|---------|-------|---------|
| 本機提交前（含 Phase 3b） | 本票相關測試檔 | 實作代理人 | 該次測試命令的結束碼 |
| 合併 main 前 | 全套件 | worktree 合併流程，於名額閘門內 | 合併閘門讀取的結束碼；紅燈不合併 |
| Level 4 驗收 | 讀合併結果，不重跑全套件 | acceptance-auditor | `.claude/logs/worktree-merge.log` 的 `[合併前測試]` 套件結果行與 `[合併閘門]` 結束行 |

Level 4 找不到閘門結果的處置與 `--skip-gate` 例外，以 `.claude/agents/acceptance-auditor.md`〈Step 5 測試驗證：依審查時點分兩種做法〉為準。套件選擇、快照、重試與日誌格式見 `.claude/skills/worktree/SKILL.md`〈合併前全套件〉。測試入口與回報規格見 `.claude/references/agent-dispatch-template.md`〈測試入口〉。

**Hook 回報的定位**：post-test-hook 等回報只是輔助訊號，不是「合併前全綠」的保證；保證來自合併閘門讀取的結束碼。條文與驗收不得依賴 hook 回報判定全綠。

### 實機驗證票

**原則**：runtime surface 的實機驗證集中成批，由 PM 開獨立的實機驗證票承接，不由每張開發票各自執行。

**Why**：實機驗證需編譯 app，屬重量級工作；每張開發票各編譯一次，並行時同機疊加多份編譯。**Consequence**：不集中則編譯負載與全套件同型重複；不開票則 runtime 失效（host 測試以替身隔離接縫，全綠仍可能起不來）要到發版冒煙才暴露。

**開票條件**（任一成立，由 PM 開一張）：

| 條件 | 說明 |
|------|------|
| 一批合併中有票觸及 runtime surface | 任一票的 `where.files` 觸及 `lib/presentation/`、`lib/main.dart`、平台整合層（判準同〈Runtime-surface ticket 的實機驗證 AC 要求〉）；該批合併後開一張，取代各票各自的實機驗收；批次邊界由 PM 判斷，例如同一 wave 內相關 UI 票全數合併後 |
| 版本發布前 | 固定一張，承接發版的 on-device 套件要求 |
| 自動化 integration_test 紅燈且歸因於 runner 環境 | 歸因程式或測試本身的紅燈不屬此條，走一般除錯票 |

**執行方式**：PM 以 `/verify`、`/run` 驅動 app 觀察 runtime 行為（實機驗證屬 PM 職責，見 `.claude/references/pm-role-details.md`「實機驗證屬 PM 職責」）。

**排入名額閘門**：需要編譯或執行 integration_test 時，命令經 `run-with-timeout.py` 執行；該類命令判為 heavy，自動排入全機 1 名額的閘門，同一時間全機只有一份編譯，排隊時間不計逾時。不經包裝的 heavy 命令不得執行。

**與 CI 的分工**：integration_test 與 macOS 編譯預定由 CI 承接，該外移尚在規劃中，現行條文不得當作已落地；CI 落地前，這兩類驗證由實機驗證票經名額閘門執行。CI 落地後，實機驗證票仍承擔 CI 無法覆蓋的部分：人眼觀察、平台權限與檔案系統互動、需用戶環境的流程。

---

## ANA 專屬驗收 checklist：Solution spawn 一致性（Level 4 延伸）

> **核心定位**：本章節是 Level 4 驗收層的 ANA 專屬延伸，補強 PM 在 ANA complete 前對 Solution 規劃 vs 實際 spawned ticket 的一致性檢查。**作為 hook 強制層（acceptance-gate-hook 整合 ana_spawn_consistency_checker）+ 規則自律層（quality-baseline 規則 5）之外的第三道行為層防護**。
>
> 來源：W17-167 ANA L4 結論。落地基線：W17-162 ANA 暴露 ANA Solution 規劃 spawn 但未實際建 ticket，acceptance 勾選只檢文字產出，靜默放行。

### 適用範圍

| 觸發條件 | 是否啟用 |
|---------|---------|
| ANA 類 ticket complete 前驗收 | 是 |
| Solution 內含 spawn 規劃表格（IMP/DOC 清單） | 是 |
| ANA 結論為「無需 spawn」且已顯性標註 | 例外豁免（Q3） |
| IMP / DOC 類 ticket | 否（不適用） |

### 三題 Checklist（PM 驗收 ANA 時逐題核對）

#### Q1：Solution spawn 規劃表格的每一項，是否都已建對應 ticket？

**Why**：Solution 寫了規劃不等於建了 ticket。acceptance 條目「產出 spawned IMP/DOC 清單」勾選只代表 Solution 章節文字產出存在，與「實際 `ticket track create` 建檔」是兩件事。

**Consequence**：未建 ticket 的規劃會在 ANA complete 後靜默遺忘——觸發 PC-093（無 trigger 延後決策累積）模式，且違反 quality-baseline 規則 5（所有發現必須追蹤）。歷史 W17-162 / W11-003.6 等案例證實此漏洞反覆發生。

**Action**：逐項比對 Solution 表格 vs frontmatter `spawned_tickets` / `children`，缺漏立即執行 `ticket track create` 補建並追加至 frontmatter。

#### Q2：frontmatter `spawned_tickets` + `children` 數量是否 >= Solution 規劃數量？

**Why**：數量不一致代表至少有一項規劃漏建。Q1 的逐項比對若有遺漏（如表格項目較多時人工比對失準），數量門檻提供第二層防護。

**Consequence**：部分規劃遺忘會導致後續 Wave 排程缺料；ANA L1-L4 多層防護中，若 L4 行為層未檢，hook + 規則層的設計意圖無法在「PM 主動驗收」場景閉環。

**Action**：以 `len(spawned_tickets) + len(children) >= Solution 表格列數` 為門檻；數量不足時逐行回查 Solution 表格，補建遺漏 ticket，並在 ticket frontmatter `spawned_tickets` 補入新建 ticket ID。

#### Q3：若合法不 spawn，Solution 是否有顯性否定標記？

**Why**：合法不 spawn 的情境確實存在（如 ANA 結論為「現有方案足夠，無需新 ticket」）。顯性否定標記讓 hook 偵測到 spawn 規劃不一致時可豁免，且讓後人理解決策理由——避免誤判為漏建。

**Consequence**：無否定標記時，ana_spawn_consistency_checker 會阻擋 complete（誤判為漏建）；後人接手 ANA 時也會誤以為是漏建而重新建 ticket，造成重工。

**Action**：在 Solution 章節以下列任一格式顯性標註：
- `「無需建 ticket：[具體理由，如：現有 Wave X 已涵蓋 / 等待外部依賴 Y / 經多視角審查確認屬 over-engineering]」`
- 對應 hook 偵測模式由 `ana_spawn_consistency_checker` 規格定義（W17-167 spawned IMP #1 落地）。

### 與既有驗收條目的關係

| 既有條目 | 本 checklist 補強點 |
|---------|------------------|
| Level 4 驗收條件（acceptance-auditor） | 本 checklist 為 PM 操作層延伸，acceptance-auditor 仍為主驗收者 |
| Level 3「驗收條件主動勾選」 | Q1-Q3 是「驗收條件」內容的具體化（針對 ANA 類 ticket） |
| quality-baseline 規則 5（所有發現必須追蹤） | Q1 是規則 5 在 ANA Solution 場景的具體化執行步驟 |

### PM 操作流程整合

ANA complete 前，PM 在主線程依序執行：

1. `ticket track show <ana-id>` 取得 frontmatter `spawned_tickets` / `children` 與 Solution 章節
2. 逐題執行 Q1 / Q2 / Q3
3. 若 Q1 / Q2 不通過，立即 `ticket track create` 補建並更新 frontmatter
4. 若 Q3 適用，在 Solution 補上顯性否定標記
5. 執行 `ticket track check-acceptance --all <ana-id>` + `ticket track complete <ana-id>`

> 三層防護銜接：本 checklist（L4 行為層）失守時，acceptance-gate-hook 整合的 `ana_spawn_consistency_checker`（L2 hook 強制層）會阻擋 complete；hook 規格見 `.claude/hooks/acceptance_checkers/ana_spawn_consistency_checker.py`。

---

## 驗收條件爭議裁決框架（Level 4 延伸）

> **定位**：Level 4 驗收層的裁決依據延伸，補足「PM 裁決 AC 與實況爭議」缺乏固定判準、需臨場推導的缺口。來源：同一 session 內出現兩次代理人回報「acceptance 與實際狀態不一致、請裁決」的爭議，兩次的正確處置相反，臨場推導出的結論不成文，下次仍要重新推導。

### 核心區分軸

裁決 AC「是否已完成」的爭議時，先問一個問題：**這個爭議的癥結，是實質要求本身沒做到，還是拿來判定「做到了沒」的量尺本身壞了？** 兩者答案分別導向判準一與判準二，處置方向相反。混為一談會產生兩種壞結果：把未完成的工作勾選為完成，或把已完成的工作卡在錯誤的驗證方法上。

### 判準一：條件未觸發 不等於 條件未滿足

**情境**：AC 寫成條件式（「X 完成後做 Y」），裁決時前提 X 尚未成立。

**判別問句**：若前提 X 現在成立，Y 這項要求是否仍然存在、且尚未被滿足？

- 答「是」→ 命中判準一。這不是「已達成」，也不是「不適用」，是義務尚未到期。Ticket 系統的 checkbox 只有勾選/未勾選二元狀態，沒有 N/A（不適用）這個第三態，不可用「改寫 AC 文字」去遷就這個工具限制。
- 答「否」（X 成立後 Y 本來就不必做，如目標已被架構變動取消）→ 不屬本判準，另評估是否為 AC 本身已過時需改寫。

**Why**：checkbox 的二元限制是工具形態限制，不是業務判斷。用改寫 AC 文字去消化「前提未成立」，等於讓工具限制反過來決定業務事實，而業務事實是「這件事還沒到該做的時候」。

**Consequence**：若誤將條件未觸發當作「已達成」勾選，會把尚未完成的實質工作標記為完成，後續 Wave 或驗收會漏查；若誤將其當作「不適用」而刪除該條款，則遺失了「X 成立後仍要做 Y」這個依然有效的約定。

**Action**：
1. 不修改 AC 原文遷就 checkbox 缺 N/A 狀態的工具限制。
2. 用 ticket 系統的 `blockedBy` 欄位表達依賴，將本 ticket 標記 `blockedBy: [<X 對應 ticket ID>]`。
3. AC 維持未勾選，ticket 退回 `pending`（不可 complete），等 X 完成後才重新評估 Y。

### 判準二：實質要求 不等於 驗證代理指標

**情境**：AC 的實質要求已經達成，但用來判定「已達成」的驗證方法（如 grep 命中數）本身有缺陷。

**判別問句**：若把驗證方法修正後重新驗證，實質要求原文陳述的完成與否結論會不會因此改變？

- 答「不會」（只是驗證管道對現象不敏感，如例外清單不完整導致誤判）→ 命中判準二。問題出在量尺，不在工作本身。
- 答「會」（驗證方法修正後，結論從「完成」變回「未完成」）→ 不屬本判準，回頭評估是否命中判準一或直接視為未完成。

**Why**：AC 的驗證子句是「代理指標」（proxy metric），用可執行的觀察管道去逼近「實質要求是否達成」這個業務事實。代理指標本身可能與待驗現象脫鉤（見 `PC-BAL-010` 恆偽案例：grep 命中不區分「主張」與「引用並否定」）。代理指標與業務事實脫鉤時，錯的是代理指標，不是業務事實。

**Consequence**：若把驗證方法缺陷誤判為實質要求未達成，會退回已完成的工作要求重做，浪費工時且可能誤導後續依賴此 AC 的判斷；反過來，若把「驗證方法有問題」當成放寬實質要求的藉口，兩種誤判方向都損害驗收的可信度。

**Action**：
1. 修正驗證子句本身（如補齊 grep 排除清單、換更精準的確認方法），AC 實質要求原文不動。
2. 不需要 `blockedBy`，也不需要退回 `pending`——工作本身已完成，只是量尺失準。
3. 修正後以新驗證方法重新檢查一次，確認結論一致再勾選。

### 與 acceptance 漂移反模式的邊界

判準二**不是**放寬驗收標準的授權。以下兩種情況必須嚴格區分：

| 情況 | 是否命中判準二 | 正確處置 |
|------|--------------|---------|
| 驗證管道本身對現象不敏感（如 grep 例外清單遺漏），修正管道後結論不變 | 是 | 修正驗證子句，AC 原文不動 |
| 實質要求根本沒做到，藉口「這只是驗證方法問題」試圖放行 | 否 | 依實況判定未完成，不可勾選；此為 acceptance 漂移（見 `PC-055`），必須退回代理人補做 |

`.claude/agents/acceptance-auditor.md`「禁止放寬驗收標準」的既有規則於此依然適用：判準二修正的對象是驗證子句的表述精度，不是實質要求的門檻高度。

### 操作流程

PM 遇 AC 爭議裁決時：
1. 先問核心區分軸問句：癥結在實質要求還是驗證方法？
2. 依對應判準的判別問句確認命中哪一類（可能兩者皆非，需另行評估是否為 AC 本身過時）。
3. 判準一 → `blockedBy` + 退回 `pending`；判準二 → 修正驗證子句 + AC 原文不動。
4. 兩者皆不成立時，依實況直接判定完成/未完成，不可用任一判準當藉口迴避裁決。

### 相關文件（本節專屬）

- `.claude/methodologies/acceptance-criteria-methodology.md`「條件式驗收條件的設計判準」— AC 撰寫階段如何預先避免爭議
- `.claude/error-patterns/process-compliance/PC-BAL-010-verification-channel-insensitive-to-target-phenomenon.md` — 判準二的理論基礎（恆真/恆偽驗證管道）
- `.claude/error-patterns/process-compliance/PC-055-ticket-ac-drift-undetected.md` — acceptance 漂移反模式
- `.claude/agents/acceptance-auditor.md` — 「禁止放寬驗收標準」既有規則

---

## 相關文件

- @.claude/pm-rules/decision-tree.md - 主線程決策樹
- @.claude/pm-rules/skip-gate.md - Skip-gate 防護機制
- @.claude/rules/core/cognitive-load.md - 認知負擔設計原則
- @.claude/pm-rules/tdd-flow.md - TDD 流程
- @.claude/pm-rules/incident-response.md - 事件回應流程
- .claude/references/verification-scenario-examples.md - 場景範例
- .claude/references/verification-hook-implementation.md - Hook 實作細節

---

## 品質不達標重做決策

| 品質問題 | 處理方式 |
|---------|---------|
| 測試未通過（檢查 1） | 派發 incident-responder 分析，不可直接修復 |
| dart analyze 有新增 error（檢查 1） | 退回執行代理人修復 |
| 改了範圍外的檔案（檢查 2） | 退回執行代理人還原範圍外的變更 |
| 驗收條件的產出缺漏或格式不符（檢查 3） | 退回執行代理人補充，附上具體缺失說明 |
| 認知負擔超標、其他品質建議 | 不退件，建立重構 Ticket 排進後續版本 |

重做上限：同一 Ticket 重做 3 次後，PM 必須重新評估 Ticket 設計是否合理。

---

**Last Updated**: 2026-11-09
**Version**: 2.1.0 - 〈驗收三項固定檢查〉新增〈檢查 2 的 where 擴充程序〉：概念替換類票在 where 以外 grep 到同概念命中時，執行者停手回報，PM 以 set-where 擴充並記理由，驗收以擴充後的 where 機械比對、無理由的擴充條目視為範圍外。消解檢查 2 與 DOC-008 變體的衝突。來源：用戶裁定（2026-11-09）
**Version**: 2.0.0 - 新增〈驗收三項固定檢查〉：收退只看能不能跑、有沒有動到範圍外的檔案、輸出格式對不對，其他一律不退件；Phase 4 與多視角審查照跑，發現排進後續版本。〈驗證失敗處理〉Level 3／4 與〈品質不達標重做決策〉依三項改寫。來源：用戶裁定（2026-11-09）
**Version**: 1.11.0 - 新增「合併前全綠與實機驗證票」章節（時點分工、開票條件、名額閘門排入、與 CI 分工）；Phase 3b 驗收改為本票相關測試檔
**Version**: 1.10.0 - 新增「驗收條件爭議裁決框架」（Level 4 延伸）：核心區分軸（實質要求 vs 驗證方法）+ 判準一（條件未觸發不等於條件未滿足，附 blockedBy 表達法）+ 判準二（實質要求不等於驗證代理指標，附 PC-BAL-010 理論依據）+ 與 acceptance 漂移反模式的邊界 + PM 操作流程
**Status**: Active
**Responsible**: rosemary-project-manager, acceptance-auditor, Hook 系統

**Change Log**:
- v1.10.0 (2026-08-10): 新增「驗收條件爭議裁決框架」章節，補足 PM 裁決 AC 與實況爭議時缺乏固定判準、需臨場推導的缺口；與 `acceptance-criteria-methodology.md`「條件式驗收條件的設計判準」章節雙向引用
- v1.9.0 (2026-05-08): 新增 ANA 專屬驗收 checklist（Q1 規劃 vs ticket / Q2 數量比對 / Q3 否定標記），每題附 Why/Consequence/Action 三明示；作為 hook 強制層 + 規則自律層之外的第三道行為層防護（W17-170，源 W17-167）
- v1.8.0 (2026-03-27): 新增品質不達標重做決策
- v1.7.0 (2026-03-13): Level 3 新增「驗收條件主動勾選」驗證項目
- v1.5.0 (2026-03-04): Level 1 新增建立後品質審核
- v1.4.0 (2026-02-26): Level 3 新增並行派發後驗證
- v1.3.0 (2026-02-10): Level 1 新增 Ticket 內容品質驗證
- v1.2.0 (2026-02-06): Context 最佳化
- v1.1.0 (2026-01-30): Level 4 驗收層更新
- v1.0.0 (2026-01-23): 初始版本
