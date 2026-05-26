# PC-161: ANA grep 範圍誤判導致「前車之鑑」強論證崩塌

> **錯誤類別**：流程合規（ANA 用 grep 結果支撐強論證但 grep 範圍 / 方法有誤）
> **嚴重度**：高（ANA 結論被 PM 採信後若無 PC-007 獨立驗證，會直接導致錯誤決策落地；本案靠 PM 驗收抓到，但若 saffron ANA 直接 spawn IMP 走豁免，後續若真有需求才會曝光）
> **發現案例**：0.19.0-W3-063（saffron ANA 聲稱 `emit_hook_output / generate_hook_output` 0 個呼叫者作為「前車之鑑」核心論證，PM 驗收 `rg -n` 發現 8+ hook 直接呼叫，論證崩塌）

---

## 症狀

ANA 代理人提交分析結論時，使用 grep / rg 結果作為強論證（特別是「0 個」「無使用」「未採用」這類絕對量詞），但 grep 範圍 / 方法有誤，導致：

| 訊號類型 | 典型表現 |
|---------|---------|
| 絕對量詞 + 單一 grep | 「grep 結果為 0」「無任何 hook 使用」「100% 未採用」僅一次 grep 支撐 |
| 結論強度遠超證據 | 「前車之鑑：預建 helper 不被採用」用單一 grep 結果反推整個設計模式失效 |
| 缺次級驗證 | 「0 採用率」結論未交叉驗證（如：若真 0 採用，為何 helper 還在維護？） |
| 含「結論-證據反向推理」嫌疑 | 先有「應該豁免」傾向，再找支持的 grep 結果 |

## 根因

ANA 用 grep 結果支撐強論證時，至少四道落差會放大誤判：

1. **glob 範圍隱性限制**：`rg -l 'pattern' .claude/hooks/*.py` 的 `*.py` glob 不含巢狀子目錄。但 hook 體系可能有 helper 在 `hook_utils/` 子目錄、tests 在 `tests/` 子目錄。若 ANA 想證明「整個 hook 體系 0 採用」，glob 必須 `--type py` 或顯式遞迴，否則 *.py 只覆蓋頂層。

2. **`rg -l` 只列檔案不列行**：`-l` 模式列出含 pattern 的檔案，無法區分「該檔案有 1 處 call」vs「該檔案有 N 處 call vs def vs import」。ANA 若以 `rg -l` 結果為 0 判定，可能是 grep 範圍錯誤（檔案有但 `-l` 沒列），不是真 0。

3. **def / call / import 混淆**：grep `'emit_hook_output'` 同時抓到函式定義、import 語句、實際呼叫。若 ANA 直接以「grep 命中數」推「呼叫者數」，會把 def 自身計入或反向把 import 視為非 call。

4. **未做次級驗證**：「0 採用率」這類絕對結論若為真，邏輯上會有附隨現象（helper 應被建議刪除、historical commits 應有 deprecation 訊號、相關 ticket 應有討論記錄）。ANA 未交叉檢驗附隨現象就直接結論，是強論證的脆弱點。

## 案例：W3-063 saffron ANA 0 採用率論證崩塌

| 階段 | 觀察 |
|------|------|
| saffron ANA 執行 | 用 `rg -l 'emit_hook_output\|generate_hook_output' .claude/hooks/*.py` 得 0 結果（推測 glob 範圍或 `-l` 模式有誤） |
| ANA 結論 | 「同層級 helper 已證明 0 採用率 → 預建 terminalSequence helper 必步同樣後塵 → 豁免實作」 |
| PM 驗收（PC-007） | 執行 `rg -n 'emit_hook_output\(\|generate_hook_output\(' .claude/hooks/ --type py` 過濾掉 `hook_utils/` 與 `tests/`，得 30+ 行 call 分布於 8+ hook |
| 事實 | emit_hook_output 廣泛採用（bash-edit / main-thread / mcp-write / askuserquestion / phase4 / utf8-integrity 等），是穩定基礎設施 |
| 論證影響 | 「前車之鑑」論點崩塌；「terminalSequence 語意不匹配 AI 通訊」論點仍成立 |
| 結論調整 | W3-031.1 仍走豁免，但主因從「前車之鑑」改為「YAGNI 主因 + 語意層差異次因」 |

> 完整 grep 對照與重評見 W3-063 Solution 章節「PM 驗收修正（2026-05-26）」區塊。

## 防護要點

### ANA 規劃層（saffron / 任何 ANA 代理人自律）

ANA 結論含「0 個」「無任何」「未採用」這類絕對量詞時，**強制執行三項次級驗證**：

