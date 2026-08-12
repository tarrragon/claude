"""測試 0.2.1-W3-425：complete 時列出 where.files 重疊的 pending 票提示。

介入點為 lifecycle._print_overlapping_pending_hint，於 complete 成功路徑末端
呼叫。提示為純 stdout 輸出，不改變 exit code，不阻擋 complete（設計依據見
0.2.1-W3-388 Solution 方案 C）。

交集判定與來源票重現實驗一致：`own_files & other_files != set()`（有交集，
非子集測試——子集測試會漏掉宣告了自己專屬測試檔的吸收方，見 0.2.1-W3-388
Problem Analysis「重現實驗結果」W3-162 案例）。
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Dict, List, Optional


def _ticket(
    ticket_id: str,
    files: Optional[List[str]] = None,
    *,
    status: str = "pending",
    title: str = "",
) -> Dict:
    return {
        "id": ticket_id,
        "status": status,
        "title": title,
        "where": {"files": files or []},
    }


def _capture(ticket: Dict, ticket_map: Dict[str, Dict]) -> str:
    from ticket_system.commands.lifecycle import _print_overlapping_pending_hint

    buf = io.StringIO()
    with redirect_stdout(buf):
        _print_overlapping_pending_hint(ticket, ticket_map)
    return buf.getvalue()


class TestOverlappingPendingHint:
    def test_hint_printed_when_files_intersect_with_pending(self):
        completed = _ticket("IMP-A", files=["lib/a.dart", "lib/b.dart"], status="completed")
        pending = _ticket(
            "IMP-B", files=["lib/b.dart", "lib/c.dart"], title="修 b.dart 的 bug"
        )
        ticket_map = {"IMP-A": completed, "IMP-B": pending}

        out = _capture(completed, ticket_map)

        assert "IMP-B" in out
        assert "修 b.dart 的 bug" in out

    def test_hint_includes_relatedto_guidance_text(self):
        completed = _ticket("IMP-A", files=["lib/a.dart"], status="completed")
        pending = _ticket("IMP-B", files=["lib/a.dart"])
        ticket_map = {"IMP-A": completed, "IMP-B": pending}

        out = _capture(completed, ticket_map)

        assert "relatedTo" in out or "set-related-to" in out

    def test_no_hint_when_no_intersection(self):
        completed = _ticket("IMP-A", files=["lib/a.dart"], status="completed")
        pending = _ticket("IMP-B", files=["lib/z.dart"])
        ticket_map = {"IMP-A": completed, "IMP-B": pending}

        out = _capture(completed, ticket_map)

        assert out == ""

    def test_no_hint_when_own_files_empty(self):
        completed = _ticket("IMP-A", files=[], status="completed")
        pending = _ticket("IMP-B", files=["lib/a.dart"])
        ticket_map = {"IMP-A": completed, "IMP-B": pending}

        out = _capture(completed, ticket_map)

        assert out == ""

    def test_no_hint_when_pending_files_empty(self):
        completed = _ticket("IMP-A", files=["lib/a.dart"], status="completed")
        pending = _ticket("IMP-B", files=[])
        ticket_map = {"IMP-A": completed, "IMP-B": pending}

        out = _capture(completed, ticket_map)

        assert out == ""

    def test_non_pending_status_excluded(self):
        completed = _ticket("IMP-A", files=["lib/a.dart"], status="completed")
        other_completed = _ticket("IMP-B", files=["lib/a.dart"], status="completed")
        in_progress = _ticket("IMP-C", files=["lib/a.dart"], status="in_progress")
        closed = _ticket("IMP-D", files=["lib/a.dart"], status="closed")
        ticket_map = {
            "IMP-A": completed,
            "IMP-B": other_completed,
            "IMP-C": in_progress,
            "IMP-D": closed,
        }

        out = _capture(completed, ticket_map)

        assert out == ""

    def test_self_excluded_even_if_present_in_map(self):
        completed = _ticket("IMP-A", files=["lib/a.dart"], status="pending")
        ticket_map = {"IMP-A": completed}

        out = _capture(completed, ticket_map)

        assert out == ""

    def test_multiple_overlapping_pending_all_listed(self):
        completed = _ticket("IMP-A", files=["lib/a.dart"], status="completed")
        pending_1 = _ticket("IMP-B", files=["lib/a.dart"], title="B 票")
        pending_2 = _ticket("IMP-C", files=["lib/a.dart"], title="C 票")
        ticket_map = {"IMP-A": completed, "IMP-B": pending_1, "IMP-C": pending_2}

        out = _capture(completed, ticket_map)

        assert "IMP-B" in out
        assert "IMP-C" in out

    def test_full_subset_relation_still_counts_as_intersection(self):
        # W3-162 案例反例：pending 票宣告專屬測試檔使其非子集，但仍應以「有交集」
        # 判準命中（設計約束明文禁止改用子集測試）。
        completed = _ticket(
            "IMP-A", files=["lib/a.dart", "lib/shared.dart"], status="completed"
        )
        pending = _ticket(
            "IMP-B", files=["lib/shared.dart", "test/imp_b_only_test.dart"]
        )
        ticket_map = {"IMP-A": completed, "IMP-B": pending}

        out = _capture(completed, ticket_map)

        assert "IMP-B" in out


# ---------------------------------------------------------------------------
# 交集特異性排序與標註（0.2.1-W3-427：不改觸發判準，只改輸出排序）
# ---------------------------------------------------------------------------

def _with_noise(base: Dict[str, Dict], file_path: str, count: int) -> Dict[str, Dict]:
    """補上一批只宣告 file_path 的 completed 票，用於墊高該路徑的熱度。"""
    noise = {
        f"NOISE-{file_path}-{i}": _ticket(
            f"NOISE-{file_path}-{i}", files=[file_path], status="completed"
        )
        for i in range(count)
    }
    return {**base, **noise}


class TestOverlapSpecificityRanking:
    def test_lower_heat_candidate_ranked_first(self):
        # rare.dart 僅被 IMP-A / IMP-B 兩票宣告（熱度 2）；common.dart 額外被
        # 10 張虛構票宣告，熱度遠高於 rare.dart，特異性較低，應排在較後面。
        completed = _ticket(
            "IMP-A", files=["rare.dart", "common.dart"], status="completed"
        )
        candidate_rare = _ticket("IMP-B", files=["rare.dart"], title="Rare 候選")
        candidate_common = _ticket("IMP-C", files=["common.dart"], title="Common 候選")
        ticket_map = _with_noise(
            {"IMP-A": completed, "IMP-B": candidate_rare, "IMP-C": candidate_common},
            "common.dart",
            10,
        )

        out = _capture(completed, ticket_map)

        assert out.index("IMP-B") < out.index("IMP-C")

    def test_specificity_value_annotated_per_line(self):
        completed = _ticket("IMP-A", files=["lib/a.dart"], status="completed")
        pending = _ticket("IMP-B", files=["lib/a.dart"])
        ticket_map = {"IMP-A": completed, "IMP-B": pending}

        out = _capture(completed, ticket_map)

        # 熱度 = IMP-A + IMP-B 共 2 張宣告 lib/a.dart
        assert "IMP-B" in out
        assert "熱度 2" in out

    def test_specificity_uses_minimum_heat_of_intersection_files(self):
        completed = _ticket(
            "IMP-A", files=["rare.dart", "common.dart"], status="completed"
        )
        candidate = _ticket("IMP-B", files=["rare.dart", "common.dart"])
        ticket_map = _with_noise(
            {"IMP-A": completed, "IMP-B": candidate}, "common.dart", 10
        )

        out = _capture(completed, ticket_map)

        # 交集含 rare.dart（熱度 2）與 common.dart（熱度 12），特異性取最低值
        assert "熱度 2" in out
        assert "熱度 12" not in out

    def test_candidate_set_unchanged_by_sorting(self):
        # acceptance 3：排序不得過濾候選，即使熱度極高也要列出
        completed = _ticket("IMP-A", files=["hot.dart"], status="completed")
        candidate = _ticket("IMP-B", files=["hot.dart"])
        ticket_map = _with_noise(
            {"IMP-A": completed, "IMP-B": candidate}, "hot.dart", 20
        )

        out = _capture(completed, ticket_map)

        assert "IMP-B" in out

    def test_known_dry_run_case_regression_ranks_first(self):
        """重現已知空轉案例形態：吸收方宣告兩檔案（一低熱度、一高熱度），
        被吸收方僅宣告低熱度那個，應排在較高熱度的巧合候選之前。
        以構造資料重現形態，不依賴真實 ticket 語料（避免測試隨語料成長漂移）。
        """
        completed = _ticket(
            "ABSORBER",
            files=["shared_low_heat.dart", "shared_high_heat.dart"],
            status="completed",
        )
        absorbed = _ticket(
            "ABSORBED", files=["shared_low_heat.dart"], title="已被吸收的空轉票"
        )
        decoy = _ticket(
            "DECOY", files=["shared_high_heat.dart"], title="高熱度巧合候選"
        )
        ticket_map = _with_noise(
            {"ABSORBER": completed, "ABSORBED": absorbed, "DECOY": decoy},
            "shared_high_heat.dart",
            15,
        )

        out = _capture(completed, ticket_map)

        assert out.index("ABSORBED") < out.index("DECOY")
