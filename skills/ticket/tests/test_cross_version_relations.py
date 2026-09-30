"""關聯寫入端跨版本測試：以被引用 ID 自身版本驗證存在性。

涵蓋 set-related-to、set-blocked-by、create --blocked-by（validate_blocked_by_references）。
替身以 (version, id) 為鍵：只有以被引用 ID 自身版本載入才會命中。
"""
import argparse
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.commands import track_relations
from ticket_system.lib import field_validators

_LOCK_TARGET = Path(tempfile.gettempdir()) / "w1006_1_test_lock_target.md"


@pytest.fixture(autouse=True)
def _isolate_auto_commit():
    """本檔測項使用虛構票檔路徑，不驗證提交行為；隔離真實 git 呼叫。
    提交失敗語意見 tests/test_write_command_autocommit_scope.py。"""
    with patch("ticket_system.lib.git_utils._auto_commit_ticket_md", return_value="no_change"):
        yield

OLD_ID = "0.3.1-W1-001"
NEW_ID = "1.0.0-W1-001"
GHOST_OLD = "0.3.1-W1-999"
GHOST_NEW = "1.0.0-W1-999"


def _store() -> dict:
    """(version, id) -> ticket；僅兩張真實存在的票。"""
    return {
        ("0.3.1", OLD_ID): {"id": OLD_ID, "status": "pending", "blockedBy": [], "relatedTo": []},
        ("1.0.0", NEW_ID): {"id": NEW_ID, "status": "pending", "blockedBy": [], "relatedTo": []},
    }


def _loader(store: dict):
    def load(version, ticket_id):
        ticket = store.get((version, ticket_id))
        return dict(ticket) if ticket is not None else None
    return load


def _run_set(field_name: str, version: str, target: str, value: str):
    args = argparse.Namespace(ticket_id=target, value=value, add=False, remove=False)
    runner = (
        track_relations.execute_set_related_to
        if field_name == "relatedTo"
        else track_relations.execute_set_blocked_by
    )
    with patch("ticket_system.commands.track_relations.load_ticket", side_effect=_loader(_store())), \
         patch("ticket_system.commands.track_relations.get_ticket_path", return_value=_LOCK_TARGET), \
         patch("ticket_system.commands.track_relations.save_ticket") as mock_save:
        rc = runner(args, version)
    return rc, mock_save


@pytest.mark.parametrize("field_name", ["relatedTo", "blockedBy"])
class TestSetRelationCrossVersion:
    def test_old_version_references_new_version(self, field_name):
        rc, mock_save = _run_set(field_name, "0.3.1", OLD_ID, NEW_ID)
        assert rc == 0
        assert mock_save.call_args[0][0][field_name] == [NEW_ID]

    def test_new_version_references_old_version(self, field_name):
        rc, mock_save = _run_set(field_name, "1.0.0", NEW_ID, OLD_ID)
        assert rc == 0
        assert mock_save.call_args[0][0][field_name] == [OLD_ID]

    def test_truly_missing_cross_version_id_still_fails(self, field_name, capsys):
        rc, mock_save = _run_set(field_name, "0.3.1", OLD_ID, GHOST_NEW)
        assert rc == 1
        mock_save.assert_not_called()
        assert GHOST_NEW in capsys.readouterr().out

    def test_truly_missing_same_version_id_still_fails(self, field_name):
        rc, mock_save = _run_set(field_name, "0.3.1", OLD_ID, GHOST_OLD)
        assert rc == 1
        mock_save.assert_not_called()


class TestCreateBlockedByCrossVersion:
    @staticmethod
    def _validate(version: str, new_ticket_id: str, blocked_by: list[str]) -> bool:
        with patch("ticket_system.lib.field_validators.load_ticket", side_effect=_loader(_store())), \
             patch("ticket_system.lib.field_validators.list_tickets", return_value=[]):
            return field_validators.validate_blocked_by_references(
                version, new_ticket_id, blocked_by
            )

    def test_old_version_blocked_by_new_version(self):
        assert self._validate("0.3.1", "0.3.1-W2-001", [NEW_ID]) is True

    def test_new_version_blocked_by_old_version(self):
        assert self._validate("1.0.0", "1.0.0-W2-001", [OLD_ID]) is True

    def test_truly_missing_cross_version_id_still_fails(self, capsys):
        assert self._validate("0.3.1", "0.3.1-W2-001", [GHOST_NEW]) is False
        assert "BLOCKED_BY_NOT_FOUND" in capsys.readouterr().out

    def test_truly_missing_same_version_id_still_fails(self):
        assert self._validate("0.3.1", "0.3.1-W2-001", [GHOST_OLD]) is False


class TestResolveReferenceVersion:
    def test_uses_own_version_prefix(self):
        assert field_validators.resolve_reference_version("0.3.1", NEW_ID) == "1.0.0"

    def test_falls_back_when_no_version_prefix(self):
        assert field_validators.resolve_reference_version("0.3.1", "legacy-id") == "0.3.1"
