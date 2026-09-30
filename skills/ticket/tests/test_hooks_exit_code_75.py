"""hook 端對 ticket 寫入命令退出碼 75 的判讀（E1 對照）。

75（EXIT_AUTO_COMMIT_FAILED）代表動作已完成、僅 auto-commit 失敗。
每個 hook 同 fixture 下：exit_code 0 與 75 都視為成功，1 視為失敗。
"""
import importlib.util
import logging
import sys
from pathlib import Path

from unittest.mock import patch

import pytest

_CLAUDE = Path(__file__).resolve().parents[3]
_LOGGER = logging.getLogger("test_hooks_exit_code_75")


def _load(path: Path, name: str):
    hooks_dir = str(_CLAUDE / "hooks")
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload(command: str, exit_code: int, stdout: str, stderr: str = "") -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"exit_code": exit_code, "stdout": stdout, "stderr": stderr},
    }


_CODES = [(0, True), (75, True), (1, False)]


@pytest.mark.parametrize("exit_code, expected", _CODES)
def test_parallel_dispatch_verification_hook(exit_code, expected):
    hook = _load(_CLAUDE / "hooks" / "parallel-dispatch-verification-hook.py", "pdv_hook")
    payload = _payload("ticket track complete 0.1.0-W1-001", exit_code, "[OK] 已完成 Ticket")
    assert hook.is_ticket_complete_success(payload) is expected


@pytest.mark.parametrize("exit_code, expected", _CODES)
def test_handoff_cleanup_hook(exit_code, expected):
    hook = _load(_CLAUDE / "skills" / "ticket" / "hooks" / "handoff-cleanup-hook.py", "hc_hook")
    payload = _payload("ticket track complete 0.1.0-W1-001", exit_code, "[OK] 已完成 Ticket")
    assert hook.is_complete_command_success(payload, _LOGGER) is expected


@pytest.mark.parametrize("exit_code, expected", _CODES)
def test_needs_context_listener_hook(exit_code, expected, capsys):
    hook = _load(
        _CLAUDE / "skills" / "ticket" / "hooks" / "needs-context-listener-hook.py", "ncl_hook"
    )
    payload = _payload(
        "ticket track append-log 0.1.0-W1-001 --section NeedsContext x",
        exit_code,
        "[OK] 已追加日誌到 NeedsContext",
    )
    with patch.object(hook, "read_json_from_stdin", return_value=payload):
        hook.main_logic()
    assert ("NeedsContext" in capsys.readouterr().out) is expected


@pytest.mark.parametrize("exit_code, expected_feedback", [(0, False), (75, False), (1, True)])
def test_cli_error_feedback_hook(exit_code, expected_feedback):
    hook = _load(_CLAUDE / "skills" / "ticket" / "hooks" / "cli-error-feedback-hook.py", "cef_hook")
    payload = _payload(
        "ticket track append-log 0.1.0-W1-001 --section Solution x",
        exit_code,
        "",
        "error: unrecognized arguments: --bogus",
    )
    result = hook.check_skill_cli_error(payload, _LOGGER)
    assert (result is not None) is expected_feedback


@pytest.mark.parametrize(
    "rc, must_contain, must_not_contain",
    [(75, "日誌已寫入，自動提交失敗", "落票失敗"), (1, "落票失敗", "日誌已寫入"), (0, "", "[reclaim]")],
)
def test_reclaim_landing_report_message_by_append_log_rc(rc, must_contain, must_not_contain, capsys):
    from datetime import datetime, timezone

    from ticket_system.commands import track

    with patch("ticket_system.commands.track_acceptance.execute_append_log", return_value=rc):
        track._reclaim_landing_report_hook("0.1.0", "0.1.0-W1-001", "report", datetime.now(timezone.utc))
    err = capsys.readouterr().err
    assert must_contain in err
    assert must_not_contain not in err


@pytest.mark.parametrize("rc, expected_bound", [(0, True), (75, True), (1, False)])
def test_dispatch_identity_bind_hook_set_who_rc(rc, expected_bound, tmp_path):
    """set-who 回 75 表示 who.current 已寫入、只是提交失敗，綁定須視為成功。"""
    hook = _load(_CLAUDE / "hooks" / "dispatch-identity-bind-hook.py", "dib_hook")

    def fake_run(cmd, **_kwargs):
        is_write = "set-who" in cmd
        return type("P", (), {
            "returncode": rc if is_write else 0,
            "stdout": "[OK]\n" if is_write else "Who: pending\n",
            "stderr": "",
        })()

    with patch.object(hook.subprocess, "run", side_effect=fake_run):
        bound = hook.bind_dispatch_identity("0.1.0-W1-001", "some-agent", tmp_path, _LOGGER)
    assert bound is expected_bound


_COMMIT_FAIL_STDERR = (
    "[WARNING] [claim] 0.1.0-W1-001 已寫入 working tree 但 auto-commit 失敗"
    "（嘗試 1 次）；尚未入庫，exit code 75。\n"
    "失敗原因：git update-ref failed: cannot lock ref\n"
)


@pytest.mark.parametrize(
    "result, expected",
    [
        # 對照：同樣含 "failed" 字樣的 stderr，但 claim 本身失敗（無 exit_code 75、無 WARNING 片語）
        ({"stdout": "", "stderr": "update-ref failed"}, False),
        # claim 已寫入但提交失敗：exit_code 75 為權威
        ({"exit_code": 75, "stdout": "", "stderr": _COMMIT_FAIL_STDERR}, True),
        # exit_code 欄位缺席時，以 WARNING 固定片語後備判讀
        ({"stdout": "", "stderr": _COMMIT_FAIL_STDERR}, True),
        ({"exit_code": 0, "stdout": "認領成功", "stderr": ""}, True),
    ],
)
def test_parallel_claim_audit_hook_claim_rc75_is_success(result, expected):
    """claim 回 75 表示已認領、只是提交失敗；stderr 內的 failed 字樣不得使審計漏記。"""
    hook = _load(_CLAUDE / "hooks" / "parallel-claim-audit-hook.py", "pca_hook")
    assert hook.is_claim_successful(result) is expected
