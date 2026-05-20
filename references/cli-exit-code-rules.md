# CLI Exit Code 分層規範

本文件規範 `.claude/skills/` 與專案內所有 CLI 命令的退出碼設計，以三值（0/1/2）區分「業務通過 / 程式錯誤 / 業務拒絕」，作為 PC-096 防護的 SSOT。

> **核心理念**：exit code 是 CLI 與呼叫方（PM / Hook / shell pipeline / CI）之間的機器介面契約。`$?` 必須在不 parse stdout/stderr 的前提下，就能讓呼叫方決定「該重試、該停手、還是依拒絕原因處理」。

---

## 適用範圍

| 對象 | 是否適用 |
|------|---------|
| `.claude/skills/ticket/ticket_system/commands/*.py` | 是 |
| `.claude/skills/` 下其他 CLI 命令 | 是 |
| `.claude/hooks/*.py` 中以 exit code 表達決策的 hook | 是（0=allow / 1=internal error / 2=deny，與本規範對齊） |
| 純語法錯誤類（如 `print_not_executable_and_exit()` 模組 guard） | 否（可保留 `sys.exit(1)`） |
| 第三方 CLI 工具呼叫的結果轉譯 | 視情況（建議轉譯為本規範三值再回傳） |

---

## 強制規則

### 規則 1：三值 exit code 定義

| Exit Code | 語意 | 呼叫方應採取的動作 |
|-----------|------|------------------|
| `0` | GO / SUCCESS：業務邏輯通過、命令完成預期工作 | 繼續流程，無需介入 |
| `1` | INTERNAL_ERROR：例外、IO 失敗、依賴模組崩潰、程式 bug | 通知人類介入、檢查 stderr traceback、考慮重試或修復 |
| `2` | BUSINESS_REJECT / NO-GO：邏輯正常運作，依規則回答「不可放行」、輸入無效、查無資料 | 依拒絕原因（stdout / structured payload）決策，不應重試 |

**Why**：「程式錯誤」與「業務拒絕」是兩個本質不同的非成功狀態。前者表示命令本身無法完成工作（需修復），後者表示命令完成工作後給出否定結論（依結論行動）。若兩者共用 `exit 1`，呼叫方必須 parse stdout 才能區分，違反 exit code 作為機器決策訊號的設計初衷。

**Consequence**：混用 `exit 1` 會導致 Hook / CI 無法用 `$?` 自動化決策，shell `||` 與 `&&` 邏輯失準，PM 無法判斷該重試還是該停手；breaking change 修正成本隨著呼叫方增加而擴大。

**Action**：CLI 命令的 Phase 1 規格定義階段即列出三值對照表；實作階段在 except 區塊與業務判定區塊使用不同的 return 值；文件必含「呼叫方收到此 exit code 應如何處理」。

---

### 規則 2：路徑分離（except vs 業務判定）

| 路徑類型 | 必用 exit code | 範例 |
|---------|-------------|------|
| `try` 區塊內捕獲的非預期 `Exception` | `1` | 讀檔失敗、依賴模組 import 失敗、未預期 KeyError |
| 已知的 IO 錯誤導致無法判定 | `2`（保守回 NO-GO）或 `1`（依語意選擇） | 資料源暫時不可用，無法給出 GO 結論 → 視為業務拒絕 |
| 業務判定回答「不通過」 | `2` | acceptance 未通過、有阻擋項、查無資料 |
| 業務判定回答「通過」 | `0` | acceptance 全綠、無阻擋項 |
| 使用者輸入錯誤（參數互斥、找不到 ticket、index 解析失敗） | `2` | argparse 業務型錯誤 / 查無 ticket / 互斥旗標 |

**Why**：使用者輸入錯誤屬於「業務拒絕」（命令收到輸入後判定無法執行），不是程式自身崩潰，呼叫方需依錯誤訊息修正輸入而非重試或回報 bug。

**Consequence**：若把「找不到 ticket」與「YAML parse 崩潰」都 return 1，CI 無法只看 exit code 決定該回報用戶還是回報維運。

**Action**：實作時把 `except Exception` 與業務判定 if/else 明確拆為兩條 return 路徑，禁止共用 `return 1`。

---

