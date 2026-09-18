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

# test-map 掃描的測試目錄清單（相對 project_root）。
# 本專案為 Flutter：test/ 為單元/widget 測試，integration_test/ 為裝置測試。
# 若未來專案改用其他佈局，改此清單即可，不需改 test_map.py 邏輯。
TEST_SCAN_DIRS = ["test", "integration_test"]

# test-map 檔案掃描辨識的測試檔副檔名（含 dart，涵蓋 Flutter 專案）。
TEST_FILE_EXTENSIONS = (".dart", ".js", ".ts", ".py", ".test.js", ".spec.js")
