#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Dispatch Record Hook - PreToolUse (Agent) [DEPRECATED, 保留檔案僅供歷史查詢]

DEPRECATED：本 hook 已停用，不再註冊於 settings.json 的 PreToolUse(Agent)
matcher 下。派發記錄職責已完整遷移至 active-dispatch-tracker-hook.py
（PostToolUse:Agent）。

背景（幽靈派發記錄修復票）：
  PreToolUse(Agent) matcher 下所有 hook 皆會執行、deny 為彙總結果，本 hook
  的寫入無法感知同批次是否已被其他 PreToolUse hook（如 PC-019）拒絕——被
  阻擋的派發仍會留下 agent_id=None 的幽靈記錄，因無對應 agent 啟動，
  SubagentStop 永不觸發、記錄永不清除，污染 bare-commit-guard 的並行判定。

  比照 who.current 綁定遷移票的同一先例（該票已把身份綁定遷至
  PostToolUse），本次把 dispatch-active.json 記錄本身也遷過去。PostToolUse
  只在 Agent 工具實際執行（未被任何 PreToolUse hook deny）後才觸發，天然
  具備「派發已成功」語意，被阻擋的派發不再留下任何記錄。

  保留本檔案（不刪除）是為了讓歷史 commit / error-pattern 對本檔路徑的
  引用仍可解析；本檔不再被 settings.json 引用，執行也是純粹的 no-op。

來源:
  - PC-050 — PM 在代理人仍在工作時誤判完成
  - who.current 綁定遷移票（issue 47 殘留缺口修復）
  - 幽靈派發記錄修復票（本檔停用，記錄職責遷至 active-dispatch-tracker-hook.py）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely

HOOK_NAME = "dispatch-record-hook"
EXIT_SUCCESS = 0


def main() -> int:
    """DEPRECATED：no-op。記錄職責已遷至 active-dispatch-tracker-hook.py。"""
    logger = setup_hook_logging(HOOK_NAME)
    logger.debug(
        "dispatch-record-hook 已停用（記錄職責遷至 active-dispatch-tracker-hook.py），no-op"
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
