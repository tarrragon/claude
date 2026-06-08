# 引用穩定性規則

> **本檔承載原 `.claude/rules/core/document-format-rules.md` 規則 7-8**。規則 1-6、YAML frontmatter、檢查清單骨架仍保留在 document-format-rules.md 自動載入。

本文件定義「引用穩定性」相關規範：規格文件的引用穩定性（規則 7）和框架文件對專案層級識別符的引用禁制（規則 8）。兩者共享「哪些來源可信、哪些引用會在時間或跨專案 sync 中失效」的核心主題。

---

## 適用情境（何時需要讀取本檔）

| 情境 | 涉及規則 |
|------|---------|
| 編輯 `docs/spec/`、`docs/use-cases.md`、`docs/proposals/` 等規格文件 | 規則 7 |
| 編輯 `.claude/` 框架檔案（rules / pm-rules / references / methodologies / agents / skills / hooks / error-patterns / best-practices） | 規則 8 |
| Code review 時檢查跨檔案引用是否指向穩定來源 | 規則 7、規則 8 |
| 升級 memory 或 ticket 內容至框架層時評估引用穩定度 | 規則 7、規則 8 |

---

## 規則 7：規格文件引用穩定性

**規格文件（docs/spec/、docs/use-cases.md）禁止引用臨時性文件**

| 文件類型 | 穩定性 | 可被規格引用 |
|---------|--------|------------|
| 規格文件（docs/spec/） | 穩定 | 是 |
| Use Cases（docs/use-cases.md） | 穩定 | 是 |
| 提案文件（docs/proposals/） | 穩定 | 是 |
| CLAUDE.md | 穩定 | 是 |
| Worklog（docs/work-logs/） | 臨時 | **否** |
| Ticket 檔案 | 臨時 | **否** |
| Plan 檔案 | 臨時 | **否** |

**允許的例外**：
- 變更歷史中記錄 Ticket ID 作為「來源標注」（如：「本次變更由 0.17.0-W1-002 執行」）
- 這是記錄歷史事實，不是建立依賴

**禁止的模式**：

| 禁止 | 原因 | 正確做法 |
|------|------|---------|
| `詳見 v0.17.1 W1-001` | Ticket 可能被遷移、刪除、重新編號 | `待定義於匯出規格章節` 或直接在此定義 |
| `參考 docs/work-logs/v0.17/...` | Worklog 會被歸檔，路徑可能失效 | 引用對應的 spec 文件 |
| `依 0.18.0-W2-001 的分析結論` | 結論應提煉為規格，而非依賴分析過程 | 將結論寫入規格文件 |

**理由**：
- 規格文件是開發的**唯一穩定依據**，worklog 和 ticket 是**過程記錄**
- 過程記錄可能遺失、修改、遷移，規格文件不應依賴不穩定來源
- 如果規格需要引用的資訊尚未定義，標記為「待定義」而非指向臨時文件

---

## 規則 8：框架文件禁止引用專案層級識別符

**`.claude/` 框架文件禁止引用專案特定的 ticket ID、commit hash、worklog 路徑等專案層級識別符**

`.claude/` 是**跨專案共用框架**，透過 sync 機制同步到多個專案（如 `.claude/skills/sync-push`、`sync-pull`）。專案層級識別符只存在於當前專案，sync 到其他專案後會變成死連結和誤導性資訊。

| 識別符類型 | 範例 | 可在框架文件引用？ |
|---------|------|-----------------|
| 專案 ticket ID | `0.18.0-W5-001`、`W2-007` | **否** |
| 專案 commit hash | `8f74d08`、`abc1234` | **否** |
| 專案 worklog 路徑 | `docs/work-logs/v0.17/...` | **否** |
| 專案 proposals ID | `PROP-007` | **否**（除非已提煉為方法論） |
| 框架 error-pattern ID | `PC-050`、`IMP-003`、`ARCH-002` | **是**（框架內部分類） |
| Claude Code 版本號 | `CC 2.1.97` | **是**（外部平台識別） |
| 框架檔案路徑 | `.claude/rules/core/pm-role.md` | **是**（框架內部結構） |

