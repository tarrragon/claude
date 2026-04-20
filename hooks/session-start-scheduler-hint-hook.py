#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Session Start Scheduler Hint Hook

SessionStart 事件觸發時，呼叫 `ticket track runqueue` 取得排程提示，
並作為 additionalContext 顯示於新 session 啟動訊息中。

邏輯：
1. 優先呼叫 `ticket track runqueue --context=resume --top 3`
   - 有待恢復 handoff → 用該輸出
2. 若 resume 無結果（輸出含「無可執行 Ticket」標記）→ fallback
   呼叫 `ticket track runqueue --format=list --top 1` 顯示下一個可執行任務
3. 若兩者皆無 → suppressOutput=True，不干擾 session

失敗模式：
- CLI 執行錯誤 / timeout / 不存在 → logger.error（stderr）+ 靜默
  （規則 4：失敗可見；但 SessionStart hook 不阻塞 session 啟動）

來源：W17-011.4 / W17-009 scheduler 缺口 D（motd/login info 類比）
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# 加入 hook_utils 路徑
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin  # noqa: E402

EXIT_SUCCESS = 0

# CLI 超時秒數（SessionStart 不可長等）
CLI_TIMEOUT_SECONDS = 8

# 判斷「無可執行 Ticket」的輸出特徵（與 ticket track runqueue 對齊）
EMPTY_MARKER = "無可執行 Ticket"


def _run_ticket_cli(args: list, logger) -> Optional[str]:
    """執行 `ticket track runqueue ...` 並回傳 stdout；失敗回 None。"""
    cmd = ["ticket", "track", "runqueue"] + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_SECONDS,
        )
        if proc.returncode != 0:
            logger.error(
                "ticket track runqueue 非零退出 (rc=%s): stderr=%s",
                proc.returncode, proc.stderr.strip()[:300],
            )
            return None
        return proc.stdout
    except subprocess.TimeoutExpired as e:
        logger.error("ticket track runqueue 逾時 (%ss): %s", CLI_TIMEOUT_SECONDS, e)
        return None
    except FileNotFoundError as e:
        logger.error("ticket CLI 未安裝或不在 PATH: %s", e)
        return None
    except Exception as e:  # noqa: BLE001 — session 啟動不可因任何例外阻塞
        logger.error("ticket track runqueue 執行錯誤: %s", e, exc_info=True)
        return None


def _has_content(output: Optional[str]) -> bool:
    """判斷 runqueue 輸出是否有實質內容（非空清單）。"""
    if not output or not output.strip():
        return False
    return EMPTY_MARKER not in output


def fetch_scheduler_context(logger) -> Optional[str]:
    """
    取得排程提示內容。

    流程：
    1. 試 resume（--context=resume --top 3）
    2. resume 空則 fallback next（--format=list --top 1）
    3. 皆空 → None
    """
    # Step 1: resume
    resume_out = _run_ticket_cli(["--context=resume", "--top", "3"], logger)
    if _has_content(resume_out):
        return resume_out.strip()

    # Step 2: fallback next
    next_out = _run_ticket_cli(["--format=list", "--top", "1"], logger)
    if _has_content(next_out):
        return next_out.strip()

    # Step 3: 皆無內容
    return None


def build_hook_output(scheduler_context: Optional[str]) -> Dict[str, Any]:
    """組裝 SessionStart hook 的 JSON 輸出。"""
    if not scheduler_context:
        return {"suppressOutput": True}

    message = (
        "## 排程提示（scheduler hint）\n\n"
        "```\n"
        f"{scheduler_context}\n"
        "```\n"
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": message,
        },
        "suppressOutput": False,
    }


def main() -> int:
    """主入口：讀 stdin（可忽略內容）→ 取 context → 輸出 JSON。"""
    logger = setup_hook_logging("session-start-scheduler-hint-hook")
    logger.info("scheduler hint hook 啟動")

    try:
        # SessionStart 可能無 stdin 或給簡短 JSON；不阻塞
        read_json_from_stdin(logger)
    except Exception as e:  # noqa: BLE001
        logger.warning("讀取 stdin 失敗（忽略）: %s", e)

    scheduler_context = fetch_scheduler_context(logger)
    output = build_hook_output(scheduler_context)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info("scheduler hint hook 完成（有內容=%s）", scheduler_context is not None)
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-start-scheduler-hint"))
