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

# 路徑模式與具體度（機器可比對的 carrier 補充，人讀 carrier 描述保留不動）。
#
# 只有 carrier 是「檔案路徑」的型別才有 carrier_path_patterns；FlowStep
# 的 carrier 是 UC 文件內的區塊，不適用。
#
# carrier_path_patterns：清單，每個元素為 {"pattern": <regex>,
# "specificity": [literal_segment_count, cross_segment_wildcard_count]}。
# 同一型別若有多個合法替代路徑形態（例如 DomainBundle 的 per-domain 巢
# 狀路徑與根層路徑），拆成清單中的多個元素，每個各自計算具體度；不將
# 多個形態合併成單一 alternation 正則後只算一個具體度。
#
# pattern：與 id_pattern 同一正則方言（見匯出端 ID_PATTERN_DIALECT，
# "python-re"）。比對對象是相對於工作區根目錄、以 "/" 分隔的完整路徑
# （含檔名），區分大小寫。
#
# specificity 由路徑樣板（非最終正則字串）以 "/" 切分計算，只有兩層：
#   1. literal_segment_count：整段皆為固定文字才算「字面段」；只要該段
#      含任何萬用成分（例如 {slug}.md、PROP-*-*.md）即整段不算，不採部
#      分計分。
#   2. cross_segment_wildcard_count：能一次跨越多個路徑段的萬用成分數
#      （例如樣板中的 "..."）；單一路徑段內的萬用字元不計入本項。
#
# 具體度比較僅在「同一路徑可能同時命中多個型別的模式」時才有意義——目
# 錄名不重疊的型別（例如 proposals 與 usecases）不會命中同一路徑，兩者
# 具體度打平不影響任何實際分類決策。比對規則：先比
# literal_segment_count（多者優先），再比 cross_segment_wildcard_count
# （少者優先）；兩項皆同視為打平，**打平即為 schema 歧義，交由消費端回
# 報**，不引入任何第三層次悄悄消歧——新增型別若與既有的、路徑命名空間
# 可能重疊的型別在兩項打平，須調整路徑深度或縮小重疊範圍化解，不得用
# 額外比對層次掩蓋。

# 型別表相容版本：`doc schema export` 寫入 JSON 鍵
# `schema_generated_at_framework_version` 的值，取自本常數，不讀 .claude/VERSION。
# 語意是「型別表最後一次變更時的框架版本」，只在 GRAPH_NODE_TYPES /
# GRAPH_EDGE_TYPES 等型別表內容變更時手動升版，升為變更當下的框架版本。
# 鍵名不改的理由：改名會影響所有舊 consumer；舊 consumer 照舊寫入的框架
# 版本與本常數落在同一條遞增序列，消費端閘門無需修改即可比較。
TYPE_TABLE_COMPAT_VERSION = "2.77.1"

