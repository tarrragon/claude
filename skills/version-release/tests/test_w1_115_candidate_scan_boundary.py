"""
0.38.1-W1-115: version-release 下一版本候選掃描窗口越界誤傷 tech_debt 回歸測試

覆蓋 _scan_todolist_planned_candidates() 與 activate_next_planned_version()：
1. 最後一個版本條目 completed 且後續 section 含 status: "pending" 時，
   該後續 section 的條目不得被誤判為候選（窗口越界修復）
2. 唯一候選為跨大版本時，觸發閘門攔截而非自動推進
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


TODOLIST_WITH_TECH_DEBT_PENDING = """\
meta:
  schema_version: 1

versions:
  - version: "0.37.0"
    status: "completed"
  - version: "0.12.0"
    status: "completed"

tech_debt:
  - id: "0.20.0-TD-001"
    status: "pending"
    description: "some debt"

quality_standards:
  coverage: 80
"""


TODOLIST_WITH_CROSS_MAJOR_CANDIDATE = """\
meta:
  schema_version: 1

versions:
  - version: "0.37.0"
    status: "completed"
  - version: "1.0.0"
    status: "planned"

tech_debt:
  - id: "0.20.0-TD-002"
    status: "pending"
    description: "other debt"
"""


class TestScanTodolistPlannedCandidatesBoundary:
    def test_last_completed_entry_window_does_not_leak_into_tech_debt(self):
        """最後一個版本條目（completed）的搜尋窗口不得延伸進 tech_debt section，
        誤判 tech_debt 的 status: "pending" 為候選（原始 bug：0.12.0 completed
        被誤判為候選，因窗口一路延伸到檔尾撞上 tech_debt 的 pending）。
        """
        candidates = vr._scan_todolist_planned_candidates(
            TODOLIST_WITH_TECH_DEBT_PENDING
        )

        versions = [c["version"] for c in candidates]
        assert "0.12.0" not in versions
        assert versions == []

    def test_tech_debt_status_untouched_when_no_real_planned_version(self, tmp_path):
        """無真正 planned/pending 版本時，tech_debt 條目不應被觸碰。"""
        todolist_path = tmp_path / "todolist.yaml"
        todolist_path.write_text(TODOLIST_WITH_TECH_DEBT_PENDING, encoding="utf-8")

        result = vr.activate_next_planned_version(
            todolist_path, completed_version="0.37.0", dry_run=True
        )

        assert result is True
        # dry-run 不寫檔，內容應維持不變
        assert todolist_path.read_text(encoding="utf-8") == TODOLIST_WITH_TECH_DEBT_PENDING


class TestCrossMajorGateWithSingleCandidate:
    def test_single_cross_major_candidate_blocks_auto_advance(self, tmp_path, capsys):
        """唯一候選為跨大版本時，觸發閘門警告而非自動推進為 active。"""
        todolist_path = tmp_path / "todolist.yaml"
        todolist_path.write_text(
            TODOLIST_WITH_CROSS_MAJOR_CANDIDATE, encoding="utf-8"
        )

        result = vr.activate_next_planned_version(
            todolist_path, completed_version="0.37.0", dry_run=True
        )

        assert result is True
        captured = capsys.readouterr()
        assert "跨大版本" in captured.out
        assert "1.0.0" in captured.out
        # 內容不應被改動（閘門攔截，未呼叫 _apply_version_activation 寫入）
        assert (
            todolist_path.read_text(encoding="utf-8")
            == TODOLIST_WITH_CROSS_MAJOR_CANDIDATE
        )

    def test_tech_debt_status_untouched_when_cross_major_blocked(self, tmp_path):
        """跨大版本閘門攔截時，tech_debt 的 status 欄位不受影響。"""
        todolist_path = tmp_path / "todolist.yaml"
        todolist_path.write_text(
            TODOLIST_WITH_CROSS_MAJOR_CANDIDATE, encoding="utf-8"
        )

        vr.activate_next_planned_version(
            todolist_path, completed_version="0.37.0", dry_run=False
        )

        content = todolist_path.read_text(encoding="utf-8")
        assert '0.20.0-TD-002' in content
        # tech_debt status 仍是 pending，未被錯誤改為 active
        tech_debt_section = content.split("tech_debt:")[1]
        assert 'status: "pending"' in tech_debt_section
        assert "active" not in tech_debt_section
