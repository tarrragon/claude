"""
SPEC 引用驗證機制單元測試（0.4.1-W2-001）

測試建票時掃描 SPEC-NNN 引用、對照 traceability.yaml 已登錄編號、
未登錄即輸出警告（不阻擋建立）的完整鏈路。

動機：F1（SPEC-008 誤植跨票傳染，0.4.1-W1-001 → 0.4.1-W2-004）。
"""
from pathlib import Path

import pytest
import yaml

from ticket_system.lib.spec_reference_checker import (
    extract_spec_references,
    load_registered_spec_ids,
    registries_uninitialized,
    detect_unregistered_spec_references,
)
from ticket_system.lib.command_lifecycle_messages import CreateMessages


def _write_proposals_tracking(tmp_path: Path, spec_ids) -> Path:
    """在 tmp_path/docs/proposals-tracking.yaml 寫入 specs: 區段測試 fixture。"""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    data = {"specs": [{"id": spec_id} for spec_id in spec_ids]}
    path = docs_dir / "proposals-tracking.yaml"
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ============================================================
# 測試 extract_spec_references
# ============================================================

class TestExtractSpecReferences:
    """extract_spec_references 函式測試"""

    def test_single_reference(self):
        """場景 1：單一 SPEC 引用"""
        assert extract_spec_references("依 SPEC-008 實作") == ["SPEC-008"]

    def test_multiple_references_dedup_and_order(self):
        """場景 2：多個引用去重並保留出現順序"""
        text = "對照 SPEC-002 和 SPEC-013，另補 SPEC-002 交叉引用"
        assert extract_spec_references(text) == ["SPEC-002", "SPEC-013"]

    def test_no_reference(self):
        """場景 3：文字中無 SPEC 引用"""
        assert extract_spec_references("純文字，無引用") == []

    def test_empty_string(self):
        """場景 4：空字串回傳空清單"""
        assert extract_spec_references("") == []

    def test_none_input(self):
        """場景 5：None 輸入不拋例外，回傳空清單"""
        assert extract_spec_references(None) == []

    def test_non_string_input(self):
        """場景 6：非字串輸入不拋例外，回傳空清單"""
        assert extract_spec_references(12345) == []

    def test_multi_digit_spec_number(self):
        """場景 7：三位數以上編號不被截斷"""
        assert extract_spec_references("見 SPEC-1234") == ["SPEC-1234"]


# ============================================================
# 測試 load_registered_spec_ids
# ============================================================

class TestLoadRegisteredSpecIds:
    """load_registered_spec_ids 函式測試"""

    def _write_traceability(self, tmp_path: Path, data: dict) -> Path:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        traceability_path = docs_dir / "traceability.yaml"
        traceability_path.write_text(
            yaml.dump(data, allow_unicode=True), encoding="utf-8"
        )
        return traceability_path

    def test_loads_spec_ids_from_nested_structure(self, tmp_path):
        """場景 1：從巢狀結構（spec_frs 清單）擷取已登錄編號"""
        self._write_traceability(
            tmp_path,
            {
                "UC-01": {
                    "scenarios": {
                        "main": {
                            "spec_frs": ["SPEC-002-FR-01", "SPEC-003-FR-01"],
                        }
                    }
                }
            },
        )

        registered = load_registered_spec_ids(project_root=tmp_path)

        assert registered == {"SPEC-002", "SPEC-003"}

    def test_missing_file_returns_empty_set(self, tmp_path):
        """場景 2：traceability.yaml 不存在時回傳空集合（不拋例外）"""
        registered = load_registered_spec_ids(project_root=tmp_path)
        assert registered == set()

    def test_empty_file_returns_empty_set(self, tmp_path):
        """場景 3：traceability.yaml 存在但內容為空"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "traceability.yaml").write_text("", encoding="utf-8")

        registered = load_registered_spec_ids(project_root=tmp_path)
        assert registered == set()

    def test_malformed_yaml_returns_empty_set(self, tmp_path):
        """場景 4：格式錯誤的 YAML 不拋例外，回傳空集合"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "traceability.yaml").write_text(
            "UC-01:\n  - broken: [unclosed", encoding="utf-8"
        )

        registered = load_registered_spec_ids(project_root=tmp_path)
        assert registered == set()

    def test_loads_spec_ids_from_proposals_tracking_only(self, tmp_path):
        """場景 5（0.38.1-W1-107）：traceability.yaml 不存在，改讀
        proposals-tracking.yaml 的 specs: 區段"""
        _write_proposals_tracking(tmp_path, ["SPEC-001", "SPEC-006"])

        registered = load_registered_spec_ids(project_root=tmp_path)

        assert registered == {"SPEC-001", "SPEC-006"}

    def test_unions_both_registries(self, tmp_path):
        """場景 6：兩份登錄簿皆存在時取聯集"""
        self._write_traceability(
            tmp_path,
            {"UC-01": {"scenarios": {"main": {"spec_frs": ["SPEC-002-FR-01"]}}}},
        )
        _write_proposals_tracking(tmp_path, ["SPEC-006"])

        registered = load_registered_spec_ids(project_root=tmp_path)

        assert registered == {"SPEC-002", "SPEC-006"}


