"""
Error Patterns Index Consistency Check Hook 測試

涵蓋範圍：
1. extract_filename_id — 檔名 ID 抽取（含可選中段 PC-BAL-001 / IMP-V1-006 / PC-SCLK-004）
2. collect_dir_id_map — 目錄掃描 + ID 分組（含碰撞情境）
3. collect_readme_ids — README 表格列 ID 抽取（含消歧括號註記）
4. compare — 三項比對邏輯（缺漏 / 過時 / 碰撞）各自正例反例
5. format_report — 有/無發現時的輸出格式
6. main — 端對端 tmp fixture 情境 + 對現況 repo 的回歸基線
7. extract_frontmatter_text / parse_related_field — frontmatter 解析（inline
   flow / block list / 缺欄位）
8. collect_related_map / check_related_bidirectional — related 雙向性檢查
   （雙向完整 / 單向 / related 缺失三種情況）
"""

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "error_patterns_index_consistency_check_hook",
    _HOOKS_DIR / "error-patterns-index-consistency-check-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)


# ---------------------------------------------------------------------------
# extract_filename_id
# ---------------------------------------------------------------------------


class TestExtractFilenameId:
    def test_plain_id(self):
        assert _hook.extract_filename_id("PC-166-some-title.md") == "PC-166"

    def test_id_with_middle_segment(self):
        assert (
            _hook.extract_filename_id("PC-BAL-001-stale-validator.md") == "PC-BAL-001"
        )

    def test_id_with_alnum_middle_segment(self):
        assert _hook.extract_filename_id("IMP-V1-006-something.md") == "IMP-V1-006"

    def test_id_with_short_middle_segment(self):
        assert _hook.extract_filename_id("PC-SCLK-004-clock-bomb.md") == "PC-SCLK-004"

    def test_unrecognized_filename_returns_empty(self):
        assert _hook.extract_filename_id("README.md") == ""
        assert _hook.extract_filename_id("notes.md") == ""

    def test_no_slug_placeholder_file(self):
        """allocate_and_reserve_pattern_id 建立的佔位檔無 slug（`{id}.md`），
        建立端為權威（SKILL.md「佔位檔檔名（無 slug）即 pattern_id」），
        本函式須正確辨識，不可歸入 UNRECOGNIZED（PC-BAL-040 入庫實證）。
        """
        assert _hook.extract_filename_id("PC-BAL-040.md") == "PC-BAL-040"
        assert _hook.extract_filename_id("IMP-V1-006.md") == "IMP-V1-006"
        assert _hook.extract_filename_id("TEST-001.md") == "TEST-001"


# ---------------------------------------------------------------------------
# collect_dir_id_map
# ---------------------------------------------------------------------------


class TestCollectDirIdMap:
    def _make_tree(self, tmp_path: Path, files_by_category: dict) -> Path:
        root = tmp_path / "error-patterns"
        for category, filenames in files_by_category.items():
            cat_dir = root / category
            cat_dir.mkdir(parents=True, exist_ok=True)
            for name in filenames:
                (cat_dir / name).write_text("# stub\n", encoding="utf-8")
        return root

    def test_single_file_per_id(self, tmp_path):
        root = self._make_tree(
            tmp_path, {"test": ["TEST-001-a.md", "TEST-002-b.md"]}
        )
        result = _hook.collect_dir_id_map(root)
        assert result["TEST-001"] == ["test/TEST-001-a.md"]
        assert result["TEST-002"] == ["test/TEST-002-b.md"]

    def test_collision_two_files_same_id(self, tmp_path):
        root = self._make_tree(
            tmp_path,
            {
                "architecture": [
                    "ARCH-010-module-assembly-omission.md",
                    "ARCH-010-overengineered-state-management.md",
                ]
            },
        )
        result = _hook.collect_dir_id_map(root)
        assert len(result["ARCH-010"]) == 2

    def test_readme_excluded_from_scan(self, tmp_path):
        root = self._make_tree(
            tmp_path, {"test": ["README.md", "TEST-001-a.md"]}
        )
        result = _hook.collect_dir_id_map(root)
        assert "TEST-001" in result
        assert not any("README" in v for values in result.values() for v in values)

    def test_missing_category_dir_skipped(self, tmp_path):
        root = tmp_path / "error-patterns"
        root.mkdir()
        # 只建立部分分類目錄，其餘不存在
        (root / "test").mkdir()
        (root / "test" / "TEST-001-a.md").write_text("# stub\n", encoding="utf-8")
        result = _hook.collect_dir_id_map(root)
        assert result == {"TEST-001": ["test/TEST-001-a.md"]}

    def test_unrecognized_filename_tracked_separately(self, tmp_path):
        root = self._make_tree(tmp_path, {"test": ["not-an-id-file.md"]})
        result = _hook.collect_dir_id_map(root)
        assert any(k.startswith("UNRECOGNIZED:") for k in result)

    def test_no_slug_placeholder_file_recognized_not_unrecognized(self, tmp_path):
        """無 slug 佔位檔須被正確歸入其 ID，不落入 UNRECOGNIZED（PC-BAL-040
        入庫實證：先前誤判會使該 ID 從 dir_ids 消失，觸發 stale 誤報）。"""
        root = self._make_tree(
            tmp_path, {"process-compliance": ["PC-BAL-040.md"]}
        )
        result = _hook.collect_dir_id_map(root)
        assert result["PC-BAL-040"] == ["process-compliance/PC-BAL-040.md"]
        assert not any(k.startswith("UNRECOGNIZED:") for k in result)


