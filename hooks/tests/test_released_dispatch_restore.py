"""已釋放派發條目的放回點：子代理人自身的 PreToolUse(Bash) 事件（3.4.0-W1-122）

- dispatch_tracker.restore_released_by_agent_id：payload agent_id 與釋放紀錄的 agent_id 完全相等時放回
- released-dispatch-restore-hook：掛在 PreToolUse:Bash 分派群組第一位，先於 bare-commit-guard、
  workspace-wipe-guard 執行；失敗時 fail-open（不 deny），寫 stderr 與日誌

背景：3.3.0-W1-120.2 只在 PostToolUse(SendMessage) 放回；代理人因背景工作完成而恢復時不經
SendMessage，恢復後的 Bash 寫入落在守衛視野外。實機觀測（本票 Solution）：子代理人 payload 的
agent_id 與 spawn 回傳 ID 逐字相同。
"""

import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_HOOKS_DIR.parent))
sys.path.insert(0, str(_HOOKS_DIR))

from lib import dispatch_tracker as dt  # noqa: E402
from lib.dispatch_tracker import (  # noqa: E402
    get_active_dispatches,
    get_state_file_path,
    record_dispatch,
    release_dispatch,
)

_spec = importlib.util.spec_from_file_location(
    "released_dispatch_restore_hook", _HOOKS_DIR / "released-dispatch-restore-hook.py"
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

SID = "sess-me"
AGENT_ID = "aprobe122n-19ba327d5504f786"


@pytest.fixture
def root():
    dt.reset_cache()
    with tempfile.TemporaryDirectory() as tmpdir:
        r = Path(tmpdir)
        (r / ".claude").mkdir()
        yield r
    dt.reset_cache()


def _released(root, agent_id=AGENT_ID, handle="probe122n"):
    """寫一筆回合已結束的條目並釋放。"""
    record_dispatch(
        root, agent_description="desc", agent_id=agent_id, agent_handle=handle,
        session_id=SID, ticket_id="", branch_name="", work_checkout=str(root),
    )
    state = json.loads(get_state_file_path(root).read_text(encoding="utf-8"))
    state["dispatches"][-1]["turn_ended_at"] = "2026-11-19T00:00:00+00:00"
    get_state_file_path(root).write_text(json.dumps(state), encoding="utf-8")
    dt.reset_cache()
    status, _ = release_dispatch(root, handle, SID)
    assert status == dt.RELEASE_OK


# ---------------------------------------------------------------------------
# restore_released_by_agent_id
# ---------------------------------------------------------------------------


class TestRestoreByAgentId:
    def test_exact_agent_id_restores(self, root):
        _released(root)
        entry = dt.restore_released_by_agent_id(root, AGENT_ID)
        assert entry is not None and entry["agent_id"] == AGENT_ID
        active = get_active_dispatches(root)
        assert [d["agent_id"] for d in active] == [AGENT_ID]
        assert active[0]["turn_ended_at"] is None and "resumed_at" in active[0]

    @pytest.mark.parametrize("other", [AGENT_ID[:-1], AGENT_ID + "0", "probe122n", ""])
    def test_non_equal_id_does_not_restore(self, root, other):
        """完全相等才放回：前綴、延長、handle、空字串都不算"""
        _released(root)
        assert dt.restore_released_by_agent_id(root, other) is None
        assert get_active_dispatches(root) == []

    def test_no_release_record_writes_nothing(self, root):
        record_dispatch(
            root, agent_description="d", agent_id=AGENT_ID, agent_handle="h",
            session_id=SID, ticket_id="", branch_name="", work_checkout=str(root),
        )
        before = get_state_file_path(root).read_text(encoding="utf-8")
        assert dt.restore_released_by_agent_id(root, AGENT_ID) is None
        assert get_state_file_path(root).read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# hook
# ---------------------------------------------------------------------------


def _run(monkeypatch, root, payload):
    monkeypatch.setattr(_hook, "get_project_root", lambda: root)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return _hook.main()


def _payload(agent_id=AGENT_ID):
    p = {"session_id": SID, "hook_event_name": "PreToolUse", "tool_name": "Bash",
         "tool_input": {"command": "git status"}}
    if agent_id is not None:
        p["agent_id"] = agent_id
    return p


class TestHook:
    def test_e1_subagent_first_bash_restores_entry(self, root, monkeypatch, capsys):
        """E1：同一份已釋放狀態，子代理人 payload 放回條目；主線程 payload（無 agent_id）不放回"""
        _released(root)
        assert _run(monkeypatch, root, _payload(agent_id=None)) == 0
        assert get_active_dispatches(root) == []
        assert _run(monkeypatch, root, _payload()) == 0
        assert [d["agent_id"] for d in get_active_dispatches(root)] == [AGENT_ID]
        assert capsys.readouterr().out.strip() == ""  # 不輸出決策，不影響同群組其他守衛

    def test_main_thread_skips_state_io(self, root, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("主線程不應讀狀態檔")

        monkeypatch.setattr(_hook, "restore_released_by_agent_id", boom)
        assert _run(monkeypatch, root, _payload(agent_id=None)) == 0

    def test_restore_failure_fails_open_and_is_visible(self, root, monkeypatch, capsys):
        def boom(*a, **k):
            raise OSError("injected")

        monkeypatch.setattr(_hook, "restore_released_by_agent_id", boom)
        assert _run(monkeypatch, root, _payload()) == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == ""  # 不 deny
        assert "injected" in captured.err

    def test_non_bash_tool_skipped(self, root, monkeypatch):
        _released(root)
        payload = dict(_payload(), tool_name="Edit")
        assert _run(monkeypatch, root, payload) == 0
        assert get_active_dispatches(root) == []


# ---------------------------------------------------------------------------
# 分派群組位置
# ---------------------------------------------------------------------------


def test_registered_first_in_pre_tool_use_bash_group_within_budget():
    """排第一位：dispatcher 序列段依 registry 順序執行，放回先於 bare-commit-guard、workspace-wipe-guard"""
    registry = json.loads((_HOOKS_DIR / "hook-dispatch-registry.json").read_text(encoding="utf-8"))
    group = registry["groups"]["PreToolUse:Bash"]
    first = group["hooks"][0]
    assert first["path"] == ".claude/hooks/released-dispatch-restore-hook.py"
    assert float(first.get("timeout", 60)) <= float(group["budget"])
    names = [h["path"].rsplit("/", 1)[-1] for h in group["hooks"]]
    for guard in ("bare-commit-guard-hook.py", "workspace-wipe-guard-hook.py"):
        assert names.index(guard) > 0, guard
