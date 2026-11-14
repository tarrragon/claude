"""
提醒受眾含模型的 hook 改走 additionalContext（3.3.0-W1-213.13）。

exit 0 的 stderr 模型看不到。skill-body-size-check、uv-tool-ownership-guard 的提醒
影響模型接下來的判斷，改經 emit_model_reminder 輸出 additionalContext；stderr 保留給用戶。
沒有提醒時不輸出任何內容（不帶 permissionDecision）。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load(name: str, filename: str):
    for p in (str(HOOKS_DIR), str(HOOKS_DIR.parent)):
        if p not in sys.path:
            sys.path.insert(0, p)
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    # dataclass 搭配延後註解需在 sys.modules 查得到模組
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _hso(out: str):
    out = out.strip()
    return json.loads(out)["hookSpecificOutput"] if out else None


# ---------- skill-body-size-check ----------

def _skill(root: Path, name: str, lines: int) -> None:
    d = root / ".claude" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text("x\n" * lines, encoding="utf-8")


def test_skill_body_size_over_threshold_reaches_model(tmp_path, monkeypatch, capsys):
    hook = _load("sbs_audience", "skill-body-size-check-hook.py")
    _skill(tmp_path, "big", hook.LINE_THRESHOLD + 10)
    monkeypatch.setattr(hook, "get_code_root", lambda: str(tmp_path))
    assert hook.main() == 0
    captured = capsys.readouterr()
    hso = _hso(captured.out)
    assert hso["hookEventName"] == "SessionStart"
    assert "big" in hso["additionalContext"]
    assert "permissionDecision" not in hso
    assert "big" in captured.err  # 用戶管道保留


def test_skill_body_size_within_threshold_emits_nothing(tmp_path, monkeypatch, capsys):
    hook = _load("sbs_audience_ok", "skill-body-size-check-hook.py")
    _skill(tmp_path, "small", 3)
    monkeypatch.setattr(hook, "get_code_root", lambda: str(tmp_path))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


# ---------- uv-tool-ownership-guard ----------

def _run_uv(hook, monkeypatch, payload):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return hook.main()


def test_uv_tool_drift_reaches_model(tmp_path, monkeypatch, capsys):
    hook = _load("uv_audience_drift", "uv-tool-ownership-guard-hook.py")
    monkeypatch.setattr(hook, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(hook, "_scan_candidate_skills", lambda root: {"ghost-skill": "ghost"})
    assert _run_uv(hook, monkeypatch, {"hook_event_name": "SessionStart"}) == 0
    hso = _hso(capsys.readouterr().out)
    assert hso["hookEventName"] == "SessionStart"
    assert "ghost-skill" in hso["additionalContext"]


def test_uv_tool_reinstall_notice_reaches_model(tmp_path, monkeypatch, capsys):
    hook = _load("uv_audience_reinstall", "uv-tool-ownership-guard-hook.py")
    monkeypatch.setattr(hook, "get_project_root", lambda: tmp_path)
    skill = hook.SKILLS[0]

    def fake_guard(command, project_root, logger):
        hook._notify(f"[OwnershipGuard] {skill.cli_name} reinstall 失敗: boom")

    with patch.object(hook, "_guard_command", side_effect=fake_guard):
        rc = _run_uv(hook, monkeypatch, {
            "hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": f"{skill.cli_name} --help"},
        })
    assert rc == 0
    hso = _hso(capsys.readouterr().out)
    assert hso["hookEventName"] == "PreToolUse"
    assert "reinstall 失敗" in hso["additionalContext"]
    assert "permissionDecision" not in hso


def test_uv_tool_no_notes_emits_nothing(tmp_path, monkeypatch, capsys):
    hook = _load("uv_audience_quiet", "uv-tool-ownership-guard-hook.py")
    monkeypatch.setattr(hook, "get_project_root", lambda: tmp_path)
    assert _run_uv(hook, monkeypatch, {
        "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "tool_input": {"command": "ls"},
    }) == 0
    assert capsys.readouterr().out == ""
