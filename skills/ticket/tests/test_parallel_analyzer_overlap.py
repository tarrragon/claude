"""
並行分析檔案重疊檢測測試

測試 ParallelAnalyzer 的路徑語意重疊檢測功能：
- 完全相同路徑檢測
- 父子目錄關係檢測
- 同目錄不同檔案判斷
- Glob 模式支援
- 混合場景測試

測試案例覆蓋：
- lib/a.dart vs lib/ab.dart → 不重疊（字符串包含誤判防護）
- lib/a.dart vs lib/a.dart → 重疊
- lib/ vs lib/models/book.dart → 重疊（父子目錄）
- lib/**/*.dart vs lib/models/book.dart → 重疊（glob 展開）
- test/ vs lib/ → 不重疊
- 空路徑列表 → 不重疊
"""

import pytest
from typing import List, Dict, Any, Set

from ticket_system.lib.parallel_analyzer import ParallelAnalyzer, ParallelAnalysisResult


class TestPathsOverlap:
    """測試 _paths_overlap() 方法的路徑重疊檢測"""

    def test_identical_paths(self):
        """測試完全相同的路徑"""
        assert ParallelAnalyzer._paths_overlap("lib/a.dart", "lib/a.dart") is True

    def test_no_overlap_string_prefix(self):
        """測試防止字符串包含誤判：lib/a.dart vs lib/ab.dart"""
        # 這是之前會誤判的情況
        assert ParallelAnalyzer._paths_overlap("lib/a.dart", "lib/ab.dart") is False

    def test_no_overlap_sibling_files(self):
        """測試同目錄下的不同檔案：lib/a.dart 和 lib/b.dart"""
        assert ParallelAnalyzer._paths_overlap("lib/a.dart", "lib/b.dart") is False

    def test_parent_directory_overlap(self):
        """測試父子目錄關係：lib/ 和 lib/models/book.dart"""
        assert ParallelAnalyzer._paths_overlap("lib/", "lib/models/book.dart") is True

    def test_parent_directory_overlap_no_slash(self):
        """測試父子目錄關係（不帶末尾斜線）：lib 和 lib/models/book.dart"""
        assert ParallelAnalyzer._paths_overlap("lib", "lib/models/book.dart") is True

    def test_child_directory_overlap(self):
        """測試子目錄是父目錄：lib/models/book.dart 和 lib/"""
        # 順序相反也應該檢測出重疊
        assert ParallelAnalyzer._paths_overlap("lib/models/book.dart", "lib/") is True

    def test_no_overlap_different_directories(self):
        """測試不同的目錄樹：test/ 和 lib/"""
        assert ParallelAnalyzer._paths_overlap("test/", "lib/") is False

    def test_no_overlap_nested_different_directories(self):
        """測試嵌套但不同的目錄：lib/models/ 和 lib/view/"""
        assert ParallelAnalyzer._paths_overlap("lib/models/", "lib/view/") is False

    def test_glob_pattern_match(self):
        """測試 glob 模式：lib/**/*.dart 匹配 lib/models/book.dart"""
        assert ParallelAnalyzer._paths_overlap("lib/**/*.dart", "lib/models/book.dart") is True

    def test_glob_pattern_no_match(self):
        """測試 glob 模式不匹配：lib/**/*.dart 不匹配 test/book.dart"""
        assert ParallelAnalyzer._paths_overlap("lib/**/*.dart", "test/book.dart") is False

    def test_glob_pattern_reverse(self):
        """測試 glob 模式（順序相反）：lib/models/book.dart 匹配 lib/**/*.dart"""
        assert ParallelAnalyzer._paths_overlap("lib/models/book.dart", "lib/**/*.dart") is True

    def test_single_star_glob(self):
        """測試單層 glob：lib/*.dart 匹配 lib/main.dart"""
        assert ParallelAnalyzer._paths_overlap("lib/*.dart", "lib/main.dart") is True

    def test_single_star_glob_no_match_nested(self):
        """測試單層 glob 不匹配嵌套：lib/*.dart 不匹配 lib/models/book.dart"""
        # * 只匹配單層級，不匹配 /，所以 lib/*.dart 不匹配 lib/models/book.dart
        # 但 lib/ 是路徑 lib/models/book.dart 的父目錄，所以會匹配
        # 正確的行為：lib/*.dart 不應該匹配嵌套路徑
        result = ParallelAnalyzer._paths_overlap("lib/*.dart", "lib/models/book.dart")
        assert result is False

    def test_question_mark_glob(self):
        """測試 ? 萬用字元：lib/?.dart 匹配 lib/a.dart"""
        assert ParallelAnalyzer._paths_overlap("lib/?.dart", "lib/a.dart") is True

    def test_question_mark_glob_no_match(self):
        """測試 ? 萬用字元不匹配：lib/?.dart 不匹配 lib/ab.dart"""
        assert ParallelAnalyzer._paths_overlap("lib/?.dart", "lib/ab.dart") is False

    def test_backslash_normalization(self):
        """測試反斜線正規化：lib\\a.dart 應該等同於 lib/a.dart"""
        assert ParallelAnalyzer._paths_overlap("lib\\a.dart", "lib/a.dart") is True

    def test_trailing_slash_normalization(self):
        """測試末尾斜線正規化：lib/ 和 lib 應該視為相同"""
        assert ParallelAnalyzer._paths_overlap("lib/", "lib") is True

    def test_deep_nested_paths(self):
        """測試深層嵌套路徑：lib/domain/entities/book.dart 在 lib/"""
        assert ParallelAnalyzer._paths_overlap("lib/", "lib/domain/entities/book.dart") is True

    def test_complex_glob_pattern(self):
        """測試複雜 glob：lib/**/*_test.dart 匹配 lib/models/book_test.dart"""
        assert ParallelAnalyzer._paths_overlap("lib/**/*_test.dart", "lib/models/book_test.dart") is True

    def test_glob_with_question_mark(self):
        """測試組合 glob：lib/**/*_test.dart 不匹配 lib/test.dart"""
        # lib/**/*_test.dart 表示在 lib/ 下的任何層級的 *_test.dart 檔案
        # 但 lib/test.dart 沒有匹配到 lib/**/那部分（** 之後必須有 /）
        # 實際上這個 glob 應該匹配 lib/models/book_test.dart 這樣的結構
        # lib/test.dart 不符合 lib/**/*_test.dart，因為 ** 後面要有其他內容
        result = ParallelAnalyzer._paths_overlap("lib/**/*_test.dart", "lib/test.dart")
        assert result is False


