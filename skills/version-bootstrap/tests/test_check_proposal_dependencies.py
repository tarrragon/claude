"""check_proposal_dependencies 單元測試。

以 0.4.0-W1-001 實際發生的排序矛盾（PROP-010 依賴 PROP-011 卻排入更早版本）
作為回歸測試案例，確認 pipeline Step 1 能在提案確認階段攔截此類矛盾。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_proposal_dependencies import check_dependencies, normalize_version  # noqa: E402


def _todolist(version: str, proposals: list[str]) -> dict:
    return {"versions": [{"version": version, "proposals": proposals}]}


def test_normalize_version_strips_v_prefix():
    assert normalize_version("v0.4.0") == (0, 4, 0)
    assert normalize_version("0.4.0") == (0, 4, 0)


def test_normalize_version_comparable():
    assert normalize_version("0.5.0") > normalize_version("0.4.0")


def test_detects_0_4_0_prop010_prop011_contradiction():
    """還原 0.4.0-W1-001 事故：PROP-010 依賴 PROP-011，但排入更早版本。"""
    todolist = _todolist("0.4.0", ["PROP-008", "PROP-010"])
    tracking = {
        "proposals": {
            "PROP-008": {"target_version": "v0.4.0"},
            "PROP-010": {"target_version": "v0.4.0", "depends_on": ["PROP-011"]},
            "PROP-011": {"target_version": "v0.5.0"},
        }
    }

    warnings = check_dependencies(todolist, tracking, "0.4.0")

    assert len(warnings) == 1
    assert "PROP-010" in warnings[0]
    assert "PROP-011" in warnings[0]


def test_no_warning_when_dependency_scheduled_before():
    """依賴排在同版或更早版本時不應告警（正確排序）。"""
    todolist = _todolist("0.5.0", ["PROP-010", "PROP-011"])
    tracking = {
        "proposals": {
            "PROP-010": {"target_version": "v0.5.0", "depends_on": ["PROP-011"]},
            "PROP-011": {"target_version": "v0.5.0"},
        }
    }

    warnings = check_dependencies(todolist, tracking, "0.5.0")

    assert warnings == []


def test_no_warning_when_no_depends_on_field():
    """未定義 depends_on 的提案（多數情況）不受影響。"""
    todolist = _todolist("0.3.0", ["PROP-003"])
    tracking = {"proposals": {"PROP-003": {"target_version": "v0.3.0"}}}

    warnings = check_dependencies(todolist, tracking, "0.3.0")

    assert warnings == []


def test_warns_when_proposal_missing_from_tracking():
    todolist = _todolist("0.6.0", ["PROP-099"])
    tracking = {"proposals": {}}

    warnings = check_dependencies(todolist, tracking, "0.6.0")

    assert len(warnings) == 1
    assert "PROP-099" in warnings[0]


def test_warns_when_dependency_missing_from_tracking():
    todolist = _todolist("0.6.0", ["PROP-020"])
    tracking = {
        "proposals": {"PROP-020": {"target_version": "v0.6.0", "depends_on": ["PROP-021"]}}
    }

    warnings = check_dependencies(todolist, tracking, "0.6.0")

    assert len(warnings) == 1
    assert "PROP-021" in warnings[0]
