"""
關鍵路徑分析模組

使用 Critical Path Method（CPM）演算法識別專案中影響整體進度的關鍵任務。
由於 Ticket 無明確工期，本實作將每個 Ticket 視為等權重（duration = 1），
因此 CPM 退化為「最長路徑」問題。

核心演算法：
- 正向遍歷（Forward Pass）：計算每個節點的最早開始時間（ES）和最早完成時間（EF）
- 反向遍歷（Backward Pass）：計算最晚開始時間（LS）和最晚完成時間（LF）
- 浮動時間計算：Slack = LS - ES，Slack = 0 的節點在關鍵路徑上
- 關鍵路徑：DAG 中最長的依賴鏈

時間複雜度：O(V + E)，其中 V 為 Ticket 數，E 為依賴數
空間複雜度：O(V)
"""
# 防止直接執行此模組
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from collections import defaultdict

from .cycle_detector import CycleDetector
from .ui_constants import SEPARATOR_SECONDARY, SEPARATOR_SECONDARY_DASH


@dataclass
class CriticalPathResult:
    """
    關鍵路徑分析結果

    儲存 CPM 計算得出的關鍵路徑和進度時程資訊。
    """
    critical_path: List[str] = field(default_factory=list)  # 關鍵路徑上的 ticket_ids（按順序）
    critical_path_length: int = 0  # 關鍵路徑長度（最長路徑的節點數）
    ticket_schedule: Dict[str, Dict] = field(
        default_factory=dict
    )  # ticket_id → {"es": int, "ef": int, "ls": int, "lf": int, "slack": int}
    is_valid: bool = True  # DAG 是否有效（無環）
    cycle_info: Optional[List[str]] = None  # 若有環，環路資訊
    all_critical_paths: List[List[str]] = field(
        default_factory=list
    )  # 所有關鍵路徑（可能有多條等長的關鍵路徑）


