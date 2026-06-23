# TDD 含 SA 前置審查流程

本文件定義包含 SA（System Analyst）前置審查的完整 TDD 開發流程。

---

## 流程總覽

```
需求進入
    |
    v
需求類型判斷
    |
    +-- 新功能需求 --> [Phase 0] SA 前置審查 → saffron-system-analyst
    |                      |
    |                      +-- 通過 --> 進入 TDD Phase 1
    |                      +-- 不通過 --> 補充前置作業 --> 重新審查
    |
    +-- Legacy Code 處理 --> [Phase 0-L] Legacy Code 評估
                               |
                               +-- Step 1: UC/功能盤點
                               +-- Step 2: 逐 UC 測試漏洞分析
                               +-- Step 3: 根因分類（知識/基礎設施/設計）
                               +-- Step 4: 多視角精簡（含語言代理人）
                               +-- Step 5: 聚焦執行
                               |
                               +-- 完成 --> 進入 TDD Phase 1（如需新功能）
                               +-- 完成 --> 直接結束（如僅修復測試）
    |
    v
[Phase 1] 功能設計 → [lavender-interface-designer](../../agents/lavender-interface-designer.md)
    |
    v
[Phase 1.5] 規格多視角審查 → /parallel-evaluation G（Consistency/Completeness/CogLoad）
    |
    +-- 發現問題 → 建立修正 Ticket → 修正後重新審查
    +-- 通過 → 進入 Phase 2
    |
    v
[Phase 2] 測試設計 → [sage-test-architect](../../agents/sage-test-architect.md)
    |
    v
[Phase 3a] 策略規劃 → [pepper-test-implementer](../../agents/pepper-test-implementer.md)
    |
    v
[3b 拆分評估] PM 評估是否拆分為多個並行子任務
    |
    +-- 不拆分（豁免）→ 單一 parsley 執行
    +-- 拆分 → 建立 N 個子任務，並行派發
    |
    v
[Phase 3b] 實作執行 → [parsley-flutter-developer](../../agents/parsley-flutter-developer.md)
    |
    v
[Phase 4a] 多視角分析 → /parallel-evaluation B（Redundancy/Coupling/Complexity）
    |
    v（豁免時直接跳至 Phase 4b）
[Phase 4b] 重構執行 → [cinnamon-refactor-owl](../../agents/cinnamon-refactor-owl.md)
    |
    v（豁免時跳過 Phase 4c，直接執行 /tech-debt-capture → 完成）
[Phase 4c] 多視角再審核 → /parallel-evaluation A（Reuse/Quality/Efficiency）
    |
    v
完成 → 提交
```

> **各 Phase 的摩擦力配置原則**：前期階段（Phase 0/1/1.5）為決策點，摩擦力應較高（強制審查、多視角）；後期階段（Phase 3b）為執行點，摩擦力應較低（Hook 自動化、快速迭代）。詳見 `.claude/methodologies/friction-management-methodology.md`「開發流程階段的摩擦力曲線」章節。

---

## TDD Phase 代理人職責清單

PM 派發 Phase 代理人時可立即查表確認允許/禁止產出，防止職責越界（如 W5-001 Phase 2 sage 越界撰寫測試 .py 實作案例）。

| Phase | 代理人 | 允許產出 | 禁止產出 |
|-------|-------|---------|---------|
| 0 | saffron | 系統審查報告 | 程式碼、測試 |
| 1 | lavender | 功能設計文件 | 程式碼、測試檔 |
| 2 | sage | 測試設計文件 | **測試 .py 實作**（W5-001 Phase 2 越界教訓）|
| 3a | pepper | 實作策略/虛擬碼 | 真實 .py 程式碼 |
| 3b | {lang}-developer | 真實程式碼 + 測試 .py | 修改既有測試契約 |
| 4 | cinnamon | 重構評估 + 重構執行 | 新功能開發 |

---

## Phase 0：SA 前置審查

### 觸發條件

| 條件 | 需要 SA 審查 |
|------|-------------|
| 新功能需求 | 是 |
| 架構變更 | 是 |
| 影響 3+ 模組 | 是 |
| 小型修改/Bug 修復 | 否 |

### 審查內容

1. **系統一致性檢查** - 與現有架構是否一致、遵循設計原則、無命名衝突
2. **重複實作檢查** - 無類似功能、無可重用元件、無重複造輪子
3. **需求文件完整性** - 需求書有記錄、用例有定義、驗收標準明確

### 審查結論