## Unix 慣例對照

本規範對齊 Unix 三值 exit code 的成熟慣例（40+ 年）：

| 工具 | exit 0 | exit 1 | exit 2 |
|------|--------|--------|--------|
| `grep` | found（pattern 命中） | not found（pattern 未命中） | error（檔案讀不到、regex 無效） |
| `diff` | files identical | files differ | trouble（檔案讀不到等錯誤） |
| `test` / `[ ]` | expression true | expression false | error（語法錯誤） |
| **本規範** | GO / SUCCESS | INTERNAL_ERROR | BUSINESS_REJECT / NO-GO |

**注意對應差異**：`grep` / `diff` / `test` 把「business false」放在 `1`、「error」放在 `2`；本規範反向（「error」在 `1`、「business false」在 `2`）。差異原因：

1. 本規範服務的 CLI 多屬「驗收 / 派發決策 / handoff 檢查」類，「業務拒絕」需含 structured payload（阻擋項清單）由呼叫方解析，語意上更接近「需呼叫方介入處理」，與 Unix 慣例中的 `2` 對應「呼叫方需注意」的語感一致。
2. 本專案先行案例（`track_handoff_ready.py`、`ArgparseFormatErrorParser`）已採 `2=NO-GO/業務拒絕`，本規範跟隨既成事實避免再造混亂。

跨專案整合若需與 `grep` 慣例對齊，可在文件中明示對照表，但本專案內部一律採本規範語意。

---

## Phase 1 設計檢查清單

CLI 命令規格 review（含新命令設計、既有命令修改 exit code 行為）時必過下列檢查：

- [ ] 是否列出所有非成功狀態？是否已區分「程式錯誤（internal error）」與「業務拒絕（business reject）」兩類？
- [ ] exit code 表格是否涵蓋所有情境，且每個 code 的語意唯一（不重疊、不混用）？
- [ ] 程式內 `except` 區塊與業務判定區塊是否使用不同 exit code（前者 `1`、後者 `2`）？
- [ ] 命令文件是否說明「呼叫方收到此 exit code 應如何處理」（retry / abort / 顯示拒絕原因）？
- [ ] 是否對應 Unix 慣例（grep / diff / test）？若不一致是否有正當理由並明示？
- [ ] 使用者輸入錯誤（無效參數、查無資料）是否回 `2`（業務拒絕）而非 `1`？
- [ ] IO 異常導致「無法判定」時，是否依語意選 `2`（保守 NO-GO）或 `1`（無法繼續），且文件已說明？
- [ ] 測試是否含三值斷言（至少一個 `return 0`、`return 1`、`return 2` 案例）？

**Why**：上述檢查涵蓋 PC-096 識別出的所有混淆點。Phase 1 漏檢會讓 breaking change 累積到 Phase 3b 才暴露，修正成本隨呼叫方增加而擴大。

**Consequence**：若未過此清單就放行 Phase 1，後續 Hook 串接時必再發現混淆，需回頭修規格與既有呼叫端，違規範圍會隨呼叫方擴散。

**Action**：CLI 命令的 Phase 1 規格 review 應同時派發 thyme-python-developer 或 basil-writing-critic 對照本清單；發現未通過項目即列入 acceptance，不得豁免。

---

## 套用範例

### 正例：`track_handoff_ready.py`

來源：`.claude/skills/ticket/ticket_system/commands/track_handoff_ready.py:62-97`

```python
def execute_handoff_ready(args: argparse.Namespace) -> int:
    """執行 handoff-ready 命令。

    Returns:
        0: GO；1: 內部錯誤；2: NO-GO（含 IO_ERRORS 保守判定）
    """
    ticket_id = getattr(args, "ticket_id", None)

    try:
        state = checkpoint_state(
            ticket_id=ticket_id, caller="handoff-ready", log_metrics=True
        )
    except IO_ERRORS as e:
        # IO_ERRORS 視為「無法判定」，保守回 exit 2 (NO-GO)
        sys.stderr.write(f"WARN: data source(s) unavailable: {e}\n")
        print("結論: NO-GO  資料源異常無法確認 ready 狀態")
        return 2
    except Exception as e:
        # 非 IO_ERRORS：stderr + exit 1
        sys.stderr.write(f"handoff-ready internal error: {e}\n")
        return 1

    blockers = compute_blockers(state, ticket_id=ticket_id)
    if blockers:
        _print_no_go(blockers)
        return 2

    _print_go(state, ticket_id=ticket_id)
    return 0
```

