"""
Test: branch-verify 與 main-thread-edit-restriction 對 NotebookEdit 的判定與 Edit 相同

NotebookEdit 的路徑欄位是 notebook_path（非 file_path）。兩支守衛原本只受理
Edit、Write 且只讀 file_path，.ipynb 經 NotebookEdit 寫入時不受檢查。

驗證：
1. settings.json 的 NotebookEdit matcher 註冊兩支守衛
2. branch-verify：保護分支上 notebook_path 指向非豁免路徑 → deny（E2 正向對照）；
   豁免路徑與開發分支不輸出決策（與 Edit 相同）
3. main-thread-edit-restriction：notebook_path 指向受限路徑 → deny（E2 正向對照）；
   可寫路徑 → allow
4. Edit 既有判定不變（同一路徑以 file_path 送入，結果與 NotebookEdit 相同）

monkeypatch 皆為 function scope；不呼叫 git 子行程（分支以 monkeypatch 固定）。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
SETTINGS = HOOKS_DIR.parent / "settings.json"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(module, monkeypatch, capsys, payload):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    rc = module.main()
    out = capsys.readouterr().out.strip()
    return rc, (json.loads(out) if out else None)


def _notebook(path: str) -> dict:
    return {"tool_name": "NotebookEdit",
            "tool_input": {"notebook_path": path, "new_source": "x", "edit_mode": "replace"}}


def _edit(path: str) -> dict:
    return {"tool_name": "Edit",
            "tool_input": {"file_path": path, "old_string": "a", "new_string": "b"}}


def _decision(obj):
    return None if obj is None else obj["hookSpecificOutput"].get("permissionDecision")


# ---------- settings.json 註冊 ----------

def test_notebook_edit_matcher_registers_both_guards():
    pre = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    commands = [
        h["command"]
        for block in pre if block.get("matcher") == "NotebookEdit"
        for h in block["hooks"]
    ]
    assert any("branch-verify-hook.py" in c for c in commands)
    assert any("main-thread-edit-restriction-hook.py" in c for c in commands)


# ---------- branch-verify ----------

@pytest.fixture
def branch_verify():
    return _load("branch_verify_notebook", "branch-verify-hook.py")


@pytest.mark.parametrize("payload", [_notebook("lib/a.ipynb"), _edit("lib/a.ipynb")])
def test_branch_verify_protected_non_exempt_denied(branch_verify, monkeypatch, capsys, payload):
    # E2 正向對照：保護分支上非豁免路徑，NotebookEdit 與 Edit 皆 deny（修前 NotebookEdit 不輸出）
    monkeypatch.setattr(branch_verify, "get_current_branch", lambda cwd=None: "main")
    rc, obj = _run(branch_verify, monkeypatch, capsys, payload)
    assert _decision(obj) == "deny"


@pytest.mark.parametrize("payload", [_notebook("docs/a.ipynb"), _edit("docs/a.ipynb")])
def test_branch_verify_protected_exempt_emits_nothing(branch_verify, monkeypatch, capsys, payload):
    monkeypatch.setattr(branch_verify, "get_current_branch", lambda cwd=None: "main")
    rc, obj = _run(branch_verify, monkeypatch, capsys, payload)
    assert rc == 0
    assert obj is None


def test_branch_verify_notebook_on_feature_branch_emits_nothing(branch_verify, monkeypatch, capsys):
    monkeypatch.setattr(branch_verify, "get_current_branch", lambda cwd=None: "feat/x")
    rc, obj = _run(branch_verify, monkeypatch, capsys, _notebook("lib/a.ipynb"))
    assert rc == 0
    assert obj is None


def test_branch_verify_reads_notebook_path_for_branch_lookup(branch_verify, monkeypatch, capsys):
    # 分支查詢的目錄取自 notebook_path（修前 NotebookEdit 在工具過濾即返回，不查分支）
    seen = []
    monkeypatch.setattr(branch_verify, "_resolve_cwd_for_branch_detection",
                        lambda p: seen.append(p) or None)
    monkeypatch.setattr(branch_verify, "get_current_branch", lambda cwd=None: "feat/x")
    _run(branch_verify, monkeypatch, capsys, _notebook("/abs/nb/a.ipynb"))
    assert seen == ["/abs/nb/a.ipynb"]


# ---------- main-thread-edit-restriction ----------

@pytest.fixture
def main_thread(monkeypatch):
    module = _load("main_thread_notebook", "main-thread-edit-restriction-hook.py")
    monkeypatch.setattr(module, "is_subagent_environment", lambda data: False)
    monkeypatch.setattr(module, "_check_dispatch_warning", lambda path, logger: "")
    monkeypatch.setattr(module, "save_check_log", lambda *a, **k: None)
    return module


@pytest.mark.parametrize("payload", [_notebook("src/a.ipynb"), _edit("src/a.ipynb")])
def test_main_thread_restricted_path_denied(main_thread, monkeypatch, capsys, payload):
    # E2 正向對照：受限路徑 NotebookEdit 與 Edit 皆 deny（修前 NotebookEdit 為 allow）
    rc, obj = _run(main_thread, monkeypatch, capsys, payload)
    assert rc == 2
    assert _decision(obj) == "deny"


@pytest.mark.parametrize("payload", [_notebook("docs/a.ipynb"), _edit("docs/a.ipynb")])
def test_main_thread_writable_path_allowed(main_thread, monkeypatch, capsys, payload):
    rc, obj = _run(main_thread, monkeypatch, capsys, payload)
    assert rc == 0
    assert _decision(obj) == "allow"
