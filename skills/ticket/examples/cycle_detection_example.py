#!/usr/bin/env python3
"""
循環依賴檢測使用範例

此檔案展示了 CycleDetector 的各項功能和使用方式。
"""

import sys
from pathlib import Path

# 新增專案路徑以供匯入
sys.path.insert(0, str(Path(__file__).parent.parent))

from ticket_system.lib.cycle_detector import CycleDetector


def example_1_simple_cycle_detection():
    """
    範例 1：簡單的環檢測

    偵測直接的循環依賴：A → B → C → A
    """
    print("=" * 60)
    print("範例 1：簡單的環檢測")
    print("=" * 60)

    def get_dependencies(ticket_id: str) -> list[str]:
        """Ticket 依賴定義"""
        deps = {
            "A": ["B"],
            "B": ["C"],
            "C": ["A"]
        }
        return deps.get(ticket_id, [])

    # 檢測環
    has_cycle, cycle_path = CycleDetector.has_cycle("A", get_dependencies)

    print(f"起始 Ticket：A")
    print(f"發現環：{has_cycle}")

    if has_cycle:
        print(f"環路路徑：{' → '.join(cycle_path)}")
    else:
        print("無環！")

    print()


def example_2_no_cycle():
    """
    範例 2：無環的依賴結構

    展示正常的依賴鏈：A → B → C
    """
    print("=" * 60)
    print("範例 2：無環的依賴結構")
    print("=" * 60)

    def get_dependencies(ticket_id: str) -> list[str]:
        """Ticket 依賴定義"""
        deps = {
            "A": ["B"],
            "B": ["C"],
            "C": []
        }
        return deps.get(ticket_id, [])

    # 檢測環
    has_cycle, cycle_path = CycleDetector.has_cycle("A", get_dependencies)

    print(f"起始 Ticket：A")
    print(f"發現環：{has_cycle}")

    if has_cycle:
        print(f"環路路徑：{' → '.join(cycle_path)}")
    else:
        print("無環！正常的依賴鏈。")

    print()


def example_3_self_dependency():
    """
    範例 3：自我依賴檢測

    檢測 Ticket 對自己的依賴：A → A
    """
    print("=" * 60)
    print("範例 3：自我依賴檢測")
    print("=" * 60)

    def get_dependencies(ticket_id: str) -> list[str]:
        """Ticket 依賴定義"""
        deps = {
            "A": ["A"]  # 自我依賴
        }
        return deps.get(ticket_id, [])

    # 檢測環
    has_cycle, cycle_path = CycleDetector.has_cycle("A", get_dependencies)

    print(f"起始 Ticket：A")
    print(f"發現環：{has_cycle}")

    if has_cycle:
        print(f"環路路徑：{' → '.join(cycle_path)}")
        print("警告：檢測到自我依賴！")

    print()


def example_4_detect_all_cycles():
    """
    範例 4：全面掃描所有環

    掃描所有 Ticket，找出所有循環依賴
    """
    print("=" * 60)
    print("範例 4：全面掃描所有環")
    print("=" * 60)

    tickets = [
        {"id": "A", "blockedBy": ["B"]},
        {"id": "B", "blockedBy": ["C"]},
        {"id": "C", "blockedBy": ["A"]},  # 循環：A → B → C → A
        {"id": "D", "blockedBy": []},
    ]

    print("Ticket 清單：")
    for ticket in tickets:
        print(f"  {ticket['id']}: 被 {ticket['blockedBy']} 阻塞")

    # 掃描所有環
    cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)

    print(f"\n發現 {len(cycles)} 個環：")
    for start_id, cycle_path in cycles:
        print(f"  起點 {start_id}：{' → '.join(cycle_path)}")

    print()