**正例分析**：

| 路徑 | exit code | 對應規則 |
|------|-----------|---------|
| 成功檢查、無阻擋項 | `0` | 規則 1 GO |
| `IO_ERRORS`（資料源暫不可用） | `2` | 規則 2「無法判定」保守回 NO-GO |
| 非預期 `Exception` | `1` | 規則 2 except 區塊 |
| 業務判定有阻擋項 | `2` | 規則 1 NO-GO |

四條路徑語意清晰、無重疊；docstring 與註解明示「為何 IO_ERRORS 選 2 而非 1」的判斷依據，符合 Phase 1 檢查清單第 7 項。

---

### 反例：`track_audit.py:127-145`

來源：`.claude/skills/ticket/ticket_system/commands/track_audit.py:127-145`

```python
try:
    # 執行驗收檢查
    report = run_audit(ticket_id, version)
    print(_format_audit_report(report))

    # 根據結果返回狀態碼
    if report.overall_passed:
        return 0
    else:
        return 1                                    # 違規 1：業務拒絕回 1

except ValueError as e:
    print(format_error(f"{TrackAuditMessages.AUDIT_CHECK_FAILED_PREFIX}{str(e)}"))
    return 1                                        # 違規 2：與業務拒絕同碼
except Exception as e:
    print(format_error(f"{TrackAuditMessages.AUDIT_PROCESS_ERROR_PREFIX}{str(e)}"))
    return 1                                        # 違規 3：與業務拒絕同碼
```

**反例分析**：

| 路徑 | 現況 exit code | 違反規則 | 應改為 |
|------|--------------|---------|-------|
| `report.overall_passed=False`（業務拒絕） | `1` | 規則 1 / 規則 2 | `2`（NO-GO） |
| `ValueError`（內部錯誤） | `1` | （正確，但與業務拒絕共用） | 維持 `1` |
| `except Exception`（內部錯誤） | `1` | （正確，但與業務拒絕共用） | 維持 `1` |

**為何是反例**：呼叫方（PM / Hook）拿到 `exit 1` 後無法只用 `$?` 判斷「audit 確實沒過」還是「audit 本身崩潰」，必須 parse stdout 才能決定該回報 ticket 缺料還是回報 ticket CLI bug——正是 PC-096 描述的混淆模式。

**修復方向**：`report.overall_passed=False` → `return 2`；except 兩條維持 `return 1`。後續測試應加 return 2 與 return 1 各一個斷言案例（對應 Phase 1 檢查清單的三值斷言要求）。

---

## 與既有錯誤訊息機制的銜接

CLI exit code 是「機器決策訊號」；錯誤訊息內容是「人類可讀說明」。兩者必須協同運作，本專案既有機制如下：

### `lib/messages.py::ArgparseFormatErrorParser`

來源：`.claude/skills/ticket/ticket_system/lib/messages.py:404-442`

`ArgparseFormatErrorParser` 是 `argparse.ArgumentParser` 的 subclass，將業務型 argparse 錯誤（`invalid choice` / `invalid type value`）改走 `ErrorEnvelope` 結構化輸出，並呼叫 `sys.exit(2)`。

**與本規範的對應關係**：

| 機制 | 觸發條件 | exit code | 對應本規範規則 |
|-----|---------|-----------|--------------|
| `ArgparseFormatErrorParser.error()` | 使用者輸入無效（invalid choice 等） | `2` | 規則 2「使用者輸入錯誤 = 業務拒絕」 |
| `format_error(ErrorEnvelope)` 輸出（stderr） | 同上 | （搭配 exit 2） | 規則 1「人類可讀說明伴隨機器訊號」 |

**Action**：新 CLI 命令若以 argparse 接收輸入，應使用 `ArgparseFormatErrorParser` 而非預設 `ArgumentParser`，使參數錯誤自動採 `exit 2`（避免 argparse 預設的 `exit 2` 行為與本規範意外對齊但語意不明確的情況，改為顯式銜接）。

