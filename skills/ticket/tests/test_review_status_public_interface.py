"""0.5.0-W1-247：lifecycle 只經 phase4_review_checker 的公開介面判定 Review Status。"""

import logging
import re
import sys
from pathlib import Path

import pytest

from ticket_system.commands import lifecycle
from ticket_system.commands.lifecycle import _judge_review_status

_HOOKS_DIR = Path(lifecycle.__file__).resolve().parents[4] / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
from acceptance_checkers.phase4_review_checker import (  # noqa: E402
    check_phase4_review_evidence,
    has_phase4_review_evidence,
)

_WITH = "---\nid: x\n---\n## Solution\n\n### Phase 4 結論\n重構需要：否\n"
_WITHOUT = "---\nid: x\n---\n## Solution\n\n只有實作說明\n"
_NO_SOLUTION = "---\nid: x\n---\n## Problem Analysis\n\nfoo\n"


def test_lifecycle_does_not_reference_checker_private_functions():
    src = Path(lifecycle.__file__).read_text(encoding="utf-8")
    assert not re.search(r"\bp4\._\w+|phase4_review_checker\._\w+", src)


@pytest.mark.parametrize("body", [_WITH, _WITHOUT, _NO_SOLUTION])
def test_gate_and_complete_agree(body):
    gate_passes = (
        check_phase4_review_evidence(body, "IMP", logging.getLogger("t")) is None
    )
    status = _judge_review_status({"type": "IMP", "_body": body})
    assert has_phase4_review_evidence(body) == (status == "reviewed")
    if "## Solution" in body:
        assert gate_passes == (status == "reviewed")
