#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 W14-036 類別 A 中頻 6 hook 的 effort 感知

涵蓋 hook：
1. 5w1h-compliance-check-hook
2. phase-contract-validator-hook（CLI sys.argv 模式，僅 $CLAUDE_EFFORT）
3. phase-completion-gate-hook
4. wrap-decision-tripwire-hook（advisory：low effort 不短路）
5. sibling-blockedby-validator-hook
6. layer-boundary-validator-hook

每個 hook 覆蓋 low / medium / high 三路徑（依適用性調整）。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(HOOKS_DIR))


def _run_hook(script_path: Path, payload: dict, env: dict = None, args: list = None):
    """以 subprocess 模擬執行 hook，回傳 (returncode, stdout, stderr)"""
    full_env = os.environ.copy()
    full_env.pop("CLAUDE_EFFORT", None)
    if env:
        full_env.update(env)

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    result = subprocess.run(
        cmd,
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True,
        text=True,
        env=full_env,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


# ============================================================================
# 1. 5w1h-compliance-check-hook
# ============================================================================

class Test5w1hComplianceEffort:
    HOOK = HOOKS_DIR / "5w1h-compliance-check-hook.py"

    def test_low_effort_does_not_short_circuit(self):
        # content 存在但缺少 Who 欄位 → 應與 medium/high 同樣被 block（rc=1），
        # 證明移除短路後 low effort 也執行完整 5W1H 檢查。
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "x.md", "content": "hi"},
            "effort": {"level": "low"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 1
        assert "block" in stdout.lower()

    def test_medium_effort_runs_full_path(self):
        payload = {
            "tool_name": "Read",  # Read 不觸發 5W1H 檢查，會放行
            "tool_input": {"file_path": "x.py"},
            "effort": {"level": "medium"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        # medium 不短路，會走 make_decision；Read 工具放行
        assert "allow" in stdout.lower()

    def test_high_effort_runs_full_path(self):
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "x.py"},
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


# ============================================================================
# 2. phase-contract-validator-hook（CLI 模式）
# ============================================================================

class TestPhaseContractValidatorEffort:
    HOOK = HOOKS_DIR / "phase-contract-validator-hook.py"

    def test_low_effort_short_circuits_via_env(self):
        # CLI 模式：透過 $CLAUDE_EFFORT 控制
        rc, stdout, _ = _run_hook(
            self.HOOK,
            payload=None,
            env={"CLAUDE_EFFORT": "low"},
            args=["fake-ticket-id", "1", "/tmp/fake-dir"],
        )
        assert rc == 0
        assert "effort=low" in stdout or "短路" in stdout

    def test_no_args_returns_usage(self):
        # 無 args 時應 exit 1（和 effort 無關）
        rc, _, _ = _run_hook(self.HOOK, payload=None)
        assert rc == 1

    def test_medium_effort_runs_full_validation(self):
        # medium effort 會嘗試執行完整驗證；fake ticket 應失敗，但效應不應為短路
        rc, stdout, _ = _run_hook(
            self.HOOK,
            payload=None,
            env={"CLAUDE_EFFORT": "medium"},
            args=["fake-ticket-id", "1", "/tmp/nonexistent"],
        )
        # 不應為短路訊息
        assert "短路" not in stdout


# ============================================================================
# 3. phase-completion-gate-hook
# ============================================================================

class TestPhaseCompletionGateEffort:
    HOOK = HOOKS_DIR / "phase-completion-gate-hook.py"

    def test_low_effort_does_not_short_circuit(self):
        # Phase 4 完成報告缺少必要內容 → 應輸出 additionalContext 警告，
        # 移除短路後 low effort 應與 medium 產出相同的完整分析結果。
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "docs/work-logs/vTEST/Phase 4 完成報告.md",
                "content": "# Phase 4",
            },
            "effort": {"level": "low"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        assert "additionalContext" in stdout
        assert "缺少必要內容" in stdout  # 證明完整檢查邏輯確實執行，非短路的空白 PostToolUse 輸出

    def test_medium_effort_processes(self):
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "x.py"},
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_processes(self):
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "x.py"},
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


