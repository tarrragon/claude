"""W11-003.5: 升級 PROP-009 清單式驗證為阻擋建立。

測試 _enforce_create_checklist 的阻擋行為與 --force 逃生閥。
"""

import pytest

from ticket_system.commands.create import _enforce_create_checklist


class TestEnforceCreateChecklist:
    """_enforce_create_checklist 阻擋行為測試。"""

    def test_no_missing_does_not_block(self, capsys):
        """無缺失欄位時不阻擋（return None）。"""
        # 不應拋出 SystemExit
        _enforce_create_checklist(missing=[], force=False)

    def test_missing_blocks_with_exit_1(self, capsys):
        """有缺失欄位且未 --force 時 sys.exit(1)。"""
        with pytest.raises(SystemExit) as exc_info:
            _enforce_create_checklist(missing=["who", "acceptance"], force=False)
        assert exc_info.value.code == 1

    def test_missing_with_force_does_not_block(self, capsys):
        """有缺失欄位但 --force 時不阻擋，但輸出 WARNING。"""
        # 不應拋出 SystemExit
        _enforce_create_checklist(missing=["who", "acceptance"], force=True)
        captured = capsys.readouterr()
        # WARNING 應輸出（含欄位名）
        assert "who" in captured.out + captured.err
        assert "acceptance" in captured.out + captured.err

    def test_blocked_message_lists_missing_fields(self, capsys):
        """阻擋訊息列出所有缺失欄位（讓使用者知道補哪些）。"""
        with pytest.raises(SystemExit):
            _enforce_create_checklist(
                missing=["who", "where.files", "acceptance"],
                force=False,
            )
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "who" in output
        assert "where.files" in output
        assert "acceptance" in output

    def test_blocked_message_mentions_force_flag(self, capsys):
        """阻擋訊息提示 --force 逃生閥可用。"""
        with pytest.raises(SystemExit):
            _enforce_create_checklist(missing=["who"], force=False)
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "--force" in output


class TestForceArgPassthrough:
    """確認 --force CLI 旗標已加入 argparser。"""

    def _build_parser(self):
        import argparse
        from ticket_system.commands.create import register

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="cmd")
        register(subparsers)
        return parser

    def test_force_flag_registered_in_parser(self):
        """argparser 含 --force 旗標。"""
        parser = self._build_parser()
        args = parser.parse_args([
            "create",
            "--action", "test",
            "--target", "sth",
            "--force",
        ])
        assert getattr(args, "force", False) is True

    def test_force_flag_default_false(self):
        """未指定 --force 時預設 False。"""
        parser = self._build_parser()
        args = parser.parse_args([
            "create",
            "--action", "test",
            "--target", "sth",
        ])
        assert getattr(args, "force", False) is False
