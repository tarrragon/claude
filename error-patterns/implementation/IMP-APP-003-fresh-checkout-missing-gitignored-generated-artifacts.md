# IMP-APP-003: fresh checkout 缺 gitignored 生成產物導致連鎖編譯失敗（並被誤歸因為資源耗盡）

## 基本資訊

- **Pattern ID**: IMP-APP-003
- **分類**: 實作（implementation）
- **風險等級**: 高（每次 worktree / CI fresh checkout 跑全套件都會踩，且症狀誤導）
- **相關 Pattern**: PC-166（confabulation：把預期當觀測）、PC-168（flaky baseline 幸運連勝）

---

## 問題描述

### 症狀

在 fresh checkout（git worktree、CI runner、新 clone）執行全套件測試，出現**大量**編譯失敗：

```
Error: Error when reading '<path>/generated/<file>.dart': No such file or directory
```

以及隨之而來的大批 `undefined` 連鎖錯誤，偶爾夾雜一兩個 `The Dart compiler exited unexpectedly.`

### 歸因陷阱

失敗數量龐大（數十至上百）且夾帶編譯器崩潰訊息，極易被歸因為**高並行下編譯器資源耗盡**——這個解釋聽起來合理、符合直覺（測試並行跑、機器負載高），且無需進一步調查即可「解釋」現象。

真正的原因是：該生成產物（code generation 輸出，如 i18n 的 `AppLocalizations`、序列化、DI 註冊）被列入 `.gitignore`，fresh checkout 自然沒有它。缺少單一入口檔會讓所有 import 它的檔案編譯失敗，形成連鎖。

兩種歸因的後果完全相反：

| 歸因 | 若採信 | 實際代價 |
|------|--------|---------|
| 資源耗盡 | 視為環境噪音，降低並行度或忽略 | 全套件結果永遠不可信，真實紅燈被淹沒 |
| 缺生成產物 | 執行 code generation 即修復 | 需納入派發／CI SOP，或將產物納入版控 |

### 為何難以自我察覺

執行者在該環境內看到的每一個編譯失敗都是真的，沒有任何跡象顯示「另一個環境不會這樣」。**單環境觀察無法區分這兩個假說**，必須做對照實驗。

---

## 偵測方式

### 對照實驗（唯一可靠方法）

固定所有其他變因，只切換生成產物是否存在：

```bash
# 環境 A：已執行 code generation 的工作區
ls <generated_dir>/ | head          # 確認產物存在
<test_command> --file-reporter json:/tmp/env_a.json

# 環境 B：fresh checkout，刻意不執行 code generation
git worktree add /tmp/clean HEAD
ls /tmp/clean/<generated_dir>/       # 確認產物不存在
<test_command> --file-reporter json:/tmp/env_b.json
```

比較兩者的**編譯失敗數**。若 A 為 0 而 B 為大量，假說成立。

### 量測工具要求

大型套件在高並行下，**純文字 reporter 會行覆寫交錯**，用字串搜尋判斷「某測試是否執行」會產生假陰性。判定必須以結構化事件輸出（JSON reporter）逐筆解析：

```python
import json, collections
errs = collections.Counter()
for line in open(path):
    try: e = json.loads(line)
    except: continue
    if e.get('type') == 'error':
        errs[(e.get('error') or '').split('\n')[0][:80]] += 1
print(errs.most_common(5))
```

錯誤訊息分類後，看有多少直接指向缺失的生成檔——這是決定性證據，不是推論。

---

## 防護措施

### 立即層

fresh checkout 執行全套件前，先跑 code generation（`flutter gen-l10n`、`build_runner`、`protoc` 等，視專案而定）。納入派發 SOP 與 CI 腳本。

### 根治層

評估將生成產物**納入版控**。取捨：

| | 納入版控 | 維持 gitignore |
|---|---|---|
| fresh checkout | 直接可用 | 須先跑 generation |
| merge 衝突 | 產物衝突需處理 | 無 |
| diff 雜訊 | 每次 regenerate 都有 diff | 無 |

無普遍正確答案，但**必須顯性決策並記錄理由**，不能因為「預設就 gitignore」而不評估。

### 診斷層

當看到大量編譯失敗夾雜編譯器崩潰時，在歸因為資源耗盡之前，先問：

1. 這個環境是 fresh checkout 嗎？
2. 專案有 code generation 步驟嗎？
3. 生成產物在 `.gitignore` 裡嗎？

三問皆是，先做對照實驗再下結論。

---

## 案例背景

某 Flutter 專案的 agent 在 git worktree（fresh checkout）執行全套件，得到 88 項失敗，其中 87 項為編譯錯誤。agent 歸因為「疑似高並行編譯器資源耗盡」——措辭誠實（用了「疑似」），但未排除競爭假說。

對照實驗結果：有生成產物的工作區編譯失敗 **0** 項，無生成產物的 fresh checkout 編譯失敗 **86** 項，其中 85 項的錯誤訊息直接指向缺失的 i18n 生成檔。「編譯器意外退出」在整個實驗中僅出現 **1** 次（單一檔案），不足以支撐「資源耗盡導致 87 項失敗」。

值得注意的是，同一專案更早的 ticket 已記錄過「worktree 內生成產物缺失導致連鎖編譯失敗，已手動補跑 generation」，但該觀察停留在單張 ticket 的執行紀錄，未升格為 SOP 或 error-pattern，因此後續 agent 重蹈覆轍並給出錯誤歸因。

**教訓**：單張 ticket 裡的環境觀察若未升格，下一個執行者不會讀到它。

---

## 附帶發現：計時斷言污染紅燈判讀

同一對照實驗中，兩個絕對計時門檻斷言在兩環境間 GREEN/RED 擺盪（同一斷言 main FAIL、worktree PASS）。此類斷言量測的是機器負載而非程式正確性，會與真實紅燈混雜，使全套件失敗數無法作為品質指標。詳見 `.claude/rules/core/test-assertion-design-rules.md`。

---

## 相關規則

- `.claude/rules/core/test-assertion-design-rules.md`（絕對計時門檻禁令）
- `.claude/rules/core/quality-baseline.md` 規則 1 邊界（測試綠燈不等於 runtime 正確；flaky baseline 取樣門檻）
- `.claude/rules/core/tool-output-trust-rules.md` 規則 3（用無法腦補的固定值交叉驗證）

---

**建立日期**: 2026-07-10
**Version**: 1.0.0
