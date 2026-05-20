"""
paths.py 的 get_tickets_dir() 單元測試（W14-052 RED）

針對未存在主版本的目錄結構生成測試。

根因：get_tickets_dir() 行 92-104 依賴目錄存在性檢查決定三層 vs flat 路徑，
未存在主版本（v2.0.0 / v10.3.1 等）會 fallback 到 flat 結構，與 v0.x 三層
規則不一致。

修復方向：解析得到 `len(parts) >= 2` 時一律回傳三層階層路徑；
flat 結構僅作為無法解析 major.minor 時的最終 fallback。
"""

from pathlib import Path
from unittest.mock import patch
from ticket_system.lib.paths import get_tickets_dir


class TestGetTicketsDirHierarchical:
    """get_tickets_dir() 三層階層路徑生成測試"""

    def test_v2_major_returns_hierarchical_even_when_dir_not_exists(self, tmp_path):
        """v2.0.0（未存在主版本）應回傳三層 v2/v2.0/v2.0.0/tickets。

        重現 W14-051 根因：v2/ 目錄不存在時，當前實作 fallback 到 flat
        docs/work-logs/v2.0.0/tickets，違反三層規則。
        """
        with patch("ticket_system.lib.paths.get_project_root", return_value=tmp_path):
            result = get_tickets_dir("2.0.0")
            expected = tmp_path / "docs" / "work-logs" / "v2" / "v2.0" / "v2.0.0" / "tickets"
            assert result == expected, (
                f"未存在主版本應產生三層路徑，"
                f"預期 {expected}，實際 {result}"
            )

    def test_v10_3_1_double_digit_major_returns_hierarchical(self, tmp_path):
        """v10.3.1（雙位數主版本）應回三層 v10/v10.3/v10.3.1/tickets。

        邊界測試：多位數版本號的字串分割正確性。
        """
        with patch("ticket_system.lib.paths.get_project_root", return_value=tmp_path):
            result = get_tickets_dir("10.3.1")
            expected = tmp_path / "docs" / "work-logs" / "v10" / "v10.3" / "v10.3.1" / "tickets"
            assert result == expected

    def test_v0_18_0_existing_hierarchical_preserved(self, tmp_path):
        """v0.18.0 既有三層結構不受影響（回歸防護）。

        建立 v0/ 目錄模擬既有 series 存在，確認回傳路徑仍為三層。
        """
        (tmp_path / "docs" / "work-logs" / "v0" / "v0.18" / "v0.18.0" / "tickets").mkdir(
            parents=True
        )
        with patch("ticket_system.lib.paths.get_project_root", return_value=tmp_path):
            result = get_tickets_dir("0.18.0")
            expected = tmp_path / "docs" / "work-logs" / "v0" / "v0.18" / "v0.18.0" / "tickets"
            assert result == expected

    def test_v_prefixed_version_strips_correctly(self, tmp_path):
        """版本字串含 v 前綴（如 "v3.1.0"）應正確解析為三層。

        邊界測試：lstrip 處理 + parts 解析。
        """
        with patch("ticket_system.lib.paths.get_project_root", return_value=tmp_path):
            result = get_tickets_dir("v3.1.0")
            expected = tmp_path / "docs" / "work-logs" / "v3" / "v3.1" / "v3.1.0" / "tickets"
            assert result == expected
