"""
test_enum_gate
==============

save_ticket 落盤前枚舉驗證閘的行為測試（寫入邊界收斂）。

覆蓋設計測試案例（W5-005.1 Solution 第五節；案例 5 狀態轉移屬 lifecycle
接線票，不在本檔）：
1. 化石豁免：載入含正典外值的既有票，未觸碰該欄位的寫入不觸發警告
2. changed-only：同票將欄位改為另一非法值 → 觸發
3. 合法寫入：改為正典值 → 無警告落盤
4. 新建票（無載入快照）：非法值全欄位驗證觸發；合法值通過
6. warn / deny 模式：warn 記錄後照常落盤；deny raise 且不落盤、dict 恢復

環境：autouse `_isolate_project_root` 將 CLAUDE_PROJECT_DIR 導向 tmp，
get_ticket_path / get_project_root（enum-gate.log 落點）皆解析於隔離 root。
"""
import os
from pathlib import Path

import pytest

from ticket_system import constants as ticket_constants
from ticket_system.lib.parser import (
    ENUM_SNAPSHOT_FIELD,
    EnumGateViolation,
    load_ticket,
    save_ticket,
)
from ticket_system.lib.paths import get_ticket_path

_VERSION = "9.9.9"


def _write_ticket_file(ticket_id: str, priority: str = "P9") -> Path:
    """在隔離 root 下寫入含指定 priority 的最小合法 ticket 檔。"""
    path = get_ticket_path(_VERSION, ticket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: enum gate fixture\n"
        "type: IMP\n"
        "status: pending\n"
        f"priority: {priority}\n"
        "what: 原始描述\n"
        "---\n\n# Execution Log\n",
        encoding="utf-8",
    )
    return path


def _gate_log_path() -> Path:
    return Path(os.environ["CLAUDE_PROJECT_DIR"]) / ".claude" / "hook-logs" / "enum-gate.log"


# ---------------------------------------------------------------------------
# 案例 1：化石豁免——未觸碰的正典外欄位不驗
# ---------------------------------------------------------------------------


def test_fossil_field_untouched_no_warn(capsys):
    path = _write_ticket_file("9.9.9-W1-001", priority="P9")
    ticket = load_ticket(_VERSION, "9.9.9-W1-001")
    assert ticket[ENUM_SNAPSHOT_FIELD]["priority"] == "P9"

    ticket["what"] = "只改 what，不碰 priority"
    save_ticket(ticket, path)

    assert "[enum-gate" not in capsys.readouterr().err
    assert "priority: P9" in path.read_text(encoding="utf-8")
    assert not _gate_log_path().exists()


# ---------------------------------------------------------------------------
# 案例 2：changed-only——改為另一非法值觸發 warn（照常落盤 + 記錄）
# ---------------------------------------------------------------------------


def test_changed_to_invalid_triggers_warn_and_log(monkeypatch, capsys):
    monkeypatch.setattr(ticket_constants, "ENUM_GATE_MODE", "warn")
    path = _write_ticket_file("9.9.9-W1-002", priority="P9")
    ticket = load_ticket(_VERSION, "9.9.9-W1-002")

    ticket["priority"] = "P8"
    save_ticket(ticket, path)

    err = capsys.readouterr().err
    assert "[enum-gate:warn]" in err
    assert "priority" in err
    # warn 模式照常落盤
    assert "priority: P8" in path.read_text(encoding="utf-8")
    # 量測日誌落點與內容
    log_content = _gate_log_path().read_text(encoding="utf-8")
    assert "9.9.9-W1-002" in log_content
    assert "'P8'" in log_content


# ---------------------------------------------------------------------------
# 案例 3：合法寫入無警告
# ---------------------------------------------------------------------------


def test_valid_change_no_warn(capsys):
    path = _write_ticket_file("9.9.9-W1-003", priority="P9")
    ticket = load_ticket(_VERSION, "9.9.9-W1-003")

    ticket["priority"] = "P1"
    save_ticket(ticket, path)

    assert "[enum-gate" not in capsys.readouterr().err
    assert "priority: P1" in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 案例 4：新建票（無快照）全欄位驗證
