"""post-ticket-lifecycle-hook / handoff-cleanup-hook 完成命令辨識（finish 別名）測試。

兩支 hook 為 PostToolUse(Bash)，完成命令成功後分別：
- lifecycle：輸出 checkpoint 提醒（additionalContext）；不再計數（計數只在 session-context-guard-hook）
- handoff-cleanup：刪除 .claude/handoff/pending|archive/{ticket_id}.json

E2 紀律：每支 hook 以 finish 觸發，斷言具體副作用（無計數器檔、檔案被刪、
結構化輸出整體相等），不以子字串存在性斷言。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[3]
HOOKS_DIR = CLAUDE_DIR / "skills" / "ticket" / "hooks"
LIFECYCLE = HOOKS_DIR / "post-ticket-lifecycle-hook.py"
HANDOFF = HOOKS_DIR / "handoff-cleanup-hook.py"
TICKET_ID = "0.5.0-W1-270.6"
SESSION_ID = "finish-alias-test-session"

sys.path.insert(0, str(CLAUDE_DIR))
from lib.hook_messages import AskUserQuestionMessages  # noqa: E402

DEFAULT_OUTPUT = {"hookSpecificOutput": {"hookEventName": "PostToolUse"}}
SUPPRESS_OUTPUT = {"suppressOutput": True}


def _payload(command: str) -> str:
    return json.dumps({
        "session_id": SESSION_ID,
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {
            "stdout": f"[OK] 已完成 Ticket {TICKET_ID}",
            "stderr": "",
            "exit_code": 0,
        },
    })


def _run(script: Path, command: str, env_extra: dict):
    env = dict(os.environ)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(script)],
        input=_payload(command), capture_output=True, text=True, env=env, timeout=30,
    )


@pytest.fixture
def lifecycle_env(tmp_path):
    """隔離計數器路徑：lifecycle 不應寫出它（計數只在 session-context-guard-hook）。"""
    counter = Path(f"/tmp/claude-session-completed-tickets-{SESSION_ID}")
    counter.unlink(missing_ok=True)
    yield {"HOOK_TEST_ISOLATION": "1", "CLAUDE_PROJECT_DIR": str(tmp_path)}, counter
    counter.unlink(missing_ok=True)


@pytest.fixture
def handoff_env(tmp_path):
    pending = tmp_path / ".claude" / "handoff" / "pending"
    archive = tmp_path / ".claude" / "handoff" / "archive"
    pending.mkdir(parents=True)
    archive.mkdir(parents=True)
    (tmp_path / ".claude" / "hook-logs" / "handoff-cleanup").mkdir(parents=True)
    pf = pending / f"{TICKET_ID}.json"
    pf.write_text("{}")
    env = {"HOOK_TEST_ISOLATION": "1", "CLAUDE_PROJECT_DIR": str(tmp_path)}
    return env, pf


# --- E2：finish 觸發原本對 complete 的處理 ---

def test_lifecycle_finish_emits_checkpoint_without_counting(lifecycle_env):
    env, counter = lifecycle_env
    r = _run(LIFECYCLE, f"ticket track finish {TICKET_ID}", env)
    assert r.returncode == 0
    assert not counter.exists()
    out = json.loads(r.stdout)
    assert out == {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": AskUserQuestionMessages.POST_TICKET_COMPLETE_CHECKPOINT_REMINDER,
        }
    }


def test_handoff_finish_removes_pending_file(handoff_env):
    env, pf = handoff_env
    assert pf.exists()
    r = _run(HANDOFF, f"ticket track finish {TICKET_ID}", env)
    assert r.returncode == 0
    assert not pf.exists()
    assert json.loads(r.stdout) == SUPPRESS_OUTPUT


# --- 回歸：complete / batch-complete 仍處理 ---

def test_handoff_complete_still_removes_pending_file(handoff_env):
    env, pf = handoff_env
    _run(HANDOFF, f"ticket track complete {TICKET_ID}", env)
    assert not pf.exists()


def test_lifecycle_batch_complete_does_not_count(lifecycle_env):
    env, counter = lifecycle_env
    _run(LIFECYCLE, f"ticket track batch-complete {TICKET_ID}", env)
    assert not counter.exists()


# --- 不辨識：引號內字面、heredoc 內文 ---

@pytest.mark.parametrize("command", [
    f'echo "ticket track finish {TICKET_ID}"',
    f"cat <<'EOF'\nticket track finish {TICKET_ID}\nEOF",
])
def test_literal_inside_quote_or_heredoc_not_recognized(lifecycle_env, handoff_env, command):
    env, counter = lifecycle_env
    r = _run(LIFECYCLE, command, env)
    assert json.loads(r.stdout) == DEFAULT_OUTPUT
    assert not counter.exists()

    henv, pf = handoff_env
    _run(HANDOFF, command, henv)
    assert pf.exists()


# --- fail-open：命令無法解析（未閉合引號）維持不處理、不阻擋 ---

def test_unparseable_command_is_noop_and_exit_zero(lifecycle_env, handoff_env):
    command = f'ticket track finish {TICKET_ID} "unclosed'
    env, counter = lifecycle_env
    r = _run(LIFECYCLE, command, env)
    assert r.returncode == 0
    assert json.loads(r.stdout) == DEFAULT_OUTPUT
    assert not counter.exists()

    henv, pf = handoff_env
    r2 = _run(HANDOFF, command, henv)
    assert r2.returncode == 0
    assert pf.exists()
