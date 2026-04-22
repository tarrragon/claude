"""
handoff-prompt-reminder-hook tests.
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock


HOOK_PATH = Path(__file__).parent.parent / "handoff-prompt-reminder-hook.py"


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "handoff_prompt_reminder_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