| 結論 | 下一步 |
|------|-------|
| 通過 | 進入 Phase 1 |
| 需補充 | 完成補充後重新審查 |
| 不建議 | 升級到 PM 決定 |

> 詳細規格：@.claude/agents/saffron-system-analyst.md

---

## ANA 全量 grep/regex 範圍驗證完整性規範

> **適用範圍**：所有 ANA Ticket 中涉及「全量 grep/regex 範圍判定」的 Solution——即 ANA 結論中含「某字元集/字串集於整個 codebase 中的覆蓋範圍」判定，且結論影響後續 IMP acceptance 設計者。

**Why**：ANA 若以手工列舉 Unicode 區段作為「已知全量」依據，遺漏的區段會讓後續 IMP ticket 的 acceptance 建立在錯誤基礎上。W1-005 ANA 案例：AC-4「直接斷言依賴=0」僅用 `rg 'Popup Script 載入完成' tests/` 單一關鍵字驗證，未掃描 tests/ 下所有 emoji 字面，致誤判「無斷言依賴」（實際 12 檔 48+ 處）；加上 emoji 偵測範圍靠手工列舉 U+1F000-1FFFF + U+2600-27BF 兩區段，漏 U+2139-25B6 區段 9 種 + FE0F 336 處，造成範圍二度誤判。

**Consequence**：ANA 範圍判定失準會導致：(a) IMP acceptance 建立在錯誤覆蓋假設上；(b) IMP 執行期才發現範圍不足，需新增 patch ticket；(c) 每次範圍修訂都讓前後 ticket 的驗收條件不一致，後人難以追蹤正確基準。

**Action**：ANA Solution 中含「全量 grep/regex 範圍判定」時，必須在 Solution 明示以下三項：

### 1. 驗證方法涵蓋完整性聲明（必填）

| 驗證方法 | 適用場景 | 已知盲區 |
|---------|---------|---------|
| **區段列舉法**（手工列 Unicode block） | 已知目標字元屬特定 block，block 數量少（≤5） | 遺漏未列舉的 block；FE0F 等修飾符跨 block 不會被涵蓋 |
| **全字元集掃描法**（Python `unicodedata` + `rg` 搭配）| 不確定目標字元分佈，或需要完整 codebase 掃描 | 需安裝 Python 依賴；regex 語法需正確覆蓋多字節 |
| **直接 rg regex 法**（單一 pattern 掃描）| 目標字元有明確唯一 regex 模式 | Pattern 不完整會遺漏邊際字元；依賴作者對字元集的完整認識 |

Solution 必須明示使用哪種驗證方法，並說明「此方法的已知盲區」及「為什麼認為此盲區不影響本 ANA 結論」。

**三種方法的組合使用（推薦）**：

若範圍判定屬高風險（後續 IMP 範圍直接從 ANA 繼承），建議「全字元集掃描 + rg 交叉驗證」：

```bash
# Step 1：Python 全字元集掃描，取得完整字元清單
python3 -c "
import subprocess, unicodedata
result = subprocess.run(['rg', '--no-filename', '-o', '.', 'path/'], capture_output=True, text=True)
chars = set(result.stdout.replace('\n', ''))
targets = {c for c in chars if unicodedata.category(c).startswith('S') or unicodedata.category(c) == 'So'}
print(sorted(hex(ord(c)) for c in targets))
"

# Step 2：rg 驗證特定字元在測試檔的依賴關係
rg -rn '[\xf0-\xf4][\x80-\xbf]{3}|[\xe2-\xe3][\x80-\xbf]{2}' tests/ --count-matches
```

### 2. 覆蓋完整性聲明格式

ANA Solution 涉及全量 grep/regex 範圍判定時，必須包含以下格式的聲明（置於 Solution 結論前）：

```markdown
**範圍驗證方法**：[列舉法 / 全字元集掃描法 / rg regex 法 / 組合]
**驗證指令**：（附上實際執行的指令或腳本）
**已知盲區**：（說明此方法無法偵測什麼）
**盲區影響評估**：（說明為何盲區不影響本結論，或盲區已另行驗證）
```

**強制觸發條件**：ANA Solution 中若出現以下任一句型，即視為「全量 grep/regex 範圍判定」，必須補上上方聲明：

| 句型 | 說明 |
|------|------|
| 「X 在 codebase 中共有 N 處」 | 數量斷言 |
| 「無任何 X 依賴」「X 依賴 = 0」 | 零依賴斷言 |
| 「X 僅出現於 [路徑]」 | 路徑範圍斷言 |
| 「所有 X 已覆蓋 Unicode 區段 U+XXXX-YYYY」 | 字元集覆蓋斷言 |