class CriticalPathAnalyzer:
    """
    關鍵路徑分析器

    使用 CPM 演算法計算關鍵路徑和進度時程。
    設計特點：
    - 純函式式設計（無副作用）
    - 整合 CycleDetector 進行環檢測
    - 支援孤立節點（無依賴也無被依賴）
    - Guard Clause 風格處理邊界情況
    """

    @staticmethod
    def analyze(
        tickets: List[Dict], duration_map: Optional[Dict[str, int]] = None
    ) -> CriticalPathResult:
        """
        使用 CPM 計算關鍵路徑

        演算法步驟：
        1. Guard Clause：檢查輸入有效性
        2. 建立票據 ID 集合（用於識別外部依賴）
        3. 使用 CycleDetector 檢查循環依賴
        4. 若有環，返回無效結果
        5. 建立鄰接表和反向鄰接表
        6. 正向遍歷：計算 ES 和 EF
        7. 反向遍歷：計算 LS 和 LF
        8. 計算 Slack 並識別關鍵路徑（Slack = 0 的節點）
        9. 回溯找出所有關鍵路徑
        10. 返回結果

        blockedBy 語義：
        若 B.blockedBy = [A]，表示 A 必須先完成，B 才能開始。
        所以 A 必定在 B 之前的路徑上。

        Args:
            tickets: Ticket 清單，每個 Ticket 包含：
                   - id: Ticket ID（如 "0.31.0-W4-001"）
                   - blockedBy: 依賴的 Ticket ID 清單（可選，預設 []）
                   其他欄位會被忽略
            duration_map: 可選的工期映射 {ticket_id: duration}
                         若未提供，預設每個 Ticket 工期為 1

        Returns:
            CriticalPathResult: 包含以下資訊的分析結果：
                - critical_path: List[str] - 關鍵路徑上的 ticket_ids（按順序）
                - critical_path_length: int - 關鍵路徑的長度
                - ticket_schedule: Dict - 每個 ticket 的時程資訊
                  - es: 最早開始時間
                  - ef: 最早完成時間
                  - ls: 最晚開始時間
                  - lf: 最晚完成時間
                  - slack: 浮動時間
                - is_valid: bool - 是否為有效 DAG（無環）
                - cycle_info: Optional[List[str]] - 環路資訊（若有環）
                - all_critical_paths: List[List[str]] - 所有關鍵路徑

        Examples:
            >>> # 無依賴 Ticket → 都在關鍵路徑上
            >>> tickets = [
            ...     {"id": "A", "blockedBy": []},
            ...     {"id": "B", "blockedBy": []},
            ... ]
            >>> result = CriticalPathAnalyzer.analyze(tickets)
            >>> len(result.critical_path)  # 孤立節點都在關鍵路徑上
            2
            >>> result.critical_path_length
            1

            >>> # 線性依賴：A → B → C
            >>> tickets = [
            ...     {"id": "A", "blockedBy": []},
            ...     {"id": "B", "blockedBy": ["A"]},
            ...     {"id": "C", "blockedBy": ["B"]},
            ... ]
            >>> result = CriticalPathAnalyzer.analyze(tickets)
            >>> result.critical_path
            ['A', 'B', 'C']
            >>> result.critical_path_length
            3
        """
        # Guard Clause 1：無票據
        if not tickets:
            return CriticalPathResult(
                critical_path=[],
                critical_path_length=0,
                ticket_schedule={},
                is_valid=True,
                cycle_info=None,
                all_critical_paths=[],
            )

        # 建立票據 ID 集合
        all_ticket_ids = {ticket.get("id") for ticket in tickets if ticket.get("id")}

        # Guard Clause 2：無有效票據 ID
        if not all_ticket_ids:
            return CriticalPathResult(
                critical_path=[],
                critical_path_length=0,
                ticket_schedule={},
                is_valid=True,
                cycle_info=None,
                all_critical_paths=[],
            )

        # 步驟 1：檢查循環依賴
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        if cycles:
            _, cycle_path = cycles[0]
            return CriticalPathResult(
                critical_path=[],
                critical_path_length=0,
                ticket_schedule={},
                is_valid=False,
                cycle_info=cycle_path,
                all_critical_paths=[],
            )

        # 步驟 2：初始化工期映射（預設每個 Ticket 工期為 1）
        if duration_map is None:
            duration_map = {}

        def get_duration(ticket_id: str) -> int:
            """取得 Ticket 的工期，預設為 1"""
            return duration_map.get(ticket_id, 1)

        # 步驟 3：建立鄰接表和反向鄰接表
        # adjacency_list: ticket_id → [依賴它的 ticket_ids]
        # reverse_adjacency_list: ticket_id → [它依賴的 ticket_ids]
        adjacency_list: Dict[str, List[str]] = defaultdict(list)
        reverse_adjacency_list: Dict[str, List[str]] = defaultdict(list)

        for ticket in tickets:
            ticket_id = ticket.get("id")
            blocked_by = ticket.get("blockedBy", [])

            # Guard Clause：無效 ticket_id
            if not ticket_id or ticket_id not in all_ticket_ids:
                continue

            # 標準化 blockedBy
            if isinstance(blocked_by, str):
                blocked_by = [d.strip() for d in blocked_by.split(",") if d.strip()]
            elif not isinstance(blocked_by, list):
                blocked_by = []

            # 為每個依賴建立邊
            for dep_id in blocked_by:
                # Guard Clause：忽略不存在的依賴（外部依賴）
                if dep_id not in all_ticket_ids:
                    continue

                # 邊：dep_id → ticket_id
                adjacency_list[dep_id].append(ticket_id)
                reverse_adjacency_list[ticket_id].append(dep_id)

        # 步驟 4：正向遍歷（Forward Pass）計算 ES 和 EF
        # ES（最早開始時間）= max(所有前置節點的 EF)
        # EF（最早完成時間）= ES + duration
        es_time: Dict[str, int] = {}
        ef_time: Dict[str, int] = {}

        def compute_forward_pass(ticket_id: str) -> int:
            """
            遞迴計算某個 Ticket 的 EF（最早完成時間）
            使用備忘錄模式避免重複計算
            """
            # 如果已計算過，直接返回
            if ticket_id in ef_time:
                return ef_time[ticket_id]

            # 計算前置節點的最大 EF
            predecessors = reverse_adjacency_list.get(ticket_id, [])

            if not predecessors:
                # 無前置節點，ES = 0
                es_time[ticket_id] = 0
            else:
                # ES = max(所有前置節點的 EF)
                max_predecessor_ef = max(
                    compute_forward_pass(pred) for pred in predecessors
                )
                es_time[ticket_id] = max_predecessor_ef

            # EF = ES + duration
            duration = get_duration(ticket_id)
            ef_time[ticket_id] = es_time[ticket_id] + duration

            return ef_time[ticket_id]

        # 對所有 Ticket 執行正向遍歷
        for ticket_id in all_ticket_ids:
            compute_forward_pass(ticket_id)

        # 計算專案最早完成時間（所有節點的最大 EF）
        project_ef = max(ef_time.values()) if ef_time else 0

        # 步驟 5：反向遍歷（Backward Pass）計算 LS 和 LF
        # LF（最晚完成時間）= min(所有後繼節點的 LS)
        # LS（最晚開始時間）= LF - duration
        ls_time: Dict[str, int] = {}
        lf_time: Dict[str, int] = {}

        def compute_backward_pass(ticket_id: str) -> int:
            """
            遞迴計算某個 Ticket 的 LS（最晚開始時間）
            使用備忘錄模式避免重複計算
            """
            # 如果已計算過，直接返回
            if ticket_id in ls_time:
                return ls_time[ticket_id]

            # 計算後繼節點的最小 LS
            successors = adjacency_list.get(ticket_id, [])

            if not successors:
                # 無後繼節點，LF = 專案完成時間
                lf_time[ticket_id] = project_ef
            else:
                # LF = min(所有後繼節點的 LS)
                min_successor_ls = min(
                    compute_backward_pass(succ) for succ in successors
                )
                lf_time[ticket_id] = min_successor_ls

            # LS = LF - duration
            duration = get_duration(ticket_id)
            ls_time[ticket_id] = lf_time[ticket_id] - duration

            return ls_time[ticket_id]

        # 對所有 Ticket 執行反向遍歷
        for ticket_id in all_ticket_ids:
            compute_backward_pass(ticket_id)

        # 步驟 6：計算 Slack 並建立時程表
        ticket_schedule: Dict[str, Dict] = {}
        critical_tickets: Set[str] = set()

        for ticket_id in all_ticket_ids:
            slack = ls_time[ticket_id] - es_time[ticket_id]
            ticket_schedule[ticket_id] = {
                "es": es_time[ticket_id],
                "ef": ef_time[ticket_id],
                "ls": ls_time[ticket_id],
                "lf": lf_time[ticket_id],
                "slack": slack,
            }

            # Slack = 0 的節點在關鍵路徑上
            if slack == 0:
                critical_tickets.add(ticket_id)

        # 步驟 7：識別所有關鍵路徑
        # 關鍵路徑是從起點（無前置節點）到終點（無後繼節點）的路徑
        # 且路徑上所有節點的 slack = 0
        all_critical_paths = CriticalPathAnalyzer._find_all_critical_paths(
            all_ticket_ids,
            critical_tickets,
            reverse_adjacency_list,
            adjacency_list,
        )

        # Guard Clause：無關鍵路徑（不應發生）
        if not all_critical_paths:
            # 若無關鍵路徑，返回最長路徑
            all_critical_paths = CriticalPathAnalyzer._find_longest_paths(
                all_ticket_ids, reverse_adjacency_list, adjacency_list, ef_time
            )

        # 選擇第一條關鍵路徑作為主關鍵路徑
        primary_critical_path = all_critical_paths[0] if all_critical_paths else []
        critical_path_length = len(primary_critical_path)

        return CriticalPathResult(
            critical_path=primary_critical_path,
            critical_path_length=critical_path_length,
            ticket_schedule=ticket_schedule,
            is_valid=True,
            cycle_info=None,
            all_critical_paths=all_critical_paths,
        )

    @staticmethod
    def _find_all_critical_paths(
        all_ticket_ids: Set[str],
        critical_tickets: Set[str],
        reverse_adjacency_list: Dict[str, List[str]],
        adjacency_list: Dict[str, List[str]],
    ) -> List[List[str]]:
        """
        找出所有關鍵路徑

        從所有起點（無前置節點且在關鍵路徑上）開始，
        使用 DFS 回溯找出所有從起點到終點的關鍵路徑。

        Args:
            all_ticket_ids: 所有 Ticket ID
            critical_tickets: 在關鍵路徑上的 Ticket ID（slack = 0）
            reverse_adjacency_list: 反向依賴圖
            adjacency_list: 依賴圖

        Returns:
            List[List[str]]: 所有關鍵路徑
        """
        # Guard Clause
        if not critical_tickets:
            return []

        # 找出所有起點（無前置節點且在關鍵路徑上）
        start_nodes = [
            tid
            for tid in critical_tickets
            if tid not in reverse_adjacency_list or not reverse_adjacency_list[tid]
        ]

        # Guard Clause
        if not start_nodes:
            return []

        all_paths = []

        def dfs_find_critical_paths(
            current: str, path: List[str], visited: Set[str]
        ) -> None:
            """
            DFS 回溯找出關鍵路徑

            從當前節點開始，沿著關鍵節點遍歷到終點（無後繼節點）
            """
            # 是否為終點（無後繼節點或所有後繼都不在關鍵路徑上）
            successors = [
                succ
                for succ in adjacency_list.get(current, [])
                if succ in critical_tickets
            ]

            if not successors:
                # 到達終點，記錄路徑
                all_paths.append(path[:])
                return

            # DFS 遍歷所有後繼
            for succ in successors:
                if succ not in visited:
                    path.append(succ)
                    visited.add(succ)
                    dfs_find_critical_paths(succ, path, visited)
                    path.pop()
                    visited.remove(succ)

        # 從所有起點開始 DFS
        for start in start_nodes:
            dfs_find_critical_paths(start, [start], {start})

        return all_paths

    @staticmethod
    def _find_longest_paths(
        all_ticket_ids: Set[str],
        reverse_adjacency_list: Dict[str, List[str]],
        adjacency_list: Dict[str, List[str]],
        ef_time: Dict[str, int],
    ) -> List[List[str]]:
        """
        找出最長路徑（備用方案，當無關鍵路徑時使用）

        Args:
            all_ticket_ids: 所有 Ticket ID
            reverse_adjacency_list: 反向依賴圖
            adjacency_list: 依賴圖
            ef_time: EF 時間映射

        Returns:
            List[List[str]]: 最長路徑清單
        """
        # 找出所有起點（無前置節點）
        start_nodes = [
            tid
            for tid in all_ticket_ids
            if tid not in reverse_adjacency_list or not reverse_adjacency_list[tid]
        ]

        if not start_nodes:
            return []

        # 找出最大 EF
        max_ef = max(ef_time.values()) if ef_time else 0

        # 找出所有終點（EF = max_ef）
        end_nodes = [tid for tid in all_ticket_ids if ef_time.get(tid, 0) == max_ef]

        longest_paths = []

        def dfs_find_longest(current: str, path: List[str]) -> None:
            """DFS 找出最長路徑"""
            if current in end_nodes:
                longest_paths.append(path[:])
                return

            successors = adjacency_list.get(current, [])
            if not successors:
                longest_paths.append(path[:])
                return

            for succ in successors:
                if succ not in path:  # 避免環
                    path.append(succ)
                    dfs_find_longest(succ, path)
                    path.pop()

        # 從所有起點開始 DFS
        for start in start_nodes:
            dfs_find_longest(start, [start])

        return longest_paths

    @staticmethod
    def get_critical_path_summary(result: CriticalPathResult) -> str:
        """
        產生可讀的關鍵路徑分析摘要

        使用 analyze() 的結果，格式化為易於閱讀的文字說明。
        若計算失敗（有環），返回錯誤訊息。

        Args:
            result: CPM 分析結果

        Returns:
            str: 文字格式的關鍵路徑分析摘要

        Examples:
            >>> tickets = [
            ...     {"id": "A", "blockedBy": []},
            ...     {"id": "B", "blockedBy": ["A"]},
            ... ]
            >>> result = CriticalPathAnalyzer.analyze(tickets)
            >>> summary = CriticalPathAnalyzer.get_critical_path_summary(result)
            >>> "關鍵路徑" in summary
            True
        """
        # Guard Clause：計算失敗
        if not result.is_valid:
            if result.cycle_info:
                cycle_str = " → ".join(result.cycle_info)
                return f"計算失敗：發現循環依賴\n環路：{cycle_str}"
            else:
                return "計算失敗：未知錯誤"

        # Guard Clause：無 Ticket
        if result.critical_path_length == 0:
            return "無 Ticket，無關鍵路徑"

        # 格式化輸出
        summary = f"關鍵路徑分析結果\n"
        summary += SEPARATOR_SECONDARY + "\n\n"

        summary += f"關鍵路徑長度：{result.critical_path_length}\n"
        summary += f"關鍵路徑：{' → '.join(result.critical_path)}\n"

        # 若有多條關鍵路徑
        if len(result.all_critical_paths) > 1:
            summary += f"\n備選關鍵路徑（共 {len(result.all_critical_paths)} 條）：\n"
            for i, path in enumerate(result.all_critical_paths[1:], start=2):
                summary += f"  {i}. {' → '.join(path)}\n"

        # 時程資訊（僅列出關鍵路徑上的節點）
        summary += "\n關鍵路徑上的節點時程：\n"
        summary += SEPARATOR_SECONDARY_DASH + "\n"
        summary += f"{'Ticket':<15} {'ES':<5} {'EF':<5} {'LS':<5} {'LF':<5} {'Slack':<5}\n"
        summary += SEPARATOR_SECONDARY_DASH + "\n"

        for ticket_id in result.critical_path:
            schedule = result.ticket_schedule.get(ticket_id, {})
            es = schedule.get("es", 0)
            ef = schedule.get("ef", 0)
            ls = schedule.get("ls", 0)
            lf = schedule.get("lf", 0)
            slack = schedule.get("slack", 0)

            summary += (
                f"{ticket_id:<15} {es:<5} {ef:<5} {ls:<5} {lf:<5} {slack:<5}\n"
            )

        return summary.rstrip()

    @staticmethod
    def identify_bottlenecks(result: CriticalPathResult, threshold: int = 0) -> List[
        str
    ]:
        """
        識別瓶頸任務

        Slack <= threshold 的任務被視為瓶頸。
        - threshold = 0（預設）：僅關鍵路徑上的任務（slack = 0）
        - threshold > 0：包含接近關鍵路徑的任務

        Args:
            result: CPM 分析結果
            threshold: slack 閾值，預設 0

        Returns:
            List[str]: 瓶頸 ticket_ids 清單（按 slack 排序）

        Examples:
            >>> tickets = [
            ...     {"id": "A", "blockedBy": []},
            ...     {"id": "B", "blockedBy": ["A"]},
            ...     {"id": "C", "blockedBy": []},
            ... ]
            >>> result = CriticalPathAnalyzer.analyze(tickets)
            >>> bottlenecks = CriticalPathAnalyzer.identify_bottlenecks(result, threshold=0)
            >>> "A" in bottlenecks
            True
            >>> "B" in bottlenecks
            True
        """
        # Guard Clause：無時程資訊
        if not result.ticket_schedule:
            return []

        # 找出所有 slack <= threshold 的 Ticket
        bottlenecks = [
            ticket_id
            for ticket_id, schedule in result.ticket_schedule.items()
            if schedule.get("slack", float("inf")) <= threshold
        ]

        # 按 slack 排序（slack 小的優先）
        bottlenecks.sort(
            key=lambda tid: result.ticket_schedule[tid].get("slack", float("inf"))
        )

        return bottlenecks


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