**適用範圍**：

| 目錄 | 適用規則 8？ |
|------|-------------|
| `.claude/rules/` | 是 |
| `.claude/pm-rules/` | 是 |
| `.claude/references/` | 是 |
| `.claude/methodologies/` | 是 |
| `.claude/error-patterns/` 內容（檔名除外） | 是 |
| `.claude/agents/` | 是 |
| `.claude/skills/` | 是 |
| `.claude/hooks/` Python docstring/comment | 是 |
| `.claude/best-practices/` | 是 |
| `.claude/handoff/archive/` | **否**（歷史紀錄，合理保留） |
| 專案 `docs/` | **否**（專案內部，可引用） |
| `CLAUDE.md` | **否**（專案入口，可引用） |

**Memory 和 ticket 也是專案層級**：

用戶/專案 auto-memory（`~/.claude/projects/<project>/memory/`）和 ticket（`docs/work-logs/`）**都不會跨專案 sync**，所以「把原則寫到 memory」不能取代框架規則。需要跨專案落實的原則必須寫入：
- `.claude/rules/`（自動載入規則）
- `.claude/error-patterns/`（錯誤學習經驗）
- `.claude/methodologies/`（方法論）

**禁止的模式**：

| 禁止 | 改為 |
|------|------|
| `（來源：0.18.0-W4-002）` | `（防範 Hook error 干擾代理人判斷）` |
| `（W5-021 教訓）` | `（多代理人 permissionMode 批次修復教訓）` |
| `**Ticket**: 0.17.3-W12-001`（在 error-pattern 內） | 移除整行（檔名 PC-XXX 已是足夠識別） |
| `來源：PROP-007` | 以提案內容的抽象描述取代 |

**允許的例外**：

| 例外 | 說明 |
|------|------|
| error-pattern 檔名本身 | `PC-050-premature-agent-completion-judgment.md` 是框架內部分類 |
| 觸發日期 | 「2026-04-12 新增」可保留，日期不是專案識別符 |
| 通用 CC 能力版本號 | 「CC 2.1.97 新增 /agents 分頁」屬外部平台能力 |

**理由**：
- `.claude/` 經 sync 跨專案共用，專案識別符在其他專案是死連結
- 框架文件的價值在於**抽象原則**，專案引用是耦合而非依賴
- Memory/ticket 也是專案內部，不能承擔跨專案原則的傳遞責任

### 引用性質判準：依賴型 vs 歷史錨點型

> **本章節定位**：規則 8 上文是「載體 + 識別符類型」維度的禁制（哪些檔案、哪類識別符）。本章節補充「引用性質」維度——同樣是 ticket ID，**建立跳轉依賴**與**標注設計脈絡**兩種性質的處置不同。兩維度疊加才是完整判定。

**Why**：規則 8 字面「禁任何 ticket ID」與三個既有機制衝突——comment-writing 方法論鼓勵 inline comment 記錄「為什麼這樣做」的決策脈絡（含變更時點）；PC-093 `history` 豁免允許引用已完成歷史 / 動機脈絡作歷史錨點；文件慣例以變更歷史標注來源。框架程式碼 comment 的 `# 遷移後改用 X 模式` 這類設計脈絡標注，移除 ticket ID 後句子仍完整，與「詳見某 ticket」的跳轉依賴性質完全不同。

**Consequence**：缺判準會出現兩種失敗模式：(1) 嚴格執行字面 → 清理掉合理的設計脈絡記錄，違反 comment-writing 方法論，讀者失去「此處為何如此寫」的歷史脈絡；(2) 寬鬆執行 → 依賴型引用（讀者被引導查不存在的 ticket）漏網，sync 後死連結誤導。

**Action**：對每處 ticket ID 引用，先以操作判準分類為「依賴型（禁止）」或「歷史錨點 / 設計脈絡型（允許）」，再依處置欄行動。

#### 兩類定義

