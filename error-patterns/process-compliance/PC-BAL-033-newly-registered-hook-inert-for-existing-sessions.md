---
id: PC-BAL-033
title: 新註冊的 hook 對既有 session 零效力，且從日誌缺席不可鑑別
category: process-compliance
severity: high
created: 2026-08-13
related:
  - PC-BAL-014
  - PC-145
  - ARCH-TUNL-001
  - PC-148
---

# PC-BAL-033: 新註冊的 hook 對既有 session 零效力，且從日誌缺席不可鑑別

## 基本資訊

- **分類**: 流程合規（process-compliance）
- **風險等級**: 高（防護類機制失效且無告警）
- **關聯**: [[PC-BAL-014]]（同機制，subject 為 skill 註冊表）、[[PC-145]]（同家族，執行載體持有源碼快照）、[[ARCH-TUNL-001]]（hook 註冊路徑失聯）、[[PC-148]]（hook 雙重註冊）

---

## 症狀

於 session 進行中新增一個 hook 並註冊到 `settings.json`，該 hook 對**所有當時已在執行的 session** 零效力。它要防的操作照常通過，沒有阻擋、沒有警告、沒有日誌。

檔案存在於磁碟、註冊存在於設定檔、單元測試全綠——但它從未被呼叫過一次。

最惡劣的一點：**這個失效的可鑑別性依 hook 是否覆蓋 `run_hook_safely` 共用執行框架而不同**（涵蓋率與例外路徑見根因 4）。日誌零筆不再永遠同時符合三種互斥情形，但覆蓋外的 hook 仍舊如此：

| 情形 | 覆蓋 `run_hook_safely` 的 hook | 覆蓋外的 hook（含根因 4 所述的降級 stub） |
|------|------|------|
| hook 未被呼叫（本模式） | 零筆——與「崩潰於 import 期」同形，兩者本身仍無法互相區分 | 零筆——與其餘兩種情形同形 |
| hook 被呼叫但未命中判準 | 至少一筆 DEBUG「Hook execution time」，可鑑別（非零筆） | 零筆（若僅在命中時記錄）——與其餘兩種情形同形 |
| hook 被呼叫但崩潰於寫日誌之前（import 期錯誤） | 零筆——與「未被呼叫」同形 | 零筆——與其餘兩種情形同形 |

換言之：在覆蓋 `run_hook_safely` 的 hook 上，缺席可鑑別為「未呼叫」或「import 期崩潰」兩者之一（僅這兩者本身仍同形，需步驟 2、3 佐證）；在覆蓋外的 hook 上，三種情形依舊完全同形、缺席不可鑑別。而防護類 hook 的正常狀態本來就是「什麼都沒發生」，於是在覆蓋外的路徑上，「零效力」與「一切正常」在可觀測面上依然完全同形。

## 四個假訊號

本模式之所以難以自我察覺，是因為部署者會連續拿到四個都指向「已受保護」的訊號：

| 假訊號 | 為何為假 |
|--------|---------|
| 單元測試全綠 | 測的是判準函式對命令字串的分類正確性，與「runtime 是否會呼叫它」正交 |
| `settings.json` 已註冊 | 註冊的是**磁碟狀態**；runtime 讀的是 session 啟動時的快照 |
| 手動 dogfooding 通過 | dogfooding 通常在**新開的**驗證 session 進行，該 session 啟動於註冊之後，故確實載入。既有 session 未受涵蓋 |
| 自動化完整性檢查（如 hook-completeness-check）於 SessionStart 回報「權限已確認可執行」全綠 | 回報全綠的原因是它自己在**同一次啟動**中才把該檔案 chmod 成可執行；「已修復」與「下次生效」之間仍有一個 session 的落差（見根因 5）。全綠訊息因此系統性地早於實際生效一個 session |

第三項最關鍵：驗證行為本身選在一個不會重現問題的環境進行，而且是**自然而然**地選在那裡。第四項最陰險：它是四者中唯一由自動化機制主動產出、而非人為選擇的訊號，且它回報的「已修復」與「已生效」共用同一份輸出，使自動化本身變成誤導來源。

## 觸發情境

