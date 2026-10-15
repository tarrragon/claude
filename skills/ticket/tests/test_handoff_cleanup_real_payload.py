"""handoff-cleanup-hook 以真實 payload 形狀觸發的測試。

真實 Bash PostToolUse 的 tool_response 只有 stdout、stderr、interrupted、isImage、
noOutputExpected，沒有 exit_code。斷言具體副作用：handoff 檔是否被刪。
"""
import importlib.util
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CLAUDE_DIR))

TID = "0.1.0-W41-002"


def _load():
    path = CLAUDE_DIR / "skills" / "ticket" / "hooks" / "handoff-cleanup-hook.py"
    spec = importlib.util.spec_from_file_location("handoff_cleanup_hook_real", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def real_response(stdout, interrupted=False):
    return {"stdout": stdout, "stderr": "", "interrupted": interrupted,
            "isImage": False, "noOutputExpected": False}


def run(tmp_path, tool_response, command=f"ticket track complete {TID}"):
    pending = tmp_path / ".claude" / "handoff" / "pending"
    pending.mkdir(parents=True)
    (tmp_path / ".claude" / "hook-logs" / "handoff-cleanup").mkdir(parents=True)
    f = pending / f"{TID}.json"
    f.write_text("{}", encoding="utf-8")
    data = {"tool_name": "Bash", "tool_input": {"command": command},
            "tool_response": tool_response}
    with patch.object(hook, "read_json_from_stdin", return_value=data), \
         patch.object(hook, "is_subagent_environment", return_value=False), \
         patch.object(hook, "get_project_root", return_value=tmp_path), \
         patch("sys.stdout", StringIO()):
        rc = hook.main()
    return rc, f


def test_real_payload_success_deletes_handoff(tmp_path):
    rc, f = run(tmp_path, real_response(f"[OK] 已完成 Ticket {TID}"))
    assert rc == 0
    assert not f.exists()


def test_real_payload_finish_deletes_handoff(tmp_path):
    rc, f = run(tmp_path, real_response(f"[OK] 已完成 Ticket {TID}"),
                command=f"ticket track finish {TID}")
    assert rc == 0 and not f.exists()


def test_real_payload_failure_keeps_handoff(tmp_path):
    # 286.3：未遮蔽命令走第 1 層即成功；失敗回音只對被遮蔽的命令（管線／分號）生效
    rc, f = run(tmp_path, real_response("[Error] 無法完成"),
                command=f"ticket track complete {TID} 2>&1 | tail -5")
    assert rc == 0 and f.exists()


def test_unmasked_redirected_output_deletes_handoff(tmp_path):
    """286.3：輸出被重導向吸走（stdout 空）的未遮蔽命令仍判成功。"""
    rc, f = run(tmp_path, real_response(""),
                command=f"ticket track complete {TID} > /dev/null 2>&1")
    assert rc == 0 and not f.exists()


def test_masked_swallowed_output_with_verifier_true_deletes_handoff(tmp_path):
    """被遮蔽且輸出被吸走：completed 驗證器為真即判成功。"""
    with patch.object(hook, "make_completed_verifier", return_value=lambda: True):
        rc, f = run(tmp_path, real_response(""),
                    command=f"out=$(ticket track complete {TID} 2>&1); rc=$?")
    assert rc == 0 and not f.exists()


def test_masked_swallowed_output_with_verifier_false_keeps_handoff(tmp_path):
    """E1 對照：同一命令，驗證器為假（票未完成）-> 不清理。"""
    with patch.object(hook, "make_completed_verifier", return_value=lambda: False):
        rc, f = run(tmp_path, real_response(""),
                    command=f"out=$(ticket track complete {TID} 2>&1); rc=$?")
    assert rc == 0 and f.exists()


def test_masked_without_marker_and_unreadable_ticket_keeps_handoff(tmp_path):
    """被遮蔽且輸出被吸走、驗證器讀不到票（tmp 專案無票）：退回標記，無標記即不清理。"""
    rc, f = run(tmp_path, real_response(""),
                command=f"out=$(ticket track complete {TID} 2>&1); rc=$?")
    assert rc == 0 and f.exists()


def test_interrupted_keeps_handoff(tmp_path):
    rc, f = run(tmp_path, real_response(f"[OK] 已完成 {TID}", interrupted=True))
    assert rc == 0 and f.exists()


@pytest.mark.parametrize("code,deleted", [(0, True), (75, True), (1, False)])
def test_legacy_exit_code_compat(tmp_path, code, deleted):
    resp = dict(real_response(f"[OK] 已完成 {TID}"), exit_code=code)
    rc, f = run(tmp_path, resp)
    assert rc == 0 and (not f.exists()) is deleted


@pytest.mark.parametrize("resp", ["[OK] 已完成", None, 42, ["x"]])
def test_non_dict_response_fail_open(tmp_path, resp):
    rc, f = run(tmp_path, resp)
    assert rc == 0 and f.exists()