| 類別 | 引用性質 | 處置 | 典型形式 |
|------|---------|------|---------|
| 依賴型 | 建立跳轉依賴：明示或隱含「讀者需查該 ticket 才能理解本句」 | **禁止**，改抽象化或內聯定義 | `詳見 / 參考 / 依 / 根據 / 來源是 W-xxx`、「相關文件」章節列 ticket ID、規則正文以 ticket ID 作動機 / 銜接 / 驗證 |
| 歷史錨點 / 設計脈絡型 | 標注「何時 / 因何變更」的設計脈絡記錄，不建立跳轉依賴 | **允許** | 程式碼 inline comment `# 遷移後改用 X 模式`、設計變更時點標注 |

#### 操作判準（移除測試）

問：**移除 ticket ID 後，讀者是否仍能理解該句？**

| 測試結果 | 分類 | 處置 |
|---------|------|------|
| 仍能理解（ticket ID 為可選的時點標注） | 歷史錨點 / 設計脈絡型 | 保留 |
| 無法理解（ticket ID 是理解該句的必要跳轉目標） | 依賴型 | 抽象化（改檔案路徑 / 抽象角色 / PC 編號）或內聯定義 |

**為何歷史錨點型即使 sync 後是死編號也無害**：規則 8 的傷害模型是「sync 後死連結誤導」——讀者被引導去查一個在其他專案不存在的 ticket。歷史錨點型不引導讀者查 ticket（ticket ID 僅為時點標注），移除後句子完整，故不構成此傷害。依賴型才會讓讀者跳轉到不存在的編號，這正是規則 8 要防範的對象。

#### 正反範例

依賴型（禁止）：

| 引用 | 移除測試 | 修正 |
|------|---------|------|
| `詳見 W15-005 WRAP 方案 F` | 「詳見...方案 F」指向空 → 無法理解 | `詳見 wrap-decision SKILL 方案章節` |
| 「相關文件」章節列 `W10-011（擴充註解規則）` | 列為相關文件即建立跳轉依賴 | 改檔案路徑 `comment-writing-methodology.md` |
| 規則正文 `W10-011 為註解專項套用` | 移除後語意不完整（依賴該 ticket 脈絡） | 抽象角色「註解專項規則」（對齊 PC-098） |

歷史錨點 / 設計脈絡型（允許）：

| 引用 | 移除測試 | 判定 |
|------|---------|------|
| inline comment `# 遷移後此處改用 globalThis` 附時點標注 | 「遷移後此處改用 globalThis」仍可理解 | 歷史錨點型，保留 |
| inline comment `# 此防護源於某次 global 未定義崩潰事件` 附 ticket 時點 | 移除 ticket ID 後決策說明完整 | 設計脈絡型，保留 |

#### 三方對齊

本判準統一規則 8 與三個既有機制，消除衝突：

| 機制 | 適用載體 | 立場 | 與本判準關係 |
|------|---------|------|------------|
| 規則 7 來源標注例外 | `docs/` 規格文件（不 sync） | 允許變更歷史以 ticket ID 作來源標注 | 規格文件不 sync，來源標注等同歷史錨點型；框架文件 footer 因在 sync 範圍且對讀者無操作價值，仍依 PC-098 不引用（見下「邊界」） |
| PC-093 `history` 豁免 | ticket / worklog（不 sync） | 允許引用已完成歷史 / 動機脈絡作歷史錨點（事實陳述，非延後決策） | ticket 不 sync，歷史錨點合法；本判準將同一性質延伸至框架程式碼 comment |
| comment-writing 方法論 | 程式碼 comment（含框架 hooks / scripts） | 鼓勵 inline comment 記錄「為什麼這樣做」的決策脈絡 | 設計變更時點標注屬歷史錨點型，本判準明訂允許 |

#### 與 PC-098 的邊界

PC-098（PM 撰寫規則本能引用當下 ticket ID）禁止的「規則正文 / 相關文件 / footer 嵌入當下任務 ticket ID」，均屬依賴型（移除後理解斷裂）或無操作價值的紀念型。本判準是 PC-098 的上位區分框架，PC-098 立場不變：

