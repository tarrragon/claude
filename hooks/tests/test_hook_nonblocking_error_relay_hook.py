#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hook-nonblocking-error-relay-hook.py 測試（3.3.0-W1-204.2.1）

runtime 把 exit 非 0 非 2 的 hook 記為 non-blocking error，寫進 transcript 的
attachment（type=hook_non_blocking_error），不送模型。本 hook 在後續事件讀取
transcript 新增部分，以 additionalContext 轉告模型。

涵蓋：
  - 摘要行：Traceback 取末行、一般 stderr 取首行、無 stderr 時取 stdout 首行
  - 從 command 取出 hook 檔名
  - 增量讀取：只讀上次位置之後的完整行；未寫完的末行不推進位置
  - 去重：同一 uuid 不重複提醒；transcript 變短時從頭讀但不重複
  - 端到端：同一 transcript 第一次執行有提醒、第二次無提醒（正向對照）
  - 無錯誤時不輸出提醒（反向對照）
  - fail-open：讀取端自身例外 exit 0，寫 stderr
  - 每筆轉送寫一行紀錄到 records 目錄，供 hook-liveness 統計
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "hook-nonblocking-error-relay-hook.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "hook_nonblocking_error_relay_hook", HOOK_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def relay():
    return _load_hook_module()


# runtime 寫入 stderr 欄位的實際形式：一律帶前綴（取自真實 transcript）
RUNTIME_PREFIX = "Failed with non-blocking status code: "
TRACEBACK_STDERR = (
    RUNTIME_PREFIX
    + "Traceback (most recent call last):\n"
    '  File "/x/crash-hook.py", line 2, in <module>\n'
    "    import does_not_exist_mod\n"
    "    ^^^^^^^^^^^^^^^^^^^^^^^^^\n"
    "ModuleNotFoundError: No module named 'does_not_exist_mod'"
)


def _error_entry(
    uuid: str,
    *,
    stderr: str = TRACEBACK_STDERR,
    stdout: str = "",
    hook_name: str = "PreToolUse:Bash",
    hook_event: str = "PreToolUse",
    command: str = "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/crash-hook.py",
    exit_code: int = 1,
) -> dict:
    """依 runtime 實際寫入的形狀構造 attachment（欄位取自真實 transcript）。"""
    return {
        "parentUuid": "p-" + uuid,
        "attachment": {
            "type": "hook_non_blocking_error",
            "hookName": hook_name,
            "toolUseID": "toolu_x",
            "hookEvent": hook_event,
            "stderr": stderr,
            "stdout": stdout,
            "exitCode": exit_code,
            "command": command,
            "durationMs": 12,
        },
        "type": "attachment",
        "uuid": uuid,
        "timestamp": "2026-11-13T12:00:00.000Z",
        "sessionId": "sess-1",
    }


def _plain_entry(uuid: str) -> dict:
    return {
        "type": "user",
        "uuid": uuid,
        "message": {"role": "user", "content": "hook_non_blocking_error 只是字串"},
    }


