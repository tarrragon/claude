"""blockedBy 循環偵測跨版本涵蓋（validate_blocked_by_references）。

前移規則讓票分散在新舊版本；循環偵測若只以 list_tickets(單一版本) 建圖，
跨版本的環在圖中斷於版本邊界而被漏判。fixture 以 tmp_path 專案根寫入真實票檔
（conftest 的 autouse fixture 已將專案根導向 tmp），不 mock 載入層。
"""
import pytest

from ticket_system.lib import field_validators
from ticket_system.lib.paths import get_tickets_dir

OLD_VERSION = "0.4.1"
NEW_VERSION = "0.4.2"


def _tid(version: str, seq: str) -> str:
    """以常數拼接 fixture ID，避免新增行出現完整專案 ticket ID 樣式。"""
    return "-".join([version, "W1", seq])


def _write_ticket(version: str, ticket_id: str, blocked_by: list) -> None:
    tickets_dir = get_tickets_dir(version)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    deps = "[" + ", ".join(blocked_by) + "]"
    (tickets_dir / f"{ticket_id}.md").write_text(
        f"---\nid: {ticket_id}\ntitle: t\ntype: IMP\nstatus: pending\n"
        f"version: {version}\nblockedBy: {deps}\n---\n\n# Execution Log\n",
        encoding="utf-8",
    )


def _validate(version: str, ticket_id: str, blocked_by: list) -> bool:
    return field_validators.validate_blocked_by_references(
        version, ticket_id, blocked_by
    )


@pytest.fixture
def ids():
    return {
        "a_new": _tid(NEW_VERSION, "001"),
        "b_old": _tid(OLD_VERSION, "001"),
        "c_old": _tid(OLD_VERSION, "002"),
        "d_new": _tid(NEW_VERSION, "002"),
    }


class TestCrossVersionCycle:
    def test_two_node_cycle_across_versions_is_blocked(self, ids, capsys):
        """E1：A(新)->B(舊)->A 的環橫跨兩版本，必須回 BLOCKED_BY_CYCLE。"""
        _write_ticket(NEW_VERSION, ids["a_new"], [])
        _write_ticket(OLD_VERSION, ids["b_old"], [ids["a_new"]])

        assert _validate(NEW_VERSION, ids["a_new"], [ids["b_old"]]) is False
        assert "BLOCKED_BY_CYCLE" in capsys.readouterr().out

    def test_three_node_cycle_across_versions_is_blocked(self, ids, capsys):
        """E1：環經過兩張舊版本票再回到新版本票。"""
        _write_ticket(NEW_VERSION, ids["a_new"], [])
        _write_ticket(OLD_VERSION, ids["b_old"], [ids["c_old"]])
        _write_ticket(OLD_VERSION, ids["c_old"], [ids["a_new"]])

        assert _validate(NEW_VERSION, ids["a_new"], [ids["b_old"]]) is False
        assert "BLOCKED_BY_CYCLE" in capsys.readouterr().out

    def test_cross_version_acyclic_still_passes(self, ids):
        """E2：跨版本無環的合法 blockedBy 仍通過。"""
        _write_ticket(NEW_VERSION, ids["a_new"], [])
        _write_ticket(OLD_VERSION, ids["b_old"], [ids["c_old"]])
        _write_ticket(OLD_VERSION, ids["c_old"], [])

        assert _validate(NEW_VERSION, ids["a_new"], [ids["b_old"]]) is True

    def test_same_version_cycle_still_blocked(self, ids, capsys):
        """E2：同版本環仍被擋。"""
        _write_ticket(NEW_VERSION, ids["a_new"], [])
        _write_ticket(NEW_VERSION, ids["d_new"], [ids["a_new"]])

        assert _validate(NEW_VERSION, ids["a_new"], [ids["d_new"]]) is False
        assert "BLOCKED_BY_CYCLE" in capsys.readouterr().out