# 節點型別表：A 層 5 節點 + B 層 2 節點。FR 與 Test 不列為獨立節點型別
# （無獨立檔案/ID 空間，語意由 SPEC / traceability 節點欄位承載）。
GRAPH_NODE_TYPES = {
    "PROP": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        "id_pattern": r"^PROP-\d{3}$",
        "carrier": "docs/proposals/PROP-NNN-{slug}.md frontmatter",
        "carrier_path_patterns": [
            {
                "pattern": r"^docs/proposals/PROP-\d{3}-[^/]+\.md$",
                "specificity": [2, 0],
            },
        ],
    },
    "SPEC": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        # SPEC ID 雙形態：數字型 SPEC-NNN 與 slug 型 SPEC-{SLUG} 皆合法，
        # 不強制配發數字別名。
        "id_pattern": r"^SPEC-([0-9]{3}|[A-Z0-9-]+)$",
        "carrier": "docs/spec/{domain}/{slug}.md frontmatter",
        # README.md 排除在外（domain 目錄的說明文件非 SPEC）；domain-map.md
        # 未排除——與 DomainBundle 的巢狀路徑刻意重疊，由具體度分出優先
        # 序（DomainBundle 巢狀形態的字面段數較高，見其 carrier_path_patterns）。
        "carrier_path_patterns": [
            {
                "pattern": r"^docs/spec/[^/]+/(?!README\.md$)[^/]+\.md$",
                "specificity": [2, 0],
            },
        ],
    },
    "UC": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        "id_pattern": r"^UC-\d{2,}$",
        "carrier": "docs/usecases/UC-NN-{slug}.md frontmatter",
        "carrier_path_patterns": [
            {
                "pattern": r"^docs/usecases/UC-\d{2,}-[^/]+\.md$",
                "specificity": [2, 0],
            },
        ],
    },
    "Ticket": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        "id_pattern": r"^[\w.]+-W\d+-\d+(\.\d+)*$",
        "carrier": "docs/work-logs/.../tickets/{id}.md frontmatter",
        # Ticket 欄位/驗證器歸屬 ticket_system（field-semantics.md 為權
        # 威），本節僅收錄 doc_system 消費圖譜所需的 id_pattern 與 carrier。
        # "..." 為可變版本/波次目錄，對應 cross_segment_wildcard_count=1。
        "carrier_path_patterns": [
            {
                "pattern": r"^docs/work-logs/(?:[^/]+/)+tickets/[^/]+\.md$",
                "specificity": [3, 1],
            },
        ],
    },
    "DomainBundle": {
        "layer": GRAPH_LAYER_ESTABLISHED,
        "id_pattern": r"^DOMAIN-MAP-[a-z0-9-]+$",
        "carrier": "docs/spec/{domain}/domain-map.md 或 docs/domain-map.md frontmatter",
        # 兩種合法路徑形態各自列一個元素，各自計算具體度：巢狀形態
        # （字面段數 3）用於與 SPEC 的重疊消歧（domain-map.md 同時符合
        # 兩型別的路徑模式，SPEC 為 2）；根層形態為獨立路徑，與其他型別
        # 命名空間不重疊。
        "carrier_path_patterns": [
            {
                "pattern": r"^docs/spec/[^/]+/domain-map\.md$",
                "specificity": [3, 0],
            },
            {
                "pattern": r"^docs/domain-map\.md$",
                "specificity": [2, 0],
            },
        ],
    },
    "FlowStep": {
        "layer": GRAPH_LAYER_PROPOSED,
        # 不透明穩定識別符：位置與父步驟不編進 ID，拓撲全交 branch_from /
        # return_to 表達。kebab-case，與首批真實資料一致。
        "id_pattern": r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$",
        "carrier": "UC 文件內結構化 flow 區塊（YAML list）",
        # 無 carrier_path_patterns：carrier 非獨立檔案路徑，見本節前言。
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
        "carrier_path_patterns": [
            {
                "pattern": r"^docs/events/[^/]+/EVT-[A-Z0-9]+-\d{3}-[^/]+\.md$",
                "specificity": [2, 0],
            },
        ],
    },
}

# 具備 carrier_path_patterns 的型別集合（供匯出與測試查表，避免各處自行
# 枚舉 FlowStep 是否排除而彼此漂移）。
CARRIER_PATH_TYPES = frozenset(
    name for name, entry in GRAPH_NODE_TYPES.items() if "carrier_path_patterns" in entry
)

# 完整性集合的共通語意（#99 第三項裁決，2026-09-24）：欄位必須存在；值
# 可為 None（單值）或空清單 []（多值），代表「明確沒有」。此語意對應
# JSON Schema 的 `required`（只管鍵存在，不管值是否為空）。更嚴格的值
# 規則（例如 EVT 的 producers/consumers 不得為空）屬各型別 validator 的
# 附加規則，不放進本節的完整性集合。判斷一律用 `in`（鍵是否存在），不
# 用真值判斷，否則合法的 null/[] 會被誤判為缺漏。


def find_missing_completeness_fields(fields: frozenset[str], entry: dict) -> set[str]:
    """回傳 entry 缺漏的完整性欄位（值為 None 或 [] 仍算存在，非缺漏）。

    共用實作供 validate.py 與其他消費端引用，避免各自重寫「用 `in` 而非
    真值判斷」這條件，一旦分散重寫，某處退化為 `if not entry.get(field)`
    會把合法空值誤判為缺漏卻無測試攔截（見 test_tracking_schema_conformance
    的鑑別對照測試）。
    """
    return {field for field in fields if field not in entry}


# EVT 節點必填欄位（完整性集合，語意見上方共通說明）。
EVT_REQUIRED_FIELDS = frozenset({"id", "name", "canonical_name", "category"})

# PROP／SPEC／UC 識別與顯示最小集（#99 第三項裁決 Q2：c 選項）。
PROP_REQUIRED_FIELDS = frozenset({"id", "title", "status"})
SPEC_REQUIRED_FIELDS = frozenset({"id", "title", "status"})
UC_REQUIRED_FIELDS = frozenset({"id", "title", "status"})