def _write_lines(path: Path, entries: list, mode: str = "w") -> None:
    with path.open(mode, encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# 摘要行與 hook 檔名
# ---------------------------------------------------------------------------


def test_summary_takes_last_line_for_traceback(relay):
    assert relay.summarize_output(TRACEBACK_STDERR, "") == (
        "ModuleNotFoundError: No module named 'does_not_exist_mod'"
    )


def test_summary_takes_first_line_for_plain_stderr(relay):
    stderr = RUNTIME_PREFIX + "設定檔缺欄位 x\n第二行\n"
    assert relay.summarize_output(stderr, "") == "設定檔缺欄位 x"


def test_summary_without_runtime_prefix_still_works(relay):
    assert relay.summarize_output("設定檔缺欄位 x\n", "") == "設定檔缺欄位 x"


def test_summary_falls_back_to_stdout_when_runtime_placeholder(relay):
    placeholder = RUNTIME_PREFIX + "No stderr output"
    assert relay.summarize_output(placeholder, "\n[FAIL] 發現問題\n細節\n") == "[FAIL] 發現問題"


def test_summary_truncates_long_line(relay):
    summary = relay.summarize_output("x" * 1000, "")
    assert len(summary) <= relay.SUMMARY_MAX_CHARS + 1


def test_extract_hook_file_from_command(relay):
    cmd = "uv run --quiet $CLAUDE_PROJECT_DIR/.claude/hooks/crash-hook.py --group A"
    assert relay.extract_hook_file(cmd) == "crash-hook.py"


def test_extract_hook_file_without_py_returns_none(relay):
    assert relay.extract_hook_file("echo hi") is None


# ---------------------------------------------------------------------------
# 增量讀取
# ---------------------------------------------------------------------------


def test_read_new_errors_filters_and_advances_offset(relay, tmp_path):
    t = tmp_path / "t.jsonl"
    _write_lines(t, [_plain_entry("u0"), _error_entry("e1")])
    errors, offset = relay.read_new_errors(t, 0)
    assert [e["uuid"] for e in errors] == ["e1"]
    assert offset == t.stat().st_size

    _write_lines(t, [_error_entry("e2")], mode="a")
    errors2, offset2 = relay.read_new_errors(t, offset)
    assert [e["uuid"] for e in errors2] == ["e2"]
    assert offset2 == t.stat().st_size


def test_read_new_errors_does_not_consume_partial_last_line(relay, tmp_path):
    t = tmp_path / "t.jsonl"
    _write_lines(t, [_error_entry("e1")])
    full = t.stat().st_size
    partial = json.dumps(_error_entry("e2"))[:40]
    with t.open("a", encoding="utf-8") as fh:
        fh.write(partial)
    errors, offset = relay.read_new_errors(t, 0)
    assert [e["uuid"] for e in errors] == ["e1"]
    assert offset == full


def test_read_new_errors_restarts_when_transcript_shrinks(relay, tmp_path):
    t = tmp_path / "t.jsonl"
    _write_lines(t, [_error_entry("e9")])
    errors, offset = relay.read_new_errors(t, 10_000_000)
    assert [e["uuid"] for e in errors] == ["e9"]
    assert offset == t.stat().st_size


# ---------------------------------------------------------------------------
# 端到端（以 subprocess 執行整支 hook）
# ---------------------------------------------------------------------------


def _run_hook(tmp_path: Path, payload: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HOOK_TEST_ISOLATION"] = "1"
    env["HOOK_NONBLOCKING_RELAY_STATE_DIR"] = str(tmp_path / "state")
    env["HOOK_NONBLOCKING_RELAY_RECORDS_DIR"] = str(tmp_path / "records")
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def _payload(t: Path, event: str = "UserPromptSubmit") -> dict:
    return {
        "session_id": "sess-1",
        "transcript_path": str(t),
        "hook_event_name": event,
        "prompt": "hi",
    }


def _context_of(proc: subprocess.CompletedProcess) -> str:
    if not proc.stdout.strip():
        return ""
    out = json.loads(proc.stdout)
    return (out.get("hookSpecificOutput") or {}).get("additionalContext") or ""


def test_e2e_relays_error_once(tmp_path):
    t = tmp_path / "t.jsonl"
    _write_lines(t, [_plain_entry("u0"), _error_entry("e1")])

    first = _run_hook(tmp_path, _payload(t))
    assert first.returncode == 0, first.stderr
    ctx = _context_of(first)
    assert "crash-hook.py" in ctx
    assert "PreToolUse" in ctx
    assert "ModuleNotFoundError: No module named 'does_not_exist_mod'" in ctx

    second = _run_hook(tmp_path, _payload(t, "PostToolUse"))
    assert second.returncode == 0, second.stderr
    assert _context_of(second) == ""


def test_e2e_relays_only_new_error_after_append(tmp_path):
    t = tmp_path / "t.jsonl"
    _write_lines(t, [_error_entry("e1")])
    _run_hook(tmp_path, _payload(t))
    _write_lines(
        t,
        [_error_entry("e2", command="python3 /a/b/other-hook.py", stderr=RUNTIME_PREFIX + "壞掉了")],
        mode="a",
    )
    ctx = _context_of(_run_hook(tmp_path, _payload(t, "PostToolUse")))
    assert "other-hook.py" in ctx
    assert "壞掉了" in ctx
    assert "crash-hook.py" not in ctx


def test_e2e_no_error_no_output(tmp_path):
    t = tmp_path / "t.jsonl"
    _write_lines(t, [_plain_entry("u0"), _plain_entry("u1")])
    proc = _run_hook(tmp_path, _payload(t))
    assert proc.returncode == 0, proc.stderr
    assert _context_of(proc) == ""


def test_e2e_writes_record_per_relayed_error(tmp_path):
    t = tmp_path / "t.jsonl"
    _write_lines(t, [_error_entry("e1"), _error_entry("e2", hook_event="SessionStart")])
    _run_hook(tmp_path, _payload(t))
    rec_file = tmp_path / "records" / "sess-1.jsonl"
    records = [json.loads(x) for x in rec_file.read_text(encoding="utf-8").splitlines()]
    assert [r["uuid"] for r in records] == ["e1", "e2"]
    assert records[0]["hook_file"] == "crash-hook.py"
    assert records[1]["hook_event"] == "SessionStart"
    assert records[0]["summary"].startswith("ModuleNotFoundError")


def test_e2e_caps_listed_errors(tmp_path, relay):
    t = tmp_path / "t.jsonl"
    n = relay.MAX_LISTED_ERRORS + 3
    _write_lines(t, [_error_entry(f"e{i}") for i in range(n)])
    ctx = _context_of(_run_hook(tmp_path, _payload(t)))
    assert f"另有 3 筆" in ctx


def test_e2e_fail_open_on_unreadable_transcript(tmp_path):
    proc = _run_hook(tmp_path, _payload(tmp_path / "missing.jsonl"))
    assert proc.returncode == 0
    assert _context_of(proc) == ""


def test_e2e_fail_open_on_internal_exception(tmp_path):
    """讀取端自身例外：exit 0，stderr 有訊息（不可靜默）。"""
    t = tmp_path / "t.jsonl"
    _write_lines(t, [_error_entry("e1")])
    blocker = tmp_path / "state"
    blocker.write_text("不是目錄", encoding="utf-8")  # state 目錄無法建立
    proc = _run_hook(tmp_path, _payload(t))
    assert proc.returncode == 0
    assert "hook-nonblocking-error-relay" in proc.stderr
