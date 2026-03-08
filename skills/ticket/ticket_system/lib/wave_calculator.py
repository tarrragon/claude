"""
Wave 自動計算模組

使用 Kahn's Algorithm（拓撲排序）自動計算最優 Wave 分組。
根據 Ticket 的 blockedBy 依賴關係，將 Ticket 分配到不同的 Wave（執行批次）。
同一 Wave 中的 Ticket 可以並行執行（無先後依賴關係）。

核心演算法：
- 將 Ticket 及其 blockedBy 依賴關係視為有向圖
- 建立鄰接表（被依賴者 → 依賴者清單）和入度表
- 使用 CycleDetector 先檢查是否存在循環依賴
- 使用 BFS 層級遍歷（Kahn's Algorithm）
- 入度為 0 的節點歸為同一 Wave
- 移除一層節點後，新的入度為 0 的節點構成下一 Wave

時間複雜度：O(V + E)，其中 V 為 Ticket 數，E 為依賴數
空間複雜度：O(V)，用於圖表示和佇列
"""
# 防止直接執行此模組
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque

from .cycle_detector import CycleDetector
from .ui_constants import SEPARATOR_SECONDARY


@dataclass
class WaveCalculationResult:
    """
    Wave 計算結果

    儲存 Kahn's Algorithm 計算得出的 Wave 分配結果。
    """
    waves: Dict[int, List[str]] = field(default_factory=dict)  # wave_number → [ticket_ids]
    ticket_wave_map: Dict[str, int] = field(default_factory=dict)  # ticket_id → wave_number
    total_waves: int = 0  # Wave 總數
    is_valid: bool = True  # 是否為有效 DAG（無環）
    cycle_info: Optional[List[str]] = None  # 若有環，環路資訊


