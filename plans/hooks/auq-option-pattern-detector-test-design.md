# AUQ Option Pattern Detector Hook — 測試設計（Phase 2）

**Ticket**: 0.18.0-W5-042
**Phase**: 2（測試設計）
**依據規格**: `.claude/plans/hooks/auq-option-pattern-detector-spec.md`（267 行）
**目標實作**: `.claude/hooks/auq-option-pattern-detector-hook.py`（Phase 3b）
**測試檔案**: `.claude/tests/hooks/test_auq_option_pattern_detector.py`

---

## 1. 測試框架與執行策略

### 1.1 框架選擇

| 項目 | 選擇 | 理由 |
|------|------|------|
| 測試框架 | pytest | `.claude/` 既有測試一致採用；支援 fixture / parametrize / tmp_path |
| 執行方式 | `uv run pytest`（uv single-file script 模式） | 對齊 hook 本身的 UV 依賴管理 |
| 執行命令 | `(cd .claude && uv run pytest tests/hooks/test_auq_option_pattern_detector.py -v)` | 避免 shell cwd 污染（bash-tool-usage-rules 規則 1） |
| 通過標準 | 10+ 測試全綠（3 TP + 3 FP + 4 邊界 + N 契約） | 對應 AC6 + AC8 |

### 1.2 測試組織

```
.claude/tests/hooks/
├── test_auq_option_pattern_detector.py   # 主測試檔（本設計產物）
└── fixtures/
    └── auq_transcripts/                   # JSONL transcript fixtures
        ├── tp1_abc_options.jsonl
        ├── tp2_numeric_options.jsonl
        ├── tp3_binary_question.jsonl
        ├── fp1_document_reference.jsonl
        ├── fp2_historical_review.jsonl
        ├── fp3_code_block_options.jsonl
        ├── b1_two_options.jsonl
        ├── b2_distant_question.jsonl
        ├── b3_rule_writing.jsonl
        └── malformed.jsonl
```

---

## 2. Fixture 策略

### 2.1 JSONL Transcript Fixture 格式

Claude Code transcript JSONL 格式（每行一個 JSON object）：

```jsonl
{"type":"user","message":{"role":"user","content":"先前任務"}}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"<主要測試目標文字>"}]}}
```

實作測試時須在 Phase 3b 實地確認格式細節（規格 §11 未決事項 1）；本設計提供兩種候選格式的 fixture 讓實作者二擇一對齊：
- 候選 A（stringified content）：`"content":"純文字"`
- 候選 B（content blocks）：`"content":[{"type":"text","text":"..."}]`

測試設計**預設採候選 B**（較接近 Claude Code runtime 實際格式），若 Phase 3b 發現為候選 A，改用 parametrize 覆蓋兩種即可。

### 2.2 Hook 輸入 JSON Fixture 結構

Hook 從 stdin 讀取的 JSON（基於既有 askuserquestion-reminder-hook 模式）：

```json
{
  "hook_event_name": "UserPromptSubmit",
  "transcript_path": "<tmp_path>/session.jsonl",
  "session_id": "test-session-abc",
  "cwd": "/Users/.../book_overview_v1",
  "user_prompt": "下一輪用戶輸入（本 Hook 不依賴此欄位，但格式需完整）"
}
```

Subagent 環境額外欄位（觸發 E5 豁免）：

```json
{
  "hook_event_name": "UserPromptSubmit",
  "transcript_path": "...",
  "agent_id": "thyme-extension-engineer"
}
```

### 2.3 Pytest Fixture 設計

| Fixture | 作用範圍 | 產出 |
|---------|---------|------|
| `tmp_transcript_path(tmp_path)` | function | 建立空 JSONL 檔，回傳 Path |
| `make_transcript(tmp_transcript_path)` | function | callable：`make_transcript(assistant_text: str, prior_user: str = "...")`，寫入 JSONL 並回傳路徑 |
| `hook_input(make_transcript)` | function | callable：`hook_input(assistant_text, *, agent_id=None)`，回傳完整 stdin dict |
| `run_hook(monkeypatch, capsys)` | function | callable：`run_hook(stdin_dict) -> (stdout_json, stderr_text, exit_code)`，執行 hook entry function |

### 2.4 Hook 執行介接

兩種可行做法（Phase 3b 擇一）：

