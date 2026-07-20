"""tracking_schema.py SSOT 與真實 tracking 檔一致性測試。

取代手寫 fixture 宣稱鏡射真實檔卻會漂移的問題：本測試直接載入真實
docs/proposals-tracking.yaml，斷言其結構符合 SSOT 定義。

create.py 與 status.py 已對齊 list-based 格式並引用 SSOT。
"""

from pathlib import Path

import pytest
import yaml

from doc_system.core.tracking_schema import (
    PROPOSALS_TRACKING_SCHEMA,
    TRACEABILITY_SCHEMA,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROPOSALS_TRACKING_PATH = PROJECT_ROOT / "docs" / "proposals-tracking.yaml"
TRACEABILITY_PATH = PROJECT_ROOT / "docs" / "traceability.yaml"


class TestSchemaConstantsWellFormed:
    """SSOT 常數本身的結構完整性。"""

    def test_proposals_schema_has_required_keys(self):
        assert "top_level_keys" in PROPOSALS_TRACKING_SCHEMA
        assert "proposal_entry_required" in PROPOSALS_TRACKING_SCHEMA
        assert PROPOSALS_TRACKING_SCHEMA["proposals_format"] == "list"

    def test_proposals_confirm_date_field_is_confirmed_at(self):
        assert PROPOSALS_TRACKING_SCHEMA["confirm_date_field"] == "confirmed_at"

    def test_traceability_schema_has_required_keys(self):
        assert "top_level_keys" in TRACEABILITY_SCHEMA
        assert "mapping_entry_required" in TRACEABILITY_SCHEMA
        assert TRACEABILITY_SCHEMA["mappings_format"] == "list"

    def test_schemas_are_independent(self):
        """per-file 邊界：兩個 schema 頂層鍵不應互相假設（per-file 邊界原則）。"""
        assert "last_updated" not in PROPOSALS_TRACKING_SCHEMA["top_level_keys"]
        assert "proposals" not in TRACEABILITY_SCHEMA["top_level_keys"]


class TestProposalsTrackingRealFileConformance:
    """載入真實 docs/proposals-tracking.yaml 驗證與 SSOT 一致。"""

    @classmethod
    @pytest.fixture(scope="class")
    def real_data(cls):
        assert PROPOSALS_TRACKING_PATH.exists(), (
            f"真實 tracking 檔不存在：{PROPOSALS_TRACKING_PATH}"
        )
        with open(PROPOSALS_TRACKING_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_top_level_keys_match_schema(self, real_data):
        assert set(real_data.keys()) == PROPOSALS_TRACKING_SCHEMA["top_level_keys"]

    def test_proposals_is_list(self, real_data):
        assert isinstance(real_data["proposals"], list)

    def test_each_proposal_entry_has_required_keys(self, real_data):
        required = PROPOSALS_TRACKING_SCHEMA["proposal_entry_required"]
        for entry in real_data["proposals"]:
            missing = required - set(entry.keys())
            assert not missing, f"entry {entry.get('id')} 缺少必要欄位：{missing}"

    def test_each_proposal_entry_keys_are_known(self, real_data):
        """entry 欄位須在 required 或 optional 集合內，防止 schema 漂移未被發現。"""
        allowed = (
            PROPOSALS_TRACKING_SCHEMA["proposal_entry_required"]
            | PROPOSALS_TRACKING_SCHEMA["proposal_entry_optional"]
        )
        for entry in real_data["proposals"]:
            unknown = set(entry.keys()) - allowed
            assert not unknown, f"entry {entry.get('id')} 含未知欄位：{unknown}"


class TestTraceabilityRealFileConformance:
    """traceability.yaml 為按需建立檔，不存在時 skip。"""

    def test_traceability_conformance_if_exists(self):
        if not TRACEABILITY_PATH.exists():
            pytest.skip("docs/traceability.yaml 尚未建立（按需由 batch_init 產生）")
        with open(TRACEABILITY_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert set(data.keys()) == TRACEABILITY_SCHEMA["top_level_keys"]


class TestConsumerConformance:
    """消費端寫入點是否引用 SSOT。"""

    def test_create_py_uses_list_format(self):
        create_py = PROJECT_ROOT / ".claude" / "skills" / "doc" / "doc_system" / "commands" / "create.py"
        source = create_py.read_text(encoding="utf-8")
        assert "from doc_system.core.tracking_schema import" in source, (
            "create.py 尚未引用 tracking_schema SSOT"
        )

    def test_status_py_uses_list_format(self):
        status_py = PROJECT_ROOT / ".claude" / "skills" / "doc" / "doc_system" / "commands" / "status.py"
        source = status_py.read_text(encoding="utf-8")
        assert "from doc_system.core.tracking_schema import" in source, (
            "status.py 尚未引用 tracking_schema SSOT"
        )

    def test_batch_init_py_uses_list_format(self):
        """W1-013 修復：batch_init.py 曾以 dict-keyed-by-id 查找 proposals，與 SSOT 不符。"""
        batch_init_py = PROJECT_ROOT / ".claude" / "skills" / "doc" / "doc_system" / "commands" / "batch_init.py"
        source = batch_init_py.read_text(encoding="utf-8")
        assert "from doc_system.core.tracking_schema import" in source, (
            "batch_init.py 尚未引用 tracking_schema SSOT"
        )
        assert "PROPOSALS_TRACKING_SCHEMA" in source, (
            "batch_init.py 應引用 PROPOSALS_TRACKING_SCHEMA 而非 inline 猜測 proposals 格式"
        )