| PC-098 禁止項 | 本判準分類 | 處置一致性 |
|--------------|----------|----------|
| 規則正文 `W-xxx 為 X 套用` | 依賴型 | 禁止，一致 |
| 「相關文件」列 ticket ID | 依賴型 | 禁止，一致 |
| Version footer `— W-xxx 落地`（無變更摘要） | 依賴型（移除後僅剩「落地」、無摘要無法理解改了什麼） | 禁止，內聯變更摘要 |

**框架文件 footer 來源標注的處理**：footer 同樣以操作判準「移除測試」判定，依「移除 ticket ID 後變更摘要是否仍完整」分流：

| footer 形式 | 移除測試 | 分類 | 處置 |
|------------|---------|------|------|
| `Version: 1.5.1 — 規則 6「以價值優先」加入（W-xxx）` | 移除後「規則 6 加入」變更摘要仍完整 | 歷史錨點型 | 保留 |
| `Version: 1.0.0 — W-xxx 落地`（PC-098 #3 例） | 移除後僅剩「Version: 1.0.0 — 落地」、無摘要 | 依賴型 | 禁止，內聯變更摘要（補「改了什麼」） |

此判定使 footer 與 PC-098、規則 7 三方自洽：PC-098 #3 禁止的 `— W-xxx 落地` 正是無變更摘要的依賴型 footer；含變更摘要的歷史來源標注屬歷史錨點型可保留，與規則 7「記錄變更歷史事實」例外一致。本檔自身 footer（`Version: 1.1.0 — 規則 8 新增...`）即屬含摘要的歷史錨點型，保留無 ticket ID 引用為更嚴格的自律選擇。

#### 功能字串（運行時輸出）子類

> **本子類定位**：補充「載體維度」。前述移除測試判定的歷史錨點型 ticket ID 允許保留，前提是載體為程式碼 comment / docstring（僅讀碼開發者可見）。當載體為**功能字串（運行時輸出）**時，即使通過移除測試屬歷史錨點型，仍應清理。此子類是歷史錨點型「允許保留」的明文例外。

**Why**：comment / docstring 的歷史錨點型 ticket ID 之所以允許保留，前提是讀者為讀碼的框架開發者——他們理解 ticket ID 僅為時點標注，不會誤以為是當前專案的有效編號。功能字串（hook 提示訊息、CLI 輸出、UI 文案、錯誤回饋）在 runtime 顯示給所有使用者；sync 到其他專案後，這些訊息會引導不知情的用戶去查一個在該專案不存在的 ticket。誤導面比 comment 廣得多——comment 僅暴露給讀碼開發者，功能字串暴露給每一個觸發該訊息的用戶。

**Consequence**：功能字串內保留 ticket ID（即使屬歷史錨點型）會在 sync 後對其他專案所有運行時用戶造成死連結誤導。用戶看到「參考案例：W-xxx」「估算依 W-xxx」會嘗試查找該 ticket，但該編號在其專案不存在，造成困惑並降低工具信任度。此傷害不因 ticket ID 屬「時點標注」性質而減輕，因為運行時用戶無從區分時點標注與有效引用。

**Action**：功能字串（運行時輸出）內的 ticket ID 一律清理，改為抽象描述或移除，不適用歷史錨點型保留。判別載體是否為功能字串：該字串是否會在 runtime 顯示給最終用戶（hook stdout / stderr 提示、CLI message、UI 文案、錯誤回饋）。是 → 清理；否（純 comment / docstring）→ 回到移除測試判定。

**載體處置差異表**：

| 載體 | 可見對象 | 歷史錨點型 ticket ID 處置 | 理由 |
|------|---------|------------------------|------|
| 程式碼 comment / docstring | 讀碼的框架開發者 | 允許保留（依移除測試判定） | 讀者理解 ticket ID 為時點標注，誤導面限於開發者 |
| 功能字串（hook 提示 / CLI 輸出 / UI 文案 / 錯誤回饋） | 所有運行時用戶 | 清理（即使屬歷史錨點型） | sync 後誤導其他專案所有用戶，誤導面廣 |

**正反範例**：

功能字串（應清理，即使屬歷史錨點型）：

