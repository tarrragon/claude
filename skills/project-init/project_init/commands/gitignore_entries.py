"""gitignore-entries 指令 — 逐行印出專案 .gitignore 的必要條目.

條目與 SessionStart gitignore 檢查同源，供安裝步驟直接追加到 .gitignore。
"""

import sys
from pathlib import Path

from project_init.lib.onboard_checker import collect_required_gitignore_entries


def run_gitignore_entries(project_root: Path) -> int:
    """印出必要條目到 stdout；條目不完整或無法取得時回非 0.

    Returns:
        0 = 條目完整；1 = manifest 載入失敗（不印清單）或 lock 項無法判定（印 manifest 條目）。
    """
    collected = collect_required_gitignore_entries(project_root)
    if collected is None:
        sys.stderr.write(
            "[project-init] 無法取得 .gitignore 必要條目：sync_exclude_manifest 載入失敗"
            "（舊版框架？），不印出不完整的清單；請先更新 .claude 框架\n"
        )
        return 1
    entries, lock_determined = collected
    for entry in entries:
        print(entry)
    if not lock_determined:
        sys.stderr.write(
            "[project-init] 票庫 lock 項無法判定（ticket_lock_gitignore 缺失或過舊）；"
            "上列條目不含票庫 lock 項（{票庫}/**/*.md.lock），請更新 .claude 框架後重跑\n"
        )
        return 1
    return 0
