"""PROP-009 清單式欄位驗證測試。

測試 _validate_create_checklist 函式的各種場景。
"""

import pytest

from ticket_system.commands.create import _validate_create_checklist
from ticket_system.lib.constants import DEFAULT_UNDEFINED_VALUE


def _build_complete_config():
    """建立一個所有欄位都填寫的完整 config。"""
    return {
        "where_files": ["src/core/foo.js"],
        "acceptance": ["功能正常運作"],
        "decision_tree_path": {
            "entry_point": "接收任務",
            "final_decision": "派發 thyme",
            "rationale": "Python 檔案修改",
        },
        "when": "v0.17.4",
        "parent_id": None,
    }


class TestValidateCreateChecklist:
    """_validate_create_checklist 測試群組。"""

    def test_all_fields_present_no_missing(self):
        """全部填寫，回傳空 list。"""
        config = _build_complete_config()
        result = _validate_create_checklist(config, "IMP")
        assert result == []

    def test_missing_where_files(self):
        """where_files 為空，回傳 ["where.files"]。"""
        config = _build_complete_config()
        config["where_files"] = []
        result = _validate_create_checklist(config, "IMP")
        assert "where.files" in result

    def test_missing_where_files_none(self):
        """where_files 為 None，回傳 ["where.files"]。"""
        config = _build_complete_config()
        config["where_files"] = None
        result = _validate_create_checklist(config, "IMP")
        assert "where.files" in result

    def test_missing_acceptance(self):
        """acceptance 為 None，回傳 ["acceptance"]。"""
        config = _build_complete_config()
        config["acceptance"] = None
        result = _validate_create_checklist(config, "IMP")
        assert "acceptance" in result

    def test_missing_acceptance_empty_list(self):
        """acceptance 為空 list，回傳 ["acceptance"]。"""
        config = _build_complete_config()
        config["acceptance"] = []
        result = _validate_create_checklist(config, "IMP")
        assert "acceptance" in result

    def test_missing_decision_tree_path_none(self):
        """decision_tree_path 為 None，回傳 ["decision_tree_path"]。"""
        config = _build_complete_config()
        config["decision_tree_path"] = None
        result = _validate_create_checklist(config, "IMP")
        assert "decision_tree_path" in result

    def test_missing_decision_tree_path_partial(self):
        """decision_tree_path 子欄位不完整，回傳 ["decision_tree_path"]。"""
        config = _build_complete_config()
        config["decision_tree_path"] = {
            "entry_point": "接收任務",
            "final_decision": "",
            "rationale": "理由",
        }
        result = _validate_create_checklist(config, "IMP")
        assert "decision_tree_path" in result

    def test_missing_when(self):
        """when 為「待定義」，回傳 ["when"]。"""
        config = _build_complete_config()
        config["when"] = DEFAULT_UNDEFINED_VALUE
        result = _validate_create_checklist(config, "IMP")
        assert "when" in result

    def test_multiple_missing(self):
        """多個欄位缺失，全部列出。"""
        config = {
            "where_files": [],
            "acceptance": None,
            "decision_tree_path": None,
            "when": DEFAULT_UNDEFINED_VALUE,
            "parent_id": None,
        }
        result = _validate_create_checklist(config, "IMP")
        assert "where.files" in result
        assert "acceptance" in result
        assert "decision_tree_path" in result
        assert "when" in result
        assert len(result) == 4

    def test_doc_type_skips_decision_tree(self):
        """DOC 類型不檢查 decision_tree_path。"""
        config = _build_complete_config()
        config["decision_tree_path"] = None
        result = _validate_create_checklist(config, "DOC")
        assert "decision_tree_path" not in result

    def test_child_ticket_skips_decision_tree(self):
        """有 parent_id 的子任務不檢查 decision_tree_path。"""
        config = _build_complete_config()
        config["decision_tree_path"] = None
        config["parent_id"] = "0.17.4-W1-001"
        result = _validate_create_checklist(config, "IMP")
        assert "decision_tree_path" not in result