### 3. AC 設計連動要求

ANA 的覆蓋完整性聲明必須直接體現在後續 IMP 的 acceptance 設計中：

| ANA 結論 | IMP acceptance 要求 |
|---------|-------------------|
| 「依賴 = 0（驗證方法：rg regex 全路徑）」 | acceptance 必須含與 ANA 相同 rg 指令的重新驗證 |
| 「依賴 = N 處（驗證方法：全字元集掃描）」 | acceptance 含「執行相同掃描腳本確認 = 0 後」通過 |
| 「覆蓋區段 U+XXXX-YYYY」 | acceptance 含「全字元集掃描確認無遺漏後」通過 |

**禁止**：IMP acceptance 僅驗 build/lint 通過而不重新驗證 ANA 所聲明的範圍（W1-005.2 根因）。

> **觸發案例**：W1-005 ANA AC-4 二度誤判（單關鍵字 rg 替代全量掃描 + 手工區段列舉漏 FE0F）→ 兩個 patch ticket + 48+ 處隱性測試回歸（W1-007 ANA 教訓 1）
>
> **相關 Error Pattern**：本規範與 `.claude/error-patterns/process-compliance/PC-161-ana-grep-scope-misjudgment-collapses-precedent-argument.md` 互補。PC-161 聚焦「ANA 以 grep 結果支撐強論證但範圍有誤」；本規範聚焦「ANA 涉及 Unicode/字元集覆蓋判定的完整性聲明要求」。兩者同屬 ANA grep 驗證品質家族，防護不同面向。

---

## Phase 0-L：Legacy Code 評估

### 觸發條件

| 條件 | 需要 Legacy Code 評估 |
|------|---------------------|
| 接手現有專案/模組 | 是 |
| 測試大量失敗（>10%） | 是 |
| 為無測試的程式碼建立測試 | 是 |
| 現有測試全部通過的新功能開發 | 否（走 Phase 0 SA 審查） |

### 評估流程

遵循 Legacy Code 測試重建方法論的五步驟流程：

1. **UC/功能盤點** — 列出所有功能和測試覆蓋狀態
2. **逐 UC 測試漏洞分析** — 跑測試、記錄失敗模式
3. **根因分類** — 區分知識問題 / 基礎設施問題 / 設計問題
4. **多視角精簡** — 含語言代理人，避免過度工程
5. **聚焦執行** — 只做解決根因的工作

### 評估結論

| 結論 | 下一步 |
|------|-------|
| 主要是知識問題 | 更新 CLAUDE.md + 代理人知識，可直接進入 TDD |
| 主要是基礎設施問題 | 建立修復 Ticket，完成後進入 TDD |
| 主要是設計問題 | 建立重構 Ticket，優先修復架構後再進入 TDD |

> 詳細方法論：@.claude/methodologies/legacy-code-test-rebuild-methodology.md

---

## 任務類型豁免規則

並非所有任務都需要完整 TDD（Phase 0-4）。遷移/轉換類任務適用簡化流程。

**識別標準**（任一符合即視為遷移任務）：

- 主要工作是「轉換」而非「建立新業務邏輯」
- 輸出可完全由輸入推導（無新業務規則）
- 現有測試或驗證步驟已足夠確認正確性

**禁止行為**：

| 禁止 | 說明 |
|------|------|
| 以「遷移任務」跳過結果驗證 | 驗證是遷移任務不可省略的步驟 |
| 無 dry-run 或備份直接執行不可回滾的遷移 | 須先備份或執行 dry-run |
| 將有新業務邏輯的任務誤判為遷移 | 遷移是純轉換，有新邏輯則走完整 TDD |

> 遷移任務範例、TDD Phase 豁免表、簡化流程：.claude/references/tdd-flow-details.md（任務類型豁免規則章節）

---

## Phase 1.5：規格多視角審查（Phase 1 完成後強制）

### 目的

單一視角必然有盲點。Phase 1 產出的功能規格、Schema 定義、邊界條件等文件，需經多視角審查才能作為測試和實作的穩定依據。

### 觸發條件

Phase 1 功能規格完成後**強制執行**，無豁免。

### 審查方式

使用 `/parallel-evaluation`（情境 G：系統設計）派發三人組：

