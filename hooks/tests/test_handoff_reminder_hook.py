"""
handoff-reminder-hook 測試（W17-095.3）

驗證 stale handoff 過濾與 reminder 訊息「已過濾 N 個 stale」提示。
"""

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch


HOOK_PATH = Path(__file__).parent.parent.parent / "skills" / "ticket" / "hooks" / "handoff-reminder-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location("handoff_reminder_hook", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_handoff(handoff_dir: Path, name: str, payload: dict) -> None:
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def _make_record(
    ticket_id: str,
    direction: str = "auto",
    from_status: str = "in_progress",
    title: str = "測試任務",
    timestamp: str = "2026-05-02T10:00:00",
):
    return {
        "ticket_id": ticket_id,
        "from_ticket": ticket_id,
        "title": title,
        "direction": direction,
        "from_status": from_status,
        "timestamp": timestamp,
        "what": "test",
        "chain": {},
        "resumed_at": None,
    }


def _scan(hook, project_root: Path, stale_map: dict):
    """以 stale_map（檔名 stem -> (is_stale, reason)）替身呼叫 scan。"""

    def fake_is_stale(record, project_root=None):
        ticket_id = record.get("ticket_id") or record.get("from_ticket") or ""
        return stale_map.get(ticket_id, (False, ""))

    with patch.object(hook, "is_handoff_stale", side_effect=fake_is_stale):
        return hook.scan_handoff_pending_directory(project_root, MagicMock())


def test_filters_stale_task_chain_target_started():
    """情境 1：3 個 handoff，1 個 task chain target started → 過濾 1，剩 2，stale_count=1"""
    hook = load_hook_module()
    with TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        handoff_dir = project_root / ".claude" / "handoff" / "pending"
        _write_handoff(handoff_dir, "T-001", _make_record("T-001", direction="to-sibling:T-999"))
        _write_handoff(handoff_dir, "T-002", _make_record("T-002", direction="auto"))
        _write_handoff(handoff_dir, "T-003", _make_record("T-003", direction="auto"))

        pending, stale_count = _scan(
            hook,
            project_root,
            {"T-001": (True, "任務鏈目標 T-999 已 in_progress")},
        )

        assert stale_count == 1
        assert len(pending) == 2
        ids = {t["ticket_id"] for t in pending}
        assert ids == {"T-002", "T-003"}


def test_filters_stale_non_chain_source_completed():
    """情境 2：非任務鏈 + from_ticket completed → 過濾，stale_count=1"""
    hook = load_hook_module()
    with TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        handoff_dir = project_root / ".claude" / "handoff" / "pending"
        _write_handoff(handoff_dir, "T-100", _make_record("T-100", direction="auto", from_status="completed"))
        _write_handoff(handoff_dir, "T-200", _make_record("T-200", direction="auto"))

        pending, stale_count = _scan(
            hook,
            project_root,
            {"T-100": (True, "來源 ticket T-100 已 completed")},
        )

        assert stale_count == 1
        assert len(pending) == 1
        assert pending[0]["ticket_id"] == "T-200"


def test_no_stale_returns_zero_count():
    """情境 3：全部非 stale → stale_count == 0，pending_tasks 全保留"""
    hook = load_hook_module()
    with TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        handoff_dir = project_root / ".claude" / "handoff" / "pending"
        _write_handoff(handoff_dir, "T-A", _make_record("T-A"))
        _write_handoff(handoff_dir, "T-B", _make_record("T-B"))

        pending, stale_count = _scan(hook, project_root, {})

        assert stale_count == 0
        assert len(pending) == 2


# ===== 0.2.1-W3-308: 顯示/排序路徑統一以 target 為對象 =====


def test_scan_source_completed_explicit_target_displays_target_id_and_title():
    """來源已 completed + 顯式 target_ticket_id → 顯示 target 的 ID 與 title。"""
    hook = load_hook_module()
    with TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        handoff_dir = project_root / ".claude" / "handoff" / "pending"
        record = _make_record(
            "0.2.1-W3-304", direction="next", from_status="completed",
            title="來源票的標題",
        )
        record["target_ticket_id"] = "0.2.1-W3-294"
        _write_handoff(handoff_dir, "0.2.1-W3-304", record)

        fake_path = project_root / "target.md"
        fake_path.write_text("---\ntitle: target 的標題\n---\n")

        with patch.object(hook, "is_handoff_stale", return_value=(False, "")), \
             patch.object(hook, "find_ticket_file", return_value=fake_path), \
             patch.object(
                 hook, "parse_ticket_frontmatter",
                 return_value={"title": "target 的標題"},
             ):
            pending, stale_count = hook.scan_handoff_pending_directory(
                project_root, MagicMock()
            )

    assert stale_count == 0
    assert len(pending) == 1
    assert pending[0]["ticket_id"] == "0.2.1-W3-294", "應顯示 target 而非來源票"
    assert pending[0]["title"] == "target 的標題", "應顯示 target 的 title"


def test_scan_direction_auto_fallback_uses_ticket_id_as_target():
    """direction=auto 記錄的 ticket_id 欄位本身即 target，須靠 fallback 正確顯示。"""
    hook = load_hook_module()
    with TemporaryDirectory() as tmp:
        project_root = Path(tmp)
        handoff_dir = project_root / ".claude" / "handoff" / "pending"
        _write_handoff(
            handoff_dir, "0.2.1-W3-500",
            _make_record("0.2.1-W3-500", direction="auto", title="auto 任務標題"),
        )

        with patch.object(hook, "is_handoff_stale", return_value=(False, "")):
            pending, stale_count = hook.scan_handoff_pending_directory(
                project_root, MagicMock()
            )

    assert stale_count == 0
    assert len(pending) == 1
    assert pending[0]["ticket_id"] == "0.2.1-W3-500"
    assert pending[0]["title"] == "auto 任務標題"


def test_reminder_message_includes_filtered_count():
    """情境 4：reminder 訊息含「已過濾 N 個 stale handoff」字樣"""
    hook = load_hook_module()
    pending = [
        {"ticket_id": "T-001", "title": "demo", "direction": "auto"},
    ]
    msg = hook.generate_reminder_message(pending, MagicMock(), stale_count=3)

    assert "已過濾 3 個 stale handoff" in msg
    assert "T-001" in msg

    # stale_count=0 時不顯示過濾訊息（避免噪音）
    msg_zero = hook.generate_reminder_message(pending, MagicMock(), stale_count=0)
    assert "已過濾" not in msg_zero