# ---------------------------------------------------------------------------
# collect_readme_ids
# ---------------------------------------------------------------------------


class TestCollectReadmeIds:
    def test_plain_row(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            "| ID | 標題 | 風險 | 來源版本 |\n"
            "|----|------|------|---------|\n"
            "| TEST-001 | 錯誤的等待機制 | 高 | v0.6.2 |\n",
            encoding="utf-8",
        )
        assert _hook.collect_readme_ids(readme) == {"TEST-001"}

    def test_row_with_disambiguation_suffix(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            "| ARCH-010 (module-assembly-omission) | 標題 A | 高 | v0.15.4 |\n"
            "| ARCH-010 (overengineered-state-management) | 標題 B | 中 | v0.1.0 |\n",
            encoding="utf-8",
        )
        # 消歧註記的兩列應收斂為同一 ID（集合去重）
        assert _hook.collect_readme_ids(readme) == {"ARCH-010"}

    def test_middle_segment_id_in_readme(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            "| PC-BAL-001 | 某標題 | 高 | v0.1.0 |\n", encoding="utf-8"
        )
        assert _hook.collect_readme_ids(readme) == {"PC-BAL-001"}

    def test_non_table_lines_ignored(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            "# 標題\n\n這不是表格列，也不應被抽取。\n", encoding="utf-8"
        )
        assert _hook.collect_readme_ids(readme) == set()

    def test_missing_readme_returns_empty_set(self, tmp_path):
        assert _hook.collect_readme_ids(tmp_path / "not-exist.md") == set()


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


class TestCompare:
    def test_fully_synced_no_findings(self):
        dir_id_map = {"TEST-001": ["test/TEST-001-a.md"]}
        readme_ids = {"TEST-001"}
        result = _hook.compare(dir_id_map, readme_ids)
        assert result["missing_in_readme"] == []
        assert result["stale_in_readme"] == []
        assert result["collisions"] == {}

    def test_missing_in_readme_detected(self):
        dir_id_map = {"TEST-001": ["test/TEST-001-a.md"]}
        readme_ids = set()
        result = _hook.compare(dir_id_map, readme_ids)
        assert result["missing_in_readme"] == ["TEST-001"]

    def test_stale_in_readme_detected(self):
        dir_id_map = {}
        readme_ids = {"TEST-999"}
        result = _hook.compare(dir_id_map, readme_ids)
        assert result["stale_in_readme"] == ["TEST-999"]

    def test_collision_detected_even_when_id_in_readme(self):
        """核心設計約束：ID 集合比對為 0 仍須報出碰撞（見 ticket Problem Analysis）。"""
        dir_id_map = {
            "ARCH-010": [
                "architecture/ARCH-010-a.md",
                "architecture/ARCH-010-b.md",
            ]
        }
        readme_ids = {"ARCH-010"}
        result = _hook.compare(dir_id_map, readme_ids)
        assert result["missing_in_readme"] == []
        assert result["stale_in_readme"] == []
        assert result["collisions"] == {
            "ARCH-010": ["architecture/ARCH-010-a.md", "architecture/ARCH-010-b.md"]
        }

    def test_single_file_id_not_flagged_as_collision(self):
        dir_id_map = {"TEST-001": ["test/TEST-001-a.md"]}
        result = _hook.compare(dir_id_map, {"TEST-001"})
        assert result["collisions"] == {}

    def test_unrecognized_excluded_from_missing_and_collision(self):
        dir_id_map = {"UNRECOGNIZED:test/not-an-id.md": ["test/not-an-id.md"]}
        result = _hook.compare(dir_id_map, set())
        assert result["missing_in_readme"] == []
        assert result["collisions"] == {}
        assert result["unrecognized"] == ["test/not-an-id.md"]


