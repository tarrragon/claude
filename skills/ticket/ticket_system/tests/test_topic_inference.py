"""topic_inference 模組的直接單元測試（0.2.1-W3-831）。

與 test_create_topic_selection 的分工：後者走完整 create 流程，驗證推導在
建票路徑上的接線與副作用（映射寫入、輸出訊息、rc）；本檔直接呼叫推導函式，
驗證判準本身的邊界條件。分開的理由是走完整流程的測試每項約 0.13 秒，
要窮舉門檻與平手的邊界組合成本過高，且失敗時無法分辨是判準錯還是接線錯。
"""
from __future__ import annotations

import argparse

import pytest

from ticket_system.lib import topic_inference as ti


class TestPathDepth:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("docs/", 1),
            ("docs/spec/x.md", 3),
            (".claude/hooks/", 2),
            ("/a/b/c/", 3),
            ("", 0),
            (None, 0),
        ],
    )
    def test_counts_non_empty_segments(self, path, expected):
        assert ti.path_depth(path) == expected


class TestInferTopicFromFiles:
    """S2 判準的門檻與平手行為。"""

    def _stub_clusters(self, monkeypatch, clusters):
        monkeypatch.setattr(ti, "build_topic_file_clusters", lambda: clusters)

    def test_returns_none_when_no_paths_given(self, monkeypatch):
        self._stub_clusters(monkeypatch, {"主題": {".claude/a/b/c.py"}})
        assert ti.infer_topic_from_files(None) == (None, None)
        assert ti.infer_topic_from_files("") == (None, None)

    def test_shallow_cluster_path_below_threshold_is_rejected(self, monkeypatch):
        self._stub_clusters(monkeypatch, {"淺層主題": {"docs/"}})
        topic, basis = ti.infer_topic_from_files("docs/spec/deep/file.md")
        assert topic is None
        assert basis is None

    def test_exact_threshold_depth_is_accepted(self, monkeypatch):
        self._stub_clusters(monkeypatch, {"門檻主題": {".claude/hooks/guard.py"}})
        topic, basis = ti.infer_topic_from_files(".claude/hooks/guard.py")
        assert topic == "門檻主題"
        assert "S2" in basis

    def test_specificity_uses_shallower_side(self, monkeypatch):
        """新票路徑很深但主題路徑很淺時，特異性應取淺的一方而遭拒。"""
        self._stub_clusters(monkeypatch, {"淺層主題": {"docs/"}})
        assert ti.infer_topic_from_files("docs/a/b/c/d/e.md") == (None, None)

    def test_deeper_match_wins_over_shallower(self, monkeypatch):
        self._stub_clusters(monkeypatch, {
            "淺主題": {".claude/skills/ticket/"},
            "深主題": {".claude/skills/ticket/lib/target.py"},
        })
        topic, _ = ti.infer_topic_from_files(".claude/skills/ticket/lib/target.py")
        assert topic == "深主題"

    def test_tie_resolved_by_topic_name_not_insertion_order(self, monkeypatch):
        shared = ".claude/skills/ticket/lib/shared.py"
        forward = {"乙主題": {shared}, "甲主題": {shared}}
        backward = {"甲主題": {shared}, "乙主題": {shared}}

        self._stub_clusters(monkeypatch, forward)
        first, _ = ti.infer_topic_from_files(shared)
        self._stub_clusters(monkeypatch, backward)
        second, _ = ti.infer_topic_from_files(shared)

        assert first == second

    def test_multiple_input_paths_any_may_match(self, monkeypatch):
        self._stub_clusters(monkeypatch, {"主題": {".claude/lib/target.py"}})
        topic, basis = ti.infer_topic_from_files("docs/unrelated.md,.claude/lib/target.py")
        assert topic == "主題"
        assert ".claude/lib/target.py" in basis


