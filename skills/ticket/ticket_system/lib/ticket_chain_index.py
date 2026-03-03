"""
Ticket 任務鏈索引模組

提供快速的父子任務關係查詢，將查詢時間從 O(n) 優化到 O(1)。

索引結構：
- parent_index: dict[str, list[str]] - 父任務 ID → 直接子任務 ID 列表
- root_index: dict[str, list[str]] - 根任務 ID → 所有後代任務 ID 列表

使用 defaultdict 確保查詢不存在的鍵時返回空列表而非異常。
"""

# 防止直接執行此模組
from collections import defaultdict
from typing import Dict, List, Any


class TicketChainIndex:
    """
    Ticket 任務鏈索引管理器

    提供快速的父子任務關係查詢，支援兩個索引：
    - parent_index: 父任務 ID → 直接子任務 ID 列表
    - root_index: 根任務 ID → 所有後代任務 ID 列表

    設計特點：
    1. 使用 defaultdict 避免 KeyError
    2. 支援遞迴遍歷建立 root_index
    3. 提供簡單的查詢介面
    4. 無副作用，不修改原始 Ticket 資料
    """

    def __init__(self) -> None:
        """初始化空索引"""
        self.parent_index: Dict[str, List[str]] = defaultdict(list)
        self.root_index: Dict[str, List[str]] = defaultdict(list)

    def build_from_tickets(self, tickets: List[Dict[str, Any]]) -> None:
        """
        從 Ticket 列表建立索引

        演算法：
        1. 掃描所有 Ticket，建立 parent_index
        2. 掃描所有根任務（parent_id 為空），建立 root_index
        3. 使用遞迴 _collect_descendants 遍歷任務樹

        時間複雜度：O(n + m)，其中 n = ticket 數，m = 邊數
        空間複雜度：O(n)

        Args:
            tickets: Ticket 列表，每個 Ticket 包含 id、chain（含 parent）、children 欄位

        Raises:
            無，異常時安全降級（遺漏無效 Ticket）
        """
        # 清空既有索引
        self.parent_index.clear()
        self.root_index.clear()

        # Guard Clause：空列表直接返回
        if not tickets:
            return

        # Step 1：建立 parent_index
        # 掃描所有 Ticket，將子任務 ID 加入父任務的列表
        for ticket in tickets:
            ticket_id = ticket.get("id")
            children = ticket.get("children", [])

            # Guard：無效 Ticket ID 跳過
            if not ticket_id:
                continue

            # 遍歷所有子任務（支援字串 ID 和字典兩種格式）
            for child in children:
                # 提取子任務 ID（字串或字典）
                child_id = self._extract_id(child)
                if child_id:
                    self.parent_index[ticket_id].append(child_id)

        # Step 2：建立 root_index
        # 掃描所有根任務（parent_id 為空）
        for ticket in tickets:
            ticket_id = ticket.get("id")
            chain = ticket.get("chain", {})
            parent_id = chain.get("parent")

            # Guard：無效 Ticket ID 跳過
            if not ticket_id:
                continue

            # 識別根任務（無父任務）
            if not parent_id:
                # 以此任務為根，遞迴收集所有後代
                descendants = [ticket_id]
                self._collect_descendants(ticket_id, descendants)
                self.root_index[ticket_id] = descendants

    def _extract_id(self, child: Any) -> str:
        """
        從子任務記錄中提取 ID

        支援兩種格式：
        - 字串：直接返回
        - 字典：返回 'id' 欄位

        Args:
            child: 子任務記錄（字串或字典）

        Returns:
            str: 子任務 ID（若無法提取返回空字串）
        """
        if isinstance(child, str):
            return child
        elif isinstance(child, dict):
            return child.get("id", "")
        return ""

    def _collect_descendants(self, parent_id: str, descendants: List[str]) -> None:
        """
        遞迴收集所有後代任務

        演算法：深度優先搜尋，遍歷 parent_index

        Args:
            parent_id: 父任務 ID
            descendants: 後代列表（傳入時包含根任務，此函式會追加後代）
        """
        # 取得此父任務的所有直接子任務
        children = self.parent_index.get(parent_id, [])

        # 遞迴遍歷每個子任務
        for child_id in children:
            # 將子任務加入後代列表
            descendants.append(child_id)
            # 遞迴收集此子任務的後代
            self._collect_descendants(child_id, descendants)

    def get_children(self, parent_id: str) -> List[str]:
        """
        取得直接子任務

        Args:
            parent_id: 父任務 ID

        Returns:
            List[str]: 直接子任務 ID 列表（無子任務時返回空列表）

        Examples:
            >>> index = TicketChainIndex()
            >>> tickets = [
            ...     {"id": "001", "chain": {}, "children": ["001.1", "001.2"]},
            ...     {"id": "001.1", "chain": {"parent": "001"}, "children": []},
            ... ]
            >>> index.build_from_tickets(tickets)
            >>> index.get_children("001")
            ['001.1', '001.2']
            >>> index.get_children("999")  # 不存在的 ID
            []
        """
        return self.parent_index.get(parent_id, [])

    def get_descendants(self, root_id: str) -> List[str]:
        """
        取得所有後代任務（包含根任務本身）

        Args:
            root_id: 根任務 ID

        Returns:
            List[str]: 所有後代任務 ID 列表（包含根任務，無後代時返回 [root_id]）

        Examples:
            >>> index = TicketChainIndex()
            >>> tickets = [
            ...     {"id": "001", "chain": {}, "children": ["001.1"]},
            ...     {"id": "001.1", "chain": {"parent": "001"}, "children": ["001.1.1"]},
            ...     {"id": "001.1.1", "chain": {"parent": "001.1"}, "children": []},
            ... ]
            >>> index.build_from_tickets(tickets)
            >>> index.get_descendants("001")
            ['001', '001.1', '001.1.1']
        """
        return self.root_index.get(root_id, [])

    def has_children(self, parent_id: str) -> bool:
        """
        檢查是否有子任務

        Args:
            parent_id: 父任務 ID

        Returns:
            bool: 是否有至少一個子任務

        Examples:
            >>> index = TicketChainIndex()
            >>> tickets = [{"id": "001", "chain": {}, "children": ["001.1"]}]
            >>> index.build_from_tickets(tickets)
            >>> index.has_children("001")
            True
            >>> index.has_children("999")
            False
        """
        return bool(self.parent_index.get(parent_id))

    def get_child_count(self, parent_id: str) -> int:
        """
        取得子任務數量

        Args:
            parent_id: 父任務 ID

        Returns:
            int: 直接子任務數量

        Examples:
            >>> index = TicketChainIndex()
            >>> tickets = [
            ...     {"id": "001", "chain": {}, "children": ["001.1", "001.2"]},
            ... ]
            >>> index.build_from_tickets(tickets)
            >>> index.get_child_count("001")
            2
            >>> index.get_child_count("999")
            0
        """
        return len(self.parent_index.get(parent_id, []))

    def get_descendant_count(self, root_id: str) -> int:
        """
        取得後代任務數量（包含根任務本身）

        Args:
            root_id: 根任務 ID

        Returns:
            int: 後代任務數量

        Examples:
            >>> index = TicketChainIndex()
            >>> tickets = [
            ...     {"id": "001", "chain": {}, "children": ["001.1"]},
            ...     {"id": "001.1", "chain": {"parent": "001"}, "children": []},
            ... ]
            >>> index.build_from_tickets(tickets)
            >>> index.get_descendant_count("001")
            2
        """
        return len(self.root_index.get(root_id, []))


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