# ---------------------------------------------------------------------------
# extract_frontmatter_text / parse_related_field
# ---------------------------------------------------------------------------


class TestExtractFrontmatterText:
    def test_extracts_block_between_delimiters(self):
        content = "---\nid: PC-001\nrelated: [PC-002]\n---\n\n# 標題\n"
        text = _hook.extract_frontmatter_text(content)
        assert "id: PC-001" in text
        assert "related: [PC-002]" in text
        assert "# 標題" not in text

    def test_no_frontmatter_returns_empty_string(self):
        assert _hook.extract_frontmatter_text("# stub\n") == ""


class TestParseRelatedField:
    def test_inline_flow_style(self):
        text = "id: PC-001\nrelated: [PC-002, PC-BAL-003]\nseverity: high\n"
        assert _hook.parse_related_field(text) == {"PC-002", "PC-BAL-003"}

    def test_block_list_style_zero_indent(self):
        text = "id: PC-001\nrelated:\n- PC-002\n- PC-BAL-003\nseverity: high\n"
        assert _hook.parse_related_field(text) == {"PC-002", "PC-BAL-003"}

    def test_block_list_style_two_space_indent(self):
        text = "id: PC-001\nrelated:\n  - PC-002\n  - PC-BAL-003\nseverity: high\n"
        assert _hook.parse_related_field(text) == {"PC-002", "PC-BAL-003"}

    def test_related_patterns_field_name(self):
        text = "id: PC-001\nrelated_patterns: [PC-APP-010]\nseverity: high\n"
        assert _hook.parse_related_field(text) == {"PC-APP-010"}

    def test_empty_related_field_returns_empty_set(self):
        text = "id: PC-001\nrelated:\ncreated: 2026-08-18\n"
        assert _hook.parse_related_field(text) == set()

    def test_missing_related_field_returns_empty_set(self):
        text = "id: PC-001\nseverity: high\n"
        assert _hook.parse_related_field(text) == set()

    def test_non_pattern_id_items_ignored(self):
        """非 error-pattern 命名慣例的項目（方法論 slug）不匹配 ID pattern，忽略。"""
        text = "id: PC-001\nrelated:\n- PC-002\n- hook-system-design\n"
        assert _hook.parse_related_field(text) == {"PC-002"}


# ---------------------------------------------------------------------------
# collect_related_map / check_related_bidirectional
# ---------------------------------------------------------------------------


class TestExtractCreatedDate:
    def test_parses_valid_date(self):
        text = "id: PC-001\ncreated: 2026-08-18\n"
        assert _hook.extract_created_date(text) == date(2026, 8, 18)

    def test_missing_field_returns_none(self):
        text = "id: PC-001\nseverity: high\n"
        assert _hook.extract_created_date(text) is None

    def test_malformed_date_returns_none(self):
        text = "id: PC-001\ncreated: not-a-date\n"
        assert _hook.extract_created_date(text) is None


