---
id: PC-170
title: 第三方 Claude Code skill vendoring 至框架的四個陷阱
category: process-compliance
severity: medium
status: active
created: 2026-06-03
---

# PC-170：第三方 Claude Code skill vendoring 至框架的四個陷阱

## 症狀

用戶要求「把這個 skill 加入專案」，PM 若直接 `npx <skill> install` 或盲目複製檔案，會在四處踩雷：commit 被 lint-staged 擋下、授權 attribution 遺失、第三方資產意外傳播到所有專案、以及把重型工具誤判為輕量 skill。

**核心識別訊號**：

| 訊號 | 說明 |
|------|------|
| 加入後 `git commit` 報 ESLint 錯誤，違規來自第三方 `.mjs` | lint-staged 對所有 staged JS 跑 `eslint --max-warnings=0`，第三方碼必報錯 |
| skill 目錄無 `LICENSE` / `NOTICE` | Apache/MIT 要求 redistribution 保留 attribution，遺失即違反授權 |
| 第三方 skill 出現在其他不相關專案的 skills 清單 | `.claude/skills/` 不在 sync 排除清單，加入即傳播共用框架 repo |
| skill 表面描述「設計指引」但實際 1.9MB / 數十個腳本 | 表面描述系統性低估實際規模與性質 |

## 根因

### 1. 表面描述低估實際規模

skill 的 README / npm description 常以「設計指引」「工具」一詞帶過，實際可能含 live server、detector 引擎、附帶 agent。本案 impeccable 描述為「design skill」，實為 1.9MB / 83 檔 / 54 個 `.mjs` 腳本的 web-app live 編輯系統，且 dev-server 導向，對 Chrome Extension MV3 契合度低。未先審查即假設輕量。

### 2. 第三方 .mjs 與 lint-staged 衝突

專案 husky lint-staged 對 `*.{js,mjs,cjs,...}` 跑 `eslint --max-warnings=0`。第三方碼風格不符專案規範，staged 時必報錯擋 commit。PM 易誤以為是自己引入的違規而嘗試修改第三方碼。

### 3. 授權合規被忽略

vendoring 等同 redistribution。Apache 2.0 / MIT 要求保留 LICENSE 與 NOTICE。直接只複製 skill 目錄而不含授權檔，違反授權條款；且授權檔不隨 skill 目錄走時，sync 傳播後其他專案更無從追溯來源。

### 4. sync 範圍未確認

本專案 `.claude/` 透過 `sync-claude-push.py` 推送至共用框架 repo（影響所有專案）。`.claude/skills/` 不在 `EXCLUDE_PATTERNS`，故加入即框架共用。用戶若只想本專案用，PM 未主動確認 scope 會造成非預期的框架膨脹。

## 案例

**情境**：0.19.1-W1-006，用戶要求加入 `pbakaus/impeccable`（Apache 2.0 設計 skill）。

PM 經 `git clone --depth 1` 審查發現實為 1.9MB / 83 檔 / 54 腳本的重型 live 工具，向用戶揭露實況（體積 / 腳本數 / web-app 導向契合度 / 與既有 `style-guardian` 重疊 / 英文含 emoji 與 language-constraints 張力 / sync 傳播範圍），用戶確認完整安裝 + 框架共用。複製時保留 LICENSE + NOTICE，commit 以 `--no-verify` 繞過 lint-staged 第三方碼報錯（理由寫進 commit message）。建 ADJ ticket 追蹤（PC-053）。

## 防護措施

| 步驟 | 動作 |
|------|------|
| 1 審查 | `git clone --depth 1` 到 /tmp，查體積、腳本數、真實性質，**勿信表面描述** |
| 2 揭露 | 向用戶揭露實況（體積 / 腳本 / 契合度 / sync 範圍 / 與既有 skill 重疊 / language-constraints 衝突）讓其決定 scope（框架共用 vs 本專案） |
| 3 授權 | 複製 LICENSE + NOTICE 至 skill 目錄（Apache/MIT attribution 合規） |
| 4 commit | 含第三方 `.mjs` 時用 `git commit --no-verify`，理由寫進 message（`.claude/` 為 ESLint dotfile 預設忽略、CI lint 僅掃 `src/ tests/`，合規 CLAUDE.md 第三方豁免） |
| 5 追蹤 | 依 PC-053 建 ADJ ticket，body 記錄已知考量供後人 |
| 6 sync | 僅本專案用時加入 `sync-claude-push.py` EXCLUDE_PATTERNS；框架共用則不動 |

**Why**：第三方 skill 注入有隱性成本（體積、context、語言規範衝突、sync 傳播），表面描述常低估規模。

**Consequence**：跳過審查直接安裝會導致 commit 卡關、授權違規、非預期框架膨脹，且重型工具誤裝後 context 與維護成本長期累積。

**Action**：依上方六步防護；關聯 memory `feedback_vendoring_third_party_cc_skill`（跨對話記憶）。

## 關聯

- Ticket：0.19.1-W1-006
- Memory：`feedback_vendoring_third_party_cc_skill`
- 相關規則：PC-053（skills 修改須 ticket）、`.claude/references/plugin-management.md`（注入成本評估）、CLAUDE.md（`--no-verify` 第三方豁免）
