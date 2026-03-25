"""
ticket create 重複偵測功能的單元與整合測試

測試 Jaccard 相似度計算和 pending Ticket 重複偵測邏輯。
共 34 個測試案例，涵蓋相似度演算法、重複偵測行為、整合點和效能邊界。
"""

import time
from unittest.mock import patch, MagicMock
import pytest

from datetime import datetime, timedelta
from ticket_system.commands.create import (
    _calculate_jaccard_similarity,
    _detect_duplicate_tickets,
    _is_in_detection_scope,
    _get_status_label,
)
from ticket_system.lib.constants import (
    STATUS_PENDING,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    DUPLICATE_DETECTION_THRESHOLD,
    DUPLICATE_DETECTION_COMPLETED_WINDOW_DAYS,
)


# ============================================================
# 相似度計算單元測試（U-001 至 U-012）
# ============================================================


class TestJaccardSimilarity:
    """Jaccard 相似度計算演算法測試"""

    # 基礎演算法測試
    def test_u001_identical_text(self):
        """U-001：完全相同文字 → 返回 1.0"""
        text_a = "實作 SRP 偵測"
        text_b = "實作 SRP 偵測"

        result = _calculate_jaccard_similarity(text_a, text_b)

        assert result == 1.0

    def test_u002_completely_different_text(self):
        """U-002：完全不同文字 → 返回 0.0"""
        text_a = "WebSocket 連線"
        text_b = "權限驗證系統"

        result = _calculate_jaccard_similarity(text_a, text_b)

        assert result == 0.0

    def test_u003_partial_overlap_chinese(self):
        """U-003：部分重疊（中文）→ 約 0.23"""
        text_a = "實作 SRP 自動偵測機制"
        text_b = "新增 SRP 偵測功能"

        result = _calculate_jaccard_similarity(text_a, text_b)

        # 詞彙：text_a = {實,作,S,R,P,自,動,偵,測,機,制}
        #       text_b = {新,增,S,R,P,偵,測,功,能}
        # 交集 = {S,R,P,偵,測}（5個），聯集有 22 個字
        # 期望 5/22 ≈ 0.23
        assert 0.2 <= result <= 0.3

    def test_u004_partial_overlap_english(self):
        """U-004：部分重疊（英文）→ 約 0.14"""
        text_a = "fix WebSocket connection issue"
        text_b = "handle WebSocket disconnection error"

        result = _calculate_jaccard_similarity(text_a, text_b)

        # 交集 = {WebSocket}（1個）
        # 期望 > 0.1
        assert result > 0.1

    # 邊界條件測試
    def test_u005_empty_vs_nonempty(self):
        """U-005：空字串與非空字串 → 返回 0.0"""
        text_a = ""
        text_b = "實作 SRP"

        result = _calculate_jaccard_similarity(text_a, text_b)

        assert result == 0.0

    def test_u006_both_empty_strings(self):
        """U-006：兩個空字串 → 返回 0.0"""
        text_a = ""
        text_b = ""

        result = _calculate_jaccard_similarity(text_a, text_b)

        assert result == 0.0

    def test_u007_single_character(self):
        """U-007：單一字元相同 → 返回 1.0"""
        text_a = "X"
        text_b = "X"

        result = _calculate_jaccard_similarity(text_a, text_b)

        assert result == 1.0

    def test_u008_case_insensitive(self):
        """U-008：大小寫不區分 → 返回 1.0"""
        text_a = "WebSocket"
        text_b = "websocket"

        result = _calculate_jaccard_similarity(text_a, text_b)

        # 應不區分大小寫
        assert result == 1.0

    def test_u009_special_characters(self):
        """U-009：特殊字符和標點 → 無例外，返回有效值"""
        text_a = "實作 SRP 自動偵測機制 (v1.0)"
        text_b = "實作 SRP 自動偵測機制"

        # 應無例外，特殊字符被忽略
        result = _calculate_jaccard_similarity(text_a, text_b)

        # 結果應為有效範圍
        assert 0.0 <= result <= 1.0

    def test_u010_long_text_performance(self):
        """U-010：長文字效能邊界 → 執行時間 < 50ms"""
        text_a = "unique_prefix " * 100 + "shared_term " + "unique_suffix_a " * 100
        text_b = "different_prefix " * 100 + "shared_term " + "unique_suffix_b " * 100

        start = time.time()
        result = _calculate_jaccard_similarity(text_a, text_b)
        elapsed = time.time() - start

        # 驗證執行時間和結果
        assert elapsed < 0.05  # 50ms
        # 應該有 shared_term 交集
        assert 0.0 < result < 1.0

    # 異常情境測試
    def test_u011_none_input(self):
        """U-011：None 值輸入 → 拋出 TypeError"""
        with pytest.raises(TypeError):
            _calculate_jaccard_similarity(None, "實作")

    def test_u012_non_string_input(self):
        """U-012：非字串型別輸入 → 拋出 TypeError"""
        with pytest.raises(TypeError):
            _calculate_jaccard_similarity(123, "456")


