"""
ticket show 子命令測試

對應 Ticket 0.18.0-W17-015.1 驗收條件 6 項：
1. TTY 下預設彩色渲染
2. pipe 至 cat 自動降 raw
3. -r 強制 raw
4. -R X 指定渲染器缺失時明確報錯 exit 2
5. -p/-P 分頁控制生效
6. 全部渲染器缺失時 fallback raw 不 crash
"""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from ticket_system.commands.show import (
    RENDERER_INSTALL_HINTS,
    RENDERER_PRIORITY,
    build_full_content,
    build_renderer_command,
    detect_installed_renderers,
    detect_renderer,
    execute_show,
    expand_short_id,
    format_renderer_choices_help,
)


# ---------- 單元測試：純函式 ----------

class TestExpandShortId:
    def test_short_id_gets_version_prepended(self):
        assert expand_short_id("W17-015", "0.18.0") == "0.18.0-W17-015"

    def test_short_id_with_subtask(self):
        assert expand_short_id("W17-015.1", "0.18.0") == "0.18.0-W17-015.1"

    def test_full_id_unchanged(self):
        assert expand_short_id("0.18.0-W17-015", "0.18.0") == "0.18.0-W17-015"

    def test_short_id_without_version_unchanged(self):
        assert expand_short_id("W17-015", None) == "W17-015"

    def test_invalid_format_unchanged(self):
        assert expand_short_id("not-an-id", "0.18.0") == "not-an-id"


class TestBuildFullContent:
    def test_combines_frontmatter_and_body(self):
        ticket = {"id": "X-1", "status": "pending", "_body": "# Title\nhello"}
        content = build_full_content(ticket)
        assert content.startswith("---\n")
        assert "id: X-1" in content
        assert "status: pending" in content
        assert "---\n\n# Title\nhello" in content

    def test_skips_private_keys(self):
        ticket = {"id": "X-1", "_path": "/tmp/x", "_body": "body"}
        content = build_full_content(ticket)
        assert "_path" not in content


class TestDetectRenderer:
    def test_auto_returns_first_available(self):
        def fake_which(name):
            return "/usr/bin/mdcat" if name == "mdcat" else None

        with patch("ticket_system.commands.show.shutil.which", side_effect=fake_which):
            assert detect_renderer("auto") == "mdcat"

    def test_auto_all_missing_returns_none(self):
        with patch("ticket_system.commands.show.shutil.which", return_value=None):
            assert detect_renderer("auto") is None

    def test_specific_available(self):
        with patch("ticket_system.commands.show.shutil.which", return_value="/usr/bin/bat"):
            assert detect_renderer("bat") == "bat"

    def test_specific_missing_returns_none(self):
        with patch("ticket_system.commands.show.shutil.which", return_value=None):
            assert detect_renderer("glow") is None


class TestBuildRendererCommand:
    def test_bat_auto(self):
        cmd = build_renderer_command("bat", "auto")
        assert cmd[0] == "bat"
        assert "--paging=always" not in cmd
        assert "--paging=never" not in cmd

    def test_bat_always(self):
        assert "--paging=always" in build_renderer_command("bat", "always")

    def test_bat_never(self):
        assert "--paging=never" in build_renderer_command("bat", "never")

    def test_glow_always_adds_pager(self):
        cmd = build_renderer_command("glow", "always")
        assert "-p" in cmd

    def test_glow_auto_no_pager_flag(self):
        cmd = build_renderer_command("glow", "auto")
        assert "-p" not in cmd


# ---------- 整合測試：execute_show ----------

SAMPLE_TICKET = {
    "id": "0.18.0-W17-015",
    "status": "in_progress",
    "_body": "# Sample\n\nContent here.",
}


def _make_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        ticket_id="0.18.0-W17-015",
        version=None,
        raw=False,
        renderer="auto",
        pager=False,
        no_pager=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def mock_ticket_load():
    with patch(
        "ticket_system.commands.show.load_and_validate_ticket",
        return_value=(SAMPLE_TICKET, None),
    ) as m:
        yield m


@pytest.fixture
def mock_version():
    with patch(
        "ticket_system.commands.show.resolve_version",
        return_value="0.18.0",
    ) as m:
        yield m


