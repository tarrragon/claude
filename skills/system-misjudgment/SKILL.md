---
name: system-misjudgment
description: "以系統為索引的 AI 誤判檢查庫：記錄除錯、實機驗證時對系統行為的常見錯誤判讀、實際機制與可執行檢查方法。Use when: 除錯、實機驗證、觀測不到事件或 log、懷疑系統行為、否定結果（零事件、沒有 log、分支還在）要當證據前、誤判後要記錄。"
metadata:
  version: 1.0.3
---

# system-misjudgment：依「正在面對的系統」查已知誤判與檢查方法

除錯當下，讀者知道自己面對哪個系統，未必知道錯誤屬哪個類別。

error-patterns 依類別分目錄，查不到同一系統上的陷阱。本 skill 以系統為第一層索引。每個條目的核心是**可執行的檢查方法**。

## 用法

1. 從下表找到你正在面對的系統，開對應的 reference。
2. 在該檔找症狀與你看到的現象相符的條目，先照「檢查方法」跑命令，再依「判讀標準」下結論。
3. 條目的原因敘事不在本 skill：來源欄若有 error-pattern ID，用 `/error-pattern query <ID>` 查；若是機制敘述，該敘述已自足。
4. 找不到相符條目：照下方〈通則〉處理，事後依〈持續更新〉新增條目。

| 系統 | 檔案 | 現象關鍵字 |
|------|------|-----------|
| macOS FSEvents／fseventsd／檔案監看 | `references/macos-fsevents.md` | 監看零事件、刪監看根目錄、/private 路徑、驗證 PASS 但可能被他人寫入污染 |
| Dart VM service Logging／flutter run | `references/dart-vm-service-log.md` | 沒有 log、log 漏行、訊息被截斷、時間戳矛盾 |
| git index／worktree／工作區 | `references/git-index-worktree.md` | index.lock、`git status` 的「改動」、index 吸入他人變更、worktree 路徑 |
| 合併閘門與背景程序 | `references/merge-gate-background-process.md` | 分支還在、閘門像失敗、程序已結束的宣告、測試數下降、測試綠但行為未變 |
| 工具輸出與 AI 自身記錄 | `references/tool-output-and-records.md` | 輸出夾旁白、記憶中的 commit、工作區觀測當持久結論 |
| Riverpod provider 接線 | `references/riverpod-provider-wiring.md` | 測試綠但啟動報 provider 錯誤 |

## 通則

**否定結果（零事件、沒有 log、沒有輸出）在拿來當證據之前，先對環境與觀測工具各做一次正向對照。** 「沒收到」同時符合被測物壞、環境沒送、工具沒接到三種成因，單看這個結果分不出來。判讀順序：環境健康 → 觀測工具完整性 → 被測物。前一層沒過，後一層的否定結果一律不採計。

## 條目欄位

每個條目必含七欄，缺欄即不合格：

| 欄位 | 內容 |
|------|------|
| 症狀 | 讀者實際看到什麼 |
| 常見誤判 | AI 會把它讀成什麼 |
| 實際機制 | 一到兩句；細節只用 ID 引用 |
| 檢查方法 | 可直接貼上執行的命令 |
| 正向對照 | 證明檢查本身有效的對照（已知該有結果的輸入） |
| 判讀標準 | 什麼輸出算通過、什麼算失敗 |
| 來源 | error-pattern ID 或指名的實測依據 |

## 持續更新

三個觸發點都要問一次「這個誤判屬哪個系統，該系統檔有沒有對應條目」：有則補充或修正，沒有則新增，不屬任何現有系統則新增一個系統檔並登記到上表。

| 觸發點 | 時機 |
|--------|------|
| `error-pattern add` | 新 pattern 的症狀涉及某系統的行為判讀（`error-pattern` skill 的 add 流程步驟 9） |
| incident-responder 結論 | 結論的根因是「判讀者對系統行為想錯」 |
| 實機驗證出現誤判 | 驗證中的否定或異常結果，事後證明是環境或觀測工具造成 |

新增條目的步驟：(1) 寫入對應系統檔，七欄填齊，來源欄放 error-pattern ID，或自足的機制敘述；(2) 檢查方法已實際跑過一次，輸出貼在來源 pattern 或票面，不憑推論；(3) 修改本 skill 內容的票，同票升版號並寫 `CHANGELOG.md`；版號不動，發佈前才會發現本地與發佈庫版號相同而內容不同。

## 與相鄰 skill 的分工

| skill | 管什麼 | 與本 skill 的界線 |
|-------|--------|------------------|
| `evidence-driven-bugfix` | 除錯流程（重現、failing test、根因、最小修復） | 它管步驟順序；本 skill 管步驟中「讀系統輸出」那一環的陷阱 |
| `error-pattern` | 錯誤經驗的記錄與查詢（依類別） | 它存原因敘事；本 skill 依系統索引檢查方法，以 ID 引用 |
| `wrap-decision` | 決策偏誤（假選項、倉促結論） | 它管選擇怎麼做；本 skill 管觀測到的現象怎麼讀 |

## 範例

情境：實機驗證時 App 監看收到 0 筆事件。

1. 找系統：檔案監看，開 `references/macos-fsevents.md`。
2. 命中條目 FS-1，檢查方法：`ps -axo pcpu,comm | grep fseventsd` 取三次樣，任一次不低於 `WV_CPU_LIMIT`（預設 50）即為異常。
3. 正向對照：FS-1 的金絲雀命令必須收到即時事件。
4. 判讀：閘門紅 → 結論是「環境不可驗證」，不派修正批、不判 App 失敗。
