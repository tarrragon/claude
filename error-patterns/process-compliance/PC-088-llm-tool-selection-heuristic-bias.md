---
id: PC-088
title: LLM 對 tool call 路徑的步驟數估算偏誤（單步敏感、總步驟盲）
category: process-compliance
severity: high
created: 2026-04-18
updated: 2026-04-18
---

# PC-088: LLM 對 tool call 路徑的步驟數估算偏誤

> **框架重大修訂（2026-04-18）**：原 v1 框架為「LLM 偏好低摩擦路徑是架構層 bias 需對抗」。用戶指出此框架與 `.claude/methodologies/friction-management-methodology.md` 衝突——**摩擦力是中性工具，短路徑偏好本身是正確預設**。真實問題不在「偏好」，而是**路徑步驟數的估算偏誤**：LLM 對單步複雜度敏感但對總步驟數盲。本 v2 版依此重構。

> **E3 實驗更新（2026-04-18）**：E3 retrospective audit（n=1157 observations, 50 sessions）顯示各 task 類別的 long_path_rate 存在顯著異質性（0.000–0.412）。PC-088 v2 主張限縮為「**在特定 task 類別有實證支持**」，不作全稱 causal claim。詳見下方「分類證據」章節。

## 症狀

LLM 面對多步驟任務時，會把**實際步驟多但每步簡單**的路徑**誤估為短路徑**，選擇後才發現總成本高於替代方案。

### 實證案例對照

| 情境 | LLM 誤選路徑 | 實際總步驟 | 真正短路徑 | 真正總步驟 |
|------|-----------|-----------|-----------|-----------|
| 傳遞長文字到 CLI | Write /tmp → cat → pipe | **3 步** | heredoc 內嵌 | **1 步** |
| 改大檔案 | Read → Write 整檔 | 2 步但每步重 | Edit 精確替換 | 1 步 |
| 查詢程式碼 | 逐檔 Read → 人工比對 | N 步 | Grep pattern | 1 步 |
| 多檔案搜尋 | Bash find + grep 組合 | 2 步 | Grep 或 Glob | 1 步 |
| 執行分析 | 自己逐步推理 | 10+ 步 | 派發 Agent | 1 步 |

**關鍵觀察**：在每個誤選案例中，LLM 以為自己選的是「輕路徑」，但計算下來反而是「長路徑」。問題不在偏好，在**無法準確估算路徑總長度**。

## 真實根因（架構層，三點）

### 1. 單步敏感、總步驟盲

LLM 是 autoregressive，**每個 next-token 的 perplexity 是直接感受**，但「10 個 next-token 組成的序列」只能靠推理總計：

- 生成 `Write("/tmp/x.md", content)` 的每個 token 都低 perplexity → **感覺簡單**
- 需要「預想」後續還要 `cat` + `append-log` → **不會被直覺感受**
- 真正簡單的 heredoc 每個 token perplexity 較高 → **感覺複雜**

結果：LLM 對「每步感覺」敏感，對「路徑總長度」盲。

### 2. Tool result 回饋的進度錯覺

每步 tool call 都有 tool_result 回饋。多步驟路徑每步都「有回饋 = 進度」，給 LLM **虛假的推進感**。單步 heredoc 沒有中途回饋，感覺「風險更高」。

但實際上：有回饋不等於進度，多步驟反而增加失敗風險面。

### 3. 訓練資料頻率 ≠ 最佳實踐

訓練資料含大量「Write file → process」sysadmin tutorials，這是歷史 shell 限制的產物，不是現代最佳實踐。LLM 把**訓練頻率誤讀為權威性**。

## 框架：與 friction-management 的正確關係

### 短路徑偏好 = 正確預設（象限 A / 執行點）

摩擦力方法論明確指出：
- 高頻 + 可逆 + 只影響當前任務 → **降低摩擦，直接執行**
- Phase 3b 實作執行 → 低摩擦
- LLM 選短路徑本身符合此預設，不該被「對抗」

### 真正的問題在估算偏誤

當 LLM **誤認為**自己選的是短路徑（實際是長路徑），低摩擦預設就失效——此時 PM 在 Phase 3b 類場景選了 3 步路徑做 1 步能完成的事。

**這不是偏好問題，是事實判斷錯誤**。

### 決策點加摩擦仍屬必要（象限 C / 前期階段）

摩擦力方法論也指出：低頻 + 不可逆 + 跨版本影響 → 加摩擦。這與短路徑偏好並不衝突：
- 執行點保留短路徑預設
- 決策點強制 WRAP / 多視角 / two-phase reflection
- 兩者並存，不互斥

## 分類證據（E3 實驗，2026-04-18）

**來源**：`docs/experiments/PC-088-v2-validation.md`（W15-014 執行）
**方法**：掃描 50 個 session transcript，n=1157 tool_use 事件，依 4 類 canonical task 編碼為 short/long path。

### E3 long_path_rate 結果