| 引用（功能字串內） | 問題 | 修正 |
|------|------|------|
| hook 提示訊息 `參考案例：W-xxx` | runtime 顯示給用戶，sync 後該 ticket 在他專案不存在 | 移除 ticket ID，改抽象描述「參考類似歷史案例」 |
| CLI 輸出 `估算依 W-xxx` | 同上 | 移除 ticket ID，改「估算依歷史基線」 |

comment（對照，允許保留）：

| 引用（comment 內） | 移除測試 | 判定 |
|------|---------|------|
| `# 此防護源於某次 global 未定義崩潰事件（W-xxx）` | 移除後決策說明完整 | 歷史錨點型，保留（僅開發者可見） |

### 豁免機制

某些情境下，框架文件確實需要保留產品名稱或專案層級識別符作為情境舉例（例如測試任務的具體系統名稱、業務情境驅動的程式碼註解正例、5 Whys 真實事件分析）。完全禁止會破壞寫作教學的可讀性或事件記錄真實性。豁免機制提供合法的「具體舉例」保留路徑。

**Why**：規則 8 主目標是防止 sync 後死連結與誤導，但「具體舉例」的價值在於可讀性與場景感，與「框架描述」（如「本專案是 X」聲明）性質不同。一刀切禁止會傷及寫作教學的核心目的。

**Consequence**：缺豁免機制會出現兩種失敗模式：(1) 嚴格執行→教學範例失去場景感（如「系統 X」「平台 Y」），讀者無法建立心智模型；(2) 寬鬆執行→A 類框架描述漏網，sync 後跨專案誤導。

**Action**：依下方判別表將每處產品名稱出現分為「A 類框架描述（需泛化）」vs「B 類具體舉例（可豁免）」，B 類處加標準格式 HTML comment 豁免註解。

#### A/B 類判別表（角色二分）

| 類別 | 語意角色 | 處理 | 範例情境 |
|------|---------|------|---------|
| A 類 | 框架描述（「本專案是 X」聲明、跨專案通用 agent 的目標清單列舉） | 泛化為通用描述 | agent 定義中的「本專案」聲明 / data-miner agent 中的具體網站清單 |
| B 類 | 具體舉例（測試任務情境設定、業務情境驅動正例、業務意圖正例、過度驗證反例、5 Whys 真實事件記錄） | 加豁免註解保留 | 寫作 SKILL 的 dry-run 測試任務 / 程式碼註解範例 / 文件正例表格 / 反例 Widget Key 命名 / 事件分析鏈中的 storage key |

**判別準則**：問「若此處改為『系統 X』『平台 Y』後，讀者還能理解教學/事件意圖嗎？」

- 不能理解 → B 類（具體舉例，加豁免註解保留）
- 仍能理解（甚至更清晰）→ A 類（框架描述，泛化）

#### HTML comment 標準格式

```html
<!-- 規則 8 豁免（reference-stability-rules.md / DOC-010）：[此處 XXX] 作為 [情境類型]。[泛化會失去 YYY] 故保留。本豁免經 [評估方式] 後保留。 -->
```

**欄位填寫要求**：

| 欄位 | 內容 | 範例 |
|------|------|------|
| `[此處 XXX]` | 具體指出豁免對象（產品名稱 / 識別符） | 「以下任務描述中的某產品名稱」「`platform_icon_<product>` Widget Key」「`<product>_books` storage key」 |
| `[情境類型]` | 為何屬於 B 類（語意角色） | 「dry-run 測試的具體任務情境設定」「業務情境驅動正例 Dart 註解」「5 Whys 真實事件分析鏈中的 storage key」 |
| `[泛化會失去 YYY]` | 泛化會喪失的具體價值 | 「測試人員需具體系統名稱才能模擬撰寫情境，改為『系統 X』會失去場景感」「降低反例真實性」 |
| `[評估方式]` | 豁免決策來源（不引用專案 ticket ID） | 「跨檔評估」「規則 8 自律審視」 |

#### 撰寫慣例

**禁止**：

| 禁止 | 改為 |
|------|------|
| 在豁免註解中引用專案 ticket ID（如 `(W{N}-{seq} 評估)`） | 改為抽象描述（如「跨檔評估」） |
| 用「Why: 因為這樣比較好讀」這類無具體價值理由 | 必須說明「泛化會具體失去什麼」 |
| 一筆豁免覆蓋多處不同性質的內容 | 每個 B 類處獨立加註解，理由不可共用 |

