# project-init 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.4.0（2026-11-13）— onboard 的 `.gitignore` 必要規則改與 SessionStart 檢查同源：以檔案路徑載入受檢專案的 `.claude/lib/sync_exclude_manifest.py`，取 `required_gitignore_entries()` 為必要規則，涵蓋判定以 `gitignore_probe_paths()` 的代表路徑跑 git check-ignore（巢狀名稱探測根層、一層、二層），git 無法判定時退回字面比對。原本的手寫清單只有 8 項，缺 `settings.local.json`、`.sync-state.json` 等 local-only 名稱，照 onboard 補完 `.gitignore` 後首次 `git add .claude` 仍會夾帶本機設定。受檢專案沒有該函式（舊版框架）時寫 stderr 並退回原清單。根層 `__pycache__/` 改為 `.claude/**/__pycache__`、不再單獨要求 `htmlcov/`，與 SessionStart 檢查一致。
- 移除框架檔內的專案層級票號（規則 8 存量清理），改為自足敘述或佔位符；僅註解與 docstring，行為不變。

**Version**: 1.3.0（2026-11-12）— hook 註冊檢查改名為「註冊涵蓋率」（tarrragon/claude#53）：`lib/hook_verifier` 的 `HookCompletenessResult` 改為 `HookRegistrationCoverageResult`、`completeness_ok` 改為 `coverage_ok`、`check_hook_completeness` 改為 `check_hook_registration_coverage`，`project_init.lib` 匯出名同步，舊名不保留別名。onboard 區段標題由「Hook 完整性驗證」改為「Hook 註冊涵蓋率」，並加一行寫明只量是否已登記（settings.json + hook-dispatch-registry），不量觸發、事件、權限、依賴；`OnboardMessages.HOOK_COMPLETENESS_*` 常數改為 `HOOK_COVERAGE_*`。原名聲稱完整性，實際只量登記，與 2026-09-09 已改名的 `hook-registration-coverage-check` 對齊。同版另含：已登記的判定併入 `hook-dispatch-registry.json` 的成員，與 coverage check 採同一份來源；載入 `.claude/lib/hook_registry.py` 失敗時寫 stderr 並退回只比對 `settings.json`。

**Version**: 1.2.2（2026-11-11）— onboard 與檢查輸出的處置提示對齊 shim 化與框架現況：CLI 未安裝或過期時提示 `python3 .claude/scripts/install-skill-clis.py`（原為 `uv tool install`）；`settings.local.json` 待辦提示改指向 `.claude/templates/settings-local-template.json` 複製後調整；hook 未註冊提示改為回報 framework issue，已由其他管道執行者加入 `hook-exclude-list.json`（原為要求修改 `settings.json`）。`SKILL.md` 與 `references/remediation-guides.md` 同步。檢查邏輯不變。

**Version**: 1.2.1（2026-11-10）— hook 註冊衛生（tarrragon/claude#53）：`lib/hook_verifier.check_hook_completeness` 在 `settings.json` 不存在或無法解析時改判 `completeness_ok=False`，並以新欄位 `failure_reason` 寫明原因，onboard 輸出同步顯示。原本缺 `settings.json` 的環境 hook 全數未載入，檢查卻報通過。測試 fixture 的 `settings.json` 改寫到 `.claude/settings.json`。

**Version**: 1.2.0（2026-10-20）— 〈常見使用情境〉新增「建立或接手專案：確認執行方式」：專案以工具管理語言或工具鏈版本時，先以版本查詢確認實際執行寫法，再寫入 CLAUDE.md §1「執行方式」列。起因：代理人未經釘選工具直接呼叫 PATH 上的指令，測試、分析與生成檔落在全域版本，差異被提交進主幹（用戶要求列為框架注意事項）。`CLAUDE-template.md` §1 同步新增「執行方式」列與常見工具鏈的識別檔提示；案例見 IMP-GPD-010。

**Version**: 1.1.0 - 新增後續流程銜接說明
**Last Updated**: 2026-04-01
