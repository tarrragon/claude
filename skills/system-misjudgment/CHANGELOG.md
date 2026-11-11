# system-misjudgment 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.3.0 — 新增系統檔 `references/python-os-path-platform.md`（Python os.path 的平台實作），首條 OSP-1：在 POSIX 主機上以反斜線字串模擬 Windows 路徑，`os.path` 仍是 posixpath，只驗證到字串層；檢查方法為以 `ntpath` 取代被測模組的 `os.path`；來源 `TEST-LLM-003`。SKILL.md 系統索引表同步加列
**Last Updated**: 2026-11-11

**Version**: 1.2.0 — `references/git-index-worktree.md` 新增 GW-5：隔離派發 worktree 的鎖記錄派發方 session 的 pid，被讀成代理人的 pid（只看 pid 分不出代理人執行中或已交回），檢查方法改看分支 tip 與 reflog 建立點及是否已併入 main；SKILL.md 系統索引表該列補「worktree 鎖的 pid」
**Last Updated**: 2026-11-10

**Version**: 1.1.0 — 新增系統檔 `references/flutter-test-binding.md`（Flutter 測試 binding 的幀與時鐘），首條 FTB-1：on-device 測試等待真實 I/O 時 `pumpAndSettle` 立即返回，finder 找不到元件被讀成元件改名；來源 `TEST-LLM-001`。SKILL.md 系統索引表同步加列
**Last Updated**: 2026-11-10

**Version**: 1.0.3 — `references/dart-vm-service-log.md` 移除對專案層實機驗證 skill 的腳本路徑的引用，改為「專案的實機驗證配方（如有）」通用指涉，並以輸入參數描述取代具名命令；至此全目錄無專案層引用
**Last Updated**: 2026-11-04

**Version**: 1.0.2 — 第二輪讀者探針與可攜性修正：MG-3 計數只計 Dart 測試檔（`'test/*.dart'`，排除 test/fixtures 的 md）；範例與 FS-1 統一以 `WV_CPU_LIMIT` 為門檻；FS-1 金絲雀改為內嵌命令；FS-2、FS-3 改為不綁專案的寫法，FS-3 來源欄改為「專案的實機驗證配方（如有）」通用指涉；移除對專案層 skill 的名稱與路徑引用（本 skill 會推 canonical）及分工表對應列。`references/dart-vm-service-log.md` 仍有專案層引用，不在本次範圍
**Last Updated**: 2026-11-04

**Version**: 1.0.1 — 讀者探針修正：移除本專案分域 error-pattern ID（來源欄改自足機制敘述）；bundle id 改 `<bundle-id>` 並寫取得方式；補 vm_log.mjs 可貼用命令與 ws-uri 取得；MG-3 改 `git grep -c <commit>`；MG-2 移除 TaskStop；FS-2 補計數命令；索引表補「測試綠但行為未變」；開頭說明句拆短
**Last Updated**: 2026-11-04

**Version**: 1.0.0 — 初版。以系統為第一層索引，六份系統檔（macOS FSEvents、Dart VM service log、git index 與 worktree、合併閘門與背景程序、工具輸出與 AI 自身記錄、Riverpod provider 接線）；條目七欄（症狀、常見誤判、實際機制、檢查方法、正向對照、判讀標準、來源）；持續更新機制三個觸發點（error-pattern add、incident-responder 結論、實機驗證誤判），error-pattern skill add 流程新增步驟 9 承接
**Last Updated**: 2026-11-04
