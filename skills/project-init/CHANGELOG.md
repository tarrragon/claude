# project-init 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.7.0（2026-11-18）— 新增子命令 `project-init gitignore-entries`：逐行印出專案 `.gitignore` 必要條目，與 SessionStart gitignore 檢查同源（manifest 的 `required_gitignore_entries()` 加票庫 lock 項）。manifest 載入失敗（舊版框架）時不印清單、stderr 說明、非 0 結束；只缺 lock 模組時印出 manifest 條目、stderr 註明 lock 項無法判定、非 0 結束。`.claude/README.md` 安裝第 5 步改用 `uv run --project .claude/skills/project-init project-init gitignore-entries`，取代 `python3 -c` 匯入內部模組；同時拿掉「另外加上 `coverage/` 與 `docs/work-logs/**/*.md.lock`」的手動補充，因為子命令已包含這兩項。`onboard_checker` 新增 `collect_required_gitignore_entries()` 供子命令使用。
- 對齊版號住址：`pyproject.toml` 的 `version`（1.1.0）與 `project_init/__init__.py` 的 `__version__`（0.1.0）改為 1.7.0。

**Version**: 1.6.0（2026-11-18）— onboard 的 `.gitignore` 檢查新增報缺票庫 lock 項 `{票庫}/**/*.md.lock`（票庫路徑取自受檢專案的 ticket `WORK_LOGS_DIR`，預設 `docs/work-logs`；票庫在 `.claude/` 下、`.gitignore` 沒涵蓋時同樣報缺，因為必要規則清單沒有 `.claude/**/*.lock`，有 `.claude/**/*.lock` 才算涵蓋）。推導移到 `.claude/lib/ticket_lock_gitignore.py`，與 SessionStart gitignore 檢查共用，同一份 `.gitignore` 下兩邊缺項清單一致；涵蓋判定走 git check-ignore，git 無法判定時退回字面比對。受檢專案沒有該模組（舊版框架）時寫 stderr，報告本文另列「無法判定以下規則」並加一則待辦（新欄位 `GitignoreCheckInfo.undetermined_rules`、`undetermined_reason`）；無法判定不算缺漏，不影響 `all_required_complete`。

**Version**: 1.5.0（2026-11-18）— onboard 的 `.gitignore` 檢查另列可移除的舊規則：`sync-preserve.yaml`、`sync-skills.yaml` 改為進版控後，`.gitignore` 仍忽略它們會讓新 clone 讀不到宣告檔。判定取受檢專案 manifest 的 `retired_gitignore_lines()`（與 SessionStart 檢查同源），結果放在 `GitignoreCheckInfo.retired_rules`，報告與待辦各列一則；舊規則不算缺漏，不影響 `all_required_complete`。受檢專案的 manifest 沒有該函式（舊版框架）時不報。

**Version**: 1.4.0（2026-11-13）— onboard 的 `.gitignore` 必要規則改與 SessionStart 檢查同源：以檔案路徑載入受檢專案的 `.claude/lib/sync_exclude_manifest.py`，取 `required_gitignore_entries()` 為必要規則，涵蓋判定以 `gitignore_probe_paths()` 的代表路徑跑 git check-ignore（巢狀名稱探測根層、一層、二層），git 無法判定時退回字面比對。原本的手寫清單只有 8 項，缺 `settings.local.json`、`.sync-state.json` 等 local-only 名稱，照 onboard 補完 `.gitignore` 後首次 `git add .claude` 仍會夾帶本機設定。受檢專案沒有該函式（舊版框架）時寫 stderr 並退回原清單。根層 `__pycache__/` 改為 `.claude/**/__pycache__`、不再單獨要求 `htmlcov/`，與 SessionStart 檢查一致。
- 移除框架檔內的專案層級票號（規則 8 存量清理），改為自足敘述或佔位符；僅註解與 docstring，行為不變。

**Version**: 1.3.0（2026-11-12）— hook 註冊檢查改名為「註冊涵蓋率」（tarrragon/claude#53）：`lib/hook_verifier` 的 `HookCompletenessResult` 改為 `HookRegistrationCoverageResult`、`completeness_ok` 改為 `coverage_ok`、`check_hook_completeness` 改為 `check_hook_registration_coverage`，`project_init.lib` 匯出名同步，舊名不保留別名。onboard 區段標題由「Hook 完整性驗證」改為「Hook 註冊涵蓋率」，並加一行寫明只量是否已登記（settings.json + hook-dispatch-registry），不量觸發、事件、權限、依賴；`OnboardMessages.HOOK_COMPLETENESS_*` 常數改為 `HOOK_COVERAGE_*`。原名聲稱完整性，實際只量登記，與 2026-09-09 已改名的 `hook-registration-coverage-check` 對齊。同版另含：已登記的判定併入 `hook-dispatch-registry.json` 的成員，與 coverage check 採同一份來源；載入 `.claude/lib/hook_registry.py` 失敗時寫 stderr 並退回只比對 `settings.json`。

**Version**: 1.2.2（2026-11-11）— onboard 與檢查輸出的處置提示對齊 shim 化與框架現況：CLI 未安裝或過期時提示 `python3 .claude/scripts/install-skill-clis.py`（原為 `uv tool install`）；`settings.local.json` 待辦提示改指向 `.claude/templates/settings-local-template.json` 複製後調整；hook 未註冊提示改為回報 framework issue，已由其他管道執行者加入 `hook-exclude-list.json`（原為要求修改 `settings.json`）。`SKILL.md` 與 `references/remediation-guides.md` 同步。檢查邏輯不變。

**Version**: 1.2.1（2026-11-10）— hook 註冊衛生（tarrragon/claude#53）：`lib/hook_verifier.check_hook_completeness` 在 `settings.json` 不存在或無法解析時改判 `completeness_ok=False`，並以新欄位 `failure_reason` 寫明原因，onboard 輸出同步顯示。原本缺 `settings.json` 的環境 hook 全數未載入，檢查卻報通過。測試 fixture 的 `settings.json` 改寫到 `.claude/settings.json`。

**Version**: 1.2.0（2026-10-20）— 〈常見使用情境〉新增「建立或接手專案：確認執行方式」：專案以工具管理語言或工具鏈版本時，先以版本查詢確認實際執行寫法，再寫入 CLAUDE.md §1「執行方式」列。起因：代理人未經釘選工具直接呼叫 PATH 上的指令，測試、分析與生成檔落在全域版本，差異被提交進主幹（用戶要求列為框架注意事項）。`CLAUDE-template.md` §1 同步新增「執行方式」列與常見工具鏈的識別檔提示；案例見 IMP-GPD-010。

**Version**: 1.1.0 - 新增後續流程銜接說明
**Last Updated**: 2026-04-01