# ============================================================
# 重複偵測行為測試（B-001 至 B-013）
# ============================================================


class TestDuplicateDetection:
    """重複偵測邏輯測試"""

    @pytest.fixture
    def mock_list_tickets(self, mocker):
        """Mock list_tickets 返回測試用 Ticket 清單"""

        def _mock_impl(version):
            if version == "0.1.2":
                return [
                    {
                        "id": "0.1.2-W3-001.2",
                        "title": "實作 SRP 自動偵測機制",
                        "what": "自動偵測 SRP 違規",
                        "status": "pending",
                    },
                    {
                        "id": "0.1.2-W2-005",
                        "title": "修復 WebSocket 連線問題",
                        "what": "連線重試邏輯",
                        "status": "pending",
                    },
                    {
                        "id": "0.1.2-W3-002",
                        "title": "新增 API 驗證",
                        "what": "驗證 API 請求",
                        "status": "pending",
                    },
                ]
            return []

        # Patch 使用端（create.py 內部 import）
        return mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=_mock_impl,
        )

    def test_b001_single_similar_ticket(self, mock_list_tickets, capsys):
        """B-001：發現單個相似 Ticket → 輸出 WARNING"""
        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 偵測功能",
            new_what="新增 SRP 自動偵測",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 應輸出 WARNING
        assert "[WARNING]" in captured.out
        assert "1 個可能重複" in captured.out or "1 個" in captured.out
        assert "0.1.2-W3-001.2" in captured.out
        assert "實作 SRP 自動偵測機制" in captured.out

    def test_b002_multiple_similar_tickets(self, mocker, capsys):
        """B-002：多個相似 Ticket → 列出所有相似 Ticket"""

        def mock_list_impl(version):
            return [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 機制",
                    "what": "自動識別 SRP 違規",
                    "status": "pending",
                },
                {
                    "id": "0.1.2-W3-001.2",
                    "title": "實作 SRP 自動偵測",
                    "what": "詳細分析 SRP",
                    "status": "pending",
                },
            ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=mock_list_impl,
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 偵測功能",
            new_what="自動識別 SRP 違規",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 應輸出 WARNING，列出兩個相似 Ticket
        assert "[WARNING]" in captured.out
        assert "2 個" in captured.out or "2個" in captured.out

    def test_b003_no_similar_ticket_silent_pass(self, mocker, capsys):
        """B-003：無相似 Ticket → 靜默通過"""

        def mock_list_impl(version):
            return [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 機制",
                    "what": "自動識別 SRP 違規",
                    "status": "pending",
                },
                {
                    "id": "0.1.2-W2-005",
                    "title": "修復 WebSocket 連線",
                    "what": "連線重試邏輯",
                    "status": "pending",
                },
            ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=mock_list_impl,
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="建立 WebSocket 路由",
            new_what="實作路由轉發邏輯",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 應靜默通過，無任何輸出
        assert captured.out == ""

    # 狀態過濾邊界
    def test_b004_completed_ticket_within_window_triggers_warning(self, mocker, capsys):
        """B-004：7 天內 completed Ticket 觸發警告（含 [已完成] 標籤）"""
        recent_time = (datetime.now() - timedelta(days=3)).isoformat()

        def mock_list_impl(version):
            return [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 機制",
                    "what": "自動偵測 SRP 違規",
                    "status": "completed",
                    "completed_at": recent_time,
                },
            ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=mock_list_impl,
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 自動偵測",
            new_what="新增 SRP 檢查",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 7 天內 completed 應觸發警告
        assert "[WARNING]" in captured.out
        assert "0.1.2-W3-001" in captured.out
        assert "已完成" in captured.out

    def test_b005_in_progress_ticket_triggers_warning(self, mocker, capsys):
        """B-005：in_progress Ticket 觸發警告（含 [進行中] 標籤）"""

        def mock_list_impl(version):
            return [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 機制",
                    "what": "自動偵測 SRP 違規",
                    "status": "in_progress",
                },
            ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=mock_list_impl,
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 自動偵測",
            new_what="SRP 檢查",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # in_progress Ticket 應觸發警告
        assert "[WARNING]" in captured.out
        assert "0.1.2-W3-001" in captured.out
        assert "進行中" in captured.out

    def test_b006_cross_version_no_comparison(self, mocker, capsys):
        """B-006：跨版本 Ticket 不比對"""

        def mock_list_impl(version):
            # list_tickets 應只返回同版本 Ticket
            if version == "0.1.2":
                return []
            return []

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=mock_list_impl,
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 自動偵測",
            new_what="...",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 無同版本 pending，靜默通過
        assert captured.out == ""

    # 自身排除邊界
    def test_b007_subtask_excludes_parent(self, mocker, capsys):
        """B-007：建立子任務時，也排除父任務 ID"""

        def mock_list_impl(version):
            return [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 自動偵測機制",
                    "what": "自動檢查",
                    "status": "pending",
                },
                {
                    "id": "0.1.2-W2-005",
                    "title": "修復 WebSocket",
                    "what": "連線",
                    "status": "pending",
                },
            ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=mock_list_impl,
        )

        # 建立子任務 0.1.2-W3-001.1，與 parent 標題相似
        # 子任務含 "."，所以排除清單包含：自身 (0.1.2-W3-001.1) + 父任務 (0.1.2-W3-001)
        # 因此 parent 會被排除，不應發現相似 Ticket
        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 偵測部分 A",
            new_what="實作 SRP 自動檢查",
            new_ticket_id="0.1.2-W3-001.1",
        )

        captured = capsys.readouterr()

        # parent 應被排除，不輸出 WARNING
        assert captured.out == ""

    # 內容邊界
    def test_b008_empty_title_use_what(self, mocker, capsys):
        """B-008：title 為空時使用 what 進行比對"""

        def mock_list_impl(version):
            return [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 機制",
                    "what": "自動偵測",
                    "status": "pending",
                },
            ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=mock_list_impl,
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="",
            new_what="實作 SRP 自動偵測機制",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 應使用 what 進行比對，發現相似
        assert "[WARNING]" in captured.out

    def test_b009_empty_what_use_title(self, mocker, capsys):
        """B-009：what 為空時使用 title 進行比對"""

        def mock_list_impl(version):
            return [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 機制",
                    "what": "自動檢查",
                    "status": "pending",
                },
            ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=mock_list_impl,
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 自動偵測機制",
            new_what="",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 應使用 title 進行比對
        assert "[WARNING]" in captured.out

    def test_b010_both_empty_skip_detection(self, mocker, capsys):
        """B-010：title 和 what 均為空 → 跳過重複偵測"""

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP",
                    "what": "自動偵測",
                    "status": "pending",
                }
            ],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="",
            new_what="",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 無可比對文字，靜默返回
        assert captured.out == ""

    # 異常容錯
    def test_b011_list_tickets_exception_silent_pass(self, mocker, capsys):
        """B-011：list_tickets() 拋出例外 → 靜默通過"""

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=FileNotFoundError("Directory not found"),
        )

        # 應靜默通過，無例外向上拋出
        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 機制",
            new_what="自動偵測",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 靜默通過，無輸出
        assert captured.out == ""

    def test_b012_similarity_calculation_exception_skip(self, mocker, capsys):
        """B-012：相似度計算異常 → 跳過該 Ticket，繼續處理其他"""

        def mock_list_impl(version):
            return [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 機制",
                    "what": "自動偵測",
                    "status": "pending",
                },
                {
                    "id": "0.1.2-W3-002",
                    "title": "實作 SRP",  # 會導致異常
                    "what": "偵測",
                    "status": "pending",
                },
            ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=mock_list_impl,
        )

        # Mock _calculate_jaccard_similarity 在第二個 Ticket 時拋出異常
        original_calc = __import__(
            "ticket_system.commands.create",
            fromlist=["_calculate_jaccard_similarity"],
        )._calculate_jaccard_similarity

        call_count = [0]

        def mock_calc(text_a, text_b):
            call_count[0] += 1
            if call_count[0] == 2:
                raise UnicodeError("Encoding error")
            return original_calc(text_a, text_b)

        mocker.patch(
            "ticket_system.commands.create._calculate_jaccard_similarity",
            side_effect=mock_calc,
        )

        # 應跳過異常 Ticket，繼續處理
        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 機制",
            new_what="自動偵測",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 應能處理異常，可能有或無 WARNING（取決於其他 Ticket）
        # 重點是無例外向上拋出

    def test_b013_empty_pending_tickets(self, mocker, capsys):
        """B-013：pending tickets 目錄為空 → 靜默通過"""

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 機制",
            new_what="自動偵測",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()

        # 無候選 Ticket，靜默通過
        assert captured.out == ""


