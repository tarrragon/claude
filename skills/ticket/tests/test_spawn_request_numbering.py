"""add-spawn-request 編號只取 Spawn Requests 章節的結構化條目。"""

import re

from ticket_system.commands.track_acceptance import _next_spawn_request_number
from ticket_system.lib.section_locator import find_section


def _next_for(body: str) -> int:
    match = find_section(body, "Spawn Requests")
    content = match.content if match.found else ""
    return _next_spawn_request_number(content)


_SOLUTION = "## Solution\n\n草稿提到 SR-9 與 - **SR-7** 內文。\n\n"


def test_prose_mention_ignored_when_section_empty():
    body = _SOLUTION + "## Spawn Requests\n\n（無）\n"
    assert _next_for(body) == 1


def test_missing_section_starts_at_one():
    assert _next_for(_SOLUTION) == 1


def test_structured_entries_increment():
    body = (
        _SOLUTION
        + "## Spawn Requests\n\n"
        + "- **SR-1** (t)\n  - status: pending\n"
        + "- **SR-2** (t)\n  - status: pending\n  - context: 參照 SR-40\n"
    )
    assert _next_for(body) == 3


def test_resolve_entry_lookup_ignores_prose_mention():
    """resolve 以章節內行首 `- **SR-N**` 定位，正文提及不會命中。"""
    body = _SOLUTION + "## Spawn Requests\n\n- **SR-1** (t)\n  - status: pending\n"
    content = find_section(body, "Spawn Requests").content
    pattern = rf"^- \*\*{re.escape('SR-9')}\*\*"
    assert re.search(pattern, content, re.MULTILINE) is None
