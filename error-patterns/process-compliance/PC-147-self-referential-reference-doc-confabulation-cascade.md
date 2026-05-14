---
id: PC-147
title: Reference doc 自寫自引導致 confabulation cascade
category: process-compliance
severity: high
source_case: 0.18.0-W14-031
created: 2026-05-14
---

# PC-147: Reference doc 自寫自引導致 confabulation cascade

## 症狀

PM 或代理人在單一 commit 內完成「寫 reference doc → 引用該 reference 作為 ticket 依據 → 機械性遷移大範圍配置 → acceptance 全綠」的鏈，事後才發現 reference doc 本身的技術陳述是錯誤的（typically 對外部 schema / API 的誤解），導致整個 commit 的產出無效或破壞性。

## 觸發條件

以下三個條件**同時成立**時，confabulation cascade 風險極高：

1. **新建或改寫 reference doc** 描述外部系統（Claude Code、Chrome API、第三方 schema）的能力或格式
2. **同 commit 或同 ticket 週期內**，依該 reference 作為「新功能來源」實施遷移、重構或機械性套用
3. **acceptance 設計**只測「腳本/模組本身行為」，未測「外部系統驗證新配置是否合法」（例如未跑 `/doctor`、未起新 session、未 WebFetch 官方 schema）

## 根因

LLM 的訓練分布與工具邊界互動產生三層放大：

| 層級 | 機制 |
|------|------|
| L1 訓練分布 | release notes / 文章片段可能讓 LLM 對新 API 形成「自信但錯誤」的內推 |
| L2 寫作慣性 | 寫成 reference doc 的範例會自然填滿格式（如 JSON），缺欄位的範例**看起來和對的一樣可信** |
| L3 自我引用閉環 | 同 commit 內 ticket why 引用該 reference → reference 是「自己剛寫的」但被當作外部權威 → 沒有外部反駁訊號 → 一路綠燈 |

當 acceptance 設計沒有「外部系統驗證點」時，整條鏈會在純內部測試中完整通過，缺陷只能等下一次外部交互（`/doctor`、新 session、用戶報錯）才被發現。

## 案例

**0.18.0-W14-031（2026-05-14）**：

- reference `.claude/references/hook-architect-technical-reference.md` 加入 `args` exec form 範例，但範例**漏寫必填的 `command` 欄位**
- ticket why 引用該 reference 作為「v2.1.139+ 推薦形式」依據
- 123 條 hook entry 機械性遷移為 `args`-only
- acceptance 4 條全綠：
  - settings.json 完成轉換 → grep 通過
  - npm run test:hooks 2213 passed → 測 hook 腳本不測 settings schema
  - 抽樣 3 個 hook → `echo '{}' | hook.py` 走 Python 直送不走 Claude Code spawn
  - reference 標註遷移完成 → 改文件
- 完成時間 17:06:05，距離 started_at 17:01:39 僅 4 分 26 秒
- 同日下午 `/doctor` 報告 123 個 `command: Expected string, but received undefined`，事後 WebFetch 官方文件確認 `args` 從不取代 `command`

## 防護

### 規則層（已固化）

**規則 A**：reference doc 描述外部系統 schema / API / 格式時，必須在文件開頭或修改段落附**官方文件來源 URL**，且修改 reference 前必須 WebFetch 該 URL 對齊。

**規則 B**：「reference doc 變更 → 依該 reference 執行遷移」不可在同一 commit 完成。最小間隔：
- reference 變更先單獨 commit
- 後續引用該 reference 的 ticket 必須在獨立 commit（且至少跨一次 session，讓變更有外部審視機會）

**規則 C**：涉及 settings.json / manifest.json / Chrome Extension 等「外部驗證器存在的配置檔」變更，acceptance 必須包含至少一條外部驗證：
- Claude Code settings → `claude doctor` 0 warnings
- Chrome Extension → `chrome://extensions/` 重新載入 0 errors
- package.json → `npm install --dry-run` 0 conflicts

**規則 D**：機械性遷移超過 N=20 條同類項目時，acceptance 必須含「**官方文件 URL 引用**」與「**抽樣項目對照官方範例**」兩條，禁止只依賴 npm test 全綠。

### Hook 層（待設計）

| Hook | 觸發 | 行為 |
|------|------|------|
| commit-time reference-self-reference-detection | 偵測同 commit 內 reference doc 修改 + ticket md 引用該 reference 路徑 | warning：建議拆 commit |
| settings.json schema 變更 PreToolUse | 偵測 settings.json 中 hooks.*.hooks.*.command/args 結構變更 | 提示執行 `claude doctor` |

### 認知層（自查清單）

寫或修改 reference doc 前自問：

- [ ] 我是否 WebFetch 過官方文件？URL 是？
- [ ] 範例是否與官方範例**逐欄位對照**過？
- [ ] 如果範例缺某個欄位，我是否能引用官方說「該欄位 optional」的明文？

執行引用 reference doc 的 ticket 前自問：

- [ ] 該 reference 變更是不是同一 commit 內寫的？若是，**先 commit reference、跨 session 再執行 ticket**
- [ ] acceptance 是否有至少一條會被「外部 validator」拒絕的檢查？

## 相關

- PC-079: backtick command substitution in CLI args（被 W14-031 誤引為遷移理由）
- PC-088: LLM 工具選擇偏誤（單步敏感總步驟盲）—同源於 LLM 對外部系統認知的內推偏誤
- PC-098: PM 寫規則本能引用 ticket ID（self-reference 反模式同源）

---

**Last Updated**: 2026-05-14 | **Source**: 0.18.0-W14-031 4 分鐘完成 123 條錯誤遷移 + 同日 `/doctor` 報 schema 違規後 revert