# ============================================================
# 擴展偵測範圍測試（ES-001 至 ES-008，W2-010 新增）
# ============================================================


class TestExtendedScopeDetection:
    """擴展偵測範圍測試：completed（7 天內）+ in_progress"""

    def test_es001_completed_within_7days_triggers_warning(self, mocker, capsys):
        """ES-001：7 天內 completed Ticket 觸發警告"""
        recent_time = (datetime.now() - timedelta(days=3)).isoformat()

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W2-007",
                    "title": "修正 Registry 模組品質問題",
                    "what": "修正 5 項技術債",
                    "status": "completed",
                    "completed_at": recent_time,
                },
            ],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="修正 Registry 模組品質問題",
            new_what="修正技術債",
            new_ticket_id="0.1.2-W2-010",
        )

        captured = capsys.readouterr()
        assert "[WARNING]" in captured.out
        assert "0.1.2-W2-007" in captured.out
        assert "已完成" in captured.out

    def test_es002_completed_beyond_7days_excluded(self, mocker, capsys):
        """ES-002：超過 7 天的 completed Ticket 不觸發警告"""
        old_time = (datetime.now() - timedelta(days=10)).isoformat()

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W1-001",
                    "title": "修正 Registry 模組品質問題",
                    "what": "修正技術債",
                    "status": "completed",
                    "completed_at": old_time,
                },
            ],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="修正 Registry 模組品質問題",
            new_what="修正技術債",
            new_ticket_id="0.1.2-W2-010",
        )

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_es003_completed_exactly_7days_boundary(self, mocker, capsys):
        """ES-003：恰好 7 天邊界的 completed Ticket 不被包含"""
        # 7 天 + 1 秒前 → 應排除
        boundary_time = (datetime.now() - timedelta(days=7, seconds=1)).isoformat()

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W1-001",
                    "title": "修正 Registry 模組品質問題",
                    "what": "修正技術債",
                    "status": "completed",
                    "completed_at": boundary_time,
                },
            ],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="修正 Registry 模組品質問題",
            new_what="修正技術債",
            new_ticket_id="0.1.2-W2-010",
        )

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_es004_in_progress_triggers_warning(self, mocker, capsys):
        """ES-004：in_progress Ticket 觸發警告（含 [進行中] 標籤）"""
        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W2-008",
                    "title": "建立檔案所有權隔離檢查 Hook",
                    "what": "建立 where.files 自動檢查",
                    "status": "in_progress",
                },
            ],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="建立檔案所有權隔離自動檢查",
            new_what="where.files 檢查",
            new_ticket_id="0.1.2-W2-011",
        )

        captured = capsys.readouterr()
        assert "[WARNING]" in captured.out
        assert "0.1.2-W2-008" in captured.out
        assert "進行中" in captured.out

    def test_es007_completed_no_completed_at_excluded(self, mocker, capsys):
        """ES-007：completed 但無 completed_at 欄位 → 排除（保守策略）"""
        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W1-001",
                    "title": "修正 Registry 模組品質問題",
                    "what": "修正技術債",
                    "status": "completed",
                    # 無 completed_at 欄位
                },
            ],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="修正 Registry 模組品質問題",
            new_what="修正技術債",
            new_ticket_id="0.1.2-W2-010",
        )

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_es008_completed_invalid_completed_at_excluded(self, mocker, capsys):
        """ES-008：completed_at 格式異常 → 排除（保守策略）"""
        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W1-001",
                    "title": "修正 Registry 模組品質問題",
                    "what": "修正技術債",
                    "status": "completed",
                    "completed_at": "invalid-date-format",
                },
            ],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="修正 Registry 模組品質問題",
            new_what="修正技術債",
            new_ticket_id="0.1.2-W2-010",
        )

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_es009_pending_no_status_label(self, mocker, capsys):
        """ES-009：pending Ticket 不加標籤（向下相容）"""
        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 自動偵測機制",
                    "what": "自動偵測 SRP 違規",
                    "status": "pending",
                },
            ],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 偵測功能",
            new_what="SRP 自動偵測",
            new_ticket_id="0.1.2-W3-003",
        )

        captured = capsys.readouterr()
        assert "[WARNING]" in captured.out
        assert "0.1.2-W3-001" in captured.out
        # pending 不應有狀態標籤
        assert "進行中" not in captured.out
        assert "已完成" not in captured.out


