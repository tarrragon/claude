# AUQ Option Pattern Detector Hook — 功能規格

**Ticket**: 0.18.0-W5-042
**Phase**: 1（功能規格設計）
**狀態**: 待 Phase 2 測試設計 / Phase 3b 實作
**Hook 名稱**: `auq-option-pattern-detector-hook.py`

---

## 1. 目的與背景

補齊 PC-064（PM 列純文字選項未用 AskUserQuestion）多層防護的最後一層——Hook 層。

既有 `askuserquestion-reminder-hook.py` 只在 `PreToolUse/Task` 且 prompt 含 2+ Ticket ID 時觸發，**不覆蓋 PM 對話中途列選項（A./B./C.、1./2./3.）或以二元問句結尾等待用戶回應的場景**。本 Hook 專責此缺口。

**非目標**：本 Hook **不阻擋** PM 輸出（warning-only），只在下一輪注入提醒文字，避免新增 permission 摩擦（PC-064 設計原則）。

---

## 2. Hook 類型與觸發時機

### 決策：UserPromptSubmit

| 候選 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| **UserPromptSubmit** | 可注入 additionalContext 給下一輪 PM；讀 transcript 取得上一輪 assistant 輸出；與既有 prompt-submit-hook 生態對齊 | 提醒延後到用戶下一次輸入後才出現 | **採用** |
| Stop | 回合結束時可即時檢查 output | Stop hook 無 additionalContext 注入通道；回合已結束，提醒無處落點 | 不採用 |
| PreToolUse | 工具呼叫前可阻擋 | PM 列選項通常是純文字回覆不伴隨工具呼叫；覆蓋不到場景 | 不採用 |

### ADR-1: 為何選 UserPromptSubmit

- **落點正確**：PC-064 違規模式是「PM 輸出純文字選項後等用戶回答」。提醒必須出現在「用戶即將輸入回答」那一刻，正好是 UserPromptSubmit 的時機。
- **有注入通道**：`hookSpecificOutput.additionalContext` 可將提醒文字注入到下一輪 PM 的 context 前綴，PM 在生成下次回應時會看到「上次可能該用 AUQ」提醒。
- **transcript 可讀**：透過 `transcript_path` 欄位讀取 session transcript，取得上一輪 assistant 訊息文字進行 pattern 偵測。

### ADR-2: 為何不採 Stop

Stop hook 的設計目的是阻擋 stop 行為或執行清理，`hookSpecificOutput` 無 `additionalContext` 語意；即使輸出文字，也不會進入下一輪 PM 的 context。

---

## 3. 偵測規則

### 3.1 輸入來源

- 從 `input_data.transcript_path`（JSONL session log）讀取最後一則 role=assistant 訊息。
- 若 transcript 讀取失敗（檔案不存在 / 讀取異常），**預設放行**（logger.info 記錄，不 stderr）。

### 3.2 選項 Pattern 偵測（真陽性信號）

必須**同時**滿足以下兩條件才算命中：

| 條件 | 規則 | 範例 |
|------|------|------|
| (A) 連續選項標記 | 同一訊息內出現 **3 個以上**行首選項標記 | `A. 繼續`、`B. 暫停`、`C. 回退` |
| (B) 選項語境 | 訊息結尾 400 字內出現問句關鍵字 | `要選哪個`、`請選擇`、`哪個比較好`、`?`、`？` |

**支援的選項標記 regex**（行首，allow 前置空白 ≤ 2）：

```
^[ ]{0,2}(?:[A-Ea-e]\.|[1-5]\.|選項[一二三四五ABCDE12345]|Option\s*[A-E1-5])[ \t]+\S
```

**問句結尾 heuristic**：取訊息尾端 400 字，若含以下任一：
- `要選哪個`、`哪個比較好`、`請選擇`、`要不要`、`需要做`、`應該`、`先做...還是`
- 最後 50 字內含 `?` 或 `？`
- 最後一行以問號結尾

### 3.3 二元問句 Pattern（擴展真陽性）

即使無 A./B./C. 標記，若訊息**結尾 200 字**同時含以下兩種信號，也算命中：

- 二元問句關鍵字：`要繼續嗎`、`確認執行嗎`、`需要做 X 嗎`、`要不要`、`是否繼續`
- 明顯問號結尾（`?` 或 `？`）

理由：覆蓋 askuserquestion-rules 通用觸發原則問題 2「二元確認問句」。

### 3.4 Code Block 排除

