"""PROP-009 清單式欄位驗證測試。

測試 _validate_create_checklist 函式的各種場景。
"""

import pytest

from ticket_system.commands.create import (
    _enforce_create_checklist,
    _validate_create_checklist,
)
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
        "who": "thyme-python-developer",
        "what": "升級驗證為阻擋",
        "why": "規格不完整導致下游派發失敗",
        "how_strategy": "改 sys.exit(1) 並加 --force",
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
        """多個欄位缺失，全部列出（W11-003.5 升級後含 5W1H 全欄位）。"""
        config = {
            "where_files": [],
            "acceptance": None,
            "decision_tree_path": None,
            "when": DEFAULT_UNDEFINED_VALUE,
            "parent_id": None,
            "who": "pending",
            "what": "",
            "why": DEFAULT_UNDEFINED_VALUE,
            "how_strategy": DEFAULT_UNDEFINED_VALUE,
        }
        result = _validate_create_checklist(config, "IMP")
        # 原 4 項
        assert "where.files" in result
        assert "acceptance" in result
        assert "decision_tree_path" in result
        assert "when" in result
        # W11-003.5 新增 4 項
        assert "who" in result
        assert "what" in result
        assert "why" in result
        assert "how_strategy" in result
        assert len(result) == 8

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

    # ===== W11-003.5: 5W1H 全欄位必填擴充 =====

    def test_missing_who_pending(self):
        """who 為 'pending' 視為缺失。"""
        config = _build_complete_config()
        config["who"] = "pending"
        result = _validate_create_checklist(config, "IMP")
        assert "who" in result

    def test_missing_who_undefined(self):
        """who 為「待定義」視為缺失。"""
        config = _build_complete_config()
        config["who"] = DEFAULT_UNDEFINED_VALUE
        result = _validate_create_checklist(config, "IMP")
        assert "who" in result

    def test_missing_who_empty(self):
        """who 為空字串視為缺失。"""
        config = _build_complete_config()
        config["who"] = ""
        result = _validate_create_checklist(config, "IMP")
        assert "who" in result

    def test_missing_why(self):
        """why 為「待定義」視為缺失（IMP 類型）。"""
        config = _build_complete_config()
        config["why"] = DEFAULT_UNDEFINED_VALUE
        result = _validate_create_checklist(config, "IMP")
        assert "why" in result

    def test_doc_type_skips_why(self):
        """DOC 類型豁免 why 檢查。"""
        config = _build_complete_config()
        config["why"] = DEFAULT_UNDEFINED_VALUE
        result = _validate_create_checklist(config, "DOC")
        assert "why" not in result

    def test_missing_how_strategy(self):
        """how_strategy 為「待定義」視為缺失。"""
        config = _build_complete_config()
        config["how_strategy"] = DEFAULT_UNDEFINED_VALUE
        result = _validate_create_checklist(config, "IMP")
        assert "how_strategy" in result

    def test_missing_what(self):
        """what 為空視為缺失。"""
        config = _build_complete_config()
        config["what"] = ""
        result = _validate_create_checklist(config, "IMP")
        assert "what" in result


class TestEnforceCreateChecklistForce:
    """_enforce_create_checklist 的 --force 豁免分支測試（1.0.0-W1-038）。

    背景：1.0.0-W1-024.1 將 why 從「不可豁免」改為「可由 --force 豁免」（刻意決策），
    但既有測試全部 force=False，豁免路徑零覆蓋。本群組補上 force=True 分支，
    確保「缺 why + --force」不阻擋建立（不呼叫 sys.exit），且印出 WARNING。
    """

    def test_no_missing_returns_without_action(self, capsys):
        """無缺失欄位 → 直接 return，不阻擋也不印 WARNING。"""
        _enforce_create_checklist([], force=False)
        out = capsys.readouterr().out
        assert "已 --force 跳過阻擋" not in out
        assert "CHECKLIST_VALIDATION_FAILED" not in out

    def test_missing_why_without_force_blocks(self):
        """缺 why + 未 --force → 阻擋建立（sys.exit(1)）。"""
        with pytest.raises(SystemExit) as exc_info:
            _enforce_create_checklist(["why"], force=False)
        assert exc_info.value.code == 1

    def test_missing_why_with_force_allows(self, capsys):
        """缺 why + --force → 放行（不 raise SystemExit），印 WARNING 並列出 why。

        驗證 1.0.0-W1-024.1 的 --force why 豁免語意：why 可由 --force 跳過阻擋。
        """
        # 不應 raise SystemExit
        _enforce_create_checklist(["why"], force=True)
        out = capsys.readouterr().out
        assert "已 --force 跳過阻擋" in out
        assert "why" in out
        # 豁免路徑不應輸出阻擋用的錯誤 errno
        assert "CHECKLIST_VALIDATION_FAILED" not in out

    def test_multiple_missing_with_force_allows(self, capsys):
        """多欄位缺失（含 why）+ --force → 放行並列出所有缺失欄位。"""
        _enforce_create_checklist(["when", "why", "how_strategy"], force=True)
        out = capsys.readouterr().out
        assert "已 --force 跳過阻擋" in out
        assert "why" in out
        assert "when" in out
        assert "how_strategy" in out