# DomainBundle 識別最小集。個別 domain 的 carrier 是整份 domain-map.md，
# 本集合僅描述單一 bundle 的識別欄位，不含 domain-map 全域結構。
DOMAINBUNDLE_REQUIRED_FIELDS = frozenset({"id", "domain"})

# Ticket 型別不在此設完整性集合：欄位權威在 ticket skill
# （field-semantics.md），本模組僅收錄圖譜消費所需的 id_pattern/carrier
# （見 GRAPH_NODE_TYPES["Ticket"] 的既有註解）。

# 完整性集合總表，供 JSON 匯出與消費端查表使用（單一入口，避免各處各自
# 列舉型別名稱清單而彼此漂移）。FlowStep 完整性集合定義在下方（含
# traverses 的詳細語意說明），此處以底部賦值方式併入，故本行不重複列出。
COMPLETENESS_FIELDS: dict[str, frozenset[str]] = {
    "PROP": PROP_REQUIRED_FIELDS,
    "SPEC": SPEC_REQUIRED_FIELDS,
    "UC": UC_REQUIRED_FIELDS,
    "DomainBundle": DOMAINBUNDLE_REQUIRED_FIELDS,
    "EVT": EVT_REQUIRED_FIELDS,
}

# EVT category 值域：domain_event（狀態變更事實，必有 consumer）或
# process_event（步驟進行中標記，允許無 consumer）。
EVT_CATEGORIES = frozenset({"domain_event", "process_event"})

# FlowStep 於 UC 結構化 flow 區塊內的必填欄位（依首批真實資料實例對齊）。
#
# traverses：本步驟直接觸及的 domain 公開面，值為 domain 名字串清單（0..n）。
# - 欄位必存在；不觸及任何 domain 的純畫面步驟（畫面狀態屬 layer 而非
#   domain）填空清單 []，不得省略欄位
# - 只列直接觸及者；經 domain 依賴邊間接到達的 domain 不列
# - 一個步驟可同時觸及多個 domain（多對多），故為清單而非單值
# - 語意對應 domain map 的「貫穿」：domain 被幾條 flow 貫穿由消費端依本欄位
#   聚合，不另存反向欄位
# - domain 名是否存在於 domain map 不在 schema 層檢查
FLOWSTEP_REQUIRED_FIELDS = frozenset(
    {"id", "name", "next", "branch_from", "return_to", "emits", "consumes", "traverses"}
)

# 併入完整性集合總表（FlowStep 定義晚於 COMPLETENESS_FIELDS 賦值處，故
# 於此補登記，不在上方重複宣告 FLOWSTEP_REQUIRED_FIELDS 的內容）。
COMPLETENESS_FIELDS["FlowStep"] = FLOWSTEP_REQUIRED_FIELDS

# 正向基數（用戶 WRAP 裁決 2026-09-30）：forward_field 在節點上可宣告
# 一個終點（one，frontmatter 為純量）或多個終點（many，為清單）。
# - 由 schema 宣告，不由 frontmatter 寫法或讀取端程式寫死
# - many 的欄位寫成純量時，消費端視為只有一項的清單（如 source_proposal:
#   PROP-001 等同 [PROP-001]）；one 的欄位不接受清單
# - 值域見 EDGE_CARDINALITY_VALUES；每個邊型必帶 forward_cardinality
EDGE_CARDINALITY_ONE = "one"
EDGE_CARDINALITY_MANY = "many"
EDGE_CARDINALITY_VALUES = frozenset({EDGE_CARDINALITY_ONE, EDGE_CARDINALITY_MANY})


def find_edge_types_with_invalid_cardinality(edge_types: dict) -> dict[str, str]:
    """回傳缺少 forward_cardinality 或值不在值域的邊型（名稱 → 原因）。

    判斷用 `in`（鍵是否存在），與完整性集合同一原則，不用真值判斷。
    """
    invalid: dict[str, str] = {}
    for name, entry in edge_types.items():
        if "forward_cardinality" not in entry:
            invalid[name] = "缺少 forward_cardinality"
        elif entry["forward_cardinality"] not in EDGE_CARDINALITY_VALUES:
            invalid[name] = f"forward_cardinality 值域錯誤: {entry['forward_cardinality']!r}"
    return invalid