| 視角 | 審查重點 |
|------|---------|
| linux（常駐） | 設計品味：是否過度複雜、YAGNI、是否有更簡單的解法 |
| Consistency | 跨文件一致性：UC vs Schema vs Storage vs 遷移規則 |
| Completeness | 邊界條件完整性：遺漏的錯誤場景、模糊的規格、測試撰寫時的缺口 |

### 審查後處理

| 發現優先級 | 處理方式 |
|-----------|---------|
| 高（設計缺陷、雙重真相、YAGNI） | 建立修正 Ticket，修正後方可進入 Phase 2 |
| 中（規格模糊、邊界遺漏） | 建立修正 Ticket，修正後方可進入 Phase 2 |
| 低（風格、最佳化建議） | 建立延後追蹤 Ticket，不阻擋 Phase 2 |

### 通過條件

所有高/中優先發現的修正 Ticket 已完成。低優先可延後。

---

## Phase 1-4：標準 TDD 流程

| Phase | 代理人 | 產出 |
|-------|-------|------|
| Phase 1 功能設計 | lavender-interface-designer | 功能規格、API 定義、驗收標準 |
| Phase 1.5 規格審查 | /parallel-evaluation G | 跨文件一致性、邊界完整性、設計品味 |
| Phase 2 測試設計 | sage-test-architect | 測試案例、GWT 規格、檔案結構 |
| Phase 3a 策略規劃 | pepper-test-implementer | 策略文件、虛擬碼、債務評估 |
| Phase 3b 實作執行 | parsley-flutter-developer | 程式碼、通過測試、品質報告 |
| Phase 4a 多視角分析 | /parallel-evaluation B | 重構分析報告 |
| Phase 4b 重構執行 | cinnamon-refactor-owl | 重構程式碼、債務記錄 |
| Phase 4c 多視角再審核 | /parallel-evaluation A | 審核報告 |

**Phase 4 派發前預檢（強制）：TD 清單校準（td-status）**

Phase 4a 或 Phase 4b（豁免時）派發前，PM 必須執行 TD 清單校準，確認已完成項不浪費多視角 token：

```bash
ticket track td-status <ticket-id>
```

| 輸出狀態 | PM 動作 |
|---------|---------|
| 無 pending TD 或 pending 皆符合預期（本 Phase 待處理） | 直接進行派發 |
| pending TD 實際已處理但未標記 | 先於 body 補標「已處理：[原因]」再派發 |
| pending TD 確認無需處理 | 先於 body 補標「無需處理：[原因]」再派發 |

> **Why**：Phase 3a/3b 演進中已修正的 TD 若未更新清單，多視角分析會在已完成項上消耗 token，降低 Phase 4 審查效能（PC-094 W10-017.8 案例教訓）。完整校準規則見 `.claude/pm-rules/tech-debt.md`「TD 清單即時校準（td-status）」章節。

**Phase 4 豁免條件（可簡化為單步驟，直接 Phase 4b，跳過 4a/4c）**：

| 豁免情況 | 說明 |
|---------|------|
| 小型修改（修改 <= 2 個檔案） | 影響範圍有限，多視角成本大於收益 |
| DOC 類型任務 | 純文件更新，不涉及程式碼品質 |
| 任務範圍單純（單一模組、修改目的明確） | 低複雜度任務，cinnamon 單視角已足夠 |

**Phase 4 強制 Checkpoint：重構評估 → WRAP Phase 2**：

Phase 4a 多視角分析報告完成後，進入 Phase 4b 前，PM 必須執行 WRAP Phase 2 檢驗：

| 步驟 | 說明 |
|------|------|
| 觸發條件 | Phase 4a 報告完成（或豁免後直接進 Phase 4b 前） |
| 強制動作 | 以 Phase 4a 報告結論為 Phase 1 輸入，執行 WRAP Phase 2（R + A + P 三問） |
| 目的 | 防止重構評估「太表層」——確認根因假設層級多元（非僅實作手段層級），並檢驗機會成本 |
| 參考 | `.claude/skills/wrap-decision/SKILL.md`「觸發條件」S4 節 + `.claude/methodologies/three-phase-reflection-methodology.md` |
| 豁免 | DOC 類型任務（無程式碼品質問題）+ 小型修改（認知負擔 <= 5）可豁免 |

> 各 Phase 詳細描述和代理人連結：.claude/references/tdd-flow-details.md（Phase 1-4 章節）

---

## 階段轉換規則

### 轉換條件