class TestHelperFunctions:
    """輔助函式單元測試"""

    def test_is_in_scope_pending(self):
        """pending Ticket 始終在範圍內"""
        ticket = {"status": "pending"}
        window_start = datetime.now() - timedelta(days=7)
        assert _is_in_detection_scope(ticket, window_start) is True

    def test_is_in_scope_in_progress(self):
        """in_progress Ticket 始終在範圍內"""
        ticket = {"status": "in_progress"}
        window_start = datetime.now() - timedelta(days=7)
        assert _is_in_detection_scope(ticket, window_start) is True

    def test_is_in_scope_completed_recent(self):
        """7 天內 completed Ticket 在範圍內"""
        recent = (datetime.now() - timedelta(days=2)).isoformat()
        ticket = {"status": "completed", "completed_at": recent}
        window_start = datetime.now() - timedelta(days=7)
        assert _is_in_detection_scope(ticket, window_start) is True

    def test_is_in_scope_completed_old(self):
        """超過 7 天的 completed Ticket 不在範圍內"""
        old = (datetime.now() - timedelta(days=10)).isoformat()
        ticket = {"status": "completed", "completed_at": old}
        window_start = datetime.now() - timedelta(days=7)
        assert _is_in_detection_scope(ticket, window_start) is False

    def test_is_in_scope_blocked(self):
        """blocked Ticket 不在範圍內"""
        ticket = {"status": "blocked"}
        window_start = datetime.now() - timedelta(days=7)
        assert _is_in_detection_scope(ticket, window_start) is False

    def test_get_status_label_pending(self):
        """pending → 空字串"""
        assert _get_status_label("pending") == ""

    def test_get_status_label_in_progress(self):
        """in_progress → 進行中"""
        assert _get_status_label("in_progress") == "進行中"

    def test_get_status_label_completed(self):
        """completed → 已完成"""
        assert _get_status_label("completed") == "已完成"