| 條件 | 說明 |
|------|------|
| 於 session 進行中新增 hook 並註冊 | 主要觸發點 |
| 有其他 session／代理人正在並行執行 | 受害範圍；session 越長、暴露窗越大 |
| 該 hook 的職責是**防護**（阻擋破壞性操作） | 失效方向為 fail-silent，無人察覺 |
| 以「新開 session 手測」作為部署驗收 | 驗收環境系統性地排除了問題情境 |

並行派發情境下風險加乘：新增防護的動機通常正是「剛發生過一次事故」，而此時並行代理人都還在跑——**最需要防護的那一刻，正是防護必然無效的那一刻**。

## 根因

### 根因 1：註冊是 session 啟動時的快照，無 session 內失效手段（機制層，必要非充分）

hook 註冊於 session 啟動時載入為快照。磁碟上的 `settings.json` 是世界平面，runtime 持有的註冊表是啟動瞬間的記錄平面，兩者在新增後必然分歧，直到下個 session 才收斂。

與 [[PC-145]]（`uv tool install` 快照，可用 reinstall 使其失效）的差別在於：**本機制沒有任何 session 內的失效手段**，這點與 [[PC-BAL-014]] 相同。

> 本條依證據形態與 [[PC-BAL-014]] 對同一 runtime 的 skill 註冊表所獨立確立的同機制推得，非直接讀官方文件實測。

**必要非充分（2026-08-13 差分實測）**：本模式的示例 hook 於當日 09:38 隨 `settings.json` 一併註冊。本根因的推論意味著「session 於註冊之後啟動即可正確載入」，但同日 12:52 啟動、晚於註冊 3 小時 20 分的新 session，對該 hook 依然是零效力——同一個 PreToolUse block 內其餘 18 個 hook 全程持續被呼叫，唯獨這一個全程零筆（全 block 掃描 + 即時探針差分實測，見鑑別方法步驟 2、3）。單靠本根因無法解釋此觀測；操作性成因見根因 5。

### 根因 2：部署延遲等於最長 session 壽命，但無人把它當延遲

一般會預期「改了設定檔就生效」。實際的生效延遲是**所有既有 session 結束為止**，可能是數小時。這段延遲沒有任何介面呈現，也沒有任何倒數或提示。

### 根因 3：防護類機制缺 liveness 訊號

防護 hook 的正常輸出是「無輸出」，因此它與「不存在」在可觀測面同形。系統沒有提供「這個 hook 剛才確實被呼叫了」的正向訊號，使得部署者只能用「沒出事」推論「有在保護」——而這正是 [[PC-BAL-014]] 家族的共同陷阱。

### 根因 4：`run_hook_safely` 涵蓋率非 100%，降級路徑完全不寫日誌（獨立成因）

「症狀」節描述的部分鑑別力，來自 `.claude/lib/hook_logging.py` 的共用執行框架 `run_hook_safely`：main_func 返回後無條件寫入一筆 DEBUG「Hook execution time」，`FILE_HANDLER_LEVEL = logging.DEBUG` 使其落檔，`FileHandler(delay=True)` 使「日誌檔存在」等價於「確有寫入」。但此框架的涵蓋率僅 88/103（`rg -l run_hook_safely .claude/hooks/ -g '*.py'` 實測），其中 4 個 hook 在 `from lib import` 失敗時降級為自訂 no-op stub——該路徑完全繞過 `run_hook_safely`，不寫任何日誌。

**Why 這是與根因 1 獨立的成因**：根因 1 的病灶是「registry 未收到新註冊」；本根因的病灶是「即使 hook 已被此 session 載入且確實被呼叫，只要落入這 4 個 hook 的降級路徑，寫日誌的能力本身就被繞過」。兩者觸發條件互不相依——根因 1 只需新註冊發生在 session 中途，本根因需 `lib` import 於該 hook 執行環境中失敗——但終端症狀相同：日誌零筆。

**Consequence**：鑑別方法步驟 1（日誌零筆檢查）若未先排除降級路徑，會把「hook 正常運作但走了 no-op stub」誤判為「未被此 session 載入」，使原本可鑑別的一類 hook 也被誤歸為不可鑑別。

