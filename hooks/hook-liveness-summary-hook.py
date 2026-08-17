#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook Liveness 彙整

SessionStart 觸發，讀取上一個完成 session 的 liveness 索引
（.claude/hook-logs/_liveness/<session_id>.jsonl），比對 settings.json
註冊表，將「已載入 / 本 session 從未觸發 / 未涵蓋（無 liveness 探針）」
三類清單寫入自身日誌，供事後查證「hook 是否已載入」時直接查詢，不需
依賴對照組（另一持續寫入的 hook）或即時探針推論。

三類清單定義：
- 已載入：涵蓋範圍內（run_hook_safely 覆蓋）且該 session 有 liveness 紀錄
- 本 session 從未觸發：涵蓋範圍內但該 session 無 liveness 紀錄（可能是該
  session 未觸發對應事件，非必然異常）
- 未涵蓋（無 liveness 探針）：hook 檔案未呼叫 run_hook_safely（如 lib
  import 失敗時定義自訂 no-op stub 的降級路徑），本機制無法觀測

不比對「本 session」（觸發本 hook 的新 session）而比對「上一個完成 session」
的理由：SessionStart 是新 session 的第一個事件，此時新 session 自己的
liveness 檔案尚無實質資料（僅本 hook自身剛寫入的一筆），比對上一個完成
session 才能反映有意義的覆蓋率。
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.hook_logging import (
    setup_hook_logging,
    run_hook_safely,
    get_project_root,
    ENV_SESSION_ID,
    LIVENESS_SUBDIR,
)
from lib.hook_io import read_json_from_stdin

HOOK_NAME = "hook-liveness-summary"


def _registered_hook_names(settings: dict) -> set:
    """從 settings.json 擷取所有 .claude/hooks/*.py 的檔名（去副檔名）"""
    names = set()
    hooks_cfg = settings.get("hooks", {})
    for event_entries in hooks_cfg.values():
        if not isinstance(event_entries, list):
            continue
        for group in event_entries:
            if not isinstance(group, dict):
                continue
            for entry in group.get("hooks", []):
                if not isinstance(entry, dict):
                    continue
                command = entry.get("command", "")
                if "/.claude/hooks/" not in command or not command.endswith(".py"):
                    # 僅涵蓋 .claude/hooks/ 直屬檔案；skills/scripts 下的
                    # hook 有各自的 hook_name 慣例，不在本次彙整範圍
                    continue
                names.add(Path(command).stem)
    return names


def _covered_by_run_hook_safely(root: Path, hook_names: set) -> set:
    """回傳有呼叫 run_hook_safely 的 hook 名稱子集（有 liveness 探針）"""
    covered = set()
    hooks_dir = root / ".claude" / "hooks"
    for name in hook_names:
        candidate = hooks_dir / "{}.py".format(name)
        if not candidate.exists():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if "run_hook_safely" in text:
            covered.add(name)
    return covered


def _most_recent_completed_liveness_file(root: Path, exclude_session_id: str):
    """取得最近修改的 liveness 檔案，排除當前 session 自己的檔案"""
    liveness_dir = root / ".claude" / "hook-logs" / LIVENESS_SUBDIR
    if not liveness_dir.is_dir():
        return None
    candidates = [
        p for p in liveness_dir.glob("*.jsonl")
        if p.stem != exclude_session_id
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _invoked_hook_names(liveness_file: Path) -> set:
    """解析 liveness 索引檔，回傳出現過的 hook 名稱集合"""
    invoked = set()
    try:
        with open(liveness_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                hook = entry.get("hook")
                if hook:
                    invoked.add(hook)
    except OSError:
        pass
    return invoked


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    read_json_from_stdin(logger)  # SessionStart 常無 stdin，僅統一入口消費

    root = get_project_root()
    settings_path = root / ".claude" / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.info("讀取 settings.json 失敗，跳過本次彙整: {}".format(e))
        return 0

    registered = _registered_hook_names(settings)
    covered = _covered_by_run_hook_safely(root, registered)
    uncovered = registered - covered

    current_session_id = os.environ.get(ENV_SESSION_ID, "").strip()
    liveness_file = _most_recent_completed_liveness_file(root, current_session_id)
    if liveness_file is None:
        logger.info(
            "尚無可比對的 liveness 索引（首次啟用或前一 session 無任何 hook "
            "觸發），涵蓋 {} / 未涵蓋(無探針) {}".format(len(covered), len(uncovered))
        )
        if uncovered:
            logger.info("未涵蓋（無 liveness 探針）: {}".format(sorted(uncovered)))
        return 0

    invoked = _invoked_hook_names(liveness_file)
    loaded = covered & invoked
    never_triggered = covered - invoked

    logger.info(
        "Liveness 彙整（比對來源: {}）：已載入 {} / 涵蓋範圍 {} / "
        "未涵蓋(無探針) {}".format(
            liveness_file.name, len(loaded), len(covered), len(uncovered)
        )
    )
    if never_triggered:
        logger.info(
            "本 session 從未觸發（涵蓋範圍內，可能只是對應事件未發生）: {}".format(
                sorted(never_triggered)
            )
        )
    if uncovered:
        logger.info("未涵蓋（無 liveness 探針，需另評估）: {}".format(sorted(uncovered)))

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
