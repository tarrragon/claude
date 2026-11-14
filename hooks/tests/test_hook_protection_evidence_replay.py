"""28 組證據回放：過渡期放行當下的票面，在放寬後的辨識下是否仍缺證據。

fixture（fixtures/evidence_replay_cases.json）自足，執行時不讀 git 歷史。
每組斷言：
1. missing_evidence_categories 對該類別的判定與 expect_pass 相符
2. 原有判定 _strict_missing_evidence 下該類別都缺（證明是過渡期放行的案例）
"""

import json
import sys
from pathlib import Path

import pytest

_hooks_dir = Path(__file__).parent.parent
if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))

import acceptance_checkers.hook_protection_acceptance_checker as mod  # noqa: E402

_FIXTURE = Path(__file__).parent / "fixtures" / "evidence_replay_cases.json"
_CASES = json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _body(case: dict) -> str:
    return (
        "## Solution\n" + case["solution"] + "\n\n"
        "## Test Results\n" + case["test_results"] + "\n"
    )


def test_fixture_has_28_cases_18_pass():
    # 18 通過、10 判缺：liveness 輸出只寫在 acceptance 的 1 組判缺（acceptance
    # 只承認失敗語意宣告），acceptance 已寫 fail-open 加觸發條件的 2 組通過
    assert len(_CASES) == 28
    assert sum(c["expect_pass"] for c in _CASES) == 18


@pytest.mark.parametrize("case", _CASES, ids=[c["case"] for c in _CASES])
def test_replay_matches_expectation(case):
    missing = mod.missing_evidence_categories(
        _body(case), case["acceptance"], tuple(case["hook_names"])
    )
    still_missing = case["category"] in missing
    assert still_missing is (not case["expect_pass"])


@pytest.mark.parametrize("case", _CASES, ids=[c["case"] for c in _CASES])
def test_replay_was_missing_under_strict_rule(case):
    evidence = "\n".join(
        mod._extract_section(_body(case), n) for n in mod._EVIDENCE_SECTION_NAMES
    )
    assert case["category"] in mod._strict_missing_evidence(evidence)
