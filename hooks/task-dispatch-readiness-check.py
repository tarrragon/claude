#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.8"
# dependencies = ["pyyaml"]
# ///
"""
代理人派發前置檢查 Hook
PreToolUse Hook（Agent/Task 工具）：派發缺少 prompt 時擋下。

另在 prompt 引用 handoff 指向的票時輸出可見訊號（不影響放行）。

重構紀錄:
- 移除代理人分派對應比對：設定檔 known_agents 全數列在 agent_to_task_map 內、
  名單外代理人不算錯，比對永遠判定為正確，deny 分支實際走不到；連帶移除
  HOOK_MODE（strict/warning）與 agent-dispatch-warnings.jsonl 記錄。
- v0.31.0: 移除 check_task_requirements（已被 Ticket 檢查機制取代）
"""

import sys
from pathlib import Path

# 加入共用模組路徑
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))


from lib import setup_hook_logging, prompt_references_handoff_ticket, emit_handoff_recovery_signal, run_hook_safely
from lib.hook_io import read_hook_input, write_hook_output, create_pretooluse_output


def write_deny_or_exit2(output: dict, logger) -> None:
    """輸出 deny 決定；stdout 寫入失敗時以 exit 2 阻擋。

    不改用 emit_hook_output：其輸出為單行 JSON，本守衛既有輸出為 indent=2，
    改用會改變輸出位元組。故自行兜底：寫入失敗若沿用原行為會經
    run_hook_safely 回 exit 1（放行）。
    """
    try:
        write_hook_output(output)
    except Exception as exc:
        logger.critical(f"deny 輸出失敗，以 exit 2 阻擋: {exc}")
        try:
            sys.stderr.write(f"[deny 輸出失敗，以 exit 2 阻擋] {exc}\n")
        except Exception:
            # stderr 亦不可寫：無通道可回報，仍維持 exit 2 阻擋語意
            pass
        raise SystemExit(2)


def main() -> None:
    """主執行函式"""
    logger = setup_hook_logging("agent-dispatch-check")

    try:
        input_data = read_hook_input()
        if not input_data:
            logger.error("Invalid JSON input")
            sys.exit(0)
    except Exception as e:
        logger.error(f"讀取輸入失敗: {e}")
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    # 只處理 Task/Agent 工具（CC subagent 工具已由 Task 改名 Agent）
    if tool_name not in ("Agent", "Task"):
        sys.exit(0)

    prompt = tool_input.get("prompt", "")
    if not prompt:
        output = create_pretooluse_output("deny", "Task 工具缺少 prompt 參數")
        write_deny_or_exit2(output, logger)
        sys.exit(0)

    # Handoff 恢復：prompt 引用 handoff 指向的票時輸出可見訊號（不影響放行）
    if prompt_references_handoff_ticket(prompt, logger):
        emit_handoff_recovery_signal(prompt, logger)
        logger.info("檢測到 Handoff 恢復模式")

    logger.info("所有檢查通過")
    sys.exit(0)


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "agent-dispatch-check"))
