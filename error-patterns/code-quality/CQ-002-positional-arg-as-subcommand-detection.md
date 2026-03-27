# CQ-002: Positional Argument 作為子命令偵測導致路由不一致

**發現日期**: 2026-03-07
**相關 Ticket**: 0.1.0-W6-001

## 症狀

- 新增子命令時，使用 positional argument 的值作為子命令判斷（如 `ticket_id == "gc"`）
- 現有子命令用 flag 路由（`--status`），新子命令用值路由（`ticket_id == "gc"`），行為不一致
- 若用戶 ticket ID 恰好為保留關鍵字，行為會被誤攔截

## 根因

快速整合 GC 命令時，沒有重構現有的 argparse 結構（新增嵌套 subparsers），而是選擇在 `execute()` 中用值判斷繞過。

## 解決方案

使用 argparse 的嵌套 subparsers 結構，確保同層級路由邏輯一致。

## 預防措施

1. 新增命令功能時，優先考慮使用 argparse subparsers 而非值判斷
2. 相同層級的路由邏輯應保持一致（都用 flag 或都用 subparser）
3. 保留字（`gc`, `status`, `help` 等）應列出清單並在文件中說明