def example_5_validate_new_dependency():
    """
    範例 5：驗證新的依賴關係

    檢查新增依賴是否會產生循環
    """
    print("=" * 60)
    print("範例 5：驗證新的依賴關係")
    print("=" * 60)

    existing_tickets = [
        {"id": "B", "blockedBy": ["C"]},
        {"id": "C", "blockedBy": []},
    ]

    print("現有 Ticket：")
    for ticket in existing_tickets:
        print(f"  {ticket['id']}: 被 {ticket['blockedBy']} 阻塞")

    # 嘗試新增一個 Ticket A，被 B 阻塞
    print("\n嘗試新增：A 被 B 阻塞")
    valid, msg, path = CycleDetector.validate_blocked_by(
        "A", ["B"], existing_tickets
    )

    print(f"驗證通過：{valid}")
    if not valid:
        print(f"錯誤訊息：{msg}")
        print(f"環路：{' → '.join(path)}")
    else:
        print("✓ 可以安全地新增此依賴")

    # 嘗試另一種情況：C 被 A 阻塞（會產生環）
    print("\n嘗試修改：C 被 A 阻塞")

    modified_tickets = [
        {"id": "B", "blockedBy": ["C"]},
        {"id": "C", "blockedBy": ["A"]},
    ]

    valid, msg, path = CycleDetector.validate_blocked_by(
        "A", ["B"], modified_tickets
    )

    print(f"驗證通過：{valid}")
    if not valid:
        print(f"錯誤訊息：{msg}")
        print(f"環路：{' → '.join(path)}")

    print()


def example_6_complex_dag():
    """
    範例 6：複雜的有向無環圖（DAG）

    展示複雜的依賴結構和環檢測
    """
    print("=" * 60)
    print("範例 6：複雜的依賴結構")
    print("=" * 60)

    tickets = [
        {"id": "A", "blockedBy": ["B", "C"]},
        {"id": "B", "blockedBy": ["D", "E"]},
        {"id": "C", "blockedBy": ["E"]},
        {"id": "D", "blockedBy": []},
        {"id": "E", "blockedBy": []},
    ]

    print("Ticket 依賴結構：")
    print("  A 被 B, C 阻塞")
    print("  B 被 D, E 阻塞")
    print("  C 被 E 阻塞")
    print("  D 無依賴（可立即開始）")
    print("  E 無依賴（可立即開始）")

    # 掃描環
    cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)

    print(f"\n發現 {len(cycles)} 個環")
    if len(cycles) == 0:
        print("✓ 此結構為有向無環圖（DAG），無循環依賴")

    print()


def example_7_multiple_cycles():
    """
    範例 7：多個獨立的循環

    系統中存在多個互不相關的循環
    """
    print("=" * 60)
    print("範例 7：多個循環依賴")
    print("=" * 60)

    tickets = [
        # 循環 1：A → B → A
        {"id": "A", "blockedBy": ["B"]},
        {"id": "B", "blockedBy": ["A"]},

        # 循環 2：C → D → C
        {"id": "C", "blockedBy": ["D"]},
        {"id": "D", "blockedBy": ["C"]},

        # 正常的
        {"id": "E", "blockedBy": []},
    ]

    print("Ticket 結構：")
    print("  循環 1：A ↔ B")
    print("  循環 2：C ↔ D")
    print("  正常：E（無依賴）")

    # 掃描所有環
    cycles = CycleDetector.detect_cycles_in_all_tickets(tickets)

    print(f"\n發現 {len(cycles)} 個環：")
    for i, (start_id, cycle_path) in enumerate(cycles, 1):
        print(f"  循環 {i}：{' → '.join(cycle_path)}")

    print()


def main():
    """執行所有範例"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " 循環依賴檢測機制 - 使用範例 ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    # 執行所有範例
    example_1_simple_cycle_detection()
    example_2_no_cycle()
    example_3_self_dependency()
    example_4_detect_all_cycles()
    example_5_validate_new_dependency()
    example_6_complex_dag()
    example_7_multiple_cycles()

    print("=" * 60)
    print("所有範例執行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
