"""validate 子命令測試。"""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from doc_system.commands.validate import execute
from doc_system.core.file_locator import FileLocator


PROJECT_ROOT = Path(__file__).resolve().parents[4]
REAL_DATA_CONTRACT = (
    PROJECT_ROOT
    / "docs"
    / "spec"
    / "balance-sheet"
    / "SPEC-002-accounts-snapshots-data-contract.md"
)


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
