---
id: PC-148
title: Hook 雙重註冊：settings.local.json python3 直呼繞過 shebang pep723 deps
category: process-compliance
severity: medium
source_case: 0.18.0-W11-030
created: 2026-05-16
---

# PC-148: Hook 雙重註冊 shebang bypass

## 症狀

派發 Agent / 觸發 Hook 事件時，UI 出現以下並存訊號：

- `.claude/hook-logs/<hook-name>/...log` 顯示 `INFO` 成功通過
- Claude Code UI 同時顯示 `PreToolUse:Agent hook error: Failed with non-blocking status code: Traceback (most recent call last): ModuleNotFoundError: No module named 'yaml'`（或其他模組）

兩條訊號矛盾——log 說成功、UI 說失敗。雖 non-blocking 不阻擋執行，但污染 UI 與用戶信任。

**Why**：訊號矛盾本身就是一條 PC 模式——它會誤導除錯方向。**Consequence**：後人接手時可能誤判 hook 邏輯有 bug 而改 hook 程式碼或 lib，忽略真因在「設定檔層級的重複註冊」，產生無效或破壞性修復。**Action**：看到雙重訊號優先比對 `settings.json` vs `settings.local.json` 對同事件同 matcher 的註冊重複狀況，再決定是否動 hook 程式碼。

## 觸發條件

以下三條件同時成立：

1. **同一 hook 在 `.claude/settings.json` 與 `.claude/settings.local.json` 都被註冊**
2. **兩處註冊形式不同**：
   - `settings.json` 用 `$CLAUDE_PROJECT_DIR/.claude/hooks/foo-hook.py`（依 shebang 執行，hook 必有 `#!/usr/bin/env -S uv run --quiet --script` + pep723 deps）
   - `settings.local.json` 用 `python3 $CLAUDE_PROJECT_DIR/.claude/hooks/foo-hook.py`（強制系統 python3，繞過 shebang 與 pep723）
3. **hook 程式碼或其 import 的 lib 模組頂層 import 非 stdlib 套件**（如 `pyyaml`），pep723 deps 已宣告

## 根因

**核心原則**：Claude Code runtime 對同一事件同一 matcher 的多處註冊採「逐一執行」語意——不做去重、不以後者覆寫前者、不挑單一最佳路徑。任何寫入 `settings.json` 或 `settings.local.json` 的 hook entry 都會被依序觸發，因此兩處註冊的執行模式差異會同時暴露。

兩條執行路徑對照：

| 來源 | 執行方式 | pep723 deps | 結果 |
|------|---------|-------------|------|
| settings.json | shebang `uv run --script` | 生效 | hook 正常執行，寫 INFO log |
| settings.local.json | `python3 ...` 直呼 | **繞過** | top-level `import yaml` 觸發 ModuleNotFoundError，吐 stderr traceback |

「hook log 顯示成功」與「stderr 吐 traceback」並存是雙重註冊的指紋。

## 與相鄰 PC 模式區分

| 模式 | 觸發 | 本案區別 |
|------|------|---------|
| PC-124 (subagent pytest vs hook subprocess env) | uv ephemeral env transitive deps 不裝 | 本案 deps 已宣告，問題在「執行路徑繞過 pep723」 |
| PC-135 (lib refactor caller sync) | caller hook 漏宣告新 lib 引入的 deps | 本案三個 caller (agent-dispatch-validation / layer-boundary-validator / commit-msg-layer2-marker-check) 都已宣告 pyyaml，問題在第二處註冊形式 |

本案為**全新模式**：deps 完整、caller 同步、ephemeral env 也正常，但設定檔層級的重複註冊用了「強制 python3」形式打破單一執行路徑假設。

## 防護措施

四層防護分工：規則層定義禁區、Hook 層自動偵測、文件層提供正向範例、自檢層保留人工 fallback。任一層獨用都會留破口，四層疊加才能在 LLM 撰寫設定時穩定攔截。

| 層級 | 動作 |
|------|------|
| 規則層 | 規範同一 hook 不得在 `settings.json` 與 `settings.local.json` 同事件同 matcher 同時註冊。**正確 local override 做法**：在 `settings.local.json` 對應 block 完整覆寫並明示移除或停用 base entry，禁止「兩處並存讓 runtime 自行決議」的依賴 |
| Hook 層 | 新增 `settings-duplicate-hook-registration-check-hook.py` 比對兩檔同事件同 matcher 的命令前綴，重複時啟動 warn |
| 文件層 | `.claude/references/hook-architect-technical-reference.md` 補「hook 註冊統一以 `$CLAUDE_PROJECT_DIR/.claude/hooks/foo-hook.py`（依 shebang）」章節，明示 `python3 ...` 直呼形式不可作為註冊入口 |
| 自檢層 | session 啟動 hook 健康檢查補「PreToolUse Agent matcher 註冊數 > 預期」訊號偵測 |

## 修正動作

修復順序設計為「先確保 base 註冊正確 → 再移除冗餘 → 雙路徑驗證」，避免移除冗餘後 base 缺漏導致 hook 完全失效。

1. 確認 `settings.json` 該 hook 註冊形式正確（shebang 路徑）
2. 從 `settings.local.json` 對應 event/matcher block 移除重複條目
3. 跑 smoke test 派發任意 agent，預期 UI 無 traceback、hook log 仍有 INFO 紀錄
4. shebang 路徑直接 exec hook（`echo '{}' | .claude/hooks/foo-hook.py`），預期：無 stderr traceback、exit code = 0

## 自我檢查清單

**適用時機**：派發 agent 或觸發任意 hook event 後，UI 出現 traceback 但對應 hook log 顯示 INFO 時對照本清單。

- [ ] 同一 hook 是否在 settings.json + settings.local.json 都註冊？
- [ ] 兩處註冊形式是否一致（都走 shebang）？
- [ ] settings.local.json 是否有 `python3` 或其他語言直接呼叫 hook 的字串？
- [ ] hook log 顯示成功時，UI 是否仍出現 traceback？

## 案例

- 0.18.0-W11-030 ANA 發現本模式（basil-hook-architect 調查）
- 0.18.0-W11-030.1 修復 `.claude/settings.local.json:199-209`，commit 0208d13d
