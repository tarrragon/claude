# IMP-077: 測試 helper 設計反模式（local fork 變死碼 + 同名異介面命名衝突）

## 基本資訊

- **Pattern ID**: IMP-077
- **分類**: 實作 bug（implementation）
- **來源版本**: v0.19.0
- **發現日期**: 2026-05-25
- **風險等級**: 低（功能正常但維護性退化）
- **影響範圍**: 任何專案的 `tests/helpers/` 共用測試 helper 與 test-file local helper 並存場景

---

## 問題描述

本 pattern 涵蓋兩種子模式，都是「測試 helper 設計時對使用情境的演化沒做明示」造成的維護性退化。

### 子模式 A：共用 helper 被測試端 local fork 後變死碼

**症狀**：某測試發現共用 helper 不適用（例如 `tests/helpers/test-data-generator.js` 的 `generateBooksWithProgress` 在特定場景產生 flaky），測試端複製/重寫一份 local helper（例如 `buildScenarioBooks` 內聯於測試檔），共用 helper 仍保留但無人引用。

**可觀察訊號**：

```bash
# helper 仍存在
$ grep -rn "function generateBooksWithProgress" tests/helpers/
tests/helpers/test-data-generator.js:385:  generateBooksWithProgress(...)

# 但無人呼叫
$ grep -rn "generateBooksWithProgress" tests/ src/ --include="*.js" | grep -v "test-data-generator.js"
# (僅 backup 檔案，無實際 consumer)
```

**Consequence**：未來維護者可能誤引共用 helper 重蹈舊 bug；helper 演化分裂為「保留但無人用」與「local fork 但無共享」兩條獨立路徑。

### 子模式 B：同名異介面的測試 helper

**症狀**：多個測試檔各自實作同名 helper（例如 `createMockFsAdapter`），但介面契約不同（一個吃 `string[]` 只支援 `fileExists`，另一個吃 `Map<string,string>` 支援 `readFile/readdir/stat`）。命名相同造成讀者誤以為可共用。

**可觀察訊號**：

```bash
$ grep -rn "function createMockFsAdapter\|const createMockFsAdapter" tests/
tests/unit/scripts/build-version-check.test.js:38:  const createMockFsAdapter = (files) => ...   # Map 介面
tests/unit/scripts/validate-manifest.test.js:29:  const createMockFsAdapter = (existingFiles) => ...  # string[] 介面
```

**Consequence**：第三個 scripts 測試需重新實作 helper；讀者切換測試檔時 cognitive load 上升（同名不同義）；難以重構為共用 utility（介面不相容）。

---

## 根因

**設計者層**：測試 helper 演化時，缺乏「使用情境變更觸發 helper 重新設計」的機制。情境變更包含：
- 新測試發現原 helper 不適用 → 預設行為應為「重新設計 helper 介面」而非「local fork」
- 新測試需求只是原 helper 子集 → 預設行為應為「複用且只用所需介面」而非「新建同名 helper」

**框架層**：缺乏自動化偵測機制：
- 共用 helper 在 N 個版本後仍無 consumer → 標 `@deprecated` 或移除
- 跨檔案出現同名 helper 但 signature 不同 → linting 提醒

---

## 防護措施

### 設計階段

| 情境 | 正確做法 | 反模式 |
|------|---------|--------|
| 共用 helper 在新測試不適用 | 重新設計 helper 介面（接受 strategy/options 參數）+ migrate 既有 consumer | 測試端 local fork helper |
| 新測試 helper 需求是現有 helper 子集 | 用既有 helper（即使有用不到的能力） | 新建同名 helper 簡化介面 |
| 真的需要兩個不同 helper | 命名差異化（`createMinimalFsAdapter` vs `createFullFsAdapter`） | 同名異介面 |

### Code review 檢查

- [ ] 新增測試 helper 前，grep 同名 helper 是否已存在
- [ ] 共用 helper 修改後，grep consumer 數量；若為 0 → 標 `@deprecated`
- [ ] PR 描述若含「本測試新增 local helper」→ 追問為何不用共用 helper、是否值得重新設計共用 helper