| 從 | 到 | 條件 | PM 強制動作 |
|----|----|------|-----------|
| Phase 0 | Phase 1 | SA 審查通過 | 填寫 Context Bundle（→ Phase 1） |
| Phase 1 | Phase 1.5 | 功能規格完成 | 填寫 Context Bundle（→ 多視角審查） |
| Phase 1.5 | Phase 2 | 多視角審查通過 + Phase 2 條件式強制判斷（見下方） | 填寫 Context Bundle（→ Phase 2） |
| Phase 2 | Phase 3a | 測試案例設計完成 | 填寫 Context Bundle（→ Phase 3a） |
| Phase 3a | 3b 拆分評估 | 策略文件完成 | 填寫 Context Bundle（→ Phase 3b） |
| 3b 拆分評估 | Phase 3b | PM 完成拆分評估（見下方） | 各子任務填寫 Context Bundle |
| Phase 3b | Phase 4a 或 4b | 測試全部通過 | 填寫 Context Bundle（→ Phase 4a） |
| Phase 4a | Phase 4b | 多視角分析報告完成 | - |
| Phase 4b | Phase 4c | 重構執行完成 | - |
| Phase 4c | 完成 | 多視角再審核報告完成 | - |

> **Context Bundle**：PM 在派發下一階段代理人前，必須將該代理人所需的前置資訊寫入 Ticket。詳見 `.claude/pm-rules/context-bundle-spec.md`。

### Phase 2 條件式強制判斷（Phase 1.5 通過後，W1-004）

Phase 1 完成後，依 source spec 有無和 FR 驗收標準規模決定 Phase 2 形態：

| 情境 | Phase 2 需求 |
|------|-------------|
| 有 spec 且 FR 驗收標準合計 >= 3 條 | 強制：ANA 必須產出至少一個 Phase 2 測試設計 ticket（派發 sage-test-architect） |
| 有 spec 但 FR 驗收標準合計 < 3 條 | 建議：可在 IMP ticket 內嵌入測試設計 |
| 無 spec（純 bug fix / 流程改善） | Phase 2 豁免 |

**Why**：Phase 2 的價值在於「紅燈先行」確保 spec 驗收標準被轉化為可執行測試。小範圍 FR 可在 IMP 內同步處理；大範圍 FR 需 sage 獨立設計以避免 IMP 執行者漏蓋 spec 邊界條件。

### 3b 拆分評估（Phase 3a 完成後，強制）

Phase 3a 策略文件完成後，PM **必須**評估 Phase 3b 是否需要拆分為多個並行子任務。

**拆分決策表**（基於 SRP 功能職責導向，任一觸發即拆分）：

| 指標 | 觸發條件 | 判定 |
|------|---------|------|
| 功能職責數 | Phase 3a 策略文件中識別出 > 1 個獨立功能職責 | 必須拆分 |
| 測試群組數 | Phase 2 定義的 GWT scenario group > 3 個且無交叉依賴 | 建議拆分 |
| 認知負擔指數 | > 10 | 必須拆分 |
| 跨架構層級數 | > 2 層 | 必須拆分 |

> **SRP 優先原則**：拆分判斷的首要標準是「功能職責是否單一」，而非 context 預算。代理人做得到不代表應該合併——讓代理人專注單一功能面才能發揮最大效能。
>
> **依賴不阻擋拆分**：測試群組間有函式呼叫依賴不代表不能拆分，可透過序列派發解決。

**拆分單位：測試群組**（非模組/檔案）

拆分的最小單位是 Phase 2 定義的 **GWT scenario group**（測試群組），而非模組或檔案。每個 3b 子任務聚焦「通過特定測試群組」，代理人只需理解該群組的 API 簽名和測試案例，不需理解整個模組。

| 拆分方式 | 子任務定義 | 代理人需讀取 |
|---------|-----------|------------|
| 按測試群組（推薦） | 「通過 TC-01~TC-13」 | 對應 API 簽名 + 測試案例 |
| 按模組（舊方式） | 「實作 Module A」 | 整個模組設計文件 |

**無需拆分**：上述觸發條件均未命中（單一功能職責、單一測試群組、負擔 <= 10、層級 <= 2），且修改目的單一明確時，由單一代理人執行。

### Context 預算評估（輔助參考，非拆分主標準）

> **定位**：Context 預算是拆分後的**資源規劃工具**，不是拆分與否的判斷標準。先用 SRP 決定是否拆分，再用 context 預算規劃各子任務的資源分配。

PM 在派發 Phase 3b 代理人前，可根據 Phase 3a 策略文件估算 context 消耗，用於規劃子任務粒度和代理人資源。

