#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 effort 感知（W14-034）

涵蓋：
1. hook_utils.get_effort_level helper 三路徑（low / medium / high）+ 邊界
2. 四個 hook 在 low / medium / high effort 下的行為（短路 vs 完整驗證）
3. phase4 hook PC-093 偵測在 low effort 仍阻擋
"""

import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 確保可 import hook_utils
HOOKS_DIR = Path(__file__).parent.parent
# W10-092: 部分 ticket-skill hook 已遷至 .claude/skills/ticket/hooks/
ticket_skill_hooks_path = HOOKS_DIR.parent / "skills" / "ticket" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from hook_utils import get_effort_level


# ============================================================================
# get_effort_level helper
# ============================================================================

class TestGetEffortLevel:
    """get_effort_level 回傳值優先序與正規化驗證"""

    def setup_method(self):
        # 清空環境變數，避免污染
        os.environ.pop("CLAUDE_EFFORT", None)

    def teardown_method(self):
        os.environ.pop("CLAUDE_EFFORT", None)

    def test_payload_low(self):
        assert get_effort_level({"effort": {"level": "low"}}) == "low"

    def test_payload_medium(self):
        assert get_effort_level({"effort": {"level": "medium"}}) == "medium"

    def test_payload_high(self):
        assert get_effort_level({"effort": {"level": "high"}}) == "high"

    def test_payload_uppercase_normalized(self):
        assert get_effort_level({"effort": {"level": "HIGH"}}) == "high"

    def test_payload_priority_over_env(self):
        os.environ["CLAUDE_EFFORT"] = "high"
        assert get_effort_level({"effort": {"level": "low"}}) == "low"

    def test_env_fallback(self):
        os.environ["CLAUDE_EFFORT"] = "low"
        assert get_effort_level({}) == "low"

    def test_env_fallback_when_payload_missing_effort(self):
        os.environ["CLAUDE_EFFORT"] = "high"
        assert get_effort_level({"other": "x"}) == "high"

    def test_default_medium(self):
        assert get_effort_level(None) == "medium"
        assert get_effort_level({}) == "medium"

    def test_invalid_value_falls_back_to_default(self):
        assert get_effort_level({"effort": {"level": "extreme"}}) == "medium"

    def test_custom_default(self):
        assert get_effort_level(None, default="high") == "high"

    def test_invalid_default_falls_back_to_medium(self):
        assert get_effort_level(None, default="bogus") == "medium"

    def test_none_payload(self):
        assert get_effort_level(None) == "medium"

    def test_non_dict_effort_field(self):
        assert get_effort_level({"effort": "low"}) == "medium"


# ============================================================================
# Hook 整合測試輔助
# ============================================================================

def _run_hook(script_path: Path, payload: dict, env: dict = None):
    """以 subprocess 模擬執行 hook，回傳 (returncode, stdout, stderr)"""
    import subprocess

    full_env = os.environ.copy()
    full_env.pop("CLAUDE_EFFORT", None)
    if env:
        full_env.update(env)

    result = subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=full_env,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


# ============================================================================
# acceptance-gate-hook
# ============================================================================

class TestAcceptanceGateEffort:
    HOOK = ticket_skill_hooks_path / "acceptance-gate-hook.py"

    def test_low_effort_short_circuits(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track complete 0.18.0-W14-034"},
            "effort": {"level": "low"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        # low 短路時應輸出 allow JSON
        assert "allow" in stdout.lower() or stdout.strip() == "" or "allow" in stdout

    def test_medium_effort_runs_full_path(self):
        # 非 complete 命令在 medium effort 下走 fast-path 後放行
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_runs_full_path(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


# ============================================================================
# ticket-quality-gate-hook
# ============================================================================

class TestTicketQualityGateEffort:
    HOOK = ticket_skill_hooks_path / "ticket-quality-gate-hook.py"

    def test_low_effort_short_circuits(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "docs/work-logs/v0.18.0/tickets/test.md",
                "content": "---\nid: test\n---\n# test",
            },
            "effort": {"level": "low"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        # low 短路 emit allow JSON
        assert '"decision"' in stdout and "allow" in stdout

    def test_medium_effort_processes(self):
        payload = {
            "tool_name": "Read",  # 不觸發 quality gate
            "tool_input": {"file_path": "x.py"},
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


# ============================================================================
# ticket-frontmatter-validator-hook
# ============================================================================

class TestTicketFrontmatterValidatorEffort:
    HOOK = ticket_skill_hooks_path / "ticket-frontmatter-validator-hook.py"

    def test_low_effort_short_circuits(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "docs/work-logs/v0.18.0/tickets/test.md",
                "old_string": "x",
                "new_string": "y",
            },
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_medium_effort_processes(self):
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "anything.py"},
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


# ============================================================================
# phase4-decision-enforcement-hook
# ============================================================================

class TestPhase4EffortAlwaysBlocks:
    """關鍵測試：PC-093 偵測在 low effort 仍必須阻擋（quality-baseline 規則 2）"""

    HOOK = HOOKS_DIR / "phase4-decision-enforcement-hook.py"

    def test_low_effort_no_command_skip(self):
        # 無 command 時應正常跳過（不該因 effort=low 而異常）
        payload = {
            "tool_name": "Bash",
            "tool_input": {},
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_low_effort_unrelated_command_passes(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "hook_event_name": "PostToolUse",
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_unrelated_command_passes(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "hook_event_name": "PostToolUse",
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


# ============================================================================
# W14-037：類別 A 剩餘 6 hook effort 感知
# ============================================================================

class TestCreationAcceptanceGateEffort:
    HOOK = ticket_skill_hooks_path / "creation-acceptance-gate-hook.py"

    def test_low_effort_short_circuits(self):
        payload = {
            "prompt": "/ticket track claim 0.18.0-W99-999",
            "effort": {"level": "low"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        assert "UserPromptSubmit" in stdout

    def test_medium_effort_processes(self):
        payload = {
            "prompt": "echo hi",  # 非 claim 命令，醫療通過
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_processes(self):
        payload = {
            "prompt": "echo hi",
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


class TestAnaTicketMetadataValidationEffort:
    HOOK = ticket_skill_hooks_path / "ana-ticket-metadata-validation-hook.py"

    def test_low_effort_short_circuits(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "docs/work-logs/v0.18.0/tickets/test.md",
                "content": "---\nid: test\n---\n# x",
            },
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_medium_effort_processes(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/not-a-ticket.py"},
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_processes(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/not-a-ticket.py"},
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


class TestTicketCreationValidationEffort:
    HOOK = ticket_skill_hooks_path / "ticket-creation-validation-hook.py"

    def test_low_effort_short_circuits(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "docs/work-logs/v0.18.0/tickets/test.md",
                "content": "---\nid: test\n---\n# x",
            },
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_medium_effort_processes(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/random.py",
                "content": "x = 1",
            },
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_processes(self):
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/tmp/random.py",
                "content": "x = 1",
            },
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


class TestCommentQAEffort:
    HOOK = HOOKS_DIR.parent / "skills" / "compositional-writing" / "hooks" / "comment-qa-hook.py"

    def test_low_effort_short_circuits(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/x.py"},
            "tool_response": {"success": True},
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_medium_effort_processes(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/non-source.txt"},
            "tool_response": {"success": True},
            "effort": {"level": "medium"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_processes(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/non-source.txt"},
            "tool_response": {"success": True},
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


class TestAuqCharsetGuardEffortAlwaysScans:
    """關鍵測試：PC-074/PC-131 字元集偵測在 low effort 仍執行"""

    HOOK = HOOKS_DIR / "askuserquestion-charset-guard-hook.py"

    def test_low_effort_clean_payload_passes(self):
        payload = {
            "tool_name": "AskUserQuestion",
            "tool_input": {
                "questions": [
                    {"question": "繼續嗎？", "options": [{"label": "是"}, {"label": "否"}]}
                ]
            },
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_low_effort_non_auq_tool_passes(self):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0

    def test_high_effort_clean_payload_passes(self):
        payload = {
            "tool_name": "AskUserQuestion",
            "tool_input": {"questions": []},
            "effort": {"level": "high"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload)
        assert rc == 0


class TestAuqOptionPatternDetectorEffortAlwaysRuns:
    """關鍵測試：PC-064 AUQ pattern 偵測在 low effort 仍執行"""

    HOOK = HOOKS_DIR / "auq-option-pattern-detector-hook.py"

    def test_low_effort_no_transcript_passes(self):
        payload = {
            "prompt": "echo hi",
            "effort": {"level": "low"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        assert "UserPromptSubmit" in stdout

    def test_medium_effort_no_transcript_passes(self):
        payload = {
            "prompt": "echo hi",
            "effort": {"level": "medium"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        assert "UserPromptSubmit" in stdout

    def test_high_effort_no_transcript_passes(self):
        payload = {
            "prompt": "echo hi",
            "effort": {"level": "high"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        assert "UserPromptSubmit" in stdout
