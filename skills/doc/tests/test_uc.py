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


class TestUcVerifyInlineExemptAndNoDigit:
    """uc verify 端到端：行內標記與無數字 token 放行。"""

    def test_marker_line_exempt_exit_0(self, tmp_path):
        root = _setup_project(tmp_path, {"lib/a.dart": "// UC-99 uc-verify-exempt: 示例\n"})
        assert _run_verify(root, str(tmp_path / "lib")) == 0

    def test_marker_absent_exit_1(self, tmp_path):
        root = _setup_project(tmp_path, {"lib/a.dart": "// UC-99\n"})
        assert _run_verify(root, str(tmp_path / "lib")) == 1

    def test_blank_reason_exit_1(self, tmp_path):
        root = _setup_project(tmp_path, {"lib/a.dart": "// UC-99 uc-verify-exempt:   \n"})
        assert _run_verify(root, str(tmp_path / "lib")) == 1

    def test_marker_on_other_line_exit_1(self, tmp_path):
        root = _setup_project(tmp_path, {"lib/a.dart": "// uc-verify-exempt: 說明\n// UC-99\n"})
        assert _run_verify(root, str(tmp_path / "lib")) == 1

    def test_no_digit_token_exit_0(self, tmp_path):
        root = _setup_project(tmp_path, {"lib/a.dart": "// UC-A 與 UC-X 為占位\n"})
        assert _run_verify(root, str(tmp_path / "lib")) == 0

    def test_digit_token_still_exit_1(self, tmp_path):
        root = _setup_project(tmp_path, {"lib/a.dart": "// UC-A1\n"})
        assert _run_verify(root, str(tmp_path / "lib")) == 1


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


# ---------------------------------------------------------------------------
# code root 分離（3.5.0-W1-151.1.8.1）
# ---------------------------------------------------------------------------
def _external_project(tmp_path, cfg=True):
    ws = tmp_path / "ws"
    repo = tmp_path / "repo"
    _setup_project(ws)
    (repo / "lib").mkdir(parents=True)
    (repo / "lib" / "bad.dart").write_text("// UC-99 違規\n// UC-01 ok\n", encoding="utf-8")
    if cfg:
        (ws / "docs" / "traceability.yaml").write_text(f"code_root: {repo}\n")
    return ws, repo


def _patch_external(monkeypatch):
    monkeypatch.setattr("doc_system.core.file_locator.is_external_mode", lambda *a, **k: True)


class TestUcExternalCodeRoot:
    def test_verify_no_path_scans_code_root(self, tmp_path, capsys, monkeypatch):
        """不帶路徑時掃到 code root 的違規（原本假陰性只印通過）。"""
        ws, _ = _external_project(tmp_path)
        _patch_external(monkeypatch)
        args = argparse.Namespace(uc_command="verify", path=None, code_root=None)
        with patch.object(FileLocator, "get_project_root", return_value=str(ws)):
            with pytest.raises(SystemExit) as exc:
                uc.execute(args)
        out = capsys.readouterr().out
        assert exc.value.code == 1
        assert "repo:lib/bad.dart:1:UC-99" in out
        assert "../" not in out

    def test_verify_external_without_code_root_exits_nonzero(self, tmp_path, capsys, monkeypatch):
        ws, _ = _external_project(tmp_path, cfg=False)
        _patch_external(monkeypatch)
        args = argparse.Namespace(uc_command="verify", path=None, code_root=None)
        with patch.object(FileLocator, "get_project_root", return_value=str(ws)):
            with pytest.raises(SystemExit) as exc:
                uc.execute(args)
        assert exc.value.code not in (0, 1)
        assert "code_root" in capsys.readouterr().err

    def test_verify_explicit_path_external_without_code_root_exits_nonzero(
        self, tmp_path, capsys, monkeypatch
    ):
        """正向對照：外接、帶明示 path、無 code_root 無旗標，仍 exit 2；帶旗標則放行。"""
        ws, repo = _external_project(tmp_path, cfg=False)
        _patch_external(monkeypatch)
        target = str(repo / "lib")
        args = argparse.Namespace(uc_command="verify", path=target, code_root=None)
        with patch.object(FileLocator, "get_project_root", return_value=str(ws)):
            with pytest.raises(SystemExit) as exc:
                uc.execute(args)
        assert exc.value.code == 2
        assert "code_root" in capsys.readouterr().err

        args = argparse.Namespace(uc_command="verify", path=target, code_root=str(repo))
        with patch.object(FileLocator, "get_project_root", return_value=str(ws)):
            with pytest.raises(SystemExit) as exc:
                uc.execute(args)
        assert exc.value.code == 1

    def test_verify_zero_files_scanned_not_a_pass(self, tmp_path, capsys):
        """無可掃檔案時不得印通過。"""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "app-use-cases.md").write_text("## UC-01: a\n")
        empty = tmp_path / "code"
        empty.mkdir()
        (tmp_path / "docs" / "traceability.yaml").write_text(f"code_root: {empty}\n")
        args = argparse.Namespace(uc_command="verify", path=None, code_root=None)
        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc:
                uc.execute(args)
        assert exc.value.code == 2
        assert "通過" not in capsys.readouterr().out

    def test_verify_pass_message_reports_scan_count(self, tmp_path, capsys):
        project_root = _setup_project(tmp_path, {"lib/a.dart": "// UC-01\n"})
        args = argparse.Namespace(uc_command="verify", path=None, code_root=None)
        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc:
                uc.execute(args)
        assert exc.value.code == 0
        assert "個檔案" in capsys.readouterr().out

    def test_trace_scans_code_root_with_prefix(self, tmp_path, capsys, monkeypatch):
        ws, _ = _external_project(tmp_path)
        _patch_external(monkeypatch)
        args = argparse.Namespace(uc_command="trace", uc_id="UC-01", code_root=None, all=False, limit=None)
        with patch.object(FileLocator, "get_project_root", return_value=str(ws)):
            uc.execute(args)
        assert "repo:lib/bad.dart:2" in capsys.readouterr().out

    def test_trace_external_without_code_root_exits_nonzero(self, tmp_path, capsys, monkeypatch):
        ws, _ = _external_project(tmp_path, cfg=False)
        _patch_external(monkeypatch)
        args = argparse.Namespace(uc_command="trace", uc_id="UC-01", code_root=None, all=False, limit=None)
        with patch.object(FileLocator, "get_project_root", return_value=str(ws)):
            with pytest.raises(SystemExit) as exc:
                uc.execute(args)
        assert exc.value.code != 0