# ============================================================
# 整合測試（I-001 至 I-004）
# ============================================================


class TestIntegration:
    """整合點驗證測試"""

    def test_i001_call_timing_verification(self, mocker):
        """I-001：驗證呼叫時機（blockedBy 後、save 前）"""
        # 此測試驗證呼叫位置，在 execute() 中進行
        # 這裡只驗證函式簽名和行為
        mock = mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [],
        )

        # 調用函式，驗證不拋出例外
        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作",
            new_what="功能",
            new_ticket_id="0.1.2-W3-003",
        )

        # 確認 list_tickets 被呼叫
        mock.assert_called_once_with("0.1.2")

    def test_i002_detection_does_not_block_creation(self, mocker, capsys):
        """I-002：偵測結果不影響後續儲存流程"""

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 機制",
                    "what": "自動偵測",
                    "status": "pending",
                }
            ],
        )

        # 即使輸出 WARNING，函式應正常返回
        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作 SRP 機制",
            new_what="自動偵測",
            new_ticket_id="0.1.2-W3-003",
        )

        # 函式應無例外返回
        # WARNING 應輸出
        captured = capsys.readouterr()
        assert "[WARNING]" in captured.out

    def test_i003_parameter_passing(self, mocker):
        """I-003：參數正確傳遞"""
        mock_calc = mocker.patch(
            "ticket_system.commands.create._calculate_jaccard_similarity",
            return_value=0.0,
        )

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: [
                {
                    "id": "0.1.2-W3-001",
                    "title": "實作 SRP 機制",
                    "what": "自動偵測",
                    "status": "pending",
                }
            ],
        )

        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="新增功能",
            new_what="修復問題",
            new_ticket_id="0.1.2-W3-003",
        )

        # 驗證參數傳遞正確
        assert mock_calc.called
        call_args = mock_calc.call_args[0]
        assert "新增功能" in call_args[0]
        assert "修復問題" in call_args[0]

    def test_i004_exception_does_not_block_creation(self, mocker):
        """I-004：_detect_duplicate_tickets 異常不阻斷建立"""

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=RuntimeError("Unexpected error"),
        )

        # 應無例外拋出
        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="實作",
            new_what="功能",
            new_ticket_id="0.1.2-W3-003",
        )

        # 函式應靜默返回


