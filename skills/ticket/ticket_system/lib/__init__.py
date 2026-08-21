"""
Ticket System 共用工具庫（lib package）

本檔不再 re-export 任何符號。消費者一律直接匯入子模組
（例如 `from ticket_system.lib import ticket_loader` 或
`from ticket_system.lib.constants import TICKET_STATUS`）。

清空原本的 re-export 層，避免任何 `from lib import`
觸發整條 eager import 鏈（ticket_loader -> parser -> file_lock ->
filelock）。子模組清單請直接查看本目錄下的檔案。
"""
