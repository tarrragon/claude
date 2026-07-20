"""check_proposal_dependencies 單元測試。

以 0.4.0-W1-001 實際發生的排序矛盾（PROP-010 依賴 PROP-011 卻排入更早版本）
作為回歸測試案例，確認 pipeline Step 1 能在提案確認階段攔截此類矛盾。

W1-016 修復：tracking fixture 全數由 dict-keyed-by-id 改為 list-based，
對齊 PROPOSALS_TRACKING_SCHEMA SSOT（proposals_format == "list"）與
create.py 的真實寫入格式。修復前的 dict fixture 與修復前的 dict 存取實作
兩端一致造假通過，未曾驗證真實資料格式（IMP-APP-002 同族：測資與實作
同時錯誤導致測試失去偵錯力）。
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check_proposal_dependencies import (  # noqa: E402
    _find_proposal,
    check_dependencies,
    normalize_version,
)


def _todolist(version: str, proposals: list[str]) -> dict:
    return {"versions": [{"version": version, "proposals": proposals}]}


def _tracking(*entries: dict) -> dict:
    """建立 list-based tracking dict（每個 entry 須含 'id' 欄位）。"""
    return {"proposals": list(entries)}


def test_normalize_version_strips_v_prefix():
    assert normalize_version("v0.4.0") == (0, 4, 0)
    assert normalize_version("0.4.0") == (0, 4, 0)


def test_normalize_version_comparable():
    assert normalize_version("0.5.0") > normalize_version("0.4.0")


class TestFindProposal:
    """_find_proposal 依 id 於 list-based proposals 查找（W1-016 新增）。"""

    def test_finds_entry_by_id(self):
        proposals = [{"id": "PROP-001", "target_version": "v0.1.0"}]
        assert _find_proposal(proposals, "PROP-001") == proposals[0]

    def test_returns_none_when_not_found(self):
        proposals = [{"id": "PROP-001"}]
        assert _find_proposal(proposals, "PROP-999") is None

    def test_returns_none_for_empty_list(self):
        assert _find_proposal([], "PROP-001") is None


def test_detects_0_4_0_prop010_prop011_contradiction():
    """還原 0.4.0-W1-001 事故：PROP-010 依賴 PROP-011，但排入更早版本。"""
    todolist = _todolist("0.4.0", ["PROP-008", "PROP-010"])
    tracking = _tracking(
        {"id": "PROP-008", "target_version": "v0.4.0"},
        {"id": "PROP-010", "target_version": "v0.4.0", "depends_on": ["PROP-011"]},
        {"id": "PROP-011", "target_version": "v0.5.0"},
    )

    warnings = check_dependencies(todolist, tracking, "0.4.0")

    assert len(warnings) == 1
    assert "PROP-010" in warnings[0]
    assert "PROP-011" in warnings[0]


def test_no_warning_when_dependency_scheduled_before():
    """依賴排在同版或更早版本時不應告警（正確排序）。"""
    todolist = _todolist("0.5.0", ["PROP-010", "PROP-011"])
    tracking = _tracking(
        {"id": "PROP-010", "target_version": "v0.5.0", "depends_on": ["PROP-011"]},
        {"id": "PROP-011", "target_version": "v0.5.0"},
    )

    warnings = check_dependencies(todolist, tracking, "0.5.0")

    assert warnings == []


def test_no_warning_when_no_depends_on_field():
    """未定義 depends_on 的提案（多數情況）不受影響。"""
    todolist = _todolist("0.3.0", ["PROP-003"])
    tracking = _tracking({"id": "PROP-003", "target_version": "v0.3.0"})

    warnings = check_dependencies(todolist, tracking, "0.3.0")

    assert warnings == []


def test_warns_when_proposal_missing_from_tracking():
    todolist = _todolist("0.6.0", ["PROP-099"])
    tracking = _tracking()

    warnings = check_dependencies(todolist, tracking, "0.6.0")

    assert len(warnings) == 1
    assert "PROP-099" in warnings[0]


def test_warns_when_dependency_missing_from_tracking():
    todolist = _todolist("0.6.0", ["PROP-020"])
    tracking = _tracking(
        {"id": "PROP-020", "target_version": "v0.6.0", "depends_on": ["PROP-021"]}
    )

    warnings = check_dependencies(todolist, tracking, "0.6.0")

    assert len(warnings) == 1
    assert "PROP-021" in warnings[0]


def test_multiple_depends_on_entries_all_checked():
    """一個提案依賴多個提案時，每個依賴皆需個別檢查（W1-016 新增，acceptance 4）。"""
    todolist = _todolist("0.6.0", ["PROP-030"])
    tracking = _tracking(
        {
            "id": "PROP-030",
            "target_version": "v0.6.0",
            "depends_on": ["PROP-031", "PROP-032"],
        },
        {"id": "PROP-031", "target_version": "v0.6.0"},
        {"id": "PROP-032", "target_version": "v0.7.0"},
    )

    warnings = check_dependencies(todolist, tracking, "0.6.0")

    assert len(warnings) == 1
    assert "PROP-030" in warnings[0]
    assert "PROP-032" in warnings[0]
    assert "PROP-031" not in warnings[0]


def test_does_not_raise_on_dict_shaped_like_real_tracking_file():
    """回歸測試：對真實 list-based tracking dict 呼叫不應 AttributeError（活 bug 修復）。

    修復前：`proposals.get(prop_id)` 對 list 呼叫 AttributeError
    （'list' object has no attribute 'get'）。
    """
    todolist = _todolist("0.0.2", ["PROP-001"])
    tracking = {
        "proposals": [
            {
                "id": "PROP-001",
                "title": "資產負債表 App 核心需求與技術選型",
                "status": "draft",
                "target_version": "0.0.2",
            }
        ],
        "usecases": [],
        "specs": [],
    }

    # 修復前於此行拋 AttributeError
    warnings = check_dependencies(todolist, tracking, "0.0.2")

    assert warnings == []


def test_dict_shaped_proposals_triggers_assertion():
    """proposals 為 dict（格式假設違反）時應觸發顯性斷言，而非靜默錯誤結果。"""
    todolist = _todolist("0.6.0", ["PROP-001"])
    tracking = {"proposals": {"PROP-001": {"target_version": "v0.6.0"}}}

    with pytest.raises(AssertionError, match="proposals-tracking.yaml"):
        check_dependencies(todolist, tracking, "0.6.0")
