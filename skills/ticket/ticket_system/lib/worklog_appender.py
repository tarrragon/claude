"""
Worklog 進度行自動追加模組

在 Ticket 完成時，自動追加一行進度記錄到 main worklog。

併發安全（multi-PM 協調層 Phase 4）：main worklog 是多 session 共用的
tracked 檔案，`complete` / `batch-complete` 兩呼叫端的 read-modify-write
序列若無鎖保護，雙 session 同時 complete 不同 ticket 時會發生 lost
update（後寫者以自己讀到的舊內容覆寫檔案，先寫者的進度行消失；已有
真實案例 commit a6d1e8dd 為此問題的實例）。編輯段改用
`ticket_system.lib.file_lock.file_lock` 包圍（與 `lifecycle.py` 保護
ticket md load-modify-save 序列同一鎖模式，見該模組 docstring），寫入
後在鎖持有期間內重讀驗證自身行確實落地，缺行時 stderr 告警而非靜默
（PC-092「操作後主動驗證而非被動信任已成功」原則的落地）。
"""

import re
import sys
from datetime import date
from pathlib import Path

from .constants import WORK_LOGS_DIR
from .file_lock import file_lock
from .paths import get_project_root

# main worklog 檔名格式
MAIN_WORKLOG_FILENAME_TEMPLATE = "v{version}-main.md"

# 日期標題的正則（### YYYY-MM-DD 開頭）
DATE_HEADING_PATTERN = re.compile(r"^### \d{4}-\d{2}-\d{2}")

# 區段結束標記（下一個 ### 或 --- 或 ## ）
SECTION_END_PATTERN = re.compile(r"^(### |---|## )")


def _build_worklog_path(version: str) -> Path:
    """
    根據版本號構建 main worklog 路徑

    Args:
        version: 版本號，例如 "0.31.1"

    Returns:
        Path: worklog 檔案路徑
    """
    bare_version = version.lstrip("v")
    parts = bare_version.split(".")
    major = parts[0]
    minor = f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else bare_version

    root = get_project_root()
    filename = MAIN_WORKLOG_FILENAME_TEMPLATE.format(version=bare_version)

    return root / WORK_LOGS_DIR / f"v{major}" / f"v{minor}" / f"v{bare_version}" / filename


def _find_last_date_section_end(lines: list[str]) -> int | None:
    """
    找到最後一個日期標題區段的末尾位置（插入點）

    搜尋最後一個 '### YYYY-MM-DD' 標題，然後找該區段的最後一行
    （下一個 ###、---、## 之前，或檔案尾部的非空行之後）

    Args:
        lines: 檔案內容的行列表

    Returns:
        插入行的索引（在此索引之前插入），或 None 表示找不到
    """
    last_heading_idx = None
    for i, line in enumerate(lines):
        if DATE_HEADING_PATTERN.match(line):
            last_heading_idx = i

    if last_heading_idx is None:
        return None

    # 從標題之後開始，找區段結束位置
    for i in range(last_heading_idx + 1, len(lines)):
        if SECTION_END_PATTERN.match(lines[i]):
            # 在區段結束標記之前插入，跳過前面的空行
            insert_at = i
            while insert_at > last_heading_idx + 1 and lines[insert_at - 1].strip() == "":
                insert_at -= 1
            return insert_at

    # 沒有後續區段，插入到檔案末尾（最後一個非空行之後）
    insert_at = len(lines)
    while insert_at > last_heading_idx + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    return insert_at


def append_worklog_progress(version: str, ticket_id: str, title: str) -> None:
    """
    在 main worklog 的最後一個日期區段末尾追加進度行

    格式：- {YYYY-MM-DD}: {ticket_id} 完成 -- {title}

    失敗時輸出 WARNING 但不拋出異常，不阻擋 complete 流程。

    整段 read-modify-write（含冪等性檢查、插入點計算、寫入、寫後重讀
    驗證）皆在 `file_lock(worklog_path)` 持有期間內完成，確保雙 session
    對同一 worklog 的並行 complete 序列化執行，不發生 lost update。

    Args:
        version: 版本號，例如 "0.31.1"
        ticket_id: Ticket ID，例如 "0.31.1-W12-003"
        title: Ticket 標題
    """
    worklog_path = _build_worklog_path(version)

    if not worklog_path.exists():
        print(f"[WARNING] worklog 檔案不存在，跳過進度追加：{worklog_path}")
        return

    completion_marker = f"{ticket_id} 完成"

    try:
        with file_lock(worklog_path):
            content = worklog_path.read_text(encoding="utf-8")

            # 移除 keepends 用於搜尋，保留原始行用於寫回
            search_lines = content.splitlines()

            # 冪等性：若該 ticket 的完成行已存在則跳過，避免重複 append（W8-048）
            if any(completion_marker in line for line in search_lines):
                return

            insert_at = _find_last_date_section_end(search_lines)
            if insert_at is None:
                print("[WARNING] worklog 中找不到日期標題區段，跳過進度追加")
                return

            lines = content.splitlines(keepends=True)
            today = date.today().isoformat()
            progress_line = f"- {today}: {ticket_id} 完成 -- {title}\n"
            lines.insert(insert_at, progress_line)

            worklog_path.write_text("".join(lines), encoding="utf-8")

            # 寫後重讀驗證：自身行是否確實落地，缺行必須可見（規則 4）
            verify_content = worklog_path.read_text(encoding="utf-8")
            if completion_marker not in verify_content:
                sys.stderr.write(
                    f"[WARNING] worklog 進度行寫入後重讀驗證失敗，"
                    f"未在檔案中找到自身行：{ticket_id}（{worklog_path}）\n"
                )

    except Exception as e:
        print(f"[WARNING] worklog 進度追加失敗：{e}")