class WaveCalculator:
    """
    自動 Wave 計算器

    使用 Kahn's Algorithm 實作拓撲排序，自動計算最優 Wave 分組。
    設計特點：
    - 純函式式設計（無副作用）
    - 整合 CycleDetector 進行環檢測
    - 支援孤立節點（無依賴也無被依賴）
    - Guard Clause 風格處理邊界情況
    """

    @staticmethod
    def calculate_waves(tickets: List[Dict]) -> WaveCalculationResult:
        """
        使用 Kahn's Algorithm 計算最優 Wave 分組

        演算法步驟：
        1. Guard Clause：檢查輸入有效性
        2. 建立票據 ID 集合（用於識別外部依賴）
        3. 建立鄰接表和入度表
        4. 使用 CycleDetector 檢查循環依賴
        5. 若有環，返回無效結果
        6. BFS 層級遍歷：
           - 初始化佇列（入度為 0 的節點）
           - 逐層處理，每層構成一個 Wave
           - 移除節點，更新相依節點的入度
           - 直到佇列為空
        7. 驗證所有節點是否都被處理（無孤立環）

        blockedBy 語義：
        若 B.blockedBy = [A]，表示 A 必須先完成，B 才能開始。
        所以 A 在較早的 Wave，B 在較晚的 Wave。

        Args:
            tickets: Ticket 清單，每個 Ticket 包含：
                   - id: Ticket ID（如 "0.31.0-W4-001"）
                   - blockedBy: 依賴的 Ticket ID 清單（可選，預設 []）
                   其他欄位會被忽略

        Returns:
            WaveCalculationResult: 包含以下資訊的計算結果：
                - waves: Dict[int, List[str]] - wave_number → [ticket_ids]
                         Wave 編號從 1 開始
                - ticket_wave_map: Dict[str, int] - ticket_id → wave_number
                - total_waves: int - Wave 總數
                - is_valid: bool - 是否為有效 DAG（無環）
                - cycle_info: Optional[List[str]] - 環路資訊（若有環）

        Examples:
            >>> # 無依賴 Ticket → 全部 Wave 1
            >>> tickets = [
            ...     {"id": "A", "blockedBy": []},
            ...     {"id": "B", "blockedBy": []},
            ... ]
            >>> result = WaveCalculator.calculate_waves(tickets)
            >>> result.total_waves
            1
            >>> result.waves[1]
            ['A', 'B']

            >>> # 線性依賴：A → B → C
            >>> tickets = [
            ...     {"id": "A", "blockedBy": []},
            ...     {"id": "B", "blockedBy": ["A"]},
            ...     {"id": "C", "blockedBy": ["B"]},
            ... ]
            >>> result = WaveCalculator.calculate_waves(tickets)
            >>> result.total_waves
            3
            >>> result.ticket_wave_map["A"]
            1
            >>> result.ticket_wave_map["B"]
            2
            >>> result.ticket_wave_map["C"]
            3

            >>> # 鑽石依賴：D.blockedBy=[B,C], B.blockedBy=[A], C.blockedBy=[A]
            >>> tickets = [
            ...     {"id": "A", "blockedBy": []},
            ...     {"id": "B", "blockedBy": ["A"]},
            ...     {"id": "C", "blockedBy": ["A"]},
            ...     {"id": "D", "blockedBy": ["B", "C"]},
            ... ]
            >>> result = WaveCalculator.calculate_waves(tickets)
            >>> result.total_waves
            3
            >>> result.ticket_wave_map["A"]
            1
            >>> result.ticket_wave_map["B"]
            2
            >>> result.ticket_wave_map["C"]
            2
            >>> result.ticket_wave_map["D"]
            3
        """
        # Guard Clause 1：無票據
        if not tickets:
            return WaveCalculationResult(
                waves={},
                ticket_wave_map={},
                total_waves=0,
                is_valid=True,
                cycle_info=None
            )

        # 建立票據 ID 集合
        all_ticket_ids = {ticket.get("id") for ticket in tickets if ticket.get("id")}

        # Guard Clause 2：無有效票據 ID
        if not all_ticket_ids:
            return WaveCalculationResult(
                waves={},
                ticket_wave_map={},
                total_waves=0,
                is_valid=True,
                cycle_info=None
            )

        # 步驟 3：檢查循環依賴
        cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)
        if cycles:
            # 取第一個環的資訊
            _, cycle_path = cycles[0]
            return WaveCalculationResult(
                waves={},
                ticket_wave_map={},
                total_waves=0,
                is_valid=False,
                cycle_info=cycle_path
            )

        # 步驟 4：建立鄰接表和入度表
        # adjacency_list: ticket_id → [依賴它的 ticket_ids]（反向依賴）
        # in_degree: ticket_id → 入度
        adjacency_list: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = defaultdict(int)

        # 初始化所有票據的入度為 0
        for ticket_id in all_ticket_ids:
            in_degree[ticket_id] = 0

        # 建立邊和計算入度
        for ticket in tickets:
            ticket_id = ticket.get("id")
            blocked_by = ticket.get("blockedBy", [])

            # Guard Clause：無效 ticket_id
            if not ticket_id or ticket_id not in all_ticket_ids:
                continue

            # Guard Clause：無依賴
            if not blocked_by:
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

                # 邊：dep_id → ticket_id（dep_id 被完成後，ticket_id 才能開始）
                adjacency_list[dep_id].append(ticket_id)
                in_degree[ticket_id] += 1

        # 步驟 5：初始化佇列（入度為 0 的節點 = Wave 1 的候選）
        queue = deque([
            ticket_id for ticket_id in all_ticket_ids
            if in_degree[ticket_id] == 0
        ])

        # Guard Clause：無法開始（所有節點都有入度，應該被 cycle detection 捕獲，但以防萬一）
        if not queue:
            return WaveCalculationResult(
                waves={},
                ticket_wave_map={},
                total_waves=0,
                is_valid=False,
                cycle_info=["無可開始的節點"]
            )

        # 步驟 6：BFS 層級遍歷
        waves: Dict[int, List[str]] = {}
        ticket_wave_map: Dict[str, int] = {}
        current_wave = 1

        while queue:
            # 當前層（Wave）的所有節點
            wave_nodes = []
            wave_size = len(queue)

            # 處理當前層的所有節點
            for _ in range(wave_size):
                current_ticket = queue.popleft()
                wave_nodes.append(current_ticket)
                ticket_wave_map[current_ticket] = current_wave

                # 更新依賴此節點的所有節點的入度
                for dependent in adjacency_list.get(current_ticket, []):
                    in_degree[dependent] -= 1

                    # 若依賴的所有節點都已完成，該節點可進入下一 Wave
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

            # 記錄當前 Wave 的節點
            waves[current_wave] = wave_nodes
            current_wave += 1

        # 步驟 7：驗證
        total_waves = len(waves)

        return WaveCalculationResult(
            waves=waves,
            ticket_wave_map=ticket_wave_map,
            total_waves=total_waves,
            is_valid=True,
            cycle_info=None
        )

    @staticmethod
    def suggest_optimal_waves(tickets: List[Dict]) -> str:
        """
        產生可讀的 Wave 分配建議文字摘要

        使用 calculate_waves() 計算結果，並格式化為易於閱讀的文字說明。
        若計算失敗（有環），返回錯誤訊息。

        Args:
            tickets: Ticket 清單

        Returns:
            str: 文字格式的 Wave 分配建議

        Examples:
            >>> tickets = [
            ...     {"id": "A", "blockedBy": []},
            ...     {"id": "B", "blockedBy": ["A"]},
            ... ]
            >>> suggestion = WaveCalculator.suggest_optimal_waves(tickets)
            >>> "Wave 1" in suggestion
            True
            >>> "Wave 2" in suggestion
            True
        """
        result = WaveCalculator.calculate_waves(tickets)

        # Guard Clause：計算失敗
        if not result.is_valid:
            if result.cycle_info:
                cycle_str = " → ".join(result.cycle_info)
                return f"計算失敗：發現循環依賴\n環路：{cycle_str}"
            else:
                return "計算失敗：未知錯誤"

        # Guard Clause：無 Wave
        if result.total_waves == 0:
            return "無 Ticket，無需分配 Wave"

        # 格式化輸出
        suggestion = f"Wave 自動分配建議（共 {result.total_waves} 個 Wave）\n"
        suggestion += SEPARATOR_SECONDARY + "\n\n"

        for wave_num in sorted(result.waves.keys()):
            tickets_in_wave = result.waves[wave_num]
            suggestion += f"Wave {wave_num}（{len(tickets_in_wave)} 個 Ticket）：\n"
            for ticket_id in sorted(tickets_in_wave):
                suggestion += f"  - {ticket_id}\n"
            suggestion += "\n"

        return suggestion.rstrip()


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
