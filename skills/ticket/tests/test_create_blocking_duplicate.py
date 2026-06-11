"""
ticket create Tier 2 阻擋層（同窗口高相似度冪等防護）測試。

涵蓋（1.0.0-W1-040.1）：
- TP 阻擋：高相似 + 短窗口 + pending/in_progress → 阻擋
- FP 不阻擋：兄弟票低相似 / batch 同質 < 0.6 / 高相似但 completed / 高相似但過窗
- --allow-duplicate 旁路
- bulk_create 警告層補齊
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from ticket_system.commands.create import (
    _find_blocking_duplicate,
    _enforce_blocking_duplicate,
    _validate_before_persist,
)
from ticket_system.lib.constants import (
    DUPLICATE_BLOCK_THRESHOLD,
    DUPLICATE_BLOCK_WINDOW_MINUTES,
)


# 量測依據確認：常數值符合 parent W1-040 設計
def test_block_constants_match_design():
    assert DUPLICATE_BLOCK_THRESHOLD == 0.6
    assert DUPLICATE_BLOCK_WINDOW_MINUTES == 60


def _patch_tickets(mocker, tickets):
    mocker.patch(
        "ticket_system.commands.create.list_tickets",
        return_value=tickets,
    )


def _patch_creation_time(mocker, minutes_ago):
    """patch 候選票檔案建立時間為 N 分鐘前。"""
    target = datetime.now() - timedelta(minutes=minutes_ago)
    mocker.patch(
        "ticket_system.commands.create._get_ticket_creation_time",
        return_value=target,
    )


class TestFindBlockingDuplicate:
    def test_tp_high_similarity_in_window_pending(self, mocker):
        """TP：逐字相同 + 5 分鐘前 + pending → 命中"""
        _patch_tickets(mocker, [
            {
                "id": "0.1.2-W1-001",
                "title": "實作 SRP 偵測機制",
                "what": "自動偵測 SRP 違規",
                "status": "pending",
            },
        ])
        _patch_creation_time(mocker, minutes_ago=5)

        hit = _find_blocking_duplicate(
            version="0.1.2",
            new_title="實作 SRP 偵測機制",
            new_what="自動偵測 SRP 違規",
            new_ticket_id="0.1.2-W1-002",
        )
        assert hit is not None
        assert hit[0] == "0.1.2-W1-001"
        assert hit[3] >= DUPLICATE_BLOCK_THRESHOLD

    def test_tp_in_progress_candidate(self, mocker):
        """TP：高相似 + 短窗口 + in_progress → 命中"""
        _patch_tickets(mocker, [
            {
                "id": "0.1.2-W1-001",
                "title": "實作 SRP 偵測機制",
                "what": "自動偵測 SRP 違規",
                "status": "in_progress",
            },
        ])
        _patch_creation_time(mocker, minutes_ago=10)

        hit = _find_blocking_duplicate(
            version="0.1.2",
            new_title="實作 SRP 偵測機制",
            new_what="自動偵測 SRP 違規",
            new_ticket_id="0.1.2-W1-002",
        )
        assert hit is not None

    def test_fp_sibling_low_similarity(self, mocker):
        """FP：真實兄弟票（低相似度 < 0.6）→ 不命中"""
        _patch_tickets(mocker, [
            {
                "id": "0.1.2-W1-001",
                "title": "修復 WebSocket 連線問題",
                "what": "連線重試邏輯",
                "status": "pending",
            },
        ])
        _patch_creation_time(mocker, minutes_ago=1)

        hit = _find_blocking_duplicate(
            version="0.1.2",
            new_title="新增權限驗證系統",
            new_what="驗證使用者權限",
            new_ticket_id="0.1.2-W1-002",
        )
        assert hit is None

    def test_fp_batch_homogeneous_below_block_threshold(self, mocker):
        """FP：batch 同質模板（約 0.4 < 0.6）→ 不命中（僅 Tier 1 警告）"""
        _patch_tickets(mocker, [
            {
                "id": "0.1.2-W1-001",
                "title": "實作搜尋篩選 Widget",
                "what": "建立搜尋篩選介面元件",
                "status": "pending",
            },
        ])
        _patch_creation_time(mocker, minutes_ago=1)

        new_title = "實作批量匯出 Page"
        new_what = "建立批量匯出操作元件"
        hit = _find_blocking_duplicate(
            version="0.1.2",
            new_title=new_title,
            new_what=new_what,
            new_ticket_id="0.1.2-W1-002",
        )
        # 同質模板共享「實作/建立/元件」等 token 但任務名差異大，
        # 相似度落在 Tier 1 警告（>=0.3）與 Tier 2 阻擋（>=0.6）之間，不阻擋
        from ticket_system.commands.create import _calculate_jaccard_similarity
        sim = _calculate_jaccard_similarity(
            f"{new_title} {new_what}",
            "實作搜尋篩選 Widget 建立搜尋篩選介面元件",
        )
        assert sim < DUPLICATE_BLOCK_THRESHOLD
        assert hit is None

    def test_fp_completed_not_blocked(self, mocker):
        """FP：高相似但候選為 completed → 不阻擋（合法重做）"""
        _patch_tickets(mocker, [
            {
                "id": "0.1.2-W1-001",
                "title": "實作 SRP 偵測機制",
                "what": "自動偵測 SRP 違規",
                "status": "completed",
            },
        ])
        _patch_creation_time(mocker, minutes_ago=1)

        hit = _find_blocking_duplicate(
            version="0.1.2",
            new_title="實作 SRP 偵測機制",
            new_what="自動偵測 SRP 違規",
            new_ticket_id="0.1.2-W1-002",
        )
        assert hit is None

    def test_fp_high_similarity_out_of_window(self, mocker):
        """FP：高相似但建立時間超出窗口（120 分鐘前）→ 不命中"""
        _patch_tickets(mocker, [
            {
                "id": "0.1.2-W1-001",
                "title": "實作 SRP 偵測機制",
                "what": "自動偵測 SRP 違規",
                "status": "pending",
            },
        ])
        _patch_creation_time(mocker, minutes_ago=120)

        hit = _find_blocking_duplicate(
            version="0.1.2",
            new_title="實作 SRP 偵測機制",
            new_what="自動偵測 SRP 違規",
            new_ticket_id="0.1.2-W1-002",
        )
        assert hit is None

    def test_fp_creation_time_unavailable(self, mocker):
        """FP：無法取得建立時間（None）→ 視為不在窗口，不命中"""
        _patch_tickets(mocker, [
            {
                "id": "0.1.2-W1-001",
                "title": "實作 SRP 偵測機制",
                "what": "自動偵測 SRP 違規",
                "status": "pending",
            },
        ])
        mocker.patch(
            "ticket_system.commands.create._get_ticket_creation_time",
            return_value=None,
        )

        hit = _find_blocking_duplicate(
            version="0.1.2",
            new_title="實作 SRP 偵測機制",
            new_what="自動偵測 SRP 違規",
            new_ticket_id="0.1.2-W1-002",
        )
        assert hit is None

    def test_excludes_parent_ticket(self, mocker):
        """子任務排除 parent：高相似的 parent 不應命中"""
        _patch_tickets(mocker, [
            {
                "id": "0.1.2-W1-001",
                "title": "實作 SRP 偵測機制",
                "what": "自動偵測 SRP 違規",
                "status": "in_progress",
            },
        ])
        _patch_creation_time(mocker, minutes_ago=1)

        hit = _find_blocking_duplicate(
            version="0.1.2",
            new_title="實作 SRP 偵測機制",
            new_what="自動偵測 SRP 違規",
            new_ticket_id="0.1.2-W1-001.1",
        )
        assert hit is None


class TestEnforceBlockingDuplicate:
    def test_block_outputs_error_and_returns_false(self, mocker, capsys):
        """命中且未旁路 → 輸出阻擋訊息 + 回傳 False"""
        mocker.patch(
            "ticket_system.commands.create._find_blocking_duplicate",
            return_value=("0.1.2-W1-001", "實作 SRP 偵測機制", "pending", 0.95),
        )
        result = _enforce_blocking_duplicate(
            version="0.1.2",
            new_title="實作 SRP 偵測機制",
            new_what="自動偵測 SRP 違規",
            new_ticket_id="0.1.2-W1-002",
            allow_duplicate=False,
        )
        captured = capsys.readouterr()
        assert result is False
        assert "[ERROR]" in captured.out
        assert "0.1.2-W1-001" in captured.out
        assert "0.95" in captured.out
        assert "--allow-duplicate" in captured.out

    def test_bypass_outputs_info_and_returns_true(self, mocker, capsys):
        """命中但 --allow-duplicate → 輸出 INFO + 回傳 True（放行）"""
        mocker.patch(
            "ticket_system.commands.create._find_blocking_duplicate",
            return_value=("0.1.2-W1-001", "實作 SRP 偵測機制", "pending", 0.95),
        )
        result = _enforce_blocking_duplicate(
            version="0.1.2",
            new_title="實作 SRP 偵測機制",
            new_what="自動偵測 SRP 違規",
            new_ticket_id="0.1.2-W1-002",
            allow_duplicate=True,
        )
        captured = capsys.readouterr()
        assert result is True
        assert "[INFO]" in captured.out
        assert "--allow-duplicate" in captured.out

    def test_no_hit_returns_true_silently(self, mocker, capsys):
        """無命中 → 回傳 True，無阻擋訊息"""
        mocker.patch(
            "ticket_system.commands.create._find_blocking_duplicate",
            return_value=None,
        )
        result = _enforce_blocking_duplicate(
            version="0.1.2",
            new_title="任意標題",
            new_what="任意描述",
            new_ticket_id="0.1.2-W1-002",
            allow_duplicate=False,
        )
        captured = capsys.readouterr()
        assert result is True
        assert "[ERROR]" not in captured.out


class TestValidateBeforePersistIntegration:
    def test_blocking_duplicate_fails_validation(self, mocker):
        """整合：阻擋層命中 → _validate_before_persist 回傳 False"""
        mocker.patch(
            "ticket_system.commands.create._validate_blocked_by_references",
            return_value=True,
        )
        mocker.patch(
            "ticket_system.commands.create._enforce_blocking_duplicate",
            return_value=False,
        )
        config = {"title": "t", "what": "w", "blocked_by": None}
        result = _validate_before_persist(
            "0.1.2", "0.1.2-W1-002", config, allow_duplicate=False
        )
        assert result is False

    def test_allow_duplicate_passes_through(self, mocker):
        """整合：allow_duplicate 旁路 → 放行（Tier 1 仍執行）"""
        mocker.patch(
            "ticket_system.commands.create._validate_blocked_by_references",
            return_value=True,
        )
        enforce = mocker.patch(
            "ticket_system.commands.create._enforce_blocking_duplicate",
            return_value=True,
        )
        detect = mocker.patch(
            "ticket_system.commands.create._detect_duplicate_tickets",
            return_value=None,
        )
        config = {"title": "t", "what": "w", "blocked_by": None}
        result = _validate_before_persist(
            "0.1.2", "0.1.2-W1-002", config, allow_duplicate=True
        )
        assert result is True
        # allow_duplicate 應傳遞至阻擋層
        assert enforce.call_args.kwargs["allow_duplicate"] is True
        # Tier 1 警告層仍應執行
        detect.assert_called_once()


class TestBulkCreateWarningLayer:
    def test_bulk_create_invokes_warning_detection(self, mocker, tmp_path):
        """bulk_create 補齊警告層：每筆 target 呼叫 _detect_duplicate_tickets"""
        from ticket_system.commands import bulk_create

        detect = mocker.patch(
            "ticket_system.commands.bulk_create._detect_duplicate_tickets",
            return_value=None,
        )
        mocker.patch(
            "ticket_system.commands.bulk_create.get_next_seq",
            return_value=1,
        )
        mocker.patch(
            "ticket_system.commands.bulk_create.validate_create_checklist",
            return_value=[],
        )

        result = bulk_create._create_batch_tickets(
            template_defaults={"type": "IMP", "priority": "P2"},
            targets=["目標A", "目標B"],
            version="0.1.2",
            wave=1,
            dry_run=True,
        )
        # 兩筆 target 各觸發一次警告層偵測
        assert detect.call_count == 2
        assert result.total == 2
