---
id: PC-148
title: Hook 雙重註冊：settings.local.json python3 直呼繞過 shebang pep723 deps
category: process-compliance
severity: medium
created: 2026-05-16
---

# PC-148: Hook 雙重註冊 shebang bypass

## 症狀

派發 Agent / 觸發 Hook 事件時，UI 出現以下並存訊號：

- `.claude/hook-logs/<hook-name>/...log` 顯示 `INFO` 成功通過
- Claude Code UI 同時顯示 `PreToolUse:Agent hook error: Failed with non-blocking status code: Traceback (most recent call last): ModuleNotFoundError: No module named 'yaml'`（或其他模組）

兩條訊號矛盾——log 說成功、UI 說失敗。雖 non-blocking 不阻擋執行，但污染 UI 與用戶信任。

**Why**：訊號矛盾本身就是一條 PC 模式——它會誤導除錯方向。**Consequence**：後人接手時可能誤判 hook 邏輯有 bug 而改 hook 程式碼或 lib，忽略真因在「設定檔層級的重複註冊」，產生無效或破壞性修復。**Action**：看到雙重訊號優先比對 `settings.json` vs `settings.local.json` 對同事件同 matcher 的註冊重複狀況，再決定是否動 hook 程式碼。

## 適用範圍註記（2026-11-20 重驗）

本節只更新適用範圍與現況結論；以下觸發條件、根因、案例保留事發當時（2026-05-16）的敘述，不改寫。

**註冊形式現況**（依 `.claude/settings.json` 與 `.claude/hooks/hook-dispatch-registry.json` 實測）：

| 註冊位置 | 現行形式 | 與本 PC 描述的差異 |
|---------|---------|------------------|
| `settings.json` 的 hook 註冊 | 帶 PEP 723 區塊的 hook 一律為 `uv run --quiet $CLAUDE_PROJECT_DIR/<path>`；檔頭無 PEP 723 區塊、shebang 為 `python3` 的少數 hook 為 `python3 $CLAUDE_PROJECT_DIR/<path>`；裸路徑形式（`$CLAUDE_PROJECT_DIR/.claude/hooks/foo-hook.py`，依 shebang 執行）已無任何一筆 | 觸發條件 2 所列「`settings.json` 用裸路徑、依 shebang 執行」的形式已不存在 |
| `settings.local.json` | 本 repo 無此檔 | 雙重註冊的前提（觸發條件 1）在本 repo 不成立 |
| Bash 事件的 PreToolUse／PostToolUse／PostToolUseFailure hook | 不直接寫在 `settings.json`，改列於 `hook-dispatch-registry.json`，由 `hook-dispatcher.py` 單一程序分派執行 | 本 PC 撰寫時無此層 |

**由根因推導的現況結論**：

- 根因的核心原則（runtime 對同事件同 matcher 的多處註冊逐一執行、不去重）未變，仍成立。consumer 若在 `settings.local.json` 另行註冊同一 hook，本 PC 的症狀仍會出現；防護措施表的規則層（hook 一律只寫入 `settings.json`）仍適用。
- 「執行路徑繞過 PEP 723 依賴宣告」這個機制，在現行架構有一個同型的位置：`hook-dispatcher.py` 以自己的直譯器環境執行 registry 內的 hook（in-process 用 `runpy`，退回路徑用 `sys.executable` 子程序），不讀各 hook 自己的 PEP 723 區塊。重驗時 registry 內各 hook 宣告的依賴只有 `pyyaml`，與分派器自身宣告相同，故目前不觸發；日後若有 hook 宣告分派器未宣告的依賴並列入 registry，會以本 PC 的形態（hook 單獨執行正常、經分派器執行時 `ModuleNotFoundError`）重現。
- 修正動作第 4 步的「顯式解譯器前綴」判準仍有效；其中的 hook 支數為撰寫當時的計數。

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
| 規則層 | **框架 hook 單一註冊來源原則**：所有 hook 註冊一律寫入 `settings.json`，`settings.local.json` 完全不放任何 hook（僅 permissions / env / mcp / outputStyle）。**Why（U2 實證）**：CC hooks 跨作用域**累積合併（非覆寫）**，且**無細粒度 null / false / 停用機制**（僅 `disableAllHooks` 全局開關）——故 local 無法「覆寫或停用」base entry，所謂「local override 框架 hook」不存在，舊版本書於此處的「local 完整覆寫並停用 base entry」做法經 U2 證偽，已移除。**Consequence**：兩處並存只會被 runtime 逐一執行（症狀如本 PC），且 `settings.local.json` 是 sync 排除檔，上游 relocate 無法觸及 → 幽靈 hook（見 [[ARCH-TUNL-001]]）。**Action**：enforcement 置於 **sync / 安裝端**（真實變異源頭，非手動 Edit 介面，見 [[PC-V1-012]]）拒絕框架 hook 留在 local；既有 SessionStart `find_local_hook_registrations` / `find_phantom_registrations` 為偵測安全網（WARNING） |
| Hook 層 | 新增 `settings-duplicate-hook-registration-check-hook.py` 比對兩檔同事件同 matcher 的命令前綴，重複時啟動 warn |
| 文件層 | `.claude/references/hook-architect-technical-reference.md` 補「hook 註冊統一以 `$CLAUDE_PROJECT_DIR/.claude/hooks/foo-hook.py`（依 shebang）」章節，明示 `python3 ...` 直呼形式不可作為註冊入口 |
| 自檢層 | session 啟動 hook 健康檢查補「PreToolUse Agent matcher 註冊數 > 預期」訊號偵測 |

## 修正動作

修復順序設計為「先確保 base 註冊正確 → 再移除冗餘 → 雙路徑驗證」，避免移除冗餘後 base 缺漏導致 hook 完全失效。

1. 確認 `settings.json` 該 hook 註冊形式正確（shebang 路徑）
2. 從 `settings.local.json` 對應 event/matcher block 移除重複條目
3. 跑 smoke test 派發任意 agent，預期 UI 無 traceback、hook log 仍有 INFO 紀錄
4. 顯式解譯器前綴呼叫 hook：檔頭含 `# /// script`（PEP 723，本專案 115 支 hook 中 111 支屬此類）用 `echo '{}' | uv run --quiet --script .claude/hooks/foo-hook.py`；純 python 無此區塊才用 `echo '{}' | python3 .claude/hooks/foo-hook.py`（判準與 889 遷移的分類軸一致）。`foo-hook.py` 為佔位符，代入實際 hook 檔名前先 `head -3` 確認其 shebang 屬於哪一類。預期：無 stderr traceback、exit code = 0

## 自我檢查清單

**適用時機**：派發 agent 或觸發任意 hook event 後，UI 出現 traceback 但對應 hook log 顯示 INFO 時對照本清單。

- [ ] 同一 hook 是否在 settings.json + settings.local.json 都註冊？
- [ ] 兩處註冊形式是否一致（都走 shebang）？
- [ ] settings.local.json 是否有 `python3` 或其他語言直接呼叫 hook 的字串？
- [ ] hook log 顯示成功時，UI 是否仍出現 traceback？

## 案例

- 某次 ANA 發現本模式（basil-hook-architect 調查）
- 後續修復 `.claude/settings.local.json:199-209`，commit 0208d13d
