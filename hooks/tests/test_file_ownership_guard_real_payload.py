#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""file-ownership-guard-hook 以真實形狀 Agent payload 執行時須進入所有權檢查。

修正前：extract_ticket_id 讀 tool_input.target_id／ticket_id／id，Agent 工具輸入
沒有這些欄位，恆回 None，日誌只有「無法從派發指令中提取 Ticket ID」，守衛從未檢查。
修正後：從 tool_input.prompt 首行解析 Ticket ID（標籤錨定優先）。

隔離：以 conftest 的 hook_project_env 執行，日誌與票檔都在 tmp。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "file-ownership-guard-hook.py"

SKIP_LINE = "無法從派發指令中提取 Ticket ID"
CHECK_LINE = "檢查 Ticket 0.1.2-W2-001 的檔案所有權衝突"
WARNING_TITLE = "[檔案所有權衝突警告]"


def _ticket(root: Path, ticket_id: str, files: list[str], status: str = "in_progress") -> None:
    tickets_dir = root / "docs" / "work-logs" / "v0.1.2" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    files_yaml = "\n".join(f"    - {f}" for f in files)
    (tickets_dir / f"{ticket_id}.md").write_text(
        f"---\nid: {ticket_id}\ntitle: t\ntype: IMP\nstatus: {status}\n"
        f"where:\n  files:\n{files_yaml}\n---\n",
        encoding="utf-8",
    )


def _payload(prompt: str) -> dict:
    """Agent 工具的真實輸入形狀：沒有 target_id／ticket_id／id。"""
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {
            "prompt": prompt,
            "description": "實作",
            "subagent_type": "thyme-python-developer",
        },
    }


def _run(payload: dict, env: dict):
    full_env = os.environ.copy()
    full_env.update(env)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=full_env,
        timeout=60,
    )
    return result.returncode, result.stdout, result.stderr


def _log_text(root: Path) -> str:
    log_dir = root / ".claude" / "hook-logs" / "file-ownership-guard-hook"
    return "".join(p.read_text(encoding="utf-8") for p in sorted(log_dir.glob("*.log")))


class TestRealAgentPayload:
    def test_conflicting_sibling_produces_warning(self, hook_project_env):
        root, env = hook_project_env
        _ticket(root, "0.1.2-W2-001", ["lib/create.py"])
        _ticket(root, "0.1.2-W2-002", ["lib/create.py"])

        rc, out, _ = _run(_payload("Ticket: 0.1.2-W2-001\n執行任務"), env)

        log = _log_text(root)
        assert rc == 0
        assert SKIP_LINE not in log
        assert CHECK_LINE in log
        assert WARNING_TITLE in out
        assert "0.1.2-W2-002" in out

    def test_overlap_with_pending_only_stays_silent(self, hook_project_env):
        """反向對照：只和 pending 的票重疊時不警告（pending 尚無人在改）。"""
        root, env = hook_project_env
        _ticket(root, "0.1.2-W2-001", ["lib/create.py"], status="pending")
        _ticket(root, "0.1.2-W2-002", ["lib/create.py"], status="pending")

        rc, out, _ = _run(_payload("Ticket: 0.1.2-W2-001\n執行任務"), env)

        assert rc == 0
        assert CHECK_LINE in _log_text(root)
        assert WARNING_TITLE not in out

    def test_no_conflict_stays_silent(self, hook_project_env):
        root, env = hook_project_env
        _ticket(root, "0.1.2-W2-001", ["lib/create.py"])
        _ticket(root, "0.1.2-W2-002", ["lib/other.py"])

        rc, out, _ = _run(_payload("Ticket: 0.1.2-W2-001\n執行任務"), env)

        assert rc == 0
        assert CHECK_LINE in _log_text(root)
        assert WARNING_TITLE not in out

    def test_prompt_without_ticket_id_skips(self, hook_project_env):
        """對照：非票務派發（首行無 ID）照舊不檢查。"""
        root, env = hook_project_env
        _ticket(root, "0.1.2-W2-001", ["lib/create.py"])
        _ticket(root, "0.1.2-W2-002", ["lib/create.py"])

        rc, out, _ = _run(_payload("搜尋設定檔位置"), env)

        assert rc == 0
        assert WARNING_TITLE not in out