| 做法 | 優點 | 缺點 |
|------|------|------|
| (a) 匯入 hook 的 `main()` 函式直接呼叫，`monkeypatch` stdin/stdout | 快；可直接斷言回傳結構 | 需 hook 將 IO 與邏輯分離 |
| (b) `subprocess.run(hook.py, input=json_stdin)` | 真實端到端 | 較慢；stderr 斷言較脆弱 |

**建議 Phase 3b 採 (a)**：要求 hook 匯出 `detect_and_build_output(input_data: dict, transcript_text: str | None) -> dict` 純函式，測試直接對此函式斷言，另加 1-2 個整合測試走 subprocess 路徑保障 CLI 契約。

---

## 3. RED 測試案例清單

### 3.1 真陽性（TP）— 應觸發 warning

| # | 測試名稱 | 目的 | 輸入 assistant 訊息（摘要） | 預期輸出 | AC |
|---|---------|------|-----------------------------|---------|----|
| TP1 | `test_detects_abc_options_with_question_ending` | 覆蓋 §3.2 條件 A+B（3 個 A./B./C. + 問句結尾） | `"接下來有三個方向：\nA. 繼續下個 Ticket\nB. 補強測試\nC. 先 commit\n\n要選哪個？"` | JSON 含 `additionalContext`，內文含 `"AUQ Option Pattern Reminder"` 與 `"askuserquestion-rules"` | AC1, AC3, AC6 |
| TP2 | `test_detects_numeric_options_with_please_choose` | 覆蓋 1./2./3. 標記變體 + 「請選擇」關鍵字 | `"有以下選項：\n1. 方案甲\n2. 方案乙\n3. 方案丙\n\n請選擇。"` | 同 TP1：含 reminder additionalContext | AC1, AC3, AC6 |
| TP3 | `test_detects_binary_confirmation_question` | 覆蓋 §3.3 二元問句路徑（無標記但含確認問句+問號） | `"W5-042 Phase 1 已完成，要繼續進 Phase 2 嗎？"` | 含 reminder additionalContext | AC1, AC6 |

### 3.2 假陽性豁免（FP）— 不應觸發 warning

| # | 測試名稱 | 目的 | 輸入 assistant 訊息（摘要） | 預期輸出 | AC |
|---|---------|------|-----------------------------|---------|----|
| FP1 | `test_exempts_document_reference_citation` | E1 引用豁免 | `"根據 askuserquestion-rules 的 18 個場景：A. 驗收...B. 完成後...C. Wave 收尾... 詳見該文件"` | JSON 無 `additionalContext` 欄位（或為空） | AC4 |
| FP2 | `test_exempts_historical_decision_review` | E2 歷史回顧豁免（過去時態 + W5 編號） | `"先前 W5-040 當初提出三個方案：A. 規則強化 B. Hook 補強 C. CLAUDE.md 更新，最後選了 A"` | 無 additionalContext | AC4 |
| FP3 | `test_exempts_options_inside_code_block` | §3.4 code block 排除 | 訊息含 ` ```markdown\nA. foo\nB. bar\nC. baz\n``` ` 後接 `"執行以下 Ticket"`，**無問句** | 無 additionalContext（code block 移除後無 pattern） | AC3, AC4 |

### 3.3 邊界測試（B）

| # | 測試名稱 | 目的 | 輸入 | 預期輸出 | AC |
|---|---------|------|------|---------|----|
| B1 | `test_no_trigger_with_only_two_options` | §3.2 閾值（3+ 才算） | `"兩個方向：\nA. 做\nB. 不做\n\n要哪個？"` | 無 additionalContext | AC3 |
| B2 | `test_no_trigger_when_question_far_from_options` | §3.2 條件 B（400 字距離） | 3 個 A./B./C. 選項後接 > 400 字敘述，結尾才出現「怎麼想？」 | 無 additionalContext | AC3 |
| B3 | `test_exempts_rule_writing_context` | E4 豁免（規則文件寫作場景） | 訊息含多個 `.claude/pm-rules/*.md` 路徑 + A./B./C. | 無 additionalContext | AC4 |
| B4 | `test_skips_in_subagent_environment` | E5 豁免（`agent_id` 存在） | 標準 TP1 文字 + `hook_input(..., agent_id="thyme")` | 無 additionalContext（直接跳過偵測） | AC4 |

### 3.4 契約與例外測試（C）

