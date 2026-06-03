# CC Release Impact Review — 狀態記錄

> 本檔由 `cc-release-impact-review` skill 維護。Step 1 讀此檔取得 last-reviewed 作去重依據；Step 5 評估完成後更新。

## last-reviewed

**2.1.161**

（下次觸發時，只評估 2.1.161 之後的新版本）

## 評估歷史

| 版本區間 | 評估 ticket | 主要結論 |
|---------|------------|---------|
| 2.1.161 | 0.19.1-W1-008 | 22 項中無影響 9 / 不適用 4 / 需評估 6 / 有幫助 3。建 ANA 評估三項與既有痛點共振的平台修復：#15 worktree 背景 session 編輯修復（關聯 ARCH-015/PC-114）、#18 完成 subagent 卡 running 修復（關聯 PM 狀態歸因 PC-104）、#4 並行 Bash 失敗隔離（關聯並行派發設計）。#14 mcp secret 遮蔽自動受益；#1/#13 OTEL 低優先 |
| 2.1.157 | 0.19.0-W4-028 | 採用 worktree 解鎖清理 SOP + EnterWorktree mid-session 補註；OTEL tool_parameters 可選；agent 欄位不適用；plugin 三項不採用 |
| 2.1.154 / 2.1.156 / 2.1.158 / 2.1.159 | 0.19.0-W4-029 | 建 release-note skill（本 skill）；AUQ 規則對齊（交用戶決策）；workflow 納入派發評估；MCP env 補記；2.1.156/158/159 無影響或不適用 |
| 2.1.160 | （已決策無需建 ticket） | 27 項中 23 項 bug fix/不適用。2 項低價值採用項用戶決議跳過：Item 2（acceptEdits 寫 .npmrc/.pre-commit-config 前提示）—6 種觸發檔當前皆不存在，背景代理人新建時才有互動風險；Item 3（bash grep 滿足 read-before-edit）—框架已偏好 Grep 工具，邊際效益。取證確認：FAST_MODE_OVERRIDE env 未引用、框架未依賴 CC workflow 觸發詞、Item 24 SIGTERM 修復不解決 W1-048.10.1.4 代理人 premature-exit |
