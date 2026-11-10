#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
Session Start Sync Conflict Residue Hook

SessionStart 時檢查 sync-pull 留下的未處理衝突殘留，以 additionalContext 告知模型：
- .claude/.sync-conflicts/ 內的對照副本（前次 pull 的衝突尚未處理或未清理）
- 同步範圍內的正式檔仍含三方合併衝突標記

無殘留時不輸出任何內容。

Why：衝突殘留原本只在 pull 執行當下的輸出可見；操作者忽略那段輸出，或受影響的是
另一個 session 時無從得知。衝突標記落在 hooks/ 或 lib/ 時，hook 可能語法損毀而
靜默失效（tarrragon/claude#54）。

受眾：模型。走 additionalContext（emit_hook_output），exit 0；exit 0 加 stderr
對模型不可見，不作為提醒管道。

判準：兩項掃描都匯入 lib/sync_conflict_residue（與 sync-claude-pull.py 共用同一
函式，不另寫一份）。hook-logs 等非同步範圍的檔案含標記字樣時不列出。

失敗模式：SessionStart 不阻擋。未預期例外由 run_hook_safely 寫入日誌檔與 stderr，
exit 1，session 照常啟動；lib 匯入失敗時 stderr 提示並 exit 0。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))  # .claude/       (lib.*)
try:
    from lib import (
        emit_hook_output,
        read_json_from_stdin,
        run_hook_safely,
        setup_hook_logging,
    )
    # .claude/ 掃描屬主 repo 全域狀態：用 CLAUDE_PROJECT_DIR 導向的 git_utils 版本
    from lib.git_utils import get_project_root
    from lib.sync_conflict_residue import (
        SYNC_CONFLICTS_DIR,
        detect_conflict_residue,
        scan_conflict_marker_residue,
    )
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)

HOOK_NAME = "session-start-sync-conflict-residue"
EXIT_SUCCESS = 0
# 單一類別列出的檔名上限，超過以「另有 N 個」收尾，避免淹沒 session context
MAX_LISTED = 20


def _format_list(items: list[str]) -> list[str]:
    lines = [f"  - {item}" for item in items[:MAX_LISTED]]
    if len(items) > MAX_LISTED:
        lines.append(f"  - （另有 {len(items) - MAX_LISTED} 個未列出）")
    return lines


def build_message(conflict_copies: list[str], marker_hits: list[str]) -> str:
    """組出給模型的提醒；兩類皆空時回空字串。"""
    if not conflict_copies and not marker_hits:
        return ""
    lines = ["[Sync Conflict Residue] sync-pull 留有未處理的衝突殘留："]
    if marker_hits:
        lines.append(
            f"同步範圍內 {len(marker_hits)} 個檔案仍含衝突標記（hook 或 lib 檔含標記時可能無法執行）："
        )
        lines.extend(_format_list(marker_hits))
    if conflict_copies:
        lines.append(
            f".claude/{SYNC_CONFLICTS_DIR}/ 有 {len(conflict_copies)} 個對照副本未清理："
        )
        lines.extend(_format_list(conflict_copies))
    lines.append(
        "處理方式見 .claude/commands/sync-pull.md〈pull 後檢查清單〉步驟 2、3、5。"
    )
    return "\n".join(lines)


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    claude_dir = Path(get_project_root()) / ".claude"

    conflict_copies = detect_conflict_residue(claude_dir)
    marker_hits = scan_conflict_marker_residue(claude_dir)
    logger.info(
        "conflict copies=%d, marker hits=%d", len(conflict_copies), len(marker_hits)
    )

    message = build_message(conflict_copies, marker_hits)
    if message:
        emit_hook_output("SessionStart", message, input_data=input_data)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
