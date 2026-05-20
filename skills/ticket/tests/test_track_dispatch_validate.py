"""測試 ticket track dispatch-validate 命令（0.18.0-W17-003）。

涵蓋 5 項合理性檢查規則 + exit code 對應：
- 規則 1（欄位非空，硬性）→ 違反時 exit 2
- 規則 2（內容長度 >= 50）→ 違反時 exit 1
- 規則 3（where.files 檔案存在）→ 違反時 exit 1
- 規則 4（acceptance >= 3 項）→ 違反時 exit 1
- 規則 5（LLM 審查）→ 本 ticket 範圍外，預留不測試
- ticket 不存在 / IO 錯誤 → exit 2
"""

from __future__ import annotations

import argparse
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

import pytest

from ticket_system.commands.track_dispatch_validate import (
    check_acceptance_count,
    check_content_length,
    check_section_present,
    check_where_files_exist,
    execute_dispatch_validate,
)


# ---------------------------------------------------------------------------
# 純函式單元測試（不需 ticket fixture）
# ---------------------------------------------------------------------------


class TestRule1SectionPresent:
    def test_missing_section_fails(self):
        ok, _msg = check_section_present("# Title\n\n## Other\n\ncontent")
        assert ok is False

    def test_empty_section_fails(self):
        body = "## Context Bundle\n\n   \n\n## Next\n"
        ok, _ = check_section_present(body)
        assert ok is False

    def test_non_empty_section_passes(self):
        body = "## Context Bundle\n\n背景說明。\n\n## Next\n"
        ok, _ = check_section_present(body)
        assert ok is True


class TestSectionMatchCacheReuse:
    """W17-212 AC: 規則 1+2 共用 find_section 結果（cache 不重複解析）。"""

    def test_passing_precomputed_match_avoids_reparse(self):
        from ticket_system.lib.section_locator import find_section

        body = "## Context Bundle\n\n" + ("x" * 60) + "\n\n## Next\n"
        cached = find_section(body, "Context Bundle")
        # 傳入 cached match，函式應產出與重新解析一致的結果
        ok1, _ = check_section_present(body, match=cached)
        ok2, _ = check_content_length(body, match=cached)
        assert ok1 is True
        assert ok2 is True


class TestRule2ContentLength:
    def test_short_content_fails(self):
        body = "## Context Bundle\n\n短\n\n## Next\n"
        ok, _ = check_content_length(body)
        assert ok is False

    def test_long_content_passes(self):
        body = "## Context Bundle\n\n" + ("x" * 60) + "\n\n## Next\n"
        ok, _ = check_content_length(body)
        assert ok is True

    def test_missing_section_treated_as_fail(self):
        ok, _ = check_content_length("no section here")
        assert ok is False


class TestRule3WhereFilesExist:
    def test_empty_list_passes(self, tmp_path):
        ok, _ = check_where_files_exist([], project_root=tmp_path)
        assert ok is True

    def test_missing_file_fails(self, tmp_path):
        ok, msg = check_where_files_exist(
            ["nonexistent/file.py"], project_root=tmp_path
        )
        assert ok is False
        assert "nonexistent/file.py" in msg

    def test_existing_file_passes(self, tmp_path):
        (tmp_path / "real.py").write_text("x")
        ok, _ = check_where_files_exist(["real.py"], project_root=tmp_path)
        assert ok is True


class TestRule4AcceptanceCount:
    def test_fewer_than_three_fails(self):
        ok, _ = check_acceptance_count(["a", "b"])
        assert ok is False

    def test_exactly_three_passes(self):
        ok, _ = check_acceptance_count(["a", "b", "c"])
        assert ok is True

    def test_none_treated_as_zero(self):
        ok, _ = check_acceptance_count(None)
        assert ok is False


# ---------------------------------------------------------------------------
# CLI 入口整合測試（mock load_ticket / get_project_root）
# ---------------------------------------------------------------------------


def _args(ticket_id: str = "0.18.0-W17-003") -> argparse.Namespace:
    return argparse.Namespace(
        operation="dispatch-validate",
        ticket_id=ticket_id,
        version=None,
    )


def _run(ticket_dict, *, project_root: Path | None = None) -> tuple[int, str, str]:
    pr = project_root or Path("/tmp")
    out, err = io.StringIO(), io.StringIO()
    with patch(
        "ticket_system.lib.dispatch_common.load_ticket",
        return_value=ticket_dict,
    ), patch(
        "ticket_system.commands.track_dispatch_validate.get_project_root",
        return_value=pr,
    ), redirect_stdout(out), redirect_stderr(err):
        rc = execute_dispatch_validate(_args(), "0.18.0")
    return rc, out.getvalue(), err.getvalue()


class TestExecuteDispatchValidate:
    def test_ticket_not_found_returns_2(self):
        rc, _out, err = _run(None)
        assert rc == 2
        assert "不存在" in err

    def test_yaml_error_returns_2(self):
        rc, _out, err = _run({"_yaml_error": "bad yaml"})
        assert rc == 2
        assert "YAML" in err

    def test_missing_context_bundle_returns_2(self):
        ticket = {
            "_body": "## Problem Analysis\n\n內容\n",
            "acceptance": ["a", "b", "c"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket)
        assert rc == 2
        assert "規則 1" in out

    def test_all_rules_pass_returns_0(self, tmp_path):
        (tmp_path / "src.py").write_text("x")
        ticket = {
            "_body": "## Context Bundle\n\n" + ("a" * 100) + "\n\n## Next\n",
            "acceptance": ["a", "b", "c", "d"],
            "where": {"files": ["src.py"]},
        }
        rc, out, _err = _run(ticket, project_root=tmp_path)
        assert rc == 0
        assert "全部規則通過" in out

    def test_short_content_returns_1(self, tmp_path):
        ticket = {
            "_body": "## Context Bundle\n\n短內容\n\n## Next\n",
            "acceptance": ["a", "b", "c"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket, project_root=tmp_path)
        assert rc == 1
        assert "規則 2" in out

    def test_missing_file_returns_1(self, tmp_path):
        ticket = {
            "_body": "## Context Bundle\n\n" + ("a" * 100) + "\n",
            "acceptance": ["a", "b", "c"],
            "where": {"files": ["missing.py"]},
        }
        rc, _out, _err = _run(ticket, project_root=tmp_path)
        assert rc == 1

    def test_empty_where_files_emits_info_hint(self, tmp_path):
        """W17-212 AC: where.files 為空時 stdout 應含 [INFO] 提示。"""
        ticket = {
            "_body": "## Context Bundle\n\n" + ("a" * 100) + "\n",
            "acceptance": ["a", "b", "c"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket, project_root=tmp_path)
        assert rc == 0
        assert "[INFO] where.files 為空" in out

    def test_non_empty_where_files_no_info_hint(self, tmp_path):
        """W17-212 AC: where.files 非空時不應印 [INFO] 提示。"""
        (tmp_path / "src.py").write_text("x")
        ticket = {
            "_body": "## Context Bundle\n\n" + ("a" * 100) + "\n",
            "acceptance": ["a", "b", "c"],
            "where": {"files": ["src.py"]},
        }
        rc, out, _err = _run(ticket, project_root=tmp_path)
        assert rc == 0
        assert "[INFO] where.files 為空" not in out

    def test_few_acceptance_returns_1(self, tmp_path):
        ticket = {
            "_body": "## Context Bundle\n\n" + ("a" * 100) + "\n",
            "acceptance": ["only-one"],
            "where": {"files": []},
        }
        rc, out, _err = _run(ticket, project_root=tmp_path)
        assert rc == 1
        assert "規則 4" in out