class TestExecuteShow:
    def test_tty_with_renderer_invokes_subprocess(
        self, mock_ticket_load, mock_version
    ):
        """AC-1: TTY 下且偵測到渲染器，應呼叫 subprocess。"""
        with patch("sys.stdout.isatty", return_value=True), patch(
            "ticket_system.commands.show.shutil.which",
            side_effect=lambda n: "/usr/bin/bat" if n == "bat" else None,
        ), patch(
            "ticket_system.commands.show.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            rc = execute_show(_make_args())
            assert rc == 0
            assert mock_run.called
            cmd = mock_run.call_args.args[0]
            assert cmd[0] == "bat"

    def test_non_tty_forces_raw(self, mock_ticket_load, mock_version, capsys):
        """AC-2: pipe 到 cat（非 TTY）自動降 raw，不呼叫 subprocess。"""
        with patch("sys.stdout.isatty", return_value=False), patch(
            "ticket_system.commands.show.subprocess.run"
        ) as mock_run:
            rc = execute_show(_make_args())
            assert rc == 0
            assert not mock_run.called
            captured = capsys.readouterr().out
            assert "id: 0.18.0-W17-015" in captured

    def test_raw_flag_forces_raw_even_in_tty(
        self, mock_ticket_load, mock_version, capsys
    ):
        """AC-3: -r 即使 TTY 仍強制 raw。"""
        with patch("sys.stdout.isatty", return_value=True), patch(
            "ticket_system.commands.show.subprocess.run"
        ) as mock_run:
            rc = execute_show(_make_args(raw=True))
            assert rc == 0
            assert not mock_run.called
            assert "id: 0.18.0-W17-015" in capsys.readouterr().out

    def test_specified_renderer_missing_errors_exit_2(
        self, mock_ticket_load, mock_version, capsys
    ):
        """AC-4: -R X 指定但 X 不存在 → exit 2 + stderr 明確訊息。"""
        with patch("sys.stdout.isatty", return_value=True), patch(
            "ticket_system.commands.show.shutil.which", return_value=None
        ):
            rc = execute_show(_make_args(renderer="glow"))
            assert rc == 2
            err = capsys.readouterr().err
            assert "glow" in err
            assert "未安裝" in err or "not" in err.lower()

    def test_pager_always_sets_renderer_flag(
        self, mock_ticket_load, mock_version
    ):
        """AC-5a: -p 傳給 bat 時應加 --paging=always。"""
        with patch("sys.stdout.isatty", return_value=True), patch(
            "ticket_system.commands.show.shutil.which",
            side_effect=lambda n: "/usr/bin/bat" if n == "bat" else None,
        ), patch(
            "ticket_system.commands.show.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            execute_show(_make_args(renderer="bat", pager=True))
            cmd = mock_run.call_args.args[0]
            assert "--paging=always" in cmd

    def test_no_pager_sets_renderer_flag(
        self, mock_ticket_load, mock_version
    ):
        """AC-5b: -P 傳給 bat 時應加 --paging=never。"""
        with patch("sys.stdout.isatty", return_value=True), patch(
            "ticket_system.commands.show.shutil.which",
            side_effect=lambda n: "/usr/bin/bat" if n == "bat" else None,
        ), patch(
            "ticket_system.commands.show.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            execute_show(_make_args(renderer="bat", no_pager=True))
            cmd = mock_run.call_args.args[0]
            assert "--paging=never" in cmd

    def test_all_renderers_missing_falls_back_raw(
        self, mock_ticket_load, mock_version, capsys
    ):
        """AC-6: 全部渲染器缺失時 fallback raw + stderr warning，不 crash。"""
        with patch("sys.stdout.isatty", return_value=True), patch(
            "ticket_system.commands.show.shutil.which", return_value=None
        ), patch(
            "ticket_system.commands.show.subprocess.run"
        ) as mock_run:
            rc = execute_show(_make_args())  # auto + 全缺失
            assert rc == 0
            assert not mock_run.called
            out_err = capsys.readouterr()
            assert "id: 0.18.0-W17-015" in out_err.out
            assert "WARNING" in out_err.err or "warning" in out_err.err.lower()

    def test_ticket_not_found_returns_1(self, mock_version):
        """載入失敗回傳 1。"""
        with patch(
            "ticket_system.commands.show.load_and_validate_ticket",
            return_value=(None, "not found"),
        ):
            rc = execute_show(_make_args())
            assert rc == 1

    def test_short_id_expansion_calls_loader_with_full_id(
        self, mock_version
    ):
        """短 ID 傳入時應展開為完整 ID 後傳給 loader。"""
        with patch(
            "ticket_system.commands.show.load_and_validate_ticket",
            return_value=(SAMPLE_TICKET, None),
        ) as mock_load, patch(
            "sys.stdout.isatty", return_value=False
        ):
            execute_show(_make_args(ticket_id="W17-015"))
            assert mock_load.called
            args, _ = mock_load.call_args
            assert args[1] == "0.18.0-W17-015"


# ---------- W17-015.2：渲染器 UX（安裝狀態 + 安裝指令） ----------


class TestDetectInstalledRenderers:
    def test_returns_dict_for_each_supported_renderer(self):
        with patch(
            "ticket_system.commands.show.shutil.which",
            side_effect=lambda n: f"/usr/bin/{n}" if n == "bat" else None,
        ):
            result = detect_installed_renderers()
        assert set(result.keys()) == set(RENDERER_PRIORITY)
        assert result["bat"] is True
        assert result["glow"] is False
        assert result["mdcat"] is False

    def test_all_installed(self):
        with patch(
            "ticket_system.commands.show.shutil.which",
            return_value="/usr/bin/x",
        ):
            result = detect_installed_renderers()
        assert all(result.values())

    def test_none_installed(self):
        with patch(
            "ticket_system.commands.show.shutil.which",
            return_value=None,
        ):
            result = detect_installed_renderers()
        assert not any(result.values())


class TestFormatRendererChoicesHelp:
    def test_marks_installed_renderers(self):
        with patch(
            "ticket_system.commands.show.shutil.which",
            side_effect=lambda n: f"/usr/bin/{n}" if n == "glow" else None,
        ):
            help_text = format_renderer_choices_help()
        assert "glow[已安裝]" in help_text
        assert "mdcat[未安裝" in help_text
        assert "bat[未安裝" in help_text

    def test_contains_install_hint_for_missing(self):
        with patch(
            "ticket_system.commands.show.shutil.which",
            return_value=None,
        ):
            help_text = format_renderer_choices_help()
        # 未安裝時應帶入 RENDERER_INSTALL_HINTS 的指令
        assert "brew install glow" in help_text
        assert "brew install mdcat" in help_text
        assert "brew install bat" in help_text

    def test_all_installed_no_hint(self):
        with patch(
            "ticket_system.commands.show.shutil.which",
            return_value="/usr/bin/x",
        ):
            help_text = format_renderer_choices_help()
        assert "未安裝" not in help_text
        for name in RENDERER_PRIORITY:
            assert f"{name}[已安裝]" in help_text


class TestExecuteShowMissingRendererHint:
    def test_error_message_includes_install_command(self, capsys):
        """-R 指定未安裝渲染器時，stderr 必須包含安裝指令。"""
        with patch(
            "ticket_system.commands.show.load_and_validate_ticket",
            return_value=(SAMPLE_TICKET, None),
        ), patch(
            "sys.stdout.isatty", return_value=True
        ), patch(
            "ticket_system.commands.show.shutil.which",
            return_value=None,
        ):
            exit_code = execute_show(_make_args(renderer="glow"))
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "未安裝" in captured.err
        assert "brew install glow" in captured.err

    def test_hint_matches_renderer_install_hints_mapping(self, capsys):
        """每個支援的渲染器都應有對應的安裝指令 hint。"""
        for name in RENDERER_PRIORITY:
            with patch(
                "ticket_system.commands.show.load_and_validate_ticket",
                return_value=(SAMPLE_TICKET, None),
            ), patch(
                "sys.stdout.isatty", return_value=True
            ), patch(
                "ticket_system.commands.show.shutil.which",
                return_value=None,
            ):
                execute_show(_make_args(renderer=name))
            err = capsys.readouterr().err
            assert RENDERER_INSTALL_HINTS[name].split()[0:2] == ["brew", "install"]
            assert name in err