class TestCollectRelatedMap:
    def _write_pattern(self, tmp_path: Path, category: str, filename: str, frontmatter_body: str):
        cat_dir = tmp_path / "error-patterns" / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        content = f"---\n{frontmatter_body}\n---\n\n# 標題\n"
        (cat_dir / filename).write_text(content, encoding="utf-8")

    def test_collects_related_ids_and_created_per_file(self, tmp_path):
        self._write_pattern(
            tmp_path,
            "process-compliance",
            "PC-001-a.md",
            "id: PC-001\nrelated: [PC-002]\ncreated: 2026-08-18",
        )
        root = tmp_path / "error-patterns"
        related_map = _hook.collect_related_map(root)
        assert related_map["PC-001"][0] == {"PC-002"}
        assert related_map["PC-001"][1] == date(2026, 8, 18)
        assert related_map["PC-001"][2] == "process-compliance/PC-001-a.md"

    def test_file_without_related_field_has_empty_set(self, tmp_path):
        self._write_pattern(tmp_path, "test", "TEST-001-a.md", "id: TEST-001\nseverity: high")
        root = tmp_path / "error-patterns"
        related_map = _hook.collect_related_map(root)
        assert related_map["TEST-001"][0] == set()

    def test_file_without_created_field_has_none(self, tmp_path):
        self._write_pattern(
            tmp_path, "process-compliance", "PC-002-a.md", "id: PC-002\nseverity: high"
        )
        root = tmp_path / "error-patterns"
        related_map = _hook.collect_related_map(root)
        assert related_map["PC-002"][1] is None


class TestCheckRelatedBidirectional:
    """same_batch: created 相差在 SAME_BATCH_WINDOW_DAYS（7 天）內。"""

    def test_fully_bidirectional_no_findings(self):
        related_map = {
            "PC-001": ({"PC-002"}, date(2026, 8, 18), "process-compliance/PC-001-a.md"),
            "PC-002": ({"PC-001"}, date(2026, 8, 18), "process-compliance/PC-002-b.md"),
        }
        assert _hook.check_related_bidirectional(related_map) == []

    def test_one_way_reference_detected_within_same_batch_window(self):
        related_map = {
            "PC-001": ({"PC-002"}, date(2026, 8, 18), "process-compliance/PC-001-a.md"),
            "PC-002": (set(), date(2026, 8, 20), "process-compliance/PC-002-b.md"),
        }
        result = _hook.check_related_bidirectional(related_map)
        assert result == [("PC-001", "PC-002", "process-compliance/PC-001-a.md")]

    def test_one_way_reference_outside_window_not_flagged(self):
        """created 相差超過 SAME_BATCH_WINDOW_DAYS 天視為引註，非姊妹關係，不告警。"""
        related_map = {
            "PC-001": ({"PC-002"}, date(2026, 8, 18), "process-compliance/PC-001-a.md"),
            "PC-002": (set(), date(2026, 7, 1), "process-compliance/PC-002-b.md"),
        }
        assert _hook.check_related_bidirectional(related_map) == []

    def test_one_way_reference_missing_created_on_from_side_not_flagged(self):
        """from 端缺 created 欄位時無法判定批次，跳過不告警（漏報優先於誤報）。"""
        related_map = {
            "PC-001": ({"PC-002"}, None, "process-compliance/PC-001-a.md"),
            "PC-002": (set(), date(2026, 8, 18), "process-compliance/PC-002-b.md"),
        }
        assert _hook.check_related_bidirectional(related_map) == []

    def test_one_way_reference_missing_created_on_to_side_not_flagged(self):
        related_map = {
            "PC-001": ({"PC-002"}, date(2026, 8, 18), "process-compliance/PC-001-a.md"),
            "PC-002": (set(), None, "process-compliance/PC-002-b.md"),
        }
        assert _hook.check_related_bidirectional(related_map) == []

    def test_reference_to_id_outside_index_not_flagged(self):
        """related 指向的 ID 不在 related_map（如已刪除或不存在）不誤報。"""
        related_map = {
            "PC-001": ({"PC-999"}, date(2026, 8, 18), "process-compliance/PC-001-a.md"),
        }
        assert _hook.check_related_bidirectional(related_map) == []

    def test_self_reference_not_flagged(self):
        related_map = {
            "PC-001": ({"PC-001"}, date(2026, 8, 18), "process-compliance/PC-001-a.md"),
        }
        assert _hook.check_related_bidirectional(related_map) == []


# ---------------------------------------------------------------------------
# extract_slug
# ---------------------------------------------------------------------------


class TestExtractSlug:
    def test_slug_extracted_after_id_prefix(self):
        assert (
            _hook.extract_slug("process-compliance/PC-010-pm-skipped-checkpoint-after-ticket-complete.md", "PC-010")
            == "pm-skipped-checkpoint-after-ticket-complete"
        )

    def test_slug_fallback_when_prefix_mismatch(self):
        # 檔名與 file_id 前綴不符時退回去除副檔名
        assert _hook.extract_slug("test/odd-name.md", "TEST-001") == "odd-name"


