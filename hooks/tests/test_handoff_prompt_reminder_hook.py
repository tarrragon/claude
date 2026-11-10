"""
handoff-prompt-reminder-hook tests.
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


HOOK_PATH = Path(__file__).parent.parent.parent / "skills" / "ticket" / "hooks" / "handoff-prompt-reminder-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "handoff_prompt_reminder_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_handoff(handoff_dir: Path, name: str, payload: dict) -> None:
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_reminder_message_points_to_runqueue_entry():
    hook = load_hook_module()
    message = hook.generate_reminder_message(
        [
            {
                "ticket_id": "0.18.0-W17-001",
                "title": "測試任務",
                "direction": "next",
            }
        ],
        project_root=Path("."),
        logger=MagicMock(),
    )

    assert "/ticket                                  查看 scheduler 接手建議" in message
    assert "ticket track runqueue --context=resume --top 3" in message
    assert "/ticket resume <id>" in message
    assert "/ticket resume --list" not in message


# ===== 0.2.1-W3-308: pending_tasks 顯示/排序統一以 target 為對象 =====


def test_scan_source_completed_explicit_target_displays_target_id_and_title(tmp_path):
    """來源已 completed + 顯式 target_ticket_id → 顯示 target 的 ID 與 title。"""
    hook = load_hook_module()
    handoff_dir = tmp_path / ".claude" / "handoff" / "pending"
    record = {
        "ticket_id": "0.2.1-W3-304",
        "target_ticket_id": "0.2.1-W3-294",
        "direction": "next",
        "title": "來源票的標題",
        "resumed_at": None,
    }
    _write_handoff(handoff_dir, "0.2.1-W3-304", record)

    target_path = tmp_path / "target.md"
    target_path.write_text("---\ntitle: target 的標題\n---\n")

    with patch.object(hook, "resolve_ticket_path", return_value=target_path), \
         patch.object(hook, "is_ticket_completed", return_value=False), \
         patch.object(
             hook, "parse_ticket_frontmatter",
             return_value={"title": "target 的標題"},
         ):
        pending_tasks = hook.scan_handoff_pending_directory(tmp_path, MagicMock())

    assert len(pending_tasks) == 1
    assert pending_tasks[0]["ticket_id"] == "0.2.1-W3-294", "應顯示 target 而非來源票"
    assert pending_tasks[0]["title"] == "target 的標題", "應顯示 target 的 title"


def test_scan_direction_auto_fallback_uses_ticket_id_as_target(tmp_path):
    """direction=auto 記錄的 ticket_id 欄位本身即 target，須靠 fallback 正確顯示。"""
    hook = load_hook_module()
    handoff_dir = tmp_path / ".claude" / "handoff" / "pending"
    record = {
        "ticket_id": "0.2.1-W3-500",
        "direction": "auto",
        "title": "auto 任務標題",
        "resumed_at": None,
    }
    _write_handoff(handoff_dir, "0.2.1-W3-500", record)

    target_path = tmp_path / "auto-target.md"
    target_path.write_text("---\ntitle: auto 任務標題\n---\n")

    with patch.object(hook, "resolve_ticket_path", return_value=target_path), \
         patch.object(hook, "is_ticket_completed", return_value=False):
        pending_tasks = hook.scan_handoff_pending_directory(tmp_path, MagicMock())

    assert len(pending_tasks) == 1
    assert pending_tasks[0]["ticket_id"] == "0.2.1-W3-500"
    assert pending_tasks[0]["title"] == "auto 任務標題"
