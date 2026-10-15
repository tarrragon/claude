"""提醒類 hook 改走 additionalContext 的觸發 / 非觸發分支測試。

涵蓋 deletion-residual-reference、worklog-path-guard、uc-fingerprint-drift-check、
suggest-compact（PreToolUse）。install-guide 見 test_install_guide_edit_reminder_hook.py。
觸發分支斷言 stdout 單一 JSON 含 additionalContext 且 stderr 無提醒；
非觸發分支斷言 stdout 無輸出（E2 正向對照）。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
SUGGEST_PATH = CLAUDE_DIR / "skills" / "strategic-compact" / "suggest-compact.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ctx(out: str, event: str) -> str:
    data = json.loads(out)  # 單一 JSON：多份會在此失敗
    hso = data["hookSpecificOutput"]
    assert hso["hookEventName"] == event
    return hso["additionalContext"]


def _stdin(monkeypatch, payload) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


# === deletion-residual-reference ===

DELETION = HOOKS_DIR / "deletion-residual-reference-hook.py"


def test_deletion_residual_triggers_additional_context(monkeypatch, tmp_path, capsys):
    hook = _load(DELETION, "deletion_residual_hook")
    f = tmp_path / "a.md"
    f.write_text("保留段落 FooBarMarker 仍在這裡被引用\n", encoding="utf-8")
    old = "FooBarMarker 是被刪除的長說明文字" + "填充內容" * 20
    _stdin(monkeypatch, {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(f), "old_string": old, "new_string": ""},
    })
    assert hook.main() == 0
    cap = capsys.readouterr()
    ctx = _ctx(cap.out, "PostToolUse")
    assert "IMP-042" in ctx and "FooBarMarker" in ctx
    assert "IMP-042" not in cap.err


def test_deletion_residual_no_trigger_no_output(monkeypatch, tmp_path, capsys):
    hook = _load(DELETION, "deletion_residual_hook2")
    f = tmp_path / "a.md"
    f.write_text("完全無關內容\n", encoding="utf-8")
    _stdin(monkeypatch, {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(f), "old_string": "short", "new_string": "x"},
    })
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


# === worklog-path-guard ===

WORKLOG = HOOKS_DIR / "worklog-path-guard-hook.py"


def test_worklog_guard_triggers_additional_context(monkeypatch, capsys):
    hook = _load(WORKLOG, "worklog_guard_hook")
    _stdin(monkeypatch, {
        "tool_name": "Write",
        "tool_input": {"file_path": "docs/work-logs/v0.1.0-release.md"},
    })
    assert hook.main() == 0
    cap = capsys.readouterr()
    assert "Worklog 檔案路徑不正確" in _ctx(cap.out, "PostToolUse")
    assert "Worklog 檔案路徑不正確" not in cap.err


def test_worklog_guard_correct_path_no_output(monkeypatch, capsys):
    hook = _load(WORKLOG, "worklog_guard_hook2")
    _stdin(monkeypatch, {
        "tool_name": "Write",
        "tool_input": {"file_path": "docs/work-logs/v0.1.0/v0.1.0-release.md"},
    })
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


# === uc-fingerprint-drift-check ===

UC = HOOKS_DIR / "uc-fingerprint-drift-check-hook.py"


def test_uc_drift_triggers_additional_context(monkeypatch, tmp_path, capsys):
    hook = _load(UC, "uc_drift_hook")
    import doc_system.core.uc_registry as reg

    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(reg, "get_fingerprint_sidecar_path", lambda root: sidecar)
    monkeypatch.setattr(reg, "check_fingerprints", lambda root: (["UC-01"], ["UC-09"], []))
    _stdin(monkeypatch, {
        "tool_name": "Edit",
        "tool_input": {"file_path": "docs/app-use-cases.md"},
    })
    assert hook.main() == 0
    cap = capsys.readouterr()
    ctx = _ctx(cap.out, "PostToolUse")
    assert "UC-01" in ctx and "UC-09" in ctx
    assert "uc-fingerprint-drift-check" not in cap.err


def test_uc_drift_no_drift_no_output(monkeypatch, tmp_path, capsys):
    hook = _load(UC, "uc_drift_hook2")
    import doc_system.core.uc_registry as reg

    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(reg, "get_fingerprint_sidecar_path", lambda root: sidecar)
    monkeypatch.setattr(reg, "check_fingerprints", lambda root: ([], [], []))
    _stdin(monkeypatch, {
        "tool_name": "Edit",
        "tool_input": {"file_path": "docs/app-use-cases.md"},
    })
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


# === suggest-compact（PreToolUse） ===


@pytest.fixture
def suggest(monkeypatch, tmp_path):
    # 計數檔以 payload session_id 分檔，位於 <專案>/.claude/hook-state/（0.5.0-W1-324）；
    # 專案目錄與舊 /tmp 清理目錄皆導向 tmp_path，避免觸及真實檔案
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    legacy = tmp_path / "legacy-tmp"
    legacy.mkdir()
    monkeypatch.setenv("SUGGEST_COMPACT_LEGACY_TMP_DIR", str(legacy))
    mod = _load(SUGGEST_PATH, "suggest_compact_mod")
    counter = tmp_path / ".claude" / "hook-state" / "compact-count-s1"
    counter.parent.mkdir(parents=True)
    yield mod, counter


def test_suggest_compact_threshold_emits_pretooluse_context(suggest, monkeypatch, capsys):
    mod, counter = suggest
    monkeypatch.setenv("COMPACT_THRESHOLD", "3")
    counter.write_text("2")
    _stdin(monkeypatch, {"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": "s1"})
    mod.main()
    cap = capsys.readouterr()
    assert "StrategicCompact" in _ctx(cap.out, "PreToolUse")
    assert "StrategicCompact" not in cap.err


def test_suggest_compact_below_threshold_no_output(suggest, monkeypatch, capsys):
    mod, counter = suggest
    monkeypatch.setenv("COMPACT_THRESHOLD", "3")
    counter.write_text("0")
    _stdin(monkeypatch, {"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": "s1"})
    mod.main()
    assert capsys.readouterr().out == ""
    assert counter.read_text().strip() == "1"


def test_suggest_compact_subagent_filtered(suggest, monkeypatch, capsys):
    mod, counter = suggest
    monkeypatch.setenv("COMPACT_THRESHOLD", "3")
    counter.write_text("2")
    _stdin(monkeypatch, {"tool_name": "Edit", "agent_id": "sub-1", "session_id": "s1"})
    mod.main()
    out = capsys.readouterr().out
    assert "StrategicCompact" not in out