# ---------------------------------------------------------------------------
# parse_frozen_registry
# ---------------------------------------------------------------------------


class TestParseFrozenRegistry:
    def _write_methodology(self, tmp_path: Path, body: str) -> Path:
        path = tmp_path / "error-pattern-numbering-methodology.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_parses_valid_table(self, tmp_path):
        body = (
            "## 核心原則\n\n"
            "### 已知 legacy intra-dir 重號（凍結保留，不重編）\n\n"
            "說明文字。\n\n"
            "| Flat 號 | 教訓 A（slug） | 教訓 B（slug） |\n"
            "|---------|---------------|---------------|\n"
            "| IMP-049 | hook-error-display-is-cli-bug | undefined-constants-in-hook-source |\n"
            "| PC-010 | pm-skipped-checkpoint-after-ticket-complete | task-tracking-in-memory |\n\n"
            "### 下一節\n\n其他內容\n"
        )
        path = self._write_methodology(tmp_path, body)
        registry, error = _hook.parse_frozen_registry(path)
        assert error is None
        assert registry == {
            "IMP-049": {"hook-error-display-is-cli-bug", "undefined-constants-in-hook-source"},
            "PC-010": {"pm-skipped-checkpoint-after-ticket-complete", "task-tracking-in-memory"},
        }

    def test_missing_file_returns_error(self, tmp_path):
        registry, error = _hook.parse_frozen_registry(tmp_path / "not-exist.md")
        assert registry is None
        assert error is not None

    def test_missing_heading_returns_error(self, tmp_path):
        path = self._write_methodology(tmp_path, "## 其他章節\n\n無凍結表。\n")
        registry, error = _hook.parse_frozen_registry(path)
        assert registry is None
        assert "章節錨點" in error

    def test_empty_table_returns_error(self, tmp_path):
        body = "### 已知 legacy intra-dir 重號（凍結保留，不重編）\n\n只有文字，沒有表格列。\n\n### 下一節\n"
        path = self._write_methodology(tmp_path, body)
        registry, error = _hook.parse_frozen_registry(path)
        assert registry is None
        assert "資料列" in error


# ---------------------------------------------------------------------------
# compare — 凍結表分流
# ---------------------------------------------------------------------------


class TestCompareFrozenRouting:
    def test_registered_collision_with_matching_slugs_routes_to_info(self):
        dir_id_map = {
            "PC-010": [
                "process-compliance/PC-010-pm-skipped-checkpoint-after-ticket-complete.md",
                "process-compliance/PC-010-task-tracking-in-memory.md",
            ]
        }
        frozen_registry = {
            "PC-010": {"pm-skipped-checkpoint-after-ticket-complete", "task-tracking-in-memory"}
        }
        result = _hook.compare(dir_id_map, {"PC-010"}, frozen_registry)
        assert result["collisions"] == {}
        assert "PC-010" in result["registered_collisions"]

    def test_unregistered_collision_stays_warning(self):
        dir_id_map = {
            "TEST-999": ["test/TEST-999-a.md", "test/TEST-999-b.md"]
        }
        frozen_registry = {"PC-010": {"slug-a", "slug-b"}}
        result = _hook.compare(dir_id_map, {"TEST-999"}, frozen_registry)
        assert "TEST-999" in result["collisions"]
        assert result["registered_collisions"] == {}

    def test_registered_id_with_mismatched_slugs_stays_warning(self):
        # 已登記但 slug 組成不符（例如第三份同號檔出現，或一側被重編）
        dir_id_map = {
            "PC-010": [
                "process-compliance/PC-010-some-unlisted-slug.md",
                "process-compliance/PC-010-another-unlisted-slug.md",
            ]
        }
        frozen_registry = {
            "PC-010": {"pm-skipped-checkpoint-after-ticket-complete", "task-tracking-in-memory"}
        }
        result = _hook.compare(dir_id_map, {"PC-010"}, frozen_registry)
        assert "PC-010" in result["collisions"]
        assert result["registered_collisions"] == {}

    def test_none_registry_fail_open_all_warning(self):
        dir_id_map = {
            "PC-010": [
                "process-compliance/PC-010-pm-skipped-checkpoint-after-ticket-complete.md",
                "process-compliance/PC-010-task-tracking-in-memory.md",
            ]
        }
        result = _hook.compare(dir_id_map, {"PC-010"}, frozen_registry=None)
        assert "PC-010" in result["collisions"]
        assert result["registered_collisions"] == {}


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


