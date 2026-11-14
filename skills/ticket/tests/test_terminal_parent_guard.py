"""已結案父票的子票寫入守衛測試。

complete 之後若仍能以 create --parent 或 add-child 掛上未完成子票，父票會停在
completed／closed 而底下有 pending 子票（tarrragon/claude#70）。本檔驗證兩個寫入點
在父票 terminal 時拒絕且不寫入，非 terminal 時行為不變。
"""

from unittest.mock import Mock, patch

import pytest

from ticket_system.commands.track_relations import execute_add_child
from ticket_system.lib.terminal_parent_guard import terminal_parent_hint

PARENT_ID = "0.31.0-W4-001"
CHILD_ID = "0.31.0-W4-002"


# ----------------------------------------------------------------------------
# terminal_parent_hint
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["completed", "closed"])
def test_hint_for_terminal_parent_points_to_source_ticket(status):
    hint = terminal_parent_hint(PARENT_ID, {"id": PARENT_ID, "status": status})

    assert hint is not None
    assert status in hint
    assert f"--source-ticket {PARENT_ID}" in hint


@pytest.mark.parametrize("status", ["pending", "in_progress", "blocked"])
def test_no_hint_for_open_parent(status):
    assert terminal_parent_hint(PARENT_ID, {"id": PARENT_ID, "status": status}) is None


def test_no_hint_when_parent_missing():
    """父票讀不到交由呼叫端既有的不存在處理。"""
    assert terminal_parent_hint(PARENT_ID, None) is None


# ----------------------------------------------------------------------------
# create --parent
# ----------------------------------------------------------------------------

def _run_create_child(parent_status: str, monkeypatch):
    """以已結案或未結案父票執行 create --parent，回傳 (exit code, 是否進入 ID 配置)。"""
    from ticket_system.commands import create as create_module
    from tests.test_create_auto_commit import _make_args

    monkeypatch.setattr(
        create_module, "load_ticket",
        lambda version, ticket_id: {"id": ticket_id, "status": parent_status, "children": []},
    )
    reached_allocation = []

    def _stop_at_allocation(*args, **kwargs):
        reached_allocation.append(True)
        raise RuntimeError("stop after guard")

    monkeypatch.setattr(create_module, "resolve_ticket_id_and_wave", _stop_at_allocation)
    try:
        code = create_module.execute(_make_args(parent="0.31.0-W4-001"))
    except RuntimeError:
        code = None
    return code, bool(reached_allocation)


@pytest.mark.parametrize("status", ["completed", "closed"])
def test_create_under_terminal_parent_is_rejected_before_allocation(status, monkeypatch, capsys):
    code, reached_allocation = _run_create_child(status, monkeypatch)

    assert code == 1
    assert reached_allocation is False, "守衛須先於 ID 配置，不得留下半成品子票"
    assert "PARENT_TERMINAL" in capsys.readouterr().out


@pytest.mark.parametrize("status", ["pending", "in_progress"])
def test_create_under_open_parent_passes_guard(status, monkeypatch):
    """回歸：父票未結案時通過守衛，流程照常進入 ID 配置。"""
    _, reached_allocation = _run_create_child(status, monkeypatch)

    assert reached_allocation is True


# ----------------------------------------------------------------------------
# add-child
# ----------------------------------------------------------------------------

def _run_add_child(parent_status: str, tmp_path):
    args = Mock()
    args.parent_id = PARENT_ID
    args.child_id = CHILD_ID
    args.version = "0.31.0"
    tickets = {
        PARENT_ID: {"id": PARENT_ID, "status": parent_status, "children": []},
        CHILD_ID: {"id": CHILD_ID, "status": "pending"},
    }

    def load_side_effect(version, ticket_id):
        return dict(tickets[ticket_id])

    # 父子兩張各自一個鎖檔路徑（同一路徑會被 file_lock 判為同執行緒重入死鎖）
    def path_side_effect(*args):
        return str(tmp_path / f"{args[-1]}.md")

    with patch("ticket_system.commands.track_relations.load_ticket", side_effect=load_side_effect), \
            patch("ticket_system.commands.track_relations.save_ticket") as mock_save, \
            patch("ticket_system.commands.track_relations.get_ticket_path", side_effect=path_side_effect), \
            patch("ticket_system.commands.track_relations.resolve_ticket_path", side_effect=path_side_effect), \
            patch("ticket_system.commands.track_relations.git_utils.commit_ticket_mds_reporting", return_value=False):
        result = execute_add_child(args, "0.31.0")
    return result, mock_save


@pytest.mark.parametrize("status", ["completed", "closed"])
def test_add_child_to_terminal_parent_is_rejected_without_writes(status, capsys, tmp_path):
    result, mock_save = _run_add_child(status, tmp_path)

    assert result == 1
    assert mock_save.call_count == 0
    assert "PARENT_TERMINAL" in capsys.readouterr().out


def _run_set_parent(parent_status: str, tmp_path):
    from ticket_system.commands.track_relations import execute_set_parent

    args = Mock()
    args.child_id = CHILD_ID
    args.new_parent_id = PARENT_ID
    args.clear = False
    args.version = "0.31.0"
    tickets = {
        PARENT_ID: {"id": PARENT_ID, "status": parent_status, "children": []},
        CHILD_ID: {"id": CHILD_ID, "status": "pending", "parent_id": None},
    }

    def path_side_effect(*a):
        return str(tmp_path / f"{a[-1]}.md")

    with patch("ticket_system.commands.track_relations.load_ticket",
               side_effect=lambda v, tid: dict(tickets[tid])), \
            patch("ticket_system.commands.track_relations.save_ticket") as mock_save, \
            patch("ticket_system.commands.track_relations.get_ticket_path", side_effect=path_side_effect), \
            patch("ticket_system.commands.track_relations.resolve_ticket_path", side_effect=path_side_effect), \
            patch("ticket_system.commands.track_relations.git_utils.commit_ticket_mds_reporting", return_value=False):
        result = execute_set_parent(args, "0.31.0")
    return result, mock_save


@pytest.mark.parametrize("status", ["completed", "closed"])
def test_set_parent_to_terminal_parent_is_rejected_without_writes(status, capsys, tmp_path):
    result, mock_save = _run_set_parent(status, tmp_path)

    assert result == 1
    assert mock_save.call_count == 0
    assert "PARENT_TERMINAL" in capsys.readouterr().out


def test_set_parent_to_open_parent_still_writes(tmp_path):
    """回歸：新父票未結案時照常寫入。"""
    result, mock_save = _run_set_parent("in_progress", tmp_path)

    assert result == 0
    assert mock_save.call_count >= 1


@pytest.mark.parametrize("status", ["pending", "in_progress"])
def test_add_child_to_open_parent_still_writes_both(status, tmp_path):
    """回歸：父票未結案時照常寫入父子兩張。"""
    result, mock_save = _run_add_child(status, tmp_path)

    assert result == 0
    assert mock_save.call_count == 2
