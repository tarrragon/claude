"""set-title 子命令測試（0.2.1-W3-716）

title 欄位原本沒有任何合法更新途徑：CLI 無 set-title、set-what 只改 what、
直接編輯 frontmatter 被 guard 硬擋。本測試釘住新增的 set-title 途徑，並釘住
「set-what 不得連帶改動 title」——量測顯示 741 張票中有 124 張（17%）刻意
讓 title 為清單用短標籤、what 為完整敘述，同步兩者會破壞該既有分工。
"""

from unittest.mock import Mock, patch

from ticket_system.commands.fields import (
    execute_get_title,
    execute_set_title,
    execute_set_what,
)


def _make_args(ticket_id="0.31.0-W4-001", value=None, version="0.31.0"):
    args = Mock()
    args.ticket_id = ticket_id
    args.value = value
    args.version = version
    return args


class TestSetTitle:
    """set-title 寫入路徑"""

    def test_set_title_writes_title_field(self):
        """
        Given: 一張 title 為舊值的 Ticket
        When: 執行 set-title 帶入新值
        Then: 回傳 0，且 title 欄位被更新為新值
        """
        args = _make_args(value="修正後的短標籤")
        ticket = {"id": "0.31.0-W4-001", "title": "舊標籤", "what": "完整敘述保持不變"}

        with patch("ticket_system.commands.fields.load_and_validate_ticket") as mock_load, patch(
            "ticket_system.commands.fields.ticket_loader.save_ticket"
        ) as mock_save:
            mock_load.return_value = (ticket, None)

            result = execute_set_title(args, "0.31.0")

            assert result == 0
            assert ticket["title"] == "修正後的短標籤"
            mock_save.assert_called_once()

    def test_set_title_does_not_touch_what(self):
        """
        Given: 一張 title 與 what 刻意不同的 Ticket
        When: 只更新 title
        Then: what 維持原值不受影響
        """
        args = _make_args(value="新短標籤")
        ticket = {
            "id": "0.31.0-W4-001",
            "title": "舊短標籤",
            "what": "從遠端庫拉取 5 個版本落後的 skill：a, b, c",
        }

        with patch("ticket_system.commands.fields.load_and_validate_ticket") as mock_load, patch(
            "ticket_system.commands.fields.ticket_loader.save_ticket"
        ):
            mock_load.return_value = (ticket, None)

            execute_set_title(args, "0.31.0")

            assert ticket["what"] == "從遠端庫拉取 5 個版本落後的 skill：a, b, c"

    def test_get_title_returns_zero_when_present(self):
        """
        Given: Ticket 有 title 欄位
        When: 執行 get title
        Then: 回傳 0
        """
        args = _make_args()

        with patch("ticket_system.lib.ticket_ops.load_ticket") as mock_load:
            mock_load.return_value = {"id": "0.31.0-W4-001", "title": "某標籤"}

            assert execute_get_title(args, "0.31.0") == 0


class TestSetWhatDoesNotSyncTitle:
    """回歸防護：set-what 不得連帶改動 title

    17% 的既有票刻意讓兩者分化（title 為清單短標籤、what 為完整敘述）。
    若未來有人「順手」讓 set-what 同步 title，這些票的分工會被靜默抹平。
    """

    def test_set_what_leaves_title_untouched(self):
        """
        Given: 一張 title 與 what 不同的 Ticket
        When: 更新 what
        Then: title 維持原值
        """
        args = _make_args(value="更新後的完整敘述")
        ticket = {"id": "0.31.0-W4-001", "title": "清單用短標籤", "what": "舊的完整敘述"}

        with patch("ticket_system.commands.fields.load_and_validate_ticket") as mock_load, patch(
            "ticket_system.commands.fields.ticket_loader.save_ticket"
        ):
            mock_load.return_value = (ticket, None)

            execute_set_what(args, "0.31.0")

            assert ticket["what"] == "更新後的完整敘述"
            assert ticket["title"] == "清單用短標籤"


class TestSetTitleCliWiring:
    """CLI 接線：子命令必須註冊，否則函式存在也無法從命令列呼叫"""

    def test_set_title_registered_in_parser(self):
        """
        Given: track 的 argument parser
        When: 解析 track set-title 命令
        Then: 解析成功且帶出 ticket_id 與 value
        """
        import argparse

        from ticket_system.commands.track import register

        root = argparse.ArgumentParser()
        register(root.add_subparsers(dest="command"))
        parsed = root.parse_args(["track", "set-title", "0.31.0-W4-001", "新標籤"])

        assert parsed.operation == "set-title"
        assert parsed.ticket_id == "0.31.0-W4-001"
        assert parsed.value == "新標籤"

    def test_set_title_in_dispatch_map(self):
        """
        Given: track 的 operation dispatch map
        When: 查找 set-title
        Then: 對應到 execute_set_title

        接線與函式存在是兩件事：只加函式而不進 dispatch map，CLI 仍無法呼叫。
        """
        from ticket_system.commands.track import _create_command_handlers

        assert _create_command_handlers()["set-title"] is execute_set_title