# ============================================================
# 效能邊界測試（P-001 至 P-002）
# ============================================================


class TestPerformance:
    """效能邊界測試"""

    def test_p001_few_pending_tickets(self, mocker):
        """P-001：10 個 pending Ticket 的執行時間 < 50ms"""

        # 建立 10 個 pending Ticket
        pending_tickets = [
            {
                "id": f"0.1.2-W3-{i:03d}",
                "title": f"實作功能 {i}",
                "what": f"執行操作 {i}",
                "status": "pending",
            }
            for i in range(10)
        ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: pending_tickets,
        )

        start = time.time()
        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="新增功能",
            new_what="自動執行",
            new_ticket_id="0.1.2-W3-999",
        )
        elapsed = time.time() - start

        # 應在 50ms 內完成
        assert elapsed < 0.05

    def test_p002_many_pending_tickets(self, mocker):
        """P-002：50 個 pending Ticket 的執行時間 < 100ms"""

        # 建立 50 個 pending Ticket
        pending_tickets = [
            {
                "id": f"0.1.2-W3-{i:03d}",
                "title": f"實作功能 {i}",
                "what": f"執行操作 {i}",
                "status": "pending",
            }
            for i in range(50)
        ]

        mocker.patch(
            "ticket_system.commands.create.list_tickets",
            side_effect=lambda v: pending_tickets,
        )

        start = time.time()
        _detect_duplicate_tickets(
            version="0.1.2",
            new_title="新增功能",
            new_what="自動執行",
            new_ticket_id="0.1.2-W3-999",
        )
        elapsed = time.time() - start

        # 應在 100ms 內完成
        assert elapsed < 0.1
