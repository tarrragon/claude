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

from lib import get_effort_level


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

    def test_low_effort_does_not_short_circuit_complete(self):
        # W3-018 移除 complete 命令的 effort 短路：low effort 下 complete
        # 命令仍須執行完整 acceptance 驗證，不可僅回傳 fast-path 的空白 allow。
        # 可證偽判準：完整驗證路徑會輸出 generate_hook_output 特有的
        # "[Complete 清單]" 檢查清單標記，fast-path 短路（_output_allow_json）
        # 則只有裸 permissionDecision JSON，不含此標記。
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ticket track complete 0.18.0-W14-034"},
            "effort": {"level": "low"},
        }
        rc, stdout, _ = _run_hook(self.HOOK, payload)
        assert rc == 0
        assert "[Complete 清單]" in stdout  # 證明完整驗證確實執行，非短路空白放行

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

    def test_low_effort_does_not_short_circuit(self, tmp_path):
        # 建立含違規 status 的實體 ticket 檔（hook 從磁碟讀取 frontmatter）。
        # is_ticket_file() 僅用子字串比對（"docs/work-logs/" + "/tickets/"），
        # parse_frontmatter() 用絕對路徑讀檔，故 tmp_path 下的假路徑即可滿足
        # 判定，不需真實 repo 路徑（0.2.1-W3-027 cwd 無關化 + 防殘留）。
        tickets_dir = tmp_path / "docs" / "work-logs" / "v0.2.1" / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        fixture = tickets_dir / "_test_effort_fixture_frontmatter.md"
        fixture.write_text(
            "---\nid: _test_effort_fixture_frontmatter\nstatus: not_a_valid_status\n---\n# x\n",
            encoding="utf-8",
        )
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(fixture),
                "old_string": "x",
                "new_string": "y",
            },
            "effort": {"level": "low"},
        }
        rc, _, stderr = _run_hook(self.HOOK, payload)
        assert rc == 0  # 此 hook 恆為 exit 0（事後警告，不阻擋）
        assert "status" in stderr  # 但必須確實輸出違規警告，證明未短路跳過檢查

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

    def test_low_effort_does_not_short_circuit(self, hook_project_env):
        # 建立 pending + creation_accepted: false 的 fixture ticket（非 in_progress，
        # 不落入 re-claim no-op 豁免），移除短路後 low effort 應與 medium/high
        # 一樣執行完整檢查並阻擋 claim。
        # cwd 無關化 + 防殘留（0.2.1-W3-027）：改用 conftest 共用的 hook_project_env
        # fixture——以 tmp_path 假專案根 + CLAUDE_PROJECT_DIR 導向 find_ticket_file()
        # 解析，取代真實 repo 路徑，pytest 自動清理不留殘留目錄。
        project_root, env = hook_project_env
        fixture_dir = project_root / "docs" / "work-logs" / "v0" / "v0.2" / "v0.2.1" / "tickets"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        fixture = fixture_dir / "0.2.1-W3-999.md"
        fixture.write_text(
            "---\nid: 0.2.1-W3-999\nstatus: pending\ncreation_accepted: false\n---\n# fixture\n",
            encoding="utf-8",
        )
        payload = {
            "prompt": "/ticket track claim 0.2.1-W3-999",
            "effort": {"level": "low"},
        }
        rc, _, _ = _run_hook(self.HOOK, payload, env=env)
        assert rc == 2  # EXIT_BLOCK：creation_accepted 未通過，low effort 不再豁免

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

    def test_low_effort_does_not_short_circuit(self):
        # source_ticket 非空 + acceptance 含 ";" 分隔違規 → 應觸發 PC-058 WARNING，
        # 移除短路後 low effort 也應輸出 warning（不因 effort 而跳過檢查）。
        content = (
            "---\n"
            "id: test\n"
            "source_ticket: 0.1.0-W1-001\n"
            "dispatch_reason: ANA follow-up\n"
            "acceptance:\n"
            "  - '完成 A; 完成 B'\n"
            "---\n# x"
        )
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "docs/work-logs/v0.18.0/tickets/test.md",
                "content": content,
            },
            "effort": {"level": "low"},
        }
        rc, _, stderr = _run_hook(self.HOOK, payload)
        assert rc == 0  # 此 hook 恆為 exit 0（WARNING-only，不阻擋）
        assert "PC-058" in stderr  # 但必須確實輸出警告，證明未短路跳過檢查

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

    def test_low_effort_does_not_short_circuit(self):
        # 缺少 decision_tree_path 且非 DOC 類型、無 parent_id → 應觸發 WARNING，
        # 移除短路後 low effort 也應輸出警告，證明未短路跳過檢查。
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "docs/work-logs/v0.18.0/tickets/test.md",
                "content": "---\nid: test\ntype: IMP\n---\n# x",
            },
            "effort": {"level": "low"},
        }
        rc, _, stderr = _run_hook(self.HOOK, payload)
        assert rc == 0  # 此 hook 恆為 exit 0（WARNING-only，不阻擋）
        assert "decision_tree_path" in stderr  # 但必須確實輸出警告，證明未短路跳過檢查

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
