"""W11-003.7: _parse_cli_args_to_config 對 parent ticket where/who 的型別防護測試。

舊 ticket（v0.16/v0.17 早期）的 where/who 為字串格式，新格式為 dict。
_parse_cli_args_to_config 載入 parent ticket 時必須相容兩種格式，否則 AttributeError crash。

涵蓋：
- parent.where 為 dict → 取 .get("layer")（原行為）
- parent.where 為 str → 直接使用（legacy）
- parent.where 為 None / 缺失 → DEFAULT_UNDEFINED_VALUE
- parent.who 同類三種格式
"""

from ticket_system.commands.create import (
    _inherit_parent_where_layer,
    _inherit_parent_who,
)
from ticket_system.lib.constants import DEFAULT_UNDEFINED_VALUE


class TestInheritParentWhereLayer:
    """parent.where 型別防護"""

    def test_where_is_dict_returns_layer(self):
        parent = {"where": {"layer": "core/errors", "files": ["a.py"]}}
        assert _inherit_parent_where_layer(parent) == "core/errors"

    def test_where_is_legacy_string_returns_string(self):
        # 舊格式：where 直接為字串
        parent = {"where": "core/errors"}
        assert _inherit_parent_where_layer(parent) == "core/errors"

    def test_where_is_none_returns_default(self):
        parent = {"where": None}
        assert _inherit_parent_where_layer(parent) == DEFAULT_UNDEFINED_VALUE

    def test_where_missing_returns_default(self):
        parent = {}
        assert _inherit_parent_where_layer(parent) == DEFAULT_UNDEFINED_VALUE

    def test_parent_ticket_none_returns_default(self):
        assert _inherit_parent_where_layer(None) == DEFAULT_UNDEFINED_VALUE

    def test_where_dict_without_layer_returns_default(self):
        parent = {"where": {"files": ["a.py"]}}
        assert _inherit_parent_where_layer(parent) == DEFAULT_UNDEFINED_VALUE

    def test_where_empty_string_returns_default(self):
        parent = {"where": ""}
        assert _inherit_parent_where_layer(parent) == DEFAULT_UNDEFINED_VALUE


class TestInheritParentWho:
    """parent.who 型別防護"""

    def test_who_is_dict_returns_current(self):
        parent = {"who": {"current": "thyme-python-developer", "history": {}}}
        assert _inherit_parent_who(parent) == "thyme-python-developer"

    def test_who_is_legacy_string_returns_string(self):
        # 舊格式：who 直接為字串
        parent = {"who": "thyme-python-developer"}
        assert _inherit_parent_who(parent) == "thyme-python-developer"

    def test_who_is_none_returns_pending(self):
        parent = {"who": None}
        assert _inherit_parent_who(parent) == "pending"

    def test_who_missing_returns_pending(self):
        parent = {}
        assert _inherit_parent_who(parent) == "pending"

    def test_parent_ticket_none_returns_pending(self):
        assert _inherit_parent_who(None) == "pending"

    def test_who_dict_without_current_returns_pending(self):
        parent = {"who": {"history": {}}}
        assert _inherit_parent_who(parent) == "pending"

    def test_who_empty_string_returns_pending(self):
        parent = {"who": ""}
        assert _inherit_parent_who(parent) == "pending"


class TestRegressionLegacyParentTicketDoesNotCrash:
    """W11-003.7 回歸：舊格式 parent ticket 不再 AttributeError"""

    def test_legacy_string_where_no_attribute_error(self):
        # 修復前：parent_ticket.get("where", {}).get("layer") 對 str 會 AttributeError
        parent = {"where": "ui/popup", "who": "pending"}
        # 不 crash 即通過
        layer = _inherit_parent_where_layer(parent)
        who = _inherit_parent_who(parent)
        assert layer == "ui/popup"
        assert who == "pending"
