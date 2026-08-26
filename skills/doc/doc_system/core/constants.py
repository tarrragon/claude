"""doc_system 共用常數。"""

# frontmatter 中可能包含引用的欄位清單（nav/query 共用）。
# 與 tracking_schema.py 的 GRAPH_EDGE_TYPES 合流：本清單為既有 nav/query
# 消費端使用的欄位集合，GRAPH_EDGE_TYPES 為圖譜語意邊的完整正向欄位集合
# （含 doc_system 未涵蓋、歸屬 ticket_system 的 Ticket 邊）；本清單只新增
# doc_system 節點（PROP/SPEC/UC/DomainBundle）既有但原缺列的引用欄位。
REF_FIELDS = [
    "spec_refs",
    "usecase_refs",
    "ticket_refs",
    "source_proposal",
    "related_specs",
    "related_usecases",
    "related_proposals",
    "outputs",
    "producers",
    "consumers",
    "implements_requirements",
    "depends_on_domains",
    "source_specs",
]

# 標題顯示截斷閾值
TITLE_MAX_DISPLAY_LEN = 27
