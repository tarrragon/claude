"""
test_messages_format_error
==========================

驗證 W17-008.5.2 強化後的 format_error 雙路徑行為：

- Legacy str template 路徑（向後相容）
- 結構化 ErrorEnvelope 路徑
- isinstance 分發與型別錯誤處理

Source: ticket 0.18.0-W17-008.5.2
"""
import pytest

from ticket_system.lib.messages import (
    ERROR_ENVELOPE_VERSION_MARKER,
    ErrorEnvelope,
    ErrorMessages,
    format_error,
)


# ---------------------------------------------------------------------------
# Legacy str template 路徑（向後相容測試）
# ---------------------------------------------------------------------------


class TestLegacyStrTemplatePath:
    """確保 W17-008.5.2 升級不影響既有 ErrorMessages.X.format(...) 呼叫。"""

    def test_ticket_not_found_with_kwargs(self):
        """既有最常見呼叫：含參數的 template。"""
        result = format_error(ErrorMessages.TICKET_NOT_FOUND, ticket_id="0.31.0-W4-001")
        assert result == "[Error] 找不到 Ticket 0.31.0-W4-001"

    def test_invalid_ticket_id_no_kwargs(self):
        """無參數 template 也正常運作。"""
        result = format_error(ErrorMessages.INVALID_TICKET_ID)
        assert result == "[Error] Ticket ID 格式無效"

    def test_field_not_found_multi_kwargs(self):
        """多參數 template。"""
        result = format_error(
            ErrorMessages.FIELD_NOT_FOUND,
            ticket_id="0.31.0-W4-001",
            field_name="who",
        )
        assert "0.31.0-W4-001" in result
        assert "who" in result
        assert result.startswith("[Error]")

    def test_missing_kwargs_raises_keyerror(self):
        """str 路徑缺參數仍應拋 KeyError（既有契約）。"""
        with pytest.raises(KeyError):
            format_error(ErrorMessages.TICKET_NOT_FOUND)


# ---------------------------------------------------------------------------
# 結構化 ErrorEnvelope 路徑（W17-008.5.2 新增）
# ---------------------------------------------------------------------------


class TestStructuredEnvelopePath:
    """驗證 ErrorEnvelope 渲染含版本標記與四欄位。"""

    def test_envelope_full_fields(self):
        """完整四欄位（含 hint）渲染。"""
        env = ErrorEnvelope(
            component="track",
            action="claim",
            errno="TICKET_NOT_FOUND",
            hint="執行 ticket track list 確認可用 ID",
        )
        result = format_error(env)

        # 必含版本標記（hook 偵測錨點）
        assert ERROR_ENVELOPE_VERSION_MARKER in result
        # 必含四欄位
        assert "component: track" in result
        assert "action: claim" in result
        assert "errno: TICKET_NOT_FOUND" in result
        assert "hint: 執行 ticket track list 確認可用 ID" in result
        # 必含 [Error] 前綴
        assert result.startswith("[Error]")

    def test_envelope_without_hint(self):
        """hint 為 None 時不應出現 hint: 欄位。"""
        env = ErrorEnvelope(
            component="lifecycle",
            action="complete",
            errno="ACCEPTANCE_NOT_MET",
        )
        result = format_error(env)

        assert ERROR_ENVELOPE_VERSION_MARKER in result
        assert "component: lifecycle" in result
        assert "action: complete" in result
        assert "errno: ACCEPTANCE_NOT_MET" in result
        assert "hint:" not in result

    def test_envelope_is_frozen(self):
        """ErrorEnvelope 應為 frozen dataclass，避免意外突變。"""
        env = ErrorEnvelope(component="x", action="y", errno="Z")
        with pytest.raises(Exception):
            env.component = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 分發與錯誤處理
# ---------------------------------------------------------------------------


class TestDispatchAndErrors:
    """驗證 isinstance 分發與型別防護。"""

    def test_invalid_type_raises_typeerror(self):
        """既非 str 也非 ErrorEnvelope 應拋 TypeError。"""
        with pytest.raises(TypeError, match="format_error"):
            format_error(123)  # type: ignore[arg-type]

    def test_envelope_path_ignores_kwargs(self):
        """envelope 路徑下傳入 kwargs 不應影響輸出（不會拋錯，純粹忽略）。"""
        env = ErrorEnvelope(component="c", action="a", errno="E")
        result = format_error(env, ticket_id="ignored")
        assert "ignored" not in result
        assert "errno: E" in result