| # | 測試名稱 | 目的 | 輸入 | 預期輸出 | AC |
|---|---------|------|------|---------|----|
| C1 | `test_output_always_contains_hook_event_name` | IMP-055 契約：即使未命中也必須有 `hookEventName` | 任意未命中輸入 | stdout JSON 含 `hookSpecificOutput.hookEventName == "UserPromptSubmit"` | AC2, AC6 |
| C2 | `test_no_permission_decision_field` | 規格 §6 UserPromptSubmit 不使用 permissionDecision | 命中輸入（TP1） | stdout JSON 的 hookSpecificOutput 不含 `permissionDecision` key | AC2 |
| C3 | `test_missing_transcript_path_passes_through` | §3.1 / §6.3 transcript 讀取失敗預設放行 | `hook_input` 的 transcript_path 指向不存在檔案 | exit 0；無 additionalContext；不寫 stderr | AC2 |
| C4 | `test_malformed_jsonl_passes_through` | §6.3 JSON 解析失敗放行 | transcript 檔案含損壞 JSONL 行 | exit 0；無 additionalContext；不寫 stderr | AC2 |
| C5 | `test_no_stderr_output_on_expected_paths` | PC-053 合規：預期路徑禁寫 stderr | 遍歷 TP1 / FP1 / C3 / C4 | 所有情境 `capsys.readouterr().err == ""` | PC-053 |
| C6 | `test_logger_uses_info_debug_only` | PC-053 合規：禁用 warning/error level | 全測試跑完後檢查 hook log 檔 | log 內容無 `WARNING` / `ERROR` 標記 | PC-053 |

**測試總數**：3（TP）+ 3（FP）+ 4（B）+ 6（C） = **16 個**（超過 10+ 通過標準）。

---

## 4. 驗收條件對應表

| AC | 規格條款 | 涵蓋測試 |
|----|---------|---------|
| AC1：新增 Hook 偵測 PM 輸出含高信心度選項 pattern | 規格 §3 | TP1, TP2, TP3 |
| AC2：Hook 設為 warning 非 block 不阻擋流程 | 規格 §6, ADR-4 | C1, C2, C3, C4 |
| AC3：偵測規則（3+ A/B/C + 冒號 + 不在 code block） | 規格 §3.2, §3.4 | TP1, TP2, FP3, B1, B2 |
| AC4：false positive 豁免清單（引用/歷史回顧等） | 規格 §4 E1–E5 | FP1, FP2, FP3, B3, B4 |
| AC5：UserPromptSubmit 注入提醒 | 規格 §5, §6.2 | TP1（斷言 additionalContext 內文）, TP2, TP3 |
| AC6：單元測試覆蓋（3 TP + 3 FP） | 規格 §8.2, §8.3 | TP1-3, FP1-3 全員 |
| AC7：settings.json 註冊 Hook | 規格 §7 | **Phase 3b 實作時驗證**（非單元測試範圍，建議另加 smoke test 讀 settings.json 斷言存在該 entry） |

**AC7 補充**：建議 Phase 3b 在實作完成後加一個契約測試 `test_hook_registered_in_settings`，讀 `.claude/settings.json` 確認 `hooks.UserPromptSubmit` 陣列含 `auq-option-pattern-detector-hook.py` entry。此測試不屬本設計的 RED 燈範圍，列為 Phase 3b 實作附帶項。

---

## 5. Hook 輸入/輸出契約驗證細節

### 5.1 輸入契約（Hook 從 stdin 讀取）

| 欄位 | 型別 | 必要 | 測試策略 |
|------|------|------|---------|
| `hook_event_name` | string | 是 | 所有測試固定 `"UserPromptSubmit"` |
| `transcript_path` | string (path) | 是 | C3 測試不存在路徑；其餘用 `tmp_path` |
| `session_id` | string | 否 | 填入 dummy 值 |
| `cwd` | string | 否 | 填入 project root |
| `agent_id` | string | 否 | B4 測試填入；其餘 omit |

### 5.2 輸出契約（Hook 寫入 stdout 的 JSON）

**未命中（含豁免、讀檔失敗、非 UserPromptSubmit 等）**：

```json
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit"}}
```

斷言：
- `json.loads(stdout)` 成功
- `result["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"`
- `"additionalContext" not in result["hookSpecificOutput"]`

**命中且未豁免**：

```json
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "[AUQ Option Pattern Reminder]\n..."}}
```

斷言：
- `additionalContext` 存在且為非空字串
- 內文含 `"AUQ Option Pattern Reminder"` header（規格 §5）
- 內文含 `"askuserquestion-rules"` 指引
- 內文長度 < 400 字（規格 §5 要求）