| Task | short | long | total | long_path_rate | 判讀 |
|------|-------|------|-------|----------------|------|
| pass_long_text_to_cli | 63 | 5 | 68 | 0.074 | < 0.1，缺實證（PC-087/W15-007 規則有效） |
| modify_file_locally | 468 | 0 | 468 | 0.000 | < 0.1，缺實證（v1 保守計數，保留觀察） |
| search_strings | 361 | 124 | 485 | 0.256 | 0.1–0.3 灰色地帶，接近邊緣，加觀察條款 |
| find_files | 80 | 56 | 136 | 0.412 | > 0.3，支持偏誤，強化防護 |
| **ALL** | **972** | **185** | **1157** | **0.160** | 0.1–0.3 灰色地帶，不作全稱 causal claim |

### 主張範圍限定

- **特別 endorsed（觀察性強證據，H1 步驟估算偏誤機制支持）**：`find_files`（rate 0.412；W15-015 分層驗證：71.9% long-path 為 Glob 單步可替代；mixed-session 可替代率 60.9% 顯示「未被觸發」而非「不知道」）
- **明確 NOT endorsed（防護已有效）**：`pass_long_text_to_cli`（rate 0.074，PC-087/W15-007 heredoc 規則已控制）
- **灰色地帶觀察中**：`search_strings`（rate 0.256，接近但未達 > 0.3 閾值）
- **整體主張**：不降級為 hypothesis，但限定為「在特定 task 類別有實證支持」，不得引用 PC-088 v2 作全稱 causal claim

### 整體 rate 的 base rate 解讀

overall rate = 0.160 位於 0.1–0.3 灰色地帶，**不代表全面性偏誤**。各 task 類別的異質性（0.000 vs 0.412）顯示偏誤是 task-specific，而非普遍現象。引用此 error-pattern 時需指定 task 類別。

### E2 因果實驗暫緩說明

E3 整體 rate（0.160）未達 > 0.3 的 E2 觸發閾值，**E2 完整 A/B 因果實驗暫不執行**。

保留選項：未來可針對 `find_files` 單一類別執行 E2 子實驗（rate 0.412，具備因果分析基礎）。觸發條件：若累積更多 session 後 `find_files` rate 穩定 > 0.3，可重啟 E2 設計（參見 `docs/experiments/PC-088-v2-validation.md` §6）。

### find_files 子類因果驗證（W15-015，2026-04-18）

針對 find_files rate 0.412 觸發進一步分層分析（採 Path A 觀察性方法，放棄 Path B 因其 rule-loading 污染風險高於可獲資訊量）。結果：

| 指標 | 值 | 訊號 |
|------|-----|------|
| 納入樣本（find -name + ls -R，排除 ls DIR） | 57 | — |
| Glob 可替代率（整體） | 0.719 | H1 強 |
| Mixed session 可替代率（session 內同時用 Glob 與 long-path） | 0.609 | H1 強 |
| Session profile | mixed=9, glob-only=12, **long-only=16** | H1 強 |

**結論**：**H1（步驟估算偏誤）觀察性強證據支持**。

- 71.9% 的 find_files long-path 是 Glob 單步可替代（單純 `-name`/`-iname` 無 filter predicate）→ 非「工具不等價」
- 在已知用 Glob 的 session 中，仍有 60.9% 的 long-path 是可替代的 → 非「不知道 Glob」，而是「啟發式未被觸發」
- 16 個 long-only session 顯示偏誤最強訊號

**方法限制**：single-model、觀察性非實驗性、Glob 可替代性為保守判準（可能低估）、rule loading 相同無法分離規則效應。詳見 `docs/experiments/PC-088-v2-find-files-validation.md`。

**對 `find_files` 章節的更新**：本條款升級為「因果支持（觀察性強證據）」。Layer 2 強化防護維持，但因 mechanism 已有證據，引用時可以明確指「步驟估算偏誤導致 Glob 啟發式未被觸發」作為機制解釋。

## 防護（三層，依分類證據調整）

### Layer 1：路徑步驟數計算工具（核心防護）

選 tool 前強制估算**總步驟數**（不只單步感覺）：

| 檢查 | 問題 | 觸發重選 |
|------|------|---------|
| 完整路徑數算 | 從現在到目的地共幾步 tool call？ | > 2 步 → 問「有無 1 步解」 |
| 訓練偏誤自檢 | 我選這路徑是因為「看過很多這樣寫」還是「實測最短」？ | 前者 → 找替代 |
| Tool result 進度陷阱 | 多步驟的中途回饋是否讓我覺得「比較穩」？ | 是 → 警覺，單步風險未必高 |
| 專用工具檢查 | 有 Edit / Grep / Glob / heredoc 等 1 步工具嗎？ | 是 → 優先 |

### Layer 2：情境特定規則（依 E3 分類調整）

