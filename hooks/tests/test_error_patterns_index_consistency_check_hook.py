"""
Error Patterns Index Consistency Check Hook 測試

涵蓋範圍：
1. extract_filename_id — 檔名 ID 抽取（含可選中段 PC-BAL-001 / IMP-V1-006 / PC-SCLK-004）
2. collect_dir_id_map — 目錄掃描 + ID 分組（含碰撞情境）
3. collect_readme_ids — README 表格列 ID 抽取（含消歧括號註記）
4. compare — 三項比對邏輯（缺漏 / 過時 / 碰撞）各自正例反例
5. format_report — 有/無發現時的輸出格式
6. main — 端對端 tmp fixture 情境 + 對現況 repo 的回歸基線
"""

import importlib.util
import sys
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