偵測前**移除**所有 fenced code block（\`\`\`…\`\`\`）與 inline code（`…`）。選項列在程式碼範例中不算違規。

---

## 4. 豁免規則（假陽性防護）

偵測到 3.2 / 3.3 命中後，若同時命中以下任一豁免條件，**視為假陽性，不提醒**：

| # | 豁免名稱 | 判定規則 | 範例 |
|---|---------|---------|------|
| E1 | 引用既有文件選項 | 訊息中在命中 pattern 前後 300 字內含「引用」「參考」「根據」「如下列所述」「askuserquestion-rules」「18 個場景」「規則表」等詞 | 「根據 askuserquestion-rules 的 18 個場景：A…B…C…」 |
| E2 | 歷史決策回顧（過去時態） | 命中 pattern 前 200 字內含「先前」「已完成」「過去」「當初」「W5-0」「之前 commit」「歷史」等詞 | 「先前 W5-040 提出了 A.… B.… C.… 三個方案」 |
| E3 | 程式碼 / 表格註解 | pattern 全部落在 Markdown table cell（`\|…\|` 行）或位於 HTML 註解 `<!-- … -->` 內 | 表格文件化選項 |
| E4 | Hook/規則文件寫作場景 | 訊息含「.claude/」+「.md」路徑字串且佔比 > 10% | 正在編輯規則文件 |
| E5 | 代理人產出內容 | input_data 含 `agent_id`（subagent 環境）→ 直接跳過，不進 pattern 偵測 | 代理人回報內容 |

**豁免判斷順序**：E5（subagent）> E4（規則寫作）> E1（引用）> E2（歷史）> E3（表格/註解）。

**設計原則**：**寧可漏報不可誤報**。誤報會訓練 PM 忽略提醒，漏報只是少一次提醒（其他防護層仍會接住）。

---

## 5. 提醒訊息設計

命中且未豁免時，注入以下 additionalContext（全文 < 400 字）：

```
[AUQ Option Pattern Reminder]

你上一次回覆疑似包含選項列表（A./B./C. 等）或二元確認問句，等待用戶做決策。

根據 .claude/pm-rules/askuserquestion-rules.md 規則 1/3：
- 規則 1：所有選擇型決策（多選或二元 yes/no）必須使用 AskUserQuestion 工具，禁止純文字列選項
- 規則 3：禁止純文字提問讓用戶自由回答（自然語言回覆可能被 Hook 誤判為開發命令）

若此次確為決策點，下一輪請改用：
  1. ToolSearch("select:AskUserQuestion") 載入 schema
  2. 以 AskUserQuestion 工具重新呈現選項

若為引用文件 / 歷史回顧 / 規則寫作，忽略此提醒即可。

參考：PC-064 錯誤模式 / askuserquestion-rules 18 個場景
```

訊息來源：新增常數 `AUQOptionPatternMessages.REMINDER`（.claude/hooks/lib/hook_messages.py）。

---

## 6. hookSpecificOutput JSON 結構

### 6.1 未命中（大多數情況）

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit"
  }
}
```

### 6.2 命中且未豁免

```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[AUQ Option Pattern Reminder]\n..."
  }
}
```

**重要**（IMP-055 / PC-053）：
- `hookEventName` 欄位不可省略，半結構化 JSON 會觸發 validation failed
- UserPromptSubmit **不使用** `permissionDecision` 欄位（該欄位僅 PreToolUse 有效）
- stdout 只輸出完整 JSON，stderr 不寫任何內容
- logger 只用 `info` / `debug`（PC-053：warning/error 會觸發 hook error UI）

### 6.3 例外情境

| 情境 | 行為 | stdout |
|------|------|--------|
| subagent 環境（E5） | 跳過偵測 | 無 additionalContext 的 6.1 格式 |
| transcript 讀取失敗 | 記 info log，放行 | 6.1 格式 |
| JSON 解析失敗 | 記 info log，放行 | 6.1 格式 |
| 未預期例外 | run_hook_safely 捕捉，記 critical | 非零 exit code（由 wrapper 處理）|

---

## 7. settings.json 註冊

在 `.claude/settings.json` 的 `hooks.UserPromptSubmit` 陣列新增一筆（與既有 `prompt-submit-hook` 並列）：

```json
{
  "type": "command",
  "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/auq-option-pattern-detector-hook.py",
  "timeout": 5000
}
```

**Matcher**: UserPromptSubmit 無 matcher（全域觸發）。

**註冊順序**：排在既有 `prompt-submit-hook` 之後，確保不互相干擾（兩者皆注入 additionalContext，Claude Code runtime 會合併）。

---

## 8. 測試策略

### 8.1 單元測試覆蓋（Phase 2 sage 設計）

建立 `.claude/hooks/tests/test_auq_option_pattern_detector.py`，模式參考既有 hook 測試。

### 8.2 真陽性測試（3 場景，必須命中提醒）

