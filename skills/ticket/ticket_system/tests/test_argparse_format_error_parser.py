"""
test_argparse_format_error_parser
=================================

驗證 W17-008.5.4 的 ArgparseFormatErrorParser 雙路徑分流：

業務錯誤（→ format_error 結構化路徑，含版本標記）：
- invalid choice（subparser 子命令不存在）
- invalid type value（type=int 轉型失敗）

純語法錯誤（→ argparse 預設 POSIX 風格）：
- unrecognized arguments
- the following arguments are required

Source: ticket 0.18.0-W17-008.5.4
"""
import argparse

import pytest

from ticket_system.lib.messages import (
    ERROR_ENVELOPE_VERSION_MARKER,
    ArgparseFormatErrorParser,
    _classify_argparse_error,
)


# ---------------------------------------------------------------------------
# Fixture：與 track 結構等價的最小 parser
# ---------------------------------------------------------------------------


@pytest.fixture
def parser():
    """模擬 commands/track.py register() 結構：parent + subparsers + 多個操作 parser。"""
    p = ArgparseFormatErrorParser(prog="ticket track")
    sub = p.add_subparsers(
        dest="operation",
        required=True,
        parser_class=ArgparseFormatErrorParser,
    )
    p_claim = sub.add_parser("claim")
    p_claim.add_argument("ticket_id")
    p_claim.add_argument("--wave", type=int)
    return p


# ---------------------------------------------------------------------------
# 業務錯誤路徑（→ ErrorEnvelope 結構化）
# ---------------------------------------------------------------------------


class TestBusinessErrorsGoStructured:
    """業務錯誤應走 format_error(ErrorEnvelope)，含版本標記。"""

    def test_invalid_choice_for_subcommand(self, parser, capsys):
        """subparser 不存在的子命令 → invalid choice → 結構化輸出。"""
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["nonexistent_op"])
        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert ERROR_ENVELOPE_VERSION_MARKER in captured.err
        assert "errno: INVALID_CHOICE" in captured.err
        assert "[Error]" in captured.err

    def test_invalid_type_value(self, parser, capsys):
        """type=int 轉型失敗 → invalid int value → 結構化輸出。"""
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["claim", "T-001", "--wave", "not_a_number"])
        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert ERROR_ENVELOPE_VERSION_MARKER in captured.err
        assert "errno: INVALID_VALUE" in captured.err


# ---------------------------------------------------------------------------
# 純語法錯誤路徑（→ argparse 預設 POSIX 風格）
# ---------------------------------------------------------------------------


class TestSyntaxErrorsGoArgparseDefault:
    """純語法錯誤應保留 argparse 預設行為（不含版本標記）。"""

    def test_unrecognized_arguments(self, parser, capsys):
        """傳入未定義 flag → argparse 預設訊息。"""
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["claim", "T-001", "--bogus-flag"])
        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        # 純語法錯誤不應走結構化路徑
        assert ERROR_ENVELOPE_VERSION_MARKER not in captured.err
        assert "unrecognized arguments" in captured.err

    def test_missing_required_positional(self, parser, capsys):
        """漏帶必填 positional → argparse 預設訊息。"""
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["claim"])
        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert ERROR_ENVELOPE_VERSION_MARKER not in captured.err
        assert "required" in captured.err.lower()


# ---------------------------------------------------------------------------
# 分類器邊界測試
# ---------------------------------------------------------------------------


class TestClassifierBoundary:
    """_classify_argparse_error 邊界行為。"""

    def test_classify_invalid_choice(self):
        msg = "argument operation: invalid choice: 'foo' (choose from 'claim', 'release')"
        assert _classify_argparse_error(msg) == "INVALID_CHOICE"

    def test_classify_invalid_int_value(self):
        msg = "argument --wave: invalid int value: 'abc'"
        assert _classify_argparse_error(msg) == "INVALID_VALUE"

    def test_classify_unrecognized_returns_none(self):
        """純語法錯誤分類為 None（→ 委回 argparse 預設）。"""
        msg = "unrecognized arguments: --foo"
        assert _classify_argparse_error(msg) is None

    def test_classify_missing_required_returns_none(self):
        msg = "the following arguments are required: ticket_id"
        assert _classify_argparse_error(msg) is None