| 驗證項 | 具體動作 |
|-------|---------|
| (a) grep 工具切換 | `rg -l` 結果為 0 時，必須改 `rg -n` + 顯式 `--type` 重跑，比對結果是否一致 |
| (b) def / call / import 分離 | 用 `\(` 後綴或 `^def ` / `^import` / `^from ` 分流，避免三者混淆 |
| (c) 附隨現象交叉檢驗 | 若 helper 真 0 採用，搜尋 git log / commit messages 找 deprecation 訊號；若無，則「0 採用」結論可疑 |

### Acceptance 層（ANA ticket schema）

ANA 含「絕對量詞論證」（前車之鑑 / 100% / 0 採用率 / 從未使用）時，acceptance 必須包含：

| 驗收條件 | 範本 |
|---------|------|
| grep 工具與範圍明示 | acceptance 含「列出 grep / rg 完整指令含 --type 與排除 glob，可由 PM 重跑」 |
| 次級驗證證據 | acceptance 含「絕對量詞論證附 2+ 種驗證方法交叉確認」 |
| 反向假設測試 | acceptance 含「若論點為假會看到什麼附隨現象？已搜尋且無發現」 |

### PM 驗收層

PM 收到 ANA 結論時，若見絕對量詞論證，**強制獨立驗證**（quality-baseline 規則 1 / PC-007）：

| 驗證指令範本 | 用途 |
|------------|------|
| `rg -n '<pattern>\(' <scope> --type <lang>` | 行級別檢視，區分 def vs call |
| `rg -n '<pattern>\(' <scope> --type <lang> \| grep -v "^<def_path>" \| grep -v "<test_path>"` | 排除定義檔與測試檔，只看真實 call |
| `git log --all -S '<pattern>' --oneline \| head` | 歷史 commit 是否有 deprecation / usage 訊號 |
| 反問：「若 0 採用，為何此 helper 還在維護？是否有 grep 漏網？」 | 認知層次的次級驗證 |

### Hook 層（建議實作）

PostToolUse:Agent 或 ANA ticket complete 時，掃描 ticket body / Solution 章節是否含「0 個」「無任何」「未採用」「從未」「100% 未」等絕對量詞 + 鄰近段落含 grep / rg 指令，若是則輸出 reminder：「ANA 含絕對量詞 grep 論證，PM 驗收前建議獨立重跑（PC-161 防護）」。Hook 不阻擋，僅提示。

## 與其他 PC 的邊界

| PC | 聚焦 | 與本 PC 差異 |
|----|------|------------|
| PC-007 | ANA 描述需獨立驗證 | 本 PC 為 PC-007 子家族：聚焦 grep 範圍誤判導致絕對量詞論證崩塌 |
| PC-068 | ANA 規劃新建資產前必須 grep 既有同職責 | 互補：PC-068 要求做 grep；本 PC 要求 grep 結果為「無」時必須次級驗證 |
| PC-113 / PC-138 / PC-144 | validator regex 短英文標記 / 表格 N/A / TODO 字面誤判 | 同家族：grep / regex 工具本身的精度問題；本 PC 強調 ANA 用 grep 結果做決策時的二次驗證義務 |

## 相關 Ticket

| Ticket | 關係 |
|--------|------|
| 0.19.0-W3-063 | 觸發案例：saffron ANA 0 採用率論證 + PM 驗收修正 |
| 0.19.0-W3-064 | 本 PC 撰寫 ticket（DOC） |
| 0.19.0-W3-031.1 | 受影響子 ticket：依 W3-063 修正後結論 closed（not_executable_knowledge_captured） |
| 0.19.0-W3-031 | source ANA：spawn W3-031.1 規劃 helper 實作 |

## 相關規則 / Memory

- `.claude/rules/core/quality-baseline.md` 規則 1（測試通過率 = ANA 結論正確率）+ 規則 5（所有發現必須追蹤）+ 規則 6（失敗案例學習原則）
- `.claude/error-patterns/process-compliance/PC-007-*.md` 父家族：ANA 描述需獨立驗證
- `.claude/error-patterns/process-compliance/PC-068-*.md` 互補：ANA Spawn IMP Pre-scan
- memory `feedback_failure_learning_principle`：流程瑕疵不回退、提煉教訓固化為規則
- memory `feedback_pm_narrative_fabrication_and_shallow_attribution`：PM 論述編造防護（與本 PC 互補，本 PC 聚焦 ANA 代理人，前者聚焦 PM）

---

**Last Updated**: 2026-05-26
**Source**: 0.19.0-W3-063 saffron ANA 0 採用率論證崩塌案例
