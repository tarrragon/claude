"""
Ticket 任務鏈分析模組

負責分析 Ticket 的任務鏈狀態和方向判斷邏輯，純分析層，無 I/O 操作。
所有與檔案讀取相關的操作由調用者負責。
"""
# 防止直接執行此模組
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from ticket_system.lib.constants import STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_PENDING, STATUS_BLOCKED
from ticket_system.lib.ticket_loader import load_ticket


@dataclass
class Recommendation:
    """方向建議。"""
    direction: str
    reason: str
    next_target_id: Optional[str] = None
    next_target_title: Optional[str] = None
    command: Optional[str] = None
    blocked_by: Optional[list] = None


class ChainAnalyzer:
    """
    Ticket 任務鏈分析器

    提供純分析邏輯，用於判斷 Ticket 的交接方向和下一步建議。
    所有分析基於已載入的 Ticket 資料，不進行額外的 I/O 操作。
    """

    @staticmethod
    def determine_next_step(ticket: Dict[str, Any], all_tickets: Optional[List[Dict[str, Any]]] = None, version: Optional[str] = None) -> str:
        """
        自動判斷 handoff 方向（determine_direction 的別名）

        根據 Ticket 狀態和結構自動決定方向，實現五種情境。

        情境 1：父完成/進行中 → 子（有待執行子任務）
        情境 2：父被阻塞 → 子（需先完成子任務）
        情境 3：子完成 → 父（無平行任務）
        情境 4：子完成 → 兄弟可選（有平行任務待處理）
        情境 5：等待（依賴未滿足）

        Args:
            ticket: Ticket 資料
            all_tickets: 所有 Ticket 資料（用於載入相關 Ticket，可選）
            version: 版本號（用於載入相關 Ticket，可選）

        Returns:
            str: 方向 (to-parent, to-child, to-sibling, wait, completed)
        """
        return ChainAnalyzer.determine_direction(ticket, version)

    @staticmethod
    def determine_direction(ticket: Dict[str, Any], version: Optional[str] = None) -> str:
        """
        自動判斷 handoff 方向

        根據 Ticket 狀態和結構自動決定方向，實現五種情境。
        使用 Guard Clause 模式，優先處理異常情況。

        情境 1：父進行中/子未完成 → 進入子（downward）
        情境 2：父被阻塞 → 等待（阻塞無法進行）
        情境 3：無父任務 → 完成（根節點）
        情境 4：有待處理兄弟 → 轉向兄弟（平行）
        情境 5：無待處理兄弟 → 返回父（upward）

        演算法:
        1. 提取 Ticket 關鍵資訊（狀態、父ID、子任務清單）
        2. 版本號必要時從 ID 提取（格式：version-Wn-seq）
        3. Guard Clause 依序判斷：
           - 被阻塞 → "wait"（情境2）
           - 有子任務 → "to-child"（情境1）
           - 無父任務 → "completed"（情境3）
           - 有待處理兄弟 → "to-sibling"（情境4）
           - 否則 → "to-parent"（情境5）

        Args:
            ticket: Ticket 資料字典（必須含 id, status, chain, children）
            version: 版本號（用於載入相關 Ticket）
                    可選，若不提供會從 ticket_id 提取

        Returns:
            str: handoff 方向，值為：
                 - "wait": 當前任務被阻塞，需等待
                 - "to-child": 進入第一個待執行子任務
                 - "to-parent": 回報父任務並等待指示
                 - "to-sibling": 轉向待執行的兄弟任務
                 - "completed": 任務鏈完成，無後續任務

        Examples:
            >>> ticket = {"id": "0.31.0-W4-001", "status": "completed", "chain": {"parent": None}, "children": []}
            >>> ChainAnalyzer.determine_direction(ticket)
            'completed'
            >>> ticket = {"id": "0.31.0-W4-001", "status": "blocked", "chain": {}, "children": []}
            >>> ChainAnalyzer.determine_direction(ticket)
            'wait'
        """
        # 提取 Ticket 關鍵資訊
        ticket_id = ticket.get("id", "")
        status = ticket.get("status", "")
        chain = ticket.get("chain", {})
        children = ticket.get("children", [])
        parent_id = chain.get("parent")

        # 版本號解析：優先使用傳入參數，否則從 Ticket ID 提取
        # Ticket ID 格式：version-Wn-seq（如 0.31.0-W4-001）
        if not version:
            version = ticket_id.split("-W")[0] if "-W" in ticket_id else None

        # Guard Clause 1：情境 2 - 被阻塞，等待前置任務完成
        if status == STATUS_BLOCKED:
            return "wait"

        # Guard Clause 2：情境 1 - 有待執行的子任務，進入子任務
        if ChainAnalyzer._has_pending_children(children, version):
            return "to-child"

        # Guard Clause 3：情境 3 - 無父任務，當前為根節點，任務完成
        if not parent_id:
            return "completed"

        # Guard Clause 4：情境 4 - 有待處理的兄弟任務，轉向兄弟
        if ChainAnalyzer._get_sibling_status(ticket, version) == "has_pending":
            return "to-sibling"

        # 預設情境 5 - 無待處理兄弟，返回父任務回報進度
        return "to-parent"

    @staticmethod
    def _has_pending_children(children: list, version: Optional[str] = None) -> bool:
        """
        檢查是否有待完成的子任務。

        子任務可能以兩種格式存在：
        - 字串 ID：如 "0.31.0-W4-001.1"（需要載入檔案檢查狀態）
        - 字典：包含 id 和 status 欄位（可直接檢查狀態）

        演算法:
        1. Guard Clause：若無子任務，返回 False
        2. 遍歷每個子任務
        3. 若為字串 ID，嘗試載入對應 Ticket 檢查狀態
        4. 若為字典，直接檢查 status 欄位
        5. 只要有一個子任務未完成，立即返回 True

        Args:
            children: 子任務清單，可能為空、字串 ID、或字典混合
            version: 版本號（用於載入字串型子 Ticket）
                    可選，若無版本則無法載入字串型子任務

        Returns:
            bool: 是否有未完成（status != completed）的子任務
                 無子任務或全部完成返回 False

        Examples:
            >>> ChainAnalyzer._has_pending_children([])
            False
            >>> children = [{"id": "001", "status": "pending"}]
            >>> ChainAnalyzer._has_pending_children(children)
            True
        """
        # Guard Clause：無子任務
        if not children:
            return False

        # 檢查每個子任務
        for child_id in children:
            # 類型 1：字串型 ID（需要載入檔案）
            if isinstance(child_id, str) and version:
                # 載入子 Ticket 以檢查其狀態
                child_ticket = load_ticket(version, child_id)
                # 只要有一個子任務未完成，立即返回 True
                if child_ticket and child_ticket.get("status") != STATUS_COMPLETED:
                    return True

            # 類型 2：字典型子任務（已嵌入狀態）
            elif isinstance(child_id, dict):
                # 直接檢查字典中的 status 欄位
                if child_id.get("status") != STATUS_COMPLETED:
                    return True

        # 全部子任務都已完成或無可檢查的子任務
        return False

    @staticmethod
    def _get_sibling_status(ticket: Dict[str, Any], version: Optional[str] = None) -> str:
        """
        取得兄弟任務狀態。

        透過父任務載入兄弟列表，判斷是否有待處理的兄弟任務。
        兄弟任務是同一個父任務下的其他子任務。

        演算法:
        1. Guard Clause：無父任務 → 無兄弟
        2. Guard Clause：無版本 → 無法載入父任務
        3. 載入父任務及其子任務清單
        4. 遍歷兄弟，跳過自己
        5. 檢查每個兄弟的狀態（支援字串 ID 和字典兩種格式）
        6. 只要有未完成的兄弟，立即返回 "has_pending"

        Args:
            ticket: 當前 Ticket 資料（需要 id 和 chain.parent）
            version: 版本號（用於載入父任務和兄弟任務）

        Returns:
            str: 兄弟狀態，值為：
                 - "has_pending": 有待處理的兄弟任務
                 - "all_done": 無待處理的兄弟任務（全部完成或無兄弟）

        Examples:
            >>> ticket = {"id": "0.31.0-W4-001.1", "chain": {"parent": None}}
            >>> ChainAnalyzer._get_sibling_status(ticket)
            'all_done'
        """
        # 提取當前任務的 ID 和父任務 ID
        ticket_id = ticket.get("id", "")
        chain = ticket.get("chain", {})
        parent_id = chain.get("parent")

        # Guard Clause 1：無父任務 → 當前為根節點，無兄弟
        if not parent_id:
            return "all_done"

        # Guard Clause 2：無版本 → 無法載入父任務，假設無待處理兄弟
        if version:
            # 載入父任務以取得兄弟清單
            parent_ticket = load_ticket(version, parent_id)
            if parent_ticket:
                # 取得父任務的所有子任務（兄弟 + 自己）
                siblings = parent_ticket.get("children", [])

                # 檢查每個兄弟
                for sibling_id in siblings:
                    # 類型 1：字串型 ID
                    if isinstance(sibling_id, str):
                        # 跳過自己
                        if sibling_id == ticket_id:
                            continue
                        # 載入兄弟 Ticket 以檢查其狀態
                        sibling_ticket = load_ticket(version, sibling_id)
                        # 只要有一個兄弟未完成，立即返回
                        if sibling_ticket and sibling_ticket.get("status") != STATUS_COMPLETED:
                            return "has_pending"

                    # 類型 2：字典型兄弟（已嵌入狀態）
                    elif isinstance(sibling_id, dict):
                        # 跳過自己
                        if sibling_id.get("id") == ticket_id:
                            continue
                        # 直接檢查字典中的 status
                        if sibling_id.get("status") != STATUS_COMPLETED:
                            return "has_pending"

        # 全部兄弟都完成或無待處理兄弟
        return "all_done"

    @staticmethod
    def get_recommendation(
        direction: str,
        ticket: Dict[str, Any],
        version: Optional[str] = None
    ) -> Recommendation:
        """
        根據交接方向生成具體建議。

        使用 Guard Clause 模式，對每個可能的方向逐一處理，
        無巢狀結構，易於理解和擴展。

        演算法:
        1. 提取 Ticket 資訊（ID、子任務、父ID）
        2. 根據 direction 使用不同的輔助函式生成建議
        3. 每個方向返回對應的 Recommendation 物件
        4. Recommendation 包含：方向、原因、下一個目標、執行命令

        Args:
            direction: handoff 方向（來自 determine_direction）
                      可能值：to-child, to-sibling, to-parent, wait, completed
            ticket: Ticket 資料字典（需要 id, children, chain, blockedBy 等欄位）
            version: 版本號（用於載入相關 Ticket 的詳細資訊）

        Returns:
            Recommendation: 包含以下資訊的建議物件：
                - direction: 交接方向
                - reason: 為什麼選擇這個方向（中文說明）
                - next_target_id: 下一個目標任務 ID（可選）
                - next_target_title: 下一個目標任務標題（可選）
                - command: 執行建議的命令（可選）
                - blocked_by: 阻塞任務列表（等待情況時）

        Examples:
            >>> direction = "completed"
            >>> ticket = {"id": "0.31.0-W4-001", "chain": {"root": "0.31.0-W4-001"}}
            >>> rec = ChainAnalyzer.get_recommendation(direction, ticket)
            >>> rec.reason
            '所有子任務已完成，無待處理項目'
        """
        # 提取 Ticket 關鍵資訊
        ticket_id = ticket.get("id", "")
        children = ticket.get("children", [])
        chain = ticket.get("chain", {})
        parent_id = chain.get("parent")

        # Guard Clause 1：進入子任務
        if direction == "to-child":
            return ChainAnalyzer._get_to_child_recommendation(ticket_id, children, version)

        # Guard Clause 2：切換到兄弟任務
        if direction == "to-sibling":
            return ChainAnalyzer._get_to_sibling_recommendation(ticket_id, parent_id, version)

        # Guard Clause 3：返回父任務
        if direction == "to-parent":
            return ChainAnalyzer._get_to_parent_recommendation(ticket_id, parent_id, version)

        # Guard Clause 4：被阻塞等待
        if direction == "wait":
            # 取得阻塞當前任務的前置任務清單
            blocked_by = ticket.get("blockedBy", [])
            return Recommendation(
                direction="wait",
                reason="當前任務被阻塞，需等待前置任務完成",
                blocked_by=blocked_by,
                # 若有阻塞任務，建議查詢第一個
                command=f"/ticket track query {blocked_by[0]}" if blocked_by else None
            )

        # Guard Clause 5：任務鏈完成
        if direction == "completed":
            # 任務鏈的根節點 ID（通常就是當前 ID，除非是子任務回報）
            root_id = chain.get("root", ticket_id)
            return Recommendation(
                direction="completed",
                reason="所有子任務已完成，無待處理項目",
                next_target_id=root_id,
                # 建議執行 /ticket track complete 標記任務完成
                command=f"/ticket track complete {ticket_id}"
            )

        # 預設建議：未知方向
        return Recommendation(
            direction="unknown",
            reason="檢視當前任務狀態",
            command=f"/ticket track query {ticket_id}"
        )

    @staticmethod
    def _get_to_child_recommendation(ticket_id: str, children: list, version: Optional[str] = None) -> Recommendation:
        """
        生成進入子任務的建議。

        Args:
            ticket_id: 當前 Ticket ID
            children: 子任務列表
            version: 版本號

        Returns:
            Recommendation: 子任務建議
        """
        for child_id in children:
            # 處理字串型 ID
            if isinstance(child_id, str) and version:
                child_ticket = load_ticket(version, child_id)
                if child_ticket and child_ticket.get("status") != STATUS_COMPLETED:
                    child_title = child_ticket.get("title", "")
                    return Recommendation(
                        direction="to-child",
                        reason=f"有 {len(children)} 個子任務待處理，建議從第一個開始",
                        next_target_id=child_id,
                        next_target_title=child_title,
                        command=f"/ticket handoff {ticket_id} --to-child {child_id}"
                    )

            # 處理 dict 型 child
            if isinstance(child_id, dict) and child_id.get("status") != STATUS_COMPLETED:
                child_id_str = child_id.get("id", "")
                return Recommendation(
                    direction="to-child",
                    reason="有子任務待處理",
                    next_target_id=child_id_str,
                    command=f"/ticket handoff {ticket_id} --to-child {child_id_str}"
                )

        # 預設：無待處理子任務
        return Recommendation(
            direction="to-child",
            reason="子任務清單已處理",
            command=f"/ticket track query {ticket_id}"
        )

    @staticmethod
    def _get_to_sibling_recommendation(ticket_id: str, parent_id: Optional[str], version: Optional[str] = None) -> Recommendation:
        """
        生成切換到兄弟任務的建議。

        Args:
            ticket_id: 當前 Ticket ID
            parent_id: 父任務 ID
            version: 版本號

        Returns:
            Recommendation: 兄弟任務建議
        """
        # Guard：無父任務或無版本
        if not parent_id or not version:
            return Recommendation(
                direction="to-sibling",
                reason="無兄弟任務可切換",
                command=f"/ticket track query {ticket_id}"
            )

        # Guard：無法載入父任務
        parent_ticket = load_ticket(version, parent_id)
        if not parent_ticket:
            return Recommendation(
                direction="to-sibling",
                reason="無法載入父任務資訊",
                command=f"/ticket track query {ticket_id}"
            )

        # 搜尋第一個待處理兄弟
        siblings = parent_ticket.get("children", [])
        for sibling_id in siblings:
            # 處理字串型兄弟 ID
            if isinstance(sibling_id, str):
                if sibling_id == ticket_id:
                    continue
                sibling_ticket = load_ticket(version, sibling_id)
                if sibling_ticket and sibling_ticket.get("status") != STATUS_COMPLETED:
                    sibling_title = sibling_ticket.get("title", "")
                    return Recommendation(
                        direction="to-sibling",
                        reason="有平行任務待處理，可選擇任一開始",
                        next_target_id=sibling_id,
                        next_target_title=sibling_title,
                        command=f"/ticket handoff {ticket_id} --to-sibling {sibling_id}"
                    )

            # 處理 dict 型兄弟
            if isinstance(sibling_id, dict):
                sibling_id_str = sibling_id.get("id")
                if sibling_id_str == ticket_id:
                    continue
                if sibling_id.get("status") != STATUS_COMPLETED:
                    return Recommendation(
                        direction="to-sibling",
                        reason="有平行任務待處理",
                        next_target_id=sibling_id_str,
                        command=f"/ticket handoff {ticket_id} --to-sibling {sibling_id_str}"
                    )

        # 預設：無待處理兄弟
        return Recommendation(
            direction="to-sibling",
            reason="兄弟任務已全部完成",
            command=f"/ticket track query {ticket_id}"
        )

    @staticmethod
    def _get_to_parent_recommendation(ticket_id: str, parent_id: Optional[str], version: Optional[str] = None) -> Recommendation:
        """
        生成返回父任務的建議。

        Args:
            ticket_id: 當前 Ticket ID
            parent_id: 父任務 ID
            version: 版本號

        Returns:
            Recommendation: 父任務建議
        """
        # Guard：無父任務
        if not parent_id:
            return Recommendation(
                direction="to-parent",
                reason="當前為根任務，無父任務",
                command=f"/ticket track query {ticket_id}"
            )

        # Guard：無版本但有父任務
        if not version:
            return Recommendation(
                direction="to-parent",
                reason="無待處理的子任務或兄弟任務",
                next_target_id=parent_id,
                command=f"/ticket handoff {ticket_id} --to-parent"
            )

        # 載入父任務資訊
        parent_ticket = load_ticket(version, parent_id)
        if not parent_ticket:
            return Recommendation(
                direction="to-parent",
                reason="無待處理的子任務或兄弟任務",
                next_target_id=parent_id,
                command=f"/ticket handoff {ticket_id} --to-parent"
            )

        # 返回含父任務詳細資訊的建議
        parent_title = parent_ticket.get("title", "")
        return Recommendation(
            direction="to-parent",
            reason="當前任務的子任務已全部完成，回報進度",
            next_target_id=parent_id,
            next_target_title=parent_title,
            command=f"/ticket handoff {ticket_id} --to-parent"
        )


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