class TestRegistriesUninitialized:
    """registries_uninitialized 函式測試"""

    def test_both_missing_returns_true(self, tmp_path):
        """場景 1：兩份登錄簿皆不存在"""
        assert registries_uninitialized(project_root=tmp_path) is True

    def test_only_traceability_exists_returns_false(self, tmp_path):
        """場景 2：僅 traceability.yaml 存在"""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "traceability.yaml").write_text("UC-01: {}", encoding="utf-8")

        assert registries_uninitialized(project_root=tmp_path) is False

    def test_only_proposals_tracking_exists_returns_false(self, tmp_path):
        """場景 3：僅 proposals-tracking.yaml 存在"""
        _write_proposals_tracking(tmp_path, ["SPEC-001"])

        assert registries_uninitialized(project_root=tmp_path) is False


# ============================================================
# 測試 detect_unregistered_spec_references
# ============================================================

class TestDetectUnregisteredSpecReferences:
    """detect_unregistered_spec_references 函式測試"""

    def _write_traceability(self, tmp_path: Path, spec_frs):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        data = {"UC-01": {"scenarios": {"main": {"spec_frs": spec_frs}}}}
        (docs_dir / "traceability.yaml").write_text(
            yaml.dump(data, allow_unicode=True), encoding="utf-8"
        )

    def test_unregistered_reference_produces_warning(self, tmp_path):
        """場景 1（F1 動機案例）：誤植未登錄的 SPEC-008 觸發警告"""
        self._write_traceability(tmp_path, ["SPEC-002-FR-01"])

        warnings = detect_unregistered_spec_references(
            {"why": "依 SPEC-008 修正", "what": "", "title": ""},
            project_root=tmp_path,
        )

        assert len(warnings) == 1
        assert "SPEC-008" in warnings[0]
        assert warnings[0] == CreateMessages.UNREGISTERED_SPEC_REFERENCE_WARNING.format(
            spec_ids="SPEC-008"
        )

    def test_registered_reference_no_warning(self, tmp_path):
        """場景 2：既有正確引用不誤報（acceptance 條件 2）"""
        self._write_traceability(tmp_path, ["SPEC-002-FR-01"])

        warnings = detect_unregistered_spec_references(
            {"why": "依 SPEC-002 實作", "what": "", "title": ""},
            project_root=tmp_path,
        )

        assert warnings == []

    def test_no_spec_reference_no_warning(self, tmp_path):
        """場景 3：欄位中無 SPEC 引用時不觸發（無需讀 traceability.yaml 也不報錯）"""
        warnings = detect_unregistered_spec_references(
            {"why": "純文字需求", "what": "無引用", "title": ""},
            project_root=tmp_path,
        )

        assert warnings == []

    def test_multiple_unregistered_references_combined_in_one_warning(self, tmp_path):
        """場景 4：多個未登錄編號合併於單一警告訊息，並依編號排序"""
        self._write_traceability(tmp_path, ["SPEC-002-FR-01"])

        warnings = detect_unregistered_spec_references(
            {"why": "對照 SPEC-099", "what": "另涉 SPEC-008", "title": ""},
            project_root=tmp_path,
        )

        assert len(warnings) == 1
        assert "SPEC-008" in warnings[0]
        assert "SPEC-099" in warnings[0]
        # 依編號數值排序：SPEC-008 應排在 SPEC-099 之前
        assert warnings[0].index("SPEC-008") < warnings[0].index("SPEC-099")

    def test_scans_where_layer_and_how_strategy(self, tmp_path):
        """場景 5：掃描範圍涵蓋 where.layer 與 how.strategy 巢狀欄位"""
        self._write_traceability(tmp_path, ["SPEC-002-FR-01"])

        warnings = detect_unregistered_spec_references(
            {
                "why": "",
                "what": "",
                "title": "",
                "where": {"layer": "涉及 SPEC-777 的 collector 邊界"},
                "how": {"strategy": "無額外引用"},
            },
            project_root=tmp_path,
        )

        assert len(warnings) == 1
        assert "SPEC-777" in warnings[0]

    def test_empty_ticket_fields_no_warning(self, tmp_path):
        """場景 6：空字典輸入不拋例外"""
        assert detect_unregistered_spec_references({}, project_root=tmp_path) == []
        assert detect_unregistered_spec_references(None, project_root=tmp_path) == []

    def test_both_registries_missing_emits_uninitialized_warning(self, tmp_path):
        """場景 7（0.38.1-W1-107）：兩份登錄簿皆不存在時，輸出單一「未初始化」
        訊息，不逐號誤報"""
        warnings = detect_unregistered_spec_references(
            {"why": "依 SPEC-001 實作", "what": "", "title": ""},
            project_root=tmp_path,
        )

        assert warnings == [CreateMessages.SPEC_REGISTRY_UNINITIALIZED_WARNING]

    def test_proposals_tracking_registered_reference_no_warning(self, tmp_path):
        """場景 8（0.38.1-W1-107）：僅 proposals-tracking.yaml 登錄時，
        對應引用不誤報（W1-106 動機案例：SPEC-006 已登錄卻誤報）"""
        _write_proposals_tracking(tmp_path, ["SPEC-006"])

        warnings = detect_unregistered_spec_references(
            {"why": "依 SPEC-006 修正", "what": "", "title": ""},
            project_root=tmp_path,
        )

        assert warnings == []

    def test_union_of_both_registries_no_warning(self, tmp_path):
        """場景 9：traceability.yaml 與 proposals-tracking.yaml 各登錄一個
        編號，兩個引用皆不誤報（聯集驗證）"""
        self._write_traceability(tmp_path, ["SPEC-002-FR-01"])
        _write_proposals_tracking(tmp_path, ["SPEC-006"])

        warnings = detect_unregistered_spec_references(
            {"why": "依 SPEC-002 與 SPEC-006 實作", "what": "", "title": ""},
            project_root=tmp_path,
        )

        assert warnings == []