**允許引用的權威**：

| 引用 | 屬性 |
|------|------|
| `reference-stability-rules.md` | 規則 8 本身路徑 |
| `DOC-010` | error-pattern 框架內部分類（規則 8 例外） |
| 其他 framework error-pattern ID（`PC-XXX` / `ARCH-XXX` / `IMP-XXX` / `TEST-XXX`） | 框架內部分類同上 |

#### 範例對照

合法 B 類豁免：

```html
<!-- 規則 8 豁免（reference-stability-rules.md / DOC-010）：以下測試反例中的 `platform_icon_<product>` Widget Key 命名是反例事件的真實 Key 名稱。事件分析記錄真實事件特徵；改為 `platform_icon_xxx` 會降低反例真實性。本豁免經跨檔評估後保留。 -->
```

不合法的「偽豁免」：

```html
<!-- 規則 8 豁免：此處保留產品名稱 -->                <!-- 缺欄位、無理由 -->
<!-- 規則 8 豁免：W{N}-{seq} 評估保留 -->             <!-- 引用專案 ticket ID -->
<!-- 規則 8 豁免：這樣比較好讀 -->                    <!-- 無具體價值說明 -->
```

#### 決策追溯慣例

- 豁免註解本身不含專案 ticket ID（保持規則 8 自律）
- 大規模豁免應用後，應在 `DOC-010` 觸發案例表新增一筆紀錄（採抽象模式描述）
- 後人查找豁免決策依據時，從 `DOC-010` 觸發案例表往回追溯到對應 ANA ticket（ANA ticket 位於 `docs/work-logs/`，規則 8 不適用於 `docs/`）

---

## CLAUDE.md 章節外移決策樹

**Why**：縮減 `CLAUDE.md` 體量時，章節外移目標必須依「內容是否含專案層級識別符」決定，誤將專案內容外移到 `.claude/references/`（跨專案 sync 範圍）會觸發規則 8 違反；誤將通用內容外移到 `docs/`（專案內部）則喪失跨專案知識複用。

**Consequence**：外移目標選錯會讓 `.claude/` sync 機制把專案專屬內容（如 `src/` 路徑、產品名稱）擴散到其他專案，造成跨專案誤導；或讓跨專案通用知識被困在單一專案 `docs/` 失去複用機會。

**Action**：執行 `CLAUDE.md` 章節外移前依下方決策樹判定目標，外移後執行檢查清單驗證合規。

### 觸發條件

| 訊號 | 處理 |
|------|------|
| `CLAUDE.md` 單檔行數 > 200（或某章節 > 50 行） | 評估外移 |
| 章節內容只在特定情境（如寫程式碼前）才需要 | 評估外移為 lazy-load reference |
| 章節含具體實作細節（命名清單、檔案位置表） | 評估外移以保持 `CLAUDE.md` 抽象層級 |

### 外移目標選擇決策樹

依序回答以下問題：

| 步驟 | 問題 | 是 → 目標 | 否 → 下一步 |
|------|------|----------|------------|
| 1 | 章節是否含**專案層級識別符**（`src/` 路徑、產品名稱、專案 ticket ID、專案 commit hash、專案 worklog 路徑）？ | `docs/<descriptive-name>.md` | 進入步驟 2 |
| 2 | 章節是否含**跨專案可複用的通用知識**（如 Chrome Extension 限制、Manifest V3 行為、Python 通用規範）？ | `.claude/references/<descriptive-name>.md` | 進入步驟 3 |
| 3 | 章節是否為**混合內容**（部分專案、部分通用）？ | 拆檔：專案部分放 `docs/`、通用部分泛化後放 `.claude/references/` | 留在 `CLAUDE.md`（無法外移） |

### 目錄性質對照表

