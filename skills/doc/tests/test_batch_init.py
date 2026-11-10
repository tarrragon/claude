"""batch-init 子命令測試（W1-013：_get_proposal_info list-based 查找修復）。

Why: `_get_proposal_info` 舊實作以 `proposals.get(prop_id)` 將 proposals 當
dict-keyed-by-id 處理，但 PROPOSALS_TRACKING_SCHEMA SSOT 明定
`"proposals_format": "list"`，且 create.py 的 `_add_tracking_entry` 實際寫入
的即為 list-based 格式。對真實 tracking 檔呼叫一律 AttributeError
（'list' object has no attribute 'get'）。此缺陷在 doc create 模板打包修復後
才被實測揭露（先前 doc create proposal 本身即因模板路徑錯誤而失敗，
從未有機會產生可供 batch-init 消費的真實 tracking 檔）。
"""

import argparse
from pathlib import Path
from unittest.mock import patch

import yaml

from doc_system.commands.batch_init import _get_proposal_info, execute
from doc_system.commands.create import DOC_TYPE_CONFIG
from doc_system.core.file_locator import FileLocator


class TestGetProposalInfo:
    """_get_proposal_info 依 id 於 list-based proposals 中查找。"""

    def test_finds_entry_by_id_in_list(self):
        tracking = {
            "proposals": [
                {"id": "PROP-001", "title": "第一個提案", "status": "draft"},
                {"id": "PROP-002", "title": "第二個提案", "status": "confirmed"},
            ],
        }
        result = _get_proposal_info(tracking, "PROP-002")
        assert result == {"id": "PROP-002", "title": "第二個提案", "status": "confirmed"}

    def test_returns_none_when_id_not_found(self):
        tracking = {
            "proposals": [
                {"id": "PROP-001", "title": "第一個提案", "status": "draft"},
            ],
        }
        assert _get_proposal_info(tracking, "PROP-999") is None

    def test_returns_none_when_proposals_key_missing(self):
        assert _get_proposal_info({}, "PROP-001") is None

    def test_returns_none_when_proposals_empty_list(self):
        assert _get_proposal_info({"proposals": []}, "PROP-001") is None

    def test_does_not_raise_on_real_list_format_tracking_dict(self):
        """回歸測試：對 list-based tracking dict 呼叫不應 AttributeError（活 bug 修復）。"""
        tracking = {
            "proposals": [{"id": "PROP-001", "title": "x", "status": "draft"}],
            "usecases": [],
            "specs": [],
        }
        # 修復前：'list' object has no attribute 'get'
        result = _get_proposal_info(tracking, "PROP-001")
        assert result is not None


def _setup_project(tmp_path):
    """建立 batch-init 整合測試所需的基礎專案結構（含模板與 tracking 檔）。"""
    (tmp_path / "docs" / "spec").mkdir(parents=True)
    (tmp_path / "docs" / "usecases").mkdir(parents=True)

    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / DOC_TYPE_CONFIG["spec"]["template"]).write_text(
        '---\nid: SPEC-NNN\ntitle: "{規格標題}"\nstatus: draft\n'
        'created: "YYYY-MM-DD"\n---\n# SPEC-{NNN}\n'
    )
    (templates_dir / DOC_TYPE_CONFIG["usecase"]["template"]).write_text(
        '---\nid: UC-XX\ntitle: "{用例名稱}"\nstatus: draft\n'
        'created: "YYYY-MM-DD"\nupdated: "YYYY-MM-DD"\n---\n# UC-{XX}\n'
    )

    tracking_file = tmp_path / "docs" / "proposals-tracking.yaml"
    tracking_file.write_text(
        yaml.dump(
            {
                "proposals": [
                    {"id": "PROP-001", "title": "批次初始化測試提案", "status": "confirmed"},
                ],
                "usecases": [],
                "specs": [],
            },
            allow_unicode=True,
            sort_keys=False,
        )
    )
    return str(tmp_path), templates_dir


class TestBatchInitExecute:
    """execute() 端到端整合測試：對真實 list-based tracking 檔運作正常。"""

    def test_execute_creates_spec_and_uc_for_list_based_tracking(self, tmp_path, capsys):
        project_root, templates_dir = _setup_project(tmp_path)

        args = argparse.Namespace(proposals="PROP-001", domain=None)

        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
        ):
            execute(args)

        output = capsys.readouterr().out
        assert "PROP-001" in output
        assert "SKIP" not in output

        spec_files = list((tmp_path / "docs" / "spec").glob("SPEC-*.md"))
        uc_files = list((tmp_path / "docs" / "usecases").glob("UC-*.md"))
        assert len(spec_files) == 1
        assert len(uc_files) == 1

        traceability = tmp_path / "docs" / "traceability.yaml"
        assert traceability.is_file()
        data = yaml.safe_load(traceability.read_text())
        assert len(data["mappings"]) == 1
        assert data["mappings"][0]["title"] == "批次初始化測試提案"

    def test_execute_skips_unknown_proposal_id(self, tmp_path, capsys):
        """proposal id 不在 tracking 中時應 SKIP 而非 crash。"""
        project_root, templates_dir = _setup_project(tmp_path)

        args = argparse.Namespace(proposals="PROP-999", domain=None)

        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
        ):
            execute(args)

        output = capsys.readouterr().out
        assert "[SKIP] PROP-999" in output


class TestBatchInitSharesAllocator:
    """batch-init 與 doc create 呼叫同一個配號函式（3.1.0-W1-033）。"""

    def test_uses_create_next_id_and_has_no_private_allocator(self):
        from doc_system.commands import batch_init, create

        assert batch_init._next_id is create._next_id
        assert not hasattr(batch_init, "_next_spec_id")
        assert not hasattr(batch_init, "_next_uc_id")

    def test_three_digit_uc_corpus_continues_three_digits(self, tmp_path, capsys):
        """舊實作對 UC 寫死兩位，既有 UC-005 時會配出 UC-06；共用配號後配 UC-006。"""
        project_root, templates_dir = _setup_project(tmp_path)
        (tmp_path / "docs" / "usecases" / "UC-005-seed.md").write_text("---\nid: UC-005\n---\n")
        (tmp_path / "docs" / "spec" / "SPEC-012-seed.md").write_text("---\nid: SPEC-012\n---\n")

        with (
            patch.object(FileLocator, "get_project_root", return_value=project_root),
            patch("doc_system.commands.create._get_templates_dir", return_value=templates_dir),
        ):
            execute(argparse.Namespace(proposals="PROP-001", domain=None))
        capsys.readouterr()

        uc_names = sorted(p.name for p in (tmp_path / "docs" / "usecases").iterdir())
        spec_names = sorted(p.name for p in (tmp_path / "docs" / "spec").iterdir())
        assert [n for n in uc_names if not n.startswith("UC-005")][0].startswith("UC-006-")
        assert [n for n in spec_names if not n.startswith("SPEC-012")][0].startswith("SPEC-013-")
