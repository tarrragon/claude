# PC-096: CLI exit code 混淆「程式錯誤」與「業務拒絕」

---

## 分類資訊

| 項目 | 值 |
|------|------|
| 編號 | PC-096 |
| 類別 | process-compliance |
| 風險等級 | 中（影響 shell pipeline 自動化判讀，PM/Hook 無法區分「該重試」與「該停手」） |
| 首發時間 | 2026-04-19（W10-017.1 Phase 1 多視角審查 thyme 視角揭露） |
| 姊妹模式 | PC-005（CLI 失敗歸因假設）、PC-015（error prompt 靜默繞過） |

---

## 症狀

CLI 命令的退出碼設計只用 `exit 0` / `exit 1` 兩值，導致以下兩類本質不同的「非成功狀態」被擠進同一個 exit 1：

1. **程式錯誤**（internal error）：例外、檔案讀不到、依賴模組崩潰——應通知人類介入
2. **業務拒絕**（business reject / NO-GO）：邏輯正常運作、依規則回答「不可放行」——應由呼叫方依拒絕原因處理

呼叫方（PM / Hook / shell pipeline）無法只用 `$?` 區分兩者，必須再 parse stdout/stderr 才能決策，違反 Unix exit code 應為「機器可讀決策訊號」的設計初衷。

---

## 實際案例

### 案例 1（W10-017.1 handoff-ready 命令規格，2026-04-19）

**任務**：設計 `ticket track handoff-ready` 命令輸出規格

**錯誤的 exit code 規劃**（lavender Phase 1 初稿）：

| 情境 | exit code | 問題 |
|------|-----------|------|
| Go（可 handoff） | 0 | OK |
| No-Go（有阻擋項） | 1 | 業務拒絕 |
| 程式異常（讀 ticket 失敗） | 1 | 與 No-Go 同碼 |

**thyme 視角揭露**：

> handoff-ready 的 exit 1 同時涵蓋「業務拒絕（No-Go，正常）」與「程式錯誤（讀檔失敗，異常）」。Hook/CI 拿到 exit 1 無法決定要 retry、abort 還是顯示 No-Go 訊息給 PM。

**修正後的三值 exit code 設計**：

| 情境 | exit code | 語意 |
|------|-----------|------|
| Go | 0 | 業務通過 |
| Internal error | 1 | 程式錯誤，需人類/上游修復 |
| No-Go | 2 | 業務拒絕，呼叫方依阻擋項決策 |

對齊 Unix 慣例：`grep` 用 0=found / 1=not found / 2=error；`diff` 用 0=same / 1=diff / 2=error。

---

## 根本原因

### 真根因

1. **「成功 vs 失敗」二分思維**：設計者預設 CLI 只有「成功（0）」與「失敗（非 0）」兩種狀態，未顯式拆分「失敗」的兩個子類
2. **Unix 慣例知識斷層**：`grep` / `diff` / `test` 的 0/1/2 三值 exit code 慣例未被預設參考
3. **業務邏輯強勢蓋過機器介面設計**：規格文件聚焦「Go/No-Go 文案」，忽略「呼叫方如何只用 exit code 自動化決策」
4. **錯誤路徑與拒絕路徑共用 try/except 結構**：實作上「捕獲例外 → exit 1」與「業務判定不通過 → exit 1」自然合流

### 為什麼容易發生

- 多數 CLI 教學範例只示範 0/1 二值
- 「shell pipeline 自動化」場景在規格階段較少被想像，直到 Hook/CI 串接時才暴露
- 業務拒絕用 stderr 文字提示「已足夠告知人類」，掩蓋了「機器無法區分」的問題
- 設計者多半是 PM/Phase 1 設計者，本身用人眼看輸出，未試想自動化呼叫場景

---

## 常見陷阱模式

| 陷阱表述 | 為何仍是混淆 |
|---------|------------|
| 「No-Go 也是失敗，exit 1 合理」 | 「業務拒絕」是命令完成正常工作後的結論，不是命令執行失敗 |
| 「stderr 已寫明原因，呼叫方 parse 就好」 | exit code 是機器決策第一訊號，要求 parse stderr 違反介面契約 |
| 「Hook 可以再讀 stdout 判斷」 | 多一層 parse 等於多一個失敗點；exit code 設計就是為了避免 parse |
| 「shell `||` 可處理」 | `||` 無法區分 1 與 2，仍會把錯誤誤判為業務拒絕 |
| 「之後再補不影響當下」 | exit code 改值是 breaking change，所有呼叫方需同步修改 |

---

## 防護措施

| 層級 | 措施 | 狀態 |
|------|------|------|
| 流程 | CLI 命令規格定義時，必須列出「程式錯誤 / 業務拒絕 / 業務通過」三類 exit code | 行為準則（本 PC 後立） |
| 流程 | Phase 1 設計 review 必檢「exit code 是否區分 internal error 與 business reject」 | 行為準則 |
| 慣例 | 預設採用 Unix 三值慣例：0=GO/SUCCESS、1=INTERNAL_ERROR、2=BUSINESS_REJECT/NO-GO | 行為準則 |
| 文件 | 命令文件必含 exit code 表格（情境 → exit code → 呼叫方建議處理） | 行為準則 |

---

## 檢查清單（CLI 命令規格 Phase 1 設計時）

- [ ] 是否列出所有非成功狀態？是否區分「程式錯誤」與「業務拒絕」？
- [ ] exit code 表格是否涵蓋所有情境，且每個 code 的語意唯一？
- [ ] 程式內 except 區塊與業務判定區塊是否使用不同 exit code？
- [ ] 文件是否說明「呼叫方收到此 exit code 應如何處理」？
- [ ] 是否有對應 Unix 慣例（grep / diff / test）？若不一致是否有正當理由？

---

## 教訓

1. **exit code 是機器介面契約**：設計時要想像「Hook/CI/shell pipeline 如何用 `$?` 自動化決策」，不是只給人看
2. **「失敗」需拆分為「異常」與「拒絕」**：兩者在語意、處理方式、責任歸屬上完全不同
3. **Unix 三值慣例值得預設套用**：`grep` 的 0/1/2 已是 40 年成熟設計，無需重新發明
4. **規格 review 要納入「呼叫方視角」**：不只是「這個輸出對人類清楚嗎」，還要問「這個 exit code 對機器清楚嗎」

---

## 相關文件

- `docs/work-logs/v0/v0.18/v0.18.0/tickets/0.18.0-W10-017.1.md` — 案例 1 來源（Phase 1 多視角審查 thyme 視角第 1 條發現）
- `.claude/error-patterns/process-compliance/PC-005-cli-failure-assumption-attribution.md` — 姊妹模式（CLI 失敗歸因假設）
- `.claude/error-patterns/process-compliance/PC-015-error-prompt-silent-bypass.md` — 姊妹模式（錯誤提示靜默繞過）

---

**Last Updated**: 2026-04-19
**Version**: 1.0.0
**Source**: W10-017.1 Phase 1 多視角審查 thyme-python-developer 視角第 1 條結構性發現
