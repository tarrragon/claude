"""
循環依賴檢測模組

使用深度優先搜尋（DFS）演算法偵測有向圖中的環。
提供在 blockedBy 設定時自動觸發的循環檢測功能。

核心演算法：
- 將 Ticket 及其 blockedBy 依賴關係視為有向圖
- 使用 DFS 遍歷圖，追蹤當前路徑
- 若在當前路徑中再次遇到相同節點，表示存在環
- 返回環路路徑便於除錯

時間複雜度：O(V + E)，其中 V 為 Ticket 數，E 為依賴數
空間複雜度：O(V)，用於遞迴棧和訪問追蹤
"""
# 防止直接執行此模組
from typing import Dict, List, Optional, Set, Any, Tuple


class CycleDetector:
    """
    有向圖循環檢測器

    使用 DFS 演算法偵測有向圖中的環。
    基於 Ticket 的 blockedBy 依賴關係構建圖，
    並提供環檢測和路徑追蹤功能。

    設計特點：
    - 純函數式設計（無副作用）
    - 支援偵測多個環
    - 返回完整的環路路徑便於除錯
    - 配合 ticket_validator 進行驗證
    """

    @staticmethod
    def has_cycle(
        ticket_id: str,
        get_dependencies_fn: callable,
        visited: Optional[Set[str]] = None,
        rec_stack: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[List[str]]]:
        """
        檢測以特定 Ticket 開始的依賴圖中是否存在環

        使用 DFS 演算法，維護當前遞迴路徑。
        若在遞迴路徑中再次遇到節點，表示存在環。

        演算法：
        1. 初始化訪問集合和遞迴棧（第一次呼叫時）
        2. 將當前節點標記為已訪問
        3. 加入遞迴棧
        4. 對每個依賴進行遞迴檢查
        5. 若依賴已在遞迴棧中 → 發現環，返回環路
        6. 若依賴未訪問 → 遞迴檢查
        7. 從遞迴棧移除當前節點（回溯）
        8. 返回結果

        Args:
            ticket_id: 起始 Ticket ID
            get_dependencies_fn: 取得 Ticket 依賴的回呼函式
                                簽名：fn(ticket_id) -> List[str]
                                返回該 Ticket 的 blockedBy 依賴清單
            visited: 已訪問節點集合（內部使用）
            rec_stack: 當前遞迴路徑清單（內部使用）

        Returns:
            Tuple[bool, Optional[List[str]]]:
            - (False, None): 無環
            - (True, cycle_path): 有環，返回環路清單
              環路格式：[A, B, C, A]，其中 A 是環的起點和終點

        Examples:
            >>> def get_deps(tid):
            ...     deps = {"A": ["B"], "B": ["C"], "C": ["A"]}
            ...     return deps.get(tid, [])
            >>> has_cycle, path = CycleDetector.has_cycle("A", get_deps)
            >>> has_cycle
            True
            >>> path
            ['A', 'B', 'C', 'A']

            >>> def get_deps_no_cycle(tid):
            ...     deps = {"A": ["B"], "B": ["C"], "C": []}
            ...     return deps.get(tid, [])
            >>> has_cycle, path = CycleDetector.has_cycle("A", get_deps_no_cycle)
            >>> has_cycle
            False
            >>> path is None
            True
        """
        # Guard Clause 1：第一次呼叫時初始化集合
        if visited is None:
            visited = set()
            rec_stack = []

        # Guard Clause 2：入參檢查
        if not ticket_id or not callable(get_dependencies_fn):
            return False, None

        # 將當前節點標記為已訪問
        visited.add(ticket_id)

        # 將當前節點加入遞迴棧（用於環檢測）
        rec_stack.append(ticket_id)

        try:
            # 取得當前 Ticket 的所有依賴
            dependencies = get_dependencies_fn(ticket_id)

            # Guard Clause 3：無依賴，無環
            if not dependencies:
                return False, None

            # 遍歷所有依賴進行遞迴檢查
            for dep_id in dependencies:
                # Guard Clause 4：依賴為空，跳過
                if not dep_id:
                    continue

                # 若依賴在當前遞迴路徑中 → 發現環
                if dep_id in rec_stack:
                    # 從環的起點開始建立環路清單
                    cycle_start_idx = rec_stack.index(dep_id)
                    cycle_path = rec_stack[cycle_start_idx:] + [dep_id]
                    return True, cycle_path

                # 若依賴未訪問 → 遞迴檢查
                if dep_id not in visited:
                    has_cycle_result, cycle_path = CycleDetector.has_cycle(
                        dep_id,
                        get_dependencies_fn,
                        visited,
                        rec_stack
                    )
                    # 若遞迴中發現環 → 立即返回
                    if has_cycle_result:
                        return True, cycle_path

            # 遍歷完成，無環
            return False, None

        finally:
            # 回溯：從遞迴棧移除當前節點
            rec_stack.pop()

    @staticmethod
    def detect_cycles_in_all_tickets(
        all_tickets: List[Dict[str, Any]]
    ) -> List[Tuple[str, List[str]]]:
        """
        檢測所有 Ticket 中的所有循環依賴

        掃描所有 Ticket，對每個 Ticket 進行循環檢測。
        返回所有發現的環。

        演算法：
        1. 建立 Ticket ID 到 blockedBy 的對應表
        2. 建立全域訪問集合（避免重複處理）
        3. 遍歷所有 Ticket
        4. 若未訪問過，對其進行循環檢測
        5. 若發現環，記錄環和起始 Ticket ID
        6. 返回所有環清單

        Args:
            all_tickets: 所有 Ticket 的資料清單

        Returns:
            List[Tuple[str, List[str]]]:
            環的清單，格式為 (起始 Ticket ID, 環路清單)
            空列表表示無環

        Examples:
            >>> tickets = [
            ...     {"id": "A", "blockedBy": ["B"]},
            ...     {"id": "B", "blockedBy": ["C"]},
            ...     {"id": "C", "blockedBy": ["A"]},
            ... ]
            >>> cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
            >>> len(cycles)
            1
            >>> cycles[0][1]  # 環路
            ['A', 'B', 'C', 'A']
        """
        # Guard Clause：無 Ticket
        if not all_tickets:
            return []

        # 建立 Ticket ID 到 blockedBy 的對應表
        ticket_dependencies: Dict[str, List[str]] = {}
        for ticket in all_tickets:
            ticket_id = ticket.get("id")
            blocked_by = ticket.get("blockedBy", [])

            # Guard Clause：無效的 Ticket ID
            if not ticket_id:
                continue

            # 標準化 blockedBy（可能是字串清單或逗號分隔字串）
            if isinstance(blocked_by, str):
                # 若 blockedBy 是字串，分割成清單
                blocked_by = [d.strip() for d in blocked_by.split(",") if d.strip()]
            elif not isinstance(blocked_by, list):
                # 非字串非清單，設為空清單
                blocked_by = []

            ticket_dependencies[ticket_id] = blocked_by

        # 全域訪問集合（避免重複處理同一起始點）
        global_visited: Set[str] = set()
        cycles: List[Tuple[str, List[str]]] = []

        # 定義取得依賴的回呼函式
        def get_deps(ticket_id: str) -> List[str]:
            return ticket_dependencies.get(ticket_id, [])

        # 遍歷所有 Ticket，檢測循環
        for ticket_id in ticket_dependencies.keys():
            # 若已訪問過此起始點，跳過
            if ticket_id in global_visited:
                continue

            # 進行循環檢測
            has_cycle, cycle_path = CycleDetector.has_cycle(
                ticket_id,
                get_deps
            )

            # 標記所有訪問過的節點（避免重複處理）
            global_visited.add(ticket_id)

            # 若發現環 → 記錄
            if has_cycle and cycle_path:
                cycles.append((ticket_id, cycle_path))

        return cycles

    @staticmethod
    def validate_blocked_by(
        ticket_id: str,
        blocked_by: List[str],
        all_tickets: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[str], Optional[List[str]]]:
        """
        驗證設定 blockedBy 時是否會產生循環依賴

        此函式在 ticket_validator 中調用，用於驗證新的依賴關係。
        若設定此依賴會導致循環，應拒絕設定。

        演算法：
        1. 建立臨時 Ticket 清單（加入要驗證的 Ticket）
        2. 使用現有 Ticket 和新 Ticket 構建依賴圖
        3. 檢測新 Ticket 是否會導致環
        4. 返回驗證結果

        Args:
            ticket_id: 要設定依賴的 Ticket ID
            blocked_by: 要設定的依賴清單
            all_tickets: 現有的所有 Ticket 資料

        Returns:
            Tuple[bool, Optional[str], Optional[List[str]]]:
            - (True, None, None): 驗證通過，無環
            - (False, error_msg, cycle_path): 驗證失敗，返回錯誤訊息和環路

        Examples:
            >>> tickets = [
            ...     {"id": "B", "blockedBy": ["C"]},
            ...     {"id": "C", "blockedBy": []},
            ... ]
            >>> # 嘗試設定 A -> B -> C -> A（會產生環）
            >>> valid, msg, path = CycleDetector.validate_blocked_by(
            ...     "A", ["B"], tickets
            ... )
            # 此例無環，因為 C 的依賴為空
            >>> valid
            True

            >>> # 若 C 的依賴為 ["A"]，則會產生環
            >>> tickets = [
            ...     {"id": "B", "blockedBy": ["C"]},
            ...     {"id": "C", "blockedBy": ["A"]},
            ... ]
            >>> valid, msg, path = CycleDetector.validate_blocked_by(
            ...     "A", ["B"], tickets
            ... )
            >>> valid
            False
            >>> path
            ['A', 'B', 'C', 'A']
        """
        # Guard Clause 1：入參檢查
        if not ticket_id:
            return True, None, None

        if not blocked_by:
            return True, None, None

        # Guard Clause 2：檢查直接自我依賴
        if ticket_id in blocked_by:
            cycle_path = [ticket_id, ticket_id]
            error_msg = f"設定依賴會產生循環：{' → '.join(cycle_path)}"
            return False, error_msg, cycle_path

        # Guard Clause 3：無其他 Ticket（無法形成環）
        if not all_tickets:
            return True, None, None

        # 建立臨時 Ticket 清單（包含要驗證的 Ticket）
        temp_tickets = list(all_tickets)

        # 檢查要驗證的 Ticket 是否已存在（防止重複）
        existing_ticket_ids = {t.get("id") for t in temp_tickets}
        if ticket_id not in existing_ticket_ids:
            # 新增要驗證的 Ticket（以待驗證的 blockedBy 值）
            temp_tickets.append({"id": ticket_id, "blockedBy": blocked_by})
        else:
            # 更新現有 Ticket 的 blockedBy
            for ticket in temp_tickets:
                if ticket.get("id") == ticket_id:
                    ticket["blockedBy"] = blocked_by
                    break

        # 檢測所有循環
        cycles = CycleDetector.detect_cycles_in_all_tickets(temp_tickets)

        # 若無環 → 驗證通過
        if not cycles:
            return True, None, None

        # 查詢是否存在包含當前 Ticket 的環
        for start_ticket_id, cycle_path in cycles:
            if ticket_id in cycle_path:
                error_msg = (
                    f"設定依賴會產生循環：{' → '.join(cycle_path)}"
                )
                return False, error_msg, cycle_path

        # 即使有環，但不包含當前 Ticket（不應發生）
        # 為保險起見，返回驗證通過
        return True, None, None


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