# ---------------------------------------------------------------------------
# 豁免判定修正（136 worktree 鏡射、137 相對路徑基準、C2 雙根清單）
# ---------------------------------------------------------------------------
def _run_verify(project_root, path):
    args = argparse.Namespace(uc_command="verify", path=path, code_root=None)
    with patch.object(FileLocator, "get_project_root", return_value=project_root):
        with pytest.raises(SystemExit) as exc:
            uc.execute(args)
    return exc.value.code


class TestUcVerifyRelativePathBase:
    """137：相對路徑以 cwd 為基準，判定與實際讀取的檔案一致。"""

    def test_cwd_app_fixtures_not_exempt(self, tmp_path, monkeypatch):
        root = _setup_project(tmp_path, {"app/test/fixtures/x.dart": "// UC-99\n"})
        monkeypatch.chdir(tmp_path / "app")
        assert _run_verify(root, "test/fixtures") == 1

    def test_cwd_docs_spec_exempt(self, tmp_path, monkeypatch):
        root = _setup_project(tmp_path, {"docs/spec/a.md": "UC-99\n"})
        monkeypatch.chdir(tmp_path / "docs")
        assert _run_verify(root, "spec") == 0

    def test_cwd_docs_sibling_non_exempt_dir_exit_1(self, tmp_path, monkeypatch):
        """正向對照：cwd=docs，同層非豁免目錄含 UC-99 仍 exit 1。"""
        root = _setup_project(tmp_path, {"docs/other/a.md": "UC-99\n"})
        monkeypatch.chdir(tmp_path / "docs")
        assert _run_verify(root, "other") == 1

    def test_cwd_root_fixtures_exempt(self, tmp_path, monkeypatch):
        root = _setup_project(tmp_path, {"test/fixtures/x.dart": "// UC-99\n"})
        monkeypatch.chdir(tmp_path)
        assert _run_verify(root, "test/fixtures") == 0


class TestUcVerifyWorktreeMirror:
    """136：worktree 下產品檔受檢，框架資產仍豁免。"""

    def test_worktree_product_file_with_undefined_uc_exit_1(self, tmp_path, monkeypatch):
        root = _setup_project(tmp_path, {".claude/worktrees/w1/lib/a.dart": "// UC-99\n"})
        monkeypatch.chdir(tmp_path)
        assert _run_verify(root, ".claude/worktrees/w1/lib") == 1

    def test_worktree_framework_asset_exempt(self, tmp_path, monkeypatch):
        root = _setup_project(tmp_path, {".claude/worktrees/w1/.claude/hooks/x.py": "# UC-99\n"})
        monkeypatch.chdir(tmp_path)
        assert _run_verify(root, ".claude/worktrees/w1/.claude/hooks") == 0


class TestUcVerifyExternalDualRoot:
    """C2：外接模式交叉案例不豁免，各自根內的豁免保留。"""

    def _run(self, tmp_path, monkeypatch, ws_files, repo_files, explicit=None):
        ws, repo = _external_project(tmp_path)
        (repo / "lib" / "bad.dart").write_text("// UC-01\n", encoding="utf-8")
        for base, files in ((ws, ws_files), (repo, repo_files)):
            for rel, content in files.items():
                f = base / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(content, encoding="utf-8")
        _patch_external(monkeypatch)
        return _run_verify(str(ws), str(tmp_path / explicit) if explicit else None)

    def test_doc_root_fixtures_violation_exit_1(self, tmp_path, monkeypatch):
        assert self._run(tmp_path, monkeypatch, {"test/fixtures/x.dart": "// UC-99\n"}, {}) == 1

    def test_code_root_claude_dir_explicit_path_violation_exit_1(self, tmp_path, monkeypatch):
        """隱藏目錄不在遞迴掃描內，以明示檔案路徑驗證 code root 底下 .claude/ 不豁免。"""
        assert self._run(tmp_path, monkeypatch, {}, {".claude/a.md": "UC-99\n"}, explicit="repo/.claude/a.md") == 1

    @pytest.mark.parametrize("rel", ["docs/spec/a.md", "docs/work-logs/a.md"])
    def test_code_root_doc_prefix_violation_exit_1(self, tmp_path, monkeypatch, rel):
        assert self._run(tmp_path, monkeypatch, {}, {rel: "UC-99\n"}) == 1

    def test_code_root_fixtures_exempt(self, tmp_path, monkeypatch):
        assert self._run(tmp_path, monkeypatch, {}, {"test/fixtures/x.dart": "// UC-99\n"}) == 0

    def test_doc_root_spec_exempt(self, tmp_path, monkeypatch):
        assert self._run(tmp_path, monkeypatch, {"docs/spec/a.md": "UC-99\n"}, {}) == 0
