#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dispatch-record-hook 測試套件（0.2.1-W3-302 / multi-PM 協調層 Phase 1）

背景：派發身份綁定（who.current）已遷移至 dispatch-identity-bind-hook.py
（PostToolUse:Agent，見 test_dispatch_identity_bind_hook.py）。本 hook
（PreToolUse:Agent）僅負責記錄派發資訊到 dispatch-active.json，不涉及任何
ticket CLI 寫入（who/set-who）。

multi-PM 協調層 Phase 1 為 dispatch-active.json 補上 session_id /
ticket_id / files 欄位。其中 ticket_id 由本檔的 extract_ticket_id() 以
正則從 prompt/description 純文字擷取（不查詢 ticket CLI、不做任何
寫入），與舊架構「識別 ticket_id 後呼叫 who/set-who CLI 綁定身份」的
職責邊界不同——同名函式曾因舊架構被移除，此處是為新（不同語意的）用途
重新引入，故不違反 0.2.1-W3-302 的移除意圖。registry 契約 v2 審查後另
移除 parent_session_id（恆等 session_id 的冗餘欄位，資訊量為零）。

測試覆蓋：
- main() 基本流程：subagent 環境跳過 / 無 input 跳過 / 正常記錄
- record_dispatch 呼叫參數（isolation 對應 branch_name；新增 session_id /
  ticket_id / files）
- record_dispatch 失敗不阻擋派發
- tool_use_id 缺失時使用 fallback 識別符
- extract_ticket_id：prompt 優先、缺則 description 補、皆無回 None
- resolve_session_id：stdin 優先、缺則環境變數 fallback
- 身份綁定邏輯（who.current CLI 呼叫）仍完全不存在於本 hook
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 動態載入（檔名含 dash）
hooks_path = Path(__file__).parent.parent
hook_file = hooks_path / "dispatch-record-hook.py"
spec = importlib.util.spec_from_file_location("dispatch_record_hook", hook_file)
dispatch_record_hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch_record_hook)

EXIT_SUCCESS = dispatch_record_hook.EXIT_SUCCESS


class TestIdentityBindingRemoved:
    """0.2.1-W3-302：who.current 身份綁定（含其 ticket CLI 呼叫）不應存在於本 hook。

    extract_ticket_id 不在此列——multi-PM 協調層 Phase 1 為填 dispatch-active.json
    的 ticket_id 欄位重新引入同名函式，但語意是純正則文字擷取，不觸發任何
    ticket CLI 呼叫，見 TestExtractTicketId。
    """

    def test_no_bind_dispatch_identity_function(self):
        assert not hasattr(dispatch_record_hook, "bind_dispatch_identity")

    def test_no_parse_who_value_function(self):
        assert not hasattr(dispatch_record_hook, "parse_who_value")


class TestExtractTicketId:
    """multi-PM 協調層 Phase 1：ticket_id 由 prompt 首行提取（與 dispatch-identity-bind-hook.py
    一致），缺則從 description 全文搜尋補（0.2.1-W3-557 修正全文搜尋誤配對）。"""

    def test_extracts_from_prompt_first_line(self):
        result = dispatch_record_hook.extract_ticket_id(
            "0.2.1-W3-547 依規格實作", "unused-description"
        )
        assert result == "0.2.1-W3-547"

    def test_falls_back_to_description(self):
        result = dispatch_record_hook.extract_ticket_id(
            "no id in prompt text", "0.2.1-W3-547（hooks 職責）"
        )
        assert result == "0.2.1-W3-547"

    def test_prompt_takes_priority_over_description(self):
        result = dispatch_record_hook.extract_ticket_id(
            "0.2.1-W3-100 in prompt", "0.2.1-W3-200 in description"
        )
        assert result == "0.2.1-W3-100"

    def test_neither_returns_none(self):
        result = dispatch_record_hook.extract_ticket_id("nothing here", "nor here")
        assert result is None

    def test_multiline_prompt_ignores_id_on_later_line(self):
        """首行無 ID、後續行提及其他票 ID 時，不誤配後續行的 ID（改回 None，
        非把後續行的無關票當成派發目標）。"""
        prompt = (
            "接手該票並依規格實作。\n"
            "先讀取 ticket 的 Problem Analysis 節，內含依先前結論收尾用的"
            "其他票 0.2.1-W3-100 事實修正說明。"
        )
        result = dispatch_record_hook.extract_ticket_id(prompt, "")
        assert result is None

    def test_multiline_prompt_falls_back_to_description_when_first_line_has_no_id(self):
        """全文搜尋誤配對修正：prompt 首行無 ID，內文提及相關票時不誤配，
        正確改採 description 補位取得真正的派發目標。"""
        prompt = (
            "接手該票並依規格實作。\n"
            "先讀取 ticket 的 Problem Analysis 節，內含依先前結論收尾用的"
            "其他票 0.2.1-W3-100 事實修正說明。"
        )
        result = dispatch_record_hook.extract_ticket_id(prompt, "0.2.1-W3-547（hooks 職責）")
        assert result == "0.2.1-W3-547"

    def test_multiline_prompt_uses_first_line_even_when_later_line_has_id(self):
        """首行有 ID 時優先採首行，不受後續行內容影響。"""
        prompt = (
            "0.2.1-W3-547 依規格實作。\n"
            "背景：先前 0.2.1-W3-100 已定案採此路線。"
        )
        result = dispatch_record_hook.extract_ticket_id(prompt, "unused")
        assert result == "0.2.1-W3-547"

    def test_first_line_extraction_ignores_id_in_second_line_of_multiline_prompt(self):
        """僅首行納入 prompt 比對範圍：第二行才出現的 ID 不會被當成首行結果誤取。"""
        prompt = "沒有 ID 的第一行\n0.2.1-W3-999 在第二行"
        result = dispatch_record_hook.extract_ticket_id(prompt, "")
        assert result is None

    def test_empty_strings_return_none(self):
        assert dispatch_record_hook.extract_ticket_id("", "") is None


