"""set-blocked-by 寫入前的循環偵測。

E2（正向對照）：寫入會成環時 rc 非 0、票檔不被保存，含同版本與跨版本。
E1（對照）：無環的合法寫入仍成功；--remove 不做循環檢查。
"""
import argparse
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.commands import track_relations

_LOCK_TARGET = Path(tempfile.gettempdir()) / "set_blocked_by_cycle_lock_target.md"

A = "0.3.1-W1-001"
B = "0.3.1-W1-002"
C = "0.3.1-W1-003"
X = "1.0.0-W1-001"  # 跨版本票


@pytest.fixture(autouse=True)
def _isolate_auto_commit():
    with patch("ticket_system.lib.git_utils._auto_commit_ticket_md", return_value="no_change"):
        yield


def _store(**blocked_by) -> dict:
    """(version, id) -> ticket；blocked_by 以 'A'/'B'/'C'/'X' 鍵覆寫依賴。"""
    ids = {"A": ("0.3.1", A), "B": ("0.3.1", B), "C": ("0.3.1", C), "X": ("1.0.0", X)}
    store = {}
    for key, (version, tid) in ids.items():
        store[(version, tid)] = {"id": tid, "status": "pending", "blockedBy": blocked_by.get(key, [])}
    return store


def _run(store: dict, version: str, target: str, value: str, *, add=False, remove=False):
    def load(v, tid):
        ticket = store.get((v, tid))
        return dict(ticket) if ticket is not None else None

    args = argparse.Namespace(ticket_id=target, value=value, add=add, remove=remove)
    with patch("ticket_system.commands.track_relations.load_ticket", side_effect=load), \
         patch("ticket_system.commands.track_relations.get_ticket_path", return_value=_LOCK_TARGET), \
         patch("ticket_system.commands.track_relations.save_ticket") as mock_save:
        rc = track_relations.execute_set_blocked_by(args, version)
    return rc, mock_save


class TestCycleRejected:
    def test_self_reference_rejected(self, capsys):
        rc, mock_save = _run(_store(), "0.3.1", A, A)
        assert rc != 0
        mock_save.assert_not_called()

    def test_two_node_cycle_rejected(self, capsys):
        # B 已依賴 A；設定 A 依賴 B 會成環 A→B→A
        rc, mock_save = _run(_store(B=[A]), "0.3.1", A, B)
        assert rc != 0
        mock_save.assert_not_called()
        out = capsys.readouterr().out
        assert A in out and B in out

    def test_three_node_cycle_rejected_in_add_mode(self):
        # B→C、C→A；--add A 依賴 B 會成環
        rc, mock_save = _run(_store(B=[C], C=[A]), "0.3.1", A, B, add=True)
        assert rc != 0
        mock_save.assert_not_called()

    def test_cross_version_cycle_rejected(self, capsys):
        # X（1.0.0）依賴 A（0.3.1）；設定 A 依賴 X 會跨版本成環
        rc, mock_save = _run(_store(X=[A]), "0.3.1", A, X)
        assert rc != 0
        mock_save.assert_not_called()
        assert X in capsys.readouterr().out


class TestLegalWriteStillSucceeds:
    def test_acyclic_chain_written(self):
        # B→C；設定 A 依賴 B 無環
        rc, mock_save = _run(_store(B=[C]), "0.3.1", A, B)
        assert rc == 0
        assert mock_save.call_args[0][0]["blockedBy"] == [B]

    def test_cross_version_acyclic_written(self):
        rc, mock_save = _run(_store(), "0.3.1", A, X)
        assert rc == 0
        assert mock_save.call_args[0][0]["blockedBy"] == [X]

    def test_remove_mode_skips_cycle_check(self):
        # 既有資料已含環（A→B、B→A），--remove 移除仍可執行
        rc, mock_save = _run(_store(A=[B], B=[A]), "0.3.1", A, B, remove=True)
        assert rc == 0
        assert mock_save.call_args[0][0]["blockedBy"] == []