class TestCheckFileConflicts:
    """測試 _check_file_conflicts() 方法"""

    def test_no_conflicts_different_files(self):
        """測試無衝突：不同的檔案"""
        file_map = {
            "001": {"lib/a.dart", "lib/b.dart"},
            "002": {"lib/c.dart", "lib/d.dart"}
        }
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        assert len(conflicts) == 0

    def test_conflict_same_file(self):
        """測試衝突：修改相同檔案"""
        file_map = {
            "001": {"lib/a.dart"},
            "002": {"lib/a.dart"}
        }
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        assert ("001", "002") in conflicts or ("002", "001") in conflicts

    def test_no_conflict_sibling_files(self):
        """測試無衝突：同目錄下的不同檔案"""
        file_map = {
            "001": {"lib/a.dart"},
            "002": {"lib/b.dart"}
        }
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        assert len(conflicts) == 0

    def test_conflict_parent_child(self):
        """測試衝突：父子目錄關係"""
        file_map = {
            "001": {"lib/"},
            "002": {"lib/models/book.dart"}
        }
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        assert ("001", "002") in conflicts or ("002", "001") in conflicts

    def test_no_conflict_string_prefix(self):
        """測試無衝突：防止字符串包含誤判"""
        file_map = {
            "001": {"lib/a.dart"},
            "002": {"lib/ab.dart"}
        }
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        assert len(conflicts) == 0

    def test_conflict_with_glob(self):
        """測試衝突：glob 模式與具體檔案"""
        file_map = {
            "001": {"lib/**/*.dart"},
            "002": {"lib/models/book.dart"}
        }
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        assert ("001", "002") in conflicts or ("002", "001") in conflicts

    def test_no_conflict_different_dirs(self):
        """測試無衝突：不同目錄樹"""
        file_map = {
            "001": {"lib/"},
            "002": {"test/"}
        }
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        assert len(conflicts) == 0

    def test_multiple_tasks_complex(self):
        """測試複雜場景：多個任務，部分衝突"""
        file_map = {
            "001": {"lib/a.dart"},
            "002": {"lib/b.dart"},
            "003": {"lib/a.dart"},  # 與 001 衝突
            "004": {"test/a_test.dart"}  # 無衝突
        }
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        # 應該找到 001 和 003 的衝突
        assert ("001", "003") in conflicts or ("003", "001") in conflicts
        # 不應該有其他衝突
        assert len(conflicts) == 1

    def test_empty_file_map(self):
        """測試空檔案映射"""
        file_map: Dict[str, Set[str]] = {}
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        assert len(conflicts) == 0

    def test_single_task(self):
        """測試單一任務"""
        file_map = {
            "001": {"lib/a.dart"}
        }
        conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        assert len(conflicts) == 0


