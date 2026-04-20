"""Ticket track agent-status 命令

TaskOutput 安全查詢指引 CLI（Stub / Guidance）

設計說明：
- TaskOutput 是 Claude Code runtime 提供的 deferred tool，只能從 PM agent context 呼叫，
  無法由外部 shell / CLI 直接觸發。因此本 CLI 為「指引輸出」性質：
  * 印出 Step 0.5 / 0.5-A 時 PM 應手動複製貼上的安全查詢範本
  * 提醒「只讀 <status> 標籤、禁讀 <output> body」（PC-050 模式 D）
  * 提醒派發時間 < 2 分鐘時的強制條款（PC-050 模式 E / PC-070）

未來若 CC runtime 提供 shell-accessible 狀態查詢通道（例如透過 socket 或 task
metadata 檔），可在本命令內加上實際查詢邏輯，維持 CLI 介面不變。

來源 Ticket: 0.18.0-W10-061（項目 4，降級為 guidance stub）。
相關 Ticket: 0.18.0-W10-059（ANA）。
"""
import argparse
from typing import Optional


AGENT_STATUS_TEMPLATE = """\
=== Agent Status Query Guidance (PC-050 模式 E / PC-070 防護) ===

TaskOutput 是 Claude Code deferred tool，只能由 PM agent context 呼叫。
請由 PM 主線程複製以下片段並執行：

  # Step 1：首次使用前載入 schema（本 session 已載入可跳過）
  ToolSearch(query="select:TaskOutput")

  # Step 2：查詢特定代理人 runtime 狀態
  TaskOutput(
    task_id="{agent_id}",
    block=False,
    timeout=3000
  )

只讀標籤規則：
  - 允許：<status>（running / completed / error）
  - 允許：<task_type>、<retrieval_status>
  - 禁止：<output> body（JSONL transcript，會污染 context；PC-050 模式 D）

status 值對應行動：
  running    -> 停止推論、等 completion notification
  completed  -> 開始驗收流程
  error      -> 走代理人失敗 SOP

派發時間閾值強制條款（PC-050 模式 E / PC-070）：
  派發 < 2 分鐘 + Hook 完成訊號 + git status 無變更
    -> 禁用 Hook 訊號作為失敗依據，必須執行上述 TaskOutput 查詢

替代假設提醒：
  Step 0.5 結果出來前，至少生成 2 個假設
    A. 代理人已完成但失敗
    B. 代理人仍在工作（Hook 訊號不可靠）

參考：
  - .claude/pm-rules/agent-failure-sop.md (失敗判斷前置步驟 Step 0.5 / 0.5-A)
  - .claude/references/pm-agent-observability.md (Hook 廣播訊號可靠度表)
  - .claude/error-patterns/process-compliance/PC-050-premature-agent-completion-judgment.md (模式 E)
  - .claude/error-patterns/process-compliance/PC-070-pm-hook-signal-agent-failure-inference.md
"""


def execute_agent_status(args: argparse.Namespace) -> int:
    """印出 TaskOutput 安全查詢範本（PM 手動複製貼上）"""
    agent_id = getattr(args, "agent_id", None) or "<agentId>"
    print(AGENT_STATUS_TEMPLATE.format(agent_id=agent_id))
    return 0


def register_agent_status(subparsers: argparse._SubParsersAction) -> None:
    """註冊 agent-status 子命令到 track 下"""
    parser = subparsers.add_parser(
        "agent-status",
        help="印出 TaskOutput 安全查詢指引（PC-050 模式 E / PC-070 防護）",
    )
    parser.add_argument(
        "agent_id",
        nargs="?",
        default=None,
        help="代理人 agentId（Agent tool 返回值；可省略，範本中以 <agentId> 佔位）",
    )
