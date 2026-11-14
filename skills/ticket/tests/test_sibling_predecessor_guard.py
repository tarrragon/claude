"""兄弟前驅數寫入點檢查測試（ARCH-017）。

規則：同一父票下，一張票的 blockedBy 至多含一個兄弟票；寫入後達 2 個且並非全為
終態時，create、set-blocked-by、set-parent、add-child 拒絕寫入。每個寫入點都含
正向對照輸入（該擋的）與反向對照輸入（該放的），符合 E2。
"""

from unittest.mock import Mock, patch

import pytest

from ticket_system.lib import sibling_predecessor_guard as guard

PARENT = "0.0.0-W1-001"
A = "0.0.0-W1-001.1"
B = "0.0.0-W1-001.2"
T = "0.0.0-W1-001.3"
OTHER_PARENT = "0.0.0-W1-002"
X = "0.0.0-W1-002.1"


def _world(a_status="pending", b_status="pending", t_blocked=None, t_parent=PARENT,
           parent_children=(A, B, T)):
    return {
        PARENT: {"id": PARENT, "status": "in_progress", "children": list(parent_children)},
        OTHER_PARENT: {"id": OTHER_PARENT, "status": "in_progress", "children": [X]},
        A: {"id": A, "status": a_status, "parent_id": PARENT, "blockedBy": []},
        B: {"id": B, "status": b_status, "parent_id": PARENT, "blockedBy": []},
        T: {"id": T, "status": "pending", "parent_id": t_parent, "blockedBy": list(t_blocked or [])},
        X: {"id": X, "status": "pending", "parent_id": OTHER_PARENT, "blockedBy": []},
    }


def _loader(world):
    return lambda tid: dict(world[tid]) if tid in world else None


# ----------------------------------------------------------------------------
# 判定函式
# ----------------------------------------------------------------------------

def test_two_open_sibling_predecessors_is_violation():
    world = _world()
    violations = guard.find_violations(T, [A, B], PARENT, _loader(world))
    assert violations == [(T, [A, B])]


def test_single_sibling_predecessor_passes():
    world = _world()
    assert guard.find_violations(T, [A], PARENT, _loader(world)) == []


def test_non_sibling_predecessor_not_counted():
    world = _world()
    assert guard.find_violations(T, [A, X], PARENT, _loader(world)) == []


def test_all_terminal_sibling_predecessors_pass():
    """與 hook 條件 1 一致：前驅皆終態時結構已不影響排程。"""
    world = _world(a_status="completed", b_status="closed")
    assert guard.find_violations(T, [A, B], PARENT, _loader(world)) == []


def test_partially_terminal_predecessors_still_violation():
    world = _world(a_status="completed")
    assert guard.find_violations(T, [A, B], PARENT, _loader(world)) == [(T, [A, B])]


def test_no_parent_skips():
    world = _world()
    assert guard.find_violations(T, [A, B], None, _loader(world)) == []


def test_new_ticket_not_yet_in_children_is_checked():
    """create 時新票尚未列在父票 children，仍以父票 children 判定前驅是否為兄弟。"""
    world = _world(parent_children=(A, B))
    new_id = "0.0.0-W1-001.9"
    assert guard.find_violations(new_id, [A, B], PARENT, _loader(world)) == [(new_id, [A, B])]


def test_moving_ticket_into_parent_checks_siblings_that_depend_on_it():
    """set-parent 把 X 移入 PARENT：B 原依賴 A，又依賴 X，移入後 B 有 2 個兄弟前驅。"""
    world = _world(parent_children=(A, B))
    world[B]["blockedBy"] = [A, X]
    violations = guard.find_violations(X, [], PARENT, _loader(world))
    assert violations == [(B, [A, X])]


def test_load_exception_is_fail_open_with_stderr(capsys):
    def broken_loader(tid):
        raise OSError("disk gone")

    hint = guard.check_sibling_predecessors(T, [A, B], PARENT, broken_loader, "未修改")
    assert hint is None
    assert "兄弟前驅檢查失敗" in capsys.readouterr().err


def test_hint_names_predecessors_and_arch_017():
    world = _world()
    hint = guard.check_sibling_predecessors(T, [A, B], PARENT, _loader(world), "本票未建立")
    assert A in hint and B in hint
    assert "ARCH-017" in hint
    assert "本票未建立" in hint


# ----------------------------------------------------------------------------
# 寫入點：set-blocked-by
# ----------------------------------------------------------------------------

def _run_set_blocked_by(world, value, tmp_path, add=False, remove=False):
    from ticket_system.commands.track_relations import execute_set_blocked_by

    args = Mock()
    args.ticket_id = T
    args.value = value
    args.add = add
    args.remove = remove
    args.version = "0.0.0"

    def path_side_effect(*a):
        return str(tmp_path / f"{a[-1]}.md")

    with patch("ticket_system.commands.track_relations.load_ticket",
               side_effect=lambda v, tid: dict(world[tid]) if tid in world else None), \
            patch("ticket_system.commands.track_relations.save_ticket") as mock_save, \
            patch("ticket_system.commands.track_relations.get_ticket_path", side_effect=path_side_effect), \
            patch("ticket_system.commands.track_relations.resolve_ticket_path", side_effect=path_side_effect), \
            patch("ticket_system.commands.track_relations.git_utils.commit_ticket_md_reporting", return_value=False), \
            patch("ticket_system.commands.track_relations.hint_blocked_by_ana"):
        result = execute_set_blocked_by(args, "0.0.0")
    return result, mock_save


