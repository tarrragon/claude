"""Doc skill tracking 檔案 schema 單一真相源（SSOT）。

per-file 定義：不同 tracking 檔（proposals-tracking.yaml / traceability.yaml）
schema 互不相同，各自獨立定義，消費端一律引用本模組常數，禁止 inline 猜測欄位名。

背景：IMP-APP-002 同族 bug（欄位假設無真實資料驗證）已發生多起
（confirmed_at、last_updated 等欄位命名假設歷次偏離真實 schema）。
詳見歷次欄位/schema 對齊修復 ANA。
"""

from __future__ import annotations

# docs/proposals-tracking.yaml 的權威 schema。
# 頂層結構：{proposals: [...], usecases: [...], specs: [...]}
# proposals 為 list-based（非 dict-keyed-by-id）。
PROPOSALS_TRACKING_SCHEMA = {
    "top_level_keys": {"proposals", "usecases", "specs"},
    "proposals_format": "list",
    "proposal_entry_required": {"id", "title", "status"},
    "proposal_entry_optional": {
        "priority",
        "confirmed_at",
        "completed_note",
        "target_version",
        "proposed",
        "source",
        "spec_refs",
        "usecase_refs",
        "ticket_refs",
        "checklist",
        "canonical_ssot",
        "tracking_ticket",
        # list of str（提案 id）：本提案依賴的前置提案，供
        # version-bootstrap/scripts/check_proposal_dependencies.py 檢查跨提案
        # 排序矛盾（W1-017：補齊宣告，格式由消費端用法與既有測試 fixture
        # 雙重佐證確認，非獨立文件宣告）。
        "depends_on",
    },
    # 確認日期欄位名為 confirmed_at，非 confirmed（欄位名須對齊真實 schema）。
    "confirm_date_field": "confirmed_at",
}

# docs/traceability.yaml 的權威 schema（按需由 batch_init 建立）。
# 與 PROPOSALS_TRACKING_SCHEMA 完全獨立，last_updated 是本檔合法自洽欄位
# （per-file schema 獨立，勿跨檔套用頂層鍵假設）。
#
# 四軸追溯（對齊 docs/traceability.yaml 實際結構）：
#   mappings             = FR → UC 場景 → tests（垂直：使用者行為軸，既有）
#   domain_bundle_tests  = domain map bundle → 不變式 → tests（水平：domain 規則軸）
#   data_contract_tests  = 資料契約條目（INV-xx / A.x-x）→ tests（第三軸）
#   runtime_tests        = UC 場景 → integration_test/ on-device 測試（第四軸；
#                          前三軸指向 host 測試，本軸指向零結構替身的
#                          on-device 測試）
# 四軸各自獨立記錄覆蓋，聯集為完整覆蓋，交集去重。
#
# 頂層鍵區分「必要」與「選補」：version / last_updated 為必要；四軸皆為
# 選補——軸不存在合法（例如 domain_bundle_tests 的前置 domain-map.md 尚未
# 建立、runtime_tests 需先盤點 integration_test/ 是否符合零結構替身定義），
# 軸存在但結構錯誤才是違規。top_level_keys 是「允許的頂層鍵上限」，
# top_level_required_keys 是「必要頂層鍵下限」。
TRACEABILITY_SCHEMA = {
    "top_level_keys": {
        "version",
        "mappings",
        "domain_bundle_tests",
        "data_contract_tests",
        "runtime_tests",
        "last_updated",
    },
    "top_level_required_keys": {"version", "last_updated"},
    "mappings_format": "list",
    "mapping_entry_required": {"spec", "usecase", "title"},
    "mapping_entry_optional": {"scenarios", "alt_scenarios", "main_flow", "tests"},
    # domain_bundle_tests：list-based，每條目代表一個 domain bundle。
    "domain_bundle_tests_format": "list",
    "domain_bundle_entry_required": {"bundle", "layer", "invariants", "tests"},
    "domain_bundle_entry_optional": set(),
    # data_contract_tests：list-based，每條目對應一個資料契約不變式/邊界。
    # tests 與 (no_test_needed + reason) 互斥：有測試覆蓋填 tests；
    # 明文豁免填 no_test_needed=true + reason。
    "data_contract_tests_format": "list",
    "data_contract_entry_required": {"contract_ref", "description"},
    "data_contract_entry_optional": {
        "tests",
        "no_test_needed",
        "reason",
        "reason_supplement",
    },
    # runtime_tests：list-based，每條目對應一個 UC 場景的 on-device 測試。
    "runtime_tests_format": "list",
    "runtime_tests_entry_required": {"scenario", "covers_uc", "tests", "status"},
    "runtime_tests_entry_optional": set(),
}


