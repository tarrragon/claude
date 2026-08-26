"""
relatedTo 反向索引測試（0.2.1-W3-1067）

裁決一（0.2.1-W3-1059）：relatedTo 儲存單向，消費端做 1-hop symmetric union。
本模組驗證：反向索引正確建立（O(1) 查表，非全庫掃描）、1-hop 邊界（禁遞移）、
單向資料下的對稱查詢結果。
"""

from ticket_system.lib.relatedto_index import (
    build_reverse_index,
    get_symmetric_related_to,
    reset_reverse_index_cache,
)


def _write_ticket(tickets_dir, ticket_id, related_to=None):
    if related_to:
        items = "\n".join(f"  - {r}" for r in related_to)
        related_yaml = f"relatedTo:\n{items}\n"
    else:
        related_yaml = "relatedTo: []\n"
    content = f"---\nid: {ticket_id}\n{related_yaml}---\n\nBody\n"
    (tickets_dir / f"{ticket_id}.md").write_text(content, encoding="utf-8")


class TestBuildReverseIndex:
    """反向索引建立：被引用方 -> 引用方列表"""

    def test_single_directed_edge_produces_reverse_entry(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ticket_system.lib.relatedto_index.get_tickets_dir", lambda version: tmp_path
        )
        reset_reverse_index_cache()
        _write_ticket(tmp_path, "0.31.0-W1-001", related_to=["0.31.0-W1-002"])
        _write_ticket(tmp_path, "0.31.0-W1-002")

        reverse = build_reverse_index("0.31.0")

        assert reverse.get("0.31.0-W1-002") == ["0.31.0-W1-001"]
        assert "0.31.0-W1-001" not in reverse

    def test_no_related_to_produces_empty_index(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ticket_system.lib.relatedto_index.get_tickets_dir", lambda version: tmp_path
        )
        reset_reverse_index_cache()
        _write_ticket(tmp_path, "0.31.0-W1-001")

        reverse = build_reverse_index("0.31.0")

        assert reverse == {}

    def test_missing_tickets_dir_returns_empty_index(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ticket_system.lib.relatedto_index.get_tickets_dir",
            lambda version: tmp_path / "does-not-exist",
        )
        reset_reverse_index_cache()

        reverse = build_reverse_index("0.31.0")

        assert reverse == {}


class TestSymmetricUnion1Hop:
    """1-hop symmetric union：forward ∪ reverse，禁遞移"""

    def test_unidirectional_edge_is_visible_from_both_sides(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ticket_system.lib.relatedto_index.get_tickets_dir", lambda version: tmp_path
        )
        reset_reverse_index_cache()
        _write_ticket(tmp_path, "0.31.0-W1-001", related_to=["0.31.0-W1-002"])
        _write_ticket(tmp_path, "0.31.0-W1-002")

        # A -> B：A 自身 forward 已含 B
        result_a = get_symmetric_related_to("0.31.0", "0.31.0-W1-001", forward=["0.31.0-W1-002"])
        assert result_a == ["0.31.0-W1-002"]

        # B 儲存單向下 forward 為空，但 union 後應看得到 A（裁決一核心訴求）
        result_b = get_symmetric_related_to("0.31.0", "0.31.0-W1-002", forward=[])
        assert result_b == ["0.31.0-W1-001"]

    def test_transitive_closure_is_not_followed(self, monkeypatch, tmp_path):
        """A -> B -> C：查 A 時不得因 1-hop 規則吸入 C（禁遞移）"""
        monkeypatch.setattr(
            "ticket_system.lib.relatedto_index.get_tickets_dir", lambda version: tmp_path
        )
        reset_reverse_index_cache()
        _write_ticket(tmp_path, "0.31.0-W1-001", related_to=["0.31.0-W1-002"])
        _write_ticket(tmp_path, "0.31.0-W1-002", related_to=["0.31.0-W1-003"])
        _write_ticket(tmp_path, "0.31.0-W1-003")

        result_a = get_symmetric_related_to("0.31.0", "0.31.0-W1-001", forward=["0.31.0-W1-002"])
        assert result_a == ["0.31.0-W1-002"]
        assert "0.31.0-W1-003" not in result_a

        # C 不遞移吸收 A（C 只被 B 直接引用，B 到 A 是另一條獨立的 1-hop 邊）
        result_c = get_symmetric_related_to("0.31.0", "0.31.0-W1-003", forward=[])
        assert result_c == ["0.31.0-W1-002"]
        assert "0.31.0-W1-001" not in result_c

    def test_self_reference_excluded_from_result(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ticket_system.lib.relatedto_index.get_tickets_dir", lambda version: tmp_path
        )
        reset_reverse_index_cache()
        _write_ticket(tmp_path, "0.31.0-W1-001", related_to=["0.31.0-W1-001"])

        result = get_symmetric_related_to("0.31.0", "0.31.0-W1-001", forward=["0.31.0-W1-001"])
        assert "0.31.0-W1-001" not in result

    def test_mutual_reference_dedups_to_single_entry(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            "ticket_system.lib.relatedto_index.get_tickets_dir", lambda version: tmp_path
        )
        reset_reverse_index_cache()
        _write_ticket(tmp_path, "0.31.0-W1-001", related_to=["0.31.0-W1-002"])
        _write_ticket(tmp_path, "0.31.0-W1-002", related_to=["0.31.0-W1-001"])

        result = get_symmetric_related_to("0.31.0", "0.31.0-W1-001", forward=["0.31.0-W1-002"])
        assert result == ["0.31.0-W1-002"]


class TestReverseIndexCache:
    """process-scoped 快取：同一 version 重複呼叫不重掃檔案系統"""

    def test_cache_reused_across_calls_until_reset(self, monkeypatch, tmp_path):
        call_count = {"n": 0}

        def counting_get_tickets_dir(version):
            call_count["n"] += 1
            return tmp_path

        monkeypatch.setattr(
            "ticket_system.lib.relatedto_index.get_tickets_dir", counting_get_tickets_dir
        )
        reset_reverse_index_cache()
        _write_ticket(tmp_path, "0.31.0-W1-001", related_to=["0.31.0-W1-002"])

        build_reverse_index("0.31.0")
        build_reverse_index("0.31.0")

        assert call_count["n"] == 1

        reset_reverse_index_cache()
        build_reverse_index("0.31.0")
        assert call_count["n"] == 2