**Action**：鑑別前先確認待驗 hook 是否覆蓋 `run_hook_safely`（`grep -n run_hook_safely .claude/hooks/<hook-name>.py`）；覆蓋但仍零筆時，再確認是否落入 `from lib import` 失敗的降級 stub 路徑（`grep -n "except ImportError\|from lib import" .claude/hooks/<hook-name>.py`）。兩者皆非，零筆才等於「未呼叫或 import 期崩潰」。

### 根因 5：以 shebang 直接執行的 hook 缺可執行位，狀態與 session 生命週期無關（獨立成因，2026-08-13 實測）

`settings.json` 對本類 hook 的呼叫方式是直接執行檔案路徑（例：`$CLAUDE_PROJECT_DIR/.claude/hooks/<hook-name>.py`），依賴檔案自身的 shebang（如 `#!/usr/bin/env -S uv run --quiet --script`）啟動，而非透過 `python3 <path>` 間接呼叫。作業系統以此方式啟動程式時要求檔案具備可執行位（`+x`）；不具備時程序從未起跑，連 import 都不會發生。

`git ls-tree` 逐 commit 查證（見鑑別方法步驟 5）顯示：本模式的示例 hook 於建立並註冊當下即以模式 `100644` 提交，同日稍後的一次補強提交仍維持 `100644`；直到一次獨立的自動權限修復提交才轉為 `100755`。事故發生時段全程處於不具可執行位的狀態。

**Why 這是與根因 1 獨立的成因**：根因 1 的病灶是「該 session 的 registry 快照未收到新註冊」，其修復只需換一個在註冊之後啟動的 session；本根因的病灶是「即使 session 於註冊之後啟動、registry 快照確實含有此 hook，只要磁碟上的檔案模式仍是 `100644`，該 session 依然無法啟動它」。兩者可獨立成立、獨立失效——見根因 1「必要非充分」段落的差分實測：session 於註冊後 3 小時 20 分才啟動（滿足根因 1 的前提），該守衛仍全程零效力，證明單靠根因 1 不足以解釋此次失效，操作性成因是本根因。

**Consequence**：若復盤只查根因 1（結論為「等重啟即可」）而未查檔案模式，會誤判「已經過了一個 session 邊界，下次應該就會生效」，但只要磁碟模式仍是 `100644`，重啟幾次都不會生效。本模式的示例 hook 就出現過這種誤判：補強提交發生於原始註冊之後，但當時模式仍未修正。

**Action**：新增或修改以 shebang 直接執行的 hook 時，在寫入 `settings.json` 的當下（而非事後排查時）驗證檔案可執行位，將此檢查點前移，不依賴「下次事故再回頭查」。

**跨 session 持續、重啟不修復**：檔案模式是 git 追蹤且由磁碟持久化的狀態，不隨 session 的開始或結束而改變；重啟只是重新讀取一次 `settings.json` 快照，能解決根因 1 描述的落差，但不會讓一份已提交為 `100644` 的檔案自動變成可執行，需要一次獨立的 `chmod` + commit（人工或自動化）才會改變。進一步的觀察：**若這次修復動作本身發生在某 session 自身的 SessionStart 階段內，該次 session 仍不受益**——本模式的示例事故中，權限修復提交正是由當次 session 自身的 SessionStart 自動修復所產生，但該 session 於修復之後持續執行差分鑑別，該守衛依然全程零筆。可能的解釋（推論強度：中，未經官方文件或原始程式碼直接證實）：runtime 於啟動流程中解析並驗證 hook 可執行性的時間點，早於 SessionStart hook 實際執行的時間點，故當次修復對本次 session 而言為時已晚，須等到**下一次**重啟、開一個新 session，才會載入已修復的檔案。

## 鑑別方法（五步）

缺席的鑑別力依覆蓋範圍而異（見步驟 1）：覆蓋外的 hook 上仍完全不可鑑別，**必須用差分而非單點觀察**；覆蓋 `run_hook_safely` 的 hook 上零檔案本身可初步鑑別，但仍分不清「未呼叫」與「import 期崩潰」兩者，故亦建議續行差分佐證。前三步依成本遞增，用於確認「是否被呼叫」，任一步命中即可停；步驟 4、5 用於在確認「未被呼叫」後，進一步鑑別根因是缺可執行位（根因 5）、`run_hook_safely` 覆蓋缺口（根因 4），還是其他載入問題（根因 1）：