def test_set_blocked_by_two_siblings_rejected_without_write(tmp_path, capsys):
    result, mock_save = _run_set_blocked_by(_world(), f"{A} {B}", tmp_path)
    assert result == 1
    assert mock_save.call_count == 0
    assert "BLOCKED_BY_MULTI_SIBLING" in capsys.readouterr().out


def test_set_blocked_by_add_second_sibling_rejected(tmp_path, capsys):
    result, mock_save = _run_set_blocked_by(_world(t_blocked=[A]), B, tmp_path, add=True)
    assert result == 1
    assert mock_save.call_count == 0


def test_set_blocked_by_single_sibling_written(tmp_path):
    result, mock_save = _run_set_blocked_by(_world(), A, tmp_path)
    assert result == 0
    assert mock_save.call_count == 1


def test_set_blocked_by_remove_not_checked(tmp_path):
    """--remove 只會減少結構；既有違規票也能拆掉依賴。"""
    result, mock_save = _run_set_blocked_by(_world(t_blocked=[A, B, X]), X, tmp_path, remove=True)
    assert result == 0
    assert mock_save.call_count == 1


# ----------------------------------------------------------------------------
# 寫入點：set-parent、add-child
# ----------------------------------------------------------------------------

def _patched_relations(world, tmp_path):
    def path_side_effect(*a):
        return str(tmp_path / f"{a[-1]}.md")

    return [
        patch("ticket_system.commands.track_relations.load_ticket",
              side_effect=lambda v, tid: dict(world[tid]) if tid in world else None),
        patch("ticket_system.commands.track_relations.get_ticket_path", side_effect=path_side_effect),
        patch("ticket_system.commands.track_relations.resolve_ticket_path", side_effect=path_side_effect),
        patch("ticket_system.commands.track_relations.git_utils.commit_ticket_mds_reporting", return_value=False),
    ]


def _run_reparent(command, world, tmp_path):
    from ticket_system.commands import track_relations

    args = Mock()
    args.version = "0.0.0"
    if command == "set-parent":
        args.child_id = T
        args.new_parent_id = PARENT
        args.clear = False
        func = track_relations.execute_set_parent
    else:
        args.parent_id = PARENT
        args.child_id = T
        func = track_relations.execute_add_child

    patches = _patched_relations(world, tmp_path)
    for p in patches:
        p.start()
    try:
        with patch("ticket_system.commands.track_relations.save_ticket") as mock_save:
            result = func(args, "0.0.0")
    finally:
        for p in patches:
            p.stop()
    return result, mock_save


@pytest.mark.parametrize("command", ["set-parent", "add-child"])
def test_reparent_creating_multi_sibling_rejected(command, tmp_path, capsys):
    world = _world(t_blocked=[A, B], t_parent=OTHER_PARENT, parent_children=(A, B))
    result, mock_save = _run_reparent(command, world, tmp_path)
    assert result == 1
    assert mock_save.call_count == 0
    assert "BLOCKED_BY_MULTI_SIBLING" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["set-parent", "add-child"])
def test_reparent_with_single_sibling_predecessor_written(command, tmp_path):
    world = _world(t_blocked=[A], t_parent=OTHER_PARENT, parent_children=(A, B))
    result, mock_save = _run_reparent(command, world, tmp_path)
    assert result == 0
    assert mock_save.call_count >= 2


# ----------------------------------------------------------------------------
# 寫入點：create
# ----------------------------------------------------------------------------

def _run_create_validation(world, blocked_by, parent=PARENT):
    from ticket_system.commands import create as create_module

    config = {"blocked_by": blocked_by, "parent_id": parent, "title": "t", "what": "w", "when": "v"}
    with patch.object(create_module, "load_ticket",
                      side_effect=lambda v, tid: dict(world[tid]) if tid in world else None), \
            patch.object(create_module, "validate_blocked_by_references", return_value=True), \
            patch.object(create_module, "enforce_blocking_duplicate", return_value=True), \
            patch.object(create_module, "detect_duplicate_tickets"), \
            patch.object(create_module, "check_when_blocked_by_consistency"):
        return create_module._validate_before_persist("0.0.0", "0.0.0-W1-001.9", config)


def test_create_with_two_sibling_predecessors_rejected(capsys):
    assert _run_create_validation(_world(parent_children=(A, B)), [A, B]) is False
    assert "BLOCKED_BY_MULTI_SIBLING" in capsys.readouterr().out


def test_create_with_single_sibling_predecessor_passes():
    assert _run_create_validation(_world(parent_children=(A, B)), [A]) is True


def test_create_root_ticket_with_blockers_passes():
    assert _run_create_validation(_world(), [A, B], parent=None) is True
