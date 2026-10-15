"""post-tool-failure-liveness-hook 測試：恆 exit 0、無 stdout、摘要含失敗欄位"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = HOOKS_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / ".claude"))

_spec = importlib.util.spec_from_file_location(
    "post_tool_failure_liveness_mod", HOOKS_DIR / "post-tool-failure-liveness-hook.py")
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _run(stdin_text):
    return subprocess.run([sys.executable, str(HOOKS_DIR / "post-tool-failure-liveness-hook.py")],
                          input=stdin_text, capture_output=True, text=True, cwd=str(PROJECT_ROOT))


def test_summary_contains_failure_fields():
    text = hook.summarize_failure({
        "hook_event_name": "PostToolUseFailure", "is_interrupt": True,
        "duration_ms": 7, "error": "Exit code 1\nboom"})
    assert "event=PostToolUseFailure" in text
    assert "interrupt=True" in text and "duration_ms=7" in text
    assert "\n" not in text


def test_summary_truncates_long_error():
    text = hook.summarize_failure({"error": "x" * 1000})
    assert len(text) < 1000


def test_failure_payload_exits_zero_silently():
    p = _run(json.dumps({"hook_event_name": "PostToolUseFailure", "error": "Exit code 2"}))
    assert p.returncode == 0 and p.stdout == ""


def test_empty_stdin_exits_zero_silently():
    p = _run("")
    assert p.returncode == 0 and p.stdout == "" and p.stderr == ""
