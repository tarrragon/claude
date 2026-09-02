# chrome-extension-mcp-debug 版本紀錄

新到舊。版號規則與兩個住址（本檔與 `SKILL.md` frontmatter 的 `metadata.version`）見專案的 skill 同步規範。

**Version**: 1.1.0 — 修正 chrome-devtools MCP 工具名漂移（getExtensions → list_extensions、getConsoleMessages → list_console_messages、getNetworkRequests → list_network_requests、takeScreenshot → take_screenshot、snapshot → take_snapshot）；Workflow D-sw 的 SW log 取得流程改寫為 list_pages + select_page + list_console_messages（原 getExtensionLogs 已不存在於現行工具集）
**Last Updated**: 2026-07-02
**Source**: chrome-devtools-mcp POC + 專案設定落地 + SKILL 化使用流程 + 工具名漂移修正
