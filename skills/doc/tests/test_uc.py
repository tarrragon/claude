"""uc 子命令群組測試 — list/verify/trace/context。"""

import argparse
import json
import subprocess
from unittest.mock import patch

import pytest

from doc_system.commands import uc
from doc_system.core.file_locator import FileLocator


def _setup_project(tmp_path, extra_files=None):
    """建立含 SSOT 的最小專案骨架，extra_files: {relative_path: content}。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "app-use-cases.md").write_text(
        "## UC-01: 匯入書庫\n內容\n\n## UC-02: 匯出書庫\n內容\n",
        encoding="utf-8",
    )

    if extra_files:
        for rel_path, content in extra_files.items():
            full = tmp_path / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")

    return str(tmp_path)


class TestUcList:
    def test_lists_valid_uc_with_titles(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path)
        args = argparse.Namespace(uc_command="list")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            uc.execute(args)

        output = capsys.readouterr().out
        assert "UC-01" in output
        assert "匯入書庫" in output
        assert "UC-02" in output

    def test_missing_ssot_prints_message(self, tmp_path, capsys):
        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            uc.execute(argparse.Namespace(uc_command="list"))

        output = capsys.readouterr().out
        assert "找不到" in output


class TestUcVerify:
    def test_pass_when_no_violation(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path,
            {"lib/book.dart": "// 實現 UC-01 匯入流程\nclass Book {}\n"},
        )
        args = argparse.Namespace(uc_command="verify", path=None)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 0
        assert "通過" in capsys.readouterr().out

    def test_violation_reports_file_line_token(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path,
            {"lib/ghost.dart": "// 引用 UC-99 不存在\n"},
        )
        args = argparse.Namespace(uc_command="verify", path=None)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr().out
        assert "lib/ghost.dart:1:UC-99" in output

    def test_worklog_path_exempt(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path,
            {"docs/work-logs/v1/ticket.md": "歷史誤用 UC-999\n"},
        )
        args = argparse.Namespace(uc_command="verify", path=None)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 0

    def test_pattern_token_exempt(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path,
            {"lib/pattern.dart": "// 套用 UC-Pattern-03 設計模式\n"},
        )
        args = argparse.Namespace(uc_command="verify", path=None)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 0

    def test_scoped_path_only_scans_target(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path,
            {
                "lib/good.dart": "// UC-01\n",
                "lib/other/bad.dart": "// UC-99\n",
            },
        )
        args = argparse.Namespace(uc_command="verify", path=f"{project_root}/lib/good.dart")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 0

    def test_nonexistent_path_exits_2(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path)
        args = argparse.Namespace(uc_command="verify", path=f"{project_root}/does/not/exist")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 2
        assert "不存在" in capsys.readouterr().err

    def test_empty_whitelist_exits_2_without_scanning_violations(self, tmp_path, capsys):
        # 無 SSOT 檔案 → get_valid_uc_map 回空 dict，應 fail-fast 而非印全違規清單
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "ghost.dart").write_text("// 引用 UC-99 不存在\n", encoding="utf-8")
        args = argparse.Namespace(uc_command="verify", path=None)

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 2
        err = capsys.readouterr().err
        assert "白名單" in err
        assert "UC-99" not in err


class TestUcTrace:
    def test_lists_reference_locations(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path,
            {"lib/book.dart": "// UC-01 匯入\nclass Book {}\n"},
        )
        args = argparse.Namespace(uc_command="trace", uc_id="UC-01")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            uc.execute(args)

        output = capsys.readouterr().out
        assert "lib/book.dart:1" in output

    def test_no_reference_prints_message(self, tmp_path, capsys):
        """SSOT 檔案自身（定義行）不計入引用，UC-02 未在任何其他檔案出現時應印出無引用訊息。"""
        project_root = _setup_project(tmp_path)
        args = argparse.Namespace(uc_command="trace", uc_id="UC-02")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            uc.execute(args)

        assert "無任何 code 引用" in capsys.readouterr().out

    def test_invalid_uc_id_exits_1(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path)
        args = argparse.Namespace(uc_command="trace", uc_id="UC-99")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 1

    def test_skips_non_utf8_files_without_crashing(self, tmp_path, capsys):
        """掃描到非 UTF-8 編碼檔案（如 binary/latin-1）時不應中斷，僅略過該檔。"""
        project_root = _setup_project(
            tmp_path,
            {"lib/good.dart": "// UC-01 匯入\n"},
        )
        (tmp_path / "lib" / "binary.dart").write_bytes(b"\xcd\x00 UC-01 \xff")
        args = argparse.Namespace(uc_command="trace", uc_id="UC-01")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            uc.execute(args)

        output = capsys.readouterr().out
        assert "lib/good.dart:1" in output


class TestUcContext:
    def test_direct_uc_id_outputs_spec_location_and_references(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path,
            {"lib/book.dart": "// UC-01 匯入流程\n"},
        )
        args = argparse.Namespace(uc_command="context", target="UC-01")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            uc.execute(args)

        output = capsys.readouterr().out
        assert "UC-01: 匯入書庫" in output
        assert "docs/app-use-cases.md:1" in output
        assert "lib/book.dart:1" in output

    def test_invalid_uc_id_exits_1(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path)
        args = argparse.Namespace(uc_command="context", target="UC-77")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit):
                uc.execute(args)

    def test_ticket_id_resolves_via_ticket_cli(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path)
        args = argparse.Namespace(uc_command="context", target="0.38.1-W1-064")

        fake_result = subprocess.CompletedProcess(
            args=["ticket"], returncode=0, stdout="what: 實作 UC-01 相關 CLI\n", stderr=""
        )

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with patch("doc_system.commands.uc.subprocess.run", return_value=fake_result):
                uc.execute(args)

        output = capsys.readouterr().out
        assert "UC-01: 匯入書庫" in output

    def test_ticket_id_no_uc_reference_exits_1(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path)
        args = argparse.Namespace(uc_command="context", target="0.38.1-W1-999")

        fake_result = subprocess.CompletedProcess(
            args=["ticket"], returncode=0, stdout="what: 無關內容\n", stderr=""
        )

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with patch("doc_system.commands.uc.subprocess.run", return_value=fake_result):
                with pytest.raises(SystemExit) as exc_info:
                    uc.execute(args)

        assert exc_info.value.code == 1


class TestUcSummary:
    def _setup_project_with_main_flow(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-01: 匯入書庫\n\n"
            "### 主要成功場景\n\n"
            "1. **選擇檔案**\n   - 細節\n\n"
            "2. **確認匯入**\n\n"
            "## UC-05: 無主流程用例\n\n"
            "### 其他章節\n內容\n",
            encoding="utf-8",
        )
        return str(tmp_path)

    def test_text_output_includes_title_location_and_steps(self, tmp_path, capsys):
        project_root = self._setup_project_with_main_flow(tmp_path)
        args = argparse.Namespace(uc_command="summary", uc_id="UC-01", json=False)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            uc.execute(args)

        output = capsys.readouterr().out
        assert "UC-01: 匯入書庫" in output
        assert "docs/app-use-cases.md:1" in output
        assert "1. **選擇檔案**" in output
        assert "2. **確認匯入**" in output

    def test_json_output_is_valid_json_with_expected_keys(self, tmp_path, capsys):
        project_root = self._setup_project_with_main_flow(tmp_path)
        args = argparse.Namespace(uc_command="summary", uc_id="UC-01", json=True)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            uc.execute(args)

        output = capsys.readouterr().out
        payload = json.loads(output)
        assert payload["uc_id"] == "UC-01"
        assert payload["title"] == "匯入書庫"
        assert payload["spec_path"] == "docs/app-use-cases.md"
        assert payload["spec_line"] == 1
        assert payload["main_flow"] == ["1. **選擇檔案**", "2. **確認匯入**"]

    def test_no_main_flow_falls_back_to_section_summary_label(self, tmp_path, capsys):
        """無「主要成功場景」時 CLI 印出章節摘要標籤而非空清單提示（W1-076 修復）。"""
        project_root = self._setup_project_with_main_flow(tmp_path)
        args = argparse.Namespace(uc_command="summary", uc_id="UC-05", json=False)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            uc.execute(args)

        output = capsys.readouterr().out
        assert "章節摘要（無「主要成功場景」，非主流程）:" in output
        assert "其他章節" in output

    def test_no_main_flow_and_no_section_headings_prints_placeholder_message(self, tmp_path, capsys):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "app-use-cases.md").write_text(
            "## UC-05: 完全空白用例\n\n內容，無任何 H3 標題\n",
            encoding="utf-8",
        )
        args = argparse.Namespace(uc_command="summary", uc_id="UC-05", json=False)

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            uc.execute(args)

        output = capsys.readouterr().out
        assert "（無主要流程步驟）" in output

    def test_nonexistent_uc_exits_1(self, tmp_path, capsys):
        project_root = self._setup_project_with_main_flow(tmp_path)
        args = argparse.Namespace(uc_command="summary", uc_id="UC-99", json=False)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 1
        assert "找不到" in capsys.readouterr().err


class TestExecuteWithoutSubcommand:
    def test_missing_subcommand_exits_1(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            uc.execute(argparse.Namespace(uc_command=None))

        assert exc_info.value.code == 1


class TestExecuteUnknownSubcommand:
    def test_unknown_subcommand_exits_2_with_message(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            uc.execute(argparse.Namespace(uc_command="bogus"))

        assert exc_info.value.code == 2
        err = capsys.readouterr().err
        assert "bogus" in err
        assert "list" in err


class TestUcVerifyTokenVariants:
    def test_lowercase_and_fullwidth_variants_detected_as_violation(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path,
            {"lib/ghost.dart": "// 引用 uc-99 與 ＵＣ－９９ 皆不存在\n"},
        )
        args = argparse.Namespace(uc_command="verify", path=None)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 1
        output = capsys.readouterr().out
        assert "UC-99" in output

    def test_uppercase_extension_scanned_case_insensitively(self, tmp_path, capsys):
        project_root = _setup_project(
            tmp_path,
            {"lib/Ghost.DART": "// 引用 UC-99 不存在\n"},
        )
        args = argparse.Namespace(uc_command="verify", path=None)

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc_info:
                uc.execute(args)

        assert exc_info.value.code == 1