### 步驟 1：日誌零筆檢查（成本最低，鑑別力依 hook 是否覆蓋 `run_hook_safely` 而定）

```bash
ls -la .claude/hook-logs/<hook-name>/
```

先確認待驗 hook 是否覆蓋 `run_hook_safely`（見根因 4）：

```bash
grep -n run_hook_safely .claude/hooks/<hook-name>.py
```

**覆蓋 `run_hook_safely` 的 hook**：main_func 返回後無條件寫入 DEBUG「Hook execution time」，故「零檔案」（目錄下無任何日誌檔）與「檔案存在但零筆」是兩種不同結論，不可混為一談——後者不會發生（只要被呼叫過就至少留下一行）；一旦觀察到「有檔案但零筆」，代表覆蓋判斷有誤，或該 hook 落入根因 4 的降級 stub 路徑，須回頭核對。因此對這類 hook，**零檔案本身即是結論**：等同「未呼叫」或「import 期崩潰」兩者之一（仍無法再細分，需步驟 2、3 佐證）；目錄下若有檔案，即代表已被呼叫，不需再往下鑑別。

**覆蓋外的 hook（含根因 4 所述的降級 stub 路徑）**：零檔案仍是**嫌疑訊號**而非結論，維持原本三種情形同形的判斷——仍可能是「有跑但都沒命中且不寫 DEBUG」。先確認該 hook 是否在**未命中**時也記錄：

```bash
grep -n "logger.debug\|logger.info" .claude/hooks/<hook-name>.py
```

若存在「未命中也寫一行」的路徑，且該路徑的日誌等級確實會落檔（檢查既有日誌檔內是否含 DEBUG 行），可縮小嫌疑範圍，但仍不足以單獨定論，須續行步驟 2 或 3。

### 步驟 2：同 matcher 對照組（決定性）

找一個**註冊時間更早**、matcher 相同的 hook 當對照：

```bash
ls -la .claude/hook-logs/<peer-hook-with-same-matcher>/ | tail
```

對照組持續產出、待驗 hook 零筆 → runtime 有在跑該 matcher 的 hook，但沒跑這一個。這一步把「runtime 沒觸發任何 hook」的可能性排除掉。

### 步驟 3：即時探針（可重現、可寫進 ticket 當證據）

發一個無害的、必然觸發該 matcher 的命令，然後立刻對照兩邊日誌：

```bash
echo "liveness probe $(date '+%H:%M:%S')"
# 隨即：
ls -la .claude/hook-logs/<hook-name>/ | tail -2
ls -la .claude/hook-logs/<peer-hook>/ | tail -2
```

對照組有新檔、待驗 hook 沒有 → **同一 session、同一 matcher、同一刻的差分**，證實該 hook 未被此 session 載入。這是可重現的實證，不是推論。

> 步驟 1-3 的共同設計原則：**不要問「它有沒有擋住」（無輸出無法回答），要問「它有沒有被呼叫」（可用差分回答）。** 步驟 4、5 接續回答「若未被呼叫，是哪一層原因」。

### 步驟 4：隔離執行（排除「判準錯誤」，把嫌疑收斂到載入層）

