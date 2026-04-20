"""
W17-002.2 Context Bundle CLI wire-in 端到端測試。

驗收：
1. ticket create --source-ticket 自動抽取並寫入 Context Bundle
2. ticket track claim 後自動抽取（若尚未抽取）
3. --quiet / --verbose flag 影響 CLI 摘要輸出
4. 抽取異常降級不阻斷 create/claim（退出碼 0）
5. 二次 claim 幂等（同 sources 不重複寫入）
"""

from __future__ import annotations

import argparse
from unittest import mock

import pytest

from ticket_system.commands import create as create_cmd
from ticket_system.commands import lifecycle as lifecycle_cmd


# ============================================================================
# Fixtures
# ============================================================================


def _build_source_ticket(version: str, src_id: str, tmp_path) -> dict:
    """建立一個有 what/why/where.files/acceptance 的 source ticket."""
    return {
        "id": src_id,
        "version": version,
        "title": "Source ticket",
        "status": "pending",
        "what": "Source task description about feature X",
        "why": "Feature X needed for user requirement Y",
        "where": {"layer": "Domain", "files": ["src/featureX.py", "src/helper.py"]},
        "acceptance": ["[ ] feature X works", "[ ] tests pass"],
        "source_ticket": None,
        "blocked_by": None,
        "related_to": None,
        "_body": "## Task Summary\nSource body\n",
    }


def _build_target_ticket(version: str, tid: str, source_id: str) -> dict:
    return {
        "id": tid,
        "version": version,
        "title": "Target ticket",
        "status": "pending",
        "what": "Target task",
        "why": "Target rationale",
        "where": {"layer": "Application", "files": []},
        "acceptance": ["[ ] target works"],
        "source_ticket": source_id,
        "blocked_by": None,
        "related_to": None,
        "_body": "## Task Summary\nTarget body\n\n## Context Bundle\n\n（待自動填入）\n",
    }


# ============================================================================
# create.py wire-in 測試
# ============================================================================


class TestCreateWireIn:
    def test_post_create_helper_triggers_when_source_present(self, capsys):
        """create 後若 ticket 有 source_ticket → 呼叫 extract_and_write + 輸出摘要。"""
        with mock.patch(
            "ticket_system.lib.ticket_loader.load_ticket",
            return_value={
                "id": "0.18.0-W99-001",
                "source_ticket": "0.18.0-W99-000",
                "blocked_by": None,
                "related_to": None,
            },
        ), mock.patch(
            "ticket_system.lib.context_bundle_extractor.extract_and_write_context_bundle"
        ) as mock_extract, mock.patch(
            "ticket_system.lib.context_bundle_extractor.format_cli_summary",
            return_value="[Context Bundle] 已抽取（3 項，120 字元）",
        ):
            from ticket_system.lib.context_bundle_extractor import ExtractResult
            mock_extract.return_value = (
                ExtractResult(status="success", target_ticket_id="0.18.0-W99-001"),
                [],
            )
            create_cmd._auto_extract_context_bundle_post_create(
                "0.18.0", "0.18.0-W99-001", quiet=True
            )
        captured = capsys.readouterr()
        assert "[Context Bundle]" in captured.out
        mock_extract.assert_called_once_with("0.18.0", "0.18.0-W99-001")

    def test_post_create_skipped_when_no_sources(self, capsys):
        """ticket 無任何 source → 略過抽取（不呼叫 extract_and_write）。"""
        with mock.patch(
            "ticket_system.lib.ticket_loader.load_ticket",
            return_value={
                "id": "0.18.0-W99-001",
                "source_ticket": None,
                "blocked_by": None,
                "related_to": None,
            },
        ), mock.patch(
            "ticket_system.lib.context_bundle_extractor.extract_and_write_context_bundle"
        ) as mock_extract:
            create_cmd._auto_extract_context_bundle_post_create(
                "0.18.0", "0.18.0-W99-001"
            )
        mock_extract.assert_not_called()

    def test_post_create_exception_does_not_raise(self, capsys):
        """異常降級：extract 拋例外 → 寫 stderr，不 re-raise。"""
        with mock.patch(
            "ticket_system.lib.ticket_loader.load_ticket",
            return_value={
                "id": "0.18.0-W99-001",
                "source_ticket": "0.18.0-W99-000",
            },
        ), mock.patch(
            "ticket_system.lib.context_bundle_extractor.extract_and_write_context_bundle",
            side_effect=RuntimeError("simulated failure"),
        ):
            # 不應拋例外
            create_cmd._auto_extract_context_bundle_post_create(
                "0.18.0", "0.18.0-W99-001"
            )
        captured = capsys.readouterr()
        assert "抽取失敗" in captured.err

    def test_post_create_target_none_returns_silently(self, capsys):
        """target 不存在（load_ticket return None）→ 不呼叫 extract。"""
        with mock.patch(
            "ticket_system.lib.ticket_loader.load_ticket", return_value=None
        ), mock.patch(
            "ticket_system.lib.context_bundle_extractor.extract_and_write_context_bundle"
        ) as mock_extract:
            create_cmd._auto_extract_context_bundle_post_create(
                "0.18.0", "0.18.0-W99-001"
            )
        mock_extract.assert_not_called()

    def test_create_parser_has_quiet_verbose_flags(self):
        """create register 註冊 --quiet/--verbose flag。"""
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        create_cmd.register(sub)
        # 模擬解析必填參數 + --quiet
        args = parser.parse_args(
            ["create", "--action", "a", "--target", "t", "--quiet"]
        )
        assert args.quiet is True
        assert args.verbose is False

    def test_create_parser_has_json_flag(self):
        """W17-002.1 acceptance #7：create register 註冊 --json flag。"""
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        create_cmd.register(sub)
        args = parser.parse_args(
            ["create", "--action", "a", "--target", "t", "--json"]
        )
        assert args.json_output is True

    def test_post_create_json_output_prints_json(self, capsys):
        """--json flag → 輸出為合法 JSON 字串。"""
        from ticket_system.lib.context_bundle_extractor import ExtractResult

        with mock.patch(
            "ticket_system.lib.ticket_loader.load_ticket",
            return_value={
                "id": "0.18.0-W99-001",
                "source_ticket": "0.18.0-W99-000",
            },
        ), mock.patch(
            "ticket_system.lib.context_bundle_extractor.extract_and_write_context_bundle"
        ) as mock_extract:
            mock_extract.return_value = (
                ExtractResult(status="success", target_ticket_id="0.18.0-W99-001"),
                [],
            )
            create_cmd._auto_extract_context_bundle_post_create(
                "0.18.0", "0.18.0-W99-001", json_output=True
            )
        captured = capsys.readouterr()
        import json as _json

        payload = _json.loads(captured.out)
        assert payload["target_ticket_id"] == "0.18.0-W99-001"
        assert payload["status"] == "success"