class TestFormatReport:
    def test_no_findings_returns_empty_string(self):
        result = {
            "missing_in_readme": [],
            "stale_in_readme": [],
            "collisions": {},
            "registered_collisions": {},
            "unrecognized": [],
        }
        assert _hook.format_report(result) == ""

    def test_findings_produce_nonempty_report(self):
        result = {
            "missing_in_readme": ["TEST-999"],
            "stale_in_readme": ["TEST-998"],
            "collisions": {"ARCH-010": ["a.md", "b.md"]},
            "registered_collisions": {},
            "unrecognized": ["test/odd.md"],
        }
        report = _hook.format_report(result)
        assert "TEST-999" in report
        assert "TEST-998" in report
        assert "ARCH-010" in report
        assert "test/odd.md" in report
        assert "[WARNING]" in report

    def test_registered_collision_only_produces_info_no_warning(self):
        result = {
            "missing_in_readme": [],
            "stale_in_readme": [],
            "collisions": {},
            "registered_collisions": {"PC-010": ["a.md", "b.md"]},
            "unrecognized": [],
        }
        report = _hook.format_report(result)
        assert "[INFO]" in report
        assert "[WARNING]" not in report
        assert "PC-010" in report

    def test_frozen_error_suppressed_when_no_collisions(self):
        result = {
            "missing_in_readme": [],
            "stale_in_readme": [],
            "collisions": {},
            "registered_collisions": {},
            "unrecognized": [],
        }
        assert _hook.format_report(result, frozen_error="凍結表不存在") == ""

    def test_frozen_error_shown_when_collisions_present(self):
        result = {
            "missing_in_readme": [],
            "stale_in_readme": [],
            "collisions": {"TEST-001": ["a.md", "b.md"]},
            "registered_collisions": {},
            "unrecognized": [],
        }
        report = _hook.format_report(result, frozen_error="凍結表不存在")
        assert "凍結表不存在" in report
        assert "fail-open" in report

    def test_one_way_related_produces_warning(self):
        result = {
            "missing_in_readme": [],
            "stale_in_readme": [],
            "collisions": {},
            "registered_collisions": {},
            "unrecognized": [],
            "one_way_related": [("PC-001", "PC-002", "process-compliance/PC-001-a.md")],
        }
        report = _hook.format_report(result)
        assert "[WARNING]" in report
        assert "PC-001" in report
        assert "PC-002" in report

    def test_missing_one_way_related_key_defaults_empty(self):
        """result dict 未帶 one_way_related 鍵（舊呼叫端相容）不應報錯或誤報。"""
        result = {
            "missing_in_readme": [],
            "stale_in_readme": [],
            "collisions": {},
            "registered_collisions": {},
            "unrecognized": [],
        }
        assert _hook.format_report(result) == ""

    def test_one_way_related_capped_at_display_limit(self):
        """超過 ONE_WAY_RELATED_DISPLAY_CAP 行時截斷並附「另有 N 組未列出」。"""
        overflow = _hook.ONE_WAY_RELATED_DISPLAY_CAP + 3
        one_way = [
            (f"PC-{i:03d}", f"PC-{i + 1:03d}", f"process-compliance/PC-{i:03d}-a.md")
            for i in range(overflow)
        ]
        result = {
            "missing_in_readme": [],
            "stale_in_readme": [],
            "collisions": {},
            "registered_collisions": {},
            "unrecognized": [],
            "one_way_related": one_way,
        }
        report = _hook.format_report(result)
        shown = report.count(" -> ")
        assert shown == _hook.ONE_WAY_RELATED_DISPLAY_CAP
        assert "另有 3 組未列出" in report


# ---------------------------------------------------------------------------
# main — 端對端
# ---------------------------------------------------------------------------