class TestAnalyzeTasks:
    """測試 analyze_tasks() 完整流程"""

    def test_no_conflict_can_parallel(self):
        """測試可並行：無衝突、無依賴"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/a.dart"]},
            {"task_id": "002", "where_files": ["lib/b.dart"]}
        ]
        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert result.can_parallel is True
        assert len(result.parallel_groups) == 1
        assert set(result.parallel_groups[0]) == {"001", "002"}

    def test_file_conflict_cannot_parallel(self):
        """測試不可並行：檔案衝突"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/a.dart"]},
            {"task_id": "002", "where_files": ["lib/a.dart"]}
        ]
        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert result.can_parallel is False
        assert len(result.blocked_pairs) > 0

    def test_sibling_files_can_parallel(self):
        """測試可並行：同目錄下的不同檔案"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/models/book.dart"]},
            {"task_id": "002", "where_files": ["lib/models/author.dart"]}
        ]
        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert result.can_parallel is True

    def test_parent_child_dirs_cannot_parallel(self):
        """測試不可並行：父子目錄關係"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/"]},
            {"task_id": "002", "where_files": ["lib/models/book.dart"]}
        ]
        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert result.can_parallel is False

    def test_dependency_cannot_parallel(self):
        """測試不可並行：有依賴關係"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/a.dart"]},
            {"task_id": "002", "where_files": ["lib/b.dart"], "blockedBy": ["001"]}
        ]
        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert result.can_parallel is False

    def test_string_prefix_false_positive(self):
        """測試防止字符串包含誤判（完整流程）"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/a.dart"]},
            {"task_id": "002", "where_files": ["lib/ab.dart"]}
        ]
        result = ParallelAnalyzer.analyze_tasks(tasks)
        # 應該可並行，因為檔案不重疊
        assert result.can_parallel is True
        assert len(result.parallel_groups) == 1

    def test_glob_pattern_conflict(self):
        """測試 glob 模式檔案衝突"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/**/*.dart"]},
            {"task_id": "002", "where_files": ["lib/models/book.dart"]}
        ]
        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert result.can_parallel is False

    def test_complex_scenario_multiple_groups(self):
        """測試複雜場景：可形成多個並行群組"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/a.dart"]},
            {"task_id": "002", "where_files": ["lib/b.dart"]},
            {"task_id": "003", "where_files": ["test/a_test.dart"]},
            {"task_id": "004", "where_files": ["test/b_test.dart"]}
        ]
        result = ParallelAnalyzer.analyze_tasks(tasks)
        assert result.can_parallel is True
        # 應該分成 2 個群組（lib 和 test）或 1 個群組（都可並行）
        assert len(result.parallel_groups) >= 1

    def test_empty_tasks(self):
        """測試空任務列表"""
        result = ParallelAnalyzer.analyze_tasks([])
        assert result.can_parallel is True
        assert len(result.parallel_groups) == 0

    def test_single_task(self):
        """測試單一任務"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/a.dart"]}
        ]
        result = ParallelAnalyzer.analyze_tasks(tasks)
        # 單一任務無需並行分析，返回 can_parallel=True 但 parallel_groups 為空
        assert result.can_parallel is True
        # Guard Clause：任務數 < 2，無需構建並行群組
        assert len(result.parallel_groups) == 0


class TestBuildFileMap:
    """測試 _build_file_map() 方法"""

    def test_build_file_map_basic(self):
        """測試基本檔案映射"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/a.dart", "lib/b.dart"]},
            {"task_id": "002", "where_files": ["test/a_test.dart"]}
        ]
        file_map = ParallelAnalyzer._build_file_map(tasks)
        assert file_map["001"] == {"lib/a.dart", "lib/b.dart"}
        assert file_map["002"] == {"test/a_test.dart"}

    def test_build_file_map_backslash_normalization(self):
        """測試反斜線正規化"""
        tasks = [
            {"task_id": "001", "where_files": ["lib\\a.dart", "lib\\b.dart"]}
        ]
        file_map = ParallelAnalyzer._build_file_map(tasks)
        assert file_map["001"] == {"lib/a.dart", "lib/b.dart"}

    def test_build_file_map_deduplication(self):
        """測試重複檔案去重"""
        tasks = [
            {"task_id": "001", "where_files": ["lib/a.dart", "lib/a.dart", "lib/b.dart"]}
        ]
        file_map = ParallelAnalyzer._build_file_map(tasks)
        assert len(file_map["001"]) == 2

    def test_build_file_map_empty_files(self):
        """測試空檔案列表"""
        tasks = [
            {"task_id": "001", "where_files": []}
        ]
        file_map = ParallelAnalyzer._build_file_map(tasks)
        assert file_map["001"] == set()

    def test_build_file_map_missing_task_id(self):
        """測試缺少 task_id"""
        tasks = [
            {"where_files": ["lib/a.dart"]},
            {"task_id": "002", "where_files": ["lib/b.dart"]}
        ]
        file_map = ParallelAnalyzer._build_file_map(tasks)
        assert "002" in file_map
        assert len(file_map) == 1