| TP# | 場景 | 輸入（模擬上一輪 assistant 訊息） | 預期 |
|-----|------|-------------------------------|------|
| TP1 | 連續 A./B./C. 選項 + 問句結尾 | `"接下來有三個方向：\nA. 繼續下個 Ticket\nB. 補強測試\nC. 先 commit\n\n要選哪個？"` | additionalContext 含 AUQ 提醒 |
| TP2 | 數字標記 1./2./3. + 請選擇 | `"有以下選項：\n1. 方案甲\n2. 方案乙\n3. 方案丙\n\n請選擇。"` | 命中提醒 |
| TP3 | 二元確認問句（3.3 路徑） | `"W5-042 Phase 1 已完成，要繼續進 Phase 2 嗎？"` | 命中提醒 |

### 8.3 假陽性豁免測試（3 場景，必須靜默）

| FP# | 場景 | 輸入 | 豁免規則 | 預期 |
|-----|------|------|---------|------|
| FP1 | 引用既有文件 18 個場景 | `"根據 askuserquestion-rules 的 18 個場景：A. 驗收...B. 完成後...C. Wave 收尾... 詳見該文件"` | E1 | 無 additionalContext |
| FP2 | 歷史決策回顧 | `"先前 W5-040 當初提出三個方案：A. 規則強化 B. Hook 補強 C. CLAUDE.md，最後選了 A"` | E2 | 無 additionalContext |
| FP3 | Code block 內選項 | 訊息含 \`\`\`markdown\nA. foo\nB. bar\nC. baz\n\`\`\` 後接「執行以下 Ticket」 | code block 排除 + 無問句結尾 | 無 additionalContext |

### 8.4 邊界測試（建議 Phase 2 補充）

- 剛好 2 個選項標記（不足 3 個 → 不命中）
- 3 個標記但無問句關鍵字（不命中）
- transcript_path 不存在（放行）
- subagent 環境（agent_id 存在 → 直接放行）

---

## 9. PC-053 合規檢查

| 項目 | 合規做法 |
|------|---------|
| Logger 級別 | 只用 `logger.info()` / `logger.debug()` |
| stderr 輸出 | 禁止（會觸發 hook error UI 顯示）|
| 例外處理 | 透過 `run_hook_safely` wrapper 捕捉未預期例外 |
| 預期的例外（JSON 解析失敗、檔案不存在） | `logger.info()` 記錄後 return 0 |

---

## 10. 架構決策記錄（ADR 摘要）

| ID | 決策 | 理由 |
|----|------|------|
| ADR-1 | Hook event 選 UserPromptSubmit | 有 additionalContext 注入通道，落點正確 |
| ADR-2 | 不選 Stop | 無注入通道，提醒無落點 |
| ADR-3 | 不選 PreToolUse | PM 列選項純文字回覆通常不伴隨工具呼叫 |
| ADR-4 | Warning-only 不阻擋 | PC-064 設計原則：避免新增 permission 摩擦 |
| ADR-5 | 豁免優先於偵測（寧可漏報） | 誤報訓練 PM 忽略，漏報有其他防護層接住 |
| ADR-6 | subagent 環境直接跳過（E5） | 對齊既有 askuserquestion-reminder-hook；subagent 禁用 AUQ，提醒無意義 |
| ADR-7 | 3+ 標記閾值 | 2 個標記太易觸發（常見於普通列舉）；3+ 才是「選擇題」信號 |
| ADR-8 | 訊息常數集中 hook_messages.py | 對齊既有 AskUserQuestionMessages 模式，便於維護與國際化 |

---

## 11. Phase 2/3 交接事項

### Phase 2（sage 測試設計）需擴展

- 將 8.2 / 8.3 / 8.4 具體化為 pytest 測試函式
- 補齊 transcript JSONL 解析的測試夾具
- 補齊豁免規則 E1–E5 各自的 unit test

### Phase 3b（實作）需完成

- `.claude/hooks/auq-option-pattern-detector-hook.py`（預估 150–200 行）
- `.claude/hooks/lib/hook_messages.py` 新增 `AUQOptionPatternMessages.REMINDER`
- `.claude/settings.json` 註冊（UserPromptSubmit 陣列）
- 可選：提取 transcript 最後 assistant 訊息的 helper（若 hook_utils 未提供，新增至 hook_utils.py）

### 未決事項（留給 Phase 2/3b 決定）

- transcript JSONL 格式細節（需 sage 在 Phase 2 實地讀取 sample 確認欄位）
- 豁免關鍵字清單是否需外部化為 YAML（建議 Phase 3b 視程式碼量決定）

---

**Spec Length**: ~280 lines
**Last Updated**: 2026-04-13
**Author**: basil-hook-architect (W5-042 Phase 1)