**當 context 預算顯示單一子任務仍然過大時**（如超過 20K tokens），應檢查該子任務是否仍包含多個功能職責，需進一步拆分。

> **來源**：Phase 3b 單一代理人 context 耗盡事件分析

**拆分時的操作**：

1. 依 Phase 2 的 GWT scenario group 劃分，建立 N 個子任務（`/ticket create --parent {3b_ticket_id}`）
2. 每個子任務標明測試群組範圍（如 `TC-01~TC-13`）和對應修改檔案清單（`where.files`），確保檔案無交集
3. PM 使用 Phase 3b prompt 模板（見 `.claude/references/phase3b-prompt-template.md`）提取必要資訊，限定代理人只讀 API 簽名 + 測試案例
4. 執行並行安全檢查（見 parallel-dispatch.md）
5. 並行派發 parsley-flutter-developer 執行各子任務

> 詳細評估流程和範例：.claude/references/tdd-flow-details.md（3b 拆分評估章節）

### 轉換動作

**Phase 1/2/3a（代理人自治）**：

代理人完成後自行執行，PM 不介入：

1. 更新 Ticket Execution Log（`ticket track append-log`）
2. 執行 `git commit`（message 格式：`feat({ticket-id}): Phase X 完成 - {摘要}`）
3. 執行 `/ticket track complete {id}`
4. 回報主線程：僅「成功」或「失敗 + 原因」

**Phase 3b/4a/4b/4c（PM 管理）**：

PM 收到代理人回報後執行：

1. 讀取代理人的「Phase N 完成摘要」
2. 提取關鍵資訊，填寫下一階段的 Context Bundle（`ticket track append-log --section "Context Bundle"`）
3. 執行 `/ticket track complete {id}`
4. 更新工作日誌
5. 依決策樹第八層 Checkpoint 路由下一步

---

## 異常處理

| 情況 | 處理方式 |
|------|---------|
| 測試失敗 | 強制派發 incident-responder → 建立 Ticket → 對應代理人修復 |
| SA 審查發現問題 | 建立補充 Ticket → 完成後重新審查 |
| 需要跨階段修改 | 建立 Ticket → 完成當前階段後回到對應階段 |

> 異常處理詳細流程和工作日誌模板：.claude/references/tdd-flow-details.md（異常處理章節）
> 事件回應流程：.claude/pm-rules/incident-response.md

---

## 相關文件

- .claude/skills/tdd/SKILL.md - `/tdd` SKILL（統一 TDD 流程入口，含 `/tdd start`、`/tdd next`、`/tdd split`、`/tdd status`、`/tdd phase4-exempt`）
- .claude/references/tdd-flow-details.md - 豁免規則詳細、Phase 詳細描述、異常處理、日誌模板
- .claude/pm-rules/decision-tree.md - 主線程決策樹
- .claude/pm-rules/context-bundle-spec.md - Context Bundle 規範（派發前資訊準備）
- @.claude/rules/core/quality-baseline.md - 品質基線（Phase 4 不可跳過）

---

## SA 否決升級路徑

當 saffron-system-analyst 在 Phase 0 否決 Ticket 時：

| 否決原因 | 升級路徑 |
|---------|---------|
| 與現有架構衝突 | PM 評估是否需要架構調整，建立 ANA Ticket |
| 需求不清晰 | PM 使用 AskUserQuestion 釐清需求後重新提交 SA 審查 |
| 重複功能 | PM 確認是否與既有 Ticket 合併或關閉 |
| 技術不可行 | PM 與用戶討論替代方案 |

SA 否決不可繞過 — 必須解決否決原因後重新審查。

---

**Last Updated**: 2026-06-04
**Version**: 2.18.0 — 新增「ANA 全量 grep/regex 範圍驗證完整性規範」獨立章節：三層強制要求（驗證方法涵蓋完整性聲明、覆蓋完整性聲明格式、AC 設計連動），觸發案例 W1-005 ANA AC-4 二度誤判（0.19.1-W1-039）
**Version**: 2.17.0 — Phase 4 派發前新增「TD 清單校準（td-status）」預檢步驟（W10-083 / PC-094 落地，防止多視角浪費 token 在已完成 TD 項）
**Version**: 2.16.0 - Phase 4 新增強制 Checkpoint：重構評估前執行 WRAP Phase 2 檢驗（W15-019，防止重構根因分析太表層）
**Version**: 2.15.0 - 新增 Phase 1.5 規格多視角審查（單一視角必然有盲點，規格完成後強制多視角審查）