class TestMainEndToEnd:
    def _build_fixture_repo(self, tmp_path: Path, readme_body: str, files_by_category: dict) -> Path:
        root = tmp_path / "project"
        error_patterns = root / ".claude" / "error-patterns"
        error_patterns.mkdir(parents=True)
        (error_patterns / "README.md").write_text(readme_body, encoding="utf-8")
        for category, filenames in files_by_category.items():
            cat_dir = error_patterns / category
            cat_dir.mkdir(parents=True, exist_ok=True)
            for name in filenames:
                (cat_dir / name).write_text("# stub\n", encoding="utf-8")
        return root

    def test_main_warns_on_missing_and_collision(self, tmp_path, monkeypatch, capsys):
        root = self._build_fixture_repo(
            tmp_path,
            readme_body="| ID | 標題 | 風險 | 來源版本 |\n|----|----|----|----|\n",
            files_by_category={"test": ["TEST-001-a.md", "TEST-001-b.md"]},
        )
        monkeypatch.setattr(_hook, "get_project_root", lambda: str(root))
        exit_code = _hook.main()
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "TEST-001" in captured.err
        assert "[WARNING]" in captured.err

    def test_main_silent_when_fully_synced(self, tmp_path, monkeypatch, capsys):
        root = self._build_fixture_repo(
            tmp_path,
            readme_body=(
                "| ID | 標題 | 風險 | 來源版本 |\n"
                "|----|----|----|----|\n"
                "| TEST-001 | 標題 | 高 | v0.1.0 |\n"
            ),
            files_by_category={"test": ["TEST-001-a.md"]},
        )
        monkeypatch.setattr(_hook, "get_project_root", lambda: str(root))
        exit_code = _hook.main()
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.err == ""

    def test_main_never_exits_nonzero_even_on_missing_readme(self, tmp_path, monkeypatch):
        root = tmp_path / "project"
        (root / ".claude" / "error-patterns").mkdir(parents=True)
        monkeypatch.setattr(_hook, "get_project_root", lambda: str(root))
        exit_code = _hook.main()
        assert exit_code == 0

    def test_main_warns_on_one_way_related(self, tmp_path, monkeypatch, capsys):
        root = tmp_path / "project"
        error_patterns = root / ".claude" / "error-patterns"
        error_patterns.mkdir(parents=True)
        (error_patterns / "README.md").write_text(
            "| ID | 標題 | 風險 | 來源版本 |\n|----|----|----|----|\n"
            "| PC-001 | 標題 A | 高 | v0.1.0 |\n"
            "| PC-002 | 標題 B | 高 | v0.1.0 |\n",
            encoding="utf-8",
        )
        cat_dir = error_patterns / "process-compliance"
        cat_dir.mkdir()
        (cat_dir / "PC-001-a.md").write_text(
            "---\nid: PC-001\nrelated: [PC-002]\ncreated: 2026-08-18\n---\n\n# A\n",
            encoding="utf-8",
        )
        (cat_dir / "PC-002-b.md").write_text(
            "---\nid: PC-002\ncreated: 2026-08-19\n---\n\n# B\n", encoding="utf-8"
        )
        monkeypatch.setattr(_hook, "get_project_root", lambda: str(root))
        exit_code = _hook.main()
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "PC-001" in captured.err
        assert "PC-002" in captured.err
        assert "[WARNING]" in captured.err

    def test_main_silent_when_one_way_outside_same_batch_window(self, tmp_path, monkeypatch, capsys):
        """created 相差超過 7 天視為引註，非姊妹關係，主流程靜默。"""
        root = tmp_path / "project"
        error_patterns = root / ".claude" / "error-patterns"
        error_patterns.mkdir(parents=True)
        (error_patterns / "README.md").write_text(
            "| ID | 標題 | 風險 | 來源版本 |\n|----|----|----|----|\n"
            "| PC-001 | 標題 A | 高 | v0.1.0 |\n"
            "| PC-002 | 標題 B | 高 | v0.1.0 |\n",
            encoding="utf-8",
        )
        cat_dir = error_patterns / "process-compliance"
        cat_dir.mkdir()
        (cat_dir / "PC-001-a.md").write_text(
            "---\nid: PC-001\nrelated: [PC-002]\ncreated: 2026-08-18\n---\n\n# A\n",
            encoding="utf-8",
        )
        (cat_dir / "PC-002-b.md").write_text(
            "---\nid: PC-002\ncreated: 2026-01-01\n---\n\n# B\n", encoding="utf-8"
        )
        monkeypatch.setattr(_hook, "get_project_root", lambda: str(root))
        exit_code = _hook.main()
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.err == ""

    def test_main_silent_when_related_fully_bidirectional(self, tmp_path, monkeypatch, capsys):
        root = tmp_path / "project"
        error_patterns = root / ".claude" / "error-patterns"
        error_patterns.mkdir(parents=True)
        (error_patterns / "README.md").write_text(
            "| ID | 標題 | 風險 | 來源版本 |\n|----|----|----|----|\n"
            "| PC-001 | 標題 A | 高 | v0.1.0 |\n"
            "| PC-002 | 標題 B | 高 | v0.1.0 |\n",
            encoding="utf-8",
        )
        cat_dir = error_patterns / "process-compliance"
        cat_dir.mkdir()
        (cat_dir / "PC-001-a.md").write_text(
            "---\nid: PC-001\nrelated: [PC-002]\n---\n\n# A\n", encoding="utf-8"
        )
        (cat_dir / "PC-002-b.md").write_text(
            "---\nid: PC-002\nrelated: [PC-001]\n---\n\n# B\n", encoding="utf-8"
        )
        monkeypatch.setattr(_hook, "get_project_root", lambda: str(root))
        exit_code = _hook.main()
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.err == ""

    def test_main_silent_for_no_slug_placeholder_listed_in_readme(
        self, tmp_path, monkeypatch, capsys
    ):
        """回歸：allocator 建立的無 slug 佔位檔（已入 README 索引）不應被
        誤判為 stale_in_readme（PC-BAL-040 入庫實證，改名 workaround 前的
        真實紅燈情境）。"""
        root = self._build_fixture_repo(
            tmp_path,
            readme_body=(
                "| ID | 標題 | 風險 | 來源版本 |\n"
                "|----|----|----|----|\n"
                "| PC-BAL-040 | 標題 | 高 | v0.2.1 |\n"
            ),
            files_by_category={"process-compliance": ["PC-BAL-040.md"]},
        )
        monkeypatch.setattr(_hook, "get_project_root", lambda: str(root))
        exit_code = _hook.main()
        captured = capsys.readouterr()
        assert exit_code == 0
        assert captured.err == ""