# ---------------------------------------------------------------------------


def test_new_ticket_dict_invalid_type_warns(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ticket_constants, "ENUM_GATE_MODE", "warn")
    ticket = {
        "id": "9.9.9-W1-004",
        "type": "INV",  # 化石 type，新建票不可用
        "status": "pending",
        "priority": "P2",
        "_body": "# Execution Log\n",
    }
    save_ticket(ticket, tmp_path / "9.9.9-W1-004.md")

    err = capsys.readouterr().err
    assert "[enum-gate:warn]" in err
    assert "type" in err


def test_new_ticket_dict_all_valid_no_warn(tmp_path, capsys):
    ticket = {
        "id": "9.9.9-W1-005",
        "type": "IMP",
        "status": "pending",
        "priority": "P2",
        "_body": "# Execution Log\n",
    }
    save_ticket(ticket, tmp_path / "9.9.9-W1-005.md")
    assert "[enum-gate" not in capsys.readouterr().err


def test_missing_enum_fields_not_validated(tmp_path, capsys):
    """欄位缺席屬必填檢查職責（checklist/auditor），非枚舉閘範圍。"""
    ticket = {"id": "9.9.9-W1-006", "what": "無三枚舉欄位", "_body": ""}
    save_ticket(ticket, tmp_path / "9.9.9-W1-006.md")
    assert "[enum-gate" not in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 案例 6：deny 模式——raise、不落盤、dict 恢復
# ---------------------------------------------------------------------------


def test_deny_mode_blocks_write_and_restores_dict(monkeypatch, capsys):
    monkeypatch.setattr(ticket_constants, "ENUM_GATE_MODE", "deny")
    path = _write_ticket_file("9.9.9-W1-007", priority="P9")
    ticket = load_ticket(_VERSION, "9.9.9-W1-007")

    ticket["priority"] = "P8"
    with pytest.raises(EnumGateViolation) as exc_info:
        save_ticket(ticket, path)

    # 不落盤：檔案維持載入前狀態
    assert "priority: P9" in path.read_text(encoding="utf-8")
    # dict 欄位由 finally 恢復（_body/_path/快照仍在，呼叫端物件完整）
    assert "_body" in ticket
    assert "_path" in ticket
    assert ticket[ENUM_SNAPSHOT_FIELD]["priority"] == "P9"
    # 違規明細可供呼叫端消費
    fields = [v[0] for v in exc_info.value.violations]
    assert fields == ["priority"]
    # deny 同樣記錄量測日誌與 stderr
    assert "[enum-gate:deny]" in capsys.readouterr().err
    assert "deny" in _gate_log_path().read_text(encoding="utf-8")


def test_deny_mode_valid_write_unaffected(monkeypatch, capsys):
    monkeypatch.setattr(ticket_constants, "ENUM_GATE_MODE", "deny")
    path = _write_ticket_file("9.9.9-W1-008", priority="P9")
    ticket = load_ticket(_VERSION, "9.9.9-W1-008")

    ticket["priority"] = "P0"
    save_ticket(ticket, path)

    assert "[enum-gate" not in capsys.readouterr().err
    assert "priority: P0" in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 快照生命週期：成功落盤後刷新（同 dict 重複 save 不重複告警）
# ---------------------------------------------------------------------------


def test_snapshot_refreshed_after_successful_save(monkeypatch, capsys):
    monkeypatch.setattr(ticket_constants, "ENUM_GATE_MODE", "warn")
    path = _write_ticket_file("9.9.9-W1-009", priority="P9")
    ticket = load_ticket(_VERSION, "9.9.9-W1-009")

    ticket["priority"] = "P7"
    save_ticket(ticket, path)  # 第一次：warn
    first_err = capsys.readouterr().err
    assert "[enum-gate:warn]" in first_err

    save_ticket(ticket, path)  # ���再變更：快照已刷新，不重複告警
    assert "[enum-gate" not in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 案例 5：狀態轉移矩陣（STATUS_TRANSITIONS 接線）
