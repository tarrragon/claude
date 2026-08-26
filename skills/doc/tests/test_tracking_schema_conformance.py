"""tracking_schema.py SSOT 與真實 tracking 檔一致性測試。

取代手寫 fixture 宣稱鏡射真實檔卻會漂移的問題：本測試直接載入真實
docs/proposals-tracking.yaml，斷言其結構符合 SSOT 定義。

create.py 與 status.py 已對齊 list-based 格式並引用 SSOT。
"""

import re
from pathlib import Path

import pytest
import yaml

from doc_system.core.frontmatter_parser import parse_frontmatter
from doc_system.core.tracking_schema import (
    EVT_CATEGORIES,
    EVT_REQUIRED_FIELDS,
    FLOWSTEP_REQUIRED_FIELDS,
    GRAPH_EDGE_CLASSES,
    GRAPH_EDGE_MAINTAINERS,
    GRAPH_EDGE_TYPES,
    GRAPH_LAYER_ESTABLISHED,
    GRAPH_LAYER_PROPOSED,
    GRAPH_NODE_TYPES,
    PROPOSALS_TRACKING_SCHEMA,
    TRACEABILITY_SCHEMA,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PROPOSALS_TRACKING_PATH = PROJECT_ROOT / "docs" / "proposals-tracking.yaml"
TRACEABILITY_PATH = PROJECT_ROOT / "docs" / "traceability.yaml"
EVT_BALANCE_DIR = PROJECT_ROOT / "docs" / "events" / "balance"
UC_01_PATH_CANDIDATES = list((PROJECT_ROOT / "docs" / "usecases").glob("UC-01-*.md"))


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

    def test_traceability_schema_has_four_axes(self):
        """四軸追溯（mappings / domain_bundle_tests / data_contract_tests / runtime_tests）皆須存在。"""
        assert {
            "mappings",
            "domain_bundle_tests",
            "data_contract_tests",
            "runtime_tests",
        } <= (TRACEABILITY_SCHEMA["top_level_keys"])
        assert TRACEABILITY_SCHEMA["domain_bundle_tests_format"] == "list"
        assert TRACEABILITY_SCHEMA["data_contract_tests_format"] == "list"
        assert TRACEABILITY_SCHEMA["runtime_tests_format"] == "list"

    def test_domain_bundle_entry_required_keys(self):
        required = TRACEABILITY_SCHEMA["domain_bundle_entry_required"]
        assert required == {"bundle", "layer", "invariants", "tests"}

    def test_data_contract_entry_required_keys(self):
        required = TRACEABILITY_SCHEMA["data_contract_entry_required"]
        assert required == {"contract_ref", "description"}

    def test_schemas_are_independent(self):
        """per-file 邊界：兩個 schema 頂層鍵不應互相假設（per-file 邊界原則）。"""
        assert "last_updated" not in PROPOSALS_TRACKING_SCHEMA["top_level_keys"]
        assert "proposals" not in TRACEABILITY_SCHEMA["top_level_keys"]


class TestProposalsTrackingRealFileConformance:
    """載入真實 docs/proposals-tracking.yaml 驗證與 SSOT 一致。"""

    @pytest.fixture(scope="class")
    def real_data(self):
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
        """頂層鍵須落在允許集合內；四軸皆為選補，軸不存在合法，僅未知鍵才是違規。"""
        if not TRACEABILITY_PATH.exists():
            pytest.skip("docs/traceability.yaml 尚未建立（按需由 batch_init 產生）")
        with open(TRACEABILITY_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        keys = set(data.keys())
        required = TRACEABILITY_SCHEMA["top_level_required_keys"]
        allowed = TRACEABILITY_SCHEMA["top_level_keys"]
        missing = required - keys
        assert not missing, f"缺少必要頂層欄位：{missing}"
        unknown = keys - allowed
        assert not unknown, f"含未知頂層欄位：{unknown}"

    def test_domain_bundle_tests_entries_conform_if_exists(self):
        if not TRACEABILITY_PATH.exists():
            pytest.skip("docs/traceability.yaml 尚未建立（按需由 batch_init 產生）")
        with open(TRACEABILITY_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        required = TRACEABILITY_SCHEMA["domain_bundle_entry_required"]
        for entry in data.get("domain_bundle_tests", []):
            missing = required - set(entry.keys())
            assert not missing, f"bundle {entry.get('bundle')} 缺少必要欄位：{missing}"

    def test_data_contract_tests_entries_conform_if_exists(self):
        if not TRACEABILITY_PATH.exists():
            pytest.skip("docs/traceability.yaml 尚未建立（按需由 batch_init 產生）")
        with open(TRACEABILITY_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        required = TRACEABILITY_SCHEMA["data_contract_entry_required"]
        allowed = required | TRACEABILITY_SCHEMA["data_contract_entry_optional"]
        for entry in data.get("data_contract_tests", []):
            missing = required - set(entry.keys())
            assert not missing, f"contract {entry.get('contract_ref')} 缺少必要欄位：{missing}"
            unknown = set(entry.keys()) - allowed
            assert not unknown, f"contract {entry.get('contract_ref')} 含未知欄位：{unknown}"
            has_tests = bool(entry.get("tests"))
            has_no_test_needed = entry.get("no_test_needed") is True
            assert has_tests or has_no_test_needed, (
                f"contract {entry.get('contract_ref')} 須有 tests 或 no_test_needed=true"
            )


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


def _extract_flow_block(uc_text: str) -> list[dict]:
    """從 UC 文件正文擷取結構化 flow 區塊（```yaml 內以 flow: 起始的區塊）。"""
    marker = "```yaml\nflow:"
    start = uc_text.find(marker)
    assert start != -1, "UC 文件未含結構化 flow 區塊（```yaml\\nflow:）"
    end = uc_text.find("```", start + len(marker))
    assert end != -1, "flow 區塊未正確以 ``` 結尾"
    block_text = uc_text[start + len("```yaml\n"):end]
    data = yaml.safe_load(block_text)
    return data["flow"]


class TestGraphTypeTablesWellFormed:
    """圖譜型別表 SSOT 常數本身的結構完整性（A 層 5 節點 12 邊、B 層 2 節點 4 邊）。"""

    def test_node_types_cover_a_and_b_layer(self):
        a_layer = {n for n, v in GRAPH_NODE_TYPES.items() if v["layer"] == GRAPH_LAYER_ESTABLISHED}
        b_layer = {n for n, v in GRAPH_NODE_TYPES.items() if v["layer"] == GRAPH_LAYER_PROPOSED}
        assert a_layer == {"PROP", "SPEC", "UC", "Ticket", "DomainBundle"}
        assert b_layer == {"FlowStep", "EVT"}

    def test_every_node_type_has_id_pattern_and_carrier(self):
        for name, entry in GRAPH_NODE_TYPES.items():
            assert entry.get("id_pattern"), f"{name} 缺少 id_pattern"
            assert entry.get("carrier"), f"{name} 缺少 carrier"

    def test_edge_types_cover_a_and_b_layer(self):
        a_layer = {n for n, v in GRAPH_EDGE_TYPES.items() if v["layer"] == GRAPH_LAYER_ESTABLISHED}
        b_layer = {n for n, v in GRAPH_EDGE_TYPES.items() if v["layer"] == GRAPH_LAYER_PROPOSED}
        assert len(a_layer) == 12, f"A 層邊應為 12 條，實得 {len(a_layer)}：{sorted(a_layer)}"
        assert len(b_layer) == 4, f"B 層邊應為 4 條，實得 {len(b_layer)}：{sorted(b_layer)}"
        assert b_layer == {"emission", "consumption", "branching", "returning"}

    def test_every_edge_type_has_five_required_fields(self):
        """每條邊的 class / 正向欄位 / 反向欄位 / 維護方 / layer 皆可程式取用。"""
        for name, entry in GRAPH_EDGE_TYPES.items():
            assert entry["class"] in GRAPH_EDGE_CLASSES, f"{name}.class 值域外：{entry['class']}"
            assert entry.get("forward_field"), f"{name} 缺少 forward_field"
            assert "reverse_field" in entry, f"{name} 缺少 reverse_field 鍵（可為 None）"
            assert entry["maintainer"] in GRAPH_EDGE_MAINTAINERS, f"{name}.maintainer 值域外"
            assert entry["layer"] in {GRAPH_LAYER_ESTABLISHED, GRAPH_LAYER_PROPOSED}

    def test_cli_auto_maintained_edges_have_reverse_field(self):
        """blood / spawn 由 CLI 自動維護正反向，反向欄位不可為 None。"""
        assert GRAPH_EDGE_TYPES["blood"]["reverse_field"] == "children"
        assert GRAPH_EDGE_TYPES["spawn"]["reverse_field"] == "spawned_tickets"

    def test_node_and_edge_tables_share_same_layer_field_name(self):
        """節點表與邊表必須用同一個欄位名表示層級狀態（防再度分叉，非硬編 'layer'）。"""

        def layer_field_names(table):
            layer_values = {GRAPH_LAYER_ESTABLISHED, GRAPH_LAYER_PROPOSED}
            return {
                frozenset(k for k, val in entry.items() if val in layer_values)
                for entry in table.values()
            }

        node_layer_keys = layer_field_names(GRAPH_NODE_TYPES)
        edge_layer_keys = layer_field_names(GRAPH_EDGE_TYPES)
        assert node_layer_keys == edge_layer_keys, (
            f"節點表與邊表的層級欄位名不一致：node={node_layer_keys}, edge={edge_layer_keys}"
        )
        assert len(node_layer_keys) == 1 and len(next(iter(node_layer_keys))) == 1, (
            "每張表的層級欄位名應唯一且單一"
        )


class TestGraphTypeTablesRealEvtConformance:
    """以 UC-01 回填的首批真實 EVT 資料驗證 EVT 節點常數。"""

    @pytest.fixture(scope="class")
    def evt_entries(self):
        assert EVT_BALANCE_DIR.is_dir(), f"真實 EVT 目錄不存在：{EVT_BALANCE_DIR}"
        files = sorted(EVT_BALANCE_DIR.glob("EVT-BALANCE-*.md"))
        assert files, "docs/events/balance/ 下無 EVT-BALANCE-*.md"
        return [(f, parse_frontmatter(str(f))) for f in files]

    def test_at_least_five_real_evt_files(self, evt_entries):
        assert len(evt_entries) >= 5

    def test_every_evt_id_matches_id_pattern(self, evt_entries):
        pattern = re.compile(GRAPH_NODE_TYPES["EVT"]["id_pattern"])
        for path, fm in evt_entries:
            assert pattern.match(fm["id"]), f"{path.name}: id={fm['id']} 不符 EVT id_pattern"

    def test_every_evt_has_required_fields(self, evt_entries):
        for path, fm in evt_entries:
            missing = EVT_REQUIRED_FIELDS - set(fm.keys())
            assert not missing, f"{path.name} 缺少必填欄位：{missing}"

    def test_every_evt_category_in_value_domain(self, evt_entries):
        for path, fm in evt_entries:
            assert fm["category"] in EVT_CATEGORIES, f"{path.name}: category={fm['category']} 值域外"


class TestGraphTypeTablesRealFlowStepConformance:
    """以 UC-01 結構化 flow 區塊驗證 FlowStep 節點常數與 B 層語意邊。"""

    @pytest.fixture(scope="class")
    def flow_steps(self):
        assert UC_01_PATH_CANDIDATES, "docs/usecases/ 下找不到 UC-01-*.md"
        uc_text = UC_01_PATH_CANDIDATES[0].read_text(encoding="utf-8")
        return _extract_flow_block(uc_text)

    def test_every_flowstep_id_matches_id_pattern(self, flow_steps):
        pattern = re.compile(GRAPH_NODE_TYPES["FlowStep"]["id_pattern"])
        for step in flow_steps:
            assert pattern.match(step["id"]), f"FlowStep id={step['id']} 不符 id_pattern"

    def test_every_flowstep_has_required_fields(self, flow_steps):
        for step in flow_steps:
            missing = FLOWSTEP_REQUIRED_FIELDS - set(step.keys())
            assert not missing, f"FlowStep {step['id']} 缺少必填欄位：{missing}"

    def test_emits_and_consumes_reference_existing_evt_ids(self, flow_steps):
        """emission / consumption 語意邊：FlowStep.emits / consumes 須指向真實存在的 EVT id。"""
        real_evt_ids = {
            parse_frontmatter(str(f))["id"]
            for f in EVT_BALANCE_DIR.glob("EVT-BALANCE-*.md")
        }
        assert real_evt_ids, "無法從檔名衍生真實 EVT id 集合"
        for step in flow_steps:
            for evt_id in step.get("emits", []) or []:
                assert evt_id in real_evt_ids, f"FlowStep {step['id']}.emits 引用不存在的 {evt_id}"
            for evt_id in step.get("consumes", []) or []:
                assert evt_id in real_evt_ids, f"FlowStep {step['id']}.consumes 引用不存在的 {evt_id}"

    def test_branch_from_and_return_to_reference_existing_flowstep_ids(self, flow_steps):
        """branching / returning 語意邊：branch_from / return_to 須指向本 flow 內存在的 FlowStep id。"""
        all_ids = {step["id"] for step in flow_steps}
        for step in flow_steps:
            if step["branch_from"] is not None:
                assert step["branch_from"] in all_ids, (
                    f"FlowStep {step['id']}.branch_from 引用不存在的 {step['branch_from']}"
                )
            if step["return_to"] is not None:
                assert step["return_to"] in all_ids, (
                    f"FlowStep {step['id']}.return_to 引用不存在的 {step['return_to']}"
                )