# ---------------------------------------------------------------------------
# 回歸基線：對現況 repo 執行（非唯一測試對象，僅驗證預期基線 0/0/6）
# ---------------------------------------------------------------------------


class TestCurrentRepoBaseline:
    def test_current_repo_matches_known_baseline(self):
        project_root = Path(__file__).resolve().parents[3]
        error_patterns_root = project_root / ".claude" / "error-patterns"
        methodology_path = (
            project_root / ".claude" / "methodologies" / "error-pattern-numbering-methodology.md"
        )
        if not error_patterns_root.is_dir():
            pytest.skip("error-patterns 目錄不存在，略過回歸基線檢查")

        dir_id_map = _hook.collect_dir_id_map(error_patterns_root)
        readme_ids = _hook.collect_readme_ids(error_patterns_root / "README.md")
        frozen_registry, frozen_error = _hook.parse_frozen_registry(methodology_path)
        assert frozen_error is None, f"凍結表解析失敗：{frozen_error}"

        result = _hook.compare(dir_id_map, readme_ids, frozen_registry)

        assert result["missing_in_readme"] == []
        assert result["stale_in_readme"] == []
        assert result["collisions"] == {}
        assert len(result["registered_collisions"]) == 6

    def test_related_bidirectional_scan_runs_without_error(self):
        """related 雙向性掃描的存量基線非固定斷言（存量會隨其他票修正變動，
        固定數字斷言會使本測試對無關變更假紅燈），僅驗證掃描可正常執行並
        回傳結構正確的清單。實際存量數字由 ticket 執行紀錄另行回報。"""
        project_root = Path(__file__).resolve().parents[3]
        error_patterns_root = project_root / ".claude" / "error-patterns"
        if not error_patterns_root.is_dir():
            pytest.skip("error-patterns 目錄不存在，略過回歸基線檢查")

        related_map = _hook.collect_related_map(error_patterns_root)
        one_way = _hook.check_related_bidirectional(related_map)

        assert isinstance(one_way, list)
        for from_id, to_id, from_rel in one_way:
            assert isinstance(from_id, str) and isinstance(to_id, str)
            assert isinstance(from_rel, str)