### 自動化（建議）

- ESLint rule：偵測 `tests/` 下同名 const/function 但 signature 不同（cross-file scope）
- 死碼掃描：定期 grep `tests/helpers/` 下函式的 consumer 數量，標 0 consumer 為候選 deprecation

---

## 案例

### 案例 1：W1-079（generateBooksWithProgress 死碼）

- **背景**：W1-075 修復 cross-device-sync-workflow.test.js flaky，採方向 C 重設計 mock data。原本使用 `tests/helpers/test-data-generator.js:385` 的 `generateBooksWithProgress`（含 `randomInt` 微擾 + 最後一本補差，1000-seed sweep 顯示 5.1% flaky 機率）。
- **修復**：在測試檔內聯 `buildScenarioBooks`（46 行確定性建構器），未動共用 helper。
- **後果**：共用 helper 變死碼且 1000-seed sweep 證明的 flaky 風險仍存在，未來新測試引用會重蹈覆轍。
- **追蹤**：0.19.0-W1-079（標 `@deprecated` + 評估 `buildScenarioBooks` 抽出共用）

### 案例 2：W1-080（createMockFsAdapter 同名異介面）

- **背景**：W1-074 為 `scripts/build.js` 加版號 sanity check，測試需要 mock fs adapter 支援 `readFile/readdir/stat`，新建 `createMockFsAdapter(files: Map)`。但既有 `validate-manifest.test.js` 已有 `createMockFsAdapter(existingFiles: string[])` 只支援 `fileExists`。
- **後果**：兩個 helper 同名異介面共存，第三個 scripts 測試需重新實作。
- **追蹤**：0.19.0-W1-080（抽 `tests/unit/scripts/script-test-helpers.js` 提供 `createMinimalFsAdapter` 與 `createFullFsAdapter` 兩個命名明確工廠）

---

## 抽象層級分析（必填）

| 欄位 | 內容 |
|------|------|
| 症狀層級 | 實作層（共用 helper 變死碼 / 同名異介面 helper 跨測試檔共存） |
| 根因層級 | 協作層（跨 PR / 跨作者缺乏 helper 演化觸發重新設計的機制；無命名一致性約束讓同名 helper 累積介面分歧） |
| 跨層路徑 | 實作層（症狀：dead code + 命名衝突）→ 協作層（根因：機制缺失，向上 1 層） |
| 防護層級 | 協作層：code review checklist（新增 local helper 前 grep 同名、共用 helper 修改後 grep consumer）；工具層：ESLint cross-file 同名異 signature 偵測 + 死碼掃描（建議項），落地至 `tests/helpers/` code review 流程 |
| 跨層警示 | 禁止提升至認知層（非個人疏忽）；root cause 是缺乏機制約束的結構性演化問題，非任何一位維護者的失誤；禁止縮減至純工具層（ESLint / 靜態分析只是輔助偵測，無法替代協作層設計原則） |

---

## 相關 Pattern

- IMP-064: Local re-import mock trap（函式體 local re-import 建 local binding 遮蔽 module-level）— 同屬「測試端 local fork」家族
- IMP-067: Windows git mode loss — 與本 pattern 無直接關係，僅同為 implementation 類

---

## 後續行動

- [ ] W1-079 落地時驗證子模式 A 修復路徑（標 deprecated + 評估抽出）
- [ ] W1-080 落地時驗證子模式 B 修復路徑（命名差異化 + 共用工廠）
- [ ] 若再有第三案例（同 session pattern）→ 升級為方法論層（於 methodologies/ 新增對應方法論）

---

**Last Updated**: 2026-05-25
**Source**: 0.19.0-W1-075（子模式 A） + 0.19.0-W1-074（子模式 B），均由 parallel-evaluation 多視角審查發現（code-explorer 視角 TD-1 + TD-2）
