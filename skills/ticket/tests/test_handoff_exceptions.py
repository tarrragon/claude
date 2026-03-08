"""
HandoffError Exception 階層測試

驗證 exceptions.py 中各 Exception 類的基本行為：
- 繼承關係正確
- guidance 欄位存在且包含可操作指引
- 自訂屬性正確設定
"""

import pytest

from ticket_system.commands.exceptions import (
    HandoffError,
    HandoffTargetNotFoundError,
    HandoffDuplicateError,
    HandoffSchemaError,
    HandoffDirectionUnknownError,
)


class TestHandoffError:
    """測試 HandoffError 基底類"""

    def test_is_exception(self):
        """HandoffError 繼承自 Exception"""
        err = HandoffError("test message")
        assert isinstance(err, Exception)

    def test_message(self):
        """HandoffError 保留訊息"""
        err = HandoffError("test message")
        assert str(err) == "test message"

    def test_guidance_default_empty(self):
        """HandoffError guidance 預設為空字串"""
        err = HandoffError("test message")
        assert err.guidance == ""

    def test_guidance_custom(self):
        """HandoffError 支援自訂 guidance"""
        err = HandoffError("test message", guidance="some guidance")
        assert err.guidance == "some guidance"


class TestHandoffTargetNotFoundError:
    """測試 HandoffTargetNotFoundError"""

    def test_is_handoff_error(self):
        """HandoffTargetNotFoundError 繼承自 HandoffError"""
        err = HandoffTargetNotFoundError("0.1.0-W5-001")
        assert isinstance(err, HandoffError)
        assert isinstance(err, Exception)

    def test_target_id_attribute(self):
        """target_id 屬性正確設定"""
        err = HandoffTargetNotFoundError("0.1.0-W5-001")
        assert err.target_id == "0.1.0-W5-001"

    def test_message_contains_target_id(self):
        """錯誤訊息包含目標 ID"""
        err = HandoffTargetNotFoundError("0.1.0-W5-001")
        assert "0.1.0-W5-001" in str(err)

    def test_guidance_contains_target_id(self):
        """guidance 包含目標 ID 和可操作指引"""
        err = HandoffTargetNotFoundError("0.1.0-W5-001")
        assert "0.1.0-W5-001" in err.guidance
        assert "ticket create" in err.guidance

    def test_guidance_not_empty(self):
        """guidance 不為空"""
        err = HandoffTargetNotFoundError("0.1.0-W5-001")
        assert err.guidance != ""


class TestHandoffDuplicateError:
    """測試 HandoffDuplicateError"""

    def test_is_handoff_error(self):
        """HandoffDuplicateError 繼承自 HandoffError"""
        err = HandoffDuplicateError("0.1.0-W5-001", "2026-01-01T00:00:00")
        assert isinstance(err, HandoffError)

    def test_attributes(self):
        """ticket_id 和 existing_timestamp 屬性正確設定"""
        err = HandoffDuplicateError("0.1.0-W5-001", "2026-01-01T00:00:00")
        assert err.ticket_id == "0.1.0-W5-001"
        assert err.existing_timestamp == "2026-01-01T00:00:00"

    def test_guidance_contains_ticket_id(self):
        """guidance 包含 ticket ID"""
        err = HandoffDuplicateError("0.1.0-W5-001", "2026-01-01T00:00:00")
        assert "0.1.0-W5-001" in err.guidance

    def test_guidance_contains_resume_instruction(self):
        """guidance 包含 resume 操作指引"""
        err = HandoffDuplicateError("0.1.0-W5-001", "2026-01-01T00:00:00")
        assert "resume" in err.guidance


class TestHandoffSchemaError:
    """測試 HandoffSchemaError"""

    def test_is_handoff_error(self):
        """HandoffSchemaError 繼承自 HandoffError"""
        err = HandoffSchemaError("/path/to/handoff.json", ["ticket_id", "direction"])
        assert isinstance(err, HandoffError)

    def test_attributes(self):
        """file_path 和 missing_fields 屬性正確設定"""
        err = HandoffSchemaError("/path/to/handoff.json", ["ticket_id", "direction"])
        assert err.file_path == "/path/to/handoff.json"
        assert err.missing_fields == ["ticket_id", "direction"]

    def test_message_contains_missing_fields(self):
        """錯誤訊息包含缺失欄位"""
        err = HandoffSchemaError("/path/to/handoff.json", ["ticket_id"])
        assert "ticket_id" in str(err)

    def test_guidance_not_empty(self):
        """guidance 不為空"""
        err = HandoffSchemaError("/path/to/handoff.json", ["ticket_id"])
        assert err.guidance != ""


class TestHandoffDirectionUnknownError:
    """測試 HandoffDirectionUnknownError"""

    def test_is_handoff_error(self):
        """HandoffDirectionUnknownError 繼承自 HandoffError"""
        err = HandoffDirectionUnknownError("unknown-dir", "/path/handoff.json")
        assert isinstance(err, HandoffError)

    def test_attributes(self):
        """direction 和 file_path 屬性正確設定"""
        err = HandoffDirectionUnknownError("unknown-dir", "/path/handoff.json")
        assert err.direction == "unknown-dir"
        assert err.file_path == "/path/handoff.json"

    def test_message_contains_direction(self):
        """錯誤訊息包含未知 direction 值"""
        err = HandoffDirectionUnknownError("unknown-dir", "/path/handoff.json")
        assert "unknown-dir" in str(err)

    def test_guidance_lists_known_directions(self):
        """guidance 列出已知 direction 值"""
        err = HandoffDirectionUnknownError("unknown-dir", "/path/handoff.json")
        assert "context-refresh" in err.guidance
        assert "to-parent" in err.guidance


class TestExceptionHierarchy:
    """測試 Exception 階層整體可捕捉性"""

    def test_catch_all_as_handoff_error(self):
        """所有具名 exception 都可被 HandoffError 捕捉"""
        exceptions_to_test = [
            HandoffTargetNotFoundError("X"),
            HandoffDuplicateError("X", "T"),
            HandoffSchemaError("P", ["f"]),
            HandoffDirectionUnknownError("D", "P"),
        ]
        for exc in exceptions_to_test:
            try:
                raise exc
            except HandoffError:
                pass  # 正確捕捉
            except Exception:
                pytest.fail(f"{type(exc).__name__} 未被 HandoffError 捕捉")

    def test_catch_all_as_exception(self):
        """所有具名 exception 都可被 Exception 捕捉"""
        exceptions_to_test = [
            HandoffError("base"),
            HandoffTargetNotFoundError("X"),
            HandoffDuplicateError("X", "T"),
            HandoffSchemaError("P", ["f"]),
            HandoffDirectionUnknownError("D", "P"),
        ]
        for exc in exceptions_to_test:
            try:
                raise exc
            except Exception:
                pass  # 正確捕捉