以 stdin 直接餵 hook 協定 JSON，繞過 runtime 的載入機制、直接執行 hook 本體：

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git stash"}}' | .claude/hooks/<hook-name>.py
```

若印出預期訊息、exit code 正確、且日誌新增一筆 → hook 本體（判準、import、日誌管線）皆正常運作，問題必然在「runtime 是否呼叫了它」，而非「它自己的邏輯是否正確」。此步驟排除「崩潰於寫日誌前」與「判準未涵蓋」兩種假設，把嫌疑範圍收斂到載入層（根因 1 或根因 5）。

### 步驟 5：檔案模式溯源（鑑別根因 5：缺可執行位）

```bash
git ls-tree <commit-hash> -- .claude/hooks/<hook-name>.py
```

對建立、修改、修復等相關 commit 逐一查詢，比對是否曾以 `100644`（無 `+x`）完成提交。

**Why `git ls-tree` 是這一步的必要工具**：`git log` 與 `git show --stat` 等預設精簡輸出（僅顯示 commit 訊息或增刪行數）不會顯示模式變化——對一次純權限修復的 commit 執行 `git show --stat` 會顯示 `0 insertions(+), 0 deletions(-)`，看起來像空提交。`git show`／`git diff`（不帶 `--stat` 的完整 diff）會顯示 `old mode`/`new mode` 行，但前提是已經知道要比較哪兩個版本；`git ls-tree <commit>` 可直接查詢任一 commit 當下的磁碟模式，不需要先鎖定「是哪次提交改的」——因此是回答「事故當下磁碟狀態為何」時，唯一不依賴預先知道異動 commit 的管道。

### 輔助：時間軸交叉比對

```bash
git log --format="%h %ad %s" --date=iso -- .claude/settings.json .claude/hooks/<hook>.py
git reflog --date=iso | head -20
```

若「hook 註冊 commit 時間」早於「事發時間」，則「涵蓋不足」的假設可被排除，指向載入而非判準問題。反之若晚於事發，才是涵蓋問題。

## 解決方案

### 立即處置

1. 以上述鑑別方法確認是載入問題而非判準問題（**先做這件事**，否則會誤修判準），必要時以步驟 4、5 進一步定位是根因 1（registry 快照）還是根因 5（缺可執行位）。
2. 通知所有並行 session 重啟，或明確接受「本 wave 該防護不生效」並改用人工紀律替代。
3. 若該 hook 防的是不可逆操作，在重啟完成前不得依賴它作為 gate。

### 結構修正方向

| 方向 | 說明 |
|------|------|
| 部署即宣告 | 新增防護類 hook 的 ticket，acceptance 必含「已通知既有 session 重啟」或「已標註本 wave 不生效」，不得只驗單元測試 |
| liveness 訊號 | 防護 hook 提供可查詢的「最後一次被呼叫時間」，讓「沒出事」與「沒在跑」可分辨 |
| 缺席可鑑別 | 未命中路徑一律寫一筆可落檔的日誌，使「零筆」成為明確結論而非嫌疑 |
| 驗收環境對齊 | dogfooding 不得只在新開 session 進行；驗收須顯性涵蓋「既有 session」情境 |
| 可執行位前移檢查 | 新增或修改以 shebang 執行的 hook 時，在寫入 `settings.json` 的當下即驗證檔案可執行位，不留待下次事故才發現（見根因 5） |

### 與 fail-open 的疊加（獨立但同向）

若該 hook 的錯誤處理是 fail-open（例外時放行、僅 PreToolUse 的 exit 2 才阻擋），則本模式與 fail-open 疊加後，防護在兩個獨立維度上都靜默失效。部署防護類 hook 時應同時檢查失敗語意，兩者是不同缺口。

## 預防措施

- 新增防護類 hook 的 ticket，acceptance 增列：既有 session 生效策略、liveness 驗證方式、失敗語意（fail-open / fail-closed）三項。
- 任何「hook 應該擋卻沒擋」的事故，**第一步查載入而非查判準**——判準問題會留日誌，載入問題不會。
- 事故復盤時，「日誌無記錄」不得作為「該操作未發生」或「該操作繞過了防護」的證據；缺席不可鑑別，必須補差分觀察。

## 通用化檢驗

將專案細節（`workspace-wipe-guard-hook` / `git stash` / `settings.json`）替換為通用描述後仍成立：

> 「於系統執行中新增一個以啟動時快照載入的防護機制，該機制對所有既有執行體零效力；因防護機制的正常狀態即為無輸出，其失效與正常在可觀測面同形，無法從日誌缺席判讀；且部署者會連續取得（單元測試綠 / 註冊已寫入 / 新環境手測通過 / 自動化完整性檢查全綠回報）四個都指向已受保護的假訊號。」

→ 屬跨專案可重現的結構性缺陷。任何以「啟動時載入設定」為模型的系統（hook / plugin / middleware / sidecar 註冊）在執行中新增防護時都會踩到。
