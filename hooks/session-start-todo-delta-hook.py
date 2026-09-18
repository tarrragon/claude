#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Session Start Todo Delta Hook

SessionStart 事件觸發時，讀取本地 todo pending 登記檔（見
`todo_pending_registry` 模組），有未處理項目時輸出提醒。**本 hook 不呼叫
`todo --json`、不發任何 gh API 呼叫**——「待辦與來源*」表格聚合的預設範圍
實測需十餘秒，而 SessionStart 已註冊數十支 hook，一支慢 hook 會改變整個
啟動序列的成本結構；本 hook 的全部成本是一次本地 JSON 檔案讀取。

推送的訊號模型（delta，非清單；ack-based，非 seen-based）與範圍裁決見
`todo_pending_registry` 模組 docstring；本 hook 只負責讀取與呈現，不參與
訊號的產生或消滅——訊號完全由 `section_comment.py` 的寫入端
（cmd_init／cmd_add／cmd_update）增量維護。

退化行為（狀態遺失或損毀）：`pending_entries()` 回傳 None 時，本 hook
**選擇全列沉默**而非全列重印。全列重印需要重建完整 baseline，即呼叫
`todo --json`，違反本 hook 的成本前提（見上段）；沉默的代價是遺失期間
新增的列不會被通報，直到下一次寫入端呼叫重新建立 pending 項目。這是
成本約束下的必然選擇，非任意偏好——若日後通道重裁允許 SessionStart 路徑
呼叫 `todo --json`，才有條件重新評估「全列重印」方向。

誤報定義：見 `todo_pending_registry` 模組 docstring「誤報定義」段——本
登記檔可能落後於 canonical 真實狀態（繞過本 CLI 的直接編輯不會被偵測），
這是已知限制，不是本 hook 的判定錯誤。

失敗語意：fail-open。登記檔讀取失敗、任何例外，一律靜默略過
（`suppressOutput: true`），僅寫入 hook-logs，不阻擋 session 啟動。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
)
from lib.hook_io import is_subagent_environment  # noqa: E402

EXIT_SUCCESS = 0

FRAMEWORK_ISSUE_SCRIPTS_DIR = ".claude/skills/framework-issue/scripts"

# 同 session-start-issue-check-hook.py：只在真正的新 session 開始執行，
# compact/clear 屬同一 session 內的 context 事件，非新 session。
SOURCES_TO_RUN = frozenset({"startup", "resume"})


def _suppressed_output() -> str:
    """無內容可回報時的標準 SessionStart JSON 輸出（不顯示於對話）。"""
    return json.dumps({"suppressOutput": True}, ensure_ascii=False)


def _load_pending_entries(project_root: Path, logger):
    """讀取 todo pending 登記檔，回傳項目清單；缺檔／損毀回傳 None（見
    檔頭「退化行為」說明，呼叫端應據此選擇全列沉默）。"""
    scripts_dir = project_root / FRAMEWORK_ISSUE_SCRIPTS_DIR
    sys.path.insert(0, str(scripts_dir))
    try:
        import todo_pending_registry  # noqa: PLC0415
    except ImportError as exc:
        logger.info("todo_pending_registry 模組載入失敗，退化為全列沉默: %s", exc)
        return None
    return todo_pending_registry.pending_entries(project_root=project_root)


def _build_context(entries: List[Dict]) -> str:
    """組裝 additionalContext 內容：逐項待處理列的摘要。"""
    lines = [
        "## Framework Issue todo 待處理新增列（session-start-todo-delta）",
        "",
        f"以下 {len(entries)} 列自上次處理後為新增（未讀取的「待裁票」列，"
        "ack-based：狀態改變或整列消失前持續通報）：",
        "",
    ]
    for entry in entries:
        type_suffix = f"｜型別={entry.get('type')}" if entry.get("type") else ""
        lines.append(
            f"- #{entry.get('issue')} [{entry.get('priority', '?')}]"
            f"[{entry.get('stage', '?')}] owner={entry.get('owner', '?')} "
            f"來源票={entry.get('source_ticket', '?')} "
            f"acceptance={entry.get('acceptance_count', '?')} "
            f"— {entry.get('task', '')}{type_suffix}"
        )
    return "\n".join(lines)


def main() -> int:
    logger = setup_hook_logging("session-start-todo-delta")
    input_data = read_json_from_stdin(logger) or {}

    if is_subagent_environment(input_data):
        logger.debug("subagent 環境，todo delta 推送非其職責，略過")
        print(_suppressed_output())
        return EXIT_SUCCESS

    source = input_data.get("source", "")
    if source not in SOURCES_TO_RUN:
        logger.debug("source=%s 非 startup/resume，略過", source)
        print(_suppressed_output())
        return EXIT_SUCCESS

    project_root = get_project_root()
    entries = _load_pending_entries(project_root, logger)

    if entries is None:
        logger.info("登記檔缺失或損毀，退化為全列沉默（不重建 baseline，避免呼叫 todo --json）")
        print(_suppressed_output())
        return EXIT_SUCCESS

    if not entries:
        logger.info("無待處理項目")
        print(_suppressed_output())
        return EXIT_SUCCESS

    logger.info("待處理項目 %d 筆", len(entries))
    print(json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": _build_context(entries),
            },
            "suppressOutput": False,
        },
        ensure_ascii=False,
    ))
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-start-todo-delta"))
