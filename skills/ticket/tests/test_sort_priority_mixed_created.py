"""
_sort_tickets_by_priority created 欄位混型回歸測試（0.19.1-W1-015）

問題根因：YAML 將未加引號的 `created: 2026-06-03` 解析為 datetime.date，
加引號或缺欄位則為 str。當同一 priority_norm 下需比較 sort tuple 第 2 元素
（created）時，date 與 str 無法比較 → TypeError，整個 list 命令中斷。

修復：_key() 將 created 正規化為可比較字串（datetime.date → isoformat，
其餘 str() / 空字串）。

測試覆蓋：
- datetime.date / str / 缺 created 三型別混入同一集合
- sorted 不拋例外
- 排序穩定：P0→P3，同 priority 下舊者在前
"""

import datetime

from ticket_system.commands.track_query import _sort_tickets_by_priority


class TestSortPriorityMixedCreated:
    """created 欄位混型不應導致 sorted 拋 TypeError。"""

    def test_mixed_date_str_missing_no_exception(self):
        """
        Given: 集合內 created 同時含 datetime.date / str / 缺欄位三型別
        When: _sort_tickets_by_priority 排序
        Then: 不拋 TypeError，正常返回排序結果
        """
        tickets = [
            {"id": "A", "priority": "P1", "created": datetime.date(2026, 6, 3)},
            {"id": "B", "priority": "P1", "created": "2026-06-01"},
            {"id": "C", "priority": "P1"},  # 缺 created
        ]

        # 修復前此呼叫拋 TypeError: '<' not supported between
        # instances of 'datetime.date' and 'str'
        result = _sort_tickets_by_priority(tickets)

        assert len(result) == 3

    def test_datetime_normalized_to_isoformat_ordering(self):
        """
        Given: datetime.date 與 str created 在同一 priority 下
        When: 排序
        Then: datetime.date 以 isoformat 參與比較，舊者在前
        """
        tickets = [
            {"id": "newer", "priority": "P1", "created": datetime.date(2026, 6, 3)},
            {"id": "older", "priority": "P1", "created": "2026-06-01"},
        ]

        result = _sort_tickets_by_priority(tickets)

        assert [t["id"] for t in result] == ["older", "newer"]

    def test_priority_rank_takes_precedence(self):
        """
        Given: 不同 priority 的 ticket（含混型 created）
        When: 排序
        Then: P0 → P3 優先於 created；同 priority 才比 created
        """
        tickets = [
            {"id": "p3", "priority": "P3", "created": "2026-06-01"},
            {"id": "p0", "priority": "P0", "created": datetime.date(2026, 6, 3)},
            {"id": "p1-new", "priority": "P1", "created": datetime.date(2026, 6, 5)},
            {"id": "p1-old", "priority": "P1", "created": "2026-06-02"},
        ]

        result = _sort_tickets_by_priority(tickets)

        assert [t["id"] for t in result] == ["p0", "p1-old", "p1-new", "p3"]

    def test_datetime_datetime_subclass_covered(self):
        """
        Given: created 為 datetime.datetime（datetime.date 子類）
        When: 排序
        Then: 同樣以 isoformat 正規化，不拋例外
        """
        tickets = [
            {"id": "dt", "priority": "P1", "created": datetime.datetime(2026, 6, 3, 12, 0)},
            {"id": "str", "priority": "P1", "created": "2026-06-01"},
        ]

        result = _sort_tickets_by_priority(tickets)

        assert len(result) == 2
        assert result[0]["id"] == "str"