# ---------------------------------------------------------------------------
# 文件圖譜型別表 SSOT
#
# 節點與邊型別表原以人類可讀 Markdown 分析結論定案，不作為 validator 或
# 外部視覺化工具的實作依據。本節把該表格落成 Python 常數，供 doc CLI
# validator 與外部消費者 import；Markdown 表格內容不可再被引用為權威來
# 源（防止雙份 SSOT 漂移，language-constraints 規則 5 同精神）。
#
# 本節只承載已定案內容，不裁決。內容若與人類可讀分析結論出現矛盾或不
# 足，走 ticket spawn-request 流程，不在此處自行修改。
# ---------------------------------------------------------------------------

# 層級語意：本欄位是型別對消費端的穩定性承諾，不是開發進度。established 表示
# 該型別已被獨立語料交叉驗證、消費端可依賴；proposed 表示形狀仍可能變動。
#
# 升級判準（兩條件同時成立才升級，缺一維持 proposed）：
#   1. 該型別在兩個以上互相獨立的 consumer 專案語料中有實例。單一專案的實例
#      只證明「寫得出符合此型別的文件」，不證明型別捕捉到跨專案共通的結構——
#      同一批人在同一套領域假設下產出的語料無法互為對照。
#   2. doc CLI 對該型別有建立與驗證支援（模板產出 + validator 檢查）。缺此支援
#      時型別只是約定，實例會各自漂移，交叉驗證的對照基礎不成立。
#
# 兩條件皆成立時的動作：將該型別的 layer 改為 established，並同步更新
# tests/test_tracking_schema_conformance.py 內的 A 層 / B 層預期集合。判準由
# 消費端專案在回填新語料後自行複查，本檔不排程（框架檔不引用專案識別符，
# reference-stability 規則 8）。
GRAPH_LAYER_ESTABLISHED = "established"
GRAPH_LAYER_PROPOSED = "proposed"

# 語意邊的 class 值域（固定五種）。
GRAPH_EDGE_CLASSES = frozenset(
    {"provenance", "containment", "see-also", "dataflow", "ordering"}
)

# 語意邊的維護方值域。
GRAPH_EDGE_MAINTAINERS = frozenset({"手動", "CLI 自動", "手動/CLI"})

# 節點型別表：A 層 5 節點 + B 層 2 節點。FR 與 Test 不列為獨立節點型別
# （無獨立檔案/ID 空間，語意由 SPEC / traceability 節點欄位承載）。
GRAPH_NODE_TYPES = {
    "PROP": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        "id_pattern": r"^PROP-\d{3}$",
        "carrier": "docs/proposals/PROP-NNN-{slug}.md frontmatter",
    },
    "SPEC": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        # SPEC ID 雙形態：數字型 SPEC-NNN 與 slug 型 SPEC-{SLUG} 皆合法，
        # 不強制配發數字別名。
        "id_pattern": r"^SPEC-([0-9]{3}|[A-Z0-9-]+)$",
        "carrier": "docs/spec/{domain}/{slug}.md frontmatter",
    },
    "UC": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        "id_pattern": r"^UC-\d{2,}$",
        "carrier": "docs/usecases/UC-NN-{slug}.md frontmatter",
    },
    "Ticket": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        "id_pattern": r"^[\w.]+-W\d+-\d+$",
        "carrier": "docs/work-logs/.../tickets/{id}.md frontmatter",
        # Ticket 欄位/驗證器歸屬 ticket_system（field-semantics.md 為權
        # 威），本節僅收錄 doc_system 消費圖譜所需的 id_pattern 與 carrier。
    },
    "DomainBundle": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        "id_pattern": r"^DOMAIN-MAP-[a-z0-9-]+$",
        "carrier": "docs/spec/{domain}/domain-map.md 或 docs/domain-map.md frontmatter",
    },
    "FlowStep": {
        "layer": GRAPH_LAYER_PROPOSED,
        # 不透明穩定識別符：位置與父步驟不編進 ID，拓撲全交 branch_from /
        # return_to 表達。kebab-case，與首批真實資料一致。
        "id_pattern": r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$",
        "carrier": "UC 文件內結構化 flow 區塊（YAML list）",
    },
    "EVT": {
        "layer": GRAPH_LAYER_PROPOSED,
        "id_pattern": r"^EVT-[A-Z0-9]+-\d{3}$",
        "carrier": (
            "docs/events/{domain}/EVT-{DOMAIN}-NNN-{slug}.md frontmatter"
            "（載體形式為 per-file，已定案。曾評估集中式 registry，不採用："
            "per-file 讓事件定義與其 domain 目錄同址、diff 粒度落在單一事件、"
            "新增事件不觸碰共用檔；registry 的收益在跨事件查詢，而該需求可由"
            "目錄掃描滿足。改採 registry 屬 schema 變更，需先提出 per-file 無法"
            "滿足的具體查詢或一致性需求。）"
        ),
    },
}