# 方向性：邊語意上是否有方向，由 schema 宣告，消費端不以鍵名或 class 推導。
# - directed：A 指向 B 與 B 指向 A 是不同的陳述（含尚無反向欄位者）
# - undirected：語意對稱，消費端須做 1-hop symmetric closure（儲存端仍單向）
# - 判準：僅上游明文宣告對稱者為 undirected（目前只有 association／relatedTo）；
#   未宣告者一律 directed。see-also 類（spec／uc／proposal_association）class
#   相同，但上游未宣告對稱，故不因 class 相同而判無向
# - 值域見 EDGE_DIRECTION_VALUES；每個邊型必帶 direction
EDGE_DIRECTION_DIRECTED = "directed"
EDGE_DIRECTION_UNDIRECTED = "undirected"
EDGE_DIRECTION_VALUES = frozenset({EDGE_DIRECTION_DIRECTED, EDGE_DIRECTION_UNDIRECTED})


def find_edge_types_with_invalid_direction(edge_types: dict) -> dict[str, str]:
    """回傳缺少 direction 或值不在值域的邊型（名稱 → 原因）。

    判斷用 `in`（鍵是否存在），與 find_edge_types_with_invalid_cardinality 同一原則。
    """
    invalid: dict[str, str] = {}
    for name, entry in edge_types.items():
        if "direction" not in entry:
            invalid[name] = "缺少 direction"
        elif entry["direction"] not in EDGE_DIRECTION_VALUES:
            invalid[name] = f"direction 值域錯誤: {entry['direction']!r}"
    return invalid