class TestResolveSessionId:
    """multi-PM 協調層 Phase 1：優先 stdin session_id，缺則環境變數 fallback。"""

    def test_prefers_stdin_session_id(self, monkeypatch):
        monkeypatch.setenv(dispatch_record_hook.ENV_SESSION_ID, "env-session")
        result = dispatch_record_hook.resolve_session_id({"session_id": "stdin-session"})
        assert result == "stdin-session"

    def test_falls_back_to_env_var(self, monkeypatch):
        monkeypatch.setenv(dispatch_record_hook.ENV_SESSION_ID, "env-session")
        result = dispatch_record_hook.resolve_session_id({})
        assert result == "env-session"

    def test_none_input_falls_back_to_env_var(self, monkeypatch):
        monkeypatch.setenv(dispatch_record_hook.ENV_SESSION_ID, "env-session")
        result = dispatch_record_hook.resolve_session_id(None)
        assert result == "env-session"

    def test_missing_both_returns_empty_string(self, monkeypatch):
        monkeypatch.delenv(dispatch_record_hook.ENV_SESSION_ID, raising=False)
        result = dispatch_record_hook.resolve_session_id({})
        assert result == ""


class TestMainBasicFlow:
    """main() 基本流程：跳過條件與正常記錄路徑"""

    def _run_main(self, input_data, tool_input=None):
        with patch.object(
            dispatch_record_hook, "setup_hook_logging"
        ) as mock_log, patch.object(
            dispatch_record_hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            dispatch_record_hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            dispatch_record_hook, "extract_tool_input"
        ) as mock_input, patch.object(
            dispatch_record_hook, "get_project_root"
        ) as mock_root, patch.object(
            dispatch_record_hook, "extract_where_files"
        ) as mock_where_files, patch.object(
            dispatch_record_hook, "record_dispatch"
        ) as mock_record:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = input_data
            mock_sub.return_value = bool(input_data) and input_data.get(
                "_subagent", False
            )
            mock_input.return_value = tool_input or {}
            mock_root.return_value = Path(".")
            mock_where_files.return_value = []

            result = dispatch_record_hook.main()

        return result, mock_record

    def test_subagent_environment_skips_recording(self):
        result, mock_record = self._run_main({"_subagent": True})
        assert result == EXIT_SUCCESS
        mock_record.assert_not_called()

    def test_no_input_data_skips_recording(self):
        result, mock_record = self._run_main(None)
        assert result == EXIT_SUCCESS
        mock_record.assert_not_called()

    def test_normal_dispatch_records(self):
        result, mock_record = self._run_main(
            {"tool_use_id": "toolu_01"},
            tool_input={"description": "測試派發", "isolation": ""},
        )
        assert result == EXIT_SUCCESS
        mock_record.assert_called_once()
        kwargs = mock_record.call_args.kwargs
        assert kwargs["agent_description"] == "測試派發"
        assert kwargs["tool_use_id"] == "toolu_01"
        assert kwargs["branch_name"] == ""

    def test_worktree_isolation_sets_branch_name(self):
        result, mock_record = self._run_main(
            {"tool_use_id": "toolu_02"},
            tool_input={"description": "worktree 派發", "isolation": "worktree"},
        )
        assert result == EXIT_SUCCESS
        kwargs = mock_record.call_args.kwargs
        assert kwargs["branch_name"] == "worktree"

    def test_missing_tool_use_id_uses_fallback(self):
        # input_data 需為非空 dict（main() 對空 dict 走 no-input 提前跳過），
        # 僅 tool_use_id 缺失
        result, mock_record = self._run_main(
            {"other_field": "x"}, tool_input={"description": "無 tool_use_id 派發"}
        )
        assert result == EXIT_SUCCESS
        kwargs = mock_record.call_args.kwargs
        assert kwargs["tool_use_id"].startswith("unknown_")

    def test_record_dispatch_failure_does_not_block(self):
        with patch.object(
            dispatch_record_hook, "setup_hook_logging"
        ) as mock_log, patch.object(
            dispatch_record_hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            dispatch_record_hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            dispatch_record_hook, "extract_tool_input"
        ) as mock_input, patch.object(
            dispatch_record_hook, "get_project_root"
        ) as mock_root, patch.object(
            dispatch_record_hook,
            "record_dispatch",
            side_effect=RuntimeError("boom"),
        ):
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"tool_use_id": "toolu_03"}
            mock_sub.return_value = False
            mock_input.return_value = {"description": "失敗派發"}
            mock_root.return_value = Path(".")

            assert dispatch_record_hook.main() == EXIT_SUCCESS

    def test_session_and_ticket_fields_threaded_through(self, monkeypatch):
        """multi-PM 協調層：session_id/ticket_id/files 皆傳入 record_dispatch
        （parent_session_id 已於 registry 契約 v2 審查後移除，恆等 session_id
        的冗餘欄位）。"""
        monkeypatch.delenv(dispatch_record_hook.ENV_SESSION_ID, raising=False)
        with patch.object(
            dispatch_record_hook, "setup_hook_logging"
        ) as mock_log, patch.object(
            dispatch_record_hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            dispatch_record_hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            dispatch_record_hook, "extract_tool_input"
        ) as mock_input, patch.object(
            dispatch_record_hook, "get_project_root"
        ) as mock_root, patch.object(
            dispatch_record_hook, "extract_where_files"
        ) as mock_where_files, patch.object(
            dispatch_record_hook, "record_dispatch"
        ) as mock_record:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {
                "tool_use_id": "toolu_04",
                "session_id": "pm-session-abc",
            }
            mock_sub.return_value = False
            mock_input.return_value = {
                "description": "0.2.1-W3-547（hooks 職責）",
                "prompt": "實作 ticket 0.2.1-W3-547",
                "isolation": "",
            }
            mock_root.return_value = Path(".")
            mock_where_files.return_value = [".claude/hooks/"]

            result = dispatch_record_hook.main()

        assert result == EXIT_SUCCESS
        kwargs = mock_record.call_args.kwargs
        assert kwargs["session_id"] == "pm-session-abc"
        assert "parent_session_id" not in kwargs
        assert kwargs["ticket_id"] == "0.2.1-W3-547"
        assert kwargs["files"] == [".claude/hooks/"]

    def test_no_ticket_id_skips_where_files_lookup(self):
        """無法解析 Ticket ID 時不查表，files 為空清單。"""
        with patch.object(
            dispatch_record_hook, "setup_hook_logging"
        ) as mock_log, patch.object(
            dispatch_record_hook, "read_json_from_stdin"
        ) as mock_stdin, patch.object(
            dispatch_record_hook, "is_subagent_environment"
        ) as mock_sub, patch.object(
            dispatch_record_hook, "extract_tool_input"
        ) as mock_input, patch.object(
            dispatch_record_hook, "get_project_root"
        ) as mock_root, patch.object(
            dispatch_record_hook, "extract_where_files"
        ) as mock_where_files, patch.object(
            dispatch_record_hook, "record_dispatch"
        ) as mock_record:
            mock_log.return_value = MagicMock()
            mock_stdin.return_value = {"tool_use_id": "toolu_05"}
            mock_sub.return_value = False
            mock_input.return_value = {
                "description": "無 ticket id 派發",
                "prompt": "沒有 id",
                "isolation": "",
            }
            mock_root.return_value = Path(".")

            result = dispatch_record_hook.main()

        assert result == EXIT_SUCCESS
        mock_where_files.assert_not_called()
        kwargs = mock_record.call_args.kwargs
        assert kwargs["ticket_id"] == ""
        assert kwargs["files"] == []