# EVT 節點必填欄位。
EVT_REQUIRED_FIELDS = frozenset({"id", "name", "canonical_name", "category"})

# EVT category 值域：domain_event（狀態變更事實，必有 consumer）或
# process_event（步驟進行中標記，允許無 consumer）。
EVT_CATEGORIES = frozenset({"domain_event", "process_event"})

# FlowStep 於 UC 結構化 flow 區塊內的必填欄位（依首批真實資料實例對齊）。
FLOWSTEP_REQUIRED_FIELDS = frozenset(
    {"id", "name", "next", "branch_from", "return_to", "emits", "consumes"}
)

# 語意邊表：A 層 12 條 + B 層 4 條，欄位齊全：class / 正向欄位（儲存
# 側）/ 反向欄位 / 維護方 / status。
GRAPH_EDGE_TYPES = {
    # --- A 層（12 條，established）---
    "provenance": {
        "class": "provenance",
        "forward_field": "source_proposal",
        "reverse_field": "outputs",
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "spec_association": {
        "class": "see-also",
        "forward_field": "related_specs",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "uc_association": {
        "class": "see-also",
        "forward_field": "related_usecases",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "proposal_association": {
        "class": "see-also",
        "forward_field": "related_proposals",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "requirement_impl": {
        "class": "containment",
        "forward_field": "implements_requirements",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "domain_dependency": {
        "class": "ordering",
        "forward_field": "depends_on_domains",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "domain_coverage": {
        "class": "containment",
        "forward_field": "source_specs",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "blood": {
        "class": "containment",
        "forward_field": "parent_id",
        "reverse_field": "children",
        "maintainer": "CLI 自動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "spawn": {
        "class": "provenance",
        "forward_field": "source_ticket",
        "reverse_field": "spawned_tickets",
        "maintainer": "CLI 自動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "blocking": {
        "class": "ordering",
        "forward_field": "blockedBy",
        "reverse_field": None,
        "maintainer": "手動/CLI",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "association": {
        # relatedTo：語意無向，消費端做 1-hop symmetric closure；儲存端
        # 仍為單向欄位，故 reverse_field 仍為 None。
        "class": "see-also",
        "forward_field": "relatedTo",
        "reverse_field": None,
        "maintainer": "手動/CLI",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "discovery": {
        "class": "provenance",
        "forward_field": "discovered_during",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    # --- B 層（4 條，proposed）---
    "emission": {
        "class": "dataflow",
        "forward_field": "emits",  # FlowStep.emits → EVT
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_PROPOSED,
    },
    "consumption": {
        "class": "dataflow",
        "forward_field": "consumes",  # EVT → FlowStep.consumes
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_PROPOSED,
    },
    "branching": {
        "class": "ordering",
        "forward_field": "branch_from",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_PROPOSED,
    },
    "returning": {
        "class": "ordering",
        # back-edge，排除於 DAG 佈局。
        "forward_field": "return_to",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_PROPOSED,
    },
}