| 目錄 | sync 範圍 | 可含專案識別符？ | 適用情境 |
|------|----------|---------------|---------|
| `docs/` | 專案內部，不 sync | 是 | 專案專屬規範、架構說明、需求/規格 |
| `.claude/references/` | 跨專案 sync | 否（規則 8） | 跨專案技術速查、通用 lazy-load 參考 |
| `CLAUDE.md` | 專案入口，不 sync | 是 | 高層概覽 + lazy-load 指引 |

### 外移後檢查清單

- [ ] 新檔目標目錄符合決策樹結論（`docs/` vs `.claude/references/`）
- [ ] `CLAUDE.md` 引用路徑已更新（`@docs/<檔名>.md` 或 `@.claude/references/<檔名>.md`）
- [ ] 原檔案已刪除（外移而非複製）
- [ ] 若放 `.claude/references/`，內容已通過規則 8 自檢（無 `src/` 路徑、無產品名稱、無專案 ticket ID）
- [ ] 若放 `docs/`，已在新檔頂部說明「存放位置原因」（避免後續誤搬回 `.claude/`）
- [ ] 執行 `grep -rn "<新檔關鍵字>" .claude/ docs/` 確認無殘留舊路徑引用

### 範例對照

| 章節性質 | 外移目標 | 範例 |
|---------|---------|------|
| 專案錯誤處理體系（含 `src/core/errors/` 路徑） | `docs/project-conventions.md` | 含 `src/` 路徑與專案 enum 清單，屬步驟 1 命中 |
| Chrome Extension Manifest V3 通用限制 | `.claude/references/chrome-extension-quickref.md` | 通用限制速查表（require/global/Storage API），泛化後保留 |
| Flutter 專案的命名規範 + 通用 Dart 風格 | 拆檔：專案命名放 `docs/flutter-naming-conventions.md`、通用 Dart 風格放 `.claude/references/dart-style-quickref.md` | 混合內容拆檔範例 |

---

## 補充檢查清單（搭配 document-format-rules.md 主檢查清單使用）

編輯規格文件或 `.claude/` 框架檔案時，額外確認：

- [ ] 規格文件未引用 worklog/ticket/plan 等臨時性文件（規則 7）
- [ ] 框架文件（`.claude/`）未引用專案 ticket ID / commit hash / worklog 路徑（規則 8）
- [ ] 引用的來源屬於穩定類別（規格/提案/CLAUDE.md/框架檔案路徑/error-pattern 分類）
- [ ] 若需記錄歷史來源（如變更由某 ticket 執行），採「來源標注」模式而非依賴引用

---

## 相關文件

- `.claude/rules/core/document-format-rules.md` — 文件格式規則主檔（規則 1-6 + YAML frontmatter + 檢查清單骨架）
- `.claude/rules/README.md` — 規則系統導引
- `.claude/references/framework-asset-separation.md` — 框架資產與專案產物職責分離原則
- `.claude/error-patterns/documentation/DOC-010-framework-references-project-tickets.md` — 框架誤引用專案 ticket 的錯誤模式
- `.claude/error-patterns/process-compliance/PC-098-pm-rule-content-contains-current-ticket-id.md` — 依賴型引用的執行面 error-pattern（PM 撰寫規則本能引用當下 ticket ID）
- `.claude/methodologies/comment-writing-methodology.md` — inline comment 記錄決策脈絡（引用性質判準的對齊對象）
- `.claude/rules/core/decision-trigger-binding.md` — PC-093 `history` 豁免類別定義（引用性質判準的對齊對象）

---

**Last Updated**: 2026-06-07
**Version**: 1.2.0 — 引用性質判準新增「功能字串（運行時輸出）子類」：功能字串內 ticket ID 即使屬歷史錨點型仍應清理（運行時誤導其他專案所有用戶，誤導面比 comment 廣）+ 載體處置差異表 + 正反範例。歷史 1.0–1.1 版見 git log。
**Version**: 1.1.0 — 規則 8 新增「引用性質判準」章節（依賴型禁止 vs 歷史錨點 / 設計脈絡型允許，操作判準＝移除 ticket ID 後可否理解），對齊 PC-093 `history` 豁免 + comment-writing 方法論 + 規則 7 來源標注例外，消除三方衝突。
