"""validate 子命令測試。"""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system.commands.validate import execute, execute_filenames
from doc_system.core.file_locator import FileLocator


PROJECT_ROOT = Path(__file__).resolve().parents[4]
REAL_DATA_CONTRACT = (
    PROJECT_ROOT
    / "docs"
    / "spec"
    / "balance-sheet"
    / "SPEC-002-accounts-snapshots-data-contract.md"
)


def _violations_section(output: str) -> str:
    """從 execute_filenames 輸出中取出「驗證失敗」區段（排除 INFO 豁免清單）。"""
    marker = "驗證失敗"
    idx = output.find(marker)
    return output[idx:] if idx != -1 else ""


def _setup_spec(tmp_path, spec_id, subdomain, body):
    """建立最小 spec md 檔於 tmp_path/docs/spec/{domain}/{spec_id}-x.md。"""
    spec_dir = tmp_path / "docs" / "spec" / "demo"
    spec_dir.mkdir(parents=True)
    md = spec_dir / f"{spec_id}-x.md"
    frontmatter = f"---\nid: {spec_id}\ntitle: \"Test\"\nsubdomain: {subdomain}\n---\n"
    md.write_text(frontmatter + body, encoding="utf-8")
    return str(tmp_path)


FULL_DATA_CONTRACT_BODY = """
## 可攜性邊界原則

內容

## A 區：邏輯契約（DB-agnostic）

### A.1 表/欄位語意
內容
### A.2 狀態責任分層
內容
### A.3 不變式清單
內容
### A.4 交易邊界
內容
### A.5 錯誤語意契約
內容
### A.6 恢復模型
內容

## B 區：實作綁定（DB-specific）

### B.1 保證層歸屬
內容
### B.2 邊界行為的引擎機制
內容
### B.3 Schema 演進策略與 Seed 資料政策
內容

## 適用判準（本文件是否需要撰寫）

| 旗標 | 判定 | 理由 |
|------|------|------|
| 契約文件 | 要 | 理由 |
| migration 治理 | **不要** | 理由 |
"""


class TestValidateDataContract:
    def test_full_schema_passes(self, tmp_path, capsys):
        """章節齊全且旗標已填時應通過（exit 0）。"""
        project_root = _setup_spec(tmp_path, "SPEC-100", "data-contract", FULL_DATA_CONTRACT_BODY)
        args = argparse.Namespace(doc_id="SPEC-100")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc:
                execute(args)

        assert exc.value.code == 0
        assert "通過" in capsys.readouterr().out

    def test_missing_sections_exit_1(self, tmp_path, capsys):
        """人工構造缺章節樣本應回報缺失並 exit 1。"""
        body = """
## 可攜性邊界原則
內容

### A.1 表/欄位語意
內容
"""
        project_root = _setup_spec(tmp_path, "SPEC-101", "data-contract", body)
        args = argparse.Namespace(doc_id="SPEC-101")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc:
                execute(args)

        assert exc.value.code == 1
        output = capsys.readouterr().out
        assert "A.2" in output
        assert "B.1" in output
        assert "適用判準" in output

    def test_empty_flag_reported(self, tmp_path, capsys):
        """適用判準節存在但旗標判定欄留白（模板佔位符）時應回報。"""
        body = FULL_DATA_CONTRACT_BODY.replace(
            "| 契約文件 | 要 | 理由 |", "| 契約文件 | {要/不要} | 理由 |"
        )
        project_root = _setup_spec(tmp_path, "SPEC-102", "data-contract", body)
        args = argparse.Namespace(doc_id="SPEC-102")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc:
                execute(args)

        assert exc.value.code == 1
        assert "契約文件" in capsys.readouterr().out

    def test_non_data_contract_routes_message(self, tmp_path, capsys):
        """非 data-contract 文件應明確路由至 /spec validate，不誤報。"""
        project_root = _setup_spec(tmp_path, "SPEC-103", "null", "## 概述\n內容\n")
        args = argparse.Namespace(doc_id="SPEC-103")

        with patch.object(FileLocator, "get_project_root", return_value=project_root):
            with pytest.raises(SystemExit) as exc:
                execute(args)

        assert exc.value.code == 0
        assert "/spec validate" in capsys.readouterr().out

    def test_nonexistent_doc_exit_2(self, tmp_path, capsys):
        """文件不存在時 exit 2。"""
        (tmp_path / "docs" / "spec").mkdir(parents=True)
        args = argparse.Namespace(doc_id="SPEC-999")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc:
                execute(args)

        assert exc.value.code == 2
        assert "找不到文件" in capsys.readouterr().out

    def test_unparsable_frontmatter_exit_2(self, tmp_path, capsys):
        """frontmatter 無法解析時 exit 2。"""
        spec_dir = tmp_path / "docs" / "spec" / "demo"
        spec_dir.mkdir(parents=True)
        (spec_dir / "SPEC-104-x.md").write_text("no frontmatter here\n", encoding="utf-8")
        args = argparse.Namespace(doc_id="SPEC-104")

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc:
                execute(args)

        assert exc.value.code == 2
        assert "無法解析" in capsys.readouterr().out

    @pytest.mark.skipif(
        not REAL_DATA_CONTRACT.is_file(), reason="專案實際 data-contract 文件不存在"
    )
    def test_real_project_data_contract_passes(self, capsys):
        """對本專案實際 data-contract 文件（SPEC-002）驗證應通過。"""
        args = argparse.Namespace(doc_id="SPEC-002")

        with patch.object(FileLocator, "get_project_root", return_value=str(PROJECT_ROOT)):
            with pytest.raises(SystemExit) as exc:
                execute(args)

        assert exc.value.code == 0
        assert "通過" in capsys.readouterr().out