# 語意邊表：A 層（established）+ B 層（proposed），欄位齊全：class / 正向欄位（儲存
# 側）/ 正向基數 / 方向性 / 反向欄位 / 維護方 / status。
GRAPH_EDGE_TYPES = {
    # --- A 層（12 條，established）---
    "provenance": {
        "class": "provenance",
        "forward_field": "source_proposal",
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": "outputs",
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "spec_association": {
        "class": "see-also",
        "forward_field": "related_specs",
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "uc_association": {
        "class": "see-also",
        "forward_field": "related_usecases",
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "proposal_association": {
        "class": "see-also",
        "forward_field": "related_proposals",
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "requirement_impl": {
        "class": "containment",
        "forward_field": "implements_requirements",
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "domain_dependency": {
        "class": "ordering",
        "forward_field": "depends_on_domains",
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "domain_coverage": {
        "class": "containment",
        "forward_field": "source_specs",
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "blood": {
        "class": "containment",
        "forward_field": "parent_id",
        "forward_cardinality": "one",
        "direction": "directed",
        "reverse_field": "children",
        "maintainer": "CLI 自動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "spawn": {
        "class": "provenance",
        "forward_field": "source_ticket",
        "forward_cardinality": "one",
        "direction": "directed",
        "reverse_field": "spawned_tickets",
        "maintainer": "CLI 自動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "blocking": {
        "class": "ordering",
        "forward_field": "blockedBy",
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動/CLI",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "association": {
        # relatedTo：語意無向，消費端做 1-hop symmetric closure；儲存端
        # 仍為單向欄位，故 reverse_field 仍為 None。
        "class": "see-also",
        "forward_field": "relatedTo",
        "forward_cardinality": "many",
        "direction": "undirected",
        "reverse_field": None,
        "maintainer": "手動/CLI",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    "discovery": {
        "class": "provenance",
        "forward_field": "discovered_during",
        "forward_cardinality": "one",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_ESTABLISHED,
    },
    # --- B 層（4 條，proposed）---
    "emission": {
        "class": "dataflow",
        "forward_field": "emits",  # FlowStep.emits → EVT
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_PROPOSED,
    },
    "consumption": {
        "class": "dataflow",
        "forward_field": "consumes",  # EVT → FlowStep.consumes
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_PROPOSED,
    },
    "branching": {
        "class": "ordering",
        "forward_field": "branch_from",
        "forward_cardinality": "one",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_PROPOSED,
    },
    "returning": {
        "class": "ordering",
        # back-edge，排除於 DAG 佈局。
        "forward_field": "return_to",
        "forward_cardinality": "one",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_PROPOSED,
    },
    "bundle_dependency": {
        # DomainBundle → DomainBundle：bundle 層級（跨 domain-map 檔）的
        # 依賴方向。與 domain_dependency（domain 名稱層級、established）
        # 並存且不取代；欄位為選填，缺欄位或 null 皆視為無出邊。
        "class": "ordering",
        "forward_field": "depends_on_bundles",
        "forward_cardinality": "many",
        "direction": "directed",
        "reverse_field": None,
        "maintainer": "手動",
        "layer": GRAPH_LAYER_PROPOSED,
    },
}

BUNDLE_DEPENDENCY_FIELD = GRAPH_EDGE_TYPES["bundle_dependency"]["forward_field"]


def extract_bundle_dependencies(frontmatter: dict) -> list[str]:
    """回傳 DomainBundle frontmatter 的 depends_on_bundles 出邊目標清單。

    欄位缺失或值為 None 代表無出邊；純量視為只有一項的清單（正向基數 many
    的通則，見 EDGE_CARDINALITY_MANY 說明）。
    """
    value = frontmatter.get(BUNDLE_DEPENDENCY_FIELD)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def find_undeclared_domain_names(names: list[str], declared: set[str]) -> list[str]:
    """回傳 names 中不在 declared（DomainBundle 宣告的 domain）內的名稱，保留順序。

    比對為精確字串，不做大小寫或別名正規化：domain 名稱以 DomainBundle 的
    domain 欄位為權威字面。
    """
    return [name for name in names if name not in declared]


# DomainBundle 選填欄位 `path_patterns`：該 bundle 擁有的專案路徑前綴。
# - 值為字串清單。三態：欄位缺席＝該 bundle 未宣告（不得正規化為 []）；顯式 `[]` ＝
#   宣告該 bundle 不擁有任何路徑（無目錄的 bundle 如 History，不得宣告不存在的路徑）；
#   非空清單＝宣告其擁有的前綴。缺席與 `[]` 對 validate 同為合法，差異由
#   `read_path_patterns` 保留給消費端（含「語料全部缺席」整體狀態的判定）。
# - 每個值是專案根目錄相對的字面前綴，不是 glob：POSIX 斜線、不得以 `/` 或 `./`
#   開頭、不得含 `..`、`*`、`?`、`[`、反斜線；以 `/` 結尾為目錄前綴，否則為單一檔案。
# - 比對語意（消費端實作，本模組不比對）：路徑對全部 bundle 的 pattern 取最長前綴
#   命中，由最長者決定歸屬；不同 bundle 的巢狀前綴合法。同一字串不得出現於兩個以上
#   bundle（含同 bundle 內重複），否則最長前綴仍無法決定歸屬。
PATH_PATTERNS_FIELD = "path_patterns"
_PATH_PATTERN_FORBIDDEN_CHARS = frozenset("*?[\\")


def read_path_patterns(frontmatter: dict) -> list | None:
    """讀取 path_patterns：欄位缺席（或值為 None）回傳 None，顯式 `[]` 回傳 `[]`。

    兩者語意不同，不可用 `or []` 之類寫法合併。非清單的值原樣回傳，交由格式檢查報錯。
    """
    return frontmatter.get(PATH_PATTERNS_FIELD)


def check_path_pattern_format(value: object) -> str | None:
    """回傳單一 path_patterns 值的格式問題描述；合法回傳 None。"""
    if not isinstance(value, str) or not value:
        return "必須是非空字串"
    if value.startswith("/") or value.startswith("./"):
        return "不得以 `/` 或 `./` 開頭（須為專案根目錄相對路徑）"
    if ".." in value.split("/"):
        return "不得含 `..` 段"
    if any(ch in _PATH_PATTERN_FORBIDDEN_CHARS for ch in value):
        return "不得含 glob 字元 `*` `?` `[` 或反斜線（字面前綴，非 glob）"
    return None


def find_path_pattern_problems(bundles: dict[str, dict]) -> dict[str, list[str]]:
    """回傳各 bundle 的 path_patterns 格式與重複問題（bundle id → 問題描述清單）。

    bundles：bundle id → frontmatter。跨 bundle 重複會同時回報給所有涉及的 bundle。
    欄位缺席、None 與空清單皆合法。路徑存在性需檔案系統，由呼叫端檢查。
    """
    problems: dict[str, list[str]] = {}
    owners: dict[str, list[str]] = {}
    for bundle_id, frontmatter in bundles.items():
        raw = read_path_patterns(frontmatter)
        if raw is None:
            continue
        if not isinstance(raw, list):
            problems.setdefault(bundle_id, []).append(f"{PATH_PATTERNS_FIELD} 必須是字串清單")
            continue
        for value in raw:
            reason = check_path_pattern_format(value)
            if reason:
                problems.setdefault(bundle_id, []).append(f"{PATH_PATTERNS_FIELD} 值 {value!r}: {reason}")
            else:
                owners.setdefault(value, []).append(bundle_id)
    for value, ids in owners.items():
        if len(ids) < 2:
            continue
        for bundle_id in dict.fromkeys(ids):
            problems.setdefault(bundle_id, []).append(
                f"{PATH_PATTERNS_FIELD} 值 {value!r}: 重複宣告（出現於 {', '.join(ids)}）"
            )
    return problems


def find_missing_path_patterns(frontmatter: dict, exists) -> list[str]:
    """回傳 path_patterns 中指向不存在路徑的值；exists(value) 由呼叫端提供。

    目錄前綴（`/` 結尾）須為目錄，其餘須為檔案。格式不合法的值略過（由格式檢查負責）。
    """
    raw = read_path_patterns(frontmatter)
    if not isinstance(raw, list):
        return []
    return [v for v in raw if check_path_pattern_format(v) is None and not exists(v)]


# 非 domain 路徑清單：不屬任何 DomainBundle、但專案明確宣告的路徑前綴（如 `.claude/`）。
# 載體是專案根目錄相對的獨立設定檔（不是圖節點），位置與鍵名在此宣告，消費端
# （含 App，經 `doc schema export` 匯出）不得寫死。值格式與 path_patterns 完全相同
# （`check_path_pattern_format`）。三態：檔案缺席＝非 domain 側未宣告（合法，
# `read_non_domain_paths` 回 None）；檔案存在且鍵值為 `[]` ＝宣告無非 domain 路徑
# （回 `[]`）；檔案存在但缺鍵或值非清單＝格式錯誤（拋 NonDomainPathsFormatError，
# 不當成缺席）。不正規化缺席與 `[]`，顯示狀態的判定屬消費端。
NON_DOMAIN_PATHS_FILE = "docs/non-domain-paths.yaml"
NON_DOMAIN_PATHS_KEY = "non_domain_path_patterns"


class NonDomainPathsFormatError(ValueError):
    """非 domain 路徑清單檔存在但結構不合法（無法解析、缺鍵、值非清單）。"""


def read_non_domain_paths(project_root) -> list | None:
    """讀取非 domain 路徑清單：檔案缺席回 None，顯式 `[]` 回 `[]`，壞檔拋格式錯誤。"""
    import yaml
    from pathlib import Path

    path = Path(project_root) / NON_DOMAIN_PATHS_FILE
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise NonDomainPathsFormatError(f"YAML 無法解析: {exc}") from exc
    if not isinstance(data, dict) or NON_DOMAIN_PATHS_KEY not in data:
        raise NonDomainPathsFormatError(f"缺少必要鍵 `{NON_DOMAIN_PATHS_KEY}`")
    value = data[NON_DOMAIN_PATHS_KEY]
    if not isinstance(value, list):
        raise NonDomainPathsFormatError(f"`{NON_DOMAIN_PATHS_KEY}` 必須是字串清單")
    return value


def find_non_domain_path_problems(values: list, bundle_patterns: dict[str, list]) -> list[str]:
    """回傳非 domain 路徑清單的格式、同檔重複、與 DomainBundle path_patterns 同字串問題。

    bundle_patterns：bundle id → 該 bundle 的 path_patterns（缺席者不放入）。
    路徑存在性需檔案系統，由呼叫端檢查。
    """
    problems: list[str] = []
    seen: set[str] = set()
    for value in values:
        reason = check_path_pattern_format(value)
        if reason:
            problems.append(f"{NON_DOMAIN_PATHS_KEY} 值 {value!r}: {reason}")
            continue
        if value in seen:
            problems.append(f"{NON_DOMAIN_PATHS_KEY} 值 {value!r}: 同檔重複宣告")
        seen.add(value)
        owners = [bid for bid, pats in bundle_patterns.items() if value in pats]
        if owners:
            problems.append(
                f"{NON_DOMAIN_PATHS_KEY} 值 {value!r}: 與 DomainBundle path_patterns 同字串（{', '.join(owners)}）"
            )
    return problems


def find_dangling_bundle_dependencies(bundles: dict[str, dict]) -> dict[str, list[str]]:
    """回傳出邊指向不存在 bundle 的來源（bundle id → 懸空目標清單）。

    bundles：bundle id → 該 bundle 的 frontmatter；「存在」以此映射的鍵為準。
    """
    dangling: dict[str, list[str]] = {}
    for bundle_id, frontmatter in bundles.items():
        missing = [
            target
            for target in extract_bundle_dependencies(frontmatter)
            if target not in bundles
        ]
        if missing:
            dangling[bundle_id] = missing
    return dangling
