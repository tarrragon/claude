"""
version-release-guard-hook 提醒輸出管道測試

警告走 PreToolUse additionalContext（模型可見），且只輸出單一 JSON；
stderr 不得有提醒。非觸發分支維持 decision approve 且無 additionalContext（E2 對照）。
"""

import contextlib
import importlib.util
import io
import json
from pathlib import Path

_HOOK_FILE = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "version-release-guard-hook.py"
)
_spec = importlib.util.spec_from_file_location(
    "version_release_guard_hook_emit", _HOOK_FILE
)
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def _run(monkeypatch, command, version_check=(True, "1.0.0"), via_script=False):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    monkeypatch.setattr(hook, "read_hook_input", lambda: payload)
    monkeypatch.setattr(hook, "check_pubspec_version", lambda logger: version_check)
    monkeypatch.setattr(hook, "is_via_version_release_script", lambda logger: via_script)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = hook.main()
    return code, json.loads(out.getvalue()), err.getvalue()


def test_release_commit_without_script_emits_additional_context(monkeypatch):
    code, out, err = _run(monkeypatch, 'git commit -m "feat(v1.2.3): x"')
    assert code == 0
    assert err == ""
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert "Version Release Guard" in hso["additionalContext"]
    assert "v1.2.3" in hso["additionalContext"]
    # E1：核准決策與提醒同一份 JSON，權限語意不變（原 decision=approve）
    assert hso["permissionDecision"] == "allow"


def test_version_mismatch_is_appended_to_same_output(monkeypatch):
    code, out, err = _run(
        monkeypatch,
        'git commit -m "feat(v1.2.3): x"',
        version_check=(False, "版本不一致: a"),
    )
    assert code == 0
    assert err == ""
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "版本不一致" in ctx
    assert "建議使用正式版本發布流程" in ctx
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_version_mismatch_alone_emits_when_via_script(monkeypatch):
    code, out, err = _run(
        monkeypatch,
        'git commit -m "feat(v1.2.3): x"',
        version_check=(False, "版本不一致: a"),
        via_script=True,
    )
    assert code == 0 and err == ""
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "版本不一致" in ctx
    assert "建議使用正式版本發布流程" not in ctx
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_clean_release_commit_has_no_context(monkeypatch):
    code, out, err = _run(monkeypatch, 'git commit -m "feat(v1.2.3): x"', via_script=True)
    assert code == 0 and err == ""
    assert out == {"decision": "approve"}


def test_non_release_command_has_no_context(monkeypatch):
    code, out, err = _run(monkeypatch, "git status")
    assert code == 0 and err == ""
    assert out == {"decision": "approve"}