# ============================================================================
# 4. wrap-decision-tripwire-hook（advisory；low effort 仍須完整偵測）
# ============================================================================

class TestWrapDecisionTripwireEffort:
    """關鍵測試：WRAP 訊號偵測屬「事實判斷」核心訊號，low effort 下仍必須完整執行（quality-baseline 規則 6）"""

    HOOK = HOOKS_DIR.parent / "skills" / "wrap-decision" / "hooks" / "wrap-decision-tripwire-hook.py"

    def test_low_effort_does_not_short_circuit(self):
        # low effort 仍須執行完整偵測；hook 為 advisory（永遠 exit 0）
        # 驗證：rc=0 且不出錯（pytest env 會 skip detection 但 effort 訊息仍應記錄）
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_medium_effort_runs(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_runs(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


# ============================================================================
# 5. sibling-blockedby-validator-hook
# ============================================================================

class TestSiblingBlockedbyValidatorEffort:
    HOOK = HOOKS_DIR / "sibling-blockedby-validator-hook.py"

    def test_low_effort_does_not_short_circuit(self, hook_project_env):
        # 建立雙向 blockedBy 兄弟 fixture（條件 1+2 違反）→ 應 BLOCK（rc=2），
        # 移除短路後 low effort 應與 medium/high 一樣阻擋，不再全面放行。
        # cwd 無關化 + 防殘留（0.2.1-W3-027）：改用 conftest 共用的
        # hook_project_env fixture（tmp_path 假專案根 + CLAUDE_PROJECT_DIR），
        # 取代真實 repo 路徑，pytest 自動清理不留殘留目錄。
        project_root, env = hook_project_env
        fixture_dir = project_root / "docs" / "work-logs" / "v0" / "v0.2" / "v0.2.1" / "tickets"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        sibling_a = fixture_dir / "0.2.1-W3-998.md"
        sibling_b = fixture_dir / "0.2.1-W3-999.md"
        sibling_a.write_text(
            "---\nid: 0.2.1-W3-998\nparent_id: 0.2.1-W3-PARENT\nblockedBy: [0.2.1-W3-999]\n---\n# fixture\n",
            encoding="utf-8",
        )
        sibling_b.write_text(
            "---\nid: 0.2.1-W3-999\nparent_id: 0.2.1-W3-PARENT\nblockedBy: [0.2.1-W3-998]\n---\n# fixture\n",
            encoding="utf-8",
        )
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track claim 0.2.1-W3-999"},
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload, env=env)
        assert rc == 2  # BLOCK：雙向依賴 + 循環依賴，low effort 不再豁免

    def test_medium_effort_processes(self):
        # 非 ticket track claim 命令在 medium effort 下會被 parse_bash_command 過濾，放行
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_processes(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


# ============================================================================
# 6. layer-boundary-validator-hook
# ============================================================================

class TestLayerBoundaryValidatorEffort:
    HOOK = HOOKS_DIR.parent / "skills" / "tdd" / "hooks" / "layer-boundary-validator-hook.py"

    def test_low_effort_does_not_short_circuit(self, tmp_path):
        # Layer 1 檔案含禁止項「/ticket track」→ 應輸出邊界違規警告，
        # 移除短路後 low effort 應與 medium 產出相同的完整掃描結果。
        # is_layer1_file() 僅用子字串比對（".claude/rules/core/" + .md 結尾），
        # 讀檔用絕對路徑，故 tmp_path 下的假路徑即可滿足判定，不需真實 repo
        # 路徑（0.2.1-W3-027 cwd 無關化 + 防殘留）。
        fixture = tmp_path / ".claude" / "rules" / "core" / "_test_effort_fixture_layer1.md"
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text("執行 /ticket track claim 來認領任務\n", encoding="utf-8")
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(fixture),
                "content": "執行 /ticket track claim 來認領任務",
            },
            "effort": {"level": "low"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        assert "additionalContext" in stdout
        assert "邊界驗證警告" in stdout  # 證明完整掃描確實執行，非短路的空白 PostToolUse 輸出

    def test_medium_effort_processes_non_layer1(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "src/foo.py", "content": "x"},
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_processes(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "src/foo.py", "content": "x"},
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
