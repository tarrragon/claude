"""
Test: session-start-todo-delta-hook（SessionStart，讀取本地 todo pending
登記檔並推送 additionalContext，零 gh 呼叫、零 `todo --json` 呼叫）。

驗證項目：
1. subagent 環境 -> 略過（suppressOutput）
2. source 非 startup/resume -> 略過
3. 登記檔缺失（狀態遺失）-> 全列沉默（suppressOutput，非全列重印）
4. 登記檔存在但 pending 為空 -> 略過
5. pending 非空 -> additionalContext 含項目摘要（正向對照：應印而印）
6. ack 後（sync 移除項目）-> 不再印（正向對照：不該印而沒印）
"""

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = HOOKS_DIR.parent
SCRIPTS_DIR = CLAUDE_DIR / "skills" / "framework-issue" / "scripts"
sys.path.insert(0, str(HOOKS_DIR))
sys.path.insert(0, str(CLAUDE_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import todo_pending_registry as registry  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "session_start_todo_delta_hook",
    HOOKS_DIR / "session-start-todo-delta-hook.py",
)
hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook_module)


class _FakeLogger:
    def debug(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass

    def critical(self, *a, **k):
        pass


def _run_main(monkeypatch, tmp_path, stdin_payload):
    monkeypatch.setattr(hook_module, "setup_hook_logging", lambda name: _FakeLogger())
    monkeypatch.setattr(hook_module, "read_json_from_stdin", lambda logger: stdin_payload)
    monkeypatch.setattr(hook_module, "get_project_root", lambda: tmp_path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = hook_module.main()
    return rc, buf.getvalue()


def _row(來源票="0.1.0-W3-329", 狀態="待裁票"):
    return {
        "來源票": 來源票,
        "做什麼": "做點什麼",
        "acceptance 條數": "3",
        "優先級": "P1",
        "階段": "可立即執行",
        "狀態": 狀態,
    }


def test_subagent_environment_is_skipped(monkeypatch, tmp_path):
    monkeypatch.setattr(hook_module, "is_subagent_environment", lambda payload: True)
    rc, output = _run_main(monkeypatch, tmp_path, {"source": "startup"})
    assert rc == 0
    assert json.loads(output) == {"suppressOutput": True}


def test_non_startup_source_is_skipped(monkeypatch, tmp_path):
    monkeypatch.setattr(hook_module, "is_subagent_environment", lambda payload: False)
    rc, output = _run_main(monkeypatch, tmp_path, {"source": "compact"})
    assert rc == 0
    assert json.loads(output) == {"suppressOutput": True}


def test_missing_registry_degrades_to_silence_not_reprint_all(monkeypatch, tmp_path):
    """狀態遺失（登記檔缺失）—— 依裁定走全列沉默，而非重建 baseline 全列
    重印（重建需呼叫 `todo --json`，違反 SessionStart 零 gh 呼叫的成本
    前提，見 hook 檔頭「退化行為」）。"""
    monkeypatch.setattr(hook_module, "is_subagent_environment", lambda payload: False)
    rc, output = _run_main(monkeypatch, tmp_path, {"source": "startup"})
    assert rc == 0
    assert json.loads(output) == {"suppressOutput": True}


def test_empty_pending_is_skipped(monkeypatch, tmp_path):
    monkeypatch.setattr(hook_module, "is_subagent_environment", lambda payload: False)
    registry.sync_section_rows(33, "owner-1", [], "t1", tmp_path)  # 建立空登記檔
    # sync_section_rows 對空 rows 不會建立任何 pending 項目，但仍應建立
    # schema 正確的登記檔（load_pending 非 None、pending=[]）。
    rc, output = _run_main(monkeypatch, tmp_path, {"source": "startup"})
    assert rc == 0
    assert json.loads(output) == {"suppressOutput": True}


def test_pending_entries_are_printed_in_additional_context(monkeypatch, tmp_path):
    """正向對照：應印而印——寫入端同步了一筆待裁票列，SessionStart 應
    輸出該列摘要。"""
    monkeypatch.setattr(hook_module, "is_subagent_environment", lambda payload: False)
    registry.sync_section_rows(33, "owner-1", [_row()], "t1", tmp_path)

    rc, output = _run_main(monkeypatch, tmp_path, {"source": "startup"})
    assert rc == 0
    payload = json.loads(output)
    assert payload["suppressOutput"] is False
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "0.1.0-W3-329" in context
    assert "#33" in context


def test_acked_entry_is_not_printed(monkeypatch, tmp_path):
    """正向對照：不該印而沒印——同一列狀態已改為「已裁票」（ack），
    SessionStart 不應再輸出它。"""
    monkeypatch.setattr(hook_module, "is_subagent_environment", lambda payload: False)
    registry.sync_section_rows(33, "owner-1", [_row()], "t1", tmp_path)
    registry.sync_section_rows(33, "owner-1", [_row(狀態="已裁票")], "t2", tmp_path)

    rc, output = _run_main(monkeypatch, tmp_path, {"source": "startup"})
    assert rc == 0
    assert json.loads(output) == {"suppressOutput": True}
