# project-init 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.2.1（2026-11-10）— hook 註冊衛生（tarrragon/claude#53）：`lib/hook_verifier.check_hook_completeness` 在 `settings.json` 不存在或無法解析時改判 `completeness_ok=False`，並以新欄位 `failure_reason` 寫明原因，onboard 輸出同步顯示。原本缺 `settings.json` 的環境 hook 全數未載入，檢查卻報通過。測試 fixture 的 `settings.json` 改寫到 `.claude/settings.json`。

**Version**: 1.2.0（2026-10-20）— 〈常見使用情境〉新增「建立或接手專案：確認執行方式」：專案以工具管理語言或工具鏈版本時，先以版本查詢確認實際執行寫法，再寫入 CLAUDE.md §1「執行方式」列。起因：代理人未經釘選工具直接呼叫 PATH 上的指令，測試、分析與生成檔落在全域版本，差異被提交進主幹（用戶要求列為框架注意事項）。`CLAUDE-template.md` §1 同步新增「執行方式」列與常見工具鏈的識別檔提示；案例見 IMP-GPD-010。

**Version**: 1.1.0 - 新增後續流程銜接說明
**Last Updated**: 2026-04-01