# ---------------------------------------------------------------------------


def _write_ticket_with_status(ticket_id: str, status: str) -> Path:
    path = get_ticket_path(_VERSION, ticket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: {ticket_id}\n"
        "title: transition fixture\n"
        "type: IMP\n"
        f"status: {status}\n"
        "priority: P2\n"
        "---\n\n# Execution Log\n",
        encoding="utf-8",
    )
    return path


def test_completed_to_pending_transition_warns(monkeypatch, capsys):
    """設計案例 5：completed 票未經 release 直改 pending → 觸發。"""
    monkeypatch.setattr(ticket_constants, "ENUM_GATE_MODE", "warn")
    path = _write_ticket_with_status("9.9.9-W2-001", "completed")
    ticket = load_ticket(_VERSION, "9.9.9-W2-001")

    ticket["status"] = "pending"
    save_ticket(ticket, path)

    err = capsys.readouterr().err
    assert "[enum-gate:warn]" in err
    assert "轉移" in err
    # warn 模式照常落盤
    assert "status: pending" in path.read_text(encoding="utf-8")
    # 量測日誌帶 transition kind
    assert "transition" in _gate_log_path().read_text(encoding="utf-8")


def test_legal_transitions_no_warn(capsys):
    """合法邊（claim / complete 對應轉移）不觸發。"""
    path = _write_ticket_with_status("9.9.9-W2-002", "pending")
    ticket = load_ticket(_VERSION, "9.9.9-W2-002")
    ticket["status"] = "in_progress"  # claim 對應邊
    save_ticket(ticket, path)
    assert "[enum-gate" not in capsys.readouterr().err

    ticket["status"] = "completed"  # complete 對應邊（快照已刷新為 in_progress）
    save_ticket(ticket, path)
    assert "[enum-gate" not in capsys.readouterr().err


def test_fossil_old_status_transition_skipped(capsys):
    """舊態為化石值（skipped）→ 轉移檢查跳過；矯正回正典態不觸發任何告警。"""
    path = _write_ticket_with_status("9.9.9-W2-003", "skipped")
    ticket = load_ticket(_VERSION, "9.9.9-W2-003")

    ticket["status"] = "closed"
    save_ticket(ticket, path)

    assert "[enum-gate" not in capsys.readouterr().err
    assert "status: closed" in path.read_text(encoding="utf-8")


def test_invalid_new_status_flagged_once_as_enum(monkeypatch, capsys):
    """新態非正典 → 僅枚舉違規一筆，不重複計轉移違規。"""
    monkeypatch.setattr(ticket_constants, "ENUM_GATE_MODE", "warn")
    path = _write_ticket_with_status("9.9.9-W2-004", "completed")
    ticket = load_ticket(_VERSION, "9.9.9-W2-004")

    ticket["status"] = "weird_status"
    save_ticket(ticket, path)

    err = capsys.readouterr().err
    assert err.count("[enum-gate:warn]") == 1
    assert "不在正典" in err
    assert "轉移" not in err


def test_deny_mode_blocks_illegal_transition(monkeypatch, capsys):
    monkeypatch.setattr(ticket_constants, "ENUM_GATE_MODE", "deny")
    path = _write_ticket_with_status("9.9.9-W2-005", "completed")
    ticket = load_ticket(_VERSION, "9.9.9-W2-005")

    ticket["status"] = "pending"
    with pytest.raises(EnumGateViolation) as exc_info:
        save_ticket(ticket, path)

    assert "status: completed" in path.read_text(encoding="utf-8")  # 不落盤
    kinds = [v[4] for v in exc_info.value.violations]
    assert kinds == ["transition"]
    assert "[enum-gate:deny]" in capsys.readouterr().err
