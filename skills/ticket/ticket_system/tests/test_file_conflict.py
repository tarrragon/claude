"""ticket_system.lib.file_conflict 測試（multi-PM 協調層 Phase 2/3）。

驗證重點：
1. `compute_pairwise_conflicts` 與 `track_conflicts.find_conflicts` 行為等價
   （AC-3：交集判定與 conflicts 命令共用同一實作）
2. `compute_parallel_groups`：
   - 無交集之票全數歸入單一 parallel_group
   - 有交集之票依連通分量分組為 sequential_groups（含傳遞性關聯）
   - 衝突對（conflict_pairs）如實回傳供顯示層標示
3. `render_groups`：固定值文字輸出（無 emoji，三區塊齊全）

`where_files` / `files_intersect` / `find_nearest_tests_dir` /
`derive_test_candidates` / `expand_files` 已由既有 `test_track_conflicts.py`
直接匯入 `file_conflict` 公開名測試（0.2.1-W3-585 前為透過 track_conflicts
私名別名匯入，該 4 個別名已隨此次測試遷移退場），本檔不重複測試同一份
實作，聚焦本次新增的 `compute_parallel_groups` / `render_groups` 與跨模組
行為等價性。
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from ticket_system.commands import track_conflicts
from ticket_system.lib import file_conflict

from conftest import _ticket  # noqa: F401 — 0.2.1-W3-585 收斂逐字複本


# ---------------------------------------------------------------------------
# AC-3：與 track_conflicts.find_conflicts 行為等價
# ---------------------------------------------------------------------------


class TestSharedImplementationEquivalence:
    def test_compute_pairwise_conflicts_matches_find_conflicts_after_status_filter(self):
        tickets = [
            _ticket("A", "pending", ["lib/foo.dart"]),
            _ticket("B", "in_progress", ["lib/foo.dart"]),
            _ticket("C", "completed", ["lib/foo.dart"]),  # find_conflicts 會篩掉
        ]

        via_conflicts_command = track_conflicts.find_conflicts(tickets)
        via_shared_lib = file_conflict.compute_pairwise_conflicts(
            [t for t in tickets if t["status"] in {"pending", "in_progress"}]
        )

        assert via_conflicts_command == via_shared_lib
        # lib/foo.dart 觸發 Dart impl->test 啟發式，衍生 test/foo_test.dart
        # 亦互相命中（兩票宣告相同路徑，衍生候選自然相同）
        assert via_conflicts_command == [
            {
                "ticket_a": "A",
                "ticket_b": "B",
                "matched_files": ["lib/foo.dart", "test/foo_test.dart"],
                "heuristic_only": False,
            }
        ]

    def test_empty_id_ticket_excluded_consistently_with_compute_parallel_groups(self):
        """0.2.1-W3-584 回歸：`compute_pairwise_conflicts` 先前以
        `t.get("id") or ""` 容忍空 id（產生 ticket_a=""/ticket_b="" 的
        無意義輸出），與 `compute_parallel_groups` 的 `if t.get("id")`
        節點篩選不一致——同一批 ticket 經兩函式處理，空 id 者一邊被納入
        比對、一邊被排除。改為兩者一致排除空 id ticket。
        """
        tickets_missing_id = [
            {"id": "", "status": "pending", "where": {"files": ["lib/foo.dart"]}},
            _ticket("B", "pending", ["lib/foo.dart"]),
        ]
        tickets_no_id_key = [
            {"status": "pending", "where": {"files": ["lib/foo.dart"]}},
            _ticket("B", "pending", ["lib/foo.dart"]),
        ]

        assert file_conflict.compute_pairwise_conflicts(tickets_missing_id) == []
        assert file_conflict.compute_pairwise_conflicts(tickets_no_id_key) == []

    def test_track_conflicts_reexports_are_same_function_objects(self):
        """track_conflicts.py 直接匯入的公開名稱須是同一函式物件（非重寫），
        驗證 AC-3「無複製貼上」的實作層級保證。

        0.2.1-W3-585：原本此處還斷言 4 個私名別名（`_files_intersect` 等）
        與 `file_conflict` 公開名相同，該 4 個別名已隨測試遷移退場（見
        test_track_conflicts.py 直接改測 `file_conflict` 公開名），本測試
        僅保留仍以公開名稱直接匯入的 `expand_files` /
        `compute_pairwise_conflicts` 兩項。
        """
        assert track_conflicts.expand_files is file_conflict.expand_files
        assert track_conflicts.compute_pairwise_conflicts is file_conflict.compute_pairwise_conflicts


# ---------------------------------------------------------------------------
# compute_parallel_groups
# ---------------------------------------------------------------------------


class TestGroupByConflict:
    """`group_by_conflict` 共用衝突圖核心（0.2.1-W3-583：收斂
    `compute_parallel_groups` 與 `track_parallel_check.analyze_parallel`
    兩份原本各自實作的圖演算法）。純圖層測試，不涉及任何交集判準——
    `conflict_pairs` 直接給定，模擬呼叫端已完成判準判定的輸出。
    """

    def test_no_pairs_all_isolated_preserving_input_order(self):
        isolated, components = file_conflict.group_by_conflict(
            ["C", "A", "B"], []
        )

        assert isolated == ["C", "A", "B"]
        assert components == []

    def test_single_pair_forms_one_component(self):
        isolated, components = file_conflict.group_by_conflict(
            ["A", "B", "C"], [("A", "B")]
        )

        assert isolated == ["C"]
        assert components == [["A", "B"]]

    def test_transitive_chain_merges_into_one_component(self):
        isolated, components = file_conflict.group_by_conflict(
            ["A", "B", "C"], [("A", "B"), ("B", "C")]
        )

        assert isolated == []
        assert components == [["A", "B", "C"]]

    def test_multiple_independent_components_sorted_by_first_member(self):
        isolated, components = file_conflict.group_by_conflict(
            ["Z", "Y", "B", "A"], [("Z", "Y"), ("B", "A")]
        )

        assert isolated == []
        assert components == [["A", "B"], ["Y", "Z"]]

    def test_pair_referencing_unknown_id_ignored(self):
        """conflict_pairs 中出現不在 ids 清單的節點時忽略該邊（防禦性，
        避免呼叫端資料不一致時拋例外）。"""
        isolated, components = file_conflict.group_by_conflict(
            ["A", "B"], [("A", "GHOST")]
        )

        assert isolated == ["A", "B"]
        assert components == []

    def test_empty_ids_returns_empty_result(self):
        isolated, components = file_conflict.group_by_conflict([], [])

        assert isolated == []
        assert components == []

    def test_degree_zero_nodes_mixed_with_components_classified_correctly(self):
        """0.2.1-W3-584：度數 0 節點的獨立提前分支已收斂為通用 DFS 路徑
        （事後依 component 長度分類），本案例混合孤立節點與連通分量，
        驗證收斂後行為與收斂前完全一致。"""
        isolated, components = file_conflict.group_by_conflict(
            ["A", "B", "C", "D", "E"],
            [("A", "B"), ("D", "E")],
        )

        assert isolated == ["C"]
        assert components == [["A", "B"], ["D", "E"]]


class TestComputeParallelGroups:
    def test_no_conflicts_all_ticket_in_single_parallel_group(self):
        tickets = [
            _ticket("A", "pending", ["lib/a.dart"]),
            _ticket("B", "pending", ["lib/b.dart"]),
            _ticket("C", "pending", ["lib/c.dart"]),
        ]

        result = file_conflict.compute_parallel_groups(tickets)

        assert set(result.parallel_group) == {"A", "B", "C"}
        assert result.sequential_groups == []
        assert result.conflict_pairs == []

    def test_direct_conflict_pair_falls_into_sequential_group(self):
        tickets = [
            _ticket("A", "pending", ["lib/foo.dart"]),
            _ticket("B", "pending", ["lib/foo.dart"]),
            _ticket("C", "pending", ["lib/other.dart"]),
        ]

        result = file_conflict.compute_parallel_groups(tickets)

        assert result.parallel_group == ["C"]
        assert result.sequential_groups == [["A", "B"]]
        assert len(result.conflict_pairs) == 1
        assert result.conflict_pairs[0]["ticket_a"] == "A"
        assert result.conflict_pairs[0]["ticket_b"] == "B"

    def test_transitive_conflict_chain_merges_into_one_sequential_group(self):
        """A-B 交集、B-C 交集、A-C 本身無交集：傳遞性仍要求三者同一序列組
        （A、C 縱使無直接交集，仍因經 B 傳遞關聯不可能與 B 同時進行）。"""
        tickets = [
            _ticket("A", "pending", ["lib/shared.dart"]),
            _ticket("B", "pending", ["lib/shared.dart", "lib/other.dart"]),
            _ticket("C", "pending", ["lib/other.dart"]),
        ]

        result = file_conflict.compute_parallel_groups(tickets)

        assert result.parallel_group == []
        assert result.sequential_groups == [["A", "B", "C"]]
        assert len(result.conflict_pairs) == 2

    def test_multiple_independent_conflict_components(self):
        """兩組互相獨立的衝突對 → 各自成一個序列組，組間彼此可並行。"""
        tickets = [
            _ticket("A", "pending", ["lib/a.dart"]),
            _ticket("B", "pending", ["lib/a.dart"]),
            _ticket("C", "pending", ["lib/c.dart"]),
            _ticket("D", "pending", ["lib/c.dart"]),
            _ticket("E", "pending", ["lib/e.dart"]),
        ]

        result = file_conflict.compute_parallel_groups(tickets)

        assert result.parallel_group == ["E"]
        assert result.sequential_groups == [["A", "B"], ["C", "D"]]

    def test_parallel_group_preserves_input_order_for_priority_sorting(self):
        """parallel_group 保留呼叫端輸入順序（供呼叫端自行依 priority 預排序，
        本函式不重排）。"""
        tickets = [
            _ticket("P0-ticket", "pending", ["lib/x.dart"]),
            _ticket("P3-ticket", "pending", ["lib/y.dart"]),
            _ticket("P1-ticket", "pending", ["lib/z.dart"]),
        ]

        result = file_conflict.compute_parallel_groups(tickets)

        assert result.parallel_group == ["P0-ticket", "P3-ticket", "P1-ticket"]

    def test_tickets_without_declared_files_are_isolated(self):
        """無宣告 where.files 的票不參與任何交集判定，視為孤立節點。"""
        tickets = [
            _ticket("A", "pending", []),
            _ticket("B", "pending", ["lib/b.dart"]),
        ]

        result = file_conflict.compute_parallel_groups(tickets)

        assert set(result.parallel_group) == {"A", "B"}
        assert result.sequential_groups == []

    def test_empty_input_returns_empty_result(self):
        result = file_conflict.compute_parallel_groups([])

        assert result.parallel_group == []
        assert result.sequential_groups == []
        assert result.conflict_pairs == []


# ---------------------------------------------------------------------------
# render_groups
# ---------------------------------------------------------------------------


class TestRenderGroups:
    def test_renders_all_three_sections(self):
        result = file_conflict.GroupsResult(
            parallel_group=["A", "B"],
            sequential_groups=[["C", "D"]],
            conflict_pairs=[{
                "ticket_a": "C", "ticket_b": "D",
                "matched_files": ["lib/x.dart"], "heuristic_only": False,
            }],
        )

        text = file_conflict.render_groups(result)

        assert "可並行群組" in text
        assert "A" in text and "B" in text
        assert "序列群組" in text
        assert "群組 1: C, D" in text
        assert "衝突對" in text
        assert "C <-> D" in text
        assert "lib/x.dart" in text

    def test_renders_empty_sections_without_error(self):
        result = file_conflict.GroupsResult()

        text = file_conflict.render_groups(result)

        assert "（無）" in text

    def test_no_emoji_in_output(self):
        """交接文件格式規則：禁止 emoji（document-format-rules.md 規則 1）。"""
        result = file_conflict.GroupsResult(
            parallel_group=["A"],
            sequential_groups=[["B", "C"]],
            conflict_pairs=[{
                "ticket_a": "B", "ticket_b": "C",
                "matched_files": ["lib/y.dart"], "heuristic_only": True,
            }],
        )

        text = file_conflict.render_groups(result)

        assert all(ord(ch) < 0x1F300 or ord(ch) > 0x1FAFF for ch in text)


# ---------------------------------------------------------------------------
# files_intersect：tuple 前綴比對邊界案例（Phase 4 效能組重寫後回歸）
# ---------------------------------------------------------------------------


class TestFilesIntersectTuplePrefixEdgeCases:
    """`PurePosixPath.parents` 走訪改手動 tuple 前綴比對後的邊界案例，
    確保與既有 `test_track_conflicts.py::TestFilesIntersect` 四項基本案例
    行為一致（該檔透過 track_conflicts 別名匯入同一份實作，不重複列出）。
    """

    def test_empty_string_paths_intersect_only_when_both_empty(self):
        assert file_conflict.files_intersect("", "") is True
        assert file_conflict.files_intersect("", "lib/foo.dart") is False
        assert file_conflict.files_intersect("lib/foo.dart", "") is False

    def test_trailing_slash_normalized(self):
        assert file_conflict.files_intersect("lib/foo/", "lib/foo/bar.dart") is True

    def test_deep_nested_prefix(self):
        assert file_conflict.files_intersect(
            "lib/a/b/c", "lib/a/b/c/d/e/f.dart"
        ) is True

    def test_path_parts_cache_is_pure_and_consistent(self):
        """`_path_parts` 為 `lru_cache` 純函式，重複呼叫同一路徑須回傳一致值
        （快取正確性的最小驗證）。"""
        assert file_conflict._path_parts("lib/a/b.dart") == file_conflict._path_parts(
            "lib/a/b.dart"
        )
        assert file_conflict._path_parts("lib/a/b.dart") == ("lib", "a", "b.dart")


# ---------------------------------------------------------------------------
# 效能回歸防護（Phase 4 五視角審查效能組，@pytest.mark.perf 獨立套件）
# ---------------------------------------------------------------------------


@pytest.mark.perf
class TestComputePairwiseConflictsPerformance:
    """計時硬門檻測試（test-assertion-design-rules 規則 D1 落地）：審查實測
    基線 139 票 1.28s（`PurePosixPath` 熱路徑），改 tuple 前綴比對 + lru_cache
    後目標 <300ms。標記 `@pytest.mark.perf`，預設套件排除（pyproject.toml
    `addopts = "-m 'not perf'"`），獨立以 `pytest -m perf` 執行，避免主套件
    高負載下 flaky。
    """

    @staticmethod
    def _synthetic_tickets(count: int) -> List[Dict[str, Any]]:
        import random

        rng = random.Random(42)  # 固定 seed，測試結果可重現（規則 D4）
        pool = [
            f"lib/domain{d}/module{m}.dart" for d in range(10) for m in range(8)
        ] + [f"hooks/hook{i}.py" for i in range(20)]
        tickets = []
        for i in range(count):
            files = rng.sample(pool, k=rng.randint(2, 4))
            tickets.append(_ticket(f"T-{i:03d}", "pending", files))
        return tickets

    def test_139_tickets_under_300ms(self):
        import time

        tickets = self._synthetic_tickets(139)

        start = time.perf_counter()
        conflicts = file_conflict.compute_pairwise_conflicts(tickets)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.3, f"139 票交集判定耗時 {elapsed * 1000:.1f}ms，逾 300ms 門檻"
        assert conflicts  # 合成資料應產生非零衝突對，確保測的是真實工作量非早退空路徑
