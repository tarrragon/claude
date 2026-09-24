"""
0.2.1-W1-053: compute_overflow_target_version 補「開放後繼」分支測試

覆蓋：
- 有已登記且未凍結（planned/active）的後繼版本時，任何動詞皆回該後繼
- 後繼皆凍結或不存在時，回退舊規則（patch+1／minor+1）
- 對照測試：同一 todolist fixture 下，本 skill 複本
  （`version_release.compute_overflow_target_version`）與 ticket lib
  （`ticket_system.lib.version.suggest_overflow_version`）逐案結果相等
"""  # rule8-exempt: relocation:延用既有測試檔頭 docstring 慣例

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import version_release as vr  # noqa: E402

_TICKET_LIB_ROOT = Path(__file__).parent.parent.parent / "ticket" / "ticket_system"
sys.path.insert(0, str(_TICKET_LIB_ROOT.parent))
from ticket_system.lib import version as ticket_version  # noqa: E402


def _write_todolist(tmp_path: Path, versions: list[dict]) -> None:
    lines = ["versions:"]
    for v in versions:
        lines.append(f"  - version: {v['version']}")
        if "status" in v:
            lines.append(f"    status: {v['status']}")
        if "scope" in v:
            lines.append(f"    scope: {v['scope']}")
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "todolist.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestComputeOverflowTargetVersionOpenSuccessor:
    """有開放後繼時回後繼、無後繼時回 patch+1／minor+1"""

    def test_open_successor_wins_over_patch_action(self, tmp_path):
        """凍結版本有已登記 planned 且未凍結的後繼時，修復類動詞也回該後繼"""
        _write_todolist(
            tmp_path,
            [
                {"version": "0.2.1", "status": "active", "scope": "frozen"},
                {"version": "0.3.0", "status": "planned"},
            ],
        )
        with patch.object(vr, "get_project_root", return_value=tmp_path):
            target, reason = vr.compute_overflow_target_version("0.2.1", "IMP", "修復")

        assert target == "0.3.0"
        assert reason == "路由至最近的開放後繼版本"

    def test_open_successor_wins_over_feature_action(self, tmp_path):
        """新功能動詞（原本會 minor+1）在有開放後繼時同樣回該後繼"""
        _write_todolist(
            tmp_path,
            [
                {"version": "0.2.1", "status": "active", "scope": "frozen"},
                {"version": "0.3.0", "status": "planned"},
            ],
        )
        with patch.object(vr, "get_project_root", return_value=tmp_path):
            target, reason = vr.compute_overflow_target_version("0.2.1", "IMP", "實作")

        assert target == "0.3.0"
        assert reason == "路由至最近的開放後繼版本"

    def test_no_successor_falls_back_to_patch_plus_one(self, tmp_path):
        """無任何後繼版本登記時，回退 patch+1（既有行為）"""
        _write_todolist(tmp_path, [{"version": "0.2.1", "status": "active", "scope": "frozen"}])
        with patch.object(vr, "get_project_root", return_value=tmp_path):
            target, reason = vr.compute_overflow_target_version("0.2.1", "IMP", "修復")

        assert target == "0.2.2"
        assert reason == "修復/改善/分析/文件類型歸下一個 patch（相對凍結版本 patch+1）"

    def test_frozen_successor_falls_back_to_minor_plus_one(self, tmp_path):
        """唯一後繼也已凍結時，視為無開放後繼，新功能動詞回退 minor+1"""
        _write_todolist(
            tmp_path,
            [
                {"version": "0.2.1", "status": "active", "scope": "frozen"},
                {"version": "0.3.0", "status": "active", "scope": "frozen"},
            ],
        )
        with patch.object(vr, "get_project_root", return_value=tmp_path):
            target, reason = vr.compute_overflow_target_version("0.2.1", "IMP", "新增")

        assert target == "0.3.0"
        assert reason == "新功能歸下一個小版本（相對凍結版本 minor+1）"

    def test_completed_successor_is_not_open(self, tmp_path):
        """status 為 completed 的後繼不視為開放，回退舊規則"""
        _write_todolist(
            tmp_path,
            [
                {"version": "0.2.1", "status": "active", "scope": "frozen"},
                {"version": "0.3.0", "status": "completed"},
            ],
        )
        with patch.object(vr, "get_project_root", return_value=tmp_path):
            target, reason = vr.compute_overflow_target_version("0.2.1", "IMP", "修復")

        assert target == "0.2.2"
        assert reason == "修復/改善/分析/文件類型歸下一個 patch（相對凍結版本 patch+1）"


class TestOverflowTargetCrossCheckWithTicketLib:
    """對照測試：同一 fixture 下，version-release 複本與 ticket lib 結果逐案相等"""

    @pytest.mark.parametrize(
        "versions,frozen,ticket_type,action",
        [
            (
                [
                    {"version": "0.2.1", "status": "active", "scope": "frozen"},
                    {"version": "0.3.0", "status": "planned"},
                ],
                "0.2.1",
                "IMP",
                "修復",
            ),
            (
                [
                    {"version": "0.2.1", "status": "active", "scope": "frozen"},
                    {"version": "0.3.0", "status": "planned"},
                ],
                "0.2.1",
                "IMP",
                "實作",
            ),
            (
                [{"version": "0.2.1", "status": "active", "scope": "frozen"}],
                "0.2.1",
                "IMP",
                "修復",
            ),
            (
                [
                    {"version": "0.2.1", "status": "active", "scope": "frozen"},
                    {"version": "0.3.0", "status": "active", "scope": "frozen"},
                ],
                "0.2.1",
                "IMP",
                "新增",
            ),
            (
                [
                    {"version": "0.2.1", "status": "active", "scope": "frozen"},
                    {"version": "0.3.0", "status": "completed"},
                ],
                "0.2.1",
                "IMP",
                "修復",
            ),
            (
                [
                    {"version": "0.1.0", "status": "active", "scope": "frozen"},
                    {"version": "0.1.1", "status": "planned"},
                    {"version": "0.2.0", "status": "planned"},
                ],
                "0.1.0",
                "DOC",
                "撰寫",
            ),
        ],
    )
    def test_cross_check_matches(self, tmp_path, versions, frozen, ticket_type, action):
        _write_todolist(tmp_path, versions)

        with patch.object(vr, "get_project_root", return_value=tmp_path):
            vr_target, vr_reason = vr.compute_overflow_target_version(frozen, ticket_type, action)

        with patch.object(ticket_version, "get_project_root", return_value=tmp_path):
            lib_result = ticket_version.suggest_overflow_version(frozen, ticket_type, action)

        assert lib_result is not None
        lib_target, lib_reason = lib_result
        assert vr_target == lib_target
        assert vr_reason == lib_reason
