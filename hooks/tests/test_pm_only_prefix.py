"""[PM-ONLY] 受眾標記前綴回歸測試（PC-V1-004 防護 C 規則層落地）。

背景：
    Stop event 無 agent_id（CC runtime 硬約束），is_subagent_environment
    對其永遠返回 False，程式層無法過濾 PM 專屬注入。防護改走規則層：
    hook 端統一加 PM_ONLY_PREFIX，AGENT_PRELOAD 教 subagent 忽略該前綴訊息。

驗證三層：
    1. 前綴常數單一來源（ARCH-020）：字面只定義於 hook_utils/hook_io.py，
       其他 hook 一律 import 常數，不複製字串
    2. emit_hook_output 統一出口：audience="pm_only" + 主線程 → 自動加前綴；
       audience="all" → 不加（避免污染雙方可見訊息）
    3. Stop 類 hook 輸出（emit_hook_output 無法覆蓋的 shape）：
       - stop-worklog-handoff-sync-check：systemMessage 含前綴
       - handoff-auto-resume：decision:block 的 reason 含前綴（單任務 + 多任務）
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
CLAUDE_DIR = HOOKS_DIR.parent
sys.path.insert(0, str(HOOKS_DIR))

from hook_utils import hook_io  # noqa: E402
from hook_utils.hook_io import PM_ONLY_PREFIX  # noqa: E402


def _load_module(key: str, path: Path):
    """動態載入含 hyphen 檔名的 hook；模組名加 w1076 前綴避免撞其他測試檔。"""
    spec = importlib.util.spec_from_file_location(f"w1076_{key}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# 1. 前綴常數單一來源（ARCH-020：禁止逐 hook 複製字串字面）
# ---------------------------------------------------------------------------

class TestPrefixSingleSource:
    """PM_ONLY_PREFIX 字面只允許定義於 hook_utils/hook_io.py。"""

    def test_prefix_constant_value(self):
        """前綴字面契約：開頭標記 + 一個空格分隔訊息本體。"""
        assert PM_ONLY_PREFIX == "[PM-ONLY] "

    def test_prefix_exported_from_hook_utils_package(self):
        """hook 端 import 入口：hook_utils 套件層 re-export。"""
        import hook_utils
        assert hook_utils.PM_ONLY_PREFIX is PM_ONLY_PREFIX

    def test_prefix_literal_only_defined_in_hook_io(self):
        """掃描 .claude 下生產用 .py：'[PM-ONLY]' 字面只出現在 hook_io.py。

        其他 hook 必須 import PM_ONLY_PREFIX，不可複製字串——
        字面漂移會使 AGENT_PRELOAD 忽略規則失去比對錨點。
        """
        canonical = HOOKS_DIR / "hook_utils" / "hook_io.py"
        offenders = []
        for py_file in CLAUDE_DIR.rglob("*.py"):
            relative_parts = py_file.relative_to(CLAUDE_DIR).parts
            # 測試碼可合法引用字面（斷言期待值）；其餘生產碼禁止
            if "tests" in relative_parts or "test" in py_file.stem.split("_"):
                continue
            if py_file == canonical:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "[PM-ONLY]" in source:
                offenders.append(str(py_file.relative_to(CLAUDE_DIR)))
        assert offenders == [], (
            "以下檔案複製了 [PM-ONLY] 字面，必須改 import "
            f"hook_utils.PM_ONLY_PREFIX：{offenders}"
        )


# ---------------------------------------------------------------------------
# 2. emit_hook_output 統一出口的前綴行為
# ---------------------------------------------------------------------------

class TestEmitHookOutputPrefix:
    """audience 與前綴的對應關係（過濾與前綴邏輯的唯一實作點）。"""

    def _emit_and_parse(self, capsys, *args, **kwargs) -> dict:
        hook_io.emit_hook_output(*args, **kwargs)
        return json.loads(capsys.readouterr().out)

    def test_pm_only_main_thread_message_prefixed(self, capsys):
        """pm_only + 主線程：訊息開頭帶前綴。"""
        output = self._emit_and_parse(
            capsys, "PostToolUse", "提醒內容",
            audience="pm_only", input_data={"tool_name": "Bash"},
        )
        context = output["hookSpecificOutput"]["additionalContext"]
        assert context.startswith(PM_ONLY_PREFIX)
        assert context == PM_ONLY_PREFIX + "提醒內容"

    def test_audience_all_message_not_prefixed(self, capsys):
        """audience="all"：雙方可見訊息不加前綴（避免 subagent 誤忽略）。"""
        output = self._emit_and_parse(
            capsys, "PostToolUse", "雙方可見訊息", audience="all",
        )
        context = output["hookSpecificOutput"]["additionalContext"]
        assert not context.startswith(PM_ONLY_PREFIX)

    def test_default_audience_not_prefixed(self, capsys):
        """既有呼叫（預設 audience）：行為不變，無前綴。"""
        output = self._emit_and_parse(capsys, "PostToolUse", "舊呼叫訊息")
        assert output["hookSpecificOutput"]["additionalContext"] == "舊呼叫訊息"

    def test_pm_only_subagent_still_suppressed_no_prefix_leak(self, capsys):
        """pm_only + subagent：訊息整則丟棄（前綴不改變既有過濾語意）。"""
        output = self._emit_and_parse(
            capsys, "PostToolUse", "PM 專屬",
            audience="pm_only", input_data={"agent_id": "thyme-python-developer"},
        )
        assert "additionalContext" not in output["hookSpecificOutput"]

    def test_pm_only_empty_message_no_prefix_only_output(self, capsys):
        """pm_only + 無訊息：不可輸出只剩前綴的空殼 additionalContext。"""
        output = self._emit_and_parse(
            capsys, "PostToolUse", None, audience="pm_only",
        )
        assert "additionalContext" not in output["hookSpecificOutput"]


# ---------------------------------------------------------------------------
# 3. Stop 類 hook 輸出含前綴（程式層偵測盲區的標記落地）
# ---------------------------------------------------------------------------

STOP_WORKLOG_HOOK = (
    CLAUDE_DIR / "skills" / "ticket" / "hooks"
    / "stop-worklog-handoff-sync-check-hook.py"
)
HANDOFF_RESUME_HOOK = (
    CLAUDE_DIR / "skills" / "ticket" / "hooks"
    / "handoff-auto-resume-stop-hook.py"
)


class TestStopWorklogSyncCheckPrefix:
    """stop-worklog-handoff-sync-check：systemMessage 路徑。"""

    @pytest.fixture(scope="class")
    def hook(self):
        return _load_module("stop_worklog", STOP_WORKLOG_HOOK)

    def test_system_message_starts_with_prefix(self, hook, capsys, monkeypatch):
        """偵測到 drift 時，systemMessage 必以 PM_ONLY_PREFIX 開頭。"""
        monkeypatch.setattr(
            hook, "detect_sync_drift", lambda *a, **kw: "雙軌不同步警告內容"
        )
        monkeypatch.setattr(
            hook, "_mark_blocked_this_session", lambda *a, **kw: None
        )
        test_logger = logging.getLogger("test-w1076-stop-worklog")
        with patch("sys.stdin.isatty", return_value=True), \
             patch.object(hook, "setup_hook_logging", return_value=test_logger), \
             pytest.raises(SystemExit) as exc_info:
            hook.main()
        assert exc_info.value.code == 0
        output = json.loads(capsys.readouterr().out)
        assert output["systemMessage"].startswith(PM_ONLY_PREFIX)
        assert "雙軌不同步警告內容" in output["systemMessage"]


class TestHandoffAutoResumePrefix:
    """handoff-auto-resume：decision:block 的 reason 路徑（單任務 + 多任務）。"""

    @pytest.fixture(scope="class")
    def hook(self):
        return _load_module("handoff_resume", HANDOFF_RESUME_HOOK)

    @pytest.fixture
    def pm_context(self, hook, monkeypatch):
        """共同前置：主線程觸發、本 session 未觸發過、flag 寫入 no-op。"""
        monkeypatch.setattr(hook, "is_subagent_context", lambda *a, **kw: False)
        monkeypatch.setattr(
            hook, "has_been_triggered_this_session", lambda *a, **kw: False
        )
        monkeypatch.setattr(
            hook, "mark_triggered_this_session", lambda *a, **kw: None
        )
        return logging.getLogger("test-w1076-handoff-resume")

    def test_single_task_block_reason_prefixed(self, hook, pm_context, monkeypatch):
        """單任務阻擋：reason（恢復指令，PM 專屬）以前綴開頭。"""
        monkeypatch.setattr(
            hook, "read_session_state",
            lambda *a, **kw: {"locked_ticket_id": "9.9.9-W9-999"},
        )
        result = hook.generate_hook_output(pm_context, input_data={})
        assert result["decision"] == "block"
        assert result["reason"].startswith(PM_ONLY_PREFIX)
        assert "9.9.9-W9-999" in result["reason"]

    def test_multi_task_block_reason_prefixed(
        self, hook, pm_context, monkeypatch, capsys
    ):
        """多任務阻擋：reason 同樣帶前綴（兩條 block 路徑全覆蓋）。"""
        tasks = [
            {"ticket_id": "9.9.9-W9-991", "title": "t1", "direction": "auto"},
            {"ticket_id": "9.9.9-W9-992", "title": "t2", "direction": "auto"},
        ]
        monkeypatch.setattr(hook, "read_session_state", lambda *a, **kw: None)
        monkeypatch.setattr(
            hook, "scan_pending_handoff_tasks", lambda *a, **kw: (tasks, [])
        )
        monkeypatch.setattr(
            hook, "format_pending_tasks_list", lambda *a, **kw: "任務清單"
        )
        result = hook.generate_hook_output(pm_context, input_data={})
        assert result["decision"] == "block"
        assert result["reason"].startswith(PM_ONLY_PREFIX)
