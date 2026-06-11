"""emit_hook_output audience 受眾過濾 + 10 gap hook 遷移回歸測試（W1-075）。

背景（PC-V1-004 防護 C 方案 D）：
    30 個注入 hook 中 10 個暴露於 subagent 無偵測（W1-073 重現實驗）。
    本票將過濾邏輯下沉至 emit_hook_output 統一出口（ARCH-V1-001 單點強制），
    10 個 gap hook 遷移至該出口並標 audience="pm_only"。

驗證三層：
    1. emit_hook_output 單元行為（過濾邏輯唯一實作點，ARCH-020）
       - 既有呼叫不變（預設 audience="all" 向後相容）
       - audience="pm_only" + subagent 觸發 → additionalContext 被丟棄
       - audience="pm_only" + PM 主線程 → 照常輸出
    2. 10 gap hook 遷移 wiring（靜態檢查 audience 標記存在）
    3. 代表性 hook 端到端（input_data 確實接線到統一出口）
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from hook_utils import hook_io  # noqa: E402


# ---------------------------------------------------------------------------
# 共用工具
# ---------------------------------------------------------------------------

SUBAGENT_INPUT = {"agent_id": "thyme-python-developer"}
PM_INPUT = {"tool_name": "Bash"}


def _emit_and_parse(capsys, *args, **kwargs) -> dict:
    """呼叫 emit_hook_output 並解析 stdout JSON。"""
    hook_io.emit_hook_output(*args, **kwargs)
    return json.loads(capsys.readouterr().out)


def _load_module(key: str, path: Path):
    """動態載入含 hyphen 檔名的 hook；模組名加 w1075 前綴避免撞其他測試檔。"""
    spec = importlib.util.spec_from_file_location(f"w1075_{key}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stdin(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _run_main(module, payload: dict, capsys):
    """以 mock stdin 執行 hook main()，回傳 (exit_code, stdout)。"""
    test_logger = logging.getLogger("test-w1075")
    with patch("sys.stdin.read", return_value=_stdin(payload)), \
         patch.object(module, "setup_hook_logging", return_value=test_logger):
        rc = module.main()
    captured = capsys.readouterr()
    return rc, captured.out


# ---------------------------------------------------------------------------
# 1. emit_hook_output 單元行為（過濾邏輯唯一實作點）
# ---------------------------------------------------------------------------

class TestEmitHookOutputAudience:
    """emit_hook_output audience 參數的過濾語意。"""

    def test_default_audience_backward_compatible(self, capsys):
        """既有呼叫不變：不帶 audience/input_data 的舊簽名照常輸出訊息。"""
        output = _emit_and_parse(capsys, "PostToolUse", "提醒訊息")
        assert output["hookSpecificOutput"]["additionalContext"] == "提醒訊息"
        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"

    def test_audience_all_not_filtered_even_in_subagent(self, capsys):
        """audience="all"：即使 subagent 觸發也不過濾（雙方可見訊息）。"""
        output = _emit_and_parse(
            capsys, "PostToolUse", "雙方可見",
            audience="all", input_data=SUBAGENT_INPUT,
        )
        assert output["hookSpecificOutput"]["additionalContext"] == "雙方可見"

    def test_pm_only_subagent_suppresses_message(self, capsys):
        """audience="pm_only" + subagent 觸發：訊息被丟棄，輸出基本結構。"""
        output = _emit_and_parse(
            capsys, "PostToolUse", "PM 專屬訊息",
            audience="pm_only", input_data=SUBAGENT_INPUT,
        )
        assert "additionalContext" not in output["hookSpecificOutput"], \
            "subagent 觸發時 PM-only 訊息不應注入"
        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"

    def test_pm_only_main_thread_outputs_message(self, capsys):
        """audience="pm_only" + PM 主線程（無 agent_id）：照常輸出（含受眾前綴）。

        前綴契約（PC-V1-004 防護 C）：pm_only 訊息抵達主線程時帶
        PM_ONLY_PREFIX，供 AGENT_PRELOAD 忽略規則在程式層偵測不到的
        環境（Stop event 無 agent_id）比對。
        """
        output = _emit_and_parse(
            capsys, "PostToolUse", "PM 專屬訊息",
            audience="pm_only", input_data=PM_INPUT,
        )
        assert output["hookSpecificOutput"]["additionalContext"] == \
            hook_io.PM_ONLY_PREFIX + "PM 專屬訊息"

    def test_pm_only_none_input_treated_as_pm(self, capsys):
        """input_data=None 視為 PM（is_subagent_environment(None) 為 False）。"""
        output = _emit_and_parse(
            capsys, "PostToolUse", "PM 專屬訊息",
            audience="pm_only", input_data=None,
        )
        assert output["hookSpecificOutput"]["additionalContext"] == \
            hook_io.PM_ONLY_PREFIX + "PM 專屬訊息"

    def test_pm_only_suppression_keeps_permission_fields(self, capsys):
        """過濾只丟訊息：permission 欄位屬功能性決策，subagent 觸發時保留。"""
        output = _emit_and_parse(
            capsys, "PreToolUse", "環境警告",
            permission_decision="allow",
            permission_decision_reason="環境檢查",
            audience="pm_only", input_data=SUBAGENT_INPUT,
        )
        hook_output = output["hookSpecificOutput"]
        assert "additionalContext" not in hook_output
        assert hook_output["permissionDecision"] == "allow"
        assert hook_output["permissionDecisionReason"] == "環境檢查"

    def test_invalid_audience_raises_value_error(self):
        """非法 audience 值立即報錯，避免拼字錯誤造成 PM-only 訊息靜默洩漏。"""
        with pytest.raises(ValueError, match="audience"):
            hook_io.emit_hook_output("PostToolUse", "msg", audience="pmonly")


# ---------------------------------------------------------------------------
# 2. 10 gap hook 遷移 wiring（靜態檢查，對應 acceptance 2 的 grep 驗證）
# ---------------------------------------------------------------------------

GAP_HOOK_FILES = [
    "active-dispatch-tracker-hook.py",
    "cli-failure-help-reminder-hook.py",
    "comment-qa-hook.py",
    "dispatch-count-guard-hook.py",
    "file-ownership-guard-hook.py",
    "pre-test-hook.py",
    "session-context-guard-hook.py",
    "skill-cli-error-feedback-hook.py",
    "utf8-integrity-check-hook.py",
    "worklog-format-check.py",
]


@pytest.mark.parametrize("hook_file", GAP_HOOK_FILES)
def test_gap_hook_migrated_to_unified_exit(hook_file):
    """每個 gap hook 的訊息路徑必須經 emit_hook_output 且標 audience="pm_only"。

    過濾邏輯禁止在 hook 內複製（ARCH-020）：hook 只標受眾，
    判斷由 hook_io.emit_hook_output 單點執行。
    """
    source = (HOOKS_DIR / hook_file).read_text(encoding="utf-8")
    assert "emit_hook_output(" in source, \
        f"{hook_file} 未遷移至 emit_hook_output 統一出口"
    assert 'audience="pm_only"' in source, \
        f"{hook_file} 的 PM-only 訊息未標 audience"


# ---------------------------------------------------------------------------
# 3. 代表性 hook 端到端（驗證 input_data 確實接線到統一出口）
# ---------------------------------------------------------------------------

CLI_FAILURE_PAYLOAD = {
    "tool_name": "Bash",
    "tool_input": {"command": "./scripts/deploy.sh --target prod"},
    "tool_response": {"stdout": "", "stderr": "deploy failed: missing config"},
}


class TestCliFailureHelpReminderHook:
    """cli-failure-help-reminder：PostToolUse 訊息路徑。"""

    @pytest.fixture(scope="class")
    def hook(self):
        return _load_module("cli_failure", HOOKS_DIR / "cli-failure-help-reminder-hook.py")

    def test_subagent_env_message_suppressed(self, hook, capsys):
        payload = dict(CLI_FAILURE_PAYLOAD, **SUBAGENT_INPUT)
        rc, out = _run_main(hook, payload, capsys)
        assert rc == 0
        output = json.loads(out)
        assert "additionalContext" not in output["hookSpecificOutput"], \
            "subagent 觸發時 PC-005 提醒不應注入"

    def test_pm_env_message_emitted(self, hook, capsys):
        rc, out = _run_main(hook, CLI_FAILURE_PAYLOAD, capsys)
        assert rc == 0
        output = json.loads(out)
        assert "additionalContext" in output["hookSpecificOutput"], \
            "PM 環境 CLI 失敗時應照常輸出提醒"


SESSION_CONTEXT_PAYLOAD = {
    "tool_name": "Bash",
    "tool_input": {"command": "ticket track complete 1.0.0-W1-075"},
    "tool_response": {"stdout": "[OK] 1.0.0-W1-075 已完成", "stderr": ""},
}


class TestSessionContextGuardHook:
    """session-context-guard：閾值警告訊息路徑。"""

    @pytest.fixture(scope="class")
    def hook(self):
        return _load_module("session_context", HOOKS_DIR / "session-context-guard-hook.py")

    def test_subagent_env_message_suppressed(self, hook, capsys):
        payload = dict(SESSION_CONTEXT_PAYLOAD, **SUBAGENT_INPUT)
        with patch.object(hook, "increment_counter", return_value=2):
            rc, out = _run_main(hook, payload, capsys)
        assert rc == 0
        output = json.loads(out)
        assert "additionalContext" not in output["hookSpecificOutput"], \
            "subagent 觸發時 handoff 提醒不應注入"

    def test_pm_env_message_emitted(self, hook, capsys):
        with patch.object(hook, "increment_counter", return_value=2):
            rc, out = _run_main(hook, SESSION_CONTEXT_PAYLOAD, capsys)
        assert rc == 0
        output = json.loads(out)
        assert "Session Context Guard" in output["hookSpecificOutput"]["additionalContext"], \
            "PM 環境達閾值時應照常輸出 handoff 提醒"


class TestPreTestHook:
    """pre-test：PreToolUse 訊息 + permission 欄位共存路徑。"""

    PAYLOAD = {
        "tool_name": "Bash",
        "tool_input": {"command": "flutter test"},
    }

    @pytest.fixture(scope="class")
    def hook(self):
        return _load_module("pre_test", HOOKS_DIR / "pre-test-hook.py")

    def test_subagent_env_warning_suppressed_decision_kept(self, hook, capsys):
        """subagent 觸發：環境警告被過濾，但 allow 決策（功能性）保留。"""
        payload = dict(self.PAYLOAD, **SUBAGENT_INPUT)
        with patch.object(hook, "check_flutter_sdk", return_value=(False, "SDK 不可用")), \
             patch.object(hook, "check_dependencies", return_value=[]):
            rc, out = _run_main(hook, payload, capsys)
        assert rc == 0
        hook_output = json.loads(out)["hookSpecificOutput"]
        assert "additionalContext" not in hook_output
        assert hook_output["permissionDecision"] == "allow"

    def test_pm_env_warning_emitted(self, hook, capsys):
        with patch.object(hook, "check_flutter_sdk", return_value=(False, "SDK 不可用")), \
             patch.object(hook, "check_dependencies", return_value=[]):
            rc, out = _run_main(hook, self.PAYLOAD, capsys)
        assert rc == 0
        hook_output = json.loads(out)["hookSpecificOutput"]
        assert "SDK 不可用" in hook_output["additionalContext"]
        assert hook_output["permissionDecision"] == "allow"


class TestWorklogFormatCheckHook:
    """worklog-format-check：檔案內容觸發的訊息路徑。"""

    @pytest.fixture(scope="class")
    def hook(self):
        return _load_module("worklog_format", HOOKS_DIR / "worklog-format-check.py")

    @pytest.fixture
    def worklog_with_emoji(self, tmp_path):
        """建立含表格 emoji 的 worklog 檔案（觸發條件：work-logs 路徑 + .md）。"""
        worklog_dir = tmp_path / "docs" / "work-logs"
        worklog_dir.mkdir(parents=True)
        worklog = worklog_dir / "v1.0.0-test.md"
        worklog.write_text("| item | ✅ |\n", encoding="utf-8")
        return worklog

    def _payload(self, file_path: Path) -> dict:
        return {
            "tool_name": "Write",
            "tool_input": {"file_path": str(file_path)},
        }

    def test_subagent_env_message_suppressed(self, hook, worklog_with_emoji, capsys):
        payload = dict(self._payload(worklog_with_emoji), **SUBAGENT_INPUT)
        with patch.object(hook, "should_sample_run", return_value=True):
            rc, out = _run_main(hook, payload, capsys)
        assert rc == 0
        output = json.loads(out)
        assert "additionalContext" not in output["hookSpecificOutput"], \
            "subagent 觸發時 worklog 格式提醒不應注入（避免誘導越界寫 worklog）"

    def test_pm_env_message_emitted(self, hook, worklog_with_emoji, capsys):
        with patch.object(hook, "should_sample_run", return_value=True):
            rc, out = _run_main(hook, self._payload(worklog_with_emoji), capsys)
        assert rc == 0
        output = json.loads(out)
        assert "Issues: 1" in output["hookSpecificOutput"]["additionalContext"], \
            "PM 環境偵測到表格 emoji 時應照常輸出提醒"
