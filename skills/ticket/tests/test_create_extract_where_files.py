"""W11-026: extract_where_files 對 ticket where 欄位的型別防護測試。

舊 ticket（v0.16/v0.17 早期）的 where 為字串格式，新格式為 dict {layer, files}。
_print_parallel_analysis_result（L1405 child_info）與 _print_cognitive_load_assessment（L1456 new_ticket）
取 where.files 時必須相容兩種格式，否則 AttributeError crash。

涵蓋：
- where 為 dict 且含 files → 取 .get("files")（原行為）
- where 為 dict 但無 files → 空 list
- where 為 str（legacy） → 空 list（舊格式無 files 概念）
- where 為 None / 缺失 / ticket_data 為 None → 空 list
- 回歸：舊格式 ticket 不再 AttributeError
"""

from ticket_system.lib.create_reporter import extract_where_files


class TestExtractWhereFiles:
    """where.files 型別防護"""

    def test_where_is_dict_with_files_returns_files(self):
        ticket = {"where": {"layer": "core", "files": ["a.py", "b.py"]}}
        assert extract_where_files(ticket) == ["a.py", "b.py"]

    def test_where_is_dict_without_files_returns_empty(self):
        ticket = {"where": {"layer": "core"}}
        assert extract_where_files(ticket) == []

    def test_where_is_dict_files_none_returns_empty(self):
        ticket = {"where": {"layer": "core", "files": None}}
        assert extract_where_files(ticket) == []

    def test_where_is_legacy_string_returns_empty(self):
        # 舊格式：where 直接為字串，無 files 概念
        ticket = {"where": "core/errors"}
        assert extract_where_files(ticket) == []

    def test_where_is_none_returns_empty(self):
        ticket = {"where": None}
        assert extract_where_files(ticket) == []

    def test_where_missing_returns_empty(self):
        ticket = {}
        assert extract_where_files(ticket) == []

    def test_ticket_data_none_returns_empty(self):
        assert extract_where_files(None) == []

    def test_where_empty_string_returns_empty(self):
        ticket = {"where": ""}
        assert extract_where_files(ticket) == []

    def test_where_dict_files_empty_list_returns_empty(self):
        ticket = {"where": {"files": []}}
        assert extract_where_files(ticket) == []


class TestRegressionLegacyTicketDoesNotCrash:
    """W11-026 回歸：舊字串格式 ticket 不再 AttributeError

    觸發點：
    - L1405: child_info.get("where", {}).get("files", []) → AttributeError if where is str
    - L1456: new_ticket.get("where", {}).get("files") or [] → 同上
    """

    def test_legacy_string_where_child_info_no_attribute_error(self):
        # 修復前：child_info.get("where", {}).get("files", []) 對 str 會 AttributeError
        child_info = {"where": "ui/popup", "blockedBy": [], "title": "legacy child"}
        # 不 crash 即通過
        files = extract_where_files(child_info)
        assert files == []

    def test_legacy_string_where_new_ticket_no_attribute_error(self):
        # 修復前：new_ticket.get("where", {}).get("files") or [] 對 str 會 AttributeError
        new_ticket = {"where": "core/errors"}
        files = extract_where_files(new_ticket)
        assert files == []