# ============================================================================
# lifecycle.py execute_claim wire-in 測試
# ============================================================================


class TestClaimWireIn:
    def test_post_claim_helper_triggers_when_blocked_by_present(self, capsys):
        """claim 後若 ticket 有 blocked_by → 自動抽取。"""
        from ticket_system.lib.context_bundle_extractor import ExtractResult

        with mock.patch(
            "ticket_system.commands.lifecycle.load_ticket",
            return_value={
                "id": "0.18.0-W99-002",
                "source_ticket": None,
                "blocked_by": ["0.18.0-W99-001"],
                "related_to": None,
            },
        ), mock.patch(
            "ticket_system.lib.context_bundle_extractor.extract_and_write_context_bundle"
        ) as mock_extract, mock.patch(
            "ticket_system.lib.context_bundle_extractor.format_cli_summary",
            return_value="[Context Bundle] 已抽取",
        ):
            mock_extract.return_value = (
                ExtractResult(status="success", target_ticket_id="0.18.0-W99-002"),
                [],
            )
            lifecycle_cmd._auto_extract_context_bundle_post_claim(
                "0.18.0", "0.18.0-W99-002"
            )
        mock_extract.assert_called_once()
        captured = capsys.readouterr()
        assert "[Context Bundle]" in captured.out

    def test_post_claim_idempotent_on_second_call(self, capsys):
        """第二次 claim：若 merge 回傳 no_change_idempotent，仍輸出摘要但不重寫。

        我們只驗證 extract_and_write 被呼叫；幂等性由其內部 merge 保證（已在 extractor 測試覆蓋）。
        """
        from ticket_system.lib.context_bundle_extractor import ExtractResult

        with mock.patch(
            "ticket_system.commands.lifecycle.load_ticket",
            return_value={
                "id": "0.18.0-W99-002",
                "source_ticket": "0.18.0-W99-001",
            },
        ), mock.patch(
            "ticket_system.lib.context_bundle_extractor.extract_and_write_context_bundle"
        ) as mock_extract, mock.patch(
            "ticket_system.lib.context_bundle_extractor.format_cli_summary",
            return_value="[Context Bundle] idempotent",
        ):
            mock_extract.return_value = (
                ExtractResult(status="success", target_ticket_id="0.18.0-W99-002"),
                ["no_change_idempotent"],
            )
            lifecycle_cmd._auto_extract_context_bundle_post_claim(
                "0.18.0", "0.18.0-W99-002"
            )
            lifecycle_cmd._auto_extract_context_bundle_post_claim(
                "0.18.0", "0.18.0-W99-002"
            )
        assert mock_extract.call_count == 2

    def test_post_claim_skipped_when_no_sources(self):
        with mock.patch(
            "ticket_system.commands.lifecycle.load_ticket",
            return_value={
                "id": "0.18.0-W99-002",
                "source_ticket": None,
                "blocked_by": None,
                "related_to": None,
            },
        ), mock.patch(
            "ticket_system.lib.context_bundle_extractor.extract_and_write_context_bundle"
        ) as mock_extract:
            lifecycle_cmd._auto_extract_context_bundle_post_claim(
                "0.18.0", "0.18.0-W99-002"
            )
        mock_extract.assert_not_called()

    def test_post_claim_exception_does_not_raise(self, capsys):
        with mock.patch(
            "ticket_system.commands.lifecycle.load_ticket",
            return_value={"id": "0.18.0-W99-002", "source_ticket": "0.18.0-W99-001"},
        ), mock.patch(
            "ticket_system.lib.context_bundle_extractor.extract_and_write_context_bundle",
            side_effect=RuntimeError("boom"),
        ):
            lifecycle_cmd._auto_extract_context_bundle_post_claim(
                "0.18.0", "0.18.0-W99-002"
            )
        captured = capsys.readouterr()
        assert "抽取失敗" in captured.err

    def test_claim_parser_has_quiet_verbose_flags(self):
        """track claim register 註冊 --quiet/--verbose flag。"""
        from ticket_system.commands import track as track_cmd

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        track_cmd.register(sub)
        args = parser.parse_args(["track", "claim", "0.18.0-W99-001", "--verbose"])
        assert args.verbose is True
        assert args.quiet is False

    def test_claim_parser_has_json_flag(self):
        """W17-002.1 acceptance #7：track claim register 註冊 --json flag。"""
        from ticket_system.commands import track as track_cmd

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        track_cmd.register(sub)
        args = parser.parse_args(["track", "claim", "0.18.0-W99-001", "--json"])
        assert args.json_output is True