class TestValidateFilenames:
    """檔名慣例驗證（配號器盲區防護，0.2.1-W3-006）。"""

    def test_nonconforming_filename_reported(self, tmp_path, capsys):
        """不符 {PREFIX}-數字 慣例的檔名應被列出。"""
        spec_dir = tmp_path / "docs" / "spec" / "demo"
        spec_dir.mkdir(parents=True)
        (spec_dir / "資料契約-v2.md").write_text(
            "---\nid: SPEC-200\ntitle: \"Test\"\n---\n內容\n", encoding="utf-8"
        )
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc:
                execute_filenames(args)

        assert exc.value.code == 1
        output = capsys.readouterr().out
        assert "配號器盲區" in output
        assert "資料契約-v2.md" in output

    def test_conforming_filename_not_reported(self, tmp_path, capsys):
        """符合慣例且 frontmatter id 一致的檔名不應誤報。"""
        spec_dir = tmp_path / "docs" / "spec" / "demo"
        spec_dir.mkdir(parents=True)
        (spec_dir / "SPEC-201-x.md").write_text(
            "---\nid: SPEC-201\ntitle: \"Test\"\n---\n內容\n", encoding="utf-8"
        )
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc:
                execute_filenames(args)

        assert exc.value.code == 0
        assert "通過" in capsys.readouterr().out

    def test_frontmatter_id_mismatch_reported(self, tmp_path, capsys):
        """檔名前綴 ID 與 frontmatter id 不一致時應回報。"""
        spec_dir = tmp_path / "docs" / "spec" / "demo"
        spec_dir.mkdir(parents=True)
        (spec_dir / "SPEC-202-x.md").write_text(
            "---\nid: SPEC-999\ntitle: \"Test\"\n---\n內容\n", encoding="utf-8"
        )
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc:
                execute_filenames(args)

        assert exc.value.code == 1
        output = capsys.readouterr().out
        assert "frontmatter id 與檔名不一致" in output
        assert "SPEC-202" in output

    def test_template_file_excluded(self, tmp_path, capsys):
        """template 檔名（-template.md）不受檔名慣例約束，不應誤報。"""
        proposal_dir = tmp_path / "docs" / "proposals"
        proposal_dir.mkdir(parents=True)
        (proposal_dir / "proposal-template.md").write_text(
            "---\nid: PLACEHOLDER\n---\n內容\n", encoding="utf-8"
        )
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc:
                execute_filenames(args)

        assert exc.value.code == 0

    def test_spec_and_data_contract_share_dedup_scan(self, tmp_path, capsys):
        """spec 與 data-contract 共用 docs/spec + SPEC 前綴，掃描不應重複回報同一檔案。"""
        spec_dir = tmp_path / "docs" / "spec" / "demo"
        spec_dir.mkdir(parents=True)
        (spec_dir / "not-conforming.md").write_text(
            "---\nid: SPEC-300\n---\n內容\n", encoding="utf-8"
        )
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc:
                execute_filenames(args)

        assert exc.value.code == 1
        output = capsys.readouterr().out
        assert output.count("not-conforming.md") == 1

    def test_fixed_name_file_exempted_and_reported_as_info(self, tmp_path, capsys):
        """框架約定固定命名文件（有對應 template）不報違規，且以 INFO 顯性列出。"""
        spec_dir = tmp_path / "docs" / "spec"
        spec_dir.mkdir(parents=True)
        (spec_dir / "design-system-spec.md").write_text(
            "---\nid: N/A\ntitle: \"Design System\"\n---\n內容\n", encoding="utf-8"
        )
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=str(tmp_path)):
            with pytest.raises(SystemExit) as exc:
                execute_filenames(args)

        output = capsys.readouterr().out
        assert exc.value.code == 0
        assert "INFO" in output
        assert "design-system-spec.md" in output
        assert "配號器盲區" not in output

    def test_real_project_fixed_name_files_not_violations(self, capsys):
        """本專案實際的 component-library-spec.md / design-system-spec.md 不應被列為違規。"""
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=str(PROJECT_ROOT)):
            with pytest.raises(SystemExit) as exc:
                execute_filenames(args)

        output = capsys.readouterr().out
        assert "component-library-spec.md" not in _violations_section(output)
        assert "design-system-spec.md" not in _violations_section(output)

    def test_real_project_scan_executes(self, capsys):
        """對本專案實際文件目錄執行應可完成掃描（不驗證結果為 0，因既有檔案可能
        存在歷史遺留違規，見 0.2.1-W3-006 Solution 記錄的實際發現）。"""
        args = argparse.Namespace()

        with patch.object(FileLocator, "get_project_root", return_value=str(PROJECT_ROOT)):
            with pytest.raises(SystemExit) as exc:
                execute_filenames(args)

        assert exc.value.code in (0, 1)