### 5.3 錯誤路徑行為

| 錯誤 | 預期行為 | 測試 |
|------|---------|------|
| transcript 檔案不存在 | logger.info 記錄；exit 0；輸出 5.2 未命中格式；**不寫 stderr** | C3 |
| JSONL 格式損壞 | logger.info 記錄；exit 0；輸出 5.2 未命中格式；**不寫 stderr** | C4 |
| stdin JSON 解析失敗 | `run_hook_safely` wrapper 捕捉；exit non-zero | （不在本設計範圍，屬 hook_utils 測試）|
| 未預期例外 | `run_hook_safely` 捕捉；logger.critical；exit non-zero | （同上）|

---

## 6. Phase 3b TDD 紅燈推進順序建議

建議 thyme/basil 實作時依下列順序讓測試由紅轉綠，每步最小化實作：

| 步驟 | 目標測試 | 實作要點 |
|------|---------|---------|
| 1 | C1, C3 | 最小骨架：讀 stdin → 輸出 `{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit"}}`；transcript 讀取失敗時直接回 stdout 未命中格式 |
| 2 | B4 | 加入 `agent_id` 檢查（`is_subagent_environment`），subagent 直接短路 |
| 3 | TP1 | 實作 regex 偵測（3+ `^[ ]{0,2}[A-E]\.` 行首）+ 結尾 400 字內問句 heuristic + 注入 additionalContext |
| 4 | TP2 | 擴展 regex 支援 `1./2./3.` 與「請選擇」關鍵字 |
| 5 | FP3, B2 | Code block 移除預處理 + 距離閾值實作 |
| 6 | B1 | 嚴格 3+ 閾值（不可回退到 2） |
| 7 | FP1 | E1 引用關鍵字豁免 |
| 8 | FP2, B3 | E2 歷史回顧 + E4 規則寫作豁免 |
| 9 | TP3 | §3.3 二元問句 path（獨立分支，不依賴選項標記） |
| 10 | C2, C4, C5, C6 | PC-053 / IMP-055 契約強化；malformed JSONL 防禦；確認 logger level 使用 |

**TDD 原則**：每步只讓目標測試轉綠，不得讓已綠測試回紅（regression guard）。

---

## 7. 未決事項與 Phase 3b 確認清單

依規格 §11 留給 Phase 3b 決定的事項，本測試設計採用預設值，實作者若更改需回頭調整測試 fixture：

| 事項 | 本設計預設 | 若改變的影響 |
|------|-----------|------------|
| Transcript JSONL 格式（content string vs block） | 候選 B（content blocks） | 調整 `make_transcript` fixture 一行；改 parametrize 覆蓋兩種 |
| 豁免關鍵字清單是否外部化 YAML | 預設寫死在 hook 常數 | 若改 YAML 需加 fixture 載入；測試可保持不變 |
| `transcript_path` 相對/絕對路徑 | 統一絕對路徑（`tmp_path`）| 無影響（測試直接用 Path） |
| `run_hook_safely` wrapper 行為 | 假設沿用 `.claude/hooks/lib/hook_utils.py` 既有實作 | 若 wrapper 介面變更，C3/C4 測試入口可能需調整 |

---

## 8. 檢查清單（Phase 2 交付前自檢）

- [x] 測試框架與 fixture 策略明確（§1, §2）
- [x] RED 測試案例含 3 真陽 + 3 假陽 + 4 邊界 + 6 契約（§3）
- [x] 每個測試標註目的 / 輸入 / 預期輸出 / 對應 AC（§3）
- [x] AC1–AC7 皆有測試對應（§4，AC7 標註為 Phase 3b smoke）
- [x] Hook 輸入/輸出契約驗證詳細規範（§5）
- [x] 提供 TDD 紅燈推進順序（§6）
- [x] 標註 Phase 3b 未決事項與預設值（§7）
- [x] 未撰寫 Python 實作程式碼（僅測試設計文字）
- [x] 未修改 settings.json（留給 Phase 3b）
- [x] 行數控制在 200–400 行區間（~330 行）

---

**Design Length**: ~330 lines
**Last Updated**: 2026-04-13
**Author**: sage-test-architect (W5-042 Phase 2)
**Next Step**: Phase 3b 由 thyme-extension-engineer 或 basil-hook-architect 依 §6 TDD 順序實作