### `format_error()` 與 `ErrorEnvelope`

來源：`.claude/skills/ticket/ticket_system/lib/messages.py:244-327`

`ErrorEnvelope` 將錯誤封裝為含 `area` / `action` / `code` / `hint` 的結構化格式；`format_error()` 渲染為含版本標記的字串。

**與 exit code 的銜接準則**：

| 情境 | exit code | 訊息輸出 |
|------|-----------|--------|
| 業務拒絕（含參數錯誤、查無資料） | `2` | `format_error(ErrorEnvelope(...))` → stderr |
| 內部錯誤（unexpected exception） | `1` | `format_error(...)` 或 traceback → stderr |
| 業務通過 | `0` | 一般 stdout 輸出（無需 ErrorEnvelope） |

**Why**：人類可讀說明（stderr 訊息）與機器決策訊號（exit code）必須兩者皆有且語意一致。只給訊息不給 exit code → 自動化失敗；只給 exit code 不給訊息 → 人類除錯困難。

**Consequence**：若實作者只調整 exit code 而未同步 `ErrorEnvelope` 結構，呼叫方雖能用 `$?` 自動化，但 human-in-the-loop 修正時缺少結構化錯誤資訊。

**Action**：修復 PC-096 違規點的後續 IMP，業務拒絕路徑應同步檢查是否已輸出 `format_error(ErrorEnvelope)`，若無則一併補上；exit code 與訊息為同一 commit 的兩面，禁止分階段釋出。

---

## 與其他規則的邊界

| 規則 / 文件 | 聚焦 | 與本規範差異 |
|------------|------|------------|
| `PC-096-cli-exit-code-conflates-error-and-business-reject.md` | 反模式描述（症狀、根因、案例） | 本規範為正向 prescriptive guidance（PC-096 描述問題，本規範開藥方） |
| `quality-baseline.md` 規則 4（Hook 失敗必須可見） | stderr + 日誌雙通道 | 互補：本規範規定 exit code 語意；規則 4 規定訊息可見性 |
| `lib/messages.py` 的 `ErrorEnvelope` / `format_error` | 結構化錯誤訊息格式 | 互補：本規範用 exit code 機器決策；訊息機制處理人類可讀說明 |
| `PC-005`（CLI 失敗歸因假設） | 呼叫方對 exit 非零的歸因推論 | 互補：本規範把「失敗」拆為三類降低歸因錯誤機率 |

---

## 檢查清單

撰寫新 CLI 命令或修改既有命令前：

- [ ] 命令 docstring 是否含 `Returns:` 區塊明示 0/1/2 對應語意？
- [ ] except 區塊回 `1`、業務判定不通過回 `2`、業務通過回 `0`？
- [ ] 使用者輸入錯誤（無效參數、查無資料）走 `2` 而非 `1`？
- [ ] 業務拒絕路徑同步輸出 `format_error(ErrorEnvelope)`？
- [ ] argparse 採 `ArgparseFormatErrorParser`（若涉及業務型參數錯誤）？
- [ ] 測試含 return 0 / return 1 / return 2 各至少一案例？
- [ ] 已對照 Phase 1 設計檢查清單 8 項全部過關？

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-096-cli-exit-code-conflates-error-and-business-reject.md` — 本規範的動機案例（症狀 / 根因 / 反模式）
- `.claude/error-patterns/process-compliance/PC-005-cli-failure-assumption-attribution.md` — 姊妹模式（CLI 失敗歸因假設）
- `.claude/error-patterns/process-compliance/PC-015-error-prompt-silent-bypass.md` — 姊妹模式（錯誤提示靜默繞過）
- `.claude/rules/core/quality-baseline.md` 規則 4 — 異常可觀測性（stderr + 日誌雙通道）
- `.claude/skills/ticket/ticket_system/commands/track_handoff_ready.py` — 正例實作參考
- `.claude/skills/ticket/ticket_system/lib/messages.py` — `ArgparseFormatErrorParser` / `ErrorEnvelope` / `format_error`

---

**Last Updated**: 2026-05-17
**Version**: 1.0.0
**Source**: PC-096（CLI exit code 混淆程式錯誤與業務拒絕）