| 情境 | short path（預設）| E3 狀態 | 規則來源 |
|------|-----------|---------|---------|
| 長文字傳遞 | heredoc | 已有效（rate 0.074） | 規則五（W15-007）|
| 檔案搜尋 | Glob | **強化防護**（rate 0.412，find 是高頻 long path 來源） | tool-discovery + 本條款 |
| 內容搜尋 | Grep | 觀察中（rate 0.256，加觀察條款） | CLAUDE.md Bash 規範 |
| 檔案編輯 | Edit/MultiEdit | 無實證問題（rate 0.000） | Edit 工具描述 |
| 多步推理 | 派發 Agent | 未測量（超出 E3 範圍） | agent tool 描述 |

**find_files 強化說明**：E3 long path 樣本顯示，`find . -name "*.md"` 和 `ls | grep pattern` 是高頻違規形式。應優先使用 `Glob` 工具；若確需 Bash find，須有明確理由（如跨目錄複雜條件）。

**search_strings 觀察條款**：rate 0.256 接近但未達灰色地帶上界（0.3）。建議持續偏好 `Grep` 工具，若後續 audit 顯示率上升則升級為強化防護。

### Layer 3：決策點摩擦（與短路徑預設並行）

決策點（象限 C）不因「短路徑是預設」而降摩擦：
- ANA Ticket claim → Phase 1+2 反思（W15-009 設計）
- Phase 4 重構評估 → Phase 2 WRAP
- 規則/規格修改 → parallel-evaluation

## 識別信號

| 信號 | 含義 |
|------|-----|
| 準備 > 2 步 tool call 達成目的 | 過 Layer 1 總步驟檢查 |
| 覺得「多步驟每步有回饋比較穩」 | Tool result 進度錯覺觸發 |
| 「這樣比較乾淨」「訓練資料常見」 | 訓練偏誤信號 |
| 看到長 heredoc / 長 Edit old_string 猶豫 | 單步感覺 bias，非技術限制 |
| 使用 Bash find 而非 Glob | find_files 類 long path（E3 高頻違規形式） |
| 使用 Bash grep 而非 Grep 工具 | search_strings 類 long path（E3 灰色地帶觀察） |

## 案例

- 2026-04-18（W15-001 session）：PM 選 Write /tmp → cat → append-log（**3 步**）而非 heredoc（**1 步**）。PC-087 記錄具體案例
- 2026-04-18（W15-005 session）：用戶質疑 PC-087 根因太淺，PM 深度反思識別到「檔案感物化 + 認知負擔規避」，但此第二層深因仍未達真根因
- 2026-04-18（W15-008 後 reframe）：用戶指出此與 friction-methodology 衝突，真根因是**步驟數估算偏誤**而非「短路徑偏好 bias」。PC-088 v2 依此重寫
- 2026-04-18（W15-014 E3 audit）：n=1157 retrospective audit 顯示 find_files 偏誤最高（0.412），pass_long_text 已被防護控制（0.074）；整體 0.160 為灰色地帶，採分類討論取代一刀切結論
- 2026-04-18（W15-015 find_files 子類驗證）：採 Path A 觀察性分層分析（n=57 納入樣本）。結果：71.9% long-path 為 Glob 單步可替代，mixed-session 可替代率 60.9% → **H1 步驟估算偏誤機制獲觀察性強證據支持**。放棄 Path B prospective A/B（rule-loading 污染風險 > 資訊增益）。見 `docs/experiments/PC-088-v2-find-files-validation.md`

## 方法論教訓

### 「深度反思」本身也有盲點

W15-005 的 two-phase reflection 產出了「認知負擔規避」作為根因。但用戶的摩擦力視角 reframe 揭示：
- Phase 1 的多假設 Reality Test 深度仍不夠
- 缺少「與既有方法論對照」檢查
- 真根因再深一層（估算偏誤）

**啟示**：深度反思 + WRAP + 結論後對照權威方法論（third-phase check）才是完整流程。

### 概念使用需 second-order 檢驗

我在 PC-088 v1 用「bias」「對抗」「架構偏誤」等詞，**與本專案 friction-methodology 詞彙系統不一致**。概念挪用需確認是否與既有權威 source 衝突。

### 實驗設計需考慮異質性

E3 結果顯示不同 task 類別之間 long_path_rate 差距達 0.412 倍。若以整體 rate 一刀切，會同時：
- 過度降級有實證的 find_files 偏誤防護
- 過度強化已受控的 pass_long_text 防護

**啟示**：error-pattern 的防護策略應依 task 類別分類，而非全稱宣告。

## 相關

- `.claude/error-patterns/process-compliance/PC-087-pm-tmp-detour-for-ticket-content.md`（具體案例）
- `.claude/methodologies/friction-management-methodology.md`（摩擦力權威 source）
- `.claude/methodologies/three-phase-reflection-methodology.md`（反思方法論，W15-009 將補 Phase 3 方法論對照檢查）
- `docs/experiments/PC-088-v2-validation.md`（E3 audit 完整報告，W15-014）
- 0.18.0-W15-005（深度反思 ANA）
- 0.18.0-W15-009（決策樹反思觸發點細化，方向調整為「決策點摩擦 + 執行點短路徑預設」）
- 0.18.0-W15-014（E3 retrospective audit 執行）
- `.claude/rules/core/tool-discovery.md`（工具發現規則）
