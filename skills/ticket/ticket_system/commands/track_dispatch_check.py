"""ticket track dispatch-check 命令（0.18.0-W10-017.2）。

取代 PC-050 `cat .claude/dispatch-active.json` 片段，提供 CLI 化的活躍派發判定：
- exit 0: 無活躍派發（檔案不存在 / dispatches=[]，視同已清空）
- exit 1: 有活躍派發（列出每筆 agent_description / ticket_id / dispatched_at）
- exit 2: IO 或 JSON 格式錯誤（stderr + 保守 NO-GO 供 Hook 程式化判定）

語意等價依據：
- PC-050 派發後清點 / 收到完成通知兩處均為讀檔 + 判斷 dispatches 陣列空/非空
- 新 CLI 多加：格式化輸出 + exit code，不改變判定規則
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ticket_system.lib.paths import get_project_root

_DISPATCH_ACTIVE_RELPATH = Path(".claude/dispatch-active.json")


def _format_entry(entry: dict) -> str:
    desc = entry.get("agent_description", "(unknown)")
    tid = entry.get("ticket_id") or "(no ticket)"
    ts = entry.get("dispatched_at", "(no timestamp)")
    return f"  - {desc} | ticket: {tid} | {ts}"


def execute_dispatch_check(args: argparse.Namespace) -> int:
    """執行 dispatch-check 命令。

    Returns:
        0: 無活躍派發；1: 有活躍派發；2: IO/格式錯誤。
    """

    dispatch_file = get_project_root() / _DISPATCH_ACTIVE_RELPATH

    if not dispatch_file.exists():
        print("[PASS] 無活躍派發，可繼續")
        return 0

    try:
        raw = dispatch_file.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, PermissionError) as e:
        sys.stderr.write(f"[FAIL] dispatch-active.json 讀取失敗: {e}\n")
        return 2
    except json.JSONDecodeError as e:
        sys.stderr.write(f"[FAIL] dispatch-active.json JSON 格式錯誤: {e}\n")
        return 2

    if not isinstance(data, dict):
        sys.stderr.write("[FAIL] dispatch-active.json root 結構不是 dict\n")
        return 2

    dispatches = data.get("dispatches", [])
    if not isinstance(dispatches, list):
        sys.stderr.write("[FAIL] dispatch-active.json dispatches 欄位不是 list\n")
        return 2

    if not dispatches:
        print("[PASS] 無活躍派發，可繼續")
        return 0

    print(f"[WARN] 有 {len(dispatches)} 個活躍派發：")
    for entry in dispatches:
        if isinstance(entry, dict):
            print(_format_entry(entry))
        else:
            print(f"  - (malformed entry: {entry!r})")
    return 1


def register_dispatch_check(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """註冊 dispatch-check 子命令。"""
    p = subparsers.add_parser(
        "dispatch-check",
        help="檢查 .claude/dispatch-active.json 活躍派發（0=無/1=有/2=IO錯誤）",
    )
    return p
