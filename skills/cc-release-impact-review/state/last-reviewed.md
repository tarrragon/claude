# CC Release Impact Review — 狀態記錄

> 本檔由 `cc-release-impact-review` skill 維護。Step 1 讀此檔取得 last-reviewed 作去重依據；Step 5 評估完成後更新。

## last-reviewed

**2.1.183**

（下次觸發時，只評估 2.1.183 之後的新版本）

## 評估歷史

| 版本區間 | 評估 ticket | 主要結論 |
|---------|------------|---------|
| 2.1.164–2.1.172 | 1.0.0-W1-056 | 2.1.164/2.1.171 不存在於 CHANGELOG（跳號）；2.1.165/167/168 僅「Bug fixes」無細項。2.1.172 共 30 項：需評估 1 / 無影響 20 / 不適用 9，唯一高價值張力項 #1 嵌套 sub-agent（最深 5 層）vs 框架單層派發假設，建 ANA W1-056 深入。缺口採用候選 4 項（2.1.166 fallbackModel、2.1.169 --safe-mode + disableBundledSkills、2.1.170 Fable 5 模型策略）依 2.1.160 前例交用戶決策，結果記於 W1-056 Problem Analysis |
| 2.1.173–2.1.183 | 1.0.0-W10-001, 1.0.0-W10-002 | 102 項中無影響 49 / 不適用 30 / 對框架有幫助 17（自動受益）/ 需評估 6。兩項高價值候選建 ANA：W10-001 Tool(param:value) 權限語法派發控管、W10-002 Hook if condition 路徑修復張力項審查。其餘 4 項中價值需評估（subagent 5-level、nested .claude/、MCP disallowedTools）暫交 ANA 內部追蹤 |
| 2.1.162 / 2.1.163 | 0.19.1-W1-043 | 44 項中無影響 30 / 不適用 8 / 需評估 5 / 有幫助 1。唯一高價值採用項 2.1.163 #4（Stop/SubagentStop hook 可回傳 additionalContext 給 Claude 回饋且不算 hook error），觸及框架 5 Stop + 2 SubagentStop hook。建 ANA 統籌：子 ANA 0.19.1-W1-044（#4 逐 hook 適用性 + 風險 + 含 #1 版本釘選）、DOC 0.19.1-W1-045（#9 $TMPDIR/PC-157 驗證）。#12 顯性豁免（平台自動受益，PC-104）。2.1.162 全為 claude agents dashboard UX/截斷修復，採用項 0 |
| 2.1.161 | 0.19.1-W1-008 | 22 項中無影響 9 / 不適用 4 / 需評估 6 / 有幫助 3。建 ANA 評估三項與既有痛點共振的平台修復：#15 worktree 背景 session 編輯修復（關聯 ARCH-015/PC-114）、#18 完成 subagent 卡 running 修復（關聯 PM 狀態歸因 PC-104）、#4 並行 Bash 失敗隔離（關聯並行派發設計）。#14 mcp secret 遮蔽自動受益；#1/#13 OTEL 低優先 |
| 2.1.157 | 0.19.0-W4-028 | 採用 worktree 解鎖清理 SOP + EnterWorktree mid-session 補註；OTEL tool_parameters 可選；agent 欄位不適用；plugin 三項不採用 |
| 2.1.154 / 2.1.156 / 2.1.158 / 2.1.159 | 0.19.0-W4-029 | 建 release-note skill（本 skill）；AUQ 規則對齊（交用戶決策）；workflow 納入派發評估；MCP env 補記；2.1.156/158/159 無影響或不適用 |
| 2.1.160 | （已決策無需建 ticket） | 27 項中 23 項 bug fix/不適用。2 項低價值採用項用戶決議跳過：Item 2（acceptEdits 寫 .npmrc/.pre-commit-config 前提示）—6 種觸發檔當前皆不存在，背景代理人新建時才有互動風險；Item 3（bash grep 滿足 read-before-edit）—框架已偏好 Grep 工具，邊際效益。取證確認：FAST_MODE_OVERRIDE env 未引用、框架未依賴 CC workflow 觸發詞、Item 24 SIGTERM 修復不解決 W1-048.10.1.4 代理人 premature-exit |
