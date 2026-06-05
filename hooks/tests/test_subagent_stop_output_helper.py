"""Tests for build_subagent_stop_output version-aware helper (0.19.1-W1-046).

驗證 hook_utils.hook_io 中 SubagentStop additionalContext 輸出與版本相容
graceful fallback 的行為：
- CC >= 2.1.163 -> hookSpecificOutput.additionalContext
- CC <  2.1.163 -> top-level systemMessage（降級）
- 版本偵測失敗 -> 樂觀預設使用 additionalContext

策略：直接 import 套件模組，monkeypatch get_claude_code_version 控制版本分支。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hook_utils import hook_io  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_version_cache():
    """每個測試重置進程內版本快取，避免互相污染。"""
    hook_io._cc_version_cache = None
    hook_io._cc_version_resolved = False
    yield
    hook_io._cc_version_cache = None
    hook_io._cc_version_resolved = False


class TestParseVersionTuple:

    def test_parses_standard_output(self):
        assert hook_io._parse_version_tuple("2.1.163 (Claude Code)") == (2, 1, 163)

    def test_parses_bare_version(self):
        assert hook_io._parse_version_tuple("3.0.0") == (3, 0, 0)

    def test_returns_none_on_garbage(self):
        assert hook_io._parse_version_tuple("not a version") is None

    def test_returns_none_on_empty(self):
        assert hook_io._parse_version_tuple("") is None


class TestSupportsAdditionalContext:

    def test_supported_at_min_version(self, monkeypatch):
        monkeypatch.setattr(hook_io, "get_claude_code_version", lambda logger=None: (2, 1, 163))
        assert hook_io.supports_subagent_stop_additional_context() is True

    def test_supported_above_min_version(self, monkeypatch):
        monkeypatch.setattr(hook_io, "get_claude_code_version", lambda logger=None: (2, 2, 0))
        assert hook_io.supports_subagent_stop_additional_context() is True

    def test_unsupported_below_min_version(self, monkeypatch):
        monkeypatch.setattr(hook_io, "get_claude_code_version", lambda logger=None: (2, 1, 162))
        assert hook_io.supports_subagent_stop_additional_context() is False

    def test_optimistic_default_when_detection_fails(self, monkeypatch):
        monkeypatch.setattr(hook_io, "get_claude_code_version", lambda logger=None: None)
        assert hook_io.supports_subagent_stop_additional_context() is True


class TestBuildSubagentStopOutput:

    def test_additional_context_shape_when_supported(self, monkeypatch):
        monkeypatch.setattr(
            hook_io, "supports_subagent_stop_additional_context", lambda logger=None: True
        )
        out = hook_io.build_subagent_stop_output("hello")
        assert out == {
            "hookSpecificOutput": {
                "hookEventName": "SubagentStop",
                "additionalContext": "hello",
            }
        }

    def test_system_message_fallback_when_unsupported(self, monkeypatch):
        monkeypatch.setattr(
            hook_io, "supports_subagent_stop_additional_context", lambda logger=None: False
        )
        out = hook_io.build_subagent_stop_output("hello")
        assert out == {"systemMessage": "hello"}