class TestInferTopic:
    """S1 優先於 S2 的短路行為。"""

    def _stub(self, monkeypatch, assignments, clusters=None):
        monkeypatch.setattr(
            "ticket_system.lib.topic_assignments.list_assignments",
            lambda: assignments,
        )
        monkeypatch.setattr(ti, "build_topic_file_clusters", lambda: clusters or {})

    def _args(self, **kw):
        base = dict(source_ticket=None, parent=None, where_files=None, type="IMP")
        base.update(kw)
        return argparse.Namespace(**base)

    def test_source_ticket_inheritance(self, monkeypatch):
        self._stub(monkeypatch, {"X-W1-001": "上游主題"})
        topic, basis = ti.infer_topic(self._args(source_ticket="X-W1-001"))
        assert topic == "上游主題"
        assert "S1" in basis and "source_ticket" in basis

    def test_parent_inheritance(self, monkeypatch):
        self._stub(monkeypatch, {"X-W1-001": "父票主題"})
        topic, basis = ti.infer_topic(self._args(parent="X-W1-001"))
        assert topic == "父票主題"
        assert "parent_id" in basis

    def test_source_ticket_takes_precedence_over_parent(self, monkeypatch):
        self._stub(monkeypatch, {"S-1": "來源主題", "P-1": "父票主題"})
        topic, _ = ti.infer_topic(self._args(source_ticket="S-1", parent="P-1"))
        assert topic == "來源主題"

    def test_falls_through_to_s2_when_upstream_has_no_topic(self, monkeypatch):
        self._stub(
            monkeypatch,
            {"other": "無關主題"},
            {"叢集主題": {".claude/lib/target.py"}},
        )
        topic, basis = ti.infer_topic(
            self._args(source_ticket="X-W1-001", where_files=".claude/lib/target.py")
        )
        assert topic == "叢集主題"
        assert "S2" in basis

    def test_s1_short_circuits_without_consulting_clusters(self, monkeypatch):
        """S1 命中時不得呼叫 S2——那是 351 毫秒的全掃描，短路是成本控制的主要手段。"""
        called = []
        monkeypatch.setattr(
            "ticket_system.lib.topic_assignments.list_assignments",
            lambda: {"X-W1-001": "上游主題"},
        )
        monkeypatch.setattr(
            ti, "build_topic_file_clusters", lambda: called.append(1) or {}
        )
        ti.infer_topic(self._args(source_ticket="X-W1-001", where_files=".claude/a/b.py"))
        assert called == []


class TestRequiresTopicAssignment:
    @pytest.mark.parametrize(
        "ticket_type,expected",
        [("ANA", True), ("ana", True), ("IMP", False), ("DOC", False), (None, False)],
    )
    def test_only_ana_requires_assignment(self, ticket_type, expected):
        args = argparse.Namespace(type=ticket_type)
        assert ti.requires_topic_assignment(args) is expected


class TestValidateTopicSelection:
    """顯式參數的合法性檢查，不觸及任何持久化。"""

    def _args(self, **kw):
        base = dict(topic=None, new_topic=None, no_topic=False)
        base.update(kw)
        return argparse.Namespace(**base)

    def test_no_topic_conflicts_with_topic(self):
        topic, error, new_topic = ti.validate_topic_selection(
            self._args(no_topic=True, topic="X")
        )
        assert topic is None and new_topic is None
        assert "--no-topic" in error

    def test_no_topic_conflicts_with_new_topic(self):
        _, error, _ = ti.validate_topic_selection(
            self._args(no_topic=True, new_topic="X")
        )
        assert "--no-topic" in error

    def test_topic_conflicts_with_new_topic(self):
        _, error, _ = ti.validate_topic_selection(
            self._args(topic="X", new_topic="Y")
        )
        assert "--topic" in error and "--new-topic" in error

    def test_blank_new_topic_rejected(self):
        _, error, _ = ti.validate_topic_selection(self._args(new_topic="   "))
        assert error is not None

    def test_all_none_returns_empty_triple(self):
        assert ti.validate_topic_selection(self._args()) == (None, None, None)

    def test_no_topic_alone_returns_empty_triple(self):
        """--no-topic 不指定主題，驗證層不視為錯誤——它的效果在報告層。"""
        assert ti.validate_topic_selection(self._args(no_topic=True)) == (None, None, None)
