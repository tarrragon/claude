#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lib.hook_logging.resolve_session_id 測試（DRY 下沉，0.2.1-W3-560）

背景：session-registry-*-hook.py（4 支）與 dispatch-record-hook.py 曾各自
逐字重複定義 resolve_session_id（優先 stdin session_id，缺則環境變數
fallback），本測試收斂原本分散在各 hook 測試檔的 TestResolveSessionId
類別，改為對 lib 單一定義測一次。

涵蓋：
- stdin 優先於環境變數
- stdin 缺失時 fallback 環境變數
- input_data 為 None 時 fallback 環境變數
- stdin 與環境變數皆無時回傳空字串（非 UNKNOWN_SESSION_ID，與
  _current_session_id() 的哨兵值語意刻意不同，見函式 docstring）
"""

from lib import hook_logging


class TestResolveSessionId:
    def test_prefers_stdin_session_id(self, monkeypatch):
        monkeypatch.setenv(hook_logging.ENV_SESSION_ID, "env-session")
        result = hook_logging.resolve_session_id({"session_id": "stdin-session"})
        assert result == "stdin-session"

    def test_falls_back_to_env_var_when_stdin_missing_key(self, monkeypatch):
        monkeypatch.setenv(hook_logging.ENV_SESSION_ID, "env-session")
        result = hook_logging.resolve_session_id({})
        assert result == "env-session"

    def test_none_input_falls_back_to_env_var(self, monkeypatch):
        monkeypatch.setenv(hook_logging.ENV_SESSION_ID, "env-session")
        result = hook_logging.resolve_session_id(None)
        assert result == "env-session"

    def test_missing_both_returns_empty_string(self, monkeypatch):
        monkeypatch.delenv(hook_logging.ENV_SESSION_ID, raising=False)
        result = hook_logging.resolve_session_id({})
        assert result == ""

    def test_empty_stdin_session_id_falls_back_to_env_var(self, monkeypatch):
        """stdin 含 session_id 鍵但值為空字串時，視同缺失，改採環境變數。"""
        monkeypatch.setenv(hook_logging.ENV_SESSION_ID, "env-session")
        result = hook_logging.resolve_session_id({"session_id": ""})
        assert result == "env-session"

    def test_differs_from_current_session_id_default_when_unset(self, monkeypatch):
        """行為快照：resolve_session_id 缺值回傳空字串，_current_session_id()
        缺值回傳 UNKNOWN_SESSION_ID 哨兵值——兩者刻意不同（見兩函式
        docstring），此測試釘住此差異不被未來重構默默抹平。"""
        monkeypatch.delenv(hook_logging.ENV_SESSION_ID, raising=False)
        assert hook_logging.resolve_session_id(None) == ""
        assert hook_logging._current_session_id() == hook_logging.UNKNOWN_SESSION_ID
