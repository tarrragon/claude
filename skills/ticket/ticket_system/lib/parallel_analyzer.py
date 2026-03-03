"""
並行分析模組

負責分析子任務的並行可行性，判斷任務是否可以並行執行。
純分析層，無 I/O 操作。
"""
# 防止直接執行此模組
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class ParallelAnalysisResult:
    """並行分析結果。"""
    can_parallel: bool
    parallel_groups: List[List[str]] = field(default_factory=list)
    reason: str = ""
    blocked_pairs: List[tuple] = field(default_factory=list)


class ParallelAnalyzer:
    """
    並行分析器

    提供純分析邏輯，用於判斷子任務是否可以並行執行。
    分析基於檔案重疊和依賴關係，不進行 I/O 操作。
    """

    @staticmethod
    def analyze_tasks(tasks: List[Dict]) -> ParallelAnalysisResult:
        """
        分析任務的並行可行性。

        根據以下規則判斷：
        1. 檔案無重疊 → 可並行
        2. 檔案有重疊 → 序列
        3. 有 blockedBy 依賴 → 強制序列

        演算法:
        1. Guard Clause：任務數 < 2 → 無需並行分析
        2. 建立檔案映射（task_id → 影響的檔案集合）
        3. 檢查檔案重疊（使用集合交集）
        4. 檢查依賴關係（blockedBy 欄位）
        5. 如無衝突，使用貪心演算法分組
        6. 返回分析結果

        Args:
            tasks: 子任務清單，每個任務包含：
                   - task_id: 任務 ID（如 "001"、"001.1"）
                   - where_files: 影響的檔案清單（字串列表）
                   - blockedBy: 依賴的任務列表（可選）
                   - title: 任務標題（可選）

        Returns:
            ParallelAnalysisResult: 包含以下資訊的分析結果：
                - can_parallel: bool - 是否可並行執行
                - parallel_groups: List[List[str]] - 可並行的任務群組
                                   (每個群組內的任務可並行執行)
                - reason: str - 判斷理由（中文說明）
                - blocked_pairs: List[tuple] - 衝突的任務對

        Examples:
            >>> tasks = [
            ...     {"task_id": "001", "where_files": ["a.py", "b.py"]},
            ...     {"task_id": "002", "where_files": ["c.py", "d.py"]}
            ... ]
            >>> result = ParallelAnalyzer.analyze_tasks(tasks)
            >>> result.can_parallel
            True
            >>> result.parallel_groups
            [['001', '002']]

            >>> tasks = [
            ...     {"task_id": "001", "where_files": ["a.py"]},
            ...     {"task_id": "002", "where_files": ["a.py"]}
            ... ]
            >>> result = ParallelAnalyzer.analyze_tasks(tasks)
            >>> result.can_parallel
            False
            >>> result.blocked_pairs
            [('001', '002')]
        """
        # Guard Clause：任務數 < 2，無需分析
        if not tasks or len(tasks) < 2:
            return ParallelAnalysisResult(
                can_parallel=len(tasks) <= 1,
                reason="任務數不足 2 個，無需並行分析"
            )

        # 建立檔案映射：task_id → 影響的檔案集合
        file_map = ParallelAnalyzer._build_file_map(tasks)

        # 檢查依賴關係
        dependency_conflicts = ParallelAnalyzer._check_dependencies(tasks)
        if dependency_conflicts:
            return ParallelAnalysisResult(
                can_parallel=False,
                reason=f"任務間有依賴關係，無法並行",
                blocked_pairs=dependency_conflicts
            )

        # 檢查檔案重疊
        file_conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
        if file_conflicts:
            return ParallelAnalysisResult(
                can_parallel=False,
                reason="任務修改的檔案有重疊，無法並行",
                blocked_pairs=file_conflicts
            )

        # 無衝突，使用貪心演算法分組
        parallel_groups = ParallelAnalyzer._build_parallel_groups(tasks, file_map)

        return ParallelAnalysisResult(
            can_parallel=True,
            parallel_groups=parallel_groups,
            reason="任務間無依賴，檔案無重疊，可以並行執行"
        )

    @staticmethod
    def _build_file_map(tasks: List[Dict]) -> Dict[str, Set[str]]:
        """
        建立檔案映射表。

        將每個任務映射到其影響的檔案集合（標準化路徑）。

        Args:
            tasks: 子任務清單

        Returns:
            Dict[str, Set[str]]: task_id → 檔案集合的映射

        Examples:
            >>> tasks = [
            ...     {"task_id": "001", "where_files": ["lib/a.py", "test/a_test.py"]},
            ...     {"task_id": "002", "where_files": ["lib/b.py"]}
            ... ]
            >>> file_map = ParallelAnalyzer._build_file_map(tasks)
            >>> file_map["001"]
            {'lib/a.py', 'test/a_test.py'}
        """
        file_map: Dict[str, Set[str]] = {}

        for task in tasks:
            task_id = task.get("task_id", "")
            files = task.get("where_files", [])

            # Guard Clause：無 task_id，跳過
            if not task_id:
                continue

            # 將檔案清單轉換為集合（自動去重）
            # 使用標準路徑（正斜線）便於比較
            file_set = set()
            if isinstance(files, list):
                for file_path in files:
                    if isinstance(file_path, str):
                        # 標準化路徑：轉換反斜線為正斜線
                        normalized = file_path.replace("\\", "/")
                        file_set.add(normalized)

            file_map[task_id] = file_set

        return file_map

    @staticmethod
    def _check_dependencies(tasks: List[Dict]) -> List[tuple]:
        """
        檢查任務間的依賴關係。

        掃描每個任務的 blockedBy 欄位，找出有依賴的任務對。

        演算法:
        1. 遍歷所有任務
        2. 取得 blockedBy（被阻塞於）清單
        3. 若任務 A 被 B 阻塞，記錄 (B, A)
        4. 返回所有衝突對

        Args:
            tasks: 子任務清單

        Returns:
            List[tuple]: 衝突的任務對清單，格式 (blocking_task, blocked_task)
                        空列表表示無依賴衝突

        Examples:
            >>> tasks = [
            ...     {"task_id": "001", "blockedBy": ["002"]},
            ...     {"task_id": "002"}
            ... ]
            >>> conflicts = ParallelAnalyzer._check_dependencies(tasks)
            >>> conflicts
            [('002', '001')]
        """
        conflicts: List[tuple] = []

        for task in tasks:
            task_id = task.get("task_id", "")
            blocked_by = task.get("blockedBy", [])

            # Guard Clause：無 task_id 或無依賴
            if not task_id or not blocked_by:
                continue

            # 檢查每個依賴
            if isinstance(blocked_by, list):
                for blocking_task_id in blocked_by:
                    if isinstance(blocking_task_id, str):
                        # 記錄依賴關係 (blocking_task, blocked_task)
                        conflicts.append((blocking_task_id, task_id))

        return conflicts

    @staticmethod
    def _glob_matches(pattern: str, path: str) -> bool:
        """
        自定義 glob 匹配，支援 ** 跨越目錄。

        規則:
        - ** 匹配任意層級目錄（包括零個）
        - * 匹配同一層級的任意字符
        - ? 匹配單個字符

        Args:
            pattern: glob 模式
            path: 要匹配的路徑

        Returns:
            bool: 是否匹配
        """
        # 將 glob 模式轉換為正則表達式
        # ** → .* (任意層級)
        # * → [^/]* (單層級任意字符，不匹配 /)
        # ? → . (單個字符)
        # . → \. (轉義點)

        pattern = pattern.replace("\\", "/")
        path = path.replace("\\", "/")

        # 轉換 ** 為特殊標記（防止後續處理時被覆蓋）
        pattern = pattern.replace("**", "\x00DOUBLESTAR\x00")

        # 轉義正則特殊字符
        pattern = re.escape(pattern)

        # 處理萬用字元
        pattern = pattern.replace("\x00DOUBLESTAR\x00", ".*")  # ** → .*
        pattern = pattern.replace(r"\*", "[^/]*")  # * → [^/]*
        pattern = pattern.replace(r"\?", ".")  # ? → .

        # 完整匹配
        regex = f"^{pattern}$"
        return bool(re.match(regex, path))

    @staticmethod
    def _paths_overlap(path1: str, path2: str) -> bool:
        """
        檢查兩個路徑是否有重疊關係（語意分析）。

        規則:
        1. 完全相同 → 重疊
        2. 一個路徑是另一個的父目錄 → 重疊（e.g., lib/ 和 lib/models/book.dart）
        3. 同一目錄下的不同檔案 → 不重疊（e.g., lib/a.dart 和 lib/b.dart）
        4. 支援 glob 模式（e.g., lib/**/*.dart）

        Args:
            path1: 路徑 1（可能包含 glob 模式）
            path2: 路徑 2（可能包含 glob 模式）

        Returns:
            bool: 是否有重疊

        Examples:
            >>> ParallelAnalyzer._paths_overlap("lib/a.dart", "lib/ab.dart")
            False
            >>> ParallelAnalyzer._paths_overlap("lib/a.dart", "lib/a.dart")
            True
            >>> ParallelAnalyzer._paths_overlap("lib/", "lib/models/book.dart")
            True
            >>> ParallelAnalyzer._paths_overlap("lib/models/", "lib/view/")
            False
            >>> ParallelAnalyzer._paths_overlap("lib/**/*.dart", "lib/models/book.dart")
            True
        """
        # 標準化路徑：轉換反斜線為正斜線，移除末尾斜線
        p1 = path1.replace("\\", "/").rstrip("/")
        p2 = path2.replace("\\", "/").rstrip("/")

        # 完全相同
        if p1 == p2:
            return True

        # 處理 glob 模式
        if "*" in p1 or "?" in p1:
            # path1 是 glob 模式，測試 path2 是否匹配
            return ParallelAnalyzer._glob_matches(p1, p2)

        if "*" in p2 or "?" in p2:
            # path2 是 glob 模式，測試 path1 是否匹配
            return ParallelAnalyzer._glob_matches(p2, p1)

        # 使用 Path 物件進行語意分析
        path_obj1 = Path(p1)
        path_obj2 = Path(p2)

        # 父子目錄關係：檢查一個是否是另一個的父目錄
        try:
            # 若 path1 相對於 path2 的路徑不以".."開頭，則 path2 在 path1 下
            path_obj2.relative_to(path_obj1)
            return True
        except ValueError:
            pass

        try:
            # 若 path2 相對於 path1 的路徑不以".."開頭，則 path1 在 path2 下
            path_obj1.relative_to(path_obj2)
            return True
        except ValueError:
            pass

        # 無重疊
        return False

    @staticmethod
    def _check_file_conflicts(file_map: Dict[str, Set[str]]) -> List[tuple]:
        """
        檢查檔案重疊（使用路徑語意分析）。

        比較所有任務對的檔案集合，找出有重疊的任務。

        演算法:
        1. 取得所有 task_id
        2. 比較每一對任務
        3. 對於每對任務的檔案集合，檢查是否有路徑重疊
        4. 若有重疊，記錄衝突對
        5. 使用索引避免重複比較

        Args:
            file_map: task_id → 檔案集合的映射

        Returns:
            List[tuple]: 檔案衝突的任務對，格式 (task_a, task_b)
                        空列表表示無檔案衝突

        Examples:
            >>> file_map = {
            ...     "001": {"lib/a.dart", "test/a_test.dart"},
            ...     "002": {"lib/b.dart"},
            ...     "003": {"lib/a.dart", "test/b_test.dart"}
            ... }
            >>> conflicts = ParallelAnalyzer._check_file_conflicts(file_map)
            >>> ("001", "003") in conflicts
            True
            >>> ("001", "002") in conflicts
            False
        """
        conflicts: List[tuple] = []
        task_ids = list(file_map.keys())

        # 比較所有任務對（避免重複）
        for i in range(len(task_ids)):
            for j in range(i + 1, len(task_ids)):
                task_a = task_ids[i]
                task_b = task_ids[j]

                files_a = file_map[task_a]
                files_b = file_map[task_b]

                # 檢查任務 A 和任務 B 的檔案是否有重疊
                has_overlap = False
                for file_a in files_a:
                    for file_b in files_b:
                        if ParallelAnalyzer._paths_overlap(file_a, file_b):
                            has_overlap = True
                            break
                    if has_overlap:
                        break

                # 若有重疊，記錄衝突
                if has_overlap:
                    conflicts.append((task_a, task_b))

        return conflicts

    @staticmethod
    def _build_parallel_groups(
        tasks: List[Dict],
        file_map: Dict[str, Set[str]]
    ) -> List[List[str]]:
        """
        構建並行群組。

        使用貪心演算法將兼容的任務分組到同一個群組。
        同一群組內的任務可以並行執行（無檔案衝突、無依賴）。

        演算法:
        1. 初始化空群組清單
        2. 遍歷每個任務
        3. 對於當前任務，尋找可以加入的群組
           - 檢查與群組中所有任務的檔案是否重疊
           - 若無重疊，可加入該群組
        4. 若無兼容群組，建立新群組
        5. 返回所有群組

        Args:
            tasks: 子任務清單
            file_map: task_id → 檔案集合的映射

        Returns:
            List[List[str]]: 並行群組清單，每個群組是 task_id 清單

        Examples:
            >>> tasks = [
            ...     {"task_id": "001", "where_files": ["a.py"]},
            ...     {"task_id": "002", "where_files": ["b.py"]},
            ...     {"task_id": "003", "where_files": ["c.py"]}
            ... ]
            >>> file_map = {
            ...     "001": {"a.py"},
            ...     "002": {"b.py"},
            ...     "003": {"c.py"}
            ... }
            >>> groups = ParallelAnalyzer._build_parallel_groups(tasks, file_map)
            >>> len(groups)
            1
            >>> groups[0]
            ['001', '002', '003']
        """
        groups: List[List[str]] = []

        for task in tasks:
            task_id = task.get("task_id", "")

            # Guard Clause：無 task_id
            if not task_id:
                continue

            task_files = file_map.get(task_id, set())

            # 尋找可以加入的群組（檔案無重疊）
            added = False
            for group in groups:
                # 檢查該任務是否與群組中的所有任務兼容
                is_compatible = True
                for group_task_id in group:
                    group_task_files = file_map.get(group_task_id, set())
                    # 若有檔案重疊，不兼容
                    if task_files & group_task_files:
                        is_compatible = False
                        break

                # 若兼容，加入該群組
                if is_compatible:
                    group.append(task_id)
                    added = True
                    break

            # 若無兼容群組，建立新群組
            if not added:
                groups.append([task_id])

        return groups

    @staticmethod
    def get_parallel_summary(result: ParallelAnalysisResult) -> str:
        """
        生成並行分析的文字摘要。

        將分析結果轉換為易於閱讀的文字說明。

        Args:
            result: 並行分析結果

        Returns:
            str: 文字摘要

        Examples:
            >>> result = ParallelAnalysisResult(
            ...     can_parallel=True,
            ...     parallel_groups=[["001", "002"], ["003"]],
            ...     reason="任務間無依賴，檔案無重疊，可以並行執行"
            ... )
            >>> summary = ParallelAnalyzer.get_parallel_summary(result)
            >>> "可以並行" in summary
            True
        """
        summary = f"並行分析結果：{'可以並行' if result.can_parallel else '無法並行'}\n"
        summary += f"理由：{result.reason}\n"

        if result.can_parallel and result.parallel_groups:
            summary += f"\n並行群組：{len(result.parallel_groups)} 個\n"
            for i, group in enumerate(result.parallel_groups, 1):
                summary += f"  群組 {i}: {', '.join(group)}\n"

        if result.blocked_pairs:
            summary += f"\n衝突對：\n"
            for task_a, task_b in result.blocked_pairs:
                summary += f"  {task_a} <-> {task_b}\n"

        return summary


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
